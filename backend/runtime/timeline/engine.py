class TimelineSources:
    @classmethod
    def for_repo(cls, *args, **kwargs):
        return cls()


def correlate_incident(*args, **kwargs):
    return None


def filter_by_severity(events, *args, **kwargs):
    return iter(events)


def filter_by_source(events, *args, **kwargs):
    return iter(events)


def filter_by_window(events, *args, **kwargs):
    return iter(events)


def merge(*args, **kwargs):
    return iter(())
