from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path

from scripts.behavior_validation.insights_diff_v1 import diff_insights_files


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diff behavior insight artifacts")
    parser.add_argument("previous_insights", type=Path)
    parser.add_argument("current_insights", type=Path)
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    diff = diff_insights_files(args.previous_insights, args.current_insights)
    print(json.dumps(diff, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
