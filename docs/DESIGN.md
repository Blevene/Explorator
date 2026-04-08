# MusicExplorator Frontend Design Language

## Aesthetic Direction: Studio Monitor

Dark, focused, precise. Ableton Live meets a high-end mixing console. This is a creative tool for music producers, not a data dashboard or generic React app.

## Core Principles

- **The music is the hero** — piano rolls, chord notation, and pitch visualization take center stage. Scores and metadata are supporting cast.
- **DAW-adjacent feel** — layouts, controls, and interactions should feel familiar to someone who uses Ableton, Logic, or Bitwig. Not a spreadsheet, not a social media feed.
- **Information density without clutter** — producers are comfortable with dense interfaces (mixing consoles, arrangement views). Don't oversimplify. Use density with clear hierarchy.
- **Dark foundation** — dark backgrounds reduce eye strain during long sessions and make colored musical data pop.

## Color Palette

### Foundation
- Background: `slate-950` (#020617) primary, `slate-900` (#0f172a) panels
- Surface: `slate-800` (#1e293b) cards, `slate-700` (#334155) borders
- Text: `slate-100` (#f1f5f9) primary, `slate-400` (#94a3b8) secondary

### Musical Data (the star)
- Voicing notes: warm amber/gold `amber-400` (#fbbf24) to `amber-500` (#f59e0b)
- Bass notes: cool cyan/teal `cyan-400` (#22d3ee) to `cyan-500` (#06b6d4)
- Chord symbols: `slate-100` with subtle glow on hover

### Genre Accents
Each genre gets a signature highlight color used for badges, active states, and score accents:
- Dream Pop: soft purple `violet-400` (#a78bfa)
- Synthwave: hot pink `pink-400` (#f472b6)
- Cinematic: deep gold `yellow-500` (#eab308)

### Score Colors
- Excellent (8+): `emerald-400` (#34d399)
- Good (6-8): `amber-400` (#fbbf24)
- Poor (<6): `rose-400` (#fb7185)

### Transport Controls
- Default: `slate-500` — almost invisible, unobtrusive
- Hover/active: `slate-200` — appears on interaction
- Playing indicator: genre accent color pulse

## Typography

Avoid generic fonts (Inter, Roboto, Arial, system fonts). Choose fonts with character.

### Musical Data
Monospace or semi-monospace for pitch names, chord symbols, Roman numerals, MIDI values. This signals "precise data" and aligns with DAW conventions.

Recommendation: `JetBrains Mono`, `IBM Plex Mono`, or `Fira Code`

### UI Labels & Body
Geometric sans-serif with personality. Clean but not generic.

Recommendation: `DM Sans`, `Outfit`, or `Sora`

### Score Numbers
Tabular numerals (fixed-width digits) for score values so columns align.

## Layout Patterns

### Split Panel (M2c Arrangement View)
- **Left panel** (~280px): arrangement list, compact cards, grouped by family
- **Right panel** (flex remaining): detail view with transport + piano roll + scores
- Resizable divider (optional)

### Card Hierarchy
Arrangement cards within a family:
- Family header: progression chord symbols as a row
- Variant cards below: voicing type + bass mode badges, weighted score bar
- Selected card: left accent border in genre color, subtle background lift

### Piano Roll (Hero Element)
- Dark grid on `slate-950`
- X axis: bars/beats, with bar numbers
- Y axis: MIDI pitch range (show only the range that contains notes, with ~1 octave padding)
- Voicing notes: amber rectangles with rounded corners, height = 1 semitone
- Bass notes: cyan rectangles, same grid but visually distinct (below or separated by register gap)
- Grid lines: `slate-800` for beats, `slate-700` slightly brighter for bar lines
- Register zones: very subtle background shading to show low/mid/high

### Transport Bar
- Fixed at top of detail panel, ~48px
- Horizontal layout: [play/pause] [stop] [tempo: 120 BPM slider] [loop toggle] [mute: voicing] [mute: bass] [volume slider]
- Minimal chrome — controls appear as icons with tooltips, not buttons with borders
- Playing state: subtle pulsing indicator in genre accent color

### Score Panel
- Below piano roll, collapsible
- Horizontal bar chart: 9 dimensions, each as a thin bar with value label
- Grouped: "Arrangement" (voice_leading, register_density, playability) above "Progression" (genre_fit, emotional_fit, coherence, cadence, novelty, loopability)
- Weighted total displayed prominently

## Motion & Interaction

- **Page transitions**: none (SPA, instant panel switches)
- **Card selection**: 150ms background fade + border accent appear
- **Piano roll load**: notes fade in with staggered delay per bar (left to right, 50ms per bar)
- **Playback cursor**: thin vertical line sweeping across piano roll in sync with audio, genre accent color
- **Score bars**: animate width on load (200ms ease-out)
- **Mute toggle**: muted track notes fade to 20% opacity on piano roll

## Backgrounds & Texture

- Subtle noise grain overlay on main background (2-3% opacity) for analog warmth
- No gradients on backgrounds — flat dark surfaces
- Piano roll grid: clean, no texture — precision matters here
- Card backgrounds: very subtle gradient from `slate-800` to `slate-850` (almost imperceptible, adds depth)

## Things to Avoid

- Purple gradients on white backgrounds (AI slop)
- Rounded, bubbly, "friendly" UI patterns (this is a pro tool)
- Excessive whitespace (producers expect density)
- Cliched "music app" visuals (neon waveforms, vinyl records, equalizer bars)
- Generic component libraries with default styles (shadcn defaults, Material UI defaults)
- Animations on everything — animate the hero moments (piano roll, playback cursor), leave the rest crisp
