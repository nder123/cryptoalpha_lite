from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from scripts.behavior_validation.execution_simulator import simulate_execution
from scripts.behavior_validation.metrics import build_metrics
from scripts.behavior_validation.report_schema import build_report

DEFAULT_DATA = (
    {
        "event_id": "sample-001",
        "simulation_status": "accepted",
    },
    {
        "event_id": "sample-002",
        "simulation_status": "rejected",
    },
    {
        "event_id": "sample-003",
        "simulation_status": "delayed",
    },
)

DEFAULT_RUN_ID = "behavior-evaluation-v1"


def run_evaluation(
    *,
    data: Sequence[dict[str, object]] = DEFAULT_DATA,
    run_id: str = DEFAULT_RUN_ID,
    output_dir: Path | None = None,
) -> dict[str, object]:
    signals = _generate_signals(data)
    decisions = _generate_decisions(signals)
    executions = tuple(simulate_execution(decision) for decision in decisions)
    metrics = build_metrics(signals, decisions, executions)
    report = build_report(
        run_id=run_id,
        signals=len(signals),
        decisions=len(decisions),
        executions=len(executions),
        metrics=metrics,
    )

    _write_artifacts(output_dir or _default_output_dir(), report, metrics)
    return report


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run behavior evaluation harness")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_evaluation(run_id=args.run_id, output_dir=args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))


def _generate_signals(
    data: Sequence[dict[str, object]]
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "signal_id": f"signal-{index}",
            "source_event_id": row["event_id"],
            "simulation_status": row["simulation_status"],
        }
        for index, row in enumerate(data, start=1)
    )


def _generate_decisions(
    signals: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "decision_id": f"decision-{index}",
            "source_signal_id": signal["signal_id"],
            "simulation_status": signal["simulation_status"],
        }
        for index, signal in enumerate(signals, start=1)
    )


def _write_artifacts(
    output_dir: Path,
    report: dict[str, object],
    metrics: dict[str, int],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
