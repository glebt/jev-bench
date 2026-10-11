# CLAUDE.md - AI Assistant Instructions for Jev Bench

This file provides guidance for AI assistants (Claude Code, Codex, Hermes, etc.) working on this project.

## Project Context

- **Purpose**: Evaluate TypeSafe Jev 1.3 model on OpenRouter for structured JSON generation
- **Model**: `nvidia/nemotron-3-ultra-550b-a55b:free` (or Jev 1.3 specific model ID on OpenRouter)
- **Primary Task**: Build evaluation harness, run benchmarks, analyze results

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run evaluations
python eval.py --all                    # All schemas
python eval.py --schema schemas/simple.json  # Single schema
python eval.py --help                   # Show all options

# Lint/format
ruff check .
ruff format .
mypy eval.py

# Tests
pytest tests/ -v
```

## Code Style & Conventions

- **Python**: 3.11+, type hints required, Pydantic for validation
- **Formatting**: Ruff (line-length=100, target-version=py311)
- **Imports**: Absolute imports, grouped (stdlib, third-party, local)
- **Async**: Use `asyncio` + `httpx` for API calls
- **Config**: Pydantic Settings from `.env`

## Project Structure Rules

```
jev-bench/
├── eval.py              # Main entry point - CLI + orchestration
├── schemas/             # JSON Schema test cases (source of truth)
├── clients/             # API clients (OpenRouter, etc.)
├── evaluators/          # Scoring/validation logic
├── reporters/           # Output formatting (JSONL, HTML, etc.)
├── utils/               # Shared helpers
├── tests/               # Unit tests mirroring src structure
└── skills/              # Hermes Agent skills (this project only)
```

## Key Libraries

- `openai` / `httpx` - OpenRouter API (OpenAI-compatible)
- `pydantic` - Settings, request/response models
- `jsonschema` - Schema validation
- `rich` - CLI output
- `pytest` - Testing
- `ruff` - Linting/formatting

## AI Assistant Guidelines

### DO
- Write tests before implementation (TDD)
- Use type hints everywhere
- Keep functions small and single-purpose
- Validate all external inputs (API responses, schema files)
- Log structured data (JSON) for debugging

### DON'T
- Hardcode API keys or model names
- Skip error handling for network calls
- Mix evaluation logic with I/O
- Commit generated results to git

## Evaluation Harness Design

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Schema     │────▶│  Prompt     │────▶│  Model      │
│  Loader     │     │  Builder    │     │  Client     │
└─────────────┘     └─────────────┘     └─────────────┘
                                                │
                                                ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Reporter   │◀────│  Evaluator  │◀────│  Validator  │
│  (JSONL)    │     │  (Scoring)  │     │  (JSON      │
└─────────────┘     └─────────────┘     │   Schema)   │
                                        └─────────────┘
```

## Adding New Schema Tests

1. Add `.json` file to `schemas/`
2. Add corresponding test in `tests/test_evaluator.py`
3. Run `python eval.py --schema schemas/new.json` to verify

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key |
| `MODEL_ID` | No | Override default model (default: `nvidia/nemotron-3-ultra-550b-a55b:free`) |
| `TEMPERATURE` | No | Sampling temperature (default: 0.0) |
| `MAX_TOKENS` | No | Max completion tokens (default: 4096) |
| `REQUEST_TIMEOUT` | No | HTTP timeout seconds (default: 60) |

## Debugging

```bash
# Verbose logging
LOG_LEVEL=DEBUG python eval.py --schema schemas/simple.json

# Dry run (no API calls)
python eval.py --dry-run --schema schemas/simple.json

# Save raw responses
python eval.py --save-raw --schema schemas/simple.json
```

## Git Workflow

- Main branch: `main`
- Feature branches: `feat/<description>`
- Commits: Conventional commits (`feat:`, `fix:`, `chore:`)
- PRs required for all changes to main