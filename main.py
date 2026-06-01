from pathlib import Path
import argparse
import json
import sys

from src.formatter import format_plan_report
from src.planner import GapWisePlanner


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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent
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
        planner = GapWisePlanner(root / "data")
        result = planner.plan(user_input)
    except ValueError as exc:
        print(f"Could not create a plan: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_plan_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
