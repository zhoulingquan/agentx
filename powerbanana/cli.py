from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .agent import PowerBananaAgent

YELLOW = "\033[33m"
RESET = "\033[0m"


def yellow_logo() -> str:
    art = r"""
 ____   ___  __        __ _____ ____     ____    _    _   _    _    _   _    _
|  _ \ / _ \ \ \      / /| ____|  _ \   | __ )  / \  | \ | |  / \  | \ | |  / \
| |_) | | | | \ \ /\ / / |  _| | |_) |  |  _ \ / _ \ |  \| | / _ \ |  \| | / _ \
|  __/| |_| |  \ V  V /  | |___|  _ <   | |_) / ___ \| |\  |/ ___ \| |\  |/ ___ \
|_|    \___/    \_/\_/   |_____|_| \_\  |____/_/   \_\_| \_/_/   \_\_| \_/_/   \_\

                              POWER BANANA
"""
    return f"{YELLOW}{art}{RESET}"


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _print_report_summary(report: Any) -> None:
    print()
    print(f"Status: {report.status}")
    print(f"Answer: {report.answer}")
    if report.limitations:
        print("Limitations:")
        for limitation in report.limitations:
            print(f"- {limitation}")
    if report.security_findings:
        print("Security findings:")
        for finding in report.security_findings:
            print(f"- {finding.risk_type} at {finding.source_ref}: {finding.action}")
    print()


def interactive_loop() -> int:
    print(yellow_logo())
    print("PowerBanana v0.1 interactive data analysis CLI")
    print("Type q at the file prompt to exit.")
    agent = PowerBananaAgent()

    while True:
        file_value = input("Dataset file (.csv or simple .xlsx): ").strip()
        if file_value.lower() in {"q", "quit", "exit"}:
            print("Bye.")
            return 0
        question = input("Question: ").strip()
        if not question:
            print("Please enter a question.")
            continue
        try:
            report = agent.answer(Path(file_value), question)
        except Exception as exc:
            print(f"Error: {exc}")
            continue
        _print_report_summary(report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="powerbanana", description="PowerBanana v0.1 data analysis agent")
    parser.add_argument("file", type=Path, nargs="?", help="CSV or simple XLSX file to analyze")
    parser.add_argument("question", nargs="?", help="Analysis question")
    parser.add_argument("-i", "--interactive", action="store_true", help="Start the interactive CLI")
    args = parser.parse_args(argv)

    if args.interactive or (args.file is None and args.question is None):
        return interactive_loop()
    if args.file is None or args.question is None:
        parser.error("file and question are required unless --interactive is used")

    report = PowerBananaAgent().answer(args.file, args.question)
    print(json.dumps(report, default=_json_default, ensure_ascii=False, indent=2))
    return 0 if report.status in {"completed", "needs_clarification", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
