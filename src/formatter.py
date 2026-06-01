from src.time_utils import format_duration


def format_plan_report(result: dict) -> str:
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
        "",
    ]

    if result["best_plan"] is None:
        lines.extend(
            [
                "No feasible plan found.",
                "Try increasing the available gap time, budget, or location flexibility.",
            ]
        )
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
    return lines
