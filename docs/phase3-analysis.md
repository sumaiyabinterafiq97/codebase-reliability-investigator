# Phase 3 analysis

Benchmark version: `benchmark/cases/index.yaml` v1 (12 Python repos). Ground truth was not edited.

Configuration shared by LLM runs: `openai` / `gpt-4o-mini` / temperature `0` / max_tokens `4096`.
Post-process runs did not call the LLM; token fields are `null` (not invented). Cost is `null` in every run (no declared price table).

## Comparison

| | Baseline `baseline-001` | Baseline + Abstention `exp1-baseline-abstention` | Baseline + Deterministic Filters `exp2-baseline-filters` | Baseline + Evidence Validation `exp3-baseline-evidence` |
|--|--|--|--|--|
| Precision (micro) | 0.75 | 0.875 | **0.90** | 0.75 |
| Recall (micro) | **1.0** | 0.778 | **1.0** | **1.0** |
| Micro F1 | 0.857 | 0.824 | **0.947** | 0.857 |
| Macro F1 | 0.75 | 0.909 | **0.917** | 0.75 |
| FP count | 3 | 1 | **1** | 3 |
| Negative-repo FPR | 1.0 | **0.0** | 0.333 | 1.0 |
| Severity accuracy | 1.0 | 0.857 | 1.0 | 1.0 |
| Evidence-grounding accuracy (eval) | 1.0 | 1.0 | 1.0 | 1.0 |
| Runtime (s) | 26.11 | 20.17 | 0.004 | 0.002 |
| Prompt tokens | 9055 | 9799 | `null` | `null` |
| Completion tokens | 1368 | 1130 | `null` | `null` |
| Estimated cost | `null` | `null` | `null` | `null` |

Abstention is a **new LLM run**. Filters and evidence are **post-process of frozen `baseline-001`**, so they isolate those layers without extra model variance.

Extra (not a table row): filters on abstention (`outputs/exp2-abstention-filters`) reached precision **1.0**, FP **0**, recall still **0.778**, micro F1 **0.875**.

---

### 1. Which experiment improved the system most

Toward the stated goal (**precision and evidence quality while preserving recall**): **EXP-2 deterministic filters** on the original baseline.

Micro F1 rose from 0.857 to 0.947; recall stayed 1.0; FPs fell from 3 to 1 (cri-10 and cri-11 removed by the re-raise filter).

Abstention improved negative-repo FPR the most (1.0 → 0.0) but **violated the preserve-recall constraint** (missed cri-09; misplaced cri-05). Evidence repair improved **quote quality** without changing scored F1 or the eval grounding metric (already 1.0 via ±8 overlap).

### 2. Whether recall was preserved

- Filters: **yes** (9/9 TPs kept).
- Evidence: **yes** (no findings dropped).
- Abstention: **no** (7/9 TPs). Misses: empty list on `cri-09-validate-then-mutate`; `cri-05` cited `test_payments.py` so it did not match gold `payments.py`.

### 3. Which false positives were eliminated

On frozen baseline + filters:

- `cri-10-logged-reraise` — `error_handling_reraise`
- `cri-11-clean-checkout` — `error_handling_reraise`

**Not** eliminated: `cri-12-locked-and-tested` (labeled `error_handling` on a locked, guarded decrement). The lock filter only applies to `state_concurrency`.

Abstention eliminated all three negative-repo FPs by returning `{"findings": []}`.

### 4. Which evidence problems remained

Eval **evidence-grounding accuracy stayed 1.0** on all four rows because overlap-or-substring still holds.

Qualitatively, EXP-3 **did** replace docstring quotes on `cri-03` and `cri-04` with function-body snippets (`open`/`except OSError`; `balance_cents = current + amount_cents`). Remaining issues: snippets are still whole-function slices (up to 8 lines), not always the single failing statement; FPs still have locally valid quotes (`raise`, `stock[sku] = ...`).

### 5. Which baseline failures still need semantic reasoning

- **cri-12:** treating a locked, range-checked update as “stock might go negative” / error handling. Needs understanding of the `available < n` guard, not another surface regex.
- **cri-09 under abstention:** “validate the string then `split`/`int`” is a real issue the cautious prompt skipped. Needs judgment about derived values, not a lock/re-raise AST pattern.
- **cri-05 under abstention:** describing the right bug while pointing at the test file. Needs linking a coverage claim to the production branch.

### 6. Whether an LLM verifier is justified by the measured evidence

**Partially, and only for leftover semantic FPs — not for discovery.**

Deterministic filters already removed the two re-raise FPs without an LLM. An LLM verifier is **not** justified to re-do those checks.

It **is** justified as a **narrow yes/no on remaining candidates** such as cri-12 (“is this actually taxonomy error_handling?”) and maybe category/file repair for coverage claims. It is **not** justified as a full investigator/orchestrator: recall on the frozen baseline is already 1.0; the gap is precision on clean code and one hard validation case when we ask the model to abstain.

### 7. What the next experiment should be

1. Keep **baseline-001 + EXP-2 filters** as the precision-preserving control (do not replace it with abstention).
2. Optional **single-candidate LLM verifier** only on findings that survive filters, with a taxonomy exclusion prompt (re-raise, lock+guard, tests). Cap at one extra call per finding, no tools.
3. Do **not** start multi-agent exploration until that verifier is measured against cri-12 (and does not resurrect cri-10/11).

No investigator agent, RAG, or framework was added in this phase.
