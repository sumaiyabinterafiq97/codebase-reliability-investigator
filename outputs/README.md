# Run artifacts

Real LLM and post-process runs. Do not invent metrics.

| Run | System | Notes |
|-----|--------|--------|
| [baseline-001](baseline-001/) | baseline | Frozen control |
| [exp1-baseline-abstention](exp1-baseline-abstention/) | baseline-abstention | EXP-1 new LLM run |
| [exp2-baseline-filters](exp2-baseline-filters/) | baseline-filters | EXP-2 on baseline-001, no LLM |
| [exp3-baseline-evidence](exp3-baseline-evidence/) | baseline-evidence | EXP-3 on baseline-001, no LLM |
| [exp4-semantic-verifier](exp4-semantic-verifier/) | baseline-filters-verifier | EXP-4; rejected (recall 0) |
| [exp5-gated-semantic](exp5-gated-semantic/) | baseline-filters-gated-verifier | EXP-5 gated semantic/agentic PoC; same score as EXP-2, not control |
