import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { SELECTOR_MAP, findFirstMatchingSelector } from '../../extension/content/selectors.js';

describe('Selector Engine Tests', () => {
  it('should have required selector categories in SELECTOR_MAP', () => {
    assert.ok(Array.isArray(SELECTOR_MAP.textarea), 'textarea selectors missing');
    assert.ok(Array.isArray(SELECTOR_MAP.submitButton), 'submitButton selectors missing');
    assert.ok(Array.isArray(SELECTOR_MAP.imageElement), 'imageElement selectors missing');
    assert.ok(Array.isArray(SELECTOR_MAP.generatingIndicator), 'generatingIndicator selectors missing');
  });

  it('should find first matching selector from list', () => {
    const mockElement = { tagName: 'TEXTAREA', id: 'target' };
    const mockQuerySelector = (sel) => {
      if (sel === '[data-test-id="input-textarea"]') {
        return mockElement;
      }
      return null;
    };

    const result = findFirstMatchingSelector(
      SELECTOR_MAP.textarea,
      mockQuerySelector
    );

    assert.deepEqual(result, mockElement);
  });

  it('should fallback gracefully when earlier selectors are not present', () => {
    const mockElement = { tagName: 'TEXTAREA', id: 'fallback-match' };
    const mockQuerySelector = (sel) => {
      if (sel === 'textarea') {
        return mockElement;
      }
      return null;
    };

    const result = findFirstMatchingSelector(
      SELECTOR_MAP.textarea,
      mockQuerySelector
    );

    assert.deepEqual(result, mockElement);
  });

  it('should return null when no selectors match', () => {
    const mockQuerySelector = () => null;
    const result = findFirstMatchingSelector(
      SELECTOR_MAP.textarea,
      mockQuerySelector
    );
    assert.equal(result, null);
  });
});
