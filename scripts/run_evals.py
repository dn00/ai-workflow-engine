"""Run deterministic workflow eval cases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.evaluation.harness import load_eval_cases, run_eval_cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Run workflow eval cases")
    parser.add_argument(
        "--cases",
        default="evals/cases",
        help="Path to an eval case JSON file or directory of JSON files",
    )
    args = parser.parse_args()

    cases = load_eval_cases(Path(args.cases))
    report = run_eval_cases(cases)

    print(f"Eval cases: {report.passed}/{report.total} passed")
    for result in report.results:
        marker = "PASS" if result.passed else "FAIL"
        print(
            f"[{marker}] {result.workflow_type}/{result.name}: "
            f"status={result.status!r}"
        )
        for error in result.errors:
            print(f"  - {error}")

    return 0 if report.success else 1


if __name__ == "__main__":
    sys.exit(main())
