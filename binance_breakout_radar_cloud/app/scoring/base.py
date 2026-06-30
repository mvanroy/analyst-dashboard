from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EngineResult:
    name: str
    score: float
    metrics: dict[str, Any] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def display(self) -> str:
        return f"{self.score:.2f} / 100"


def average(scores: list[float | None]) -> float:
    values = [score for score in scores if score is not None]
    return sum(values) / len(values) if values else 0.0


def low_percentile_score(value: float | None, strong: float, moderate: float, weak: float, fakeout: float) -> tuple[float | None, str]:
    if value is None:
        return None, "missing"
    if value <= strong:
        return 100, "strong"
    if value <= moderate:
        return 75, "moderate"
    if value <= weak:
        return 50, "weak"
    if value > fakeout:
        return 0, "fakeout/already expanded"
    return 25, "elevated"


def high_percentile_score(value: float | None) -> tuple[float | None, str]:
    if value is None:
        return None, "missing"
    if value >= 80:
        return 100, "strong"
    if value >= 60:
        return 75, "moderate"
    if value >= 40:
        return 50, "weak"
    return 0, "negative"


def metric(raw: Any, score: float | None, bucket: str) -> dict[str, Any]:
    return {"raw": raw, "score": score, "bucket": bucket}
