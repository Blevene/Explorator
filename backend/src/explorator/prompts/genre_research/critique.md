<!-- stage: critique -->
# Genre Critique: {genre_name}

You are an independent music theory reviewer. You have NOT seen the research that produced these drafts — you are reviewing them fresh.

## Draft YAMLs to Review

{draft_yamls}

## Critique Instructions

Review the draft genre data for **{genre_name}** across these dimensions:

1. **Musical Accuracy**: Do the harmonic vocabulary, tendencies, and devices actually match this genre? Flag anything that seems wrong or generic.

2. **Internal Consistency**: Do the profile tendencies, rules, and grammar agree with each other? For example, if harmonic_tendencies says "low functional strength" but grammar has strong cadence archetypes, that's inconsistent.

3. **Completeness**: Compare against what you'd expect for a well-defined genre profile. Are any important chord types missing? Are rules too generic? Are anti-patterns specific enough?

4. **Weight Ranges**: Are all weights between 0.0 and 1.0? Do experimentation_envelope values seem plausible for this genre? Are severity values reasonable?

5. **Structural Correctness**: Are all required fields present? Are list fields actually lists? Are dict fields actually dicts?

6. **Value Vocabulary Conformance**: All tendency values MUST be from: `low`, `low_medium`, `medium`, `medium_high`, `high`. Bass modes MUST be one of: `supportive`, `pedal`, `syncopated`. Voicing types MUST be from: `open`, `closed`, `drop2`, `quartal`, `cluster`. Melodic fields MUST use: motion_preference (`stepwise`/`leaping`/`mixed`), range_placement (`above_voicing`/`overlapping`/`wide`), density (`sparse`/`moderate`/`active`), strong_beat_preference (`chord_tones`/`extensions`/`roots`). Harmonic vocabulary MUST use lowercase chord symbols (`maj7` not `Maj7`). Register values must be semantic labels (`low`, `mid`, `mid_high`, `high`) not concrete ranges like `C3-C5`. **SPECIAL: `articulation_style`** must be a two-word descriptive `snake_case` label (e.g., `floating_pulse`, `driving_straight`, `bouncy_staccato`) — it is NOT a tendency level. If it contains `low`, `medium`, `high`, or similar, flag as MAJOR. Flag any non-conforming values as MAJOR issues.

7. **Anti-patterns**: The rules section MUST include at least one anti-pattern. If `anti_patterns` is empty, flag as a MAJOR issue — every genre has patterns that break its identity.

## Output Format

Return JSON with:
- `issues`: list of objects with `severity` ("major" or "minor"), `field` (which part is affected), `suggestion` (specific fix)
- `passed`: true if no major issues found, false otherwise

A "major" issue means the data is musically wrong, internally contradictory, or structurally broken. A "minor" issue is a suggestion for improvement.
