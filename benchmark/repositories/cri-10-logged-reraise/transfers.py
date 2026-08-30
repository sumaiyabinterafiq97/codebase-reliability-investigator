import logging

log = logging.getLogger("transfers")


def send(amount_cents: int) -> str:
    if amount_cents <= 0:
        raise ValueError("amount must be positive")
    if amount_cents > 1_000_000_00:
        raise RuntimeError("limit")
    return f"sent:{amount_cents}"


def transfer(amount_cents: int) -> str:
    try:
        return send(amount_cents)
    except Exception:
        log.exception("transfer failed amount=%s", amount_cents)
        raise
