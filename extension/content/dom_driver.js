/**
 * DOM interaction and humanized synthetic input driver for Gemini UI.
 */

import { SELECTOR_MAP, findFirstMatchingSelector } from './selectors.js';

/**
 * Simulates human typing and triggers React/Angular synthetic input events.
 * @param {HTMLElement} element - Input element (textarea or contenteditable div)
 * @param {string} text - Text to type
 * @returns {Promise<void>}
 */
export async function simulateTyping(element, text) {
  if (!element) {
    throw new Error("Cannot type into a null or undefined element.");
  }

  element.focus();

  // Clear existing content
  if (element.tagName && element.tagName.toLowerCase() === 'textarea') {
    element.value = '';
  } else {
    element.textContent = '';
  }

  // Attempt document.execCommand to hook cleanly into React/Angular event loop
  let inserted = false;
  try {
    inserted = document.execCommand('insertText', false, text);
  } catch (e) {
    inserted = false;
  }

  if (!inserted) {
    if (element.tagName && element.tagName.toLowerCase() === 'textarea') {
      element.value = text;
    } else {
      element.innerText = text;
    }
  }

  // Dispatch synthetic input events
  element.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
  element.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
  element.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: ' ' }));
  element.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: ' ' }));

  // Short delay to let frameworks react
  await new Promise((r) => setTimeout(r, 100));
}

/**
 * Finds and clicks the Submit / Send button.
 * @returns {Promise<boolean>} True if clicked successfully
 */
export async function clickSubmitButton() {
  const submitBtn = findFirstMatchingSelector(SELECTOR_MAP.submitButton);
  if (submitBtn) {
    submitBtn.focus();
    submitBtn.click();
    return true;
  }

  // Fallback: Dispatch Enter key on the active textarea
  const textarea = findFirstMatchingSelector(SELECTOR_MAP.textarea);
  if (textarea) {
    const enterEvent = new KeyboardEvent('keydown', {
      bubbles: true,
      cancelable: true,
      key: 'Enter',
      code: 'Enter',
      keyCode: 13
    });
    textarea.dispatchEvent(enterEvent);
    return true;
  }

  return false;
}
