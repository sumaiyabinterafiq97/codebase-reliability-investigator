# Improvement changelog

## 2026-08-30 — Phase 2 baseline `outputs/baseline-001`

- Experiment ID: (control)
- Hypothesis: A single `gpt-4o-mini` prompt over the full `.py` bundle is a fair control; likely FPs on re-raise and clean repos.
- Change: Implemented file collection + one LLM call + eval. No advanced agent.
- Benchmark version: 12-repo v1
- Configuration: openai / gpt-4o-mini / temperature 0
- Result: macro F1 **0.75**, micro F1 **0.857**, recall **1.0**, precision **0.75**, FP **3**, negative-repo FPR **1.0**. Tokens 9055 + 1368. Cost `null`.
- Observed failure modes: one-finding-per-repo; re-raise FPs; cri-12 mislabeled; docstring evidence.
- Decision: **Keep** as the frozen control.
- Reason: Later systems must beat this exact run without editing gold.

## 2026-08-30 — EXP-1 abstention `outputs/exp1-baseline-abstention`

- Experiment ID: `EXP-1-abstention`
- Hypothesis: Removing “always produce an example finding” and making `findings: []` the default reduces one-finding bias without tools.
- Change: Separate system `baseline-abstention`; original baseline prompt unchanged.
- Benchmark version: 12-repo v1 (same cases)
- Configuration: same model/temperature as baseline-001
- Result vs control: precision 0.875, recall **0.778**, micro F1 **0.824**, macro F1 0.909, FP 1, neg FPR **0.0**. Tokens 9799 + 1130. Cost `null`. Runtime 20.17s.
- Observed failure modes: empty list on cri-09 (true issue); cri-05 cited `test_payments.py` (FP+FN vs gold file); cri-02 severity medium vs gold high.
- Decision: **Keep as a named variant, not as the new control.**
- Reason: Precision/FPR improved but recall was not preserved — fails the Phase 3 objective.

## 2026-08-30 — EXP-2 filters `outputs/exp2-baseline-filters`

- Experiment ID: `EXP-2-filters`
- Hypothesis: Conservative AST checks for re-raise, locked writes, and tested fallbacks remove baseline FPs without dropping TPs.
- Change: Post-process frozen `baseline-001` (no new LLM). After EXP-1, added `testing_coverage_cites_test_file` for the observed test-file citation FP.
- Benchmark version: 12-repo v1
- Configuration: n/a (deterministic). Parent: baseline-001
- Result vs control: precision **0.90**, recall **1.0**, micro F1 **0.947**, macro F1 **0.917**, FP **1**, neg FPR **0.333**. Tokens `null`. Cost `null`. Runtime 0.004s.
- Observed failure modes: cri-12 still an FP (`error_handling` on a locked decrement; lock filter does not apply to that category).
- Decision: **Keep.**
- Reason: Largest F1 gain while preserving recall; re-raise FPs removed without suppressing cri-01/06/08.

## 2026-08-30 — EXP-3 evidence `outputs/exp3-baseline-evidence`

- Experiment ID: `EXP-3-evidence`
- Hypothesis: Replacing quotes from disk, skipping module docstrings, and bounding snippets improves evidence without an LLM verifier.
- Change: Post-process frozen `baseline-001` evidence only.
- Benchmark version: 12-repo v1
- Configuration: n/a. Parent: baseline-001
- Result vs control: F1/precision/recall **unchanged** (0.75 / 1.0 / 0.857). Eval grounding still 1.0. Tokens `null`. Runtime 0.002s.
- Observed failure modes: scored grounding metric already saturated; FPs still have valid local snippets; cri-03/04 quotes are now function bodies (better) not docstrings.
- Decision: **Keep** as an evidence layer on top of whatever findings we ship.
- Reason: Does not hurt recall; qualitatively fixes the docstring problem. Does not justify skipping EXP-2.

## 2026-08-30 — EXP-2 on abstention `outputs/exp2-abstention-filters` (extra)

- Experiment ID: `EXP-2-filters-on-abstention`
- Hypothesis: The new test-file filter removes the remaining EXP-1 FP.
- Change: Same filters on EXP-1 outputs.
- Result: precision 1.0, recall 0.778, micro F1 0.875, FP 0. Still misses cri-09 and cri-05 gold location.
- Decision: **Keep as diagnostic only**, not the control.
- Reason: Perfect precision, recall still below baseline.

## 2026-08-30 — EXP-4 semantic verifier `outputs/exp4-semantic-verifier`

- Experiment ID: `EXP-4-semantic-verifier`
- Hypothesis: One skeptical LLM confirm/reject per filter-survivor removes leftover semantic FPs without dropping the nine TPs.
- Change: Unchanged EXP-2 filters, then one `gpt-4o-mini` JSON verifier call per surviving finding. No tools, no gold, no discovery. Fail-open on parse error (unused).
- Benchmark version: 12-repo v1. Parent: frozen `baseline-001`.
- Configuration: openai / gpt-4o-mini / temperature 0; 10 verifier calls.
- Result vs EXP-2: recall **1.0 → 0.0**; confirms **0**, rejects **10**; FP 1 → 0; micro F1 collapsed (`null`). Tokens 9734 + 1082. Runtime 19.97s. Cost `null`.
- Observed failure modes: default-REJECT overshot; all 9 TPs false-rejected; cri-12 correctly rejected; 5/10 verifier quotes not literal substrings.
- Decision: **Reject** as the shipped system. **Keep EXP-2 filters as the stronger candidate.**
- Reason: Failed the success condition (drop cri-12 **and** keep 9 TPs). Filters stay responsible for deterministic cases; this LLM verifier is not justified on these measurements.

## 2026-08-30 — EXP-5 gated semantic review `outputs/exp5-gated-semantic`

- Experiment ID: `EXP-5-gated-semantic`
- Hypothesis: After unchanged EXP-2 filters, a generic category↔construct gate can send only `error_handling` findings with no overlapping `except` to one fail-open, one-tool LLM call (CONFIRM unless the enclosing block prevents the claim), preserving the nine TPs while possibly dropping cri-12.
- Change: `needs_semantic_review` + `enclosing_block` + one `gpt-4o-mini` call on gated findings only. No gold/eval/filter changes. Trajectory recorded.
- Benchmark version: 12-repo v1 (same cases). Parent: frozen `baseline-001`.
- Configuration: openai / gpt-4o-mini / temperature 0; **1** LLM call (9 bypassed, cri-10/11 already filtered).
- Result vs EXP-2: precision **0.90**, recall **1.0**, micro F1 **0.947**, macro F1 **0.917**, FP **1**, neg FPR **0.333** — **unchanged**. Gate passed only cri-12; model **confirmed** (confidence 0.9). Tokens 682 + 94. Runtime 2.55s. Cost `null`.
- Observed failure modes: trajectory logging and fail-open routing were implemented and unit-tested; the live run recorded the cri-12 trajectory (`fail_open=0`, fail-open not exercised). The model incorrectly treated `if available < n: return False` as insufficient to prevent a negative update; cri-12 remained FP.
- Decision: **Keep as an agentic experimental variant, not as the new control.** EXP-2 remains the strongest measured system. EXP-4 remains rejected.
- Reason: Architecturally safer than EXP-4 (recall preserved; bounded tool use). Did not improve F1; not justified as a replacement for filters.

