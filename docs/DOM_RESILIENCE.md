# Anti-Fragile DOM Resilience & Selector Hierarchy

## 1. Problem Statement
Web applications such as `gemini.google.com` (built with dynamic component frameworks like Lit/Angular/React) frequently update class names, obfuscate CSS selectors, and alter DOM hierarchies. Direct reliance on static classes (such as `.text-input-field_textarea-wrapper`) causes automation scripts to break silently.

## 2. Multi-Tier Fallback Hierarchy

The `SelectorMap` in ImageGenPiper resolves elements through a multi-tier cascade, prioritizing accessibility attributes, standard HTML elements, and structural heuristics:

```javascript
export const SELECTOR_MAP = {
  textarea: [
    // Tier 1: Test IDs and Explicit Roles
    '[data-test-id="input-textarea"]',
    '[data-test-id="prompt-textarea"]',
    'rich-textarea [role="textbox"]',
    '[role="textbox"][contenteditable="true"]',
    
    // Tier 2: Semantic ARIA & Placeholders
    'textarea[placeholder*="Ask"]',
    'textarea[placeholder*="prompt"]',
    'textarea[aria-label*="prompt" i]',
    'textarea[aria-label*="Ask" i]',
    'div[data-placeholder*="Ask" i]',
    
    // Tier 3: Structural Heuristics
    'form textarea',
    'main footer textarea',
    'div[role="presentation"] textarea',
    'textarea'
  ],

  submitButton: [
    // Tier 1: Test IDs and ARIA labels
    'button[data-test-id="send-button"]',
    'button[aria-label*="Send" i]',
    'button[aria-label*="Submit" i]',
    'button[aria-label*="generate" i]',
    
    // Tier 2: SVG Icon Heuristics
    'button:has(svg[path*="send" i])',
    'button:has(svg[class*="send" i])',
    
    // Tier 3: Form association
    'form button[type="submit"]',
    'form button:last-of-type'
  ],

  conversationContainer: [
    '[data-test-id="conversation-turn"]',
    '[data-test-id="chat-history"]',
    '[role="list"]',
    'main [role="log"]',
    'main article',
    'main'
  ],

  imageElement: [
    'img[src*="googleusercontent.com"]',
    'img[src^="blob:"]',
    'img[alt*="generated" i]',
    'img[data-test-id="generated-image"]'
  ],

  generatingIndicator: [
    '[data-test-id="loading"]',
    'svg[class*="spinner"]',
    'button[aria-label*="Stop" i]', // "Stop generating" button
    '[aria-busy="true"]'
  ],

  safetyWarning: [
    '[data-test-id="safety-warning"]',
    '[data-test-id="blocked-content"]',
    'div:has-text("unable to generate")',
    'div:has-text("violates our guidelines")'
  ]
};
```

---

## 3. Humanized Synthetic Input Simulation

Simply updating `element.value = "prompt"` does not notify React / Angular component state trees. ImageGenPiper dispatches the complete synthetic event lifecycle and leverages `document.execCommand`:

```javascript
export async function simulateTyping(element, text) {
  element.focus();
  
  // Clear any existing content
  if (element.tagName.toLowerCase() === 'textarea' || element.tagName.toLowerCase() === 'input') {
    element.value = '';
  } else {
    element.textContent = '';
  }

  // Use execCommand where available to trigger native undo/redo & input events
  const inserted = document.execCommand('insertText', false, text);
  if (!inserted) {
    if (element.tagName.toLowerCase() === 'textarea') {
      element.value = text;
    } else {
      element.innerText = text;
    }
  }

  // Dispatch standard synthetic event sequence
  element.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
  element.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
  element.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: ' ' }));
}
```
