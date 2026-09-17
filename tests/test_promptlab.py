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
            prompt_text = file.read().decode("utf-8")

        result1 = promptlab.prompt_hash(prompt_text)
        result2 = promptlab.prompt_hash(prompt_text)

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
                {"contains": "billing"},
                response
            )
        )

        # 2. not_contains
        self.assertTrue(
            promptlab.check_assertion(
                {"not_contains": "technical"},
                response
            )
        )

        # 3. equals
        self.assertTrue(
            promptlab.check_assertion(
                {"equals": "billing"},
                response
            )
        )

        # 4. matches
        self.assertTrue(
            promptlab.check_assertion(
                {"matches": "^billing$"},
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
                {"json_valid": True},
                json_response
            )
        )

        # 6. json_field_equals
        self.assertTrue(
            promptlab.check_assertion(
                {
                    "json_field_equals": {
                        "field": "category",
                        "value": "billing"
                    }
                },
                json_response
            )
        )

        # 7. max_tokens
        self.assertTrue(
            promptlab.check_assertion(
                {"max_tokens": 10},
                response
            )
        )

        # 8. finish_is
        self.assertTrue(
            promptlab.check_assertion(
                {"finish_is": "stop"},
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

        self.assertIn("Passed: 5", result.stdout)
        self.assertIn("Failed: 0", result.stdout)

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