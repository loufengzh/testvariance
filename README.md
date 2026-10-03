# testvariance

**Compare like-for-like CI outcomes, with evidence you can inspect.**

[简体中文](README.zh-CN.md) · [Русский](README.ru.md) · [Deutsch](README.de.md)

A small, offline Python library and CLI for canonical JSONL test history. It groups observations by **test, revision, and environment**, reports mixed outcomes and recovered runs, and measures observed retry time without pretending missing measurements are zero. Runtime dependencies: Python 3.10+ standard library only.

## Why it exists

A red build followed by a green build is not enough evidence of test flakiness: the code or execution environment may have changed. testvariance keeps those comparisons separate and shows the exact run/attempt evidence. It does not rerun tests, access CI accounts, diagnose root causes, or recommend automatic quarantine.

[pytest-rerunfailures](https://github.com/pytest-dev/pytest-rerunfailures) adds retries to pytest. [test-summary/action](https://github.com/test-summary/action) presents report summaries in GitHub Actions. This project instead analyzes supplied historical observations offline, with explicit comparability and missing-cost accounting. It is an independent implementation, not an integration with those projects.

## Install and try

No published package release is assumed. From this repository:

```sh
python -m pip install .
testvariance analyze examples/outcomes.jsonl --format text
testvariance analyze examples/outcomes.jsonl --format json
cat examples/outcomes.jsonl | testvariance analyze - --fail-on-mixed
```

The fixture contains seven observations, four comparable groups, and one mixed group. The last command intentionally exits **1**. The mixed group has a failure frequency of 1/3, one recovered run, 2.5 observed retry seconds, and one retry with missing duration. The separate revision's failure is not pooled into it.

For a dependency-free source checkout invocation: `PYTHONPATH=src python -m testvariance analyze examples/outcomes.jsonl` (POSIX shell).

## Input contract

One UTF-8 JSON object per nonblank line:

```json
{"test_id":"suite/test","revision":"a1b2c3","environment":"linux-py312","run_id":"build-101","attempt":1,"outcome":"fail","duration_seconds":12.5}
```

- Required: `test_id`, `revision`, `environment`, `run_id`, `attempt`, `outcome`.
- The four identifiers are exact, nonblank strings, at most 4,096 characters. No case folding, trimming, or normalization is applied. Use a full commit identifier and include all relevant platform, dependency, and configuration dimensions in your environment identifier.
- `attempt` is a positive integer, never a boolean. It is scoped to this test, revision, environment, and run. It must represent the original attempt ordinal, not the line number.
- `outcome` is exactly `pass`, `fail`, `error`, or `skip`.
- Optional `duration_seconds`: a finite nonnegative JSON number or `null`. Omitted/null means unknown; zero is a known zero.
- Unknown fields, duplicate JSON members, invalid UTF-8, nonstandard NaN/Infinity, and duplicate observation keys are rejected. The observation key is `(test_id, revision, environment, run_id, attempt)`. Identical duplicate rows are also rejected; importing overlapping histories requires deduplication upstream.
- Limits: 32 MiB total, 64 KiB per physical line including newline, 100,000 observations. Blank lines count toward byte limits. Empty input is valid. A UTF-8 BOM is not accepted. All durations must also have a finite aggregate.

No XML or JUnit parser is included. Convert reports upstream into this contract while retaining accurate attempt and comparability metadata. Do not infer a revision or environment from a filename.

## Reading the report

CLI output uses LF line endings on every platform, including Windows, for reports, diagnostics, and help/version messages. JSON is the default output. `schema_version: 1` identifies the report format. Groups sort lexicographically by the three identifiers; runs sort by `run_id`; attempt numbers sort only **within** each run. Input line order is irrelevant. Run identifiers are not interpreted as chronological timestamps.

- `counts` counts observations by outcome. `executed_attempts` excludes skips.
- `failure_frequency = (fail + error) / (pass + fail + error)`. This is an **attempt-weighted observed frequency**, not a per-build failure probability. All-skip groups produce `null`.
- `failure_frequency_wilson_95` is a nominal 95% Wilson score interval for that frequency, or `null` with no executed observations. Retries are often correlated, selective, and non-independent, so the interval is descriptive and may not have 95% real-world coverage. It is not a guarantee or flakiness confidence score.
- `mixed_outcomes` means the same comparable group contains at least one pass and one fail/error, possibly across distinct runs. This is evidence of variation, not proof of nondeterminism or a root cause.
- `recovered_runs` counts runs whose **final observed attempt** is a pass and which have an earlier observed fail/error. Pass-then-fail and fail-pass-skip do not count. “Final” means highest supplied attempt number, not knowledge that CI has finished.
- `observed_retry_seconds` sums known durations for supplied attempts numbered greater than 1, including skips with recorded duration. `retry_missing_duration_count` counts supplied retries without a duration. Missing attempts have no imputed cost and are separately exposed by each run's `missing_attempt_count` (missing positive ordinals up to its maximum attempt). The sum is observed execution time, not wall-clock latency or money.
- `observed_duration_seconds` and `missing_duration_count` apply to all supplied attempts. A zero observed sum with missing durations does **not** establish zero cost.

Reports include your identifiers and should be treated with their confidentiality. The tool never collects stdout, failure messages, stack traces, or environment variables; it has no network calls. Text output escapes control characters in identifiers. Validation errors do not echo source contents. These safeguards do not anonymize report identifiers.

## Exit codes and CI gate

- **0:** valid report, including failures/mixed groups unless a gate was requested.
- **1:** `--fail-on-mixed` was explicitly supplied and at least one comparable group is mixed. The complete report is still written.
- **2:** invalid input, CLI usage, or I/O failure. Invalid input produces no partial report.

```sh
testvariance analyze history.jsonl --fail-on-mixed > evidence.json
```

Choose this gate only if mixed evidence is appropriate for your workflow; it is not an automatic flaky-test verdict.

## Library

```python
from testvariance import analyze, load_jsonl

with open("examples/outcomes.jsonl", "rb") as source:
    report = analyze(load_jsonl(source))
print(report["mixed_group_count"])
```

`Observation` validates direct construction; `analyze` rejects duplicate observations even when bypassing the JSONL loader. `InputError` is a `ValueError` subclass. Data is held in memory within the documented bounds. The library does not write files or mutate its observations.

## Development

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python -m pip wheel --no-deps --no-build-isolation . -w dist
```

The first command needs only Python; the second requires installed setuptools and wheel build tooling. CI tests Python 3.10–3.13 on Linux and Python 3.12 on Windows, builds a wheel, installs it, and exercises the installed command. See [contributing](CONTRIBUTING.md), [security](SECURITY.md), and [format details](docs/FORMAT.md).

## Roadmap and non-goals

- Carefully bounded JUnit/Jest adapters with explicit metadata and no captured sensitive output
- Versioned history merging with explicit duplicate conflict policy
- Evidence/cost ranking with transparent missing-data treatment

Adapters, history storage, automatic quarantine, rerunning tests, and causal diagnoses are **not implemented** in 0.1.0. MIT licensed.
