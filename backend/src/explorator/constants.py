"""Shared constants for the explorator backend."""

# M5d: canonical list of pattern types. Any change here must be mirrored in
# frontend/src/constants/patternTypes.ts.
PATTERN_TYPES: tuple[str, ...] = ("progression", "voicing", "bass", "groove", "melody")
