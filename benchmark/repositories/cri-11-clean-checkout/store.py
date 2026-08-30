from pathlib import Path


def validate_qty(quantity: int) -> None:
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
        raise ValueError("quantity must be a positive int")


def append_receipt(path: str, text: str) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text + "\n")


def charge(amount_cents: int) -> str:
    try:
        if amount_cents < 1:
            raise ValueError("amount")
        return f"paid:{amount_cents}"
    except ValueError:
        raise


def checkout(path: str, quantity: int, amount_cents: int) -> str:
    validate_qty(quantity)
    ref = charge(amount_cents)
    append_receipt(path, ref)
    return ref
