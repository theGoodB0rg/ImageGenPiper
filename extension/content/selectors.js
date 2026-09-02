/**
 * SelectorMap and DOM lookup helpers for Gemini SPA.
 */

export const SELECTOR_MAP = {
  textarea: [
    // Rich Textarea / ContentEditable
    'rich-textarea [contenteditable="true"]',
    'rich-textarea [role="textbox"]',
    'div[contenteditable="true"][role="textbox"]',
    'div[contenteditable="true"]',
    
    // Explicit Test IDs and Roles
    '[data-test-id="input-textarea"]',
    '[data-test-id="prompt-textarea"]',
    '[role="textbox"]',
    
    // Semantic ARIA & Placeholders
    'textarea[placeholder*="Ask" i]',
    'textarea[placeholder*="prompt" i]',
    'textarea[aria-label*="prompt" i]',
    'textarea[aria-label*="Ask" i]',
    'textarea[aria-label*="Enter" i]',
    'div[data-placeholder*="Ask" i]',
    
    // Structural Fallbacks
    'form textarea',
    'main footer textarea',
    'div[role="presentation"] textarea',
    'textarea',
    'input[type="text"]'
  ],

  submitButton: [
    // ARIA & Test IDs
    'button[aria-label*="Send" i]',
    'button[aria-label*="Submit" i]',
    'button[aria-label*="Generate" i]',
    'button[data-test-id="send-button"]',
    
    // Icon / Visual buttons inside input area
    'rich-textarea ~ button',
    '.input-area button:has(mat-icon)',
    '.input-area button:has(svg)',
    'button:has(svg[path*="send" i])',
    'button:has(svg[class*="send" i])',
    'button:has(mat-icon[fonticon*="send" i])',
    
    // Structural Fallback
    'form button[type="submit"]',
    'form button:last-of-type'
  ],

  conversationContainer: [
    '[data-test-id="conversation-turn"]',
    '[data-test-id="chat-history"]',
    'model-response',
    'response-container',
    '[role="list"]',
    'main [role="log"]',
    'main article',
    'main'
  ],

  imageElement: [
    'img[src*="googleusercontent.com"]',
    'img[src*="ggpht.com"]',
    'img[src^="blob:"]',
    'img[src^="data:image"]',
    'img[alt*="generated" i]',
    'img[alt*="image" i]',
    'img[data-test-id="generated-image"]',
    'img'
  ],

  generatingIndicator: [
    '[data-test-id="loading"]',
    'svg[class*="spinner"]',
    'mat-progress-spinner',
    'button[aria-label*="Stop" i]',
    '[aria-busy="true"]'
  ],

  safetyWarning: [
    '[data-test-id="safety-warning"]',
    '[data-test-id="blocked-content"]',
    'div:has-text("unable to generate")',
    'div:has-text("violates our guidelines")'
  ]
};

/**
 * Finds the first matching DOM element given an array of CSS selector fallbacks.
 * @param {string[]} selectorList - Ordered list of CSS selectors
 * @param {Function} [queryFn] - DOM query selector function, defaults to document.querySelector
 * @returns {Element|null} The matched DOM element or null
 */
export function findFirstMatchingSelector(selectorList, queryFn = null) {
  const query = queryFn || ((sel) => (typeof document !== 'undefined' ? document.querySelector(sel) : null));
  
  if (!Array.isArray(selectorList)) {
    return null;
  }

  for (const selector of selectorList) {
    try {
      const el = query(selector);
      if (el) {
        return el;
      }
    } catch (e) {
      // Ignore invalid or unsupported pseudo-selectors on old engines
    }
  }

  return null;
}
