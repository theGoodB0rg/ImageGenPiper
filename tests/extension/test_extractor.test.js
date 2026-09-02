import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { arrayBufferToBase64, sanitizePromptSlug } from '../../extension/content/extractor.js';

describe('Extractor & Utility Tests', () => {
  it('should convert ArrayBuffer to base64 correctly', () => {
    const text = "Hello Gemini";
    const buffer = new TextEncoder().encode(text);
    const b64 = arrayBufferToBase64(buffer.buffer);
    assert.equal(b64, Buffer.from(text).toString('base64'));
  });

  it('should sanitize prompt into filesystem-friendly slug', () => {
    const prompt = "A Cyberpunk City (8k! High-Res) --ar 16:9 / futuristic";
    const slug = sanitizePromptSlug(prompt);
    assert.equal(slug, "a-cyberpunk-city-8k-high-res-ar-16-9-futuristic");
  });

  it('should truncate excessively long prompt slugs', () => {
    const longPrompt = "a".repeat(200);
    const slug = sanitizePromptSlug(longPrompt, 50);
    assert.equal(slug.length, 50);
  });
});
