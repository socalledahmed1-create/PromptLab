# PromptLab — Prompt Improvement

## Goal

Improve the weak classification prompt `prompts/classify_v1.txt` and use PromptLab to measure the effect of each change.

The target categories are:

- billing
- technical
- account
- shipping
- other

The desired output is exactly one category name with no additional explanation.

## Evaluation Method

The prompt versions were evaluated using the PromptLab runner.

The current local smoke corpus contains 5 tickets. Each version was executed with:

- Runs per case: 1
- Temperature: 0.0
- Maximum output tokens: 256

The comparison uses pass rate, case status, token usage, and PromptLab's case-level comparison.

Important limitation: the supplied local `stubmodel.py` does not use the prompt file when classifying tickets. Therefore, prompt changes cannot produce a demonstrated classification improvement with this local model. Results below are reported exactly as measured rather than claiming an improvement that was not observed.

---

## Baseline

**Prompt:** `prompts/classify_v1.txt`

**Report:** `report.json`

Baseline results:

- Cases: 5
- Passed: 5
- Failed: 0
- Flaky: 0
- Input tokens: 51
- Output tokens: 11
- Overall case pass rate: 100%

The baseline prompt identifies the five allowed categories and instructs the model to return only the category name.

---

## Iteration 1 — Clearer Category Definitions

### Change

Added descriptions explaining what belongs to each category.

Examples include billing-related charges and subscriptions, technical errors and crashes, account access problems, and shipping or delivery problems.

### Predicted Effect

Clearer category definitions should reduce ambiguity when a ticket could potentially belong to more than one category.

### Measurement

The candidate was evaluated with PromptLab against the smoke suite.

### Result

The measured smoke-suite result remained:

- Passed: 5/5
- Failed: 0
- Flaky: 0
- Pass rate: 100%

No measurable improvement was observed because the current local stub model does not use the prompt text for its classification logic.

### Decision

The clearer category definitions were retained because they make the prompt specification more explicit, but they are not claimed as a measured performance improvement.

---

## Iteration 2 — Explicit Output Contract

### Change

Added explicit instructions to:

- return only the category name
- avoid explanations
- avoid punctuation
- avoid additional text

### Predicted Effect

The stricter output contract should reduce formatting-related failures when used with a model that follows the prompt.

### Measurement

The candidate was evaluated using the same PromptLab methodology.

### Result

The measured smoke-suite result remained:

- Passed: 5/5
- Failed: 0
- Flaky: 0
- Input tokens: 51
- Output tokens: 11

No measurable change was observed on the supplied local stub model.

### Decision

The explicit output contract was retained because it clearly defines the required output format.

---

## Iteration 3 — Combined Classification Rules

### Change

Combined the category definitions and strict output requirements into one prompt.

This produced:

`prompts/classify_v2.txt`

### Predicted Effect

The combined prompt should provide both clearer classification guidance and a more consistent output contract.

### Measurement

Baseline:

`report.json`

Candidate:

`report_v2.json`

Comparison:

`diff.json`

### Actual Result

PromptLab reported:

- Regressed: 0
- Improved: 0
- Unchanged: 5
- New: 0
- Removed: 0

Token comparison:

- Input tokens: 51 → 51
- Input token delta: 0
- Input token change: 0.00%
- Output tokens: 11 → 11
- Output token delta: 0
- Output token change: 0.00%

Both versions passed all 5 smoke cases.

### Decision

The combined prompt was retained as `classify_v2.txt`, but the result is described as **unchanged**, not as a measured improvement.

---

## Iteration 4 — Change That Did Not Help

### Change

Considered adding substantially more explanatory wording to the classification prompt.

The proposed change would make the prompt longer and provide additional explanations around the category rules.

### Predicted Effect

The additional explanation might help on difficult or ambiguous tickets.

### Measurement

No measurable improvement was demonstrated on the available local evaluation setup.

The existing v2 prompt already produced:

- 5/5 passed
- 100% pass rate
- 51 input tokens
- 11 output tokens

The local stub model does not use the prompt text, so adding more prompt instructions cannot currently demonstrate a classification improvement.

### Decision

The additional wording was rejected.

### Why

Prompt changes should be supported by measured evidence. Making a prompt longer without measurable improvement would add complexity without demonstrated benefit.

---

## Final Assessment

The current PromptLab comparison shows that `classify_v2.txt` is **unchanged relative to the baseline on the available 5-ticket smoke corpus**.

The measured comparison is:

```text
Regressed: 0
Improved: 0
Unchanged: 5
New: 0
Removed: 0

Input tokens:
51 → 51
Delta: 0
Change: 0.00%

Output tokens:
11 → 11
Delta: 0
Change: 0.00%
---

## Evidence Files

- Baseline report: `report.json`
- Candidate report: `report_v2.json`
- Comparison: `diff.json`
- Baseline prompt: `prompts/classify_v1.txt`
- Candidate prompt: `prompts/classify_v2.txt`