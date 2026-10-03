"""Validated, deterministic evidence aggregation. No network or CI provider access."""
from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import BinaryIO, Iterable

MAX_BYTES = 32 * 1024 * 1024
MAX_LINE_BYTES = 64 * 1024
MAX_RECORDS = 100_000
MAX_IDENTIFIER_LENGTH = 4096
OUTCOMES = ("pass", "fail", "error", "skip")
REQUIRED = {"test_id", "revision", "environment", "run_id", "attempt", "outcome"}


class InputError(ValueError):
    """Invalid or oversized input; diagnostics never echo source data."""


@dataclass(frozen=True)
class Observation:
    test_id: str
    revision: str
    environment: str
    run_id: str
    attempt: int
    outcome: str
    duration_seconds: float | None = None

    def __post_init__(self) -> None:
        for field in ("test_id", "revision", "environment", "run_id"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip() or len(value) > MAX_IDENTIFIER_LENGTH:
                raise InputError(f"{field} must be a nonblank string of at most {MAX_IDENTIFIER_LENGTH} characters")
            if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
                raise InputError(f"{field} contains an invalid Unicode surrogate")
        if type(self.attempt) is not int or self.attempt < 1:
            raise InputError("attempt must be a positive integer")
        if not isinstance(self.outcome, str) or self.outcome not in OUTCOMES:
            raise InputError("outcome must be pass, fail, error, or skip")
        duration = self.duration_seconds
        if duration is not None:
            if type(duration) not in (int, float):
                raise InputError("duration_seconds must be finite and nonnegative, or null")
            try:
                valid = math.isfinite(duration) and duration >= 0
            except OverflowError:
                valid = False
            if not valid:
                raise InputError("duration_seconds must be finite and nonnegative, or null")

    @property
    def group_key(self) -> tuple[str, str, str]:
        return self.test_id, self.revision, self.environment

    @property
    def key(self) -> tuple[str, str, str, str, int]:
        return (*self.group_key, self.run_id, self.attempt)


def _object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate JSON object member")
        result[key] = value
    return result


def _constant(_: str) -> None:
    raise InputError("nonstandard JSON numeric constant")


def load_jsonl(stream: BinaryIO) -> list[Observation]:
    """Read bounded UTF-8 JSONL. Blank lines are ignored; duplicate keys rejected."""
    observations = []
    seen = set()
    total = 0
    line_number = 0
    while True:
        raw = stream.readline(MAX_LINE_BYTES + 1)
        if not raw:
            break
        line_number += 1
        total += len(raw)
        if total > MAX_BYTES:
            raise InputError("input exceeds 32 MiB")
        if len(raw) > MAX_LINE_BYTES:
            raise InputError(f"line {line_number}: exceeds 64 KiB")
        try:
            line = raw.decode("utf-8")
            if not line.strip():
                continue
            if len(observations) >= MAX_RECORDS:
                raise InputError("input exceeds 100000 observations")
            row = json.loads(line, object_pairs_hook=_object, parse_constant=_constant)
            if not isinstance(row, dict):
                raise InputError("record must be an object")
            if not REQUIRED.issubset(row) or set(row) - REQUIRED - {"duration_seconds"}:
                raise InputError("record has missing or unknown fields")
            observation = Observation(**row)
            if observation.key in seen:
                raise InputError("duplicate observation key")
            seen.add(observation.key)
            observations.append(observation)
        except InputError as exc:
            raise InputError(f"line {line_number}: {exc}") from exc
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise InputError(f"line {line_number}: invalid UTF-8 or JSON") from exc
    return observations


def wilson_interval(failures: int, executed: int) -> list[float] | None:
    """Nominal 95% Wilson score interval; retries need not be independent."""
    if type(failures) is not int or type(executed) is not int or not 0 <= failures <= executed:
        raise ValueError("require integer 0 <= failures <= executed")
    if not executed:
        return None
    z = 1.959963984540054
    p = failures / executed
    denominator = 1 + z * z / executed
    center = (p + z * z / (2 * executed)) / denominator
    radius = z * math.sqrt(p * (1 - p) / executed + z * z / (4 * executed**2)) / denominator
    return [max(0.0, center - radius), min(1.0, center + radius)]


def _seconds(rows: list[Observation]) -> float:
    try:
        result = math.fsum(row.duration_seconds for row in rows if row.duration_seconds is not None)
    except OverflowError as exc:
        raise InputError("aggregate duration exceeds finite numeric range") from exc
    if not math.isfinite(result):
        raise InputError("aggregate duration exceeds finite numeric range")
    return result


def analyze(observations: Iterable[Observation]) -> dict:
    """Aggregate exact comparable groups, sorting attempts only inside each run."""
    grouped = defaultdict(list)
    seen = set()
    for observation in observations:
        if not isinstance(observation, Observation):
            raise InputError("analyze requires Observation instances")
        if observation.key in seen:
            raise InputError("duplicate observation key")
        if len(seen) >= MAX_RECORDS:
            raise InputError("input exceeds 100000 observations")
        seen.add(observation.key)
        grouped[observation.group_key].append(observation)
    groups = []
    for key, rows in sorted(grouped.items()):
        counts = {outcome: sum(row.outcome == outcome for row in rows) for outcome in OUTCOMES}
        executed = len(rows) - counts["skip"]
        failures = counts["fail"] + counts["error"]
        by_run = defaultdict(list)
        for row in rows:
            by_run[row.run_id].append(row)
        runs = []
        for run_id, attempts in sorted(by_run.items()):
            attempts.sort(key=lambda row: row.attempt)
            final = attempts[-1]
            retry = [row for row in attempts if row.attempt > 1]
            runs.append({
                "run_id": run_id,
                "observed_attempts": [row.attempt for row in attempts],
                "missing_attempt_count": final.attempt - len(attempts),
                "final_attempt": final.attempt,
                "final_outcome": final.outcome,
                "recovered": final.outcome == "pass" and any(row.outcome in ("fail", "error") for row in attempts[:-1]),
                "observed_retry_seconds": _seconds(retry),
                "retry_missing_duration_count": sum(row.duration_seconds is None for row in retry),
            })
        retry_rows = [row for row in rows if row.attempt > 1]
        groups.append({
            "test_id": key[0], "revision": key[1], "environment": key[2],
            "counts": counts, "executed_attempts": executed,
            "failure_frequency": failures / executed if executed else None,
            "failure_frequency_wilson_95": wilson_interval(failures, executed),
            "mixed_outcomes": counts["pass"] > 0 and failures > 0,
            "recovered_runs": sum(run["recovered"] for run in runs),
            "observed_duration_seconds": _seconds(rows),
            "missing_duration_count": sum(row.duration_seconds is None for row in rows),
            "observed_retry_seconds": _seconds(retry_rows),
            "retry_missing_duration_count": sum(row.duration_seconds is None for row in retry_rows),
            "runs": runs,
        })
    return {
        "schema_version": 1,
        "observation_count": len(seen), "group_count": len(groups),
        "mixed_group_count": sum(group["mixed_outcomes"] for group in groups),
        "groups": groups,
    }
