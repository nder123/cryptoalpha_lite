#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"

CONTROLLED_PILOT_TESTS = [
    "tests/test_contract_registry_inversion.py",
    "tests/test_validation_surface_contract.py",
    "tests/test_lineage_semantic_boundary.py",
    "tests/test_event_lineage_consistency.py",
    "tests/test_event_contract_consistency.py",
    "tests/test_cross_module_consistency.py",
    "tests/test_validation_core_shadow_evaluation.py",
    "tests/test_controlled_pilot_trace.py",
]


def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []

    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR)
    command = ["poetry", "run", "pytest", *CONTROLLED_PILOT_TESTS]
    try:
        result = subprocess.run(
            command,
            cwd=BACKEND_DIR,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        blockers.append("BLOCKER: poetry executable not found")
        _emit(False, blockers, warnings)
        return 1

    if result.returncode != 0:
        blockers.append(
            "BLOCKER: controlled pilot readiness suite failed: "
            f"{_tail(result.stdout + result.stderr)}"
        )

    ready = not blockers
    _emit(ready, blockers, warnings)
    return 0 if ready else 1


def _emit(ready: bool, blockers: list[str], warnings: list[str]) -> None:
    print(
        json.dumps(
            {
                "ready": ready,
                "blockers": blockers,
                "warnings": warnings,
            },
            sort_keys=True,
        )
    )


def _tail(value: str) -> str:
    lines = [line for line in value.splitlines() if line.strip()]
    return "\n".join(lines[-20:])


if __name__ == "__main__":
    sys.exit(main())
