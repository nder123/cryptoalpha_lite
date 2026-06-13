from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from pathlib import Path

REQUIRED_COLUMNS = ("timestamp", "symbol", "open", "high", "low", "close", "volume")
SIMULATION_STATUSES = ("accepted", "rejected", "delayed")


def load_historical_data(path: Path | str) -> tuple[dict[str, str], ...]:
    dataset_path = Path(path)
    files = _dataset_files(dataset_path)

    rows: list[dict[str, str]] = []
    for file_path in files:
        rows.extend(_read_csv(file_path))
    return tuple(rows)


def normalize_dataset(
    rows: Iterable[Mapping[str, str]],
) -> tuple[dict[str, object], ...]:
    normalized_rows = []
    for index, row in enumerate(rows, start=1):
        _require_columns(row)
        symbol = row["symbol"].strip().upper()
        timestamp = row["timestamp"].strip()
        normalized_rows.append(
            {
                "event_id": f"{symbol}-{timestamp}",
                "row_number": index,
                "timestamp": timestamp,
                "symbol": symbol,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "simulation_status": _simulation_status(row),
            }
        )
    return tuple(normalized_rows)


def _dataset_files(dataset_path: Path) -> tuple[Path, ...]:
    if dataset_path.is_dir():
        return tuple(sorted(dataset_path.glob("*.csv")))
    return (dataset_path,)


def _read_csv(file_path: Path) -> tuple[dict[str, str], ...]:
    with file_path.open(newline="", encoding="utf-8") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def _require_columns(row: Mapping[str, str]) -> None:
    missing = tuple(column for column in REQUIRED_COLUMNS if column not in row)
    if missing:
        raise ValueError(f"Historical row missing required columns: {missing!r}")


def _simulation_status(row: Mapping[str, str]) -> str:
    status = row.get("simulation_status", "accepted").strip()
    if status in SIMULATION_STATUSES:
        return status
    return "rejected"
