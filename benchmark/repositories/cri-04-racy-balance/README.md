# cri-04-racy-balance

`credit` reads and writes `balance_cents` without synchronization while `apply_credits` uses a thread pool.
