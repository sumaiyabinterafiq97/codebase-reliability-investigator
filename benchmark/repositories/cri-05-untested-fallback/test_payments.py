from payments import checkout


def test_happy_path():
    assert checkout(100) == "primary:100"
