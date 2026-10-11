"""
Jev Bench - TypeSafe Jev Model Evaluation Harness

Evaluates Jev 1.3 model on OpenRouter for structured JSON generation tasks.
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import jsonschema
import typer
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Load environment variables
load_dotenv()

console = Console()
app = typer.Typer(help="Jev Bench - Evaluate TypeSafe Jev model on OpenRouter")


# ─── Configuration ──────────────────────────────────────────────────────────


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: str = ""
    model_id: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    temperature: float = 0.0
    max_tokens: int = 4096
    request_timeout: int = 60
    max_retries: int = 3
    save_raw_responses: bool = False
    output_dir: Path = Path("results")
    log_level: str = "INFO"


def get_settings() -> Settings:
    """Get settings instance, loading from .env if available."""
    return Settings()  # type: ignore


# Global settings instance (lazy-loaded)
_settings: Optional[Settings] = None


def settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = get_settings()
    return _settings


# ─── Data Models ────────────────────────────────────────────────────────────


@dataclass
class EvaluationResult:
    schema_name: str
    schema_path: str
    success: bool
    validation_errors: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw_response: Optional[str] = None
    generated_json: Optional[dict] = None
    error: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass
class SchemaTestCase:
    name: str
    path: Path
    schema: dict
    prompt: str


# ─── Schema Loading ─────────────────────────────────────────────────────────


def load_schema(path: Path) -> dict:
    """Load and parse a JSON schema file."""
    with open(path) as f:
        return json.load(f)


def build_prompt(schema: dict, schema_name: str) -> str:
    """Build a prompt for the model to generate JSON matching the schema."""
    schema_str = json.dumps(schema, indent=2)
    return f"""Generate a valid JSON object that strictly conforms to the following JSON Schema.
Output ONLY the JSON object, no explanations, no markdown, no extra text.

Schema ({schema_name}):
{schema_str}

JSON Output:"""


def discover_schemas(schema_dir: Path = Path("schemas")) -> list[SchemaTestCase]:
    """Discover all schema test cases in the schemas directory."""
    test_cases = []
    for schema_path in sorted(schema_dir.glob("*.json")):
        schema = load_schema(schema_path)
        name = schema_path.stem
        prompt = build_prompt(schema, name)
        test_cases.append(SchemaTestCase(name=name, path=schema_path, schema=schema, prompt=prompt))
    return test_cases


# ─── OpenRouter Client ──────────────────────────────────────────────────────


class OpenRouterClient:
    """Client for calling OpenRouter API (OpenAI-compatible)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/jev-bench",
            "X-Title": "Jev Bench",
        }

    async def generate(
        self, prompt: str, schema: Optional[dict] = None
    ) -> tuple[str, dict]:
        """
        Generate completion from OpenRouter.

        Returns: (raw_response_text, usage_dict)
        """
        payload = {
            "model": self.settings.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
        }

        # Add structured output if schema provided (OpenRouter supports this)
        if schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "schema": schema, "strict": True},
            }

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            for attempt in range(self.settings.max_retries):
                try:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self.headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()

                    content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})

                    return content, {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    }

                except httpx.HTTPStatusError as e:
                    if e.response.status_code >= 500 and attempt < self.settings.max_retries - 1:
                        await asyncio.sleep(2**attempt)
                        continue
                    raise
                except httpx.RequestError:
                    if attempt < self.settings.max_retries - 1:
                        await asyncio.sleep(2**attempt)
                        continue
                    raise

        raise RuntimeError("Max retries exceeded")


# ─── Validation ─────────────────────────────────────────────────────────────


def validate_json(json_str: str, schema: dict) -> tuple[bool, list[str], Optional[dict]]:
    """
    Validate JSON string against schema.

    Returns: (is_valid, error_messages, parsed_json)
    """
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"], None

    try:
        jsonschema.validate(instance=parsed, schema=schema)
        return True, [], parsed
    except jsonschema.ValidationError as e:
        return False, [e.message], parsed
    except jsonschema.SchemaError as e:
        return False, [f"Invalid schema: {e}"], parsed


# ─── Evaluation ─────────────────────────────────────────────────────────────


async def evaluate_schema(
    client: OpenRouterClient, test_case: SchemaTestCase, dry_run: bool = False
) -> EvaluationResult:
    """Evaluate a single schema test case."""
    start_time = time.perf_counter()

    if dry_run:
        console.print(f"[yellow]DRY RUN[/yellow] Would evaluate: {test_case.name}")
        return EvaluationResult(
            schema_name=test_case.name,
            schema_path=str(test_case.path),
            success=True,
            latency_ms=0,
        )

    try:
        raw_response, usage = await client.generate(test_case.prompt, test_case.schema)
        latency_ms = (time.perf_counter() - start_time) * 1000

        is_valid, errors, parsed = validate_json(raw_response, test_case.schema)

        return EvaluationResult(
            schema_name=test_case.name,
            schema_path=str(test_case.path),
            success=is_valid,
            validation_errors=errors,
            latency_ms=latency_ms,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            raw_response=raw_response if settings().save_raw_responses else None,
            generated_json=parsed,
        )

    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return EvaluationResult(
            schema_name=test_case.name,
            schema_path=str(test_case.path),
            success=False,
            validation_errors=[f"Request failed: {e}"],
            latency_ms=latency_ms,
            error=str(e),
        )


async def run_evaluation(
    schema_names: Optional[list[str]] = None,
    dry_run: bool = False,
    model_override: Optional[str] = None,
) -> list[EvaluationResult]:
    """Run evaluation on specified schemas or all schemas."""
    test_cases = discover_schemas()

    if schema_names:
        test_cases = [tc for tc in test_cases if tc.name in schema_names]
        if not test_cases:
            console.print(f"[red]No matching schemas found for: {schema_names}[/red]")
            return []

    # Override model if specified
    client_settings = settings()
    if model_override:
        # Create a new Settings instance with overridden model
        client_settings = Settings(
            openrouter_api_key=client_settings.openrouter_api_key,
            model_id=model_override,
        )  # type: ignore

    client = OpenRouterClient(client_settings)

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Evaluating schemas...", total=len(test_cases))

        for test_case in test_cases:
            progress.update(task, description=f"Evaluating {test_case.name}...")
            result = await evaluate_schema(client, test_case, dry_run)
            results.append(result)
            progress.advance(task)

    return results


# ─── Reporting ──────────────────────────────────────────────────────────────


def print_results(results: list[EvaluationResult]) -> None:
    """Print evaluation results as a rich table."""
    table = Table(title="Jev Bench Evaluation Results")
    table.add_column("Schema", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Latency (ms)", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Errors", style="red")

    for r in results:
        status = "[green]✓ PASS[/green]" if r.success else "[red]✗ FAIL[/red]"
        tokens = f"{r.prompt_tokens} → {r.completion_tokens}"
        errors = "; ".join(r.validation_errors) if r.validation_errors else "-"
        table.add_row(r.schema_name, status, f"{r.latency_ms:.1f}", tokens, errors)

    console.print(table)

    # Summary
    passed = sum(1 for r in results if r.success)
    total = len(results)
    console.print(f"\n[bold]Summary:[/bold] {passed}/{total} passed")


def save_results(results: list[EvaluationResult], output_dir: Path) -> Path:
    """Save results to JSONL file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = uuid.uuid4().hex[:8]
    filepath = output_dir / f"eval_{timestamp}_{run_id}.jsonl"

    with open(filepath, "w") as f:
        f.writelines(json.dumps(r.__dict__) + "\n" for r in results)

    console.print(f"[green]Results saved to:[/green] {filepath}")
    return filepath


# ─── CLI Commands ───────────────────────────────────────────────────────────


# Module-level typer option/argument instances to avoid B008
_schema_opt = typer.Option(None, "--schema", "-s", help="Schema name(s) to evaluate (can repeat)")
_all_opt = typer.Option(False, "--all", "-a", help="Evaluate all schemas")
_model_opt = typer.Option(None, "--model", "-m", help="Override model ID")
_dry_run_opt = typer.Option(False, "--dry-run", help="Dry run without API calls")
_save_raw_opt = typer.Option(False, "--save-raw", help="Save raw model responses")
_output_opt = typer.Option(None, "--output", "-o", help="Output directory")
_schema_arg = typer.Argument(..., help="Path to schema file")


@app.command()
def evaluate(
    schema: Optional[list[str]] = _schema_opt,
    all_schemas: bool = _all_opt,
    model: Optional[str] = _model_opt,
    dry_run: bool = _dry_run_opt,
    save_raw: bool = _save_raw_opt,
    output_dir: Optional[Path] = _output_opt,
):
    """Run evaluation on Jev model."""
    if not all_schemas and not schema:
        console.print("[red]Error: Specify --all or --schema[/red]")
        raise typer.Exit(1)

    if schema and all_schemas:
        console.print("[red]Error: Cannot use --schema and --all together[/red]")
        raise typer.Exit(1)

    # Override settings
    current_settings = settings()
    if save_raw:
        current_settings.save_raw_responses = True
    if output_dir:
        current_settings.output_dir = output_dir

    schema_names = None if all_schemas else schema

    console.print(f"[bold]Jev Bench[/bold] - Model: {model or current_settings.model_id}")
    console.print(f"Schemas: {'all' if all_schemas else schema_names}")

    results = asyncio.run(run_evaluation(schema_names, dry_run, model))

    print_results(results)

    if not dry_run:
        save_results(results, current_settings.output_dir)

    # Exit code based on results
    if any(not r.success for r in results):
        raise typer.Exit(1)


@app.command()
def list_schemas():
    """List available schema test cases."""
    test_cases = discover_schemas()
    table = Table(title="Available Schema Test Cases")
    table.add_column("Name", style="cyan")
    table.add_column("Path")
    table.add_column("Required Fields")

    for tc in test_cases:
        required = tc.schema.get("required", [])
        table.add_row(tc.name, str(tc.path), ", ".join(required) if required else "none")

    console.print(table)


@app.command()
def validate_schema(schema_path: Path = _schema_arg):
    """Validate a schema file for correctness."""
    try:
        schema = load_schema(schema_path)
        jsonschema.Draft7Validator.check_schema(schema)
        console.print(f"[green]✓[/green] Schema is valid: {schema_path}")
    except jsonschema.SchemaError as e:
        console.print(f"[red]✗[/red] Invalid schema: {e}")
        raise typer.Exit(1) from None
    except (OSError, json.JSONDecodeError) as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1) from None


if __name__ == "__main__":
    app()

