"""B9: paired fixed-rule verification runtime experiment (not discovery accuracy).

No network, no source mutations, no API calls. This does not claim any
published-method reproduction, semantic precision, or detection quality.
"""
from __future__ import annotations

from collections import Counter
import math
import random
import statistics
import time
from typing import Callable, Mapping, Sequence

STATUSES = ('satisfied', 'violated', 'abstained', 'not_applicable')


class BenchmarkError(ValueError):
    pass


def percentile_linear(values: Sequence[float], q: float) -> float:
    """Inclusive linear interpolation; explicit because p95 choices vary."""
    if not values or not 0.0 <= q <= 1.0:
        raise BenchmarkError('Nonempty timings and 0 <= quantile <= 1 required')
    vals = sorted(float(x) for x in values)
    if any(not math.isfinite(v) or v < 0 for v in vals):
        raise BenchmarkError('Timing must be non-negative finite')
    z = (len(vals) - 1) * q
    lo = int(z)
    hi = min(len(vals) - 1, lo + 1)
    return vals[lo] * (1 - (z - lo)) + vals[hi] * (z - lo)


def count_statuses(rows: Sequence[Mapping[str, str]], fn: Callable[[Mapping[str, str]], str]) -> dict[str, int]:
    counts = Counter({x: 0 for x in STATUSES})
    for row in rows:
        status = fn(row)
        if status not in STATUSES:
            raise BenchmarkError(f'Invalid checker status: {status!r}')
        counts[status] += 1
    return dict(counts)


def ensure_row_parity(rows: Sequence[Mapping[str, str]],
                      first: Callable[[Mapping[str, str]], str],
                      second: Callable[[Mapping[str, str]], str],
                      expected: Mapping[str, int]) -> dict[str, int]:
    """Fail if one row differs; summary count equality is insufficient."""
    counts = Counter({x: 0 for x in STATUSES})
    for idx, row in enumerate(rows):
        a, b = first(row), second(row)
        if a != b or a not in STATUSES:
            raise BenchmarkError(f'Engine mismatch on source row index {idx}: {a!r} / {b!r}')
        counts[a] += 1
    expected = {k: int(expected.get(k, 0)) for k in STATUSES}
    if dict(counts) != expected:
        raise BenchmarkError(f'Counts drifted from B6.1: {dict(counts)} != {expected}')
    return dict(counts)


def repeated_paired_timing(rows: Sequence[Mapping[str, str]],
                           methods: Mapping[str, Callable[[Mapping[str, str]], str]],
                           *, repetitions: int, seed: int,
                           clock: Callable[[], float] = time.perf_counter) -> dict:
    if len(methods) != 2 or any(not k or not callable(f) for k, f in methods.items()):
        raise BenchmarkError('Two named executable checkers required')
    if type(repetitions) is not int or not 5 <= repetitions <= 31 or type(seed) is not int:
        raise BenchmarkError('Require 5-31 frozen repetitions and integer seed')
    if len(rows) == 0:
        raise BenchmarkError('Empty input is not a runtime benchmark')
    initial_reverse = bool(random.Random(seed).getrandbits(1))
    duration = {name: [] for name in methods}
    execution_order = []
    keys = list(methods)
    reference = None
    for i in range(repetitions):
        order = keys.copy()
        if bool(i % 2) != initial_reverse:
            order.reverse()
        # Alternate which method runs first to limit temperature/cache/order bias.
        execution_order.append(order)
        for name in order:
            start = clock()
            counts = count_statuses(rows, methods[name])
            elapsed = clock() - start
            if not math.isfinite(elapsed) or elapsed < 0:
                raise BenchmarkError('Invalid monotonic clock outcome')
            if reference is None:
                reference = counts
            elif counts != reference:
                raise BenchmarkError(f'Checker output changed during timing for {name}')
            duration[name].append(elapsed)
    return {
        'repetitions': repetitions, 'seed': seed, 'processed_records_per_repetition': len(rows),
        'clock': 'time.perf_counter',
        'order_per_repetition': execution_order,
        'status_counts_every_run': reference,
        'methods': {name: {
            'elapsed_seconds_each_run': [round(v, 6) for v in vals],
            'median_seconds': round(statistics.median(vals), 6),
            'p95_linear_seconds': round(percentile_linear(vals, 0.95), 6),
            'records_per_second_at_median': round(len(rows) / statistics.median(vals), 1)
                if statistics.median(vals) > 0 else None,
        } for name, vals in duration.items()},
        'limits': ['Same-rule execution comparison, not a constraint-discovery baseline',
                   'Both datasets are already inspected development sources',
                   'Rows are loaded before timing; timings exclude filesystem I/O and source hashing',
                   'Warm-process timings; Python runtime/CPU platform must be reported',
                   'No adjudicated defect ground truth, no clean false-positive rate'],
    }
