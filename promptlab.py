import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path


SUPPORTED_ASSERTIONS = {
    "contains",
    "not_contains",
    "equals",
    "matches",
    "json_valid",
    "json_field_equals",
    "max_tokens",
    "finish_is",
}


def load_suite(suite_path):
    path = Path(suite_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Suite file not found: {suite_path}"
        )

    if not path.is_file():
        raise OSError(
            f"Suite path is not a file: {suite_path}"
        )

    try:
        with open(path, "r", encoding="utf-8") as file:
            suite = json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Malformed suite JSON: {error}"
        )

    if not isinstance(suite, dict):
        raise ValueError(
            "Suite must be a JSON object."
        )

    required_fields = [
        "name",
        "prompt_file",
        "model",
        "runs",
        "cases",
    ]

    for field in required_fields:
        if field not in suite:
            raise ValueError(
                f"Suite is missing required field: {field}"
            )

    if not isinstance(suite["cases"], list):
        raise ValueError(
            "Suite 'cases' must be a list."
        )

    if not isinstance(suite["runs"], int) or suite["runs"] < 1:
        raise ValueError(
            "Suite 'runs' must be an integer greater than 0."
        )

    for case in suite["cases"]:

        if not isinstance(case, dict):
            raise ValueError(
                "Each case must be a JSON object."
            )

        for field in ["id", "input", "assert"]:

            if field not in case:
                raise ValueError(
                    f"Case is missing required field: {field}"
                )

        if not isinstance(case["assert"], list):
            raise ValueError(
                f"Assertions for case {case['id']} must be a list."
            )

        for assertion in case["assert"]:

            if (
                not isinstance(assertion, dict)
                or len(assertion) != 1
            ):
                raise ValueError(
                    f"Invalid assertion in case {case['id']}."
                )

            assertion_type = list(
                assertion.keys()
            )[0]

            if assertion_type not in SUPPORTED_ASSERTIONS:
                raise ValueError(
                    f"Unsupported assertion: {assertion_type}"
                )

    return suite


def load_prompt(prompt_path):
    path = Path(prompt_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_path}"
        )

    if not path.is_file():
        raise OSError(
            f"Prompt path is not a file: {prompt_path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return file.read()


def load_report(report_path):
    path = Path(report_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Report file not found: {report_path}"
        )

    if not path.is_file():
        raise OSError(
            f"Report path is not a file: {report_path}"
        )

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            report = json.load(file)

    except json.JSONDecodeError as error:

        raise ValueError(
            f"Malformed report JSON: {error}"
        )

    if not isinstance(report, dict):
        raise ValueError(
            "Report must be a JSON object."
        )

    required_fields = [
        "suite",
        "prompt_file",
        "prompt_hash",
        "runs",
        "model",
        "totals",
        "cases",
    ]

    for field in required_fields:

        if field not in report:

            raise ValueError(
                f"Report is missing required field: {field}"
            )

    return report


def run_model(prompt, user_input):
    start_time = time.perf_counter()

    result = subprocess.run(
        [
            sys.executable,
            "stubmodel.py",
            "--prompt",
            prompt,
            "--input",
            user_input,
        ],
        capture_output=True,
        text=True,
    )

    end_time = time.perf_counter()

    wall_ms = (
        end_time - start_time
    ) * 1000

    if result.returncode != 0:

        error_message = (
            result.stderr.strip()
        )

        if not error_message:

            error_message = (
                "Model process failed."
            )

        raise RuntimeError(
            error_message
        )

    try:

        response = json.loads(
            result.stdout
        )

    except json.JSONDecodeError:

        raise RuntimeError(
            "Model returned invalid JSON."
        )

    if not isinstance(response, dict):

        raise RuntimeError(
            "Model response must be a JSON object."
        )

    return response, wall_ms


def token_count(text):
    return math.ceil(
        len(text) / 4
    )


def prompt_hash(prompt):
    return hashlib.sha256(
        prompt.encode("utf-8")
    ).hexdigest()[:12]


def check_assertion(assertion, response):

    assertion_type = list(
        assertion.keys()
    )[0]

    expected = assertion[
        assertion_type
    ]

    output = response.get(
        "output",
        ""
    )

    if assertion_type == "contains":

        return expected in output

    elif assertion_type == "not_contains":

        return expected not in output

    elif assertion_type == "equals":

        return output == expected

    elif assertion_type == "matches":

        try:

            return (
                re.search(
                    expected,
                    output
                )
                is not None
            )

        except re.error:

            return False

    elif assertion_type == "json_valid":

        try:

            json.loads(output)

            return True

        except json.JSONDecodeError:

            return False

    elif assertion_type == "json_field_equals":

        try:

            field = expected["field"]

            expected_value = (
                expected["value"]
            )

            data = json.loads(
                output
            )

            return (
                data.get(field)
                == expected_value
            )

        except (
            json.JSONDecodeError,
            TypeError,
            KeyError,
        ):

            return False

    elif assertion_type == "max_tokens":

        actual_tokens = token_count(
            output
        )

        return (
            actual_tokens
            <= expected
        )

    elif assertion_type == "finish_is":

        return (
            response.get("finish")
            == expected
        )

    return False


def run_case(prompt, case):

    response, wall_ms = run_model(
        prompt,
        case["input"]
    )

    assertion_results = []

    for assertion in case["assert"]:

        assertion_type = list(
            assertion.keys()
        )[0]

        expected = assertion[
            assertion_type
        ]

        passed = check_assertion(
            assertion,
            response
        )

        assertion_results.append(
            {
                "type": assertion_type,
                "expected": expected,
                "passed": passed,
            }
        )

    case_passed = all(
        result["passed"]
        for result in assertion_results
    )

    input_tokens = token_count(
        prompt + case["input"]
    )

    output_tokens = token_count(
        response.get(
            "output",
            ""
        )
    )

    return (
        case_passed,
        response,
        assertion_results,
        input_tokens,
        output_tokens,
        wall_ms,
    )


def run_command(args):

    try:

        suite = load_suite(
            args.suite
        )

    except FileNotFoundError as error:

        print(
            f"ERROR: {error}"
        )

        return 4

    except OSError as error:

        print(
            f"ERROR: {error}"
        )

        return 4

    except ValueError as error:

        print(
            f"ERROR: {error}"
        )

        return 1

    try:

        prompt = load_prompt(
            suite["prompt_file"]
        )

    except FileNotFoundError as error:

        print(
            f"ERROR: {error}"
        )

        return 4

    except OSError as error:

        print(
            f"ERROR: {error}"
        )

        return 4

    print(
        "Suite name:",
        suite["name"]
    )

    print(
        "Model:",
        suite["model"]
    )

    if args.runs is not None:

        if args.runs < 1:

            print(
                "ERROR: --runs must be greater than 0."
            )

            return 1

        runs = args.runs

    else:

        runs = suite["runs"]

    print(
        "Runs:",
        runs
    )

    print(
        "Cases:",
        len(suite["cases"])
    )

    print(
        "Prompt file:",
        suite["prompt_file"]
    )

    print(
        "Prompt length:",
        len(prompt)
    )

    print(
        "Prompt hash:",
        prompt_hash(prompt)
    )

    print()

    total_cases = len(
        suite["cases"]
    )

    passed_cases = 0
    failed_cases = 0
    flaky_cases = 0

    total_assertions = 0
    passed_assertions = 0
    failed_assertions = 0

    total_tokens_in = 0
    total_tokens_out = 0
    total_wall_ms = 0

    case_reports = []

    for case in suite["cases"]:

        print(
            "Case ID:",
            case["id"]
        )

        print(
            "Input:",
            case["input"]
        )

        run_results = []
        run_reports = []

        for run_number in range(
            1,
            runs + 1
        ):

            print()

            print(
                "  Run",
                run_number,
                "of",
                runs
            )

            try:

                (
                    case_passed,
                    response,
                    assertion_results,
                    input_tokens,
                    output_tokens,
                    wall_ms,
                ) = run_case(
                    prompt,
                    case
                )

            except RuntimeError as error:

                print()

                print(
                    "ERROR: Model invocation failed."
                )

                print(error)

                return 3

            run_results.append(
                case_passed
            )

            total_tokens_in += (
                input_tokens
            )

            total_tokens_out += (
                output_tokens
            )

            total_wall_ms += (
                wall_ms
            )

            print(
                "  Model response:",
                response
            )

            print(
                "  Tokens in:",
                input_tokens
            )

            print(
                "  Tokens out:",
                output_tokens
            )

            print(
                "  Wall time: {:.2f} ms".format(
                    wall_ms
                )
            )

            for result in assertion_results:

                total_assertions += 1

                print(
                    "    Assertion:",
                    result["type"]
                )

                print(
                    "    Expected:",
                    result["expected"]
                )

                if result["passed"]:

                    passed_assertions += 1

                    print(
                        "    Result: PASS"
                    )

                else:

                    failed_assertions += 1

                    print(
                        "    Result: FAIL"
                    )

            if case_passed:

                print(
                    "  Case result: PASS"
                )

            else:

                print(
                    "  Case result: FAIL"
                )

            run_reports.append(
                {
                    "run": run_number,
                    "output": response.get(
                        "output",
                        ""
                    ),
                    "finish": response.get(
                        "finish"
                    ),
                    "tokens_in": input_tokens,
                    "tokens_out": output_tokens,
                    "wall_ms": round(
                        wall_ms,
                        2
                    ),
                    "assertions": assertion_results,
                    "passed": case_passed,
                }
            )

        passed_count = sum(
            run_results
        )

        failed_count = (
            len(run_results)
            - passed_count
        )

        if passed_count == runs:

            status = "PASS"

            passed_cases += 1

        elif failed_count == runs:

            status = "FAIL"

            failed_cases += 1

        else:

            status = "FLAKY"

            flaky_cases += 1

        case_reports.append(
            {
                "id": case["id"],
                "input": case["input"],
                "status": status,
                "runs": run_reports,
            }
        )

        print()

        print(
            "  Final status:",
            status
        )

        print()

    report = {
        "suite": suite["name"],
        "prompt_file": suite["prompt_file"],
        "prompt_hash": prompt_hash(prompt),
        "runs": runs,
        "model": suite["model"],
        "totals": {
            "cases": total_cases,
            "passed": passed_cases,
            "failed": failed_cases,
            "flaky": flaky_cases,
            "assertions": total_assertions,
            "assertions_passed": passed_assertions,
            "assertions_failed": failed_assertions,
            "tokens_in": total_tokens_in,
            "tokens_out": total_tokens_out,
            "wall_ms": round(
                total_wall_ms,
                2
            ),
        },
        "cases": case_reports,
    }

    if args.out:

        output_path = Path(
            args.out
        )

        try:

            with open(
                output_path,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    report,
                    file,
                    indent=2
                )

        except OSError as error:

            print(
                f"ERROR: Could not write report: {error}"
            )

            return 4

        print(
            "Report written to:",
            output_path
        )

    print(
        "=" * 40
    )

    print(
        "SUMMARY"
    )

    print(
        "=" * 40
    )

    print(
        "Total cases:",
        total_cases
    )

    print(
        "Passed:",
        passed_cases
    )

    print(
        "Failed:",
        failed_cases
    )

    print(
        "Flaky:",
        flaky_cases
    )

    print()

    print(
        "Total assertions:",
        total_assertions
    )

    print(
        "Assertions passed:",
        passed_assertions
    )

    print(
        "Assertions failed:",
        failed_assertions
    )

    print()

    print(
        "Tokens in:",
        total_tokens_in
    )

    print(
        "Tokens out:",
        total_tokens_out
    )

    print(
        "Wall time: {:.2f} ms".format(
            total_wall_ms
        )
    )

    print(
        "=" * 40
    )

    if (
        failed_cases > 0
        or flaky_cases > 0
    ):

        return 2

    return 0


def get_case_statuses(report):

    statuses = {}

    for case in report.get(
        "cases",
        []
    ):

        case_id = case.get(
            "id"
        )

        if case_id is not None:

            statuses[case_id] = case.get(
                "status",
                "UNKNOWN"
            )

    return statuses


def get_case_tokens(case):

    total = 0

    for run in case.get(
        "runs",
        []
    ):

        total += run.get(
            "tokens_out",
            0
        )

    return total


def percentage_change(old, new):

    if old == 0:

        if new == 0:

            return 0

        return None

    return (
        (new - old)
        / old
    ) * 100


def compare_command(args):

    try:

        baseline = load_report(
            args.baseline
        )

        candidate = load_report(
            args.candidate
        )

    except FileNotFoundError as error:

        print(
            f"ERROR: {error}"
        )

        return 4

    except OSError as error:

        print(
            f"ERROR: {error}"
        )

        return 4

    except ValueError as error:

        print(
            f"ERROR: {error}"
        )

        return 1

    baseline_statuses = (
        get_case_statuses(
            baseline
        )
    )

    candidate_statuses = (
        get_case_statuses(
            candidate
        )
    )

    all_case_ids = sorted(
        set(baseline_statuses)
        | set(candidate_statuses)
    )

    comparisons = []

    regressed = 0
    improved = 0
    unchanged = 0
    new_cases = 0
    removed_cases = 0

    baseline_cases = {
        case["id"]: case
        for case in baseline.get(
            "cases",
            []
        )
    }

    candidate_cases = {
        case["id"]: case
        for case in candidate.get(
            "cases",
            []
        )
    }

    for case_id in all_case_ids:

        in_baseline = (
            case_id in baseline_statuses
        )

        in_candidate = (
            case_id in candidate_statuses
        )

        if not in_baseline:

            classification = "new"

            new_cases += 1

            baseline_status = None

            candidate_status = (
                candidate_statuses[
                    case_id
                ]
            )

            token_delta = (
                get_case_tokens(
                    candidate_cases[
                        case_id
                    ]
                )
            )

        elif not in_candidate:

            classification = "removed"

            removed_cases += 1

            baseline_status = (
                baseline_statuses[
                    case_id
                ]
            )

            candidate_status = None

            token_delta = -get_case_tokens(
                baseline_cases[
                    case_id
                ]
            )

        else:

            baseline_status = (
                baseline_statuses[
                    case_id
                ]
            )

            candidate_status = (
                candidate_statuses[
                    case_id
                ]
            )

            if (
                baseline_status == "PASS"
                and candidate_status == "FAIL"
            ):

                classification = "regressed"

                regressed += 1

            elif (
                baseline_status == "FAIL"
                and candidate_status == "PASS"
            ):

                classification = "improved"

                improved += 1

            else:

                classification = "unchanged"

                unchanged += 1

            baseline_tokens = (
                get_case_tokens(
                    baseline_cases[
                        case_id
                    ]
                )
            )

            candidate_tokens = (
                get_case_tokens(
                    candidate_cases[
                        case_id
                    ]
                )
            )

            token_delta = (
                candidate_tokens
                - baseline_tokens
            )

        comparisons.append(
            {
                "id": case_id,
                "classification": classification,
                "baseline_status": baseline_status,
                "candidate_status": candidate_status,
                "token_delta": token_delta,
            }
        )

    baseline_total_tokens = (
        baseline.get(
            "totals",
            {}
        ).get(
            "tokens_out",
            0
        )
    )

    candidate_total_tokens = (
        candidate.get(
            "totals",
            {}
        ).get(
            "tokens_out",
            0
        )
    )

    total_token_delta = (
        candidate_total_tokens
        - baseline_total_tokens
    )

    token_percentage = percentage_change(
        baseline_total_tokens,
        candidate_total_tokens
    )

    warnings = []

    if (
        baseline.get("prompt_hash")
        == candidate.get("prompt_hash")
    ):

        warnings.append(
            "Baseline and candidate use the same prompt hash."
        )

    if (
        baseline.get("suite")
        != candidate.get("suite")
    ):

        warnings.append(
            "Baseline and candidate use different suite names."
        )

    if (
        baseline.get("model")
        != candidate.get("model")
    ):

        warnings.append(
            "Baseline and candidate use different models."
        )

    if (
        baseline.get("runs")
        != candidate.get("runs")
    ):

        warnings.append(
            "Baseline and candidate use different run counts."
        )

    diff = {
        "baseline": args.baseline,
        "candidate": args.candidate,
        "summary": {
            "regressed": regressed,
            "improved": improved,
            "unchanged": unchanged,
            "new": new_cases,
            "removed": removed_cases,
        },
        "tokens": {
            "baseline": baseline_total_tokens,
            "candidate": candidate_total_tokens,
            "delta": total_token_delta,
            "percentage_change": (
                round(
                    token_percentage,
                    2
                )
                if token_percentage is not None
                else None
            ),
        },
        "warnings": warnings,
        "cases": comparisons,
    }

    output_path = Path(
        args.out
    )

    try:

        with open(
            output_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                diff,
                file,
                indent=2
            )

    except OSError as error:

        print(
            f"ERROR: Could not write diff: {error}"
        )

        return 4

    print(
        "=" * 40
    )

    print(
        "COMPARE"
    )

    print(
        "=" * 40
    )

    print(
        "Baseline:",
        args.baseline
    )

    print(
        "Candidate:",
        args.candidate
    )

    print()

    print(
        "Regressed:",
        regressed
    )

    print(
        "Improved:",
        improved
    )

    print(
        "Unchanged:",
        unchanged
    )

    print(
        "New:",
        new_cases
    )

    print(
        "Removed:",
        removed_cases
    )

    print()

    print(
        "Baseline tokens:",
        baseline_total_tokens
    )

    print(
        "Candidate tokens:",
        candidate_total_tokens
    )

    print(
        "Token delta:",
        total_token_delta
    )

    if token_percentage is not None:

        print(
            "Token change: {:.2f}%".format(
                token_percentage
            )
        )

    else:

        print(
            "Token change: N/A"
        )

    print()

    if warnings:

        print(
            "Warnings:"
        )

        for warning in warnings:

            print(
                "-",
                warning
            )

        print()

    print(
        "Diff written to:",
        output_path
    )

    print(
        "=" * 40
    )

    return 0


def doctor_command():

    print(
        "=" * 40
    )

    print(
        "PROMPTLAB DOCTOR"
    )

    print(
        "=" * 40
    )

    problems = 0

    # Check 1: Python
    print()
    print(
        "[1/5] Checking Python..."
    )

    python_version = sys.version.split()[0]

    print(
        "      Python:",
        python_version
    )

    print(
        "      PASS"
    )

    # Check 2: stubmodel.py
    print()
    print(
        "[2/5] Checking model..."
    )

    stubmodel_path = Path(
        "stubmodel.py"
    )

    if not stubmodel_path.exists():

        print(
            "      FAIL: stubmodel.py not found."
        )

        problems += 1

    else:

        print(
            "      stubmodel.py found."
        )

        try:

            result = subprocess.run(
                [
                    sys.executable,
                    "stubmodel.py",
                    "--prompt",
                    "Doctor test",
                    "--input",
                    "I cannot log into my account.",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:

                print(
                    "      FAIL: Model process failed."
                )

                if result.stderr.strip():

                    print(
                        "      ",
                        result.stderr.strip()
                    )

                problems += 1

            else:

                print(
                    "      Model process reached."
                )

                try:

                    response = json.loads(
                        result.stdout
                    )

                    if (
                        not isinstance(
                            response,
                            dict
                        )
                    ):

                        raise ValueError(
                            "Response is not an object."
                        )

                    if "output" not in response:

                        raise ValueError(
                            "Response has no output field."
                        )

                    if "finish" not in response:

                        raise ValueError(
                            "Response has no finish field."
                        )

                    print(
                        "      Response parsing: PASS"
                    )

                except (
                    json.JSONDecodeError,
                    ValueError,
                ) as error:

                    print(
                        "      FAIL: Invalid model response."
                    )

                    print(
                        "      ",
                        error
                    )

                    problems += 1

        except subprocess.TimeoutExpired:

            print(
                "      FAIL: Model timed out."
            )

            problems += 1

    # Check 3: suites
    print()
    print(
        "[3/5] Checking suites..."
    )

    suites_path = Path(
        "suites"
    )

    if not suites_path.exists():

        print(
            "      FAIL: suites folder not found."
        )

        problems += 1

    else:

        suite_files = list(
            suites_path.glob(
                "*.json"
            )
        )

        if not suite_files:

            print(
                "      FAIL: No JSON suites found."
            )

            problems += 1

        else:

            print(
                "      Found",
                len(suite_files),
                "suite(s)."
            )

            for suite_file in suite_files:

                try:

                    suite = load_suite(
                        suite_file
                    )

                    print(
                        "      PASS:",
                        suite_file
                    )

                except (
                    FileNotFoundError,
                    OSError,
                    ValueError,
                ) as error:

                    print(
                        "      FAIL:",
                        suite_file
                    )

                    print(
                        "            ",
                        error
                    )

                    problems += 1

    # Check 4: assertions
    print()
    print(
        "[4/5] Checking assertions..."
    )

    expected_assertions = [
        "contains",
        "not_contains",
        "equals",
        "matches",
        "json_valid",
        "json_field_equals",
        "max_tokens",
        "finish_is",
    ]

    missing_assertions = [
        name
        for name in expected_assertions
        if name not in SUPPORTED_ASSERTIONS
    ]

    if missing_assertions:

        print(
            "      FAIL: Missing assertions:",
            ", ".join(
                missing_assertions
            )
        )

        problems += 1

    else:

        print(
            "      All 8 assertions registered."
        )

        print(
            "      PASS"
        )

    # Check 5: project files
    print()
    print(
        "[5/5] Checking project files..."
    )

    required_files = [
        "promptlab.py",
        "stubmodel.py",
    ]

    missing_files = []

    for filename in required_files:

        if not Path(filename).exists():

            missing_files.append(
                filename
            )

    if missing_files:

        print(
            "      FAIL: Missing:",
            ", ".join(
                missing_files
            )
        )

        problems += 1

    else:

        print(
            "      Core project files found."
        )

        print(
            "      PASS"
        )

    print()
    print(
        "=" * 40
    )

    if problems == 0:

        print(
            "DOCTOR RESULT: PASS"
        )

        print(
            "PromptLab is healthy."
        )

        print(
            "=" * 40
        )

        return 0

    else:

        print(
            "DOCTOR RESULT: FAIL"
        )

        print(
            "Problems found:",
            problems
        )

        print(
            "=" * 40
        )

        return 1


def main():

    parser = argparse.ArgumentParser(
        prog="promptlab",
        description="PromptLab - Prompt test runner",
    )

    subparsers = parser.add_subparsers(
        dest="command"
    )

    run_parser = subparsers.add_parser(
        "run"
    )

    run_parser.add_argument(
        "--suite",
        required=True
    )

    run_parser.add_argument(
        "--runs",
        type=int
    )

    run_parser.add_argument(
        "--out"
    )

    run_parser.add_argument(
        "--report",
        action="store_true"
    )

    compare_parser = subparsers.add_parser(
        "compare"
    )

    compare_parser.add_argument(
        "--baseline",
        required=True
    )

    compare_parser.add_argument(
        "--candidate",
        required=True
    )

    compare_parser.add_argument(
        "--out",
        required=True
    )

    subparsers.add_parser(
        "doctor"
    )

    args = parser.parse_args()

    if args.command == "run":

        return run_command(
            args
        )

    elif args.command == "compare":

        return compare_command(
            args
        )

    elif args.command == "doctor":

        return doctor_command()

    else:

        parser.print_help()

        return 1


if __name__ == "__main__":

    sys.exit(
        main()
    )