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


def _unfence(text: str) -> str:
    """Return the body of the first complete markdown fence, else the text as-is."""
    fence = _FENCE.search(text)
    return fence.group(1) if fence else text


def extract_json(text: str) -> str:
    """Best-effort isolation of a JSON value from raw model output.

    Strips reasoning, unwraps a markdown fence anywhere in the text, then slices
    from the first ``{``/``[`` to the last matching ``}``/``]``. Returns the
    cleaned text unchanged when no delimiters exist, so ``json.loads`` raises a
    normal ``JSONDecodeError``.
    """
    cleaned = _unfence(strip_reasoning(text))
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


_CLOSERS = {"{": "}", "[": "]"}
_PARTIAL_STR = r'"(?:[^"\\]|\\.)*(?:"|\\)?'
# What may legitimately follow the last safe cut in truncated JSON: an optional
# comma, an optional (partial) key and colon, and a (partial) string or scalar.
# Rejects junk like ``{not json`` so only genuine truncation is "repaired".
_TRUNCATED_TAIL = re.compile(
    rf"\s*,?\s*(?:{_PARTIAL_STR}\s*:?\s*)?(?:{_PARTIAL_STR}|[-+\w.]*)\s*", re.DOTALL
)


def repair_truncated_json(text: str) -> Any:
    """Parse JSON that was cut off mid-output (e.g. by a ``max_output_tokens`` cap).

    Starts at the first ``{``/``[`` (after reasoning/fence handling) and scans
    once, tracking string state (with backslash escapes) and a stack of open
    brackets. Two completions are tried, in order:

    (a) close an unterminated string with ``"``, then close every open bracket;
    (b) otherwise cut back to the last point where a complete value ended at the
        current depth (just before a ``,``, or just after a bracket opened or
        closed), then close the brackets that were open at that point. This
        handles cuts in a key, after ``:`` or ``,``, or mid-number/literal.

    Raises ``json.JSONDecodeError`` when neither completion parses. Linear time
    apart from a bracket-stack snapshot per structural character (depth is tiny).
    """
    cleaned = _unfence(strip_reasoning(text))
    starts = [i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1]
    if not starts:
        raise json.JSONDecodeError("no JSON object or array found", text, 0)
    body = cleaned[min(starts) :]

    stack: list[str] = []  # closers still owed, innermost last
    in_string = escaped = False
    # Latest safe cut: (end index of kept text, closers owed at that point).
    cut: tuple[int, str] = (0, "")
    end = len(body)
    for i, ch in enumerate(body):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in _CLOSERS:
            stack.append(_CLOSERS[ch])
            cut = (i + 1, "".join(stack))  # keep the empty container
        elif ch in "}]":
            if stack:
                stack.pop()
            cut = (i + 1, "".join(stack))  # a whole nested value just ended
            if not stack:
                end = i + 1  # top-level value complete; ignore any trailing text
                break
        elif ch == ",":
            cut = (i, "".join(stack))  # drop the comma and whatever follows

    head = body[:end]
    candidates = []
    if in_string and end == len(body):
        candidates.append(head + '"' + "".join(reversed(stack)))
    elif not stack:
        candidates.append(head)
    else:
        candidates.append(head + "".join(reversed(stack)))
    if _TRUNCATED_TAIL.fullmatch(body, cut[0]):
        candidates.append(body[: cut[0]] + "".join(reversed(cut[1])))

    first_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            first_error = first_error or e
    raise first_error or json.JSONDecodeError("unrepairable JSON", text, 0)


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
        try:
            parsed = repair_truncated_json(raw_text)
        except json.JSONDecodeError:
            logger.error(
                "%s returned invalid JSON (model=%s): %s", provider, model_name, raw_text[:500]
            )
            msg = f"{provider} returned malformed JSON for model={model_name}: {e}"
            raise ValueError(msg) from e
        logger.warning("%s output was truncated; repaired JSON (model=%s)", provider, model_name)

    parsed = truncate_to_max_length(parsed, response_model)

    try:
        return response_model.model_validate(parsed)
    except ValidationError:
        logger.error(
            "%s response failed validation (model=%s, schema=%s): %s",
            provider, model_name, response_model.__name__, parsed,
        )
        raise
