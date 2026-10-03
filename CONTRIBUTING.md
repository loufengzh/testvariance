# Contributing

Start with a reproducible issue and synthetic JSONL. Do not attach production
logs or identifiers. For code changes, add a regression test and run:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python -m pip wheel --no-deps --no-build-isolation . -w dist
```

Keep runtime dependencies in the standard library and preserve deterministic
reports. A schema change must state compatibility consequences. Update all four
README translations when the user-facing contract changes. Do not weaken input
bounds or pool revisions/environments to produce a more exciting result.

New adapters need explicit comparability metadata, resource limits, synthetic
fixtures, ambiguity checks, and a rule excluding captured test output. A report
must distinguish absent measurements from known zero. PRs should explain what
was tested and any unverified platforms; a locally passing test is not a claim
that remote CI passed.
