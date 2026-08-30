from threading import Lock

_lock = Lock()
stock = {"widget": 5}


def reserve(sku: str, n: int = 1) -> bool:
    with _lock:
        available = stock.get(sku, 0)
        if available < n:
            return False
        stock[sku] = available - n
        return True
