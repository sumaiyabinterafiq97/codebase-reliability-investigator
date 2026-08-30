"""Charge primary processor; fall back to secondary on timeout."""


class TimeoutError_(Exception):
    pass


def charge_primary(amount_cents: int) -> str:
    if amount_cents < 0:
        raise ValueError("amount")
    return f"primary:{amount_cents}"


def charge_secondary(amount_cents: int) -> str:
    return f"secondary:{amount_cents}"


def pay(amount_cents: int, primary_ok: bool = True) -> str:
    if not primary_ok:
        raise TimeoutError_("primary down")
    return charge_primary(amount_cents)


def checkout(amount_cents: int, primary_ok: bool = True) -> str:
    try:
        return pay(amount_cents, primary_ok=primary_ok)
    except TimeoutError_:
        return charge_secondary(amount_cents)
