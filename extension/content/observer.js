/**
 * MutationObserver for tracking Gemini generation state and image extraction
 * with Turn-Scoped isolation and strict intra-turn deduplication.
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
  const processedUrls = new Set();
  let imageCount = 0;

  // Snapshot existing images in DOM before this turn's prompt execution
  const existingImages = new Set(
    Array.from(document.querySelectorAll('img')).map((img) => img.src || img.currentSrc)
  );

  onStatus?.("GENERATING", "Monitoring latest conversation turn for generated image...");

  const observer = new MutationObserver(async (mutations) => {
    if (isDone) return;

    // 1. Check for safety blocked warnings
    const safetyEl = findFirstMatchingSelector(SELECTOR_MAP.safetyWarning);
    if (safetyEl && safetyEl.offsetParent !== null) {
      cleanup();
      onError?.("SAFETY_BLOCKED", "Prompt was blocked by Gemini safety guidelines.", false);
      return;
    }

    // 2. Identify candidate images in DOM
    const currentImgs = Array.from(document.querySelectorAll('img'));
    
    // Find newly appended images that were NOT in DOM prior to this prompt
    const candidateImgs = currentImgs.filter((img) => {
      const src = img.src || img.currentSrc;
      if (!src || src.startsWith("data:image/svg") || src.includes("avatar")) {
        return false;
      }
      return !existingImages.has(src) && !processedUrls.has(src);
    });

    for (const img of candidateImgs) {
      if (isDone) break;

      const src = img.src || img.currentSrc;
      if (!src || processedUrls.has(src)) continue;

      // Validate that it is a genuine Gemini generated image asset
      const isGeminiImg =
        src.includes("googleusercontent.com") ||
        src.includes("ggpht.com") ||
        src.startsWith("blob:") ||
        src.startsWith("data:image") ||
        (img.alt && img.alt.toLowerCase().includes("generated")) ||
        (img.dataset && img.dataset.testId === "generated-image");

      // Filter out tiny icons / avatars
      const width = img.naturalWidth || img.width || 0;
      const height = img.naturalHeight || img.height || 0;
      const isTooSmall = (width > 0 && width < 150) || (height > 0 && height < 150);

      if (isGeminiImg && !isTooSmall) {
        // Mark URL as processed immediately to prevent concurrent fetches
        processedUrls.add(src);
        imageCount++;
        onStatus?.("RENDERING", `Extracting image ${imageCount}...`);

        try {
          const { base64, mimeType } = await fetchImageBlobAsBase64(src);
          
          if (!isDone) {
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

            // Single image per turn: complete generation immediately
            cleanup();
            onStatus?.("DONE", `Completed generation for prompt.`);
            break;
          }
        } catch (err) {
          console.error("[ImageGenPiper Observer] Image fetch error:", err);
        }
      }
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
