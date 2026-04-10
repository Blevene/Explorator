"""Backwards-compatible alias — RealizationState is now ExplorationState.

This file exists temporarily so existing imports don't break.
It will be removed once all M2 nodes are updated to import ExplorationState directly.
"""

from explorator.engine.state import ExplorationState

RealizationState = ExplorationState
