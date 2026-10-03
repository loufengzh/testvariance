"""Command-line entry point; exit 1 only for an explicitly enabled evidence gate."""
from __future__ import annotations

import argparse
import json
import sys
from contextlib import nullcontext

from .core import InputError, analyze, load_jsonl


def render_text(report: dict) -> str:
    lines = [f"Observations: {report['observation_count']}; comparable groups: {report['group_count']}; mixed groups: {report['mixed_group_count']}"]
    for group in report["groups"]:
        # JSON quoting prevents terminal control sequences from source identifiers.
        identity = " / ".join(json.dumps(group[key], ensure_ascii=True) for key in ("test_id", "revision", "environment"))
        frequency = group["failure_frequency"]
        rate = "n/a" if frequency is None else f"{frequency:.2%}"
        lines.append(f"{identity}: failure frequency {rate}; mixed={str(group['mixed_outcomes']).lower()}; recovered runs={group['recovered_runs']}; observed retry seconds={group['observed_retry_seconds']:g}; retry durations missing={group['retry_missing_duration_count']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="testvariance", description="Offline comparable CI outcome evidence. No root-cause or flakiness verdict.")
    parser.add_argument("--version", action="version", version="testvariance 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)
    command = subparsers.add_parser("analyze", help="analyze bounded canonical UTF-8 JSONL")
    command.add_argument("file", help="JSONL path, or - for standard input")
    command.add_argument("--format", choices=("json", "text"), default="json")
    command.add_argument("--fail-on-mixed", action="store_true", help="exit 1 if a comparable group has pass and fail/error evidence")
    args = parser.parse_args(argv)
    try:
        source = nullcontext(sys.stdin.buffer) if args.file == "-" else open(args.file, "rb")
        with source as stream:
            report = analyze(load_jsonl(stream))
        output = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n" if args.format == "json" else render_text(report)
        sys.stdout.write(output)
        return 1 if args.fail_on_mixed and report["mixed_group_count"] else 0
    except (InputError, OSError) as exc:
        # OSError may carry source paths. Never echo source contents or file paths.
        reason = str(exc) if isinstance(exc, InputError) else "cannot read input or write output"
        print(f"testvariance: {reason}", file=sys.stderr)
        return 2
