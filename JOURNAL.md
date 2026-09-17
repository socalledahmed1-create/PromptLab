# PromptLab — Development Journal

## 1. Three decisions and what I rejected

### Decision 1: Subprocess model execution

I chose to invoke the model through a subprocess instead of importing or copying model logic.

**Rejected:** Importing stubmodel.py or reproducing its classification behavior inside PromptLab.

**Reason:** The harness must remain independent of the model implementation.

### Decision 2: Strict flaky classification

I chose this policy:

* 100% pass rate = pass
* 0% pass rate = fail
* Between 0% and 100% = flaky

**Rejected:** Treating a majority of passing runs as a pass.

**Reason:** A test that is not reproducible should be visible as flaky.

### Decision 3: Strict JSON validation

I chose to treat `json_valid` as valid only when the complete model output is directly parseable as JSON.

**Rejected:** Automatically stripping Markdown fences before parsing.

**Reason:** This keeps the assertion semantics predictable and makes the fenced-JSON decision explicit in the specification.

---

## 2. Hardest bug and root cause

The most difficult part was making the runner handle repeated model executions while still producing useful per-case results.

The root cause was that a single case can have different assertion results across multiple runs. The runner therefore has to retain individual run results before calculating the final case status and pass rate.

The fix was to evaluate every run separately and aggregate those results into the case-level status, assertion counts, and pass rate.

---

## 3. Something Claude Code confidently got wrong and how I caught it

During development, an implementation can appear correct because the visible smoke tests pass while still differing from the exact hackathon contract.

I caught this by comparing the implementation against the original hackathon brief and checking the required suite schema, report schema, assertions, exit codes, and documentation requirements instead of relying only on successful local tests.

This showed that passing existing tests does not prove complete compliance with the specification.

---

## 4. What I would do differently with four more hours

I would spend more time on the original starter materials and hidden-test-style cases before polishing the documentation.

In particular, I would:

1. Verify the complete 63-ticket corpus.
2. Test every malformed-input and failure scenario.
3. Run at least four measured prompt-improvement iterations.
4. Test deterministic reports more strictly.
5. Test comparison behavior with changed pass rates, model settings, and suites.
6. Run the complete project from a fresh clone before submission.

---

## 5. Who did what

The project implementation, testing, documentation, Gi

