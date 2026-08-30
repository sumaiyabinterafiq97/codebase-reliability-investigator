# EXP-5 gate design

Status: **original design** (written before implementation). The gate specified here was later implemented and measured as EXP-5 (`outputs/exp5-gated-semantic/`). Control remains baseline-001 + EXP-2 filters. EXP-5 is an experimental variant, not a new control; see [docs/phase5-analysis.md](phase5-analysis.md). This file is the design specification, not a scored-result report. It does not change gold, eval, or metrics.

Question: can a **deterministic gate** send only structurally inconsistent findings to a fail-open, one-tool LLM, while **proving** that the nine current true positives never enter?

Conclusion: **yes, one narrow gate is defensible** without repository IDs, file names, or line numbers. It is *not* a lock/guard detector (that would overfit cri-12). It is a **category ↔ construct** check: `error_handling` findings whose cited span does not overlap any `except` handler.

EXP-4 failed because it reviewed **all** filter survivors with a default-REJECT prior. The gate exists so the LLM never sees cri-01…cri-09.

---

## 1. Proposed gate predicate

After EXP-2 `apply_filters` (unchanged), a finding **enters semantic review** iff:

> `category == error_handling`  
> **and** the cited file parses  
> **and** **no** `ast.ExceptHandler` in that file has a line span overlapping the finding’s `location_span()`.

Otherwise it **does not enter**. Parse/file errors → **do not enter** (gate fail-closed ⇒ finding kept; recall preserved).

Rationale from taxonomy, not from cri-12: `error_handling` is about catching, swallowing, or continuing after **exceptions**. A claim that cites only ordinary statements (assignment, `return True`, etc.) with **no overlapping handler** is structurally the wrong construct for that category. Whether a lock or `if` later justifies a reject is the **LLM + tool** step, not the gate.

The gate does **not** look at locks, guards, inventory, `stock`, or test files.

---

## 2. Exact AST conditions

Definitions (reuse existing helpers in `src/cri/verify/astutil.py`; do not special-case names):

- `span = finding.location_span()` → `(line_start or line, line_end or line)` as today.
- Parse `repo_root / finding.file` with `ast.parse`.
- Walk all `ast.ExceptHandler` nodes; `node_span(handler) = (lineno, end_lineno)`.
- Overlap: `handler_start <= finding_end and finding_start <= handler_end` (same as `spans_overlap` today).

**Enter review** when:

```
category == "error_handling"
AND source file exists
AND AST parse succeeds
AND ∀ ExceptHandler h: NOT overlaps(span(h), span(finding))
```

No requirement that an `Assign` exist. No requirement that a `With` / `If` exist. Those belong in the tool payload if the gate fires.

**Do not enter** when:

- category is not `error_handling`, or
- file missing / `SyntaxError` (keep finding), or
- at least one `ExceptHandler` overlaps the cited span.

---

## 3. Which categories it applies to

**Only `error_handling`.**

| Category | Gate | Why |
|----------|------|-----|
| `error_handling` | yes | Must cite exception-handling control flow |
| `input_validation` | no | Typical construct **is** assignment / `split` / `int()` (cri-02, cri-09) |
| `resource_lifecycle` | no | Typical construct is `open` / missing `close` (cri-03), which may sit next to `try` |
| `state_concurrency` | no | Typical construct is unlocked assignment (cri-04, cri-07); lock cases already filtered |
| `testing_coverage` | no | Typical construct is `try/except` fallback + tests (cri-05); test-file cites already filtered |

Applying a “no except” rule to other categories would be wrong (validation and races are not handlers).

---

## 4. Why each of the 9 true positives is excluded

Using **frozen baseline-001** spans (the control’s actual citations), after EXP-2 (none of these nine are suppressed):

| Finding | category | Cited span (baseline-001) | Overlapping `ExceptHandler`? | Enters gate? |
|---------|----------|---------------------------|------------------------------|--------------|
| cri-01 | error_handling | checkout.py 16–17 `except:` / `return paid` | **Yes** (bare `except` 16–17) | **No** |
| cri-02 | input_validation | orders.py 6–7 assignment | n/a (category) | **No** |
| cri-03 | resource_lifecycle | audit.py 1–11 (wide) | n/a (category) | **No** |
| cri-04 | state_concurrency | wallet.py 1–17 | n/a (category) | **No** |
| cri-05 | testing_coverage | payments.py 24–28 `try/except` fallback | n/a (category) | **No** |
| cri-06 | error_handling | config.py 9–10 `return {}` | **Yes** (`except (OSError, JSONDecodeError)` 8–9; overlap at line 9) | **No** |
| cri-07 | state_concurrency | warehouse.py 11 assignment | n/a (category) | **No** |
| cri-08 | error_handling | billing.py 13–14 `return raw` | **Yes** (`except (KeyError, …)` 11–13; overlap at 13) | **No** |
| cri-09 | input_validation | catalog.py 7 `split` | n/a (category) | **No** |

cri-10 / cri-11 never reach the gate: EXP-2 already drops them (`error_handling_reraise`). Their spans **do** overlap `except`; if filters were skipped they still would **not** enter this gate (they have handlers). That is consistent: they are structurally `error_handling`-shaped; the filter, not the gate, is the right tool.

---

## 5. Why cri-12 is included

Frozen baseline-001: `category=error_handling`, `stock.py` lines **12–13**:

```text
        stock[sku] = available - n
        return True
```

`reserve` has **no** `try`/`except`. There is **no** `ExceptHandler` whose span overlaps 12–13. The gate therefore **enters** semantic review.

The surrounding `with _lock` and `if available < n` are **not** part of the predicate. They are why a later tool-using reject might be justified; they are not how we select cri-12.

---

## 6. Whether the rule generalizes beyond cri-12

It generalizes to the class:

> “Model labeled ordinary sequential code as swallowed-exception handling.”

That class is independent of locks, inventory, or this benchmark’s IDs. Examples that would also enter (none of which are hardcoded): `error_handling` pointing at a dict update, a `return True`, a log line outside `except`, a `for` loop, etc.

It does **not** generalize to every leftover FP. A false `state_concurrency` on locked code is already EXP-2. A false `testing_coverage` on a test file is already EXP-2. A false `error_handling` that **does** overlap `except` but misreads a legitimate fallback (cri-01-shaped) **would not enter**—and must not, because that is how we protect TPs. Those need a different, riskier mechanism (EXP-4 already showed that).

---

## 7. Potential false-positive / false-negative risks

**Gate false-negative (TP sent to LLM — recall risk if the LLM rejects):**

- Future `error_handling` TP whose citation is **only** a post-handler use site that does **not** overlap the `except` (e.g. only `debit()`’s assignment, not `return raw` inside the handler). Fail-open on the LLM limits damage; the gate itself would still *select* that finding.
- `error_handling` meaning “missing `try` entirely” citing a naked `json.loads` call: structurally no handler → **would enter**. Taxonomy allows missing handlers. Fail-open is mandatory. This case is **not** in the current 9 TPs.
- Extremely wide spans: if an `error_handling` span covered a whole file that also contains an unrelated `except`, overlap would be true → **would not enter**. Opposite risk (below).

**Gate false-positive (FP not sent — precision left on the table):**

- `error_handling` FP that **does** overlap an `except` but is still wrong for other reasons (EXP-4-style overclaim). **Intentionally not gated**; EXP-2 already handles linear re-raise. We accept leaving those to filters, not the LLM.

**Other:**

- `end_lineno` missing on old Python: treat as `lineno` only; might miss overlap. Project requires ≥3.11, so `end_lineno` exists.
- Finding span pointing at comments/`line=1` module docstring (cri-03-style) but **wrong category**: not this gate’s job.

---

## 8. Defensible vs benchmark-overfit

**Defensible:** The predicate is exactly “this category requires an exception handler construct.” It uses the same overlap idea as the existing re-raise filter, with the opposite polarity (no handler vs handler that always re-raises). No IDs, no `stock`, no `_lock`, no `available`.

**Looks overfit if** we added “must be inside `with` + `if`” to the **gate**. That would be encoding cri-12’s body. **Do not do that in the gate.**

**Honest caveat:** On *this* 12-case set, among EXP-2 survivors, cri-12 is the **only** `error_handling` finding without an `except` overlap. So the gate will fire once in the current control run. That is a consequence of the leftover FP’s shape, not a hardcoded ID. If a later model emits a second such mismatch, it would also enter—which is desired.

**Verdict:** implementable as a gate **if and only if** the LLM step is fail-open and **not** default-REJECT. The gate alone is not overfit; repeating EXP-4’s prompt would still destroy recall **if** a TP ever slipped through the gate.

If product owners refuse any LLM on leftovers, skip EXP-5 and consider a **separate** deterministic filter (assignment dominated by `if` inside lock `with`)—that *would* be more cri-12-shaped and should be justified independently, not mixed into this gate.

---

## 9. Exact pseudocode

```
function needs_semantic_review(finding, repo_root) -> bool:
    if finding.category != "error_handling":
        return False
    source = read_file(repo_root, finding.file)   # existing normalize_path
    if source is None:
        return False
    tree = ast.parse(source)                      # on SyntaxError: return False
    span = finding.location_span()
    for node in ast.walk(tree):
        if type(node) is ast.ExceptHandler:
            hspan = (node.lineno, node.end_lineno or node.lineno)
            if overlaps(hspan, span):
                return False
    return True

function exp5(findings, repo_root, llm):
    surviving, filter_log = apply_filters(findings, repos_dir)  # EXP-2 unchanged
    kept = []
    for f in surviving:
        if not needs_semantic_review(f, repo_root / f.repository_id):
            kept.append(f)
            continue
        try:
            block = enclosing_block(repo_root, f.file, f.location_span())
            result = llm.confirm_or_reject(f, block)   # one call; CONFIRM unless blocked
            if result.decision == "reject":
                log reject
            else:
                kept.append(f)
        except Exception:
            kept.append(f)   # fail-open
    return kept
```

Do not implement this here.

---

## 10. Recommended tool interface (only if the gate is viable)

The gate is viable. Tool for the **gated** call only:

**`enclosing_block(path, start_line, end_line) -> { file, start, end, text, node_types[] }`**

- Deterministic: from the AST, collect enclosing `FunctionDef`, `With`, `If`, `Try`, `ExceptHandler` whose span **contains** `start_line` (and `end_line` if possible).
- Return the **source slice** of the innermost function (or the whole file if no function), numbered.
- No repo walk, no grep, no tests directory unless that file is `finding.file`.
- `node_types` e.g. `["FunctionDef", "With", "If"]` so the model sees structure without us classifying “this is a lock.”

LLM prior (specified here; implemented later in EXP-5): **CONFIRM unless** the enclosing block shows defensive control flow that **prevents the claimed failure** (for an `error_handling` claim: there is no failure being swallowed because there is no handler, and any claimed invalid state is prevented by an explicit preceding branch). Default CONFIRM. Parse error → keep finding. Measured outcome: EXP-5 used this prior; it did not improve F1 vs EXP-2. Control remains EXP-2.

Do **not** give `list_files`, `grep`, or test execution in EXP-5.

---

## Stop

This section originally recorded that no EXP-5 run existed yet. **Implementation and measurement happened later**; do not treat the paragraph below as current project status.

Historical note (pre-implementation): unit tests should show that the nine baseline-001 TP findings return `needs_semantic_review == False` and the cri-12 baseline finding returns `True`, **without** putting those IDs in the gate predicate itself—only in tests. That constraint was followed. Scored outcome: [docs/phase5-analysis.md](phase5-analysis.md).
