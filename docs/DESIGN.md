# Explorator Frontend Design Language

## Aesthetic Direction: Studio Monitor

Dark, focused, precise. Ableton Live meets a high-end mixing console. This is a creative tool for music producers, not a data dashboard or generic React app.

## Core Principles

- **The music is the hero** — piano rolls, chord notation, and pitch visualization take center stage. Scores and metadata are supporting cast.
- **DAW-adjacent feel** — layouts, controls, and interactions should feel familiar to someone who uses Ableton, Logic, or Bitwig. Not a spreadsheet, not a social media feed.
- **Information density without clutter** — producers are comfortable with dense interfaces (mixing consoles, arrangement views). Don't oversimplify. Use density with clear hierarchy.
- **Dark foundation** — dark backgrounds reduce eye strain during long sessions and make colored musical data pop.

## Tokens vs. Tailwind

Color is owned by **CSS custom properties** defined in `frontend/src/index.css`. JS code references them via the helpers in `frontend/src/utils/designTokens.ts`. Components style with inline `style={{ background: 'var(--surface-2)' }}` rather than Tailwind color classes — Tailwind's role is layout / spacing / typography utilities, not the palette.

The exception is canvas drawing (piano roll, comparison view): the 2D context can't read CSS vars, so `CANVAS_COLORS` in `designTokens.ts` mirrors the relevant tokens as hex strings. Keep them in sync; the `CANVAS_COLORS` block has a comment to that effect.

When designing a new component:
1. Reach for an existing token first.
2. If the token doesn't exist but the use case is general (e.g., a new "warning" tier), define the token in `index.css` and update `designTokens.ts` if JS will reference it.
3. Hard-code a hex only when truly one-off (and even then, prefer a token).

## Color Palette

### Surfaces

| Token | Value | Use |
|---|---|---|
| `--surface-0` | `#08090d` | Page background, canvas background |
| `--surface-1` | `#0d0f14` | Main panels |
| `--surface-2` | `#12151c` | Cards, headers within panels |
| `--surface-3` | `#181c25` | Selected/hovered card lift, secondary buttons |
| `--surface-4` | `#1e2330` | Tertiary surfaces (rarely used) |

### Borders

| Token | Value | Use |
|---|---|---|
| `--border-subtle` | `#252a38` | Card edges, internal dividers |
| `--border-default` | `#2f3647` | Panel boundaries |
| `--border-bright` | `#3d4560` | Hover state, active inputs |

### Text

| Token | Value | Use |
|---|---|---|
| `--text-primary` | `#e2e6ef` | Body, chord symbols, emphasized labels |
| `--text-secondary` | `#8891a5` | Labels, secondary metadata |
| `--text-muted` | `#7d8699` | Tertiary metadata, placeholders, disabled |

### Accents (the music is the hero)

| Token | Value | Use |
|---|---|---|
| `--accent-primary` | `#f0b429` (amber) | Voicing notes, primary action highlight, app accent |
| `--accent-primary-dim` | `#f0b42933` | Hover background, soft glow |
| `--accent-secondary` | `#6c9bef` (blue) | Bass notes |
| `--accent-secondary-dim` | `#6c9bef22` | Bass-related backgrounds |
| `--accent-tertiary` | `#34d399` (emerald) | Melody notes, positive scores |
| `--accent-tertiary-dim` | `#34d39922` | Melody-related backgrounds |

### Scores

| Token | Value | Tier |
|---|---|---|
| `--score-high` | `#34d399` (emerald) | ≥ 8.0 |
| `--score-mid` | `#fbbf24` (amber) | 6.0 – 8.0 |
| `--score-low` | `#f87171` (rose) | < 6.0 |

`scoreColorVar(score)` in `designTokens.ts` returns the right CSS var for a given numeric score.

### Finalist roles

| Token | Value | Role |
|---|---|---|
| `--role-safest` | `#34d399` | Safest finalist |
| `--role-loop` | `#f0b429` | Best-loop finalist |
| `--role-experimental` | `#a78bfa` | Most-experimental finalist |

### Genre accents

The seed three genres have signature colors:

- `--genre-dream-pop` `#a78bfa` (violet)
- `--genre-synthwave` `#f472b6` (pink)
- `--genre-cinematic` `#eab308` (gold)

The system also ships 36 additional genres (M5c). For these, the accent falls through to `--accent-primary` (amber) by default. A small palette of `--genre-accent-{1..5}` exists for ad-hoc assignments. Do not add per-genre tokens for every genre — that would balloon the palette and force a decision per addition.

### Overlay

- `--overlay-backdrop` `rgba(0, 0, 0, 0.7)` for modal backdrops.

## Typography

Avoid generic fonts (Inter, Roboto, Arial, system fonts). Choose fonts with character.

### Musical data
Monospace or semi-monospace for pitch names, chord symbols, Roman numerals, MIDI values. This signals "precise data" and aligns with DAW conventions.

Recommended: `JetBrains Mono`, `IBM Plex Mono`, or `Fira Code`.

### UI labels & body
Geometric sans-serif with personality. Clean but not generic.

Recommended: `DM Sans`, `Outfit`, or `Sora`.

### Score numbers
Tabular numerals (`font-variant-numeric: tabular-nums`) for fixed-width digits so columns align in score panels and pattern cards.

## Layout patterns

### Split panel — `SessionWorkspace` arrangement view

- **Left panel** (~280px fixed): grouped arrangement list. Family header (chord-symbol row) + variant cards beneath.
- **Right panel** (flex remaining): detail view with transport, piano roll, score panel.

### Pattern library — `/patterns`

- Filter row at top: Genre input, Pattern Type select, Curated only checkbox.
- Card list below. Each `PatternCard` shows pattern type badge, genre, score, source-arrangement short-hash, tags, expandable abstracted_pattern JSON, optional notes, star button, delete button.
- Pagination via `Load more` button (keyset cursor — no infinite scroll, deliberate).

### Comparison view (M4c)

- Modal-overlay surface with a DAW-style lane stack: one `LaneSidebar` per arrangement, each with lane-level mute / solo controls.
- Single `ComparisonTransportBar` at top drives all lanes via a synchronized Tone.js transport.
- Cursor sweep on the (shared) piano roll renders all lanes' active notes.

### Genre management — `/genres`

- Library list (left) of all installed genres (39 today).
- Right pane shows genre detail OR research-agent progress when a job is active.
- Step indicator: 5-step pipeline (Research → Draft → Critique → Refine → Validate).

### Card hierarchy

For arrangement cards within a family:

- Family header: progression chord symbols as a row.
- Variant cards: voicing type + bass mode + groove + melody badges, weighted score.
- Selected card: left accent border in role color, subtle background lift (`--surface-3` over `--surface-2`).

For finalist cards (in `FinalistPanel`):

- Role badge (Safest / Best Loop / Most Experimental) at top-left, rounded full, color from `--role-*`.
- Score at top-right, color from `scoreColorVar()`.
- Star (curate / uncurate / disabled) immediately right of the score, color `--accent-primary`.
- Rationale truncated below.

### Piano roll (hero element)

- Background: `--surface-0`.
- Bar lines: `#252a38` (matches `--border-subtle`).
- Beat lines: `#181c25`.
- Y axis: visible MIDI range that contains notes, with ~1 octave of padding.
- Voicing notes: `--accent-primary` rectangles, height = 1 semitone, rounded corners.
- Bass notes: `--accent-secondary` rectangles in the lower register.
- Melody notes: `--accent-tertiary` rectangles in the upper register.
- Groove accents (M5a): subtle overlay glyphs/marks at accent beat positions.
- Cursor: thin vertical line in the genre accent (`--genre-*`), falling back to `--accent-primary`, sweeping with audio.

### Transport bar

- Fixed at top of detail panel, ~48px.
- Horizontal layout: play/pause, stop, tempo slider (60–200 BPM), loop toggle, per-track mutes (voicing, bass, melody), volume.
- Minimal chrome — controls are icon buttons with tooltips, no borders by default.
- Playing state: subtle pulsing indicator in `--accent-primary`.

### Score panel

- Below the piano roll, collapsible.
- Horizontal bar chart of the displayed dimensions, grouped:
  - **Arrangement:** voice_leading, register_density, playability.
  - **Progression:** genre_fit, emotional_fit, theoretical_coherence, cadence_quality, novelty, loopability.
  - groove, melody_support and collision_risk feed `weighted_total` but are not drawn yet. (A `tension_curve` dimension is planned — GitHub #3.)
- Weighted total displayed prominently. Each bar uses `scoreColorVar()`.

## Motion & interaction

- **Page transitions:** none (SPA, instant view switches).
- **Card selection:** 150ms background fade + accent border appear.
- **Piano roll load:** notes fade in with a staggered 50ms-per-bar left-to-right delay.
- **Playback cursor:** thin vertical line sweeping in sync with the audio engine.
- **Score bars:** animate width on load (200ms ease-out).
- **Mute toggle:** muted-track notes fade to ~20% opacity on the piano roll.
- **Star button (M5d-3):** instant visual flip on click, optimistic — store reverts and toasts on API failure. 300ms trailing-edge debounce prevents duplicate event-log entries from rapid double-clicks.
- **Toasts:** sonner in the bottom-right, dark theme, 3-second auto-dismiss, manual close button.

## Backgrounds & texture

- Subtle noise grain overlay at 2–3% opacity on the page background for analog warmth.
- No gradients on backgrounds — flat dark surfaces.
- Piano roll grid: clean, no texture — precision matters here.
- Card backgrounds: very subtle gradient from `--surface-2` to `--surface-3` (almost imperceptible, adds depth on selected state).

## Things to avoid

- Purple gradients on white backgrounds (AI slop).
- Rounded, bubbly, "friendly" UI patterns (this is a pro tool).
- Excessive whitespace (producers expect density).
- Cliched "music app" visuals (neon waveforms, vinyl records, equalizer bars, drum-machine pad mosaics).
- Generic component libraries with default styles (shadcn defaults, Material UI defaults).
- Animations on everything — animate the hero moments (piano roll, playback cursor), leave the rest crisp.
- Tailwind color classes for app palette (`bg-slate-900`, `text-emerald-400`). Use CSS variables.
- Hard-coded hex values in component code. Use a token, or define one if needed.
