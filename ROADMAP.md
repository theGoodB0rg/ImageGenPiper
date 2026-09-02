# ImageGenPiper Development Roadmap

## Phase 0: Scaffold, Tooling & Environment Setup ✅
- [x] Configure `pyproject.toml` and install dependencies (`websockets`, `pydantic`, `typer`, `rich`, `aiofiles`, `pytest`).
- [x] Configure `package.json` for extension testing.
- [x] Author comprehensive documentation in `docs/` (`ARCHITECTURE.md`, `PROTOCOL.md`, `DOM_RESILIENCE.md`, `TESTING_STRATEGY.md`).
- [x] Initialize modular directory structure.

---

## Phase 1: WebSocket Protocol & Server (Python + Extension Offscreen) ✅
- [x] **Red:** Wrote failing tests in `tests/python/test_protocol.py` and `tests/python/test_ws_server.py`.
- [x] **Green:** Implemented `core/protocol.py`, `core/ws_server.py`, `extension/manifest.json`, and `extension/offscreen/ws_client.js`.
- [x] Verified ping/pong and JSON-RPC dispatch.

---

## Phase 2: Content Script DOM Driver & Selector Fallback Engine ✅
- [x] **Red:** Wrote failing tests in `tests/extension/test_selectors.test.js`.
- [x] **Green:** Implemented `extension/content/selectors.js` and `extension/content/dom_driver.js`.
- [x] Verified resilient DOM element resolution and synthetic event typing simulation.

---

## Phase 3: MutationObserver & Image Extraction Engine ✅
- [x] **Red:** Wrote failing tests in `tests/extension/test_extractor.test.js`.
- [x] **Green:** Implemented `extension/content/observer.js` and `extension/content/extractor.js`.
- [x] Verified image detection, blob fetching inside authenticated context, and Base64 encoding.

---

## Phase 4: Job Queue, Token-Bucket Rate Limiter & Downloader ✅
- [x] **Red:** Wrote failing tests in `tests/python/test_job_queue.py`, `tests/python/test_rate_limiter.py`, and `tests/python/test_downloader.py`.
- [x] **Green:** Implemented `core/job_queue.py`, `core/rate_limiter.py`, and `core/downloader.py`.
- [x] Verified backpressure, exponential retry backoff, jitter calculation, and async disk persistence with SHA-256 deduplication.

---

## Phase 5: End-to-End Orchestration & Typer CLI with Rich UI ✅
- [x] **Red:** Wrote failing integration tests in `tests/python/test_orchestrator.py`.
- [x] **Green:** Implemented `core/orchestrator.py`, `cli/main.py`, `cli/config.py`, and `cli/ui.py`.
- [x] Verified live terminal progress tables, prompt batch processing, and mock E2E pipeline.

---

## Phase 6: Verification, Fixture Harness & Handover ✅
- [x] Built offline mock Gemini SPA fixture (`tests/fixtures/mock_gemini_spa.html`).
- [x] Ran full test suites (`pytest` with 23 passing tests, `npm test` with 7 passing tests).
- [x] Documented complete walkthrough and usage guide in `README.md`.
