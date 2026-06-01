from pathlib import Path
import argparse
import json
import sys

from src.formatter import format_plan_report
from src.planner import GapWisePlanner


DEMO_INPUTS = [
    "sample_input.json",
    "samples/cheap_meal.json",
    "samples/event_interest.json",
    "samples/short_gap.json",
    "samples/no_feasible_plan.json",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GapWise: Campus Gap-Time Planner"
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="sample_input.json",
        help="Path to a JSON file containing the user input.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON output instead of a readable report.",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Show why campus options were accepted or rejected.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run several built-in sample scenarios for quick peer testing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
    planner = GapWisePlanner(root / "data")

    if args.demo:
        return run_demo(root, planner, args)

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = root / input_path

    try:
        user_input = json.loads(input_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"Input file is not valid JSON: {exc}", file=sys.stderr)
        return 1

    try:
        result = planner.plan(user_input, include_explain=args.explain)
    except ValueError as exc:
        print(f"Could not create a plan: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_plan_report(result, show_explain=args.explain))
    return 0


def run_demo(root: Path, planner: GapWisePlanner, args: argparse.Namespace) -> int:
    if args.json:
        results = []
        for relative_path in DEMO_INPUTS:
            user_input = json.loads((root / relative_path).read_text(encoding="utf-8"))
            result = planner.plan(user_input, include_explain=args.explain)
            result["demo_input"] = relative_path
            results.append(result)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    reports = []
    for relative_path in DEMO_INPUTS:
        user_input = json.loads((root / relative_path).read_text(encoding="utf-8"))
        result = planner.plan(user_input, include_explain=args.explain)
        title = f"Demo scenario: {relative_path}"
        reports.extend([title, "-" * len(title), format_plan_report(result, args.explain)])
    print("\n\n".join(reports))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
