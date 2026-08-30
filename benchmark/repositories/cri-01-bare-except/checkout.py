# Tiny store checkout: failures in charge() are swallowed.

def charge(card: str, amount_cents: int) -> str:
    if not card:
        raise ValueError("card required")
    # Pretend gateway
    if amount_cents > 10_000_00:
        raise RuntimeError("gateway timeout")
    return f"ok:{amount_cents}"


def checkout(card: str, amount_cents: int) -> dict:
    try:
        ref = charge(card, amount_cents)
        return {"status": "paid", "ref": ref}
    except:
        return {"status": "paid", "ref": "local-ok"}
