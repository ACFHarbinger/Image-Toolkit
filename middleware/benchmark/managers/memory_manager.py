"""
Memory tracking for benchmark operations.
"""

import gc
import os
import time
from functools import wraps
from typing import Callable

import psutil  # pyrefly: ignore [untyped-import]


class MemoryManager:
    """Tracks memory usage for a code block."""

    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.baseline = 0
        self.peak = 0
        self.samples = []

    def start(self):
        """Start tracking memory."""
        gc.collect()
        time.sleep(0.1)  # Let GC finish
        # In Megabytes
        self.baseline = self.process.memory_info().rss / 1024 / 1024  # pyrefly: ignore [bad-assignment]
        self.peak = self.baseline
        self.samples = [self.baseline]

    def sample(self):
        """Take a memory sample."""
        current = self.process.memory_info().rss / 1024 / 1024
        self.samples.append(current)
        if current > self.peak:
            self.peak = current # pyrefly: ignore [bad-assignment]

    def stop(self):
        """Stop tracking and return stats."""
        gc.collect()
        time.sleep(0.1)
        final = self.process.memory_info().rss / 1024 / 1024

        return {
            "baseline_mb": round(self.baseline, 2),
            "peak_mb": round(self.peak, 2),
            "final_mb": round(final, 2),
            "delta_mb": round(self.peak - self.baseline, 2),
            "leaked_mb": round(final - self.baseline, 2),
        }


def measure_memory(func: Callable) -> Callable:
    """Decorator to measure memory usage of a function."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        tracker = MemoryManager()
        tracker.start()

        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start_time

        mem_stats = tracker.stop()

        return {"result": result, "time_sec": round(elapsed, 4), "memory": mem_stats}

    return wrapper
