# PromptLab Context for Claude Code

## Project Goal

Build and maintain PromptLab, a Python standard-library-only command-line harness for evaluating prompts against JSON test suites.

## Non-Negotiable Requirements

* Use Python 3.10+.
* Use only the Python standard library.
* Do not use network access.
* Invoke the model as a subprocess.
* Do not import, copy, reimplement, or predict the behavior of stubmodel.py.
* Preserve the exact CLI contract.
* Preserve the required exit-code meanings.
* Support all eight assertion types.
* Support repeated runs and flaky classification.
* Produce deterministic reports apart from isolated timing fields.
* Compare baseline and candidate reports and detect regressions.
* Keep failure information useful for debugging.
* Do not remove existing functionality when adding features.

## Development Rules

Read SPEC.md before making implementation changes.

When a design decision changes, update SPEC.md before changing the code.

Run the unit tests after meaningful implementation changes:

`python -m unittest discover -s tests -v`

Run the smoke suite after implementation changes:

`python promptlab.py run --suite suites/smoke.json --out report.json --report`

Run diagnostics:

`python promptlab.py doctor`

## Prompt Engineering

Prompt changes must be evaluated using PromptLab rather than judged only by inspecting a few outputs.

Keep baseline and candidate reports so changes can be measured.

Document prompt experiments in IMPROVEMENT.md and important prompting decisions in PROMPTS.md.

## Code Quality

Prefer small, clear standard-library functions.

Expected user errors must produce readable messages and the correct exit code instead of Python tracebacks.

Do not silently change the suite or report schema.

Before submission, verify that the project works from a fresh clone and that the required documentation files exist.

## Git Discipline

The first commit must contain only SPEC.md.

Before committing implementation changes, make sure SPEC.md reflects the current design decisions.
