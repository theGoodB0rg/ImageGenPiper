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
  const { id, prompt, reset_chat = false, sequence_index, title, timeout_ms = 120000 } = message;
  console.log(`[ImageGenPiper Content] Processing prompt [${id}] #${sequence_index || 1} "${title || ''}": "${prompt}" (reset_chat=${reset_chat})`);

  if (activeCancelFn) {
    activeCancelFn();
    activeCancelFn = null;
  }

  // 1. Reset to New Chat only if explicitly requested
  if (reset_chat) {
    sendToBridge({
      type: "STATUS_UPDATE",
      id,
      status: "RESETTING_CHAT",
      message: "Opening fresh chat session for isolated generation..."
    });
    await resetToNewChat();
  }

  // 2. Wait for any previous turn loading spinner to settle
  let attempts = 0;
  while (attempts < 20) {
    const isSpinnerActive = !!findFirstMatchingSelector(SELECTOR_MAP.generatingIndicator);
    if (!isSpinnerActive) break;
    await new Promise((r) => setTimeout(r, 500));
    attempts++;
  }

  // 3. Locate input textarea
  sendToBridge({
    type: "STATUS_UPDATE",
    id,
    status: "TYPING",
    message: "Locating input field and typing prompt..."
  });

  let textarea = findFirstMatchingSelector(SELECTOR_MAP.textarea);
  if (!textarea) {
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
    // 4. Attach observer BEFORE clicking submit to catch the earliest render events
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

    // 5. Type prompt and submit
    await simulateTyping(textarea, prompt);
    const submitted = await clickSubmitButton();
    if (!submitted) {
      throw new Error("Failed to submit prompt (Send button not found).");
    }

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
