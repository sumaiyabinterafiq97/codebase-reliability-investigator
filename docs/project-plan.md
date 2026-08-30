# Project plan — Codebase Reliability Investigator

## Competition question

Can an agent identify **important software reliability issues** in a codebase **more accurately** and **with better evidence** than a **reasonable simple baseline**?

“Important” means issues in the [taxonomy](taxonomy.md) that can cause incorrect behavior, silent failure, data loss, resource leaks, or untested failure paths — not style, naming, or generic “best practice” comments.

## What we will build (later phases)

| Piece | Role |
|-------|------|
| **Benchmark** | 12 small synthetic Python repos with deterministic ground truth (this phase) |
| **Baseline** | One-shot LLM over concatenated source files → structured findings |
| **Advanced** | Explore → investigate → evidence → verify → severity → report |
| **Eval** | Same cases, Finding F1 plus evidence/severity/cost metrics |
| **Artifacts** | Improvement changelog + agent trajectories |

## Architecture (intentionally small)

```
benchmark/repositories/<id>/     input code
benchmark/ground_truth/<id>.yaml  gold issues (or empty list)

src/cri/models/                  Finding, GroundTruth, RunReport schemas
src/cri/evaluation/              Match predicted findings to gold; compute metrics

src/cri/baseline/                NOT IMPLEMENTED YET
src/cri/advanced/                NOT IMPLEMENTED YET
```

Both systems must emit the same `FindingList` JSON so evaluation is system-agnostic.

CLI-first: `cri-eval` exists as a thin entrypoint; `cri-baseline` / `cri-investigate` come later.

## Why synthetic, small repos

Judges must be able to read a case in minutes. Real OSS is too large, noisy, and ambiguous for a 12-case gold set we can defend. Synthetic cases let us **place** issues, **omit** issues (negatives), and **bait** false positives.

## Sprint constraints (Phase 7)

**Do:** Python, pydantic, pytest, local CLI, file-based I/O, optional later: stdlib `ast`, subprocess tests.

**Do not:** frontend, auth, cloud, databases, multi-service deploy, LangGraph-style orchestration unless a later experiment justifies it, extra taxonomies (security CVE hunting, performance, a11y).

**Agent count cap (proposal):** baseline = 0 extra agents (one prompt). Advanced = at most **two** LLM roles (investigator + verifier) plus deterministic tools. More roles need changelog justification.

## Deliverable sequence (stop after this phase)

1. ~~Taxonomy, benchmark, schemas, eval matcher~~ (this phase)
2. Baseline runner + first real eval numbers
3. Advanced tools + investigator + verifier
4. Compare on the **same** 12 cases; iterate via changelog
5. Package trajectories and reproducibility notes

## Reproducibility (when runners exist)

- Pin model name, temperature, seed if the API allows
- Store raw prompts, completions, and tool traces under `outputs/<run_id>/`
- Never edit ground truth to fit a model; change gold only for factual case bugs
