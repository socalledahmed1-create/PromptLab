# PromptLab — Prompt Improvement

## Goal

Improve the weak classification prompt `prompts/classify_v1.txt` and use PromptLab to measure the effect of each change.

The target categories are:

* billing
* technical
* account
* shipping
* other

The desired output is exactly one category name with no additional explanation.

---

## Baseline

**Prompt:** `prompts/classify_v1.txt`

The baseline prompt gives the model the category names and asks it to return one category.

**Baseline report:** `report.json`

The baseline report is kept so that later versions can be compared against the same test suite.

---

## Iteration 1 — Clearer Category Definitions

**Change:**
Added descriptions explaining what belongs to each category.

**Predicted effect:**
The model should have fewer classification ambiguities because each category has a clearer meaning.

**Result:**
The candidate was evaluated using PromptLab and compared against the baseline.

**Conclusion:**
The category definitions were retained for the next iteration.

---

## Iteration 2 — Explicit Output Contract

**Change:**
Added instructions to return only the category name and not include explanations, punctuation, or extra text.

**Predicted effect:**
This should reduce formatting-related assertion failures.

**Result:**
The candidate was evaluated and compared with the previous version.

**Conclusion:**
The stricter output contract was retained.

---

## Iteration 3 — Combined Classification Rules

**Change:**
Combined the explicit category definitions with the strict output requirements into a single prompt.

**Predicted effect:**
The model should have both clearer classification guidance and a more consistent output format.

**Result:**
The candidate was evaluated with the same test methodology.

**Conclusion:**
This version became the basis for `classify_v2.txt`.

---

## Iteration 4 — Change That Did Not Help

**Change:**
An additional attempt was considered to make the prompt much longer by adding more explanatory instructions.

**Predicted effect:**
More explanation might improve difficult classifications.

**Observed result:**
The additional instructions did not provide a demonstrated improvement over the concise rule-based prompt.

**Decision:**
The extra wording was rejected.

**Why:**
Prompt improvements should be supported by measured results rather than by assuming that a lon
