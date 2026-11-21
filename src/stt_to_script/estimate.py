# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Run-time estimate.

The only measured quantity is how many seconds one request takes per 1,000
input characters, averaged over the most recent requests of this process.
Until a few requests have been measured, the configured start value is used
and the estimate is marked as uncalibrated. Waiting time in the queue is not
part of the estimate; Gradio shows the queue position itself.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

LOW_FACTOR = 0.75
HIGH_FACTOR = 1.5


class RateTracker:
    def __init__(self, initial_seconds_per_1000: float, window: int = 20, min_samples: int = 3):
        self.initial = initial_seconds_per_1000
        self.min_samples = min_samples
        self._samples: deque[float] = deque(maxlen=window)

    def record(self, chars: int, seconds: float) -> None:
        if chars >= 200 and seconds > 0:  # tiny requests are dominated by overhead
            self._samples.append(seconds / (chars / 1000))

    @property
    def calibrated(self) -> bool:
        return len(self._samples) >= self.min_samples

    @property
    def seconds_per_1000(self) -> float:
        if not self.calibrated:
            return self.initial
        return sum(self._samples) / len(self._samples)


@dataclass(frozen=True)
class Estimate:
    low: float
    high: float
    calibrated: bool

    @property
    def expected(self) -> float:
        return (self.low + self.high) / (LOW_FACTOR + HIGH_FACTOR)


def makespan(sizes: list[int], lanes: int, seconds_per_1000: float) -> float:
    """Wall time for ``sizes`` processed on ``lanes`` parallel workers (greedy)."""
    if not sizes:
        return 0.0
    loads = [0.0] * max(1, lanes)
    for size in sorted(sizes, reverse=True):
        index = loads.index(min(loads))
        loads[index] += size / 1000 * seconds_per_1000
    return max(loads)


def estimate(pass_sizes: list[tuple[list[int], int]], tracker: RateTracker) -> Estimate:
    """``pass_sizes``: per remaining pass, the segment sizes and the lane count."""
    rate = tracker.seconds_per_1000
    seconds = sum(makespan(sizes, lanes, rate) for sizes, lanes in pass_sizes)
    return Estimate(seconds * LOW_FACTOR, seconds * HIGH_FACTOR, tracker.calibrated)
