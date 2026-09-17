# PromptLab Usage Guide

PromptLab is a command-line harness for evaluating prompts against JSON test suites.

## Run

Run a suite with:

`python promptlab.py run --suite suites/smoke.json`

Use `--runs N` to repeat every case N times:

`python promptlab.py run --suite suites/smoke.json --runs 10`

Use `--out report.json` to write the JSON report to a file.

Use `--report` to print a short human-readable summary.

## Compare

Compare two reports:

`python promptlab.py compare --baseline report.json --candidate report_v2.json --out diff.json`

Use this after changing a prompt to detect regressions, improvements, unchanged cases, new cases, and removed cases.

## Doctor

Run:

`python promptlab.py doctor`

Use this before evaluation to check Python, model availability, suites, assertions, and required project files.

## Exit Codes

0 = all cases passed.

1 = bad usage or malformed suite.

2 = one or more test cases failed.

3 = the model could not be invoked or returned an invalid response.

4 = a suite or report file was unreadable.

An exit code of 2 is a test result, not a tool error.

## Assertions

PromptLab supports:

* contains
* not_contains
* equals
* matches
* json_valid
* json_field_equals
* max_tokens
* finish_is

## When to Use

Use PromptLab when a prompt needs repeatable evaluation, regression testing, or comparison between prompt versions.

Do not assume that a prompt is better from a few example outputs. Run a representative test suite and compare reports.

## Agent Instructions

An automated agent should run `doctor` first, then execute the required suite. It should inspect the exit code and report rather than treating failed test cases as a tool crash.

When comparing prompt versions, inspect regressions as well as improvements and review token-cost changes.

Do not modify the test suite merely to make a prompt pass.
