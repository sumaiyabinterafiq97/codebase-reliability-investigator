# Baseline analysis — `outputs/baseline-001`

Run: 2026-08-30, `system_id=baseline`, provider=`openai`, model=`gpt-4o-mini`, temperature=`0`.
Artifacts: `outputs/baseline-001/{findings,run_meta,metrics}.json`. Ground truth was not edited.

## Headline metrics

| Metric | Value |
|--------|--------|
| Macro Finding F1 | **0.75** |
| Micro Finding F1 | **0.857** |
| Micro precision | 0.75 |
| Micro recall | **1.0** |
| FP count | 3 |
| FP per repo (mean) | 0.25 (0 on all 9 positives; 1 on each of 3 negatives) |
| Negative-repo FPR | **1.0** (3/3) |
| Severity accuracy (TPs) | 1.0 |
| Evidence-grounding accuracy (TPs) | 1.0 (see caveat) |
| Runtime (sum of per-repo LLM calls) | 26.11 s |
| Prompt tokens | 9055 |
| Completion tokens | 1368 |
| Estimated cost | `null` (no declared price table) |

Every repository produced **exactly one** finding. Parse status was `ok` for all 12.

## What the baseline did well

- Found all 9 gold issues (no false negatives). Easy, medium, and hard **positives** all matched category + file + ±8 lines.
- Severity on those TPs matched gold (`high`/`medium` as labeled).
- Structured JSON validated without `json_parse_error` / `schema_error`.
- Several quotes were actual defect lines (`except:`, `return {}`, `return raw`, `stock[sku] = stock[sku] - n`).

## Missed issues

None on this run (recall 1.0). That is **not** a reason to skip a verifier: the score is limited by precision on negatives.

## False positives (all failures)

### `cri-10-logged-reraise` — `fp_red_herring`

Gold: `except Exception` + `log.exception` + `raise` is **allowed**.

Model: treated logging + propagating as “not ensuring a valid state” (`error_handling`, high).

This is the designed naive-LLM trap and it fired.

### `cri-11-clean-checkout` — `fp`

`charge` has `except ValueError: raise`. The model called this swallowing / missing reporting. Taxonomy: specific except that re-raises is not an issue. Validation, `with open`, and re-raise are all present.

### `cri-12-locked-and-tested` — `fp`

`reserve` holds `_lock`, checks `available < n`, then decrements. Tests cover success and insufficient stock. The model reported `error_handling` because stock “might become negative,” ignoring the guard and the lock.

## Evidence caveat (metric vs quality)

Evidence-grounding accuracy is 1.0 because the matcher accepts **line-range overlap** with gold (or a substring in that range). Two TPs used **module docstrings** as `evidence.quote` while citing a wide range that happened to include the defect:

- `cri-03-leaked-file`: quote is the file docstring; range 1–11.
- `cri-04-racy-balance`: quote is the file docstring; range 1–17.

Those still count as grounded TPs. An advanced step should require the quote to be the failing statement, not a comment that describes the bug.

## Severity mistakes

None among TPs. FPs used `high` for non-issues (over-alarm).

## Difficult cases

Positives that we expected to be hard (`cri-07`, `cri-08`, `cri-09`) were found. Difficulty in **this** benchmark, for this model, is **abstaining on clean code**, not spotting the planted bugs.

## Likely causes

1. **One-finding bias:** the prompt shows a single example object; the model always emits one issue, even when the correct answer is `[]`.
2. **Surface pattern matching:** `except`, `raise`, and assignment to shared state are treated as defects without checking *what happens next* (re-raise, lock, prior guard, tests).
3. **No verification pass:** nothing re-reads the handler to see `raise` or `_lock`.
4. **Docstrings leak the answer** in some synthetic files (helps recall; pollutes evidence).

## Capabilities the next experiment should add

Do **not** jump to a full multi-agent product. The measured gap is precision on negatives and quote quality.

Recommended order:

1. **Abstention / empty-list discipline** — prompt and schema that make `findings: []` the default; maybe a first token constraint or an explicit `has_issue` boolean that must be true before any finding is emitted.
2. **Deterministic taxonomy checks** (not an LLM): if cited lines contain `raise` as the except body, drop `error_handling`; if a `with lock` (or `with _lock`) wraps the write, drop `state_concurrency`; if tests call the fallback branch, drop `testing_coverage`.
3. **Evidence quote check:** quote must appear in the cited lines and must not be only a module docstring; prefer the statement that implements the defect.
4. Only after (1)–(3), consider a small **LLM yes/no verifier** on remaining candidates.

Those experiments belong in `docs/improvement-changelog.md` as they are tried or dropped.
