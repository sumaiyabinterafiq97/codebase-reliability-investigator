# Baseline (implemented)

Single-prompt control group. No tools, no second model, no RAG, no agent loop.

## Pipeline

```
Repository directory
    → collect *.py (stable POSIX path order; include tests)
    → numbered file bundle (full files; no truncation)
    → one LLM call (JSON object)
    → validate into FindingList
    → outputs/<run_id>/
```

Parse failure, schema failure, or HTTP error → **zero findings for that repo**, with `parse_status` and `error` in `run_meta.json`. Invalid items in an otherwise valid list are dropped and counted in `invalid_finding_count` (`partial_invalid`). This is explicit, not silent success.

`repository_id` on each finding is **forced** to the directory being scanned so a model typo cannot cross-contaminate repos.

## Fair input

- **Included:** all `.py` files under the repo, including `test_*.py`.
- **Excluded:** `README.md`, other non-Python files, `__pycache__`, `.git`, virtualenvs. Listed in `raw/manifests/<repo>.json`.
- **Order:** repository-relative POSIX paths, lexicographic.
- **Line numbers:** 1-based, matching the file on disk.
- **Cap:** `CRI_MAX_BUNDLE_CHARS` (default 200000). If the bundle is larger, the LLM is **not** called and the repo is `over_limit`. The 12 synthetic repos are far below this; we do not shrink them to handicap the baseline.

Exact bundles are copied to `raw/bundles/` and hashed (`input_sha256`) for reproduction.

## Model configuration (environment)

| Variable | Role | Default |
|----------|------|---------|
| `CRI_LLM_PROVIDER` | `openai` or `anthropic` | `openai` |
| `CRI_LLM_MODEL` | Model id | `gpt-4o-mini` / `claude-3-5-haiku-latest` |
| `CRI_LLM_TEMPERATURE` | Sampling | `0` |
| `CRI_LLM_MAX_TOKENS` | Completion cap | `4096` |
| `CRI_LLM_BASE_URL` | API host | provider default |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Auth | required |
| `CRI_USD_PER_MILLION_PROMPT_TOKENS` | Optional declared price | unset → cost `null` |
| `CRI_USD_PER_MILLION_COMPLETION_TOKENS` | Optional declared price | unset → cost `null` |

Credentials are never written to run artifacts. Token counts are stored only if the provider returns them. HTTPS uses `certifi` CA certificates.

## CLI

```bash
cp .env.example .env   # set OPENAI_API_KEY
cri-baseline --benchmark benchmark/repositories --output outputs/baseline-001
cri-eval --predictions outputs/baseline-001/findings.json \
  --run-meta outputs/baseline-001/run_meta.json \
  --output outputs/baseline-001/metrics.json
```

`cri-baseline` also writes `metrics.json` unless `--no-eval`.

## Why this is a fair baseline

It is the obvious “paste the whole small repo into a capable LLM” system. It sees production code and tests. Advanced-system gains must come from investigation structure, not from hiding files.
