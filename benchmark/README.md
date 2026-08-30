# CRI synthetic benchmark

12 tiny Python repositories. Ground truth is **hand-written** in `ground_truth/`. Do not regenerate gold with an LLM.

## Design mix

| ID | Pattern | Category | Difficulty | Present? |
|----|---------|----------|------------|----------|
| cri-01-bare-except | Bare `except:` swallows failures | error_handling | easy | yes |
| cri-02-unchecked-quantity | Negative/zero quantity mutates inventory | input_validation | easy | yes |
| cri-03-leaked-file | `open` without close on error path | resource_lifecycle | easy | yes |
| cri-04-racy-balance | Threads, no lock on balance | state_concurrency | medium | yes |
| cri-05-untested-fallback | Fallback path never tested | testing_coverage | medium | yes |
| cri-06-silent-json-default | Parse fail → `{}` treated as config | error_handling | medium | yes |
| cri-07-toctou-inventory | Check-then-decrement, no lock | state_concurrency | hard | yes |
| cri-08-log-then-use-corrupt | Log error, still return/use bad object | error_handling | hard | yes |
| cri-09-validate-then-mutate | Validate raw string; derived field unchecked | input_validation | hard | yes |
| cri-10-logged-reraise | Broad except **re-raises** (FP bait) | — | hard | **no** |
| cri-11-clean-checkout | Validation + `with` + specific except | — | easy | **no** |
| cri-12-locked-and-tested | Lock + tests for error path | — | medium | **no** |

## Intended naive-LLM trap

**cri-10-logged-reraise:** `except Exception` looks like “bad error handling.” It logs and **re-raises**, which the taxonomy explicitly allows. A one-shot model often flags it anyway.

## Languages

All cases are **Python 3**. One language keeps the sprint and the matcher simple. Expanding to a second language is a later experiment (changelog), not v1.

## How to add a case later

1. Add `repositories/<id>/` with a short README and source
2. Add `ground_truth/<id>.yaml` (empty `issues: []` for negatives)
3. Append a row to `cases/index.yaml`
