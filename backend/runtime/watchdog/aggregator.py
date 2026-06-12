from dataclasses import dataclass

from runtime.watchdog.states import H


class WatchdogAggregator:
    def __init__(self):
        pass

    def run(self):
        return True


@dataclass
class HysteresisCounters:
    critical_infra_consecutive: int = 0
    soft_fail_consecutive: int = 0


class Overrides:
    def __init__(self, *args, **kwargs):
        pass


class Tunables:
    def __init__(self, *args, **kwargs):
        pass


@dataclass
class Decision:
    target_state: H = H.HEALTHY
    tier: int = 0


def evaluate(*args, **kwargs):
    return Decision()
