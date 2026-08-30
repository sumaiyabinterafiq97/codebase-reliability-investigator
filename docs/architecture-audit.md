# Architecture audit — Codebase Reliability Investigator

Date: 2026-08-30 (after EXP-4). Inspection only. No code or gold was changed as part of the *questions* in this audit request; this file is the audit deliverable.

**Later note (does not rewrite this audit):** EXP-5 was implemented and measured after this document was written. The directory tree, CLI notes, and artifact table below are a **Phase 4 snapshot**. They do not include `outputs/exp5-gated-semantic/` or `docs/phase5-analysis.md`. Current control remains EXP-2 filters; EXP-4 remains rejected; EXP-5 is an experimental PoC with the same score as EXP-2 — see [docs/phase5-analysis.md](phase5-analysis.md). Do not read this file as if EXP-5 already existed when it was authored.

Measured control: **baseline-001 + EXP-2 deterministic filters** (micro F1 0.947, recall 1.0, 1 remaining FP: cri-12). EXP-4 verifier **rejected**.

---

## 1. Current directory tree

Source and project files (omitting `.venv`, `.pytest_cache`, `*.egg-info`, `__pycache__`):

```
.
├── README.md
├── pyproject.toml
├── .gitignore
├── .env.example
├── docs/
│   ├── project-plan.md
│   ├── taxonomy.md
│   ├── evaluation-plan.md
│   ├── baseline.md
│   ├── baseline-analysis.md
│   ├── advanced-architecture.md      # design only
│   ├── improvement-changelog.md
│   ├── phase3-analysis.md
│   ├── phase4-analysis.md
│   └── architecture-audit.md         # this file
├── benchmark/
│   ├── README.md
│   ├── cases/index.yaml
│   ├── ground_truth/*.yaml           # 12 files
│   └── repositories/cri-01-…cri-12-/ # tiny Python cases
├── src/cri/
│   ├── __init__.py
│   ├── __main__.py                   # → evaluation CLI
│   ├── models/                       # Finding, gold, metrics, run_meta, trajectory, verifier
│   ├── baseline/                     # collect, prompt, parse, llm, runner, variants, cli
│   ├── evaluation/                   # load, match, metrics, write, cli
│   ├── verify/                       # filters, evidence, postprocess, EXP-4 verifier
│   └── advanced/README.md            # stub: not implemented
├── tests/                            # evaluation, baseline, filters, evidence, verifier
└── outputs/
    ├── README.md
    ├── baseline-001/
    ├── exp1-baseline-abstention/
    ├── exp2-baseline-filters/
    ├── exp3-baseline-evidence/
    ├── exp2-abstention-filters/
    └── exp4-semantic-verifier/
```

Each LLM/post-process run directory typically contains `findings.json`, `run_meta.json`, `metrics.json`, and `raw/` (prompts, responses, logs). EXP-4 also has `qualitative_evidence.json`.

---

## 2. Current production / control pipeline

**Shipped / strongest measured system (keep):**

```
outputs/baseline-001/findings.json
        → EXP-2 apply_filters (unchanged)
        → outputs/exp2-baseline-filters/findings.json
        → cri-eval vs benchmark/ground_truth
```

- Frozen discovery run: `system_id=baseline`, `gpt-4o-mini`, temperature 0.
- Frozen post-process: deterministic filters only (no second LLM).
- EXP-1 abstention, EXP-3 evidence, EXP-4 verifier are **experiments**, not the control.

There is no implemented “advanced” pipeline (`src/cri/advanced/` is a README stub).

---

## 3. Exact baseline pipeline (repo → findings)

Entry: `cri-baseline` → `cri.baseline.runner.run_baseline` with variant `ORIGINAL` (`system_id=baseline`).

```
benchmark/repositories/<repo_id>/
    → list_repository_dirs (sorted directory names)
    → collect_repository
         include: *.py (including tests), POSIX-sorted relative paths
         exclude: README.md, non-.py, __pycache__, .git, venvs
         bundle: numbered lines, hashed (input_sha256)
         if len(bundle) > CRI_MAX_BUNDLE_CHARS: skip LLM, 0 findings (no truncation)
    → one HTTP LLM call (OpenAI or Anthropic)
         system: src/cri/baseline/prompt.py SYSTEM_PROMPT
         user: numbered bundle
         temperature 0, response_format json_object (OpenAI)
    → parse_findings
         extract JSON; validate Finding; force repository_id
         invalid items dropped (partial_invalid) or whole repo emptied
    → FindingList(system="baseline")
    → write outputs/<run>/findings.json, run_meta.json, raw/{prompts,responses,bundles,manifests}/
    → optional write_metrics → metrics.json
```

One LLM call **per repository**. No tools, no retries except implicit HTTP. JSON parse failure → zero findings for that repo (not fail-open).

Variant `baseline-abstention` uses a different prompt (`ABSTENTION`); same collection and parse path. That is EXP-1, not the frozen control.

---

## 4. Exact EXP-2 deterministic filter pipeline

Entry: `cri-postprocess --filters` or EXP-4’s first stage (`apply_filters`).

```
FindingList (typically baseline-001)
    → for each Finding:
         repo_root = repos_dir / repository_id
         first matching filter wins:
           1. error_handling_reraise
              except overlapping span; body is only Expr* + Raise (no Return/branch)
           2. state_concurrency_locked_write
              category must be state_concurrency;
              assignment in span lies inside with Lock()/RLock()/_lock
              (ThreadPoolExecutor is not a lock)
           3. testing_coverage_path_exercised
              except-body callee names ∩ calls in test_*.py / *_test.py
           4. testing_coverage_cites_test_file
              category testing_coverage and cited file is a test module
    → keep if no filter matches; log suppressions
```

On frozen baseline-001 this **suppressed cri-10 and cri-11** (re-raise). It **did not suppress cri-12** because that finding is `error_handling` on an assignment, not `state_concurrency`. It **did not suppress any of the 9 TPs**.

Filters are conservative by design (linear re-raise only; lock filter category-gated; tests must literally call the fallback name).

---

## 5. Exact evidence-processing pipeline

Entry: `cri-postprocess --evidence` → `cri.verify.evidence.apply_evidence` (EXP-3).

```
for each Finding:
    resolve file under repo_root
    missing file or line range outside file → DROP finding
    else:
        prefer named / overlapping function AST span
        skip leading module docstring / blank lines
        cap snippet at 8 lines around focus line
        replace evidence.quote with exact on-disk text
        set line_start/line_end to the repaired span
```

This is **not** in the current control pipeline (EXP-2 is filters only). EXP-3 improved quotes on cri-03/cri-04 but **did not change F1** (eval grounding already 1.0 via ±8 overlap). FPs were kept (valid local quotes).

EXP-4 separately records `verifier_evidence_in_source` (substring check of verifier quote); that is qualitative, not the scored evidence-grounding metric.

---

## 6. Current evaluation pipeline and matching logic

Entry: `cri-eval` or `write_metrics` after a run.

```
FindingList + gold YAML dir + repo roots + optional RunMeta
    → greedy match per gold present:true issue:
         hard: same repository_id, same category, normalized POSIX path
         location: predicted span overlaps gold.line ± 8
    → extra predictions: FP (or fp_red_herring if they match a present:false / red_herrings row)
    → unmatched gold: FN
    → among TPs: severity_accuracy, evidence_grounding_accuracy
    → evidence_grounded: file exists, lines in range, AND
         (cited range overlaps gold ±8  OR  quote ⊆ cited slice)
    → tokens/cost only if RunMeta has usage and declared USD/million prices
```

Primary reported metrics: micro/macro Finding F1, precision, recall, FP count, negative-repo FPR.

**Known metric artifacts:** empty predictions on a positive repo make precision `null`, so that repo can be **omitted from macro F1** (EXP-4 macro 1.0 was this, not a win). Evidence grounding saturates when ranges overlap gold even if the quote is a module docstring.

Gold is never read by baseline, filters, or the verifier.

---

## 7. Current benchmark structure

- Language: Python 3 only, `benchmark/cases/index.yaml` version 1.
- 12 repositories under `benchmark/repositories/`.
- Mix: 9 positives, 3 negatives; easy/medium/hard; FP trap cri-10 (logged re-raise).
- Cases are intentionally tiny (1–2 `.py` files) so a judge can read them.

| ID | Present? | Category (if present) |
|----|----------|------------------------|
| cri-01-bare-except | yes | error_handling |
| cri-02-unchecked-quantity | yes | input_validation |
| cri-03-leaked-file | yes | resource_lifecycle |
| cri-04-racy-balance | yes | state_concurrency |
| cri-05-untested-fallback | yes | testing_coverage |
| cri-06-silent-json-default | yes | error_handling |
| cri-07-toctou-inventory | yes | state_concurrency |
| cri-08-log-then-use-corrupt | yes | error_handling |
| cri-09-validate-then-mutate | yes | input_validation |
| cri-10-logged-reraise | no (red herring) | — |
| cri-11-clean-checkout | no | — |
| cri-12-locked-and-tested | no | — |

---

## 8. Current ground-truth schema

Pydantic `Issue` / `GroundTruthFile` (`src/cri/models/ground_truth.py`), YAML on disk:

- `repository_id`, `language`
- `issues[]`: `issue_id`, `category`, `severity`, `file`, `line`, `function_name?`, `description`, `why_reliability`, `expected_evidence`, `present`, `difficulty`
- `red_herrings[]`: same shape; used as FP anchors (`present: false`)

Negatives: `issues: []`. cri-10 also has `red_herrings: [cri-10-rh1]`.

Hand-authored; not generated at eval time.

---

## 9. Current finding schema

`Finding` / `FindingList` (`src/cri/models/finding.py`):

- `repository_id`
- `category`: error_handling | input_validation | resource_lifecycle | state_concurrency | testing_coverage
- `severity`: low | medium | high
- `file`, `line` and/or `line_start`/`line_end`, `function_name?`
- `description`
- `evidence`: `{ file, line_start, line_end, quote }`

`FindingList.system` is a string (`baseline`, `baseline-filters`, etc.).

Verifier output (EXP-4 only) is a separate schema: `decision` confirm|reject, `reason`, `confidence`, `evidence.{file,start_line,end_line,quote}`.

---

## 10. All CLI commands

Installed scripts (`pyproject.toml`):

```bash
cri-baseline --benchmark benchmark/repositories --output outputs/<run> \
  [--system baseline|baseline-abstention] [--ground-truth-dir …] [--no-eval] [--env-file .env]

cri-postprocess --source outputs/<run> --output outputs/<run2> \
  --system-id <id> --experiment-id <id> [--notes …] \
  --filters | --evidence | both \
  [--benchmark …] [--ground-truth-dir …]

cri-verify --source outputs/baseline-001 --output outputs/<run> \
  [--benchmark …] [--ground-truth-dir …] [--env-file .env] [--no-eval]
  # EXP-4: filters then one LLM call per survivor

cri-eval --predictions outputs/<run>/findings.json \
  [--ground-truth-dir …] [--repos-dir …] [--run-meta …] [--output metrics.json]
```

`python -m cri` currently invokes **eval**, not baseline (`src/cri/__main__.py`).

Env: `CRI_LLM_PROVIDER`, `CRI_LLM_MODEL`, `CRI_LLM_TEMPERATURE`, `CRI_LLM_MAX_TOKENS`, `CRI_MAX_BUNDLE_CHARS`, `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`, optional price vars. Keys are not written to artifacts.

README documents baseline, abstention, and postprocess; it does **not** currently list `cri-verify`.

---

## 11. Experiment artifacts and representation

| Directory | system_id | How produced | Role |
|-----------|-----------|--------------|------|
| `outputs/baseline-001/` | baseline | LLM, 12 calls | Frozen discovery control |
| `outputs/exp1-baseline-abstention/` | baseline-abstention | LLM, different prompt | EXP-1; not control |
| `outputs/exp2-baseline-filters/` | baseline-filters | Post-process filters on baseline-001 | **Strongest measured** |
| `outputs/exp3-baseline-evidence/` | baseline-evidence | Post-process evidence on baseline-001 | Quote repair; F1 unchanged |
| `outputs/exp2-abstention-filters/` | baseline-abstention-filters | Filters on EXP-1 | Diagnostic |
| `outputs/exp4-semantic-verifier/` | baseline-filters-verifier | Filters + 10 verifier LLM calls | **Rejected** (recall 0) |

Common files: `findings.json` (FindingList), `run_meta.json` (model, times, per-repo tokens/status, `parent_run`, `experiment_id`), `metrics.json` (EvalMetrics). Raw trees store prompts/responses/hashes. EXP-4 adds `raw/verifier_log.json`, `raw/parsed/`, `qualitative_evidence.json`.

Metrics are never invented; missing usage/cost stay `null`.

---

## 12. Current README claims

- Competition question: agent vs simple baseline on reliability issues, same cases, evidence, changelog, trajectories (trajectories **not implemented** in any runner).
- Status Phase 4: strongest system is `exp2-baseline-filters`; EXP-4 rejected; investigator not implemented.
- Layout omits `src/cri/verify/` even though that is where filters/verifier live.
- Commands omit `cri-verify`.
- Non-goals: no UI, auth, cloud, DB, extra agent frameworks.

---

## 13. Current improvement changelog

(`docs/improvement-changelog.md`, abbreviated):

| ID | Decision |
|----|----------|
| baseline-001 | **Keep** frozen control (F1 0.857, recall 1.0, FP 3) |
| EXP-1 abstention | Keep as variant only (FPR 0, recall 0.778) |
| EXP-2 filters | **Keep** as stronger candidate (F1 0.947, recall 1.0, FP 1) |
| EXP-3 evidence | Keep as optional layer (F1 unchanged) |
| EXP-2 on abstention | Diagnostic only |
| EXP-4 verifier | **Reject** (recall 0; 0 confirms / 10 rejects) |

---

## 14. Which components are deterministic

- File collection, bundling, hashes, char-cap skip
- JSON parse/validation of findings and verifier schema
- EXP-2 filters (AST)
- EXP-3 evidence repair (AST + file slice)
- Matching, metrics, CLI glue, artifact I/O
- Filter/evidence/verifier **routing** (what to call, fail-open on verifier parse error)

---

## 15. Which components use an LLM

- Baseline / abstention: **one completion per repository** (discovery)
- EXP-4 verifier: **one completion per filter-survivor** (10 calls on baseline-001); no tools
- Not LLM: filters, evidence repair, eval

No tool-using agent, no multi-step trajectory, no RAG.

---

## 16. Which components are production / control

| Piece | Status |
|-------|--------|
| `baseline-001` findings | Frozen **discovery** control |
| EXP-2 `apply_filters` | Frozen **precision** layer; **current best system** |
| `cri-eval` + gold | Frozen **scoring** |
| EXP-1 / EXP-3 / EXP-4 | Experiments; EXP-4 not shipped |
| `src/cri/advanced` | Design docs only |

---

## 17. Architectural weaknesses that could block a genuinely advanced solution

1. **Recall is already 1.0 on this 12-case synthetic set.** A full investigator that re-discovers issues has little measured room and a large risk of FPs (baseline already one-finding-per-repo). “Advanced = more search” is the wrong lever here.
2. **Category-gated filters miss cri-12.** The leftover FP is semantic (`error_handling` on a guarded, locked assignment). A lock filter that only runs for `state_concurrency` cannot see it. Expanding filters carelessly could start eating TPs.
3. **EXP-4 showed context ≠ verification.** The verifier already received the whole tiny repo and still default-rejected every TP. Adding tools that only fetch more text would likely repeat that failure unless **call selection, decision prior, and fail-open** change.
4. **Evidence metric is saturated** (±8 overlap). An advanced system can look better on F1 while still quoting docstrings unless a stricter evidence check is added later (explicitly out of scope for this audit’s “do not modify eval”).
5. **Macro F1 is fragile** when a repo has no predictions. Leaderboard narratives can lie (EXP-4).
6. **No trajectories in the control path.** Competition requires agent traces; the winning measured system is LLM-once + AST. Any agentic add-on must log `TrajectoryLog` (schema exists, unused).
7. **Benchmark ceiling / transfer.** Tiny Python toys; an agent specialized to 12 cases may not generalize. Abstention already showed that “be more careful” drops hard true issues (cri-09).
8. **Advanced design doc assumes explore → investigate → verify**, but measured need is **precision on leftovers after a strong one-shot finder**. Building the full diagram would optimize the wrong bottleneck.
9. **Production pipeline is two disconnected CLIs** (`cri-baseline` then `cri-postprocess`). Easy to eval the raw baseline by mistake.
10. **Verifier fail-open vs default-REJECT conflict.** Parse errors keep findings; the prompt told the model to reject by default. The prompt dominated.

---

## Question: smallest genuinely agentic capability likely to help without sacrificing recall

**Not** a repository-wide investigator, **not** EXP-4-style verify-all-survivors with default REJECT, **not** RAG.

The measured gap after EXP-2 is **one leftover semantic FP** (cri-12): a finding whose **claimed category does not match the cited construct** (error_handling on a store under `with _lock` plus `if available < n`). Discovery is already complete. EXP-4 failed because it applied a reject-biased LLM to **all** remaining true positives.

**Smallest genuinely agentic add-on:**

A **gated, fail-open, single-tool semantic check** on a **subset** of filter-survivors:

1. **Deterministic gate (not an LLM):** invoke the agent only if the finding’s category is inconsistent with the cited AST (example: `error_handling` but the span is not an `except` / does not contain `return` of a failure sentinel in an except handler; or `state_concurrency` already covered by the lock filter). This should fire on cri-12-like leftovers and **should not fire** on cri-01 (bare except + paid return), cri-06 (`return {}`), cri-08 (`return raw`), races, etc.
2. **One tool, one call:** e.g. `enclosing_block(file, line)` returning the enclosing `with` / `if` / `try` text from disk (or AST). The model does not search the repo for new bugs.
3. **Decision prior: CONFIRM unless the tool output shows a guard/lock that blocks the claimed failure.** Reject only then. Parse/LLM failure **keeps** the finding (fail-open), unlike EXP-4’s prompt.
4. **Cap:** at most one extra LLM call per gated finding (expected 0–1 per repo on this benchmark).
5. **Log a trajectory** (instruction, tool args, tool result, decision) so the competition artifact exists without a multi-agent graph.

Why this is the smallest *agentic* step: it adds a bounded **action** (tool) plus a **conditional LLM**, not more discovery. Why it is likely to preserve recall: TPs with matching syntax never enter the LLM. Why it might improve precision: cri-12 is exactly a category/construct mismatch plus a visible guard.

If that gate cannot be specified without overfitting cri-12, **do not add an LLM**; extend deterministic filters with a conservative “error_handling claim on an assignment that is dominated by a preceding `if` inside `with lock`” rule instead. That would not be agentic, but EXP-2 showed deterministic precision is the reliable lever.

**Do not implement either until a gate is written down with explicit non-suppression cases for all 9 TPs.**
