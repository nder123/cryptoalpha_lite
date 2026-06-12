from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeHealthSnapshot:
    state: str = "UNKNOWN"
    stale: bool = True
    stale_reason: str | None = "compat"
    reasons: tuple[str, ...] = ()
    since: str | None = None


class RuntimeHealthReader:
    def __init__(self, *args, **kwargs):
        pass

    def read(self):
        return RuntimeHealthSnapshot()


_default_reader = RuntimeHealthReader()


def get_default_reader():
    return _default_reader


def set_default_reader_for_tests(reader):
    global _default_reader
    _default_reader = reader or RuntimeHealthReader()
