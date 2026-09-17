import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import promptlab


ROOT = Path(__file__).resolve().parents[1]


class PromptLabTests(unittest.TestCase):

    def test_token_count(self):
        self.assertEqual(promptlab.token_count(""), 0)
        self.assertEqual(promptlab.token_count("abcd"), 1)
        self.assertEqual(promptlab.token_count("abcde"), 2)
        self.assertEqual(promptlab.token_count("abcdefgh"), 2)

    def test_prompt_hash(self):
        prompt_file = ROOT / "prompts" / "classify_v1.txt"

        with open(prompt_file, "rb") as file:
            prompt_bytes = file.read()

        result1 = promptlab.prompt_hash(prompt_bytes)
        result2 = promptlab.prompt_hash(prompt_bytes)

        self.assertEqual(result1, result2)
        self.assertEqual(len(result1), 12)

        self.assertTrue(
            all(
                character in "0123456789abcdef"
                for character in result1
            )
        )

    def test_all_assertions(self):
        response = {
            "output": "billing",
            "finish": "stop"
        }

        # 1. contains
        self.assertTrue(
            promptlab.check_assertion(
                {
                    "type": "contains",
                    "value": "billing"
                },
                response
            )
        )

        # 2. not_contains
        self.assertTrue(
            promptlab.check_assertion(
                {
                    "type": "not_contains",
                    "value": "technical"
                },
                response
            )
        )

        # 3. equals
        self.assertTrue(
            promptlab.check_assertion(
                {
                    "type": "equals",
                    "value": "billing"
                },
                response
            )
        )

        # 4. matches
        self.assertTrue(
            promptlab.check_assertion(
                {
                    "type": "matches",
                    "pattern": "^billing$"
                },
                response
            )
        )

        # 5. json_valid
        json_response = {
            "output": "{\"category\":\"billing\"}",
            "finish": "stop"
        }

        self.assertTrue(
            promptlab.check_assertion(
                {
                    "type": "json_valid"
                },
                json_response
            )
        )

        # 6. json_field_equals
        self.assertTrue(
            promptlab.check_assertion(
                {
                    "type": "json_field_equals",
                    "field": "category",
                    "value": "billing"
                },
                json_response
            )
        )

        # 7. max_tokens
        self.assertTrue(
            promptlab.check_assertion(
                {
                    "type": "max_tokens",
                    "value": 10
                },
                response
            )
        )

        # 8. finish_is
        self.assertTrue(
            promptlab.check_assertion(
                {
                    "type": "finish_is",
                    "value": "stop"
                },
                response
            )
        )

    def test_smoke_suite(self):
        result = subprocess.run(
            [
                sys.executable,
                "promptlab.py",
                "run",
                "--suite",
                "suites/smoke.json"
            ],
            cwd=ROOT,
            capture_output=True,
            text=True
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=result.stdout + "\n" + result.stderr
        )

        # The report goes to stdout.
        # The human-readable --report summary goes to stderr
        # only when --report is supplied.
        report = json.loads(result.stdout)

        self.assertEqual(
            report["totals"]["cases"],
            5
        )

        self.assertEqual(
            report["totals"]["passed"],
            5
        )

        self.assertEqual(
            report["totals"]["failed"],
            0
        )

        self.assertEqual(
            report["totals"]["flaky"],
            0
        )

    def test_doctor(self):
        result = subprocess.run(
            [
                sys.executable,
                "promptlab.py",
                "doctor"
            ],
            cwd=ROOT,
            capture_output=True,
            text=True
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=result.stdout + "\n" + result.stderr
        )

        self.assertIn(
            "DOCTOR RESULT: PASS",
            result.stdout
        )

    def test_compare(self):
        baseline = ROOT / "report.json"
        candidate = ROOT / "report_v2.json"

        self.assertTrue(baseline.exists())
        self.assertTrue(candidate.exists())

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_diff.json"

            result = subprocess.run(
                [
                    sys.executable,
                    "promptlab.py",
                    "compare",
                    "--baseline",
                    "report.json",
                    "--candidate",
                    "report_v2.json",
                    "--out",
                    str(output_file)
                ],
                cwd=ROOT,
                capture_output=True,
                text=True
            )

            self.assertEqual(
                result.returncode,
                0,
                msg=result.stdout + "\n" + result.stderr
            )

            self.assertTrue(output_file.exists())

            with open(
                output_file,
                "r",
                encoding="utf-8"
            ) as file:
                diff = json.load(file)

            self.assertIn("summary", diff)
            self.assertIn("cases", diff)

            self.assertEqual(
                diff["summary"]["regressed"],
                0
            )

            self.assertEqual(
                diff["summary"]["improved"],
                0
            )


if __name__ == "__main__":
    unittest.main()