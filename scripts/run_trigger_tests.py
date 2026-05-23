"""
Run trigger-based evaluation against demo_cases/ + tests/expected_triggers.json.

Examples:
    python -m scripts.run_trigger_tests
    python -m scripts.run_trigger_tests --case hr_screening
    python -m scripts.run_trigger_tests --verbose
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Trigger tests default to offline mock fixtures unless --real-llm is passed.
if "--real-llm" not in sys.argv:
    os.environ["MOCK_LLM"] = "true"

from src.config import MOCK_LLM
from src.evaluation import run_all_trigger_tests


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EU AI Act demo trigger tests.")
    parser.add_argument(
        "--case",
        metavar="SLUG",
        help="Run a single demo case (e.g. hr_screening)",
    )
    parser.add_argument(
        "--real-llm",
        action="store_true",
        help="Use the configured LLM instead of mock fixtures (slower, non-deterministic)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-check details for each case",
    )
    args = parser.parse_args()

    print(f"MOCK_LLM={'true' if MOCK_LLM else 'false'}")
    print("Running trigger tests…\n")

    summary = run_all_trigger_tests(case_filter=args.case)

    for result in summary["results"]:
        status = "PASS" if result.get("passed") else "FAIL"
        name = result.get("case_name") or result.get("case_slug")
        print(f"[{status}] {name}")
        if result.get("error"):
            print(f"       error: {result['error']}")
        elif args.verbose:
            for check in result.get("checks") or []:
                mark = "ok" if check["passed"] else "FAIL"
                print(f"       - {mark}: {check['name']} — {check['detail']}")
            print(
                f"       risk_tier={result.get('observed_risk_tier')!r}, "
                f"revision={result.get('revision_triggered')}"
            )
        elif not result.get("passed"):
            for check in result.get("checks") or []:
                if not check["passed"]:
                    print(f"       - {check['name']}: {check['detail']}")

    print(
        f"\n{summary['passed']}/{summary['total']} case(s) passed."
    )
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
