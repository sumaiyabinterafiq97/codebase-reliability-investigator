 # Advanced system (architecture only — not implemented)

## Pipeline

```
Repository
  → Repository exploration     (deterministic)
  → Investigation              (LLM + tools)
  → Evidence collection        (tools; LLM only to choose what to collect)
  → Finding verification       (LLM or deterministic checks)
  → Severity / prioritization  (LLM, constrained by taxonomy rules)
  → Final report               (deterministic assemble → FindingList)
```

Cap: **two LLM roles** (Investigator, Verifier). Everything else should be code.

---

### 1. Repository exploration

**Responsibility:** List files, sizes, entrypoints (`if __name__`, public functions), test files, imports.

**Why:** The investigator must not guess paths; exploration is cheap and complete on 12 tiny repos.

**Kind:** **Deterministic** (filesystem walk, optional `ast` parse for function names).

**Evidence:** `file_manifest.json` (paths, line counts, symbol index).

---

### 2. Investigation

**Responsibility:** Propose candidate issues in taxonomy categories; call tools to read slices of code.

**Why:** Localization and category choice need language judgment; this is the core “agent.”

**Kind:** **LLM agent** with a small tool set (see below). Bounded steps (e.g. max 12 tool calls per repo).

**Evidence:** Trajectory: thoughts, tool names, args, results, retries.

---

### 3. Evidence collection

**Responsibility:** For each candidate, attach an exact quote and line range that exists on disk.

**Why:** Grounding is a competition requirement; models hallucinate snippets.

**Kind:** **Deterministic** `read_file(path, start, end)` and `search(pattern)`. The LLM only selects ranges; the quote is **sliced from disk**, never from the model.

**Evidence:** `Evidence` objects with file, lines, quote.

---

### 4. Finding verification

**Responsibility:** Drop candidates that fail checks: file missing, quote not in file, category mismatch with cited code, or (for `testing_coverage`) tests actually covering the branch.

**Why:** Precision is the baseline’s likely weakness; verification is the main expected F1 lever.

**Kind:** **Deterministic first** (quote-in-file, path exists). **LLM verifier** only for “is this actually a reliability issue under taxonomy?” — one yes/no+reason per candidate. Optional later: **run tests** with `pytest` for cases that include tests.

**Evidence:** `verification: pass|fail` plus reason; discarded candidates stay in the trajectory, not in `FindingList`.

---

### 5. Severity / prioritization

**Responsibility:** Map remaining findings to `low|medium|high` using taxonomy rules.

**Why:** Severity accuracy is a scored metric; investigator prose is inconsistent.

**Kind:** **LLM** with a **rubric prompt** (taxonomy severity bullets). No extra agent identity required (can be the verifier’s second pass).

**Evidence:** Chosen severity + one-sentence rubric citation.

---

### 6. Final report

**Responsibility:** Emit `FindingList` JSON only.

**Kind:** **Deterministic** serialization.

**Evidence:** The findings file consumed by `cri-eval`.

---

## Tools (proposed)

| Tool | Kind | Purpose |
|------|------|---------|
| `list_files` | Deterministic | Manifest |
| `read_file` | Deterministic | Grounded quotes |
| `grep` | Deterministic | Find except/open/Lock/test defs |
| `ast_symbols` | Deterministic | Function/class locations |
| `run_pytest` | Deterministic | Optional; only repos with tests |

No web search. No issue-tracker APIs.

## What is not an LLM agent

Exploration, evidence slicing, pytest, JSON emit, eval matching.

## Human checkpoints (if used)

Only for debugging during development (approve a tool allowlist). Production eval should be unattended. If a checkpoint is used, log it in the trajectory.

## Trajectory schema (later)

See `src/cri/models/trajectory.py` — instructions, actions, tool results, retries, feedback, checkpoints.
