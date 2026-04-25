# ADR 008 — CSS custom properties + `designTokens.ts` for the palette

**Status:** Accepted

## Context

Early in the project, frontend components used Tailwind color classes directly: `bg-slate-900`, `text-emerald-400`, `border-amber-500`. This worked initially but accumulated problems:

- A score-color decision repeated dozens of times across components, each spelled the same way but with no central source of truth.
- A genre accent was a hex hardcoded into one place but used as a Tailwind class elsewhere.
- The "studio monitor" aesthetic ([`docs/DESIGN.md`](../DESIGN.md)) needed semantic names (`surface-1`, `accent-primary`) that didn't map to Tailwind's color scale.
- Canvas-based components (piano roll, comparison view) needed hex strings, not CSS classes — `ctx.fillStyle = "amber-400"` doesn't work.

We needed a way to express semantic tokens that worked across CSS, JSX inline styles, and 2D canvas contexts.

## Decision

**Three tiers, one source of truth at the top.**

1. **CSS custom properties** in `frontend/src/index.css` are the source of truth. Tokens are named semantically (`--surface-1`, `--accent-primary`, `--score-high`, `--role-safest`) and given hex values once.

2. **Component code consumes tokens via inline `style={{ color: 'var(--accent-primary)' }}`** — not via Tailwind color classes. Tailwind is still used for layout / spacing / typography utilities; just not for the app palette.

3. **`frontend/src/utils/designTokens.ts`** exports JS-side helpers that wrap the CSS variable names (`scoreColorVar(score)`, `genreAccentVar(genre)`, `roleBadgeColorVar(role)`) plus a `CANVAS_COLORS` object with the hex equivalents for canvas use. The module's docstring is explicit: keep `CANVAS_COLORS` in sync with `index.css`.

Score / role / genre tiers are domain-specific:

```css
--score-high: #34d399;     /* >= 8.0 */
--score-mid: #fbbf24;      /* 6.0 – 8.0 */
--score-low: #f87171;      /* < 6.0 */

--role-safest: #34d399;
--role-loop: #f0b429;
--role-experimental: #a78bfa;

--genre-dream-pop: #a78bfa;
--genre-synthwave: #f472b6;
--genre-cinematic: #eab308;
```

Genres outside the seed three fall through to `--accent-primary` rather than getting a per-genre token (40+ tokens would balloon the palette and force a decision per addition).

## Consequences

**Positive:**
- A palette change is a one-line edit in `index.css`. The whole app updates.
- Components are easy to read — `var(--surface-2)` says "secondary surface" where `bg-slate-800` says nothing about role.
- Canvas drawing reads from the same conceptual palette as the DOM; even if the JS-side hex literal mirrors the CSS var, the convention enforces consistency and the comment in `CANVAS_COLORS` makes the duplication visible.
- The "studio monitor" aesthetic from `docs/DESIGN.md` is faithfully encoded; future contributors browsing index.css see the actual colors and their semantic names side by side.

**Negative:**
- Two places to update for a palette change that includes canvas (CSS + `CANVAS_COLORS`). The `designTokens.ts` docstring flags this; a future cleanup could generate `CANVAS_COLORS` from a build step that parses `index.css`. Not worth it at current size.
- Inline `style={{...}}` is slightly more verbose than a Tailwind class. Acceptable tradeoff.
- New contributors who are deeply Tailwind-fluent might reach for `bg-slate-900` reflexively. The DESIGN.md "Things to avoid" section calls this out explicitly.

## Revisit if

The number of tokens grows to a point where reading `index.css` is no longer informative. At that point a token-organization pass (group into surfaces / accents / scores / roles / genres) — already partially done — becomes mandatory. Or we adopt a token tool like Style Dictionary if the palette ships outside this repo.

## See also

- `frontend/src/index.css` (token definitions)
- `frontend/src/utils/designTokens.ts` (JS-side helpers + `CANVAS_COLORS`)
- [`docs/DESIGN.md`](../DESIGN.md) (the design language these tokens serve)
