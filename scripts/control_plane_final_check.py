#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    readiness = _run_json(["python", "scripts/check_controlled_pilot_readiness.py"])
    execution = _run_json(["python", "scripts/run_controlled_pilot.py"])
    trace = _run_command(
        [
            "poetry",
            "run",
            "pytest",
            "tests/test_controlled_pilot_trace.py",
        ],
        cwd=REPO_ROOT / "backend",
    )

    readiness_ok = readiness.ok and readiness.payload.get("ready") is True
    execution_valid = execution.ok and execution.payload.get("status") == "RUNNING"
    trace_valid = trace.returncode == 0
    risk = "LOW" if readiness_ok and execution_valid and trace_valid else "HIGH"
    recommendation = "GO" if risk == "LOW" else "NO-GO"

    print(
        json.dumps(
            {
                "readiness": readiness_ok,
                "execution": "valid" if execution_valid and trace_valid else "invalid",
                "risk": risk,
                "recommendation": recommendation,
            },
            sort_keys=True,
        )
    )
    return 0 if recommendation == "GO" else 1


def _run_json(command: list[str]) -> "JsonCommandResult":
    result = _run_command(command, cwd=REPO_ROOT)
    if result.returncode != 0:
        return JsonCommandResult(ok=False, payload={})
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return JsonCommandResult(ok=False, payload={})
    return JsonCommandResult(ok=True, payload=payload)


def _run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "backend")
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


class JsonCommandResult:
    def __init__(self, ok: bool, payload: dict[str, object]):
        self.ok = ok
        self.payload = payload


if __name__ == "__main__":
    sys.exit(main())
