/**
 * ImageGenPiper Background Service Worker (Manifest V3)
 * Maintains persistent WebSocket connection to Python CLI orchestrator
 * and routes generation jobs to active Gemini tabs.
 */

const DEFAULT_WS_URL = "ws://127.0.0.1:8765";
const HEARTBEAT_INTERVAL_MS = 20000;

let ws = null;
let reconnectAttempts = 0;
let heartbeatTimer = null;

function log(...args) {
  console.log("[ImageGenPiper SW]", ...args);
}

function warn(...args) {
  console.warn("[ImageGenPiper SW]", ...args);
}

function error(...args) {
  console.error("[ImageGenPiper SW]", ...args);
}

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  log(`Connecting to Python orchestrator at ${DEFAULT_WS_URL}...`);
  try {
    ws = new WebSocket(DEFAULT_WS_URL);

    ws.onopen = () => {
      log("WebSocket connected to Python CLI.");
      reconnectAttempts = 0;
      startHeartbeat();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        log("Received message from CLI:", data.type, data.id || "");

        if (data.type === "PONG") {
          return;
        }

        if (data.type === "GENERATE_REQUEST") {
          dispatchToGeminiTab(data);
        }
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

      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
      reconnectAttempts++;
      log(`Reconnecting in ${delay}ms...`);
      setTimeout(connect, delay);
    };
  } catch (err) {
    error("Failed to initialize WebSocket:", err);
    setTimeout(connect, 2000);
  }
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

function sendToCli(message) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    const raw = typeof message === "string" ? message : JSON.stringify(message);
    ws.send(raw);
    return true;
  }
  warn("Cannot send message, WebSocket is not open.");
  return false;
}

function dispatchToGeminiTab(payload) {
  chrome.tabs.query({}, async (tabs) => {
    const targetTab = tabs.find(t => t.url && (
      t.url.includes("gemini.google.com") ||
      t.url.includes("mock_gemini_spa") ||
      t.url.includes("127.0.0.1") ||
      t.url.includes("localhost")
    ));

    if (!targetTab) {
      warn("No matching Gemini or test tab found.");
      sendToCli({
        type: "GENERATION_ERROR",
        id: payload.id || "unknown",
        error_code: "DOM_ERROR",
        message: "No active Gemini tab found. Please open gemini.google.com in Chrome.",
        retryable: true
      });
      return;
    }

    log(`Dispatching prompt [${payload.id}] to tab ${targetTab.id} (${targetTab.url})`);

    // Ensure content script is injected
    try {
      await chrome.scripting.executeScript({
        target: { tabId: targetTab.id },
        files: ["content/content_bundle.js"]
      });
    } catch (e) {
      // Content script may already be injected, continue
    }

    chrome.tabs.sendMessage(targetTab.id, payload).catch((err) => {
      error("Failed to send message to content script in tab:", err);
      sendToCli({
        type: "GENERATION_ERROR",
        id: payload.id || "unknown",
        error_code: "DOM_ERROR",
        message: `Failed to communicate with tab content script: ${err.message}`,
        retryable: true
      });
    });
  });
}

// Receive messages from content script and forward directly to Python CLI over WebSocket
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  connect();
  if (message && message.type && message.type !== "CONTENT_SCRIPT_READY") {
    log("Forwarding message from content script to CLI:", message.type, message.id || "");
    const sent = sendToCli(message);
    sendResponse({ success: sent });
  } else {
    sendResponse({ ack: true });
  }
  return true;
});

// Alarm keepalive & reconnection
try {
  chrome.alarms.create('ws_check', { periodInMinutes: 0.25 });
  chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === 'ws_check') {
      connect();
    }
  });
} catch (e) {}

// Programmatically inject and connect on tab events
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  connect();
  if (changeInfo.status === 'complete' && tab.url && (
    tab.url.includes("gemini.google.com") ||
    tab.url.includes("mock_gemini_spa") ||
    tab.url.includes("127.0.0.1") ||
    tab.url.includes("localhost")
  )) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["content/content_bundle.js"]
      });
    } catch (e) {}
  }
});

chrome.tabs.onActivated.addListener(() => {
  connect();
});

// Lifecycle listeners
chrome.runtime.onInstalled.addListener(() => {
  log("Extension installed.");
  connect();
});

chrome.runtime.onStartup.addListener(() => {
  log("Extension startup.");
  connect();
});

// Connect immediately
connect();
