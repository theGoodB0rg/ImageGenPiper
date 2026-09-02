# WebSocket JSON-RPC Protocol Specification

ImageGenPiper communicates over standard WebSockets (`ws://127.0.0.1:8765`) using JSON-encoded messages.

## Message Types

### 1. Python CLI $\rightarrow$ Extension

#### `GENERATE_REQUEST`
Sent by the Python orchestrator to dispatch a prompt generation job.

```json
{
  "type": "GENERATE_REQUEST",
  "id": "c1f7b0a8-23d4-4a2e-8d82-849f13886b45",
  "prompt": "Cyberpunk city in pouring rain at midnight, neon reflections, 8k render",
  "timeout_ms": 120000,
  "options": {
    "aspect_ratio": "16:9",
    "reset_chat": false
  }
}
```

#### `PING`
Periodic keep-alive heartbeat sent every 20 seconds.

```json
{
  "type": "PING",
  "timestamp": 1756806000000
}
```

---

### 2. Extension $\rightarrow$ Python CLI

#### `PONG`
Response to `PING`.

```json
{
  "type": "PONG",
  "timestamp": 1756806000050
}
```

#### `STATUS_UPDATE`
Progress state notification emitted as Gemini processes the prompt.

```json
{
  "type": "STATUS_UPDATE",
  "id": "c1f7b0a8-23d4-4a2e-8d82-849f13886b45",
  "status": "TYPING", // "QUEUED" | "TYPING" | "GENERATING" | "RENDERING" | "DONE" | "ERROR"
  "message": "Typing prompt into textarea"
}
```

#### `IMAGE_FOUND`
Emitted when an image is successfully rendered and extracted.

```json
{
  "type": "IMAGE_FOUND",
  "id": "c1f7b0a8-23d4-4a2e-8d82-849f13886b45",
  "image_index": 1,
  "mime_type": "image/png",
  "data_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "metadata": {
    "width": 1024,
    "height": 1024,
    "source_url": "https://lh3.googleusercontent.com/..."
  }
}
```

#### `GENERATION_ERROR`
Emitted when a generation fails or encounters safety blocks.

```json
{
  "type": "GENERATION_ERROR",
  "id": "c1f7b0a8-23d4-4a2e-8d82-849f13886b45",
  "error_code": "SAFETY_BLOCKED", // "TIMEOUT" | "RATE_LIMITED" | "SAFETY_BLOCKED" | "DOM_ERROR" | "UNKNOWN"
  "message": "Gemini blocked this prompt due to safety guidelines",
  "retryable": false
}
```
