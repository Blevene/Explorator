import { describe, it, expect } from 'vitest';
import { scoreTier, scoreColorVar, scoreTierGlyph } from '../designTokens';

describe('scoreTier', () => {
  it('returns "high" at and above 8', () => {
    expect(scoreTier(8)).toBe('high');
    expect(scoreTier(8.5)).toBe('high');
    expect(scoreTier(10)).toBe('high');
  });
  it('returns "mid" at and above 6 but below 8', () => {
    expect(scoreTier(6)).toBe('mid');
    expect(scoreTier(7.99)).toBe('mid');
  });
  it('returns "low" below 6', () => {
    expect(scoreTier(5.99)).toBe('low');
    expect(scoreTier(0)).toBe('low');
    expect(scoreTier(-1)).toBe('low');
  });
});

describe('scoreColorVar', () => {
  it('maps tiers to the right CSS vars', () => {
    expect(scoreColorVar(9)).toBe('var(--score-high)');
    expect(scoreColorVar(7)).toBe('var(--score-mid)');
    expect(scoreColorVar(3)).toBe('var(--score-low)');
  });
});

describe('scoreTierGlyph', () => {
  it('returns up triangle for high', () => {
    expect(scoreTierGlyph(8)).toBe('▲');
    expect(scoreTierGlyph(10)).toBe('▲');
  });
  it('returns diamond for mid', () => {
    expect(scoreTierGlyph(6)).toBe('◆');
    expect(scoreTierGlyph(7.5)).toBe('◆');
  });
  it('returns down triangle for low', () => {
    expect(scoreTierGlyph(5.99)).toBe('▼');
    expect(scoreTierGlyph(0)).toBe('▼');
  });
  it('all three glyphs are pairwise distinct', () => {
    const glyphs = new Set([scoreTierGlyph(9), scoreTierGlyph(7), scoreTierGlyph(3)]);
    expect(glyphs.size).toBe(3);
  });
});
