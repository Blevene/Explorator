<!-- stage: refine -->
# Genre Refinement: {genre_name}

You are refining genre data based on an independent critique. You have access to the original research to make informed corrections.

## Original Research

{research_log}

## Current Draft

{draft_yamls}

## Critique to Address

{critique}

## CRITICAL: Allowed Value Vocabulary

You MUST use values from these constrained sets. Do NOT invent new labels.

**Tendency levels**: `low`, `low_medium`, `medium`, `medium_high`, `high`
**Spacing**: `open`, `closed`, `mixed`
**Register bias**: `low`, `mid`, `mid_high`, `high`
**Comp density**: `sparse`, `moderate`, `busy`
**Syncopation level**: `none`, `light`, `moderate`, `heavy`
**Articulation style**: two-word descriptive `snake_case` label (NOT a tendency level). Examples: `floating_pulse`, `arpeggiated_pulse`, `driving_straight`, `bouncy_staccato`, `choppy_funk`
**Bass mode**: `supportive`, `pedal`, `syncopated`
**Rhythmic density**: `sparse`, `moderate`, `active`
**Voicing type**: `open`, `closed`, `drop2`, `quartal`, `cluster`
**Voicing density**: `sparse`, `medium`, `dense`
**Melodic motion_preference**: `stepwise`, `leaping`, `mixed`
**Melodic range_placement**: `above_voicing`, `overlapping`, `wide`
**Melodic density**: `sparse`, `moderate`, `active`
**Melodic strong_beat_preference**: `chord_tones`, `extensions`, `roots`
**Harmonic vocabulary**: lowercase chord symbols (`maj7`, `m7`, `add9`, `sus2`, `7`, `m9`, etc.)

## Task

Apply the critique's suggestions to produce an improved version of the three YAML structures. Use the original research to make musically informed corrections — don't just mechanically apply suggestions without considering whether they make sense in context.

Ensure all values conform to the allowed vocabulary above. Keep the same key ordering as the original draft.

Return valid JSON with top-level keys: "profile", "rules", "grammar" — same structure as the original draft.
