/**
 * ImageGenPiper Persistent WebSocket Client (runs in Offscreen Document)
 */

const DEFAULT_WS_URL = "ws://127.0.0.1:8765";
const HEARTBEAT_INTERVAL_MS = 20000;
let ws = null;
let reconnectAttempts = 0;
let heartbeatTimer = null;

function log(...args) {
  console.log("[ImageGenPiper WS]", ...args);
}

function warn(...args) {
  console.warn("[ImageGenPiper WS]", ...args);
}

function error(...args) {
  console.error("[ImageGenPiper WS]", ...args);
}

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  log(`Connecting to ${DEFAULT_WS_URL}...`);
  ws = new WebSocket(DEFAULT_WS_URL);

  ws.onopen = () => {
    log("Connected to Python CLI WebSocket server.");
    reconnectAttempts = 0;
    startHeartbeat();

    // Broadcast connected status
    chrome.runtime.sendMessage({
      target: "background",
      type: "WS_STATUS",
      connected: true
    }).catch(() => {});
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      log("Received from CLI:", data.type, data.id || "");

      if (data.type === "PONG") {
        // Heartbeat ack
        return;
      }

      // Forward to background service worker / content script
      chrome.runtime.sendMessage({
        target: "content",
        payload: data
      }).catch((err) => {
        warn("Failed to forward message to content script:", err);
      });
    } catch (err) {
      error("Failed to parse incoming WebSocket message:", err);
    }
  };

  ws.onerror = (err) => {
    warn("WebSocket error:", err);
  };

  ws.onclose = (event) => {
    log(`WebSocket disconnected (code ${event.code}).`);
    stopHeartbeat();
    ws = null;

    chrome.runtime.sendMessage({
      target: "background",
      type: "WS_STATUS",
      connected: false
    }).catch(() => {});

    // Reconnect with exponential backoff (1s, 2s, 4s, max 10s)
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
    reconnectAttempts++;
    log(`Attempting reconnect in ${delay}ms...`);
    setTimeout(connect, delay);
  };
}

function startHeartbeat() {
  stopHeartbeat();
  heartbeatTimer = setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: "PING",
        timestamp: Date.now()
      }));
    }
  }, HEARTBEAT_INTERVAL_MS);
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
}

export function sendOverWs(message) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    const raw = typeof message === "string" ? message : JSON.stringify(message);
    ws.send(raw);
    return true;
  }
  warn("Cannot send message, WebSocket is not open.");
  return false;
}

// Listen for messages from background/content scripts to forward to Python CLI
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.target === "offscreen_ws" && message.payload) {
    const sent = sendOverWs(message.payload);
    sendResponse({ success: sent });
  }
});

// Initialize connection
connect();
