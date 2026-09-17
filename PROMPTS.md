# PromptLab — Important Prompts

This file records the most important prompts used while developing PromptLab and the reasoning behind the resulting changes.

## 1. Project Specification

**What I asked:**
Create a specification for a command-line prompt evaluation harness with a fixed CLI, JSON suites, assertions, repeated runs, flaky detection, reports, comparison, and diagnostics.

**What came back:**
A structured specification covering the main commands, assertions, reports, exit codes, and testing requirements.

**What I changed:**
I kept the requirements explicit and used SPEC.md as the source of truth before implementation.

**Why:**
The hackathon requires spec-driven development and the first commit had to contain only SPEC.md.

## 2. Runner Architecture

**What I asked:**
Implement PromptLab using the Python standard library and invoke the supplied model through a subprocess.

**What came back:**
A Python CLI implementation using argparse, subprocess, JSON parsing, hashing, timing, and unittest.

**What I changed:**
I kept stubmodel.py separate and invoked it as a subprocess instead of importing or reimplementing it.

**Why:**
The judging environment can replace the model binary while keeping the same CLI contract.

## 3. Assertion Engine

**What I asked:**
Implement all eight required assertion types.

**What came back:**
An assertion evaluator covering text, regex, JSON, token, and finish-status checks.

**What I changed:**
I added individual handling for contains, not_contains, equals, matches, json_valid, json_field_equals, max_tokens, and finish_is.

**Why:**
Hidden suites can exercise every assertion type independently.

## 4. Repeated Runs and Flaky Cases

**What I asked:**
Make repeated runs distinguish pass, fail, and flaky behavior.

**What came back:**
The runner executes every case repeatedly and records the result of each run.

**What I changed:**
A case passes only when all runs pass, fails when all runs fail, and is flaky when the results are mixed.

**Why:**
A test that passes only some of the time must not be reported as a reliable pass.

## 5. Prompt Improvement

**What I asked:**
Improve the weak classification prompt and measure the change with PromptLab.

**What came back:**
A second prompt version with clearer category definitions and stricter output-format instructions.

**What I changed:**
I created classify_v2.txt and compared its evaluation report with the baseline.

**Why:**
The hackathon requires evidence that prompt improvement is measured rather than simply claimed.
