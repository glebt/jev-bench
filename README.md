# Jev Bench - TypeSafe Jev Model Evaluation

This project evaluates the **TypeSafe Jev 1.3** model via **OpenRouter.ai** for structured output generation tasks.

## Project Overview

- **Model**: Jev 1.3 (TypeSafe variant) - a model optimized for JSON/schema-constrained generation
- **Provider**: OpenRouter.ai
- **Goal**: Benchmark and evaluate Jev's ability to produce valid, typed JSON outputs against various schemas

## Quick Start

```bash
# Install dependencies
pip3 install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your OPENROUTER_API_KEY

# Run help
python3 eval.py --help 

# run evaluate all
python3 eval.py evaluate --all


## Project Structure

```
jev-bench/
├── README.md           # This file
├── CLAUDE.md           # AI assistant instructions
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
├── eval.py             # Main evaluation script
├── schemas/            # JSON schemas for testing
│   ├── simple.json
│   ├── nested.json
│   └── complex.json
├── results/            # Evaluation outputs (gitignored)
└── skills/             # Hermes Agent skills for this project
```

## Evaluation Methodology

1. **Schema Compliance** - Does output validate against the target JSON schema?
2. **Type Correctness** - Are all fields the correct type (string, number, boolean, array, object)?
3. **Completeness** - Are all required fields present?
4. **Latency** - Time to first token / total generation time
5. **Cost** - Tokens used per evaluation run

## Configuration

Set the following in `.env`:

```env
OPENROUTER_API_KEY=your_key_here
MODEL=jev-1.3-typesafe  # or specific model ID from OpenRouter
TEMPERATURE=0.0         # Deterministic for evaluation
MAX_TOKENS=4096
```

## Running Evaluations

```bash
# Run all schema tests
python eval.py --all

# Run specific schema
python eval.py --schema schemas/simple.json

# Run with custom model
python eval.py --model jev-1.3-typesafe --schema schemas/complex.json
```

## Results
Results are saved to `results/` as JSONL files with timestamps for comparison across runs.

## License

MIT