import logging

log = logging.getLogger("billing")


def parse_customer(raw: dict) -> dict:
    try:
        account_id = raw["account_id"]
        cents = int(raw["balance_cents"])
        return {"account_id": account_id, "balance_cents": cents}
    except (KeyError, TypeError, ValueError) as exc:
        log.error("parse failed: %s raw=%s", exc, raw)
        return raw


def debit(raw: dict, amount_cents: int) -> dict:
    customer = parse_customer(raw)
    customer["balance_cents"] = customer["balance_cents"] - amount_cents
    return customer
