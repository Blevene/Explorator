# Design System Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the frontend onto a single styling source of truth (CSS variables), eliminate Tailwind hardcoded colors from components, and add the spec'd animations.

**Architecture:** All color values flow from CSS variables in `index.css`. Components reference variables via inline styles. Tailwind is used for layout utilities only (flex, gap, padding, grid). A shared `designTokens.ts` provides JS access to variable names for canvas rendering and score coloring.

**Tech Stack:** React, CSS custom properties, Tailwind (layout only)

---

### Task 1: Create shared design tokens utility

**Files:**
- Create: `frontend/src/utils/designTokens.ts`

- [ ] **Step 1: Create the design tokens utility**

Create `frontend/src/utils/designTokens.ts`:

```typescript
/**
 * Shared design tokens — single source of truth for colors used in JS.
 * All values reference CSS custom properties defined in index.css.
 * Use these instead of hardcoded Tailwind classes or hex values.
 */

/** Return the CSS variable value for a score tier. */
export function scoreColorVar(score: number): string {
  if (score >= 8) return "var(--score-high)";
  if (score >= 6) return "var(--score-mid)";
  return "var(--score-low)";
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
  voicingNote: "#f0b429",      // --accent-primary (amber)
  bassNote: "#6c9bef",          // --accent-secondary (blue)
  cursorLine: "#f0b429",         // --accent-primary
  labelText: "#555e74",          // --text-muted
  headerText: "#8891a5",         // --text-secondary
  headerBg: "#12151c",           // --surface-2

  // Genre-specific accent overrides
  genreAccent: {
    dream_pop: "#a78bfa",
    synthwave: "#f472b6",
    cinematic: "#eab308",
  } as Record<string, string>,
} as const;

/** Overlay backdrop for modals. */
export const OVERLAY_BACKDROP = "rgba(0, 0, 0, 0.7)";
```

- [ ] **Step 2: Verify frontend builds**

Run: `cd /home/angel/Documents/code/Explorator/frontend && npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/utils/designTokens.ts
git commit -m "feat: shared designTokens utility — single source of truth for JS color access"
```

---

### Task 2: Migrate ArrangementCard to CSS variables

**Files:**
- Modify: `frontend/src/components/ArrangementCard.tsx`

This is the main offender — uses Tailwind color classes (`text-emerald-400`, `bg-slate-800`, `border-violet-500`) instead of CSS variables.

- [ ] **Step 1: Replace GENRE_ACCENT Tailwind classes with CSS variables**

Replace:
```typescript
const GENRE_ACCENT: Record<string, string> = {
  dream_pop: "border-violet-500",
  synthwave: "border-pink-500",
  cinematic: "border-yellow-500",
}

function getAccentBorder(genre: string): string {
  const key = genre.toLowerCase().replace(/[\s-]/g, "_")
  return GENRE_ACCENT[key] ?? GENRE_ACCENT["dream_pop"]
}
```

With import + inline style approach:
```typescript
import { scoreColorVar, genreAccentVar } from "../utils/designTokens"
```

- [ ] **Step 2: Replace scoreColor Tailwind function with CSS variable function**

Remove:
```typescript
function scoreColor(score: number): string {
  if (score >= 8) return "text-emerald-400"
  if (score >= 6) return "text-amber-400"
  return "text-rose-400"
}
```

Use `scoreColorVar` from designTokens instead (returns `var(--score-high)` etc.) applied via `style={{ color: scoreColorVar(score) }}`.

- [ ] **Step 3: Replace all Tailwind color classes in the component JSX**

Convert the entire component from `className`-based colors to `style`-based CSS variables. Key replacements:

| Old (Tailwind) | New (CSS variable) |
|---|---|
| `bg-slate-800` | `background: 'var(--surface-3)'` |
| `bg-slate-900` | `background: 'var(--surface-1)'` |
| `border-slate-700` | `border: '1px solid var(--border-default)'` |
| `text-slate-500` | `color: 'var(--text-muted)'` |
| `text-slate-400` | `color: 'var(--text-secondary)'` |
| `text-slate-300` | `color: 'var(--text-primary)'` |
| `text-emerald-400` | `color: 'var(--score-high)'` |
| `text-amber-400` | `color: 'var(--score-mid)'` |
| `text-rose-400` | `color: 'var(--score-low)'` |
| `bg-amber-400/10` | `background: 'var(--accent-primary-dim)'` |
| `bg-cyan-400/10` | `background: 'var(--accent-secondary-dim)'` |
| `text-amber-400` (badge) | `color: 'var(--accent-primary)'` |
| `text-cyan-400` (badge) | `color: 'var(--accent-secondary)'` |
| `border-violet-500` | `borderColor: genreAccentVar(genre)` |
| `hover:bg-slate-800` | `onMouseEnter` with `var(--surface-3)` |

The selected state border uses genre accent: `borderLeft: selected ? '4px solid ' + genreAccentVar(genre) : 'none'`.

- [ ] **Step 4: Replace explanation section Tailwind colors**

The explanation display section (lines 134-171) uses:
- `text-slate-300 italic` → `style={{ color: 'var(--text-primary)', fontStyle: 'italic' }}`
- `text-emerald-400 font-medium` → `style={{ color: 'var(--score-high)', fontWeight: 500 }}`
- `text-amber-400 font-medium` → `style={{ color: 'var(--score-mid)', fontWeight: 500 }}`
- `text-sky-400 font-medium` → `style={{ color: 'var(--accent-secondary)', fontWeight: 500 }}`
- `text-slate-400` (list items) → `style={{ color: 'var(--text-secondary)' }}`
- `border-slate-700` → `borderColor: 'var(--border-default)'`

- [ ] **Step 5: Verify frontend builds**

Run: `cd /home/angel/Documents/code/Explorator/frontend && npm run build`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ArrangementCard.tsx
git commit -m "refactor: migrate ArrangementCard from Tailwind colors to CSS variables"
```

---

### Task 3: Migrate ComparisonView scoreColor to CSS variables

**Files:**
- Modify: `frontend/src/components/ComparisonView.tsx`

- [ ] **Step 1: Replace local scoreColor with designTokens import**

Remove the local `scoreColor` function (lines 30-34). Import `scoreColorVar` from `../utils/designTokens`.

Replace className-based score coloring:
```tsx
<span className={`font-mono ${scoreColor(score)} ...`}>
```

With style-based:
```tsx
<span className="font-mono" style={{ color: scoreColorVar(score), fontWeight: isLeader ? 700 : 400, opacity: isLeader ? 1 : 0.7 }}>
```

Also replace `text-slate-500` (line 67) with `style={{ color: 'var(--text-muted)' }}`.

- [ ] **Step 2: Verify frontend builds**

Run: `cd /home/angel/Documents/code/Explorator/frontend && npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ComparisonView.tsx
git commit -m "refactor: migrate ComparisonView to shared scoreColorVar utility"
```

---

### Task 4: Migrate PianoRoll canvas to design tokens

**Files:**
- Modify: `frontend/src/components/PianoRoll.tsx`

- [ ] **Step 1: Import CANVAS_COLORS from designTokens**

```typescript
import { CANVAS_COLORS } from "../utils/designTokens"
```

- [ ] **Step 2: Replace hardcoded hex values in the canvas drawing**

Find all hardcoded color strings in the `useEffect` canvas drawing closure and replace with `CANVAS_COLORS` references:

| Old (hardcoded) | New (CANVAS_COLORS) |
|---|---|
| `"#0f172a"` or `"#08090d"` (background) | `CANVAS_COLORS.background` |
| `"#1e293b"` (grid lines) | `CANVAS_COLORS.gridLine` |
| `"#334155"` or similar (bar lines) | `CANVAS_COLORS.barLine` |
| Amber hex for voicing notes | `CANVAS_COLORS.voicingNote` |
| Cyan/blue hex for bass notes | `CANVAS_COLORS.bassNote` |
| Genre-specific accent colors | `CANVAS_COLORS.genreAccent[genre] ?? CANVAS_COLORS.voicingNote` |
| Label text colors | `CANVAS_COLORS.labelText` |

Read the file first to identify the exact hex values used.

- [ ] **Step 3: Verify frontend builds**

Run: `cd /home/angel/Documents/code/Explorator/frontend && npm run build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/PianoRoll.tsx
git commit -m "refactor: migrate PianoRoll canvas colors to shared CANVAS_COLORS tokens"
```

---

### Task 5: Standardize modal overlays and hover states

**Files:**
- Modify: `frontend/src/components/ExportModal.tsx`
- Modify: `frontend/src/components/MutateModal.tsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Add overlay variable to index.css**

In `:root`, add:
```css
--overlay-backdrop: rgba(0, 0, 0, 0.7);
```

- [ ] **Step 2: Update ExportModal backdrop**

Replace `style={{ background: "rgba(0,0,0,0.7)" }}` with `style={{ background: "var(--overlay-backdrop)" }}`.

- [ ] **Step 3: Update MutateModal backdrop**

Replace `style={{ background: 'rgba(0,0,0,0.7)' }}` with `style={{ background: 'var(--overlay-backdrop)' }}`.

- [ ] **Step 4: Add hover utility classes to index.css**

Add card hover state as a CSS class instead of JS events:

```css
/* Card hover states */
.card-interactive {
  transition: border-color 150ms ease, background-color 150ms ease;
}
.card-interactive:hover {
  border-color: var(--accent-primary-dim);
  background-color: var(--surface-3);
}
```

- [ ] **Step 5: Update CandidateCard to use CSS hover**

In `CandidateCard.tsx`, remove `onMouseEnter`/`onMouseLeave` handlers and add `card-interactive` class:

Replace:
```tsx
onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--accent-primary-dim)')}
onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}
```

With `className="... card-interactive"` on the root div.

- [ ] **Step 6: Verify frontend builds**

Run: `cd /home/angel/Documents/code/Explorator/frontend && npm run build`

- [ ] **Step 7: Commit**

```bash
git add frontend/src/index.css frontend/src/components/ExportModal.tsx frontend/src/components/MutateModal.tsx frontend/src/components/CandidateCard.tsx
git commit -m "refactor: standardize modal overlays and card hover states via CSS"
```

---

### Task 6: Add spec'd animations

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/src/components/CandidateCard.tsx`
- Modify: `frontend/src/components/PianoRoll.tsx`

- [ ] **Step 1: Add animation keyframes to index.css**

```css
/* Score bar width animation */
@keyframes score-bar-fill {
  from { width: 0; }
}

/* Card fade-in for staggered load */
@keyframes card-fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.card-animated {
  animation: card-fade-in 200ms ease-out both;
}
```

- [ ] **Step 2: Apply staggered card animation in SessionWorkspace**

Where candidate cards are rendered in a `.map()`, pass the index as `style={{ animationDelay: '${index * 50}ms' }}` with the `card-animated` class.

- [ ] **Step 3: Add score bar animation to ScorePanel or CandidateCard**

Where score bars are rendered, add:
```css
animation: score-bar-fill 200ms ease-out;
```

- [ ] **Step 4: Verify frontend builds**

Run: `cd /home/angel/Documents/code/Explorator/frontend && npm run build`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/index.css frontend/src/components/CandidateCard.tsx frontend/src/views/SessionWorkspace.tsx
git commit -m "feat: add spec'd animations — card stagger, score bar fill"
```

---

## File Map Summary

| # | File | Action | Task |
|---|------|--------|------|
| 1 | `frontend/src/utils/designTokens.ts` | Create | 1 |
| 2 | `frontend/src/components/ArrangementCard.tsx` | Modify | 2 |
| 3 | `frontend/src/components/ComparisonView.tsx` | Modify | 3 |
| 4 | `frontend/src/components/PianoRoll.tsx` | Modify | 4 |
| 5 | `frontend/src/components/ExportModal.tsx` | Modify | 5 |
| 6 | `frontend/src/components/MutateModal.tsx` | Modify | 5 |
| 7 | `frontend/src/components/CandidateCard.tsx` | Modify | 5 |
| 8 | `frontend/src/index.css` | Modify | 5, 6 |
| 9 | `frontend/src/views/SessionWorkspace.tsx` | Modify | 6 |
