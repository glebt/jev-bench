---
name: jev-bench
description: Skills for working with the Jev Bench evaluation project
category: evaluation
version: 1.0.0
---

# Jev Bench Skills

This skill provides commands and workflows for evaluating the TypeSafe Jev 1.3 model on OpenRouter.

## Project Commands

### Run Evaluations

```bash
# Run all schema tests (dry run - no API calls)
python eval.py evaluate --all --dry-run

# Run all schema tests (requires OPENROUTER_API_KEY in .env)
python eval.py evaluate --all

# Run specific schema
python eval.py evaluate --schema simple

# Run with custom model
python eval.py evaluate --all --model jev-1.3-typesafe

# Save raw model responses
python eval.py evaluate --all --save-raw
```

### Schema Management

```bash
# List available schemas
python eval.py list-schemas

# Validate a schema file
python eval.py validate-schema schemas/simple.json
```

## Development Workflow

### 1. Add New Schema Test Case

1. Create JSON schema in `schemas/<name>.json`
2. Add test case in `tests/test_evaluator.py`
3. Run validation: `python eval.py validate-schema schemas/<name>.json`
4. Test with dry run: `python eval.py evaluate --schema <name> --dry-run`

### 2. Run Full Evaluation

```bash
# Copy env template and add your API key
cp .env.example .env
# Edit .env with your OPENROUTER_API_KEY

# Run evaluation
python eval.py evaluate --all
```

### 3. Check Results

Results are saved to `results/eval_<timestamp>_<run_id>.jsonl`

```bash
# View latest results
cat results/eval_*.jsonl | jq -s '.[] | {schema: .schema_name, success: .success, latency_ms: .latency_ms, tokens: .total_tokens}'
```

## Testing

```bash
# Run unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=eval --cov-report=term-missing
```

## Linting & Formatting

```bash
# Check style
ruff check .

# Auto-fix
ruff check . --fix

# Format code
ruff format .

# Type check
mypy eval.py
```

## Project Structure

```
jev-bench/
├── eval.py              # Main CLI entry point
├── CLAUDE.md            # AI assistant instructions
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── .gitignore           # Git ignore rules
├── schemas/             # JSON Schema test cases
│   ├── simple.json
│   ├── nested.json
│   └── complex.json
├── tests/               # Unit tests
│   └── test_evaluator.py
├── results/             # Evaluation outputs (gitignored)
└── skills/              # Hermes Agent skills
    └── jev-bench.md     # This file
```

## Key Functions (for programmatic use)

```python
from eval import (
    discover_schemas,
    load_schema,
    build_prompt,
    validate_json,
    run_evaluation,
    OpenRouterClient,
    Settings,
)

# Discover all test cases
test_cases = discover_schemas()

# Load specific schema
schema = load_schema(Path("schemas/simple.json"))

# Build prompt for schema
prompt = build_prompt(schema, "simple")

# Validate JSON against schema
is_valid, errors, parsed = validate_json(json_string, schema)

# Run evaluation programmatically
results = asyncio.run(run_evaluation(schema_names=["simple"]))
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | Yes | - | OpenRouter API key |
| `MODEL_ID` | No | `nvidia/nemotron-3-ultra-550b-a55b:free` | Model to evaluate |
| `TEMPERATURE` | No | `0.0` | Sampling temperature |
| `MAX_TOKENS` | No | `4096` | Max completion tokens |
| `REQUEST_TIMEOUT` | No | `60` | HTTP timeout (seconds) |
| `MAX_RETRIES` | No | `3` | Max retry attempts |
| `SAVE_RAW_RESPONSES` | No | `false` | Save raw model outputs |
| `OUTPUT_DIR` | No | `results` | Output directory |
| `LOG_LEVEL` | No | `INFO` | Logging level |

## Adding Custom Evaluation Metrics

To add new metrics, extend `EvaluationResult` dataclass and update `evaluate_schema()`:

```python
@dataclass
class EvaluationResult:
    # ... existing fields ...
    custom_metric: float = 0.0  # Add your metric
```

Then in `evaluate_schema()`:
```python
result.custom_metric = compute_custom_metric(parsed, schema)
```

## OpenRouter Model Configuration

The project uses OpenRouter's API with **automatic endpoint detection**:

- **Standard models** (default): Uses `https://openrouter.ai/api/v1/chat/completions` with OpenAI-compatible format
- **Jev models** (auto-detected): Uses `https://openrouter.ai/api/alpha/decisions` with Jev System One format

The client automatically detects Jev models by checking if "jev" appears in the model ID (case-insensitive).

### For Jev 1.3 TypeSafe:

1. Use the correct model ID on OpenRouter (e.g., `jev-1.3-typesafe`)
2. Set `MODEL_ID` in `.env` or pass via `--model` flag
3. The client will automatically:
   - Switch to the `/decisions` endpoint
   - Use `input` + `schema` payload format
   - Parse Jev's `{ "output": {...}, "usage": {...} }` response

## Troubleshooting

### API Key Issues
```bash
# Verify API key is set
echo $OPENROUTER_API_KEY

# Test with curl
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  https://openrouter.ai/api/v1/models
```

### Schema Validation Errors
- Ensure schema uses JSON Schema Draft 7
- Check required fields are present
- Validate with `python eval.py validate-schema <schema>`

### Rate Limiting
- Increase `REQUEST_TIMEOUT` and `MAX_RETRIES` in `.env`
- Add delay between requests if needed