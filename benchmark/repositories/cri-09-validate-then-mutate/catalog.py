"""SKU payload looks like 'sku:qty'. Only the whole string is checked."""


def parse_line(item: str) -> tuple[str, int]:
    if not isinstance(item, str) or not item.strip():
        raise ValueError("empty item")
    sku, qty_s = item.split(":")
    return sku, int(qty_s)


def restock(item: str, inventory: dict[str, int]) -> None:
    sku, qty = parse_line(item)
    inventory[sku] = inventory.get(sku, 0) + qty
