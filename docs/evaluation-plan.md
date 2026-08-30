# Evaluation plan

Evaluation is **offline**, **deterministic**, and uses the **same** 12 cases for baseline and advanced systems. No scores are recorded in this phase.

## Primary metric: Finding F1

After matching (below), for each system run:

- **TP** = predicted findings matched to a gold issue with `present: true`
- **FP** = predicted findings with no gold match, or matched only to a `present: false` marker
- **FN** = gold issues with `present: true` that received no prediction

\[
\text{precision} = \frac{TP}{TP+FP},\quad
\text{recall} = \frac{TP}{TP+FN},\quad
F_1 = \frac{2\cdot precision\cdot recall}{precision+recall}
\]

Macro-average **Finding F1** across the 12 repositories (unweighted). Also report **micro-F1** (pool all findings) as a secondary view.

If a repo has zero gold issues, recall is defined as 1.0 when there are no FNs (always true) and 0.0 is not used; precision is 1.0 if FP=0 else `TP/(TP+FP)` with TP=0.

## Other metrics

| Metric | Definition |
|--------|------------|
| **Precision / recall** | As above (micro and macro) |
| **False-positive rate** | `FP / (FP + TN_repos)` is **not** used at finding level. Report **FP count** and **FP per repo**. For negative repos, **repo-level FPR** = fraction of negative repos with ≥1 finding. |
| **Severity accuracy** | Among TPs, fraction where `predicted.severity == gold.severity` |
| **Evidence-grounding accuracy** | Among TPs, fraction that pass the grounding check (below) |
| **Runtime** | Wall-clock seconds per repo and total (from run metadata) |
| **Token usage** | Prompt + completion tokens per repo if the provider returns them; else `null` |
| **Estimated cost** | `tokens * unit price` from a **declared** price table in run metadata; `null` if unknown. Never invent usage. |

## Matching a prediction to gold

A predicted `Finding` may match at most one gold `Issue`. Greedy matching: for each gold issue with `present: true`, pick the unmatched prediction with the highest score that meets **all hard constraints** and `score >= 1.0`.

**Hard constraints (all required):**

1. `repository_id` equal
2. `category` equal
3. Normalized file path equal (POSIX, relative to repo root, no `./`)

**Location score (need ≥ 1.0 after constraints):**

- `+1.0` if predicted `line` is within **±8 lines** of gold `line`, **or** predicted `[line_start, line_end]` overlaps `[gold.line - 8, gold.line + 8]`
- `+1.0` if `function_name` is present on both and equal (optional bonus; overlap already enough)
- `+0` otherwise → **no match** even if category and file agree

Rationale: judges and models may cite slightly different lines of the same defect. ±8 is small enough to avoid matching a different function in these tiny files.

**Multiple predictions, one gold:** extras are FP.

**One prediction, multiple gold:** greedy gold-order in YAML; leftover gold is FN.

**`present: false` gold rows:** these document known red herrings. A prediction that would have matched that row (same category+file+window) is tagged `matched_red_herring` and counted as **FP**. They are not FN if unmatched.

## Evidence-grounding check (TPs only)

A TP is **grounded** iff:

1. `evidence.file` exists in the repository
2. `evidence.line_start` / `line_end` are in-file bounds (`1..nlines`)
3. `line_start <= line_end`
4. Either:
   - the cited range overlaps the gold ±8 window, **or**
   - `evidence.quote` is a non-empty substring of the cited file content (stripped)

Ungrounded TPs still count as TP for F1 (the issue was found) but fail evidence accuracy. Competition narrative should treat ungrounded TPs as weaker.

## Predicted finding schema

See `src/cri/models/finding.py`. Required fields: `repository_id`, `category`, `severity`, `file`, `line` or line range, `description`, `evidence`.

## Reproducibility

Each run directory must contain:

- `findings.json` — `FindingList`
- `run_meta.json` — system id (`baseline` \| `advanced`), model, timestamps, per-repo runtime/tokens
- Optional: `trajectories/` for the advanced system

Eval command (after install):

```text
python -m cri.evaluation.cli --predictions outputs/<run>/findings.json --ground-truth-dir benchmark/ground_truth
```

Prints metrics JSON to stdout; writes `outputs/<run>/metrics.json` if `--output` is set.

## What we will not do

- Tune gold labels after seeing model output except to fix **factual** errors in a case
- Commit fabricated F1/token/cost numbers
- Use different case subsets for baseline vs advanced
