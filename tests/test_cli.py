import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from testvariance.cli import main

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def call(self, *args, data=b''):
        return subprocess.run([sys.executable, '-m', 'testvariance', *args], input=data, capture_output=True, check=False)

    def test_windows_newline_translation_is_disabled(self):
        # Simulate Windows translation on every host; do not normalize assertions.
        for args, expected_code in (
            (['analyze', '-'], 0),
            (['analyze', '-', '--format', 'text'], 0),
            (['--version'], 0),
            (['analyze', '/does-not-exist/private-input'], 2),
            ([], 2),
        ):
            with self.subTest(args=args):
                stdout_bytes, stderr_bytes = io.BytesIO(), io.BytesIO()
                stdout = io.TextIOWrapper(stdout_bytes, encoding='utf-8', newline='\r\n')
                stderr = io.TextIOWrapper(stderr_bytes, encoding='utf-8', newline='\r\n')
                stdin = io.TextIOWrapper(io.BytesIO(b''), encoding='utf-8')
                with patch('sys.stdout', stdout), patch('sys.stderr', stderr), patch('sys.stdin', stdin):
                    try:
                        code = main(args)
                    except SystemExit as exc:
                        code = exc.code
                    stdout.flush()
                    stderr.flush()
                    output = stdout_bytes.getvalue() + stderr_bytes.getvalue()
                self.assertEqual(code, expected_code)
                self.assertIn(b'\n', output)
                self.assertNotIn(b'\r', output)
                stdout.close()
                stderr.close()
                stdin.close()

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

    def test_duration_underflow_no_partial_report(self):
        row = dict(test_id='private-test', revision='r', environment='e', run_id='a', attempt=1, outcome='pass', duration_seconds='TOKEN')
        valid = json.dumps(dict(row, duration_seconds=1)).encode() + b'\n'
        for token in ('1e-400', '-1e-400'):
            data = valid + json.dumps(dict(row, attempt=2)).replace('"TOKEN"', token).encode()
            with self.subTest(token=token):
                result = self.call('analyze', '-', data=data)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b'')
                self.assertEqual(result.stderr, b'testvariance: line 2: nonzero number underflows the supported float range\n')
                self.assertNotIn(b'private-test', result.stderr)

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
