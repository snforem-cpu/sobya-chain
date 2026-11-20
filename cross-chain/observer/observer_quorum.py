"""Strict-majority quorum wrapper for independently configured read-only observers.

Each source must represent an independently operated RPC/observer path. The
wrapper compares normalized verified evidence; it does not make one provider
trustless or prove provider independence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
import json
from typing import Any, Callable, Iterable


class QuorumVerificationError(ValueError):
    """Raised when independent observers cannot agree on verified evidence."""


@dataclass(frozen=True)
class ObserverSource:
    source_id: str
    verify: Callable[..., Any]


@dataclass(frozen=True)
class QuorumResult:
    value: Any
    agreeing_sources: tuple[str, ...]
    attempted_sources: tuple[str, ...]
    rejected_sources: tuple[str, ...]
    required_quorum: int


def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        return _normalize(asdict(value))
    if isinstance(value, Enum):
        return _normalize(value.value)
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    if isinstance(value, dict):
        return {str(key): _normalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported observer evidence type: {type(value).__name__}")


def _fingerprint(value: Any) -> str:
    return json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"))


class IndependentObserverQuorum:
    """Run a verifier through multiple sources and require strict-majority agreement."""

    def __init__(self, sources: Iterable[ObserverSource], required_quorum: int):
        self.sources = tuple(sources)
        ids = [source.source_id for source in self.sources]
        if not self.sources or any(not source_id.strip() for source_id in ids):
            raise ValueError("at least one named observer source is required")
        if len(set(ids)) != len(ids):
            raise ValueError("observer source IDs must be unique")
        if required_quorum <= len(self.sources) // 2 or required_quorum > len(self.sources):
            raise ValueError("required quorum must be a strict majority of configured sources")
        self.required_quorum = required_quorum

    def verify(self, *args: Any, **kwargs: Any) -> QuorumResult:
        groups: dict[str, list[tuple[str, Any]]] = {}
        attempted: list[str] = []
        rejected: list[str] = []
        for source in self.sources:
            attempted.append(source.source_id)
            try:
                evidence = source.verify(*args, **kwargs)
                fingerprint = _fingerprint(evidence)
            except Exception:
                # Fail closed without leaking RPC URLs, headers, or provider errors.
                rejected.append(source.source_id)
                continue
            groups.setdefault(fingerprint, []).append((source.source_id, evidence))

        winners = [
            members for members in groups.values()
            if len(members) >= self.required_quorum
        ]
        if len(winners) != 1:
            raise QuorumVerificationError(
                f"observer quorum not reached: required {self.required_quorum} "
                f"matching results from {len(self.sources)} configured sources"
            )
        winner = winners[0]
        agreeing = tuple(source_id for source_id, _ in winner)
        winner_ids = set(agreeing)
        rejected.extend(
            source.source_id for source in self.sources
            if source.source_id not in winner_ids and source.source_id not in rejected
        )
        return QuorumResult(
            value=winner[0][1],
            agreeing_sources=agreeing,
            attempted_sources=tuple(attempted),
            rejected_sources=tuple(rejected),
            required_quorum=self.required_quorum,
        )
