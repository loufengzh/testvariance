# Security

This tool processes local UTF-8 JSONL only. It does not execute records, invoke
shells, read environment variables, parse XML, or make network requests.
Resource limits reduce accidental oversized-input risk; they are not a sandbox.
Memory overhead can exceed the source file size. Do not process untrusted files
with elevated privileges. Interrupt execution if resource consumption is unsafe.

Reports preserve test/revision/environment/run identifiers. Use synthetic or
redacted identifiers before sharing reports publicly. Input validation errors do
not echo record contents, and text reports escape identifier control characters.
These properties do not constitute general-purpose anonymization.

Only the 0.1.x line is currently maintained. For security defects, prefer the
repository's private vulnerability reporting channel if enabled. Otherwise open
an issue with a minimal description and no sensitive details, asking for a private
channel before supplying an exploit or confidential input. Do not assume an issue
is private. There is no dedicated response-time commitment.
