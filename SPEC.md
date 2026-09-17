# PromptLab Specification

## 1. Goal

PromptLab is a Python 3.10+ command-line harness for testing prompts against repeatable JSON test suites.

It must:

* execute a model through a subprocess;
* evaluate assertions;
* support repeated runs;
* identify flaky cases;
* produce machine-readable reports;
* compare baseline and candidate reports;
* identify regressions and improvements;
* provide diagnostics through `doctor`;
* support self-improvement experiments.

The implementation uses only the Python standard library.

---

## 2. CLI Contract

```text
promptlab run     --suite <file> [--runs N] [--out report.json] [--report]
promptlab compare --baseline <report.json> --candidate <report.json> [--out diff.json]
promptlab doctor
```

Exit codes:

```text
0 = all cases passed
1 = bad usage or malformed suite
2 = one or more cases failed
3 = model could not be invoked
4 = suite or report unreadable
```

Exit code 2 represents a test result and is not a tool failure.

---

## 3. Assertion Evaluation Model

Every assertion is evaluated independently for every model run.

The eight supported assertion types are:

### contains

Pass when the output contains `value`.

Optional `ignore_case` controls case-sensitive comparison.

### not_contains

Pass when the output does not contain `value`.

Optional `ignore_case` controls case-sensitive comparison.

### equals

Pass when the complete output equals `value`.

If `normalize` is true, leading/trailing whitespace is stripped and consecutive whitespace is collapsed before comparison.

### matches

Pass when the regular expression in `pattern` finds a match in the output.

Invalid regular expressions are reported as user errors rather than causing a traceback.

### json_valid

Pass when the complete output is valid JSON.

### json_field_equals

Parse the output as JSON and resolve `field` as a dotted path.

For example:

```text
customer.address.city
```

resolves nested JSON objects.

The resolved value must equal `value`.

### max_tokens

Pass when `tokens_out <= value`.

Token counts use:

```text
ceil(len(text) / 4)
```

### finish_is

Pass when the model's finish value equals the requested value.

Allowed values are:

```text
stop
length
refusal
```

---

## 4. Fenced JSON Decision

PromptLab uses strict JSON semantics.

A Markdown-fenced JSON response is **not** considered valid JSON for `json_valid` or `json_field_equals`.

The harness does not automatically remove Markdown fences before parsing.

This keeps JSON assertions deterministic and makes the output-format requirement explicit in prompts.

---

## 5. Repeated Runs and Flaky Policy

Each case is executed once per requested run.

The `--runs N` command-line argument overrides the suite's configured run count.

Case status is determined using strict unanimity:

```text
pass   = every run passes
fail   = every run fails
flaky  = at least one run passes and at least one run fails
```

The case `pass_rate` is:

```text
number of passing runs / total runs
```

Therefore a pass rate such as 0.7 is classified as flaky, not pass.

Per-assertion statistics record the number of runs that passed and failed that assertion.

---

## 6. Failure Taxonomy

PromptLab distinguishes failures by source:

```text
suite_error
prompt_error
input_error
model_invocation_error
invalid_model_response
assertion_failure
report_error
```

Expected user-facing errors are reported as concise messages without Python tracebacks.

Assertion failures contain enough information to debug the result, including the assertion, actual output, and useful truncation.

---

## 7. Reports

A run report contains:

* suite name;
* prompt file;
* first 12 hexadecimal characters of the SHA-256 hash of prompt-file bytes;
* run count;
* model settings;
* total case/pass/fail/flaky counts;
* token totals;
* wall-clock time;
* per-case status;
* pass rate;
* average output tokens;
* per-assertion pass/fail counts;
* useful failure details.

Timing fields are isolated so deterministic temperature-zero reports can be compared without treating timing variation as a content change.

Without `--out`, the JSON report is written to stdout.

Human-readable reporting is written to stderr.

With `--report`, the human summary includes pass/fail/flaky counts, token totals, wall time, and worst offenders.

---

## 8. Comparison and Regression Definition

Every case is classified as one of:

```text
regressed
improved
unchanged
new
removed
```

New and removed cases are determined from case IDs.

For cases present in both reports:

```text
candidate pass_rate < baseline pass_rate -> regressed
candidate pass_rate > baseline pass_rate -> improved
candidate pass_rate == baseline pass_rate -> unchanged
```

A decrease from 1.0 to 0.9 is therefore a regression even if both cases have a passing status.

Comparison also reports:

* tokens-in delta;
* tokens-out delta;
* percentage changes for both.

Warnings are emitted when:

* baseline and candidate have the same prompt hash;
* suite names differ;
* model settings differ.

---

## 9. Model Isolation

PromptLab invokes the model as a subprocess using the required command-line contract.

PromptLab must not:

* import the model implementation;
* copy the model implementation;
* reimplement model behavior;
* predict model output.

This allows judges to replace the model binary while preserving the interface.

---

## 10. Doctor

`promptlab doctor` checks:

1. Python version;
2. model binary reachability and response;
3. discoverable suites;
4. registration of all eight assertion types.

Doctor is intended to be the first command run after cloning the repository.

---

## 11. Self-Improvement

The weak baseline prompt is:

```text
prompts/classify_v1.txt
```

The improved prompt is:

```text
prompts/classify_v2.txt
```

Prompt changes must be evaluated with PromptLab rather than judged only by reading outputs.

The improvement record must contain at least four iterations, including at least one change that did not help.

---

## 12. Tests

The project uses Python `unittest`.

Tests cover:

* assertion evaluation;
* suite parsing;
* flaky classification;
* comparison logic.

The required command is:

```text
python -m unittest
```

It must pass from a fresh clone.

---

## 13. Definition of Done

PromptLab is considered complete when:

* the required CLI works;
* all eight assertio
