# ImageGenPiper System Architecture

## 1. Overview & High-Level Design

ImageGenPiper is a high-performance local automation bridge designed to batch-generate images via `gemini.google.com` using the user's authentic Chrome browser session. It avoids all anti-bot fingerprinting, headless detection (Playwright/Puppeteer/CDP), and fragile cookie reverse-engineering by operating natively inside the browser context through a Chrome Manifest V3 extension connected via WebSocket to a Python orchestrator.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 USER'S CHROME BROWSER                                  │
│                                                                                        │
│   ┌────────────────────────┐         ┌────────────────────────┐                        │
│   │  gemini.google.com     │         │ Content Script Bundle  │                        │
│   │  • SPA Conversation    │◄───────►│ • Selector Engine      │                        │
│   │  • Input Box (React)   │         │ • Human Typing Sim     │                        │
│   │  • Image Renderer      │         │ • MutationObserver     │                        │
│   │  • Watermark / Blobs   │         │ • Blob Fetcher / B64   │                        │
│   └────────────────────────┘         └───────────▲────────────┘                        │
│                                                  │ chrome.runtime                      │
│                                                  ▼                                     │
│   ┌───────────────────────────────────────────────────────────┐                        │
│   │ Background Service Worker (Manifest V3)                   │                        │
│   │ • Persistent Native WebSocket Client                      │                        │
│   │ • Tab Discovery & Programmatic Script Injection           │                        │
│   │ • Automated Backoff & Alarm Keepalive                     │                        │
│   └──────────────────────────┬────────────────────────────────┘                        │
└──────────────────────────────┼─────────────────────────────────────────────────────────┘
                               │ ws://127.0.0.1:8765
                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              LOCAL PYTHON ORCHESTRATOR                                 │
│                                                                                        │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │ WebSocket Server (asyncio + websockets)                                        │   │
│   │ • JSON-RPC Dispatcher • Connection Pools • Heartbeat Monitor                   │   │
│   └──────────────────────────────────────▲─────────────────────────────────────────┘   │
│                                          │                                             │
│   ┌──────────────────────────────────────┴─────────────────────────────────────────┐   │
│   │ Orchestration Engine                                                           │   │
│   │ ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐  │   │
│   │ │ Job Queue & Backoff  │  │ Token-Bucket Rate    │  │ Async Download Mgr   │  │   │
│   │ │ (Priority & Retries) │  │ Limiter + Jitter     │  │ (aiofiles + dedup)   │  │   │
│   │ └──────────────────────┘  └──────────────────────┘  └──────────────────────┘  │   │
│   └──────────────────────────────────────▲─────────────────────────────────────────┘   │
│                                          │                                             │
│   ┌──────────────────────────────────────┴─────────────────────────────────────────┐   │
│   │ CLI Interface (Typer + Rich Live Terminal UI)                                  │   │
│   │ • Prompt File Parser • Live Progress Tables • Structured Error Logging         │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Subsystems

### 2.1 Python Orchestrator (`/core` & `/cli`)
1. **`core.protocol`**: Strongly typed Pydantic V2 schemas representing all inbound and outbound WebSocket messages (`GenerateRequest`, `ImageFound`, `GenerationError`, `StatusUpdate`, `Heartbeat`).
2. **`core.ws_server`**: Asynchronous WebSocket server using `asyncio` and `websockets`. Manages client registration, bidirectional routing, ping/pong heartbeats, and message dispatch.
3. **`core.job_queue`**: Async priority queue with backpressure support, exponential retry backoff, jitter calculation, and error tracking.
4. **`core.rate_limiter`**: Token-bucket algorithm enforcing user-configured requests-per-minute (RPM) and randomized human jitter delays (e.g. 1–3 seconds).
5. **`core.downloader`**: Async disk streamer utilizing `aiofiles`. Computes SHA-256 digests for deduplication and writes metadata sidecars (`.json`) alongside downloaded images.
6. **`core.orchestrator`**: Central state engine linking the Job Queue, Rate Limiter, Downloader, and WebSocket Server.
7. **`cli.main`**: Typer command-line interface with commands `run`, `test-bridge`, and `version`.
8. **`cli.ui`**: Rich terminal interface with progress tables, status badges, and execution summary panels.

### 2.2 Chrome Extension Bridge (`/extension`)
1. **`manifest.json`**: Chrome MV3 manifest with `activeTab`, `scripting`, `storage`, `alarms`, and `tabs` permissions.
2. **`background/service_worker.js`**: Maintains a native, persistent WebSocket connection to `ws://127.0.0.1:8765` using Chrome MV3 WebSocket support, alarm keepalives, and automatic exponential reconnection. Coordinates active tab routing and programmatic script injection.
3. **`content/selectors.js`**: `SelectorMap` with prioritized fallback cascades across rich textareas, contenteditable elements, ARIA semantics, and model response blocks.
4. **`content/dom_driver.js`**: Synthetic typing driver using `beforeinput`, `insertText`, and full event dispatching to trigger framework internal fiber updates.
5. **`content/observer.js`**: Targeted `MutationObserver` filtering newly rendered image nodes, verifying dimensions, and extracting image blobs.
6. **`content/extractor.js`**: Downloads image binary in browser origin context via `fetch(url, { credentials: 'include' })` and encodes to Base64.
7. **`content/content_bundle.js`**: Self-contained content bundle generated by `scripts/build_extension.js`.

---

## 3. Data Flow

1. User invokes CLI: `imagegenpiper run --prompts-file prompts.txt --output-dir ./outputs`.
2. The Python orchestrator reads prompts, enqueues jobs into `JobQueue`, and spins up the WebSocket server on port `8765`.
3. Chrome extension background service worker connects to `ws://127.0.0.1:8765`.
4. Orchestrator dequeues a prompt, checks the Token-Bucket rate limiter, applies human jitter, and emits `GenerateRequest`.
5. Background service worker finds the active Gemini tab and forwards the request to the Content Script.
6. Content script locates the input box using `SelectorMap`, types the prompt, and submits.
7. `MutationObserver` monitors for generating spinner and waits for final rendered `<img>` elements.
8. Content script downloads image blob inside browser origin context, converts to Base64, and sends `ImageFound`.
9. Python orchestrator decodes Base64, writes image to disk asynchronously (`aiofiles`), saves sidecar metadata `.json`, and updates live progress.
10. If an error occurs, it is caught as `GenerationError`, retried if eligible, or logged in summary.
