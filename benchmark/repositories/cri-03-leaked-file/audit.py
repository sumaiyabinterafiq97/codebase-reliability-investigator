"""Write an audit line; handle is not closed if write fails."""


def append_audit(path: str, line: str) -> bool:
    handle = open(path, "a", encoding="utf-8")
    try:
        handle.write(line + "\n")
        handle.close()
        return True
    except OSError:
        return False
