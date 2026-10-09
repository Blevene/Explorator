"""Provider-neutral helpers that turn raw LLM text into validated Pydantic models.

Shared by every LLM adapter so parsing behaviour (reasoning-block stripping,
markdown-fence unwrapping, maxLength truncation, validation logging) is
identical across providers.
"""

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_CLOSE = "</think>"
_FENCE = re.compile(r"```(?:json)?[ \t]*\n?(.*?)```", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """Remove ``<think>…</think>`` reasoning emitted by reasoning models.

    Also handles chat templates that pre-fill ``<think>`` in the prompt, where
    the completion contains reasoning followed by a bare closing tag: everything
    up to the last ``</think>`` is dropped.
    """
    stripped = _THINK_BLOCK.sub("", text)
    close = stripped.lower().rfind(_THINK_CLOSE)
    if close != -1:
        stripped = stripped[close + len(_THINK_CLOSE) :]
    return stripped


def extract_json(text: str) -> str:
    """Best-effort isolation of a JSON value from raw model output.

    Strips reasoning, unwraps a markdown fence anywhere in the text, then slices
    from the first ``{``/``[`` to the last matching ``}``/``]``. Returns the
    cleaned text unchanged when no delimiters exist, so ``json.loads`` raises a
    normal ``JSONDecodeError``.
    """
    cleaned = strip_reasoning(text)
    fence = _FENCE.search(cleaned)
    if fence:
        cleaned = fence.group(1)
    starts = [i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1]
    if not starts:
        return cleaned.strip()
    start = min(starts)
    end = cleaned.rfind("}" if cleaned[start] == "{" else "]")
    if end < start:
        return cleaned.strip()
    return cleaned[start : end + 1]


def loads_lenient(text: str) -> Any:
    """``json.loads`` the text as-is; only on failure fall back to ``extract_json``.

    Trying raw JSON first keeps valid payloads intact when their string values
    happen to contain fences or ``</think>``.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(extract_json(text))


def truncate_to_max_length(
    data: dict[str, Any] | list[Any],
    model: type[BaseModel],
) -> dict[str, Any] | list[Any]:
    """Truncate string fields to their maxLength constraint before validation.

    Prevents verbose model output from causing validation rejection. Handles
    top-level string fields and lists of ``$ref`` sub-models (one level deep),
    which is all current response models need.
    """
    if not isinstance(data, dict):
        return data

    schema = model.model_json_schema()
    props = schema.get("properties", {})
    defs = schema.get("$defs", {})

    for field_name, field_schema in props.items():
        value = data.get(field_name)
        if isinstance(value, str):
            max_len = field_schema.get("maxLength")
            if max_len and len(value) > max_len:
                data[field_name] = value[:max_len]

        if isinstance(value, list):
            items_ref = field_schema.get("items", {}).get("$ref", "")
            if not items_ref:
                continue
            sub_props = defs.get(items_ref.split("/")[-1], {}).get("properties", {})
            for item in value:
                if not isinstance(item, dict):
                    continue
                for sf_name, sf_schema in sub_props.items():
                    sub_value = item.get(sf_name)
                    sub_max = sf_schema.get("maxLength")
                    if isinstance(sub_value, str) and sub_max and len(sub_value) > sub_max:
                        item[sf_name] = sub_value[:sub_max]

    return data


def parse_structured[T: BaseModel](
    raw_text: str | None,
    response_model: type[T],
    *,
    provider: str,
    model_name: str,
) -> T:
    """Parse raw model text into ``response_model``.

    Raises ``ValueError`` for empty or malformed output and
    ``pydantic.ValidationError`` (a ``ValueError`` subclass) for schema mismatch.
    """
    if not raw_text:
        msg = f"{provider} returned empty response for model={model_name}"
        raise ValueError(msg)

    try:
        parsed = loads_lenient(raw_text)
    except json.JSONDecodeError as e:
        logger.error(
            "%s returned invalid JSON (model=%s): %s", provider, model_name, raw_text[:500]
        )
        msg = f"{provider} returned malformed JSON for model={model_name}: {e}"
        raise ValueError(msg) from e

    parsed = truncate_to_max_length(parsed, response_model)

    try:
        return response_model.model_validate(parsed)
    except ValidationError:
        logger.error(
            "%s response failed validation (model=%s, schema=%s): %s",
            provider, model_name, response_model.__name__, parsed,
        )
        raise
