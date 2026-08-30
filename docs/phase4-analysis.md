# Phase 4 analysis — EXP-4 single-candidate semantic verifier

## 1. Hypothesis

A skeptical one-call LLM verifier, applied only to findings that survive unchanged EXP-2 filters, can reject leftover semantic false positives (especially a locked, guarded update mislabeled as error handling) without dropping the nine true positives.

Deterministic filters remain responsible for re-raise, locked `state_concurrency` writes, and test-file citation. The verifier is not a discovery agent.

## 2. Experimental setup

- Frozen parent: `outputs/baseline-001` (not modified)
- Filters: same `src/cri/verify/filters.py` as EXP-2 (not modified)
- Ground truth / benchmark cases: not modified
- Pipeline: baseline findings → filters → **10** survivors → **one** `gpt-4o-mini` (temperature 0) JSON confirm/reject per survivor → keep confirms only
- No tools, no gold in the prompt, no case IDs, no repository-wide search
- Invalid verifier JSON would fail-open to confirm (did not occur)
- Output: `outputs/exp4-semantic-verifier/`
- Qualitative evidence: `verifier_evidence_in_source` is true iff the verifier quote is a substring of the cited file (count only; not a new F1)

## 3. Results

| | Baseline `baseline-001` | Baseline + Filters `exp2-baseline-filters` | + Semantic Verifier `exp4-semantic-verifier` |
|--|--|--|--|
| Precision (micro) | 0.75 | **0.90** | `null` (0 TP and 0 FP) |
| Recall (micro) | **1.0** | **1.0** | **0.0** |
| Micro F1 | 0.857 | **0.947** | `null` |
| Macro F1 | 0.75 | **0.917** | 1.0 (artifact: see below) |
| FP count | 3 | 1 | **0** |
| Negative-repo FPR | 1.0 | 0.333 | 0.0 |
| Severity accuracy | 1.0 | 1.0 | `null` (no TPs) |
| Evidence-grounding accuracy | 1.0 | 1.0 | `null` (no TPs) |
| Verifier confirm / reject | — | — | **0 / 10** (10 calls) |
| Runtime (s) | 26.11 | 0.004 | **19.97** (verifier calls only) |
| Prompt tokens | 9055 | `null` | **9734** |
| Completion tokens | 1368 | `null` | **1082** |
| Estimated cost | `null` | `null` | `null` |

Macro F1 of 1.0 is **not** a quality win: positive repos with empty predictions have undefined precision, so they are omitted from the macro average; only the three negative repos (correct empty lists) remain, each with F1 1.0.

Qualitative verifier quotes: in-source **5**, not in-source **5** (whitespace/quote-style mismatches). No aggregate “evidence F1” is defined.

## 4. Findings rejected

All 10 filter-survivors were rejected, including:

- Nine gold issues: cri-01 … cri-09
- One true negative leftover: **cri-12-locked-and-tested** (guarded decrement under `_lock`, mislabeled `error_handling`)

Filters had already suppressed cri-10 and cri-11 (no verifier call).

## 5. False rejections

All nine true positives. Typical rationales over-applied “need more proof of a runtime failure” or treated a sentinel `paid` return as an acceptable fallback (cri-01), ignored the error-path `open` leak (cri-03), or denied a race without a recorded interleaving (cri-04, cri-07).

## 6. False confirmations

None (0 confirms).

## 7. Recall impact

Recall 1.0 → **0.0**. The primary success condition (**remove cri-12 while keeping all 9 TPs**) **failed**.

## 8. Precision impact

FP 1 → 0, but only by deleting every remaining finding. Precision is undefined, not “perfect.”

## 9. F1 impact

Micro F1 0.947 → undefined/collapsed. **Worse than EXP-2.**

## 10. Cost / latency impact

About **20 s** and **9734 + 1082** tokens on top of the frozen baseline, for a strictly worse finding set. Cost USD remains `null` (no declared prices).

## 11. Whether the verifier is justified

**No**, not in this prompt/model configuration. It did reject cri-12 for a valid guard-based reason, but the “challenge / default REJECT” instruction produced systematic over-rejection of real defects. Deterministic filters already handled the re-raise FPs more cheaply and without recall loss.

## 12. Whether it should be kept

**Reject as the production/control pipeline.** Keep artifacts for the changelog. **Stronger candidate remains baseline + deterministic filters (`exp2-baseline-filters`).**

Do not add an investigator agent on the back of this result. A later verifier experiment would need a different decision prior (not default-reject-all) and would still be limited to leftover semantic candidates after filters.
