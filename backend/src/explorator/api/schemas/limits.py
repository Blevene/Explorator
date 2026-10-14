"""Request-size limits shared by route models.

Every candidate id and free-text field can fan out into paid LLM calls, so
requests are bounded to what the UI sends (one id; a round yields at most 12
candidates) with headroom for scripted use.
"""

from typing import Annotated, Any

from pydantic import BeforeValidator, Field

MAX_IDS_PER_REQUEST = 12
MAX_PROMPT_CHARS = 2000


def _dedupe(value: Any) -> Any:
    """Drop repeated ids (keeping order) before the length check runs."""
    if isinstance(value, list):
        return list(dict.fromkeys(value))
    return value


CandidateIds = Annotated[
    list[str], BeforeValidator(_dedupe), Field(max_length=MAX_IDS_PER_REQUEST)
]
PromptText = Annotated[str, Field(max_length=MAX_PROMPT_CHARS)]
