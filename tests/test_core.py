import io
import json
import math
import unittest
from unittest.mock import patch

from testvariance import InputError, Observation, analyze, load_jsonl, wilson_interval


def row(**changes):
    value = dict(test_id="suite/test", revision="abc", environment="linux-py312", run_id="run-1", attempt=1, outcome="pass")
    value.update(changes)
    return value


def load(*rows):
    return load_jsonl(io.BytesIO("\n".join(json.dumps(value) for value in rows).encode()))


class ValidationTests(unittest.TestCase):
    def test_optional_duration_and_unicode(self):
        rows = load(row(test_id="测试/тест/prüfen", duration_seconds=None), row(attempt=2, duration_seconds=0))
        self.assertEqual(rows[0].duration_seconds, None)
        self.assertEqual(rows[1].duration_seconds, 0)

    def test_duration_underflow_rejected(self):
        for token in ("1e-400", "-1e-400", "2e-324", "-2e-324", "0." + "0" * 350 + "1"):
            raw = json.dumps(row(duration_seconds="TOKEN")).replace('"TOKEN"', token).encode()
            with self.subTest(token=token), self.assertRaisesRegex(InputError, "line 1: nonzero number underflows"):
                load_jsonl(io.BytesIO(raw))

    def test_duration_float_boundaries_preserved(self):
        for token in ("0e-999999", "-0.0e999999", "5e-324", "1e-320", "0.1", "1.0000000000000001"):
            raw = json.dumps(row(duration_seconds="TOKEN")).replace('"TOKEN"', token).encode()
            with self.subTest(token=token):
                value = load_jsonl(io.BytesIO(raw))[0].duration_seconds
                self.assertEqual(value, float(token))
                self.assertEqual(math.copysign(1, value), math.copysign(1, float(token)))

    def test_invalid_records(self):
        invalid = [[], {}, row(unknown=1), row(attempt=True), row(attempt=0), row(attempt=-1), row(attempt=1.5), row(attempt="1"), row(outcome="failed"), row(outcome=[]), row(test_id=" "), row(environment=None), row(revision="x" * 4097), row(run_id="\ud800"), row(duration_seconds=-1), row(duration_seconds=True), row(duration_seconds="3"), row(duration_seconds=float("inf")), row(duration_seconds=float("nan")), row(duration_seconds=10**400)]
        for value in invalid:
            with self.subTest(value=str(value)[:80]), self.assertRaises(InputError):
                load(value)

    def test_missing_fields(self):
        for key in row():
            value = row()
            del value[key]
            with self.subTest(key=key), self.assertRaises(InputError):
                load(value)

    def test_duplicate_observation_keys(self):
        for second in (row(), row(outcome="fail")):
            with self.assertRaisesRegex(InputError, "duplicate observation"):
                load(row(), second)
        with self.assertRaises(InputError):
            analyze([Observation(**row()), Observation(**row())])

    def test_malformed_sources(self):
        for raw in (b'{', b'\xff', b'{"a": 1, "a": 2}', b'null', b'NaN', b'\xef\xbb\xbf{}', b'[' * 2000, b'{"attempt":' + b'1' * 5000 + b'}'):
            with self.subTest(raw=raw[:30]), self.assertRaises(InputError):
                load_jsonl(io.BytesIO(raw))

    def test_bounds(self):
        with self.assertRaisesRegex(InputError, "64 KiB"):
            load_jsonl(io.BytesIO(b' ' * 65537))
        with patch("testvariance.core.MAX_BYTES", 2), self.assertRaisesRegex(InputError, "32 MiB"):
            load_jsonl(io.BytesIO(b'   '))
        with patch("testvariance.core.MAX_RECORDS", 1):
            with self.assertRaises(InputError):
                load(row(), row(attempt=2))
            with self.assertRaises(InputError):
                analyze([Observation(**row()), Observation(**row(attempt=2))])

    def test_no_raw_content_in_error(self):
        with self.assertRaises(InputError) as caught:
            load(row(outcome="SENSITIVE-CONTENT"))
        self.assertNotIn("SENSITIVE-CONTENT", str(caught.exception))

    def test_direct_library_validation(self):
        with self.assertRaises(InputError):
            Observation(**row(duration_seconds=float("nan")))
        with self.assertRaises(InputError):
            analyze([row()])


class AnalysisTests(unittest.TestCase):
    def group(self, *rows):
        return analyze(load(*rows))["groups"][0]

    def test_empty(self):
        self.assertEqual(analyze(load_jsonl(io.BytesIO(b'\n  \n'))), {"schema_version": 1, "observation_count": 0, "group_count": 0, "mixed_group_count": 0, "groups": []})

    def test_all_skip(self):
        group = self.group(row(outcome="skip"))
        self.assertEqual(group["executed_attempts"], 0)
        self.assertIsNone(group["failure_frequency"])
        self.assertIsNone(group["failure_frequency_wilson_95"])
        self.assertFalse(group["mixed_outcomes"])

    def test_fail_error_and_skip_denominator(self):
        group = self.group(row(outcome="fail"), row(attempt=2, outcome="error"), row(attempt=3, outcome="pass"), row(attempt=4, outcome="skip"))
        self.assertEqual(group["counts"], {"pass": 1, "fail": 1, "error": 1, "skip": 1})
        self.assertEqual(group["failure_frequency"], 2 / 3)
        self.assertTrue(group["mixed_outcomes"])
        self.assertEqual(group["recovered_runs"], 0)  # Final observed attempt is skip.

    def test_different_revisions_environments_never_mixed(self):
        report = analyze(load(row(outcome="fail"), row(revision="def"), row(environment="windows")))
        self.assertEqual(report["group_count"], 3)
        self.assertEqual(report["mixed_group_count"], 0)

    def test_failure_only_not_mixed(self):
        group = self.group(row(outcome="error"))
        self.assertFalse(group["mixed_outcomes"])
        self.assertEqual(group["failure_frequency"], 1)

    def test_out_of_order_recovery(self):
        group = self.group(row(attempt=3), row(attempt=1, outcome="error"))
        run = group["runs"][0]
        self.assertTrue(run["recovered"])
        self.assertEqual(run["observed_attempts"], [1, 3])
        self.assertEqual(run["missing_attempt_count"], 1)
        self.assertEqual(run["final_attempt"], 3)

    def test_pass_then_fail_not_recovered(self):
        group = self.group(row(), row(attempt=2, outcome="fail"))
        self.assertEqual(group["recovered_runs"], 0)

    def test_never_order_across_runs(self):
        group = self.group(row(run_id="first", outcome="fail"), row(run_id="second"))
        self.assertTrue(group["mixed_outcomes"])
        self.assertEqual(group["recovered_runs"], 0)

    def test_duration_missing_and_retry_cost(self):
        group = self.group(row(duration_seconds=10, outcome="fail"), row(attempt=2, duration_seconds=3), row(attempt=4), row(attempt=5, duration_seconds=0, outcome="skip"))
        self.assertEqual(group["observed_duration_seconds"], 13)
        self.assertEqual(group["observed_retry_seconds"], 3)
        self.assertEqual(group["missing_duration_count"], 1)
        self.assertEqual(group["retry_missing_duration_count"], 1)
        self.assertEqual(group["runs"][0]["missing_attempt_count"], 1)

    def test_first_observed_attempt_can_be_retry(self):
        group = self.group(row(attempt=3, duration_seconds=2))
        self.assertEqual(group["observed_retry_seconds"], 2)
        self.assertEqual(group["runs"][0]["missing_attempt_count"], 2)

    def test_deterministic_under_shuffle(self):
        rows = [row(), row(run_id="z", outcome="fail"), row(attempt=3), row(test_id="aaa")]
        self.assertEqual(analyze(load(*rows)), analyze(load(*reversed(rows))))

    def test_aggregate_overflow(self):
        with self.assertRaisesRegex(InputError, "aggregate duration"):
            self.group(row(duration_seconds=1e308), row(attempt=2, duration_seconds=1e308))

    def test_wilson(self):
        low, high = wilson_interval(1, 2)
        self.assertAlmostEqual(low, 0.0945312057)
        self.assertAlmostEqual(high, 0.9054687943)
        self.assertEqual(wilson_interval(0, 0), None)
        self.assertAlmostEqual(wilson_interval(0, 10)[0], 0)
        self.assertAlmostEqual(wilson_interval(10, 10)[1], 1)
        for args in ((-1, 2), (3, 2), (True, 2), (1, -1)):
            with self.assertRaises(ValueError):
                wilson_interval(*args)


if __name__ == "__main__":
    unittest.main()
