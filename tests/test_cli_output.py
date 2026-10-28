"""Real buffered-output failures must override successful and gated reports."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


class OutputErrors(unittest.TestCase):
    def cases(self):
        for count in (1, 200):
            rows = []
            for index in range(count):
                for attempt, outcome in ((1, "fail"), (2, "pass")):
                    rows.append(dict(test_id=f"private-test-{index}", revision="r",
                                     environment="e", run_id="run", attempt=attempt,
                                     outcome=outcome))
            data = ("\n".join(json.dumps(row) for row in rows) + "\n").encode()
            for format in ("json", "text"):
                for gated in (False, True):
                    command = [sys.executable, "-m", "testvariance", "analyze", "-",
                               "--format", format]
                    if gated:
                        command.append("--fail-on-mixed")
                    yield count, format, gated, command, data

    def assert_failure(self, result):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stderr,
                         b"testvariance: cannot read input or write output\n")

    @unittest.skipUnless(Path("/dev/full").exists(), "requires /dev/full")
    def test_full_device_small_large_formats_and_gate(self):
        for count, format, gated, command, data in self.cases():
            with self.subTest(count=count, format=format, gated=gated):
                with open("/dev/full", "wb") as output:
                    result = subprocess.run(command, input=data, stdout=output,
                                            stderr=subprocess.PIPE)
                self.assert_failure(result)

    def test_closed_pipe_small_large_formats_and_gate(self):
        for count, format, gated, command, data in self.cases():
            with self.subTest(count=count, format=format, gated=gated):
                reader, writer = os.pipe()
                os.close(reader)
                with os.fdopen(writer, "wb") as output:
                    result = subprocess.run(command, input=data, stdout=output,
                                            stderr=subprocess.PIPE)
                self.assert_failure(result)


if __name__ == "__main__":
    unittest.main()
