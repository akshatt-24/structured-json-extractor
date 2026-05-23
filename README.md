# Structured JSON Extractor

> Turn messy, unstructured text into clean, validated JSON — automatically.

## Project Overview

**structured-json-extractor** is a production-ready Python application that uses a Large Language Model (LLM) to extract structured, validated data from noisy, unstructured text inputs such as customer emails, support tickets, receipts, and chat logs.

### What it does

- Accepts any messy text as input
- Sends it to an LLM (via OpenRouter) with a carefully engineered prompt
- Enforces a strict Pydantic v2 schema on the output using the Instructor library
- Automatically retries failed extractions with exponential back-off
- Repairs malformed JSON outputs before retrying validation
- Returns a deterministic, validated JSON object every time

### Why it matters

Raw text from customers, forms, or OCR scans is rarely clean. Traditional regex or rule-based parsers break constantly. This system uses an LLM as the parser while enforcing strict schema validation — giving you the flexibility of natural language understanding with the reliability of typed data structures.

### Architecture Overview

```
RAW TEXT
    ↓
PROMPT ENGINEERING (prompts.py)
    ↓
LLM API CALL (OpenRouter via openai SDK + Instructor)
    ↓
RAW RESPONSE
    ↓
JSON PARSE + SCHEMA VALIDATION (validators.py + Pydantic v2)
    ↓
[If failed] → JSON REPAIR PASS → RE-VALIDATE
    ↓
[If still failed] → RETRY WITH EXPONENTIAL BACK-OFF (retry_handler.py)
    ↓
FINAL STRUCTURED OUTPUT (ExtractionResult)
```

---

## Features

- **LLM-powered extraction** using `meta-llama/llama-3.3-70b-instruct:free` via OpenRouter (free tier available)
- **Instructor integration** — automatic Pydantic schema enforcement on LLM responses
- **Retry logic** — configurable exponential back-off via Tenacity
- **JSON repair** — malformed model outputs are sent back for correction automatically
- **Pydantic v2 schemas** — strongly typed, validated, serialisable output
- **FastAPI backend** — REST API with `/extract` and `/health` endpoints
- **Rich CLI** — beautiful terminal interface for file or text extraction
- **Structured logging** — rotating log files + Rich console output
- **Confidence scoring** — optional 0–1 score on each extraction
- **Extraction metadata** — processing time, retry count, repair flag, model used
- **Hallucination prevention** — prompts explicitly forbid fabrication; unknowns become `null`
- **Deterministic outputs** — `temperature=0` on all extraction calls
- **Async throughout** — async extraction pipeline and FastAPI endpoints
- **Full test suite** — pytest with mocked and unit tests

---

## Installation

### Prerequisites

- Python 3.12.7+
- An [OpenRouter](https://openrouter.ai/) account and API key (free tier available)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/yourname/structured-json-extractor.git
cd structured-json-extractor

# 2. Create a virtual environment
python -m venv venv
```

**Activate the virtual environment:**

Windows:
```bash
venv\Scripts\activate
```

Linux / macOS:
```bash
source venv/bin/activate
```

```bash
# 3. Install dependencies
pip install -r requirements.txt
```

---

## OpenRouter Setup

OpenRouter provides access to hundreds of LLMs through a single OpenAI-compatible API.

### Create an account

1. Go to [https://openrouter.ai/](https://openrouter.ai/)
2. Sign up with your email or Google account
3. Navigate to [https://openrouter.ai/keys](https://openrouter.ai/keys)
4. Click **Create Key** and copy the key

### Configure the project

```bash
# Copy the example env file
cp .env.example .env
```

Open `.env` and paste your key:

```env
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxx
MODEL_NAME=meta-llama/llama-3.3-70b-instruct:free
MAX_RETRIES=3
LOG_LEVEL=INFO
```

---

## Running the FastAPI Server

```bash
uvicorn app.main:app --reload
```

The API will be available at:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)

### Example API call

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"text": "Hi, I am Sarah. My order ORD-88271 arrived with the wrong item. I want a refund of $299.99. Very frustrated!"}'
```

---

## Running the CLI

### Extract from a file

```bash
python run.py extract sample_inputs/customer_email.txt
python run.py extract sample_inputs/receipt.txt
python run.py extract sample_inputs/support_ticket.txt
```

### Extract from raw text

```bash
python run.py text "Customer wants refund for broken headphones order ORD-1234"
```

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use mocking — no live API key required for the test suite.

---

## Example Input / Output

### Input (`sample_inputs/customer_email.txt`)

```
From: sarah.johnson89@gmail.com
Subject: My order is WRONG and I want my money back!!!

I ordered Sony WH-1000XM5 headphones (order ORD-88271) but received a 
cheap knockoff brand. The box was damaged too. I want a FULL REFUND 
of $299.99. I've been a customer for 3 years!

— Sarah Johnson
```

### Output

```json
{
  "customer_name": "Sarah Johnson",
  "order_id": "ORD-88271",
  "product": "Sony WH-1000XM5 Noise Cancelling Headphones",
  "issue_type": "wrong_item",
  "issue_description": "Customer received wrong product instead of Sony WH-1000XM5. Box was also damaged. Requesting full refund.",
  "refund_amount": 299.99,
  "priority": "high",
  "sentiment": "angry",
  "confidence_score": 0.97
}
```

---

## Project Structure

```
structured-json-extractor/
│
├── app/
│   ├── __init__.py        # Package marker
│   ├── main.py            # FastAPI app factory + lifespan
│   ├── api.py             # /extract and /health endpoints
│   ├── extractor.py       # Core LLM extraction engine
│   ├── schemas.py         # Pydantic v2 data models
│   ├── prompts.py         # Extraction + repair prompt templates
│   ├── validators.py      # JSON parsing + schema validation helpers
│   ├── retry_handler.py   # Tenacity-based retry + back-off logic
│   ├── config.py          # Environment variable loader
│   ├── logger.py          # Rotating file + Rich console logger
│   ├── utils.py           # Shared utilities (timer, pretty_json, etc.)
│   └── cli.py             # Rich terminal UI for CLI commands
│
├── tests/
│   ├── test_extraction.py # Extraction pipeline tests (mocked)
│   └── test_validation.py # Schema validation unit tests
│
├── sample_inputs/
│   ├── customer_email.txt # Angry refund email
│   ├── receipt.txt        # Noisy OCR receipt with follow-up note
│   └── support_ticket.txt # Live chat transcript
│
├── logs/                  # Rotating log files (auto-created)
│
├── .env.example           # Environment variable template
├── requirements.txt       # Python dependencies
├── pyproject.toml         # Build system config
├── run.py                 # CLI entry point
└── README.md
```

---

## Architecture Deep Dive

### Extraction Engine (`extractor.py`)

The heart of the system. Uses the `instructor` library to patch an `AsyncOpenAI` client and automatically enforce a Pydantic schema on every response. If Instructor raises a validation error, the raw response is captured and sent through the repair pipeline before retrying.

### Prompt Engineering (`prompts.py`)

Two prompts are maintained:

1. **Extraction prompt** — instructs the model to return only valid JSON, never fabricate values, and use `null` for unknown fields.
2. **Repair prompt** — sent when malformed JSON is returned; asks the model to fix syntax errors without changing values.

### Retry + Repair (`retry_handler.py`)

Uses `run_with_retries()` — a functional async retry helper that:
- Runs the extraction coroutine
- Catches any exception
- Waits with exponential back-off (`1s → 2s → 4s → …`)
- Retries up to `MAX_RETRIES` times
- Records the retry count in metadata

### Schema (`schemas.py`)

Three Pydantic v2 models:
- `CustomerSupportTicket` — the extracted data
- `ExtractionMetadata` — run information (time, retries, model, repair flag)
- `ExtractionResult` — combines both for API and CLI responses

### Logging (`logger.py`)

Every module gets a named logger via `get_logger("module_name")`. All loggers write to:
- **Console** — via `RichHandler` (coloured, formatted)
- **File** — `logs/extractor.log` with 5 MB rotation and 5 backup files

---

## Troubleshooting

### `EnvironmentError: OPENROUTER_API_KEY is not set`

You haven't created a `.env` file or the key is missing.

```bash
cp .env.example .env
# Edit .env and add your key from https://openrouter.ai/keys
```

### `ModuleNotFoundError`

Your virtual environment is not activated or dependencies are not installed.

```bash
source venv/bin/activate        # Linux/macOS
# or
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### Rate limits / 429 errors

OpenRouter's free tier has rate limits. The system will automatically retry with back-off. If you hit persistent rate limits, wait a minute or consider upgrading your OpenRouter plan.

### Malformed JSON outputs

This is handled automatically. The system will:
1. Detect the malformed output
2. Send a repair prompt to the model
3. Re-validate the corrected output
4. Log `repair_applied: true` in the metadata

### `FileNotFoundError` when using CLI extract

Make sure you're running the command from the project root directory and that the file path is correct.

```bash
# Always run from project root
cd structured-json-extractor
python run.py extract sample_inputs/customer_email.txt
```

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | *(required)* | Your OpenRouter API key |
| `MODEL_NAME` | `meta-llama/llama-3.3-70b-instruct:free` | LLM model identifier |
| `MAX_RETRIES` | `3` | Max extraction attempts before failure |
| `LOG_LEVEL` | `INFO` | Logging verbosity: DEBUG, INFO, WARNING, ERROR |

---

## Extending the System

To add a new extraction schema (e.g. for invoices):

1. Add a new Pydantic model to `app/schemas.py`
2. Add a new prompt builder to `app/prompts.py`
3. Optionally add a new CLI command in `app/cli.py`
4. Add a new API endpoint in `app/api.py`

The retry, repair, logging, and validation infrastructure is reusable with any schema.

---

## Tech Stack

| Component | Library |
|---|---|
| Python | 3.12.7 |
| API Framework | FastAPI + Uvicorn |
| LLM Provider | OpenRouter (`openai` SDK) |
| Schema Enforcement | Instructor + Pydantic v2 |
| Retry Logic | Tenacity |
| Terminal UI | Rich |
| HTTP Client | HTTPX |
| Config | python-dotenv |
| Testing | pytest + pytest-asyncio |
| Logging | Python `logging` + RichHandler |
