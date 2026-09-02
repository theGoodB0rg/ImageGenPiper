/**
 * ImageGenPiper Content Script Coordinator
 */

import { SELECTOR_MAP, findFirstMatchingSelector } from './selectors.js';
import { simulateTyping, clickSubmitButton, resetToNewChat } from './dom_driver.js';
import { watchForImageGeneration } from './observer.js';

console.log("[ImageGenPiper] Content script initialized on:", window.location.href);

// Wake up background service worker immediately
try {
  chrome.runtime.sendMessage({ type: "CONTENT_SCRIPT_READY" }).catch(() => {});
} catch (e) {}

let activeCancelFn = null;

function sendToBridge(payload) {
  try {
    chrome.runtime.sendMessage(payload).catch((err) => {
      console.warn("[ImageGenPiper Content] Failed to send message to background SW:", err);
    });
  } catch (err) {
    console.error("[ImageGenPiper Content] Runtime error sending message:", err);
  }
}

async function handleGenerateRequest(message) {
  const { id, prompt, reset_chat = true, sequence_index, title, timeout_ms = 120000 } = message;
  console.log(`[ImageGenPiper Content] Processing prompt [${id}] #${sequence_index || 1} "${title || ''}": "${prompt}"`);

  if (activeCancelFn) {
    activeCancelFn();
    activeCancelFn = null;
  }

  // 1. Reset to New Chat if requested (Clean DOM isolation)
  if (reset_chat) {
    sendToBridge({
      type: "STATUS_UPDATE",
      id,
      status: "RESETTING_CHAT",
      message: "Opening fresh chat session for isolated generation..."
    });
    await resetToNewChat();
  }

  // 2. Locate input textarea
  sendToBridge({
    type: "STATUS_UPDATE",
    id,
    status: "TYPING",
    message: "Locating input field and typing prompt..."
  });

  let textarea = findFirstMatchingSelector(SELECTOR_MAP.textarea);
  if (!textarea) {
    // Retry once after brief wait in case SPA is rendering
    await new Promise((r) => setTimeout(r, 1000));
    textarea = findFirstMatchingSelector(SELECTOR_MAP.textarea);
  }

  if (!textarea) {
    console.error("[ImageGenPiper Content] Could not locate prompt textarea in DOM.");
    sendToBridge({
      type: "GENERATION_ERROR",
      id,
      error_code: "DOM_ERROR",
      message: "Could not locate prompt input textarea in DOM.",
      retryable: true
    });
    return;
  }

  try {
    // 3. Type prompt and submit
    await simulateTyping(textarea, prompt);
    const submitted = await clickSubmitButton();
    if (!submitted) {
      throw new Error("Failed to submit prompt (Send button not found).");
    }

    // 4. Watch for generated image
    activeCancelFn = watchForImageGeneration({
      id,
      timeoutMs: timeout_ms,
      onStatus: (status, statusMsg) => {
        sendToBridge({
          type: "STATUS_UPDATE",
          id,
          status,
          message: statusMsg
        });
      },
      onImage: (imgData) => {
        sendToBridge({
          type: "IMAGE_FOUND",
          ...imgData
        });
      },
      onError: (errorCode, errMsg, retryable) => {
        sendToBridge({
          type: "GENERATION_ERROR",
          id,
          error_code: errorCode,
          message: errMsg,
          retryable
        });
      }
    });

  } catch (err) {
    console.error("[ImageGenPiper Content] Error during generation execution:", err);
    sendToBridge({
      type: "GENERATION_ERROR",
      id,
      error_code: "DOM_ERROR",
      message: err.message || "Unknown error during DOM interaction",
      retryable: true
    });
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type === "GENERATE_REQUEST") {
    handleGenerateRequest(message);
    sendResponse({ received: true });
  }
  return true;
});
