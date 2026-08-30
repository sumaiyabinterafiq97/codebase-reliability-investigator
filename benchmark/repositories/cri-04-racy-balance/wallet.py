"""Shared wallet updated from many threads with no lock."""

from concurrent.futures import ThreadPoolExecutor

balance_cents = 0


def credit(amount_cents: int) -> None:
    global balance_cents
    current = balance_cents
    balance_cents = current + amount_cents


def apply_credits(amounts: list[int], workers: int = 8) -> int:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(credit, amounts))
    return balance_cents
