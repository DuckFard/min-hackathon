from src.time_utils import format_duration


def format_plan_report(result: dict, show_explain: bool = False) -> str:
    summary = result["input_summary"]
    lines = [
        result["project"],
        "=" * len(result["project"]),
        "",
        "Input Summary",
        f"- Current: {summary['current_time']} at {summary['current_location']}",
        f"- Next class: {summary['next_class_time']} at {summary['next_class_location']}",
        f"- Gap: {format_duration(summary['gap_minutes'])}",
        f"- Priority: {summary['priority']}",
        f"- Budget: {summary['budget']} KRW",
    ]
    if summary.get("allowed_activities"):
        lines.append(f"- Allowed activities: {', '.join(summary['allowed_activities'])}")
    if summary.get("min_activity_minutes") != 20:
        lines.append(f"- Minimum activity time: {summary['min_activity_minutes']} min")
    if summary.get("max_walking_minutes") is not None:
        lines.append(f"- Maximum walking time each way: {summary['max_walking_minutes']} min")
    if summary.get("avoid_shuttle"):
        lines.append("- Shuttle: avoided")
    lines.append("")

    if result["best_plan"] is None:
        lines.extend(
            [
                "No feasible plan found.",
                "Try increasing the available gap time, budget, or location flexibility.",
            ]
        )
        _append_explanations(lines, result, show_explain)
        return "\n".join(lines)

    lines.extend(_format_candidate("Best Plan", result["best_plan"]))

    if result["alternatives"]:
        lines.append("")
        lines.append("Backup Options")
        for index, candidate in enumerate(result["alternatives"], start=1):
            lines.append(
                f"{index}. {candidate['title']} "
                f"({candidate['type']}, score {candidate['score']})"
            )
            lines.append(f"   Reason: {candidate['reason']}")

    lines.extend(
        [
            "",
            "Pipeline",
            *[f"- {step}" for step in result["pipeline"]],
        ]
    )
    _append_explanations(lines, result, show_explain)
    return "\n".join(lines)


def _format_candidate(header: str, candidate: dict) -> list[str]:
    lines = [
        header,
        f"{candidate['title']} ({candidate['type']}, score {candidate['score']})",
        f"Location: {candidate['location']}",
        f"Reason: {candidate['reason']}",
        "",
        "Steps",
    ]
    for index, step in enumerate(candidate["steps"], start=1):
        lines.append(
            f"{index}. {step['start']} - {step['end']} | "
            f"{step['action']} ({step['duration']})"
        )
        lines.append(f"   {step['detail']}")
    if candidate.get("score_breakdown"):
        lines.append("")
        lines.append("Score Breakdown")
        for item in candidate["score_breakdown"]:
            value = item["value"]
            sign = "+" if isinstance(value, (int, float)) and value > 0 else ""
            lines.append(f"- {item['label']}: {sign}{value}")
    return lines


def _append_explanations(lines: list[str], result: dict, show_explain: bool) -> None:
    explanations = result.get("explanations", [])
    if not show_explain or not explanations:
        return
    lines.append("")
    lines.append("Explain Mode")
    for explanation in explanations:
        lines.append(f"- {explanation}")
