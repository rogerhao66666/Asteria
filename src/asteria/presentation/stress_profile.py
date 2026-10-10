"""Headless stress/profiling helpers for the canonical presentation pipeline."""

from dataclasses import dataclass
from time import perf_counter


@dataclass(frozen=True, slots=True)
class StressSample:
    frames: int
    packets: int
    elapsed_ms: float
    max_packets_per_frame: int

    @property
    def ms_per_frame(self):
        return self.elapsed_ms / self.frames if self.frames else 0.0

    @property
    def packets_per_second(self):
        return self.packets / (self.elapsed_ms / 1000) if self.elapsed_ms else float("inf")


def profile_pipeline(pipeline, times_ms):
    times = tuple(times_ms)
    packets = peak = 0
    start = perf_counter()
    for t in times:
        frame = pipeline.sample(float(t))
        n = len(frame.draw_packets)
        packets += n
        peak = max(peak, n)
    return StressSample(len(times), packets, (perf_counter() - start) * 1000, peak)
