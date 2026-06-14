from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from scripts.behavior_validation.data_adapter import (
    REQUIRED_COLUMNS,
    load_historical_data,
    normalize_dataset,
)

REQUIRED_SYMBOLS = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "LINKUSDT",
)
DEFAULT_MONTHS = ("2024-01",)
DEFAULT_INTERVAL = "1h"
DATASET_DIRNAME = "expanded_dataset_v1"
SUMMARY_FILENAME = "dataset_summary_v1.json"
CSV_COLUMNS = (*REQUIRED_COLUMNS, "simulation_status")


class KlineSource(Protocol):
    @property
    def source_name(self) -> str: ...

    def fetch_month(
        self,
        *,
        symbol: str,
        month: str,
        interval: str,
    ) -> tuple[dict[str, str], ...]: ...


@dataclass(frozen=True)
class BinanceVisionFuturesKlineSource:
    source_name: str = "binance_vision_usdt_m_futures"
    base_url: str = "https://data.binance.vision/data/futures/um/monthly/klines"
    timeout_seconds: float = 30.0

    def fetch_month(
        self,
        *,
        symbol: str,
        month: str,
        interval: str,
    ) -> tuple[dict[str, str], ...]:
        archive_name = f"{symbol}-{interval}-{month}.zip"
        url = "/".join(
            (
                self.base_url.rstrip("/"),
                urllib.parse.quote(symbol),
                urllib.parse.quote(interval),
                urllib.parse.quote(archive_name),
            )
        )
        request = urllib.request.Request(
            url, headers={"User-Agent": "cryptoalpha-lite"}
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            archive = response.read()
        return _parse_binance_kline_zip(archive, symbol=symbol)


def expand_dataset(
    *,
    symbols: Sequence[str] = REQUIRED_SYMBOLS,
    months: Sequence[str] = DEFAULT_MONTHS,
    interval: str = DEFAULT_INTERVAL,
    output_dataset_dir: Path,
    summary_path: Path,
    source: KlineSource | None = None,
) -> dict[str, object]:
    kline_source = source or BinanceVisionFuturesKlineSource()
    rows = _collect_rows(
        symbols=symbols,
        months=months,
        interval=interval,
        source=kline_source,
    )
    write_dataset(rows, output_dataset_dir)
    adapter_ready_rows = normalize_dataset(load_historical_data(output_dataset_dir))
    summary = summarize_dataset(
        adapter_ready_rows,
        symbols=symbols,
        months=months,
        interval=interval,
        source_name=kline_source.source_name,
        output_dataset_dir=output_dataset_dir,
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def write_dataset(rows: Sequence[Mapping[str, str]], output_dataset_dir: Path) -> None:
    output_dataset_dir.mkdir(parents=True, exist_ok=True)
    for stale_file in output_dataset_dir.glob("*.csv"):
        stale_file.unlink()

    rows_by_symbol: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        rows_by_symbol[row["symbol"]].append(row)

    for symbol, symbol_rows in sorted(rows_by_symbol.items()):
        file_path = output_dataset_dir / f"{symbol}_candles.csv"
        with file_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(
                {
                    column: row.get(
                        column, "accepted" if column == "simulation_status" else ""
                    )
                    for column in CSV_COLUMNS
                }
                for row in sorted(symbol_rows, key=lambda item: item["timestamp"])
            )


def summarize_dataset(
    rows: Sequence[dict[str, object]],
    *,
    symbols: Sequence[str],
    months: Sequence[str],
    interval: str,
    source_name: str,
    output_dataset_dir: Path,
) -> dict[str, object]:
    symbols_present = sorted({str(row["symbol"]) for row in rows})
    timestamps = sorted(str(row["timestamp"]) for row in rows)
    rows_per_symbol = _rows_per_symbol(rows)
    return {
        "schema_version": "dataset_expansion_v1",
        "source": source_name,
        "interval": interval,
        "months": list(months),
        "dataset_path": _portable_path(output_dataset_dir),
        "symbol_count": len(symbols_present),
        "required_symbols": list(symbols),
        "symbols": symbols_present,
        "row_count": len(rows),
        "date_range": {
            "start": timestamps[0] if timestamps else None,
            "end": timestamps[-1] if timestamps else None,
        },
        "rows_per_symbol": rows_per_symbol,
        "volatility_statistics_per_symbol": _volatility_statistics(rows),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Expand behavior-validation market input coverage"
    )
    parser.add_argument("--symbols", nargs="+", default=list(REQUIRED_SYMBOLS))
    parser.add_argument("--months", nargs="+", default=list(DEFAULT_MONTHS))
    parser.add_argument("--interval", default=DEFAULT_INTERVAL)
    parser.add_argument(
        "--output-dataset-dir",
        type=Path,
        default=_default_output_dir() / DATASET_DIRNAME,
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=_default_output_dir() / SUMMARY_FILENAME,
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    summary = expand_dataset(
        symbols=tuple(args.symbols),
        months=tuple(args.months),
        interval=args.interval,
        output_dataset_dir=args.output_dataset_dir,
        summary_path=args.summary_path,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


def _collect_rows(
    *,
    symbols: Sequence[str],
    months: Sequence[str],
    interval: str,
    source: KlineSource,
) -> tuple[dict[str, str], ...]:
    rows_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for symbol in symbols:
        for month in months:
            for row in source.fetch_month(
                symbol=symbol,
                month=month,
                interval=interval,
            ):
                rows_by_key[(row["symbol"], row["timestamp"])] = row
    return tuple(
        rows_by_key[key]
        for key in sorted(rows_by_key, key=lambda item: (item[0], item[1]))
    )


def _parse_binance_kline_zip(
    archive: bytes,
    *,
    symbol: str,
) -> tuple[dict[str, str], ...]:
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        csv_names = tuple(name for name in zipped.namelist() if name.endswith(".csv"))
        if not csv_names:
            raise ValueError(f"No CSV payload found for {symbol}")
        with zipped.open(csv_names[0]) as csv_file:
            text_stream = io.TextIOWrapper(csv_file, encoding="utf-8")
            return tuple(
                _binance_row_to_normalized(row, symbol=symbol)
                for row in csv.reader(text_stream)
                if row and row[0] != "open_time"
            )


def _binance_row_to_normalized(row: Sequence[str], *, symbol: str) -> dict[str, str]:
    if len(row) < 6:
        raise ValueError(f"Malformed Binance kline row for {symbol}: {row!r}")
    return {
        "timestamp": _timestamp_from_ms(row[0]),
        "symbol": symbol,
        "open": row[1],
        "high": row[2],
        "low": row[3],
        "close": row[4],
        "volume": row[5],
        "simulation_status": "accepted",
    }


def _timestamp_from_ms(value: str) -> str:
    timestamp = datetime.fromtimestamp(int(value) / 1000, tz=UTC)
    return timestamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rows_per_symbol(rows: Sequence[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row["symbol"])] += 1
    return dict(sorted(counts.items()))


def _volatility_statistics(
    rows: Sequence[dict[str, object]],
) -> dict[str, dict[str, float]]:
    rows_by_symbol: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        rows_by_symbol[str(row["symbol"])].append(row)

    stats = {}
    for symbol, symbol_rows in sorted(rows_by_symbol.items()):
        sorted_rows = sorted(symbol_rows, key=lambda row: str(row["timestamp"]))
        close_returns = tuple(
            _close_return(current, next_row)
            for current, next_row in zip(sorted_rows, sorted_rows[1:], strict=False)
        )
        range_pct = tuple(_range_pct(row) for row in sorted_rows)
        stats[symbol] = {
            "close_to_close_return_stddev": _stddev(close_returns),
            "mean_abs_close_to_close_return": _mean(
                tuple(abs(value) for value in close_returns)
            ),
            "mean_range_pct": _mean(range_pct),
            "max_range_pct": max(range_pct, default=0.0),
            "min_range_pct": min(range_pct, default=0.0),
        }
    return stats


def _close_return(
    current: Mapping[str, object], next_row: Mapping[str, object]
) -> float:
    current_close = _float_value(current.get("close"))
    if current_close == 0.0:
        return 0.0
    return (_float_value(next_row.get("close")) - current_close) / current_close


def _range_pct(row: Mapping[str, object]) -> float:
    open_price = _float_value(row.get("open"))
    if open_price == 0.0:
        return 0.0
    return (_float_value(row.get("high")) - _float_value(row.get("low"))) / open_price


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _stddev(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        return float(value)
    return 0.0


def _default_output_dir() -> Path:
    return _repo_root() / "artifacts" / "behavior_validation"


def _portable_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(_repo_root()))
    except ValueError:
        return str(path)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


if __name__ == "__main__":
    main()
