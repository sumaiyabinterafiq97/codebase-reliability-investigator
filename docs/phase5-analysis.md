# Phase 5 analysis — EXP-5 gated fail-open semantic review

Status: **measured**. This report does not change code, gold, eval, or artifacts.

## Verdict

EXP-5 **did not improve** the strongest system.

On the 12-repository gold set it scored **exactly the same** as EXP-2 deterministic filters: micro precision **0.90**, recall **1.0**, micro F1 **0.947**, macro F1 **0.917**, FP **1** (cri-12). The gated LLM **confirmed** that leftover false positive. It did **not** solve cri-12.

What EXP-5 did show, relative to EXP-4: a **safer agentic pattern**. Filters still did the precision work; a deterministic gate kept the nine true positives away from the LLM; one bounded `enclosing_block` call plus a fail-open CONFIRM-unless prior **preserved recall**. EXP-4’s reject-biased review of every survivor had driven recall to **0**.

That architectural result does **not** justify replacing EXP-2. EXP-5 is a named experimental variant / proof-of-concept, not the new control.

The benchmark remains the same 12-repository gold set. Ground truth and evaluation matching were not changed.

---

## 1. Hypothesis

After unchanged EXP-2 filters, a **category↔construct gate** can send only structurally inconsistent `error_handling` findings to one fail-open, tool-using LLM call, so that:

- cri-01 … cri-09 never enter semantic review (recall preserved);
- cri-12 does enter (the leftover FP);
- the LLM may reject only if the enclosing block concretely prevents the claimed failure.

Success as a **benchmark improvement** would have required dropping cri-12 **and** keeping all nine TPs, producing a higher F1 than EXP-2. Success as an **architectural** experiment required the safer pattern even if F1 did not move.

---

## 2. Experimental setup

- Frozen parent: `outputs/baseline-001` (not modified)
- Filters: same `src/cri/verify/filters.py` as EXP-2 (not modified)
- Gate: `needs_semantic_review` in `src/cri/verify/gate.py` (generic; no case IDs)
- Tool: one deterministic `enclosing_block(path, start_line, end_line)`
- LLM: one `gpt-4o-mini` call (temperature 0) **only** for gated findings; prior is CONFIRM unless the block prevents the claim
- Fail-open: tool / LLM / parse / schema errors keep the finding (did not occur)
- Ground truth / benchmark cases / evaluation logic: not modified
- Discovery run: `cri-verify --gated --source outputs/baseline-001 --output outputs/exp5-gated-semantic --no-eval`
- Evaluation: `cri-eval` → `outputs/exp5-gated-semantic/metrics.json` (written after the run; not a second LLM call)
- Output: `outputs/exp5-gated-semantic/`

`run_meta.json` records: `survivors=10 gated=1 bypassed=9 llm_calls=1 confirm=1 reject=0 fail_open=0`. Parent run `outputs/baseline-001`. System `baseline-filters-gated-verifier`. Experiment `EXP-5-gated-semantic`. Cost fields `null` (no declared prices).

---

## 3. Comparison (recorded artifacts)

Values from `outputs/*/metrics.json` and run notes. EXP-2 tokens are `null` because that run did not call the LLM. EXP-4 macro F1 **1.0** is the empty-prediction artifact described in `docs/phase4-analysis.md`, not a quality win.

| Metric | Baseline `baseline-001` | EXP-2 Filters | EXP-4 Verifier | EXP-5 Gated |
|--|--|--|--|--|
| Precision (micro) | 0.75 | **0.90** | `null` (0 TP, 0 FP) | **0.90** |
| Recall (micro) | **1.0** | **1.0** | **0.0** | **1.0** |
| Micro F1 | 0.857 | **0.947** | `null` | **0.947** |
| Macro F1 | 0.75 | **0.917** | 1.0 (artifact) | **0.917** |
| FP count | 3 | **1** | 0 | **1** |
| Negative-repo FPR | 1.0 | 0.333 | 0.0 | 0.333 |
| Severity accuracy | 1.0 | 1.0 | `null` (no TPs) | 1.0 |
| Evidence-grounding accuracy | 1.0 | 1.0 | `null` (no TPs) | 1.0 |
| LLM confirm / reject | — | — | **0 / 10** (10 calls) | **1 / 0** (1 call) |
| Gate: bypassed / gated | — | — | n/a (all survivors reviewed) | **9 / 1** |
| Fail-open keeps | — | — | 0 | 0 |
| Remaining FP | cri-10, cri-11, cri-12 | **cri-12** | none (no findings) | **cri-12** |
| Runtime (s) | 26.110 | 0.004 | 19.972 | 2.552 |
| Prompt tokens | 9055 | `null` | 9734 | 682 |
| Completion tokens | 1368 | `null` | 1082 | 94 |
| Estimated cost | `null` | `null` | `null` | `null` |

Exact micro F1 for EXP-2 and EXP-5 is `0.9473684210526316`; macro F1 is `0.9166666666666666`. Exact runtimes: baseline `26.109501`, EXP-2 `0.003778`, EXP-4 `19.972051`, EXP-5 `2.552318`.

Per-repository EXP-5 result (`metrics.json`): cri-01…cri-09 TP; cri-10 and cri-11 no finding (already filtered); cri-12 FP. **Identical to EXP-2.** Do not reinterpret this as an F1 gain.

---

## 4. Gate (implemented, not case-tuned)

Predicate (`src/cri/verify/gate.py`), after EXP-2 `apply_filters`:

```
category == "error_handling"
AND source file exists
AND AST parse succeeds
AND no ast.ExceptHandler overlaps finding.location_span()
```

Anything else returns `False`: **no LLM**, finding **retained**. File/parse/unexpected errors also return `False` (gate fail-closed ⇒ recall preserved).

The gate does **not** inspect repository IDs, issue IDs, benchmark filenames, line numbers, `stock`, `_lock`, `available`, cri-12, or ground truth. That is what makes it defensible rather than a hardcoded leftover-FP detector. Encoding lock/guard into the **gate** would have been cri-12-shaped overfitting. Those facts were left for the tool payload and the model.

### Why cri-01 … cri-09 bypassed (`raw/gate_log.json`: all `gated: false`)

| Finding | Why `needs_semantic_review` is false |
|---------|--------------------------------------|
| cri-01 | `error_handling`, cited `except` overlaps `ExceptHandler` |
| cri-02 | `input_validation` |
| cri-03 | `resource_lifecycle` |
| cri-04 | `state_concurrency` |
| cri-05 | `testing_coverage` |
| cri-06 | `error_handling`, `return {}` overlaps the `except` |
| cri-07 | `state_concurrency` |
| cri-08 | `error_handling`, `return raw` overlaps the `except` |
| cri-09 | `input_validation` |

cri-10 and cri-11 never reached the gate: EXP-2 `error_handling_reraise` (`raw/filter_log.json`).

### Why cri-12 entered

Baseline citation: `error_handling` on `stock.py` lines 12–13 (`stock[sku] = available - n` / `return True`). `reserve` has **no** `try`/`except`. No overlapping `ExceptHandler`. Gate `True`. One LLM call. This is the leftover FP’s **shape**, not a hardcoded ID.

---

## 5. Trajectory (actual; one repo only)

Source: `outputs/exp5-gated-semantic/raw/trajectories/cri-12-locked-and-tested__9.json` (same events in `raw/trajectories.json`). **Only cri-12** has a trajectory. No extra tools, retries, or repo walks.

| Seq | Kind | What happened |
|-----|------|----------------|
| 1 | `instruction` | Gated CONFIRM-unless system prompt |
| 2 | `action` | Candidate finding (category, description, evidence, span 12–13) |
| 3 | `action` | `enclosing_block` args `{path: stock.py, start_line: 12, end_line: 13}` |
| 4 | `tool_result` | `ok: true`; innermost `FunctionDef` slice; `node_types`: `FunctionDef`, `With` |
| 5 | `action` | `llm_complete` |
| 6 | `feedback` | Raw model JSON: **confirm**, confidence 0.9 |
| 7 | `feedback` | Parsed decision **confirm**, `kept: true` |

Tool slice (verbatim from the tool result):

```text
     7|def reserve(sku: str, n: int = 1) -> bool:
     8|    with _lock:
     9|        available = stock.get(sku, 0)
    10|        if available < n:
    11|            return False
    12|        stock[sku] = available - n
    13|        return True
```

The model’s reason: *“The enclosing block does not prevent the stock from becoming negative, as it only checks if available is less than n before updating.”*

That conclusion is **wrong**. `if available < n: return False` means the assignment is reached only when `available >= n`, so `available - n` is not negative. The guard **does** prevent the claimed invalid state. EXP-5 therefore **failed to remove** the remaining FP. The LLM did **not** successfully solve cri-12.

`node_types` listed `FunctionDef` and `With` only. The `If` is a **preceding sibling** of the cited lines, not an enclosing node of span 12–13. The guard was still visible in the numbered text. The model had the facts and still confirmed.

Parse status `ok`; `fail_open` false; `llm_calls` 1. Fail-open was not exercised in this run.

---

## 6. Benchmark performance

Did not improve F1, precision, recall, FP count, or negative-repo FPR versus EXP-2. Those scores are the same because the kept finding set is the same: nine TPs plus cri-12.

Versus baseline: still the EXP-2 gain (FP 3 → 1, micro F1 0.857 → 0.947), produced by **filters**, not by the gated LLM.

Versus EXP-4: recall 0.0 → 1.0 and micro F1 from undefined back to 0.947. That is recovery from a failed verifier, not a new high score.

Token use (682 + 94) and runtime (2.55 s) are much smaller than EXP-4 (9734 + 1082, ~20 s) because nine survivors never called the model. Cheaper incorrect confirmation is still not a scored win.

---

## 7. Architectural / agentic value

EXP-4 asked an LLM to semantically verify **every** filter survivor with a **reject-biased** policy. It rejected all nine true positives.

EXP-5 changed the architecture:

- deterministic filters remain responsible for broad precision (re-raise FPs);
- only structurally inconsistent candidates go to semantic review;
- review is fail-open; CONFIRM is the default;
- parse / tool / LLM failures keep the finding;
- the agent performs **one** bounded tool action;
- the trajectory records instruction, tool args, tool result, LLM response, and keep/reject.

That is a **safer agentic pattern** than EXP-4 because it **preserved recall**. It is **not** a stronger measured finder on this benchmark. Bounded tool use and trajectory logging were demonstrated; reliable semantic verification was not.

---

## 8. Qualitative evidence

The EXP-5 LLM cited `"stock[sku] = available - n"` (lines 12–13). That string is in `stock.py`. It supports “an assignment exists.” It does **not** support the claim that the guard fails to prevent a negative update. The quote restates the original false-positive evidence rather than pointing at the `if available < n` / `return False` path that would justify a reject.

Scored **evidence-grounding accuracy is 1.0** (`metrics.json`). That metric is the existing evaluation rule (location window and quote overlap/substring) on matched true positives. It does **not** score verifier quotes, and it does **not** prove the model’s semantic conclusion was correct. cri-12’s match record has `evidence_grounded: null` (FP, no gold issue).

No separate “verifier quote in source” aggregate was defined for EXP-5 (EXP-4 counted that qualitatively: 5/10 in-source). The EXP-5 quote happens to be a literal substring; that is not a new F1.

---

## 9. What EXP-5 demonstrated vs failed to demonstrate

**Demonstrated**

- Bounded agentic behavior (one tool, one LLM call, only if gated)
- Conditional tool use (nine TPs: zero calls)
- Generic deterministic gate (no repo-specific logic in production)
- Fail-open semantics (specified and tested; unused in this run)
- Preserved recall (9/9 TPs kept)
- Trajectory logging that matches the actual steps
- No benchmark / gold / evaluation modification

**Failed to demonstrate**

- Improved F1 (unchanged vs EXP-2)
- Elimination of cri-12
- Reliable semantic verification of a simple guard
- Superior reasoning over deterministic control flow (`available < n` ⇒ mutation not taken)

---

## 10. Limitations (benchmark-limited)

- **n = 12** synthetic repos; among EXP-2 survivors the gate fired **once**. A later `error_handling` citation without an overlapping `except` would also enter—that is intended—but this run does not measure a second such case.
- The CONFIRM-unless prior plus “absence of a handler is not a reject” likely **under-weighted** the explicit `if` that *does* prevent the claimed state. EXP-4 over-rejected; EXP-5 under-rejected the one leftover FP.
- `enclosing_block` returns a source slice and node-type names. It does not emit structured facts such as “assignment is dominated by `If` that returns.” The model had to recover that from text and did not.
- Fail-open, schema errors, and tool failures were not observed live; they are unit-tested only.
- Same model (`gpt-4o-mini`, temperature 0) as EXP-4; the difference is **policy and routing**, not a stronger reasoner.

---

## 11. Is another experiment justified now?

**No, not immediately**, and not another default-reject verifier.

Filters already hold the best measured F1. EXP-5 showed that gating prevents EXP-4-style recall collapse, and that this model still misread a two-line guard when asked to confirm unless prevented. Repeating a similar LLM confirm/reject on the same leftover, without a different **representation** of control flow, is not justified by these measurements.

A **possible future direction** (not implemented, not claimed): expose structured control-flow facts from the AST (e.g. whether the cited assignment is reachable only after a dominating `If`/`return`) instead of hoping the model reconstructs that from a numbered slice. That would still need a fail-open gate, still must not hard-code cri-12, and would still be an experiment—not a reason to replace EXP-2 today.

Do not implement that here.

---

## 12. Decision

- **Keep** `outputs/baseline-001` as the frozen discovery control.
- **Keep EXP-2 deterministic filters as the strongest measured system** (`outputs/exp2-baseline-filters`, micro F1 0.947, recall 1.0).
- **Keep EXP-5** as an agentic experimental variant / architectural proof-of-concept (`outputs/exp5-gated-semantic`). Same score as EXP-2; safer routing than EXP-4.
- **Reject EXP-4** as previously decided (`docs/phase4-analysis.md`).
- **Do not** replace EXP-2 with EXP-5 on benchmark score.
- **Do not** claim EXP-5 improved the benchmark.
- **Do not** immediately implement another LLM verifier.

**Not justified as the new control.**
