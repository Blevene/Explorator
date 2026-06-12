"""Context-scoped Gemini token-usage accumulator.

Every Gemini call funnels through ``adapters/gemini.py``; that adapter records
usage here. A round handler opens a scope with ``track_usage()`` around
``graph.ainvoke``; the graph node wrapper tags the active phase via
``set_phase()``. contextvars copy by reference into asyncio child tasks, so a
parallel ``asyncio.gather`` fan-out aggregates into the one accumulator.

``record*`` is a no-op when no scope is active, so calls outside a round (or in
unit tests without a scope) are safe.
"""

from __future__ import annotations

import contextlib
import contextvars
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

from explorator.config import settings


def _tier_of(model_name: str) -> str:
    """Collapse a concrete/aliased model name to a stable tier label."""
    return "flash" if "flash" in model_name.lower() else "pro"


@dataclass
class _ModelUsage:
    input: int = 0
    output: int = 0
    cached: int = 0
    calls: int = 0


@dataclass
class _PhaseUsage:
    input: int = 0
    output: int = 0
    cached: int = 0
    calls: int = 0
    model: str = ""


@dataclass
class UsageAccumulator:
    """Aggregated token usage for a single scoped run (one generate action)."""

    by_model: dict[str, _ModelUsage] = field(default_factory=dict)
    by_phase: dict[str, _PhaseUsage] = field(default_factory=dict)
    _last_emitted_total: int = field(default=0, init=False)
    synthetic: bool = field(default=False, init=False)

    def add(self, model_name: str, input_: int, output: int, cached: int, phase: str) -> None:
        tier = _tier_of(model_name)
        m = self.by_model.setdefault(tier, _ModelUsage())
        m.input += input_
        m.output += output
        m.cached += cached
        m.calls += 1
        p = self.by_phase.setdefault(phase, _PhaseUsage())
        p.input += input_
        p.output += output
        p.cached += cached
        p.calls += 1
        p.model = tier

    def totals(self) -> dict[str, int]:
        input_ = sum(m.input for m in self.by_model.values())
        output = sum(m.output for m in self.by_model.values())
        cached = sum(m.cached for m in self.by_model.values())
        total = input_ + output
        return {"input": input_, "output": output, "cached": cached, "total": total}

    def estimated_cost_usd(self) -> float:
        rates = _pricing()
        cost = 0.0
        for tier, m in self.by_model.items():
            r = rates[tier]
            # cached_content_token_count ⊆ prompt_token_count; counted within input.
            cost += m.input / 1_000_000 * r["input"]
            cost += m.output / 1_000_000 * r["output"]
        return cost

    def changed_since_last_emit(self) -> bool:
        total = self.totals()["total"]
        if total > self._last_emitted_total:
            self._last_emitted_total = total
            return True
        return False

    def to_event(self, round_number: int) -> dict[str, Any]:
        totals = self.totals()
        return {
            "round": round_number,
            "total_input": totals["input"],
            "total_output": totals["output"],
            "total_cached": totals["cached"],
            "total_tokens": totals["total"],
            "by_model": {
                tier: {"input": m.input, "output": m.output, "cached": m.cached, "calls": m.calls}
                for tier, m in self.by_model.items()
            },
            "by_phase": {
                name: {"input": p.input, "output": p.output, "calls": p.calls, "model": p.model}
                for name, p in self.by_phase.items()
            },
            "estimated_cost_usd": round(self.estimated_cost_usd(), 6),
            "is_estimate": True,
            "is_synthetic": self.synthetic,
        }


_current: contextvars.ContextVar[UsageAccumulator | None] = contextvars.ContextVar(
    "explorator_token_usage", default=None
)
_current_phase: contextvars.ContextVar[str] = contextvars.ContextVar(
    "explorator_token_phase", default="unknown"
)


def _pricing() -> dict[str, dict[str, float]]:
    """USD per 1M tokens, per tier. Cached priced at the input rate."""
    return {
        "pro": {
            "input": settings.gemini_price_pro_input,
            "output": settings.gemini_price_pro_output,
        },
        "flash": {
            "input": settings.gemini_price_flash_input,
            "output": settings.gemini_price_flash_output,
        },
    }


def current_usage() -> UsageAccumulator | None:
    """Return the active accumulator, or None when outside a scope."""
    return _current.get()


@contextlib.contextmanager
def track_usage() -> Iterator[UsageAccumulator]:
    """Open an accumulator scope. Yields the fresh UsageAccumulator."""
    accumulator = UsageAccumulator()
    token = _current.set(accumulator)
    try:
        yield accumulator
    finally:
        _current.reset(token)


@contextlib.contextmanager
def set_phase(name: str) -> Iterator[None]:
    """Tag the active phase for attribution while the body runs."""
    token = _current_phase.set(name)
    try:
        yield
    finally:
        _current_phase.reset(token)


def record_tokens(
    model_name: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0
) -> None:
    """Add raw token counts to the active accumulator. No-op outside a scope."""
    accumulator = _current.get()
    if accumulator is None:
        return
    accumulator.add(model_name, input_tokens, output_tokens, cached_tokens, _current_phase.get())


def record_synthetic_tokens(
    model_name: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0
) -> None:
    """Record token counts that come from a mock client, flagging the scope synthetic."""
    accumulator = _current.get()
    if accumulator is None:
        return
    accumulator.synthetic = True
    accumulator.add(model_name, input_tokens, output_tokens, cached_tokens, _current_phase.get())


def record(model_name: str, usage_metadata: Any) -> None:
    """Extract counts from a google-genai ``usage_metadata`` object (None-safe)."""
    if usage_metadata is None:
        return
    record_tokens(
        model_name,
        getattr(usage_metadata, "prompt_token_count", 0) or 0,
        getattr(usage_metadata, "candidates_token_count", 0) or 0,
        getattr(usage_metadata, "cached_content_token_count", 0) or 0,
    )
