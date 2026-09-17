# PromptLab Specification

## 1. Project Overview

PromptLab is a command-line evaluation tool for testing prompt/model behavior against JSON test suites.

It must:

- Execute a model program as a subprocess.
- Run one or more test cases from a JSON suite.
- Support repeated runs.
- Evaluate predefined assertions.
- Detect passed, failed, and flaky cases.
- Generate machine-readable JSON reports.
- Compare baseline and candidate reports.
- Provide a doctor command for project health checks.
- Return documented exit codes.
- Be testable using Python unittest.

The initial model implementation is `stubmodel.py`.

PromptLab must execute `stubmodel.py` as a subprocess and must not import or reimplement the model's classification logic.

---

# 2. Command Line Interface

PromptLab must support these commands:

```text
promptlab run --suite <file> [--runs N] [--out report.json] [--report]

promptlab compare --baseline <report.json> --candidate <report.json> --out diff.json

promptlab doctor