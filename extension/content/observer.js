/**
 * MutationObserver for tracking Gemini generation state and image extraction.
 */

import { SELECTOR_MAP, findFirstMatchingSelector } from './selectors.js';
import { fetchImageBlobAsBase64 } from './extractor.js';

/**
 * Watches DOM for image generation lifecycle events for a specific request ID.
 * @param {Object} options
 * @param {string} options.id - Request UUID
 * @param {number} options.timeoutMs - Timeout in milliseconds
 * @param {Function} options.onStatus - Status update callback (status, message)
 * @param {Function} options.onImage - Image extracted callback (imageData)
 * @param {Function} options.onError - Error callback (errorCode, message, retryable)
 * @returns {Function} Cancel function to disconnect observer
 */
export function watchForImageGeneration({
  id,
  timeoutMs = 120000,
  onStatus,
  onImage,
  onError
}) {
  let isDone = false;
  let timer = null;
  const processedImages = new Set();
  let imageCount = 0;

  // Track existing images before prompt was submitted so we only capture NEW images
  const initialImages = new Set(
    Array.from(document.querySelectorAll('img')).map((img) => img.src)
  );

  onStatus?.("GENERATING", "Monitoring DOM for generated images...");

  const observer = new MutationObserver(async (mutations) => {
    if (isDone) return;

    // Check for safety blocked warnings
    const safetyEl = findFirstMatchingSelector(SELECTOR_MAP.safetyWarning);
    if (safetyEl && safetyEl.offsetParent !== null) {
      cleanup();
      onError?.("SAFETY_BLOCKED", "Prompt was blocked by Gemini safety guidelines.", false);
      return;
    }

    // Check for new img elements
    const currentImgs = Array.from(document.querySelectorAll('img'));
    for (const img of currentImgs) {
      const src = img.src;
      if (!src) continue;

      // Filter: Must be a newly rendered image not present before prompt submission
      if (initialImages.has(src) || processedImages.has(src)) {
        continue;
      }

      // Check if matches Gemini image heuristics (googleusercontent or blob URL)
      const isGeminiImg =
        src.includes("googleusercontent.com") ||
        src.startsWith("blob:") ||
        (img.alt && img.alt.toLowerCase().includes("generated"));

      if (isGeminiImg) {
        processedImages.add(src);
        imageCount++;
        onStatus?.("RENDERING", `Extracting image ${imageCount}...`);

        try {
          const { base64, mimeType } = await fetchImageBlobAsBase64(src);
          onImage?.({
            id,
            image_index: imageCount,
            mime_type: mimeType,
            data_base64: base64,
            metadata: {
              width: img.naturalWidth || img.width || undefined,
              height: img.naturalHeight || img.height || undefined,
              source_url: src.startsWith("blob:") ? undefined : src
            }
          });
        } catch (err) {
          console.error("[ImageGenPiper Observer] Image fetch error:", err);
        }
      }
    }

    // Check if generation completed (spinner gone and at least 1 image found)
    const isSpinnerActive = !!findFirstMatchingSelector(SELECTOR_MAP.generatingIndicator);
    if (!isSpinnerActive && imageCount > 0) {
      // Delay slightly in case multi-image rendering completes
      setTimeout(() => {
        if (!isDone) {
          cleanup();
          onStatus?.("DONE", `Completed generation with ${imageCount} image(s).`);
        }
      }, 1500);
    }
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['src', 'class', 'style', 'aria-busy']
  });

  // Watchdog timeout
  timer = setTimeout(() => {
    if (!isDone) {
      cleanup();
      if (imageCount === 0) {
        onError?.("TIMEOUT", `Image generation timed out after ${timeoutMs / 1000}s.`, true);
      } else {
        onStatus?.("DONE", `Completed with ${imageCount} image(s) before timeout.`);
      }
    }
  }, timeoutMs);

  function cleanup() {
    isDone = true;
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    observer.disconnect();
  }

  return cleanup;
}
