# Testing Strategy: Red → Green TDD

ImageGenPiper is developed under strict Test-Driven Development (TDD) guidelines across all tiers.

## 1. Testing Hierarchy

| Level | Scope | Tools |
|---|---|---|
| **Python Unit** | Pydantic protocol, rate limiting math, priority job queue, downloader SHA-256 deduplication, config loaders | `pytest`, `pytest-asyncio` |
| **Python Integration** | WebSocket server & client lifecycle, ping/pong heartbeats, simulated prompt generation flows | `pytest`, `pytest-asyncio`, `websockets` |
| **Extension Unit** | SelectorMap cascade matching, synthetic input event dispatcher, Base64 encoder | `node --test` |
| **End-to-End Mock** | Full pipeline execution using offline mock Gemini SPA HTML fixture (`tests/fixtures/mock_gemini_spa.html`) | `pytest`, Typer CLI |

---

## 2. Test Suites Overview

### Python Tests (`/tests/python/`)
- `test_protocol.py`: Validates all JSON-RPC message schemas, serialization, and deserialization.
- `test_rate_limiter.py`: Validates token-bucket capacity, refill rates, and sleep/jitter boundaries.
- `test_job_queue.py`: Validates priority queue ordering, exponential backoff, retry caps, and backpressure.
- `test_downloader.py`: Validates async file streaming, filename sanitization, deduplication, and metadata `.json` integrity.
- `test_ws_server.py`: Validates WebSocket connection management, registration, message broadcasting, and disconnection recovery.
- `test_orchestrator.py`: Validates orchestrator state machine handling end-to-end jobs.

### Extension Tests (`/tests/extension/`)
- `test_selectors.test.js`: Verifies `findMatchingElement()` across various real & mock HTML DOM structures.
- `test_extractor.test.js`: Verifies image detection, blob URL resolution, and Base64 encoding.

### Fixture Harness (`/tests/fixtures/`)
- `mock_gemini_spa.html`: A self-contained, offline HTML/JS simulation of `gemini.google.com/app` featuring a rich textarea, submit button, loading spinner, and simulated image generation after a 1-second delay. Allows 100% deterministic automated CI testing without live Google accounts.
