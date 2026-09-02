/**
 * Image extraction, blob fetching, and buffer encoding utilities.
 */

/**
 * Converts an ArrayBuffer or TypedArray to a Base64 string.
 * @param {ArrayBuffer|Uint8Array} buffer
 * @returns {string} Base64 encoded representation
 */
export function arrayBufferToBase64(buffer) {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  
  if (typeof Buffer !== 'undefined') {
    return Buffer.from(bytes.buffer, bytes.byteOffset, bytes.byteLength).toString('base64');
  }
  
  let binary = '';
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  if (typeof btoa !== 'undefined') {
    return btoa(binary);
  }
  throw new Error("No Base64 encoder available in environment.");
}

/**
 * Sanitizes a prompt string into a safe filesystem-friendly slug.
 * @param {string} prompt
 * @param {number} [maxLength=60]
 * @returns {string} Sanitized slug
 */
export function sanitizePromptSlug(prompt, maxLength = 60) {
  if (!prompt) return "untitled";
  
  const slug = prompt
    .toLowerCase()
    .replace(/[^\w\s-]/g, ' ')  // Replace special punctuation with spaces
    .trim()
    .replace(/[\s_-]+/g, '-')   // Convert spaces/underscores to single hyphens
    .replace(/^-+|-+$/g, '');   // Trim leading/trailing hyphens

  return slug.substring(0, maxLength);
}

/**
 * Fetches an image URL using the current authenticated browser context and returns its Base64 data and mime type.
 * @param {string} url - Image source URL (https or blob)
 * @returns {Promise<{base64: string, mimeType: string, width?: number, height?: number}>}
 */
export async function fetchImageBlobAsBase64(url) {
  const response = await fetch(url, {
    credentials: 'include',
    cache: 'force-cache'
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch image: HTTP ${response.status} ${response.statusText}`);
  }

  const blob = await response.blob();
  const mimeType = blob.type || 'image/png';
  const arrayBuffer = await blob.arrayBuffer();
  const base64 = arrayBufferToBase64(arrayBuffer);

  return {
    base64,
    mimeType
  };
}
