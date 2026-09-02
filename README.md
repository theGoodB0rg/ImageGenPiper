# ImageGenPiper 🚀

> **High-Performance Programmatic CLI & Chrome Extension Bridge for Gemini Web Image Generation**

ImageGenPiper bridges a local Python asynchronous orchestrator with a Chrome Manifest V3 extension, allowing you to bulk generate images on `gemini.google.com` directly using your authenticated browser session—with **zero headless bot-fingerprinting** and **no API rate-limit bottlenecks**.

---

## 🖼️ Live Proof & Sample Output

Generated live via `imagegenpiper run` on `gemini.google.com` using Imagen:

![Crystal Dragon Sample Output](assets/sample_crystal_dragon.jpg)

> **Prompt:** *"A breathtaking crystal dragon perched atop an obsidian mountain at sunset, 8k digital art"*  
> **Resolution:** $1024 \times 559$ • **Format:** JPEG • **Extracted via:** Authenticated Browser Session Bridge

---

## Key Features

- 🛡️ **Zero Bot-Fingerprinting:** Piggybacks directly on your authenticated Chrome session and cookies. No Playwright, Puppeteer, or CDP needed.
- ⚡ **WebSocket Bridge (Manifest V3):** Fast, persistent JSON-RPC communication between the Python CLI and Chrome with automatic reconnection and heartbeat keepalive.
- 🎯 **Anti-Fragile DOM Architecture:** Multi-tier fallback selector engine (`SelectorMap`) with synthetic React/Angular event simulation.
- ⏳ **Smart Rate Limiting & Safety:** Token-bucket rate limiter with randomized human jitter and automated backoff against rate limits.
- 📥 **Async Image Persistence:** Streams full-resolution images directly to disk with metadata sidecar `.json` files and SHA-256 deduplication.
- 📊 **Rich Terminal UI:** Live status tables, real-time progress updates, and structured error reporting.
- 🧪 **100% Test-Driven:** Comprehensive unit, integration, and offline mock fixture test suites.

---

## Quick Start

### 1. Installation

```bash
# Clone repository and enter directory
cd ImageGenPiper

# Install Python package and dependencies
pip install -e .[dev]
```

### 2. Load the Chrome Extension

1. Open **Google Chrome** and navigate to `chrome://extensions/`.
2. Enable **Developer mode** in the top-right corner.
3. Click **Load unpacked** and select the `extension/` folder in this repository.
4. Open a tab with `https://gemini.google.com/app` and ensure you are logged into your Google account.

### 3. Verify Bridge Connection (Optional)

You can run a quick connection test to verify that the CLI and your Chrome extension communicate:

```bash
imagegenpiper test-bridge
```
*(or `python -m cli.main test-bridge`)*

---

## Generating Images

### Single Prompt

```bash
imagegenpiper run --prompt "A breathtaking crystal dragon perched atop an obsidian mountain at sunset, 8k digital art" --output-dir ./outputs
```

### Batch Generation via File

Create a text file (e.g. `prompts.txt`) with one prompt per line (lines starting with `#` are ignored as comments):

```text
# Fantasy Landscapes
A breathtaking crystal dragon perched atop an obsidian mountain at sunset, 8k digital art
A mystical ancient library carved inside an iceberg, glowing crystals, cinematic lighting

# Sci-Fi / Cyberpunk
A futuristic cyberpunk ramen shop in the pouring rain, neon reflections, ultra-detailed
A sleek orbital station orbiting Jupiter at twilight, hard sci-fi, photorealistic
```

Run the batch generator:

```bash
imagegenpiper run --prompts-file prompts.txt --output-dir ./outputs --rate-limit 6
```

---

## CLI Reference & Options

| Option | Flag | Default | Description |
|---|---|---|---|
| `--prompt` | `-p` | `None` | Single prompt text to generate |
| `--prompts-file` | `-f` | `None` | Path to text file with prompts (one per line) |
| `--output-dir` | `-o` | `./outputs` | Directory where generated images and metadata are saved |
| `--rate-limit` | `-r` | `6.0` | Max generation requests per minute (RPM) |
| `--concurrency` | `-c` | `1` | Number of concurrent worker pipelines |
| `--timeout` | `-t` | `120` | Timeout in seconds per prompt generation |
| `--port` | | `8765` | WebSocket bridge port |

---

## Output Organization & Metadata

Generated images are automatically organized by date inside the output directory:

```text
outputs/
└── 2026-09-02/
    ├── a-breathtaking-crystal-dragon-891894be-1.jpg
    └── a-breathtaking-crystal-dragon-891894be-1.json
```

Each image is accompanied by a `.json` metadata sidecar containing the prompt, dimensions, file size, SHA-256 hash, and timestamp:

```json
{
  "job_id": "891894be-8cb1-4239-974c-595a94c1241b",
  "prompt": "A breathtaking crystal dragon perched atop an obsidian mountain at sunset, 8k digital art",
  "image_index": 1,
  "mime_type": "image/jpeg",
  "sha256": "02cc131acee1d66af79bc00dd01d2b7a86536a219f2c46ae4da476842fee775d",
  "file_size_bytes": 144748,
  "timestamp": "2026-09-02T11:45:28.785352",
  "metadata": {
    "width": 1024,
    "height": 559
  }
}
```

---

## Troubleshooting & FAQ

#### 1. Why does the Chrome Extension console show `ERR_CONNECTION_REFUSED`?
This is completely normal when the Python CLI server is not running. The extension will automatically retry connecting with exponential backoff and will connect instantly the moment you run `imagegenpiper run` or `imagegenpiper test-bridge`.

#### 2. The CLI says `Waiting for Chrome extension to connect...`
Ensure that:
1. The extension is enabled in `chrome://extensions/`.
2. Chrome is open and has a tab on `https://gemini.google.com/app`.

#### 3. How do I modify or reload the extension?
If you make changes to extension files, run:
```bash
node scripts/build_extension.js
```
Then visit `chrome://extensions/` and click the **Reload (↻)** icon on the ImageGenPiper card.

---

## Running Test Suites

```bash
# Run Python Unit and Integration Tests
pytest

# Run Extension Unit Tests
npm test
```

---

## Documentation Links

- [Architecture Overview](docs/ARCHITECTURE.md)
- [WebSocket Protocol Specification](docs/PROTOCOL.md)
- [DOM Resilience & Selector Strategy](docs/DOM_RESILIENCE.md)
- [Testing Strategy (TDD)](docs/TESTING_STRATEGY.md)
- [Development Roadmap](ROADMAP.md)
