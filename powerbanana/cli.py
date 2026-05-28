from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .agent import PowerBananaAgent


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="powerbanana", description="PowerBanana v0.1 data analysis agent")
    parser.add_argument("file", type=Path, help="CSV or simple XLSX file to analyze")
    parser.add_argument("question", help="Analysis question")
    args = parser.parse_args(argv)

    report = PowerBananaAgent().answer(args.file, args.question)
    print(json.dumps(report, default=_json_default, ensure_ascii=False, indent=2))
    return 0 if report.status in {"completed", "needs_clarification", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
