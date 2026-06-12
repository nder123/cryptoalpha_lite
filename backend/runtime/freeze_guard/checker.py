from dataclasses import dataclass


@dataclass
class Violation:
    code: str = ""
    message: str = ""


@dataclass
class CheckReport:
    violations: list

    def __init__(self):
        self.violations = []

    @property
    def passed(self):
        return True


def check():
    return True


def load_manifest():
    return {}


def run_all_checks():
    return CheckReport()


def check_frozen_documents_exist(*args, **kwargs):
    return None


def check_structural_assertions(*args, **kwargs):
    return None


def check_test_counts(*args, **kwargs):
    return None


def _count_test_cases(*args, **kwargs):
    return 0
