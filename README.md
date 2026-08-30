# Codebase Reliability Investigator (CRI)

Competition project for the **micro1 Frontier Engineering Challenge 2026**.

## Question

Can an agent identify important software reliability issues in a codebase more accurately and with better evidence than a reasonable simple baseline?

## Status (Phase 5)

- Strongest measured system (control): [`outputs/exp2-baseline-filters`](outputs/exp2-baseline-filters/) (precision 0.90, recall 1.0, micro F1 0.947)
- Frozen discovery run: [`outputs/baseline-001`](outputs/baseline-001/)
- EXP-4 verifier: [`outputs/exp4-semantic-verifier`](outputs/exp4-semantic-verifier/) — **rejected** (recall 0); see [docs/phase4-analysis.md](docs/phase4-analysis.md)
- EXP-5 gated semantic review: [`outputs/exp5-gated-semantic`](outputs/exp5-gated-semantic/) — experimental/agentic proof-of-concept; **same scored result as EXP-2**, not a new control; see [docs/phase5-analysis.md](docs/phase5-analysis.md)
- Advanced investigator: **not implemented**; no further LLM verifier experiment is claimed

## Layout

```
docs/                 Design, taxonomy, evaluation, baseline, analysis
benchmark/            Synthetic repositories, cases, ground truth
src/cri/baseline/     File collection, one LLM call, artifacts
src/cri/evaluation/   Finding matching and metrics
tests/                Unit tests (LLM calls mocked)
outputs/              Real run artifacts (not invented)
```

## Commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # set OPENAI_API_KEY
pytest

cri-baseline --benchmark benchmark/repositories --output outputs/baseline-001

cri-baseline --system baseline-abstention \
  --benchmark benchmark/repositories \
  --output outputs/exp1-baseline-abstention

cri-postprocess --source outputs/baseline-001 --output outputs/exp2-baseline-filters \
  --filters --system-id baseline-filters --experiment-id EXP-2-filters

cri-postprocess --source outputs/baseline-001 --output outputs/exp3-baseline-evidence \
  --evidence --system-id baseline-evidence --experiment-id EXP-3-evidence

cri-verify --source outputs/baseline-001 --output outputs/exp4-semantic-verifier

cri-verify --gated --source outputs/baseline-001 --output outputs/exp5-gated-semantic
```

`cri-verify` and `cri-verify --gated` call an LLM and require `OPENAI_API_KEY` in `.env` (copy from `.env.example`; do not commit `.env`). The measured EXP-4 and EXP-5 artifacts already exist under `outputs/`; do not rerun them to reproduce the reported scores.

Score an **existing** predictions file without an LLM:

```bash
cri-eval \
  --predictions outputs/exp2-baseline-filters/findings.json \
  --run-meta outputs/exp2-baseline-filters/run_meta.json \
  --output /tmp/exp2-metrics-check.json
```

That command only reads findings and gold; it does not call a model. The frozen measured metrics remain in each run’s `metrics.json` (for example `outputs/exp2-baseline-filters/metrics.json`). The same workflow applies to EXP-5 predictions (same score as EXP-2, not a better control):

```bash
cri-eval \
  --predictions outputs/exp5-gated-semantic/findings.json \
  --run-meta outputs/exp5-gated-semantic/run_meta.json \
  --output /tmp/exp5-metrics-check.json
```

## Design docs

| Doc | Purpose |
|-----|---------|
| [docs/project-plan.md](docs/project-plan.md) | Scope and constraints |
| [docs/taxonomy.md](docs/taxonomy.md) | What counts as an issue |
| [docs/evaluation-plan.md](docs/evaluation-plan.md) | Metrics and matching |
| [docs/baseline.md](docs/baseline.md) | Single-prompt baseline |
| [docs/phase4-analysis.md](docs/phase4-analysis.md) | EXP-4 verifier (rejected) |
| [docs/phase5-analysis.md](docs/phase5-analysis.md) | EXP-5 gated review (same score as EXP-2; not control) |
| [docs/advanced-architecture.md](docs/advanced-architecture.md) | Advanced system (design only) |
| [docs/improvement-changelog.md](docs/improvement-changelog.md) | Experiment log |
| [benchmark/README.md](benchmark/README.md) | Case catalog |

## Non-goals (this sprint)

No web UI, auth, cloud deploy, database, or extra agent frameworks. CLI-first.
