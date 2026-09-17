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

VALID_FINISH_VALUES = {
    "stop",
    "length",
    "refusal",
}

MAX_FAILURE_OUTPUT = 500


def token_count(text):
    """Project token rule: ceil(len(text) / 4)."""
    if not isinstance(text, str):
        text = str(text)

    return math.ceil(len(text) / 4)


def prompt_hash(prompt_bytes):
    """First 12 hexadecimal characters of SHA-256."""
    return hashlib.sha256(prompt_bytes).hexdigest()[:12]


def read_json_file(path, description):
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"{description} file not found: {path}"
        )

    if not path.is_file():
        raise OSError(
            f"{description} path is not a file: {path}"
        )

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Malformed {description.lower()} JSON: {error}"
        )


def resolve_suite_path(suite_path, relative_path):
    """
    Resolve a path relative to the suite file.

    This is used for case input files because the specification
    defines input paths as relative to the suite file.
    """
    suite_dir = Path(suite_path).resolve().parent
    return (suite_dir / relative_path).resolve()


def resolve_prompt_path(suite_path, prompt_file):
    """
    Resolve prompt files.

    Prompt paths in the project suites use paths such as:
        prompts/classify_v1.txt

    Since the suite itself lives inside:
        suites/

    first try the suite directory, then fall back to the
    project root. This supports both path styles safely.
    """
    suite_path = Path(suite_path).resolve()
    suite_dir = suite_path.parent

    # First: path relative to suite directory.
    suite_relative = (suite_dir / prompt_file).resolve()

    if suite_relative.exists():
        return suite_relative

    # Second: path relative to project root.
    project_root = suite_dir.parent
    project_relative = (project_root / prompt_file).resolve()

    return project_relative


def find_project_root(start_path=None):
    """
    Find the project root containing promptlab.py.

    Falls back to the current working directory.
    """
    if start_path is not None:
        current = Path(start_path).resolve()

        if current.is_file():
            current = current.parent

        for directory in [current, *current.parents]:
            if (directory / "promptlab.py").exists():
                return directory

    current_directory = Path.cwd()

    for directory in [
        current_directory,
        *current_directory.parents,
    ]:
        if (directory / "promptlab.py").exists():
            return directory

    return current_directory


def load_suite(suite_path):
    suite_path = Path(suite_path)

    if not suite_path.exists():
        raise FileNotFoundError(
            f"Suite file not found: {suite_path}"
        )

    if not suite_path.is_file():
        raise OSError(
            f"Suite path is not a file: {suite_path}"
        )

    try:
        with open(
            suite_path,
            "r",
            encoding="utf-8",
        ) as file:
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

    if not isinstance(suite["name"], str):
        raise ValueError(
            "Suite 'name' must be a string."
        )

    if not isinstance(suite["prompt_file"], str):
        raise ValueError(
            "Suite 'prompt_file' must be a string."
        )

    if not isinstance(suite["model"], dict):
        raise ValueError(
            "Suite 'model' must be an object."
        )

    model = suite["model"]

    if "temperature" in model:
        if not isinstance(
            model["temperature"],
            (int, float),
        ):
            raise ValueError(
                "Suite 'model.temperature' must be a number."
            )

        if model["temperature"] < 0:
            raise ValueError(
                "Suite 'model.temperature' cannot be negative."
            )

    if "max_tokens" in model:
        if (
            not isinstance(model["max_tokens"], int)
            or isinstance(model["max_tokens"], bool)
            or model["max_tokens"] < 1
        ):
            raise ValueError(
                "Suite 'model.max_tokens' must be an integer greater than 0."
            )

    if (
        not isinstance(suite["runs"], int)
        or isinstance(suite["runs"], bool)
        or suite["runs"] < 1
    ):
        raise ValueError(
            "Suite 'runs' must be an integer greater than 0."
        )

    if not isinstance(suite["cases"], list):
        raise ValueError(
            "Suite 'cases' must be a list."
        )

    for case_index, case in enumerate(suite["cases"]):
        if not isinstance(case, dict):
            raise ValueError(
                f"Case {case_index + 1} must be a JSON object."
            )

        for field in [
            "id",
            "input",
            "assert",
        ]:
            if field not in case:
                raise ValueError(
                    f"Case {case_index + 1} is missing required field: {field}"
                )

        if not isinstance(case["id"], str):
            raise ValueError(
                f"Case {case_index + 1} 'id' must be a string."
            )

        case_input = case["input"]

        if not isinstance(
            case_input,
            (str, dict),
        ):
            raise ValueError(
                f"Case {case['id']} 'input' must be a string or object."
            )

        if isinstance(case_input, dict):
            if set(case_input.keys()) != {"file"}:
                raise ValueError(
                    f"Case {case['id']} input object must contain only 'file'."
                )

            if not isinstance(
                case_input["file"],
                str,
            ):
                raise ValueError(
                    f"Case {case['id']} input.file must be a string."
                )

        if not isinstance(
            case["assert"],
            list,
        ):
            raise ValueError(
                f"Assertions for case {case['id']} must be a list."
            )

        for assertion_index, assertion in enumerate(
            case["assert"]
        ):
            if not isinstance(
                assertion,
                dict,
            ):
                raise ValueError(
                    f"Invalid assertion in case {case['id']} "
                    f"at index {assertion_index}."
                )

            if "type" not in assertion:
                raise ValueError(
                    f"Assertion in case {case['id']} "
                    f"is missing 'type'."
                )

            assertion_type = assertion["type"]

            if assertion_type not in SUPPORTED_ASSERTIONS:
                raise ValueError(
                    f"Unsupported assertion '{assertion_type}' "
                    f"in case {case['id']}."
                )

            validate_assertion(
                assertion,
                case["id"],
            )

    return suite


def validate_assertion(assertion, case_id):
    assertion_type = assertion["type"]

    if assertion_type in {
        "contains",
        "not_contains",
    }:
        if "value" not in assertion:
            raise ValueError(
                f"Assertion '{assertion_type}' in case {case_id} "
                f"requires 'value'."
            )

        if not isinstance(
            assertion["value"],
            str,
        ):
            raise ValueError(
                f"Assertion '{assertion_type}' in case {case_id} "
                f"'value' must be a string."
            )

        if "ignore_case" in assertion:
            if not isinstance(
                assertion["ignore_case"],
                bool,
            ):
                raise ValueError(
                    f"Assertion '{assertion_type}' in case {case_id} "
                    f"'ignore_case' must be true or false."
                )

    elif assertion_type == "equals":
        if "value" not in assertion:
            raise ValueError(
                f"Assertion 'equals' in case {case_id} "
                f"requires 'value'."
            )

        if not isinstance(
            assertion["value"],
            str,
        ):
            raise ValueError(
                f"Assertion 'equals' in case {case_id} "
                f"'value' must be a string."
            )

        if "normalize" in assertion:
            if not isinstance(
                assertion["normalize"],
                bool,
            ):
                raise ValueError(
                    f"Assertion 'equals' in case {case_id} "
                    f"'normalize' must be true or false."
                )

    elif assertion_type == "matches":
        if "pattern" not in assertion:
            raise ValueError(
                f"Assertion 'matches' in case {case_id} "
                f"requires 'pattern'."
            )

        if not isinstance(
            assertion["pattern"],
            str,
        ):
            raise ValueError(
                f"Assertion 'matches' in case {case_id} "
                f"'pattern' must be a string."
            )

        try:
            re.compile(assertion["pattern"])

        except re.error as error:
            raise ValueError(
                f"Invalid regex in case {case_id}: {error}"
            )

    elif assertion_type == "json_field_equals":
        if "field" not in assertion:
            raise ValueError(
                f"Assertion 'json_field_equals' in case {case_id} "
                f"requires 'field'."
            )

        if "value" not in assertion:
            raise ValueError(
                f"Assertion 'json_field_equals' in case {case_id} "
                f"requires 'value'."
            )

        if not isinstance(
            assertion["field"],
            str,
        ):
            raise ValueError(
                f"Assertion 'json_field_equals' in case {case_id} "
                f"'field' must be a string."
            )

    elif assertion_type == "max_tokens":
        if "value" not in assertion:
            raise ValueError(
                f"Assertion 'max_tokens' in case {case_id} "
                f"requires 'value'."
            )

        if (
            not isinstance(
                assertion["value"],
                int,
            )
            or isinstance(
                assertion["value"],
                bool,
            )
            or assertion["value"] < 0
        ):
            raise ValueError(
                f"Assertion 'max_tokens' in case {case_id} "
                f"'value' must be a non-negative integer."
            )

    elif assertion_type == "finish_is":
        if "value" not in assertion:
            raise ValueError(
                f"Assertion 'finish_is' in case {case_id} "
                f"requires 'value'."
            )

        if assertion["value"] not in VALID_FINISH_VALUES:
            raise ValueError(
                f"Assertion 'finish_is' in case {case_id} "
                f"'value' must be one of: stop, length, refusal."
            )


def load_prompt(prompt_path):
    path = Path(prompt_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {path}"
        )

    if not path.is_file():
        raise OSError(
            f"Prompt path is not a file: {path}"
        )

    try:
        prompt_bytes = path.read_bytes()

    except OSError as error:
        raise OSError(
            f"Could not read prompt file: {error}"
        )

    try:
        prompt_text = prompt_bytes.decode("utf-8")

    except UnicodeDecodeError as error:
        raise ValueError(
            f"Prompt file is not valid UTF-8: {error}"
        )

    return prompt_text, prompt_bytes


def load_input(suite_path, case):
    case_input = case["input"]

    if isinstance(case_input, str):
        return case_input

    input_file = case_input["file"]

    input_path = resolve_suite_path(
        suite_path,
        input_file,
    )

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found for case {case['id']}: {input_file}"
        )

    if not input_path.is_file():
        raise OSError(
            f"Input path is not a file for case {case['id']}: {input_file}"
        )

    try:
        return input_path.read_text(
            encoding="utf-8"
        )

    except OSError as error:
        raise OSError(
            f"Could not read input file for case {case['id']}: {error}"
        )


def truncate_output(output):
    if not isinstance(
        output,
        str,
    ):
        output = str(output)

    if len(output) <= MAX_FAILURE_OUTPUT:
        return output

    return (
        output[:MAX_FAILURE_OUTPUT]
        + "... [truncated]"
    )


def normalize_text(text):
    return " ".join(
        text.strip().split()
    )


def get_json_field(data, dotted_path):
    """Resolve dotted JSON paths such as user.profile.category."""
    current = data

    for part in dotted_path.split("."):
        if isinstance(
            current,
            dict,
        ):
            if part not in current:
                return False, None

            current = current[part]

        elif isinstance(
            current,
            list,
        ):
            try:
                index = int(part)

            except ValueError:
                return False, None

            if index < 0 or index >= len(current):
                return False, None

            current = current[index]

        else:
            return False, None

    return True, current


def check_assertion(assertion, response):
    """Evaluate one assertion using the required suite schema."""
    assertion_type = assertion["type"]

    output = response.get(
        "output",
        "",
    )

    if not isinstance(
        output,
        str,
    ):
        output = str(output)

    if assertion_type == "contains":
        expected = assertion["value"]

        if assertion.get(
            "ignore_case",
            False,
        ):
            return expected.lower() in output.lower()

        return expected in output

    if assertion_type == "not_contains":
        expected = assertion["value"]

        if assertion.get(
            "ignore_case",
            False,
        ):
            return expected.lower() not in output.lower()

        return expected not in output

    if assertion_type == "equals":
        expected = assertion["value"]
        actual = output

        if assertion.get(
            "normalize",
            False,
        ):
            actual = normalize_text(actual)
            expected = normalize_text(expected)

        return actual == expected

    if assertion_type == "matches":
        pattern = assertion["pattern"]

        try:
            return re.search(
                pattern,
                output,
            ) is not None

        except re.error:
            return False

    if assertion_type == "json_valid":
        try:
            json.loads(output)
            return True

        except json.JSONDecodeError:
            return False

    if assertion_type == "json_field_equals":
        try:
            data = json.loads(output)

        except json.JSONDecodeError:
            return False

        found, actual_value = get_json_field(
            data,
            assertion["field"],
        )

        if not found:
            return False

        return actual_value == assertion["value"]

    if assertion_type == "max_tokens":
        actual_tokens = token_count(output)

        return (
            actual_tokens
            <= assertion["value"]
        )

    if assertion_type == "finish_is":
        return (
            response.get("finish")
            == assertion["value"]
        )

    return False


def run_model(
    prompt_file,
    user_input,
    model_settings,
    project_root,
    call_index=0,
):
    """Invoke the model only through subprocess."""
    start_time = time.perf_counter()

    model_path = (
        Path(project_root)
        / "stubmodel.py"
    )

    if not model_path.exists():
        raise RuntimeError(
            f"Model could not be invoked: "
            f"stubmodel.py not found at {model_path}"
        )

    command = [
        sys.executable,
        str(model_path),
        "--prompt",
        str(prompt_file),
        "--input",
        user_input,
    ]

    temperature = model_settings.get(
        "temperature"
    )

    if temperature is not None:
        command.extend(
            [
                "--temperature",
                str(temperature),
            ]
        )

    max_tokens = model_settings.get(
        "max_tokens"
    )

    if max_tokens is not None:
        command.extend(
            [
                "--max-tokens",
                str(max_tokens),
            ]
        )

    command.extend(
        [
            "--call-index",
            str(call_index),
        ]
    )

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(project_root),
        )

    except FileNotFoundError:
        raise RuntimeError(
            "Model could not be invoked: "
            "stubmodel.py not found."
        )

    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "Model process timed out."
        )

    except OSError as error:
        raise RuntimeError(
            f"Model could not be invoked: {error}"
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
                f"Model process exited with code "
                f"{result.returncode}."
            )

        raise RuntimeError(
            error_message
        )

    stdout = result.stdout.strip()

    if not stdout:
        raise RuntimeError(
            "Model returned empty output."
        )

    try:
        response = json.loads(stdout)

    except json.JSONDecodeError:
        raise RuntimeError(
            "Model returned invalid JSON."
        )

    if not isinstance(
        response,
        dict,
    ):
        raise RuntimeError(
            "Model response must be a JSON object."
        )

    if "output" not in response:
        raise RuntimeError(
            "Model response is missing 'output'."
        )

    if "finish" not in response:
        raise RuntimeError(
            "Model response is missing 'finish'."
        )

    return response, wall_ms


def run_case(
    suite_path,
    prompt_file,
    case,
    model_settings,
    project_root,
    run_number,
):
    user_input = load_input(
        suite_path,
        case,
    )

    response, wall_ms = run_model(
        prompt_file,
        user_input,
        model_settings,
        project_root,
        call_index=run_number - 1,
    )

    assertion_results = []

    for assertion in case["assert"]:
        assertion_type = assertion["type"]

        passed = check_assertion(
            assertion,
            response,
        )

        result = {
            "type": assertion_type,
            "passed": passed,
        }

        if not passed:
            result["expected"] = {
                key: value
                for key, value in assertion.items()
                if key != "type"
            }

            result["actual"] = truncate_output(
                response.get(
                    "output",
                    "",
                )
            )

        assertion_results.append(result)

    case_passed = all(
        result["passed"]
        for result in assertion_results
    )

    output = response.get(
        "output",
        "",
    )

    if not isinstance(
        output,
        str,
    ):
        output = str(output)

    input_tokens = token_count(
        user_input
    )

    output_tokens = token_count(
        output
    )

    return {
        "passed": case_passed,
        "response": response,
        "assertions": assertion_results,
        "tokens_in": input_tokens,
        "tokens_out": output_tokens,
        "wall_ms": wall_ms,
        "output": output,
        "finish": response.get("finish"),
    }


def calculate_case_report(
    case_id,
    run_reports,
):
    total_runs = len(run_reports)

    passed_runs = sum(
        1
        for run in run_reports
        if run["passed"]
    )

    failed_runs = (
        total_runs - passed_runs
    )

    if passed_runs == total_runs:
        status = "pass"

    elif failed_runs == total_runs:
        status = "fail"

    else:
        status = "flaky"

    pass_rate = (
        passed_runs / total_runs
        if total_runs
        else 0.0
    )

    total_output_tokens = sum(
        run["tokens_out"]
        for run in run_reports
    )

    tokens_out_avg = (
        total_output_tokens / total_runs
        if total_runs
        else 0
    )

    assertion_summary = {}

    for run in run_reports:
        for assertion in run["assertions"]:
            assertion_type = assertion["type"]

            if assertion_type not in assertion_summary:
                assertion_summary[
                    assertion_type
                ] = {
                    "type": assertion_type,
                    "passed": 0,
                    "failed": 0,
                }

            if assertion["passed"]:
                assertion_summary[
                    assertion_type
                ]["passed"] += 1

            else:
                assertion_summary[
                    assertion_type
                ]["failed"] += 1

    failures = []

    for run in run_reports:
        for assertion in run["assertions"]:
            if not assertion["passed"]:
                failures.append(
                    {
                        "run": run["run"],
                        "type": assertion["type"],
                        "expected": assertion.get(
                            "expected"
                        ),
                        "actual": assertion.get(
                            "actual"
                        ),
                    }
                )

    return {
        "id": case_id,
        "status": status,
        "pass_rate": round(
            pass_rate,
            4,
        ),
        "tokens_out_avg": round(
            tokens_out_avg,
            2,
        ),
        "assertions": list(
            assertion_summary.values()
        ),
        "failures": failures,
    }


def print_human_report(report):
    totals = report["totals"]

    print(
        "=" * 50,
        file=sys.stderr,
    )

    print(
        "PROMPTLAB REPORT",
        file=sys.stderr,
    )

    print(
        "=" * 50,
        file=sys.stderr,
    )

    print(
        f"Suite: {report['suite']}",
        file=sys.stderr,
    )

    print(
        f"Prompt: {report['prompt_file']}",
        file=sys.stderr,
    )

    print(
        f"Runs per case: {report['runs']}",
        file=sys.stderr,
    )

    print(
        f"Cases: {totals['cases']}",
        file=sys.stderr,
    )

    print(
        f"Passed: {totals['passed']}",
        file=sys.stderr,
    )

    print(
        f"Failed: {totals['failed']}",
        file=sys.stderr,
    )

    print(
        f"Flaky: {totals['flaky']}",
        file=sys.stderr,
    )

    print(
        f"Tokens in: {totals['tokens_in']}",
        file=sys.stderr,
    )

    print(
        f"Tokens out: {totals['tokens_out']}",
        file=sys.stderr,
    )

    print(
        f"Wall time: {totals['wall_ms']} ms",
        file=sys.stderr,
    )

    worst_cases = sorted(
        report["cases"],
        key=lambda case: (
            len(case["failures"]),
            -case["pass_rate"],
        ),
        reverse=True,
    )

    print(
        file=sys.stderr
    )

    print(
        "Worst offenders:",
        file=sys.stderr,
    )

    shown = 0

    for case in worst_cases:
        if (
            case["status"] != "pass"
            or case["failures"]
        ):
            print(
                f"  {case['id']}: "
                f"{case['status']} "
                f"(pass rate {case['pass_rate']})",
                file=sys.stderr,
            )

            shown += 1

            if shown >= 5:
                break

    if shown == 0:
        print(
            "  None",
            file=sys.stderr,
        )

    print(
        "=" * 50,
        file=sys.stderr,
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

    if args.runs is not None:
        if args.runs < 1:
            print(
                "ERROR: --runs must be greater than 0."
            )
            return 1

        runs = args.runs

    else:
        runs = suite["runs"]

    suite_path = Path(
        args.suite
    ).resolve()

    project_root = find_project_root(
        suite_path
    )

    prompt_path = resolve_prompt_path(
        suite_path,
        suite["prompt_file"],
    )

    try:
        prompt, prompt_bytes = load_prompt(
            prompt_path
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

    # Keep prompt referenced so the prompt is explicitly loaded.
    _ = prompt

    model_settings = suite["model"]

    total_cases = len(
        suite["cases"]
    )

    passed_cases = 0
    failed_cases = 0
    flaky_cases = 0

    total_tokens_in = 0
    total_tokens_out = 0
    total_wall_ms = 0.0

    case_reports = []

    for case in suite["cases"]:
        run_reports = []

        for run_number in range(
            1,
            runs + 1,
        ):
            try:
                result = run_case(
                    suite_path,
                    prompt_path,
                    case,
                    model_settings,
                    project_root,
                    run_number,
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

            except RuntimeError as error:
                print(
                    f"ERROR: Model invocation failed: {error}"
                )
                return 3

            run_reports.append(
                {
                    "run": run_number,
                    "passed": result["passed"],
                    "output": result["output"],
                    "finish": result["finish"],
                    "tokens_in": result["tokens_in"],
                    "tokens_out": result["tokens_out"],
                    "wall_ms": round(
                        result["wall_ms"],
                        2,
                    ),
                    "assertions": result["assertions"],
                }
            )

            total_tokens_in += result[
                "tokens_in"
            ]

            total_tokens_out += result[
                "tokens_out"
            ]

            total_wall_ms += result[
                "wall_ms"
            ]

        case_report = calculate_case_report(
            case["id"],
            run_reports,
        )

        case_reports.append(
            case_report
        )

        if case_report["status"] == "pass":
            passed_cases += 1

        elif case_report["status"] == "fail":
            failed_cases += 1

        else:
            flaky_cases += 1

    report = {
        "suite": suite["name"],
        "prompt_file": suite["prompt_file"],
        "prompt_hash": prompt_hash(
            prompt_bytes
        ),
        "runs": runs,
        "model": model_settings,
        "totals": {
            "cases": total_cases,
            "passed": passed_cases,
            "failed": failed_cases,
            "flaky": flaky_cases,
            "tokens_in": total_tokens_in,
            "tokens_out": total_tokens_out,
            "wall_ms": round(
                total_wall_ms,
                2,
            ),
        },
        "cases": case_reports,
    }

    if args.out:
        output_path = Path(
            args.out
        )

        try:
            output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with open(
                output_path,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    report,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

                file.write("\n")

        except OSError as error:
            print(
                f"ERROR: Could not write report: {error}"
            )
            return 4

    else:
        print(
            json.dumps(
                report,
                indent=2,
                ensure_ascii=False,
            )
        )

    if args.report:
        print_human_report(
            report
        )

    if (
        failed_cases > 0
        or flaky_cases > 0
    ):
        return 2

    return 0


def load_report(report_path):
    path = Path(
        report_path
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Report file not found: {path}"
        )

    if not path.is_file():
        raise OSError(
            f"Report path is not a file: {path}"
        )

    try:
        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:
            report = json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Malformed report JSON: {error}"
        )

    if not isinstance(
        report,
        dict,
    ):
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


def get_case_map(report):
    return {
        case["id"]: case
        for case in report.get(
            "cases",
            [],
        )
    }


def case_pass_rate(case):
    value = case.get(
        "pass_rate"
    )

    if isinstance(
        value,
        (int, float),
    ):
        return float(value)

    status = case.get(
        "status"
    )

    if status == "pass":
        return 1.0

    return 0.0


def get_case_tokens(case):
    average = case.get(
        "tokens_out_avg",
        0,
    )

    return average


def classify_existing_case(
    baseline_case,
    candidate_case,
):
    baseline_rate = case_pass_rate(
        baseline_case
    )

    candidate_rate = case_pass_rate(
        candidate_case
    )

    if candidate_rate < baseline_rate:
        return "regressed"

    if candidate_rate > baseline_rate:
        return "improved"

    return "unchanged"


def percentage_change(old, new):
    if old == 0:
        if new == 0:
            return 0.0

        return None

    return (
        (new - old) / old
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

    baseline_cases = get_case_map(
        baseline
    )

    candidate_cases = get_case_map(
        candidate
    )

    all_case_ids = sorted(
        set(baseline_cases)
        | set(candidate_cases)
    )

    comparisons = []

    regressed = 0
    improved = 0
    unchanged = 0
    new_cases = 0
    removed_cases = 0

    for case_id in all_case_ids:
        in_baseline = (
            case_id in baseline_cases
        )

        in_candidate = (
            case_id in candidate_cases
        )

        if not in_baseline:
            new_cases += 1

            candidate_case = candidate_cases[
                case_id
            ]

            comparisons.append(
                {
                    "id": case_id,
                    "classification": "new",
                    "baseline_status": None,
                    "candidate_status": candidate_case.get(
                        "status"
                    ),
                    "baseline_pass_rate": None,
                    "candidate_pass_rate": case_pass_rate(
                        candidate_case
                    ),
                    "token_delta": get_case_tokens(
                        candidate_case
                    ),
                }
            )

            continue

        if not in_candidate:
            removed_cases += 1

            baseline_case = baseline_cases[
                case_id
            ]

            comparisons.append(
                {
                    "id": case_id,
                    "classification": "removed",
                    "baseline_status": baseline_case.get(
                        "status"
                    ),
                    "candidate_status": None,
                    "baseline_pass_rate": case_pass_rate(
                        baseline_case
                    ),
                    "candidate_pass_rate": None,
                    "token_delta": -get_case_tokens(
                        baseline_case
                    ),
                }
            )

            continue

        baseline_case = baseline_cases[
            case_id
        ]

        candidate_case = candidate_cases[
            case_id
        ]

        classification = classify_existing_case(
            baseline_case,
            candidate_case,
        )

        if classification == "regressed":
            regressed += 1

        elif classification == "improved":
            improved += 1

        else:
            unchanged += 1

        baseline_tokens = get_case_tokens(
            baseline_case
        )

        candidate_tokens = get_case_tokens(
            candidate_case
        )

        comparisons.append(
            {
                "id": case_id,
                "classification": classification,
                "baseline_status": baseline_case.get(
                    "status"
                ),
                "candidate_status": candidate_case.get(
                    "status"
                ),
                "baseline_pass_rate": case_pass_rate(
                    baseline_case
                ),
                "candidate_pass_rate": case_pass_rate(
                    candidate_case
                ),
                "token_delta": (
                    candidate_tokens
                    - baseline_tokens
                ),
            }
        )

    baseline_totals = baseline.get(
        "totals",
        {},
    )

    candidate_totals = candidate.get(
        "totals",
        {},
    )

    baseline_input_tokens = baseline_totals.get(
        "tokens_in",
        0,
    )

    candidate_input_tokens = candidate_totals.get(
        "tokens_in",
        0,
    )

    input_token_delta = (
        candidate_input_tokens
        - baseline_input_tokens
    )

    input_token_percentage = percentage_change(
        baseline_input_tokens,
        candidate_input_tokens,
    )

    baseline_output_tokens = baseline_totals.get(
        "tokens_out",
        0,
    )

    candidate_output_tokens = candidate_totals.get(
        "tokens_out",
        0,
    )

    output_token_delta = (
        candidate_output_tokens
        - baseline_output_tokens
    )

    output_token_percentage = percentage_change(
        baseline_output_tokens,
        candidate_output_tokens,
    )

    baseline_total_tokens = baseline_output_tokens
    candidate_total_tokens = candidate_output_tokens
    total_token_delta = output_token_delta
    token_percentage = output_token_percentage

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
            "Baseline and candidate use different model settings."
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
                    2,
                )
                if token_percentage is not None
                else None
            ),
            "input": {
                "baseline": baseline_input_tokens,
                "candidate": candidate_input_tokens,
                "delta": input_token_delta,
                "percentage_change": (
                    round(
                        input_token_percentage,
                        2,
                    )
                    if input_token_percentage is not None
                    else None
                ),
            },
            "output": {
                "baseline": baseline_output_tokens,
                "candidate": candidate_output_tokens,
                "delta": output_token_delta,
                "percentage_change": (
                    round(
                        output_token_percentage,
                        2,
                    )
                    if output_token_percentage is not None
                    else None
                ),
            },
        },
        "warnings": warnings,
        "cases": comparisons,
    }

    output_path = Path(
        args.out
    )

    try:
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with open(
            output_path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                diff,
                file,
                indent=2,
                ensure_ascii=False,
            )

            file.write("\n")

    except OSError as error:
        print(
            f"ERROR: Could not write diff: {error}"
        )
        return 4

    print(
        "=" * 50
    )

    print(
        "PROMPTLAB COMPARE"
    )

    print(
        "=" * 50
    )

    print(
        f"Baseline: {args.baseline}"
    )

    print(
        f"Candidate: {args.candidate}"
    )

    print()

    print(
        f"Regressed: {regressed}"
    )

    print(
        f"Improved: {improved}"
    )

    print(
        f"Unchanged: {unchanged}"
    )

    print(
        f"New: {new_cases}"
    )

    print(
        f"Removed: {removed_cases}"
    )

    print()

    print(
        f"Baseline input tokens: {baseline_input_tokens}"
    )
    print(
        f"Candidate input tokens: {candidate_input_tokens}"
    )

    print(
        f"Input token delta: {input_token_delta}"
    )

    if input_token_percentage is None:
        print(
            "Input token change: N/A"
        )
    else:
        print(
            f"Input token change: {input_token_percentage:.2f}%"
        )

    print()

    print(
        f"Baseline output tokens: {baseline_output_tokens}"
    )

    print(
        f"Candidate output tokens: {candidate_output_tokens}"
    )

    print(
        f"Output token delta: {output_token_delta}"
    )

    if output_token_percentage is None:
        print(
            "Output token change: N/A"
        )
    else:
        print(
            f"Output token change: {output_token_percentage:.2f}%"
        )

    if warnings:
        print()
        print(
            "Warnings:"
        )

        for warning in warnings:
            print(
                f"- {warning}"
            )

    print()

    print(
        f"Diff written to: {output_path}"
    )

    print(
        "=" * 50
    )

    return 0


def doctor_command():
    print(
        "=" * 50
    )

    print(
        "PROMPTLAB DOCTOR"
    )

    print(
        "=" * 50
    )

    problems = 0

    project_root = find_project_root()

    print()
    print(
        "[1/5] Python version"
    )

    major = sys.version_info.major
    minor = sys.version_info.minor

    print(
        f"      Python: {major}.{minor}"
    )

    if major > 3 or (
        major == 3
        and minor >= 10
    ):
        print(
            "      PASS"
        )

    else:
        print(
            "      FAIL: Python 3.10+ required."
        )

        problems += 1

    print()
    print(
        "[2/5] Model binary"
    )

    model_path = (
        project_root
        / "stubmodel.py"
    )

    if not model_path.exists():
        print(
            "      FAIL: stubmodel.py not found."
        )

        problems += 1

    else:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(model_path),
                    "--prompt",
                    "Doctor test prompt",
                    "--input",
                    "I cannot log into my account.",
                    "--temperature",
                    "0",
                    "--call-index",
                    "0",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(project_root),
            )

            if result.returncode != 0:
                print(
                    "      FAIL: Model process failed."
                )

                if result.stderr.strip():
                    print(
                        f"      {result.stderr.strip()}"
                    )

                problems += 1

            else:
                try:
                    response = json.loads(
                        result.stdout
                    )

                    if not isinstance(
                        response,
                        dict,
                    ):
                        raise ValueError(
                            "Response is not a JSON object."
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
                        "      Model reachable: PASS"
                    )

                    print(
                        "      Response valid: PASS"
                    )

                except (
                    json.JSONDecodeError,
                    ValueError,
                ) as error:
                    print(
                        "      FAIL: Invalid model response."
                    )

                    print(
                        f"      {error}"
                    )

                    problems += 1

        except subprocess.TimeoutExpired:
            print(
                "      FAIL: Model timed out."
            )

            problems += 1

    print()
    print(
        "[3/5] Suites"
    )

    suites_path = (
        project_root
        / "suites"
    )

    if not suites_path.exists():
        print(
            "      FAIL: suites folder not found."
        )

        problems += 1

    else:
        suite_files = sorted(
            suites_path.glob("*.json")
        )

        if not suite_files:
            print(
                "      FAIL: No JSON suites found."
            )

            problems += 1

        else:
            print(
                f"      Found {len(suite_files)} suite(s)."
            )

            for suite_file in suite_files:
                try:
                    load_suite(
                        suite_file
                    )

                    # Also verify that the prompt path resolves.
                    suite_data = load_suite(
                        suite_file
                    )

                    prompt_path = resolve_prompt_path(
                        suite_file,
                        suite_data["prompt_file"],
                    )

                    if not prompt_path.exists():
                        raise FileNotFoundError(
                            f"Prompt file not found: {prompt_path}"
                        )

                    print(
                        f"      PASS: {suite_file}"
                    )

                except (
                    FileNotFoundError,
                    OSError,
                    ValueError,
                ) as error:
                    print(
                        f"      FAIL: {suite_file}"
                    )

                    print(
                        f"            {error}"
                    )

                    problems += 1

    print()
    print(
        "[4/5] Assertion registry"
    )

    expected_assertions = {
        "contains",
        "not_contains",
        "equals",
        "matches",
        "json_valid",
        "json_field_equals",
        "max_tokens",
        "finish_is",
    }

    missing = sorted(
        expected_assertions
        - SUPPORTED_ASSERTIONS
    )

    if missing:
        print(
            "      FAIL: Missing:",
            ", ".join(missing),
        )

        problems += 1

    else:
        print(
            "      All 8 assertions registered."
        )

        print(
            "      PASS"
        )

    print()
    print(
        "[5/5] Project files"
    )

    required_files = [
        "promptlab.py",
        "stubmodel.py",
        "SPEC.md",
        "CLAUDE.md",
        "PROMPTS.md",
        "USAGE.md",
    ]

    missing_files = [
        filename
        for filename in required_files
        if not (
            project_root
            / filename
        ).exists()
    ]

    if missing_files:
        print(
            "      FAIL: Missing:",
            ", ".join(missing_files),
        )

        problems += 1

    else:
        print(
            "      Required project files found."
        )

        print(
            "      PASS"
        )

    print()
    print(
        "=" * 50
    )

    if problems == 0:
        print(
            "DOCTOR RESULT: PASS"
        )

        print(
            "PromptLab is healthy."
        )

        print(
            "=" * 50
        )

        return 0

    print(
        "DOCTOR RESULT: FAIL"
    )

    print(
        f"Problems found: {problems}"
    )

    print(
        "=" * 50
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
        required=True,
    )

    run_parser.add_argument(
        "--runs",
        type=int,
    )

    run_parser.add_argument(
        "--out",
    )

    run_parser.add_argument(
        "--report",
        action="store_true",
    )

    compare_parser = subparsers.add_parser(
        "compare"
    )

    compare_parser.add_argument(
        "--baseline",
        required=True,
    )

    compare_parser.add_argument(
        "--candidate",
        required=True,
    )

    compare_parser.add_argument(
        "--out",
        required=True,
    )

    subparsers.add_parser(
        "doctor"
    )

    args = parser.parse_args()

    if args.command == "run":
        return run_command(
            args
        )

    if args.command == "compare":
        return compare_command(
            args
        )

    if args.command == "doctor":
        return doctor_command()

    parser.print_help()

    return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )