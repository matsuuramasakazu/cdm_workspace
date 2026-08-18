"""
CLI Entry Point for Universal AI Agent Harness.

Usage:
    python -m cdm_workspace.harness doctor
    python -m cdm_workspace.harness verify
    python -m cdm_workspace.harness exec "print('Hello')"
    python -m cdm_workspace.harness inspect Trade
    python -m cdm_workspace.harness events
    python -m cdm_workspace.harness irs [--output irs_trade.json]
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .core import doctor, exec_code, verify
from .cdm_plugin import generate_irs_sample, inspect_model, list_business_events


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cdm_workspace.harness",
        description="Universal AI Agent Harness & CDM Diagnostics CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Harness command to run")

    # Command: doctor
    subparsers.add_parser("doctor", help="Perform environment and dependency diagnostics")

    # Command: verify
    verify_parser = subparsers.add_parser("verify", help="Run automated test suite and verification pipeline")
    verify_parser.add_argument("--path", default="tests", help="Tests directory path (default: tests)")

    # Command: exec
    exec_parser = subparsers.add_parser("exec", help="Safely execute a Python snippet with cdm_compat initialized")
    exec_parser.add_argument("code", help="Python code string to execute")
    exec_parser.add_argument("--timeout", type=int, default=15, help="Timeout in seconds (default: 15)")

    # Command: inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect fields and types of a CDM model class")
    inspect_parser.add_argument("model", help="Class name (e.g. Trade, TradeState, InterestRatePayout)")

    # Command: events
    subparsers.add_parser("events", help="List all supported IRS lifecycle business events")

    # Command: irs
    irs_parser = subparsers.add_parser("irs", help="Generate and validate a sample Plain Vanilla IRS trade JSON")
    irs_parser.add_argument("--output", "-o", default="irs_trade.json", help="Output JSON file path")

    # Command: qualify
    qualify_parser = subparsers.add_parser("qualify", help="Qualify and classify a trade from JSON file")
    qualify_parser.add_argument("file", help="Path to trade JSON file (e.g. ird-ex01-vanilla-swap.json)")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "doctor":
        res = doctor()
        print(res["report"])
        return 0 if res["ok"] else 1

    elif args.command == "verify":
        res = verify(tests_path=args.path)
        print(res["report"])
        return res["exit_code"]

    elif args.command == "exec":
        res = exec_code(args.code, timeout=args.timeout)
        if res["stdout"]:
            print(res["stdout"], end="")
        if res["stderr"]:
            print(res["stderr"], file=sys.stderr, end="")
        return res["exit_code"]

    elif args.command == "inspect":
        res = inspect_model(args.model)
        print(res["report"])
        return 0 if res["found"] else 1

    elif args.command == "events":
        res = list_business_events()
        print(res["report"])
        return 0

    elif args.command == "irs":
        res = generate_irs_sample(args.output)
        print(f"[OK] IRS trade generated and verified: {res['output_path']} ({res['size_bytes']:,} bytes)")
        return 0

    elif args.command == "qualify":
        from ..qualify_trade import qualify_from_json, print_qualification_summary
        from pathlib import Path
        p = Path(args.file)
        if not p.exists():
            print(f"Error: File not found: {p}", file=sys.stderr)
            return 1
        res = qualify_from_json(p)
        print_qualification_summary(res)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
