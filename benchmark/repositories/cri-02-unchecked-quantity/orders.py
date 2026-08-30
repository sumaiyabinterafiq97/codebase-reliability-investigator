"""Inventory mutation without quantity checks."""

inventory = {"sku-1": 10}


def apply_order(sku: str, quantity: int) -> None:
    inventory[sku] = inventory.get(sku, 0) - quantity
