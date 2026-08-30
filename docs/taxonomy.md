# Reliability taxonomy (v1, narrow)

Only five categories. A finding **must** name one of these. Anything else is out of scope and scores as a false positive if reported.

Severity: `low` | `medium` | `high`.

---

## 1. `error_handling`

**Qualifies:** Control flow that hides, swallows, or continues after a failure in a way that can produce wrong results, lost errors, or an inconsistent program state. Includes bare `except`, returning sentinel success after failure, and catching exceptions then using invalid data.

**Does not qualify:** Broad `except Exception` that **logs and re-raises**; catching a **specific** expected exception and returning a documented fallback that callers can distinguish; comments about adding retries without a failing path.

**Examples (in benchmark):** bare `except:`; JSON load failure replaced with `{}` then treated as real config; exception logged but corrupt object still returned.

**Severity:**
- **high** — failure can look like success to callers, or corrupt persistent/domain state
- **medium** — failure is lost but impact is limited to one request/operation
- **low** — noisy or incomplete handling with little behavioral impact

**Evidence required:** File + line range of the handler (or missing handler), the failure that is caught/ignored, and what happens next (return value, continued use of data). Quote the except/return.

---

## 2. `input_validation`

**Qualifies:** Untrusted or external values used in domain operations without checks that prevent invalid states (empty, negative, wrong type after parse, missing required fields) where that invalid state can break invariants.

**Does not qualify:** Missing validation on **internal** helpers when a public boundary already validates; lack of a web framework schema when the function is not an external boundary; “should use pydantic” with no actual invalid-input path.

**Examples:** order quantity not checked before inventory mutation; string split/derived field used as int after only validating the original string.

**Severity:**
- **high** — can violate money, inventory, authz-adjacent invariants, or crash a shared service path
- **medium** — bad input causes local failure or wrong one-off result
- **low** — cosmetic or already rejected by the runtime before harm

**Evidence required:** The entrypoint that accepts the value, the missing check (or check that does not cover the derived value), and the subsequent use.

---

## 3. `resource_lifecycle`

**Qualifies:** Handles (files, sockets, locks held in a way that won’t release on error) acquired and not released on some path; double-close is **not** required if the leak/error path is the issue.

**Does not qualify:** Short-lived scripts that open a file and rely on process exit **if** there is no exception path that skips close while the process continues; using `with` correctly; “should use a connection pool” without a leak.

**Examples:** `open()` without `close`/`with` on an error path that still returns to the caller.

**Severity:**
- **high** — leak in a loop or request handler (process-lifetime accumulation)
- **medium** — leak on error path in a library function
- **low** — one-shot CLI where process exit follows immediately (still an issue if the function is reusable)

**Evidence required:** Acquire site, missing release, and the path (including exception path) that skips cleanup.

---

## 4. `state_concurrency`

**Qualifies:** Shared mutable state accessed from concurrent contexts without adequate synchronization, or check-then-act races (TOCTOU) on shared resources.

**Does not qualify:** Single-threaded scripts with no threads/async tasks/shared process state; “not using asyncio” as a style note; a `Lock` used correctly around the critical section.

**Examples:** unsynchronized balance updates; inventory check then decrement without holding a lock.

**Severity:**
- **high** — lost updates on money/inventory-like state
- **medium** — races on caches/counters with limited blast radius
- **low** — theoretical race in tests-only code

**Evidence required:** Shared object, concurrent entrypoints (thread/async/multiprocessing), missing or too-narrow lock, and the interleaving that breaks an invariant.

---

## 5. `testing_coverage`

**Qualifies:** Production logic whose **failure or recovery path** is load-bearing (fallback, retry, degraded mode) but **no test** exercises that path. This is a reliability issue because the path can rot silently.

**Does not qualify:** Missing tests for trivial getters; 100% coverage demands; “add more unit tests” without naming an untested failure path; tests that exist but use mocks if they still hit the branch.

**Examples:** fallback supplier used on timeout with tests only for the happy path.

**Severity:**
- **high** — untested recovery for a critical dependency
- **medium** — untested error branch in non-critical helper
- **low** — missing assertion on an already-invoked path

**Evidence required:** The production branch (file/lines), and confirmation that tests do not call it (test file names + what they actually assert). Absence of tests is evidence only together with the identified branch.

---

## Out of scope (do not report)

Security exploits, CWE catalogs, performance, API design taste, typing/style, documentation, CI config, dependency CVEs, “this should be a microservice.”
