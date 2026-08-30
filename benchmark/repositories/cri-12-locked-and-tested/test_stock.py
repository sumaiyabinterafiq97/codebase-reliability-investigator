from stock import reserve, stock


def test_reserve_ok():
    stock["widget"] = 2
    assert reserve("widget", 1) is True
    assert stock["widget"] == 1


def test_reserve_insufficient():
    stock["widget"] = 0
    assert reserve("widget", 1) is False
    assert stock["widget"] == 0
