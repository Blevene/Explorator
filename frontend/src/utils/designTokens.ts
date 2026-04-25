/**
 * Shared design tokens — single source of truth for colors used in JS.
 * All values reference CSS custom properties defined in index.css.
 * Use these instead of hardcoded Tailwind classes or hex values.
 */

export type ScoreTier = "high" | "mid" | "low";

/** Bucket a numeric score into one of three tiers. */
export function scoreTier(score: number): ScoreTier {
  if (score >= 8) return "high";
  if (score >= 6) return "mid";
  return "low";
}

/** Return the CSS variable value for a score tier. */
export function scoreColorVar(score: number): string {
  const tier = scoreTier(score);
  if (tier === "high") return "var(--score-high)";
  if (tier === "mid") return "var(--score-mid)";
  return "var(--score-low)";
}

/**
 * Shape glyph that mirrors a score tier as a redundant non-color signal.
 * High = up triangle, mid = diamond, low = down triangle.
 * Render with aria-hidden so screen readers don't double-announce alongside
 * the numeric score.
 */
export function scoreTierGlyph(score: number): string {
  const tier = scoreTier(score);
  if (tier === "high") return "▲"; // ▲
  if (tier === "mid") return "◆";  // ◆
  return "▼";                       // ▼
}

/** Genre accent CSS variable. */
export function genreAccentVar(genre: string): string {
  const key = genre.toLowerCase().replace(/[\s-]/g, "_");
  const map: Record<string, string> = {
    dream_pop: "var(--genre-dream-pop)",
    synthwave: "var(--genre-synthwave)",
    cinematic: "var(--genre-cinematic)",
  };
  return map[key] ?? "var(--accent-primary)";
}

/** Role badge color CSS variable. */
export function roleBadgeColorVar(role: string): string {
  const map: Record<string, string> = {
    best: "var(--role-safest)",
    safest: "var(--role-safest)",
    "runner-up": "var(--role-loop)",
    "best loop": "var(--role-loop)",
    wildcard: "var(--role-experimental)",
    experimental: "var(--role-experimental)",
  };
  return map[role.toLowerCase()] ?? "var(--text-secondary)";
}

/**
 * Canvas-safe color values — for use in canvas 2D context where CSS variables
 * don't work. These must be kept in sync with index.css.
 */
export const CANVAS_COLORS = {
  background: "#08090d",
  gridLine: "#181c25",
  barLine: "#252a38",
  voicingNote: "#f0b429",
  bassNote: "#6c9bef",
  melodyNote: "#34d399",  // emerald green, distinct from voicing (amber) and bass (blue)
  cursorLine: "#f0b429",
  labelText: "#7d8699",
  headerText: "#8891a5",
  headerBg: "#12151c",
  grooveAccent: "rgba(240, 180, 41, 0.25)",  // --accent-primary @ 25%

  genreAccent: {
    dream_pop: "#a78bfa",
    synthwave: "#f472b6",
    cinematic: "#eab308",
  } as Record<string, string>,
} as const;

/** Overlay backdrop for modals. */
export const OVERLAY_BACKDROP = "rgba(0, 0, 0, 0.7)";
