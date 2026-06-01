from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .agent import PowerBananaAgent
from .analysis_request import DEFAULT_ANALYSIS_TERMS_PATH
from .vocabulary import DEFAULT_SUGGESTION_STORE_PATH, VocabularyApprovalService, VocabularySuggestionRepository

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


def _add_vocabulary_store_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--store",
        type=Path,
        default=DEFAULT_SUGGESTION_STORE_PATH,
        help="Path to vocabulary suggestion JSONL store",
    )


def _vocab_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="powerbanana vocab", description="Review pending vocabulary suggestions")
    subparsers = parser.add_subparsers(dest="action", required=True)

    list_parser = subparsers.add_parser("list", help="List vocabulary suggestions")
    _add_vocabulary_store_options(list_parser)
    list_parser.add_argument("--status", choices=["pending_user_approval", "approved", "rejected"], help="Filter by review status")

    approve_parser = subparsers.add_parser("approve", help="Approve a vocabulary suggestion and append it to analysis_terms.csv")
    approve_parser.add_argument("suggestion_id", help="Suggestion id such as vocab_000001")
    _add_vocabulary_store_options(approve_parser)
    approve_parser.add_argument(
        "--analysis-terms",
        type=Path,
        default=DEFAULT_ANALYSIS_TERMS_PATH,
        help="Path to analysis_terms.csv",
    )
    approve_parser.add_argument("--note", default="", help="Reviewer note to store with the decision")

    reject_parser = subparsers.add_parser("reject", help="Reject a vocabulary suggestion")
    reject_parser.add_argument("suggestion_id", help="Suggestion id such as vocab_000001")
    _add_vocabulary_store_options(reject_parser)
    reject_parser.add_argument("--note", default="", help="Reviewer note to store with the decision")

    args = parser.parse_args(argv)
    repository = VocabularySuggestionRepository(args.store)
    service = VocabularyApprovalService(repository)

    try:
        if args.action == "list":
            records = repository.list_records(status=args.status)
            if not records:
                print("No vocabulary suggestions.")
                return 0
            for record in records:
                suggestion = record.suggestion
                terms = "|".join(suggestion.terms)
                print(
                    f"{record.suggestion_id} {record.status} "
                    f"{suggestion.kind}={suggestion.value} terms={terms} "
                    f"confidence={suggestion.confidence:.2f} source={suggestion.source}"
                )
            return 0
        if args.action == "approve":
            record = service.approve(args.suggestion_id, args.analysis_terms, reviewer_note=args.note)
            print(f"approved {record.suggestion_id}: {record.suggestion.kind}={record.suggestion.value}")
            return 0
        if args.action == "reject":
            record = service.reject(args.suggestion_id, reviewer_note=args.note)
            print(f"rejected {record.suggestion_id}: {record.suggestion.kind}={record.suggestion.value}")
            return 0
    except (KeyError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1
    parser.error(f"unsupported vocab action: {args.action}")
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else None
    if argv and argv[0] == "vocab":
        return _vocab_main(argv[1:])

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
