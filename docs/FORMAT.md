# Format and interpretation notes

The README defines input fields and limits. JSONL input currently has no version
field; unknown fields are errors. Output has `schema_version: 1`; consumers should
check it and access fields by name, not depend on object-member order or float
text formatting.

## Observation identity

Use the tuple `(test_id, revision, environment, run_id, attempt)`. No delimiter-based
concatenation is used internally, so embedded slashes or colons do not collide.
A single run identifier may legitimately appear in multiple test/revision/environment
groups. The caller owns that metadata's accuracy. Identical labels do not guarantee
identical real-world conditions. Selective reporting or stale environment labels
can bias every resulting measure.

## Sparse attempts

Supplied attempts 2 and 5 are accepted and sorted to `[2, 5]`. Their missing attempt
count is 3 (1, 3, 4), without materializing that range. Both supplied durations
count toward observed retry seconds. No duration is imputed for the three absent
attempts. Missing-duration counts cover supplied observations only.

An earlier fail followed by a final observed pass is a recovered run even if an
intermediate attempt is absent. The report exposes that absence rather than
claiming a complete history. A later final skip prevents recovery classification.

## Wilson calculation

Let n = executed attempts and p = (fail + error) / n, with z = 1.959963984540054.
For n > 0:

- denominator = 1 + z²/n
- center = (p + z²/(2n)) / denominator
- radius = z sqrt(p(1-p)/n + z²/(4n²)) / denominator
- endpoints = center ± radius, clipped to [0, 1]

For n = 0 the interval and frequency are null. This is the conventional score
interval under binomial sampling assumptions, offered as descriptive context.
Retries are frequently non-independent; the interval does not correct selection
bias or prove reliability. There is no claim that all test attempts share one
underlying failure probability.

## Resource and output behavior

The loader reads bounded physical lines from a binary stream. It rejects the
whole input before a report is rendered; no partial analysis is emitted on invalid
input. Parsing happens in memory, then aggregation is bounded by 100000 records.
The public `analyze` iterable interface applies the record limit and duplicate
check too. Direct `Observation` construction applies the same field validation.

Known durations use an accurate floating-point summation, with overflow rejected.
Nonzero JSON float tokens that underflow to zero are rejected before field
validation, including negative durations. Exact zero and representable subnormal
values remain valid. Values otherwise retain ordinary floating-point limitations.
The direct Python API cannot distinguish literal zero from caller-side underflow. Durations are not rounded to
currency, combined across groups as a score, or treated as wall-clock latency.

## Future adapters

JUnit dialects differ in retries and outcome representation. A future adapter
must require revision, environment, and run metadata; reject DTD/entity declarations
and ambiguous outcomes; handle XML namespaces and nested suites without double
counting; identify testcase names unambiguously; and avoid retaining captured
stdout, exception messages, or properties. Until those guarantees are tested,
there is intentionally no XML ingestion command.
