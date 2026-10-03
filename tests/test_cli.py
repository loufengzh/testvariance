import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def call(self, *args, data=b''):
        return subprocess.run([sys.executable, '-m', 'testvariance', *args], input=data, capture_output=True, check=False)

    def test_empty_exact_json(self):
        result = self.call('analyze', '-')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'{\n  "group_count": 0,\n  "groups": [],\n  "mixed_group_count": 0,\n  "observation_count": 0,\n  "schema_version": 1\n}\n')
        self.assertEqual(result.stderr, b'')

    def test_empty_exact_text(self):
        result = self.call('analyze', '-', '--format', 'text', '--fail-on-mixed')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'Observations: 0; comparable groups: 0; mixed groups: 0\n')

    def test_example_and_explicit_gate(self):
        for gate, expected in (([], 0), (['--fail-on-mixed'], 1)):
            result = self.call('analyze', str(ROOT / 'examples' / 'outcomes.jsonl'), *gate)
            self.assertEqual(result.returncode, expected, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['mixed_group_count'], 1)
            self.assertEqual(report['observation_count'], 7)

    def test_invalid_input_no_partial_report(self):
        result = self.call('analyze', '-', data=b'{"secret":"do not echo"}')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(result.stderr, b'testvariance: line 1: record has missing or unknown fields\n')

    def test_missing_file(self):
        result = self.call('analyze', '/does-not-exist/private-input')
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(b'private-input', result.stderr)

    def test_usage(self):
        self.assertEqual(self.call().returncode, 2)
        self.assertEqual(self.call('analyze', '-', '--format', 'xml').returncode, 2)
        self.assertEqual(self.call('--version').stdout, b'testvariance 0.1.0\n')

    def test_text_escapes_terminal_controls(self):
        row = dict(test_id='a\x1b[31m\n', revision='r', environment='e', run_id='a', attempt=1, outcome='pass')
        result = self.call('analyze', '-', '--format', 'text', data=json.dumps(row).encode())
        self.assertEqual(result.returncode, 0)
        self.assertNotIn(b'\x1b', result.stdout)
        self.assertEqual(len(result.stdout.splitlines()), 2)


if __name__ == '__main__':
    unittest.main()
