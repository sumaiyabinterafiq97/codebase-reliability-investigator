"""Warehouse stock: check, then decrement, no lock."""

from threading import Thread

stock = {"widget": 1}


def reserve(sku: str, n: int = 1) -> bool:
    if stock.get(sku, 0) >= n:
        # Another thread can reserve the same unit here.
        stock[sku] = stock[sku] - n
        return True
    return False


def two_customers() -> list[bool]:
    results: list[bool] = [False, False]

    def buy(i: int) -> None:
        results[i] = reserve("widget", 1)

    t1 = Thread(target=buy, args=(0,))
    t2 = Thread(target=buy, args=(1,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    return results
