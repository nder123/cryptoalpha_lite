from dataclasses import dataclass


@dataclass
class DrillResult:
    transitions: list
    restart_attempts: list
    safe_mode_entries: list
    artifact_valid: bool = True
    artifact_state: str | None = None


def all_pass():
    return {}


def repeat(value, n):
    return [value for _ in range(n)]


def run_drill(*args, **kwargs):
    return DrillResult([], [], [])


def with_fail(*args, **kwargs):
    return {}
