DAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def parse_day_time(value: str) -> int:
    parts = value.strip().split()
    if len(parts) != 2:
        raise ValueError(f"Expected a value like 'Tuesday 13:10', got {value!r}")

    day_text, time_text = parts
    day_key = day_text.lower()
    if day_key not in DAYS:
        raise ValueError(f"Unknown weekday: {day_text}")

    hour_text, minute_text = time_text.split(":")
    hour = int(hour_text)
    minute = int(minute_text)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid time: {time_text}")

    return DAYS[day_key] * 24 * 60 + hour * 60 + minute


def parse_clock_on_day(day_index: int, clock: str) -> int:
    hour_text, minute_text = clock.split(":")
    hour = int(hour_text)
    minute = int(minute_text)
    return day_index * 24 * 60 + hour * 60 + minute


def day_index(minutes: int) -> int:
    return (minutes // (24 * 60)) % 7


def format_minutes(minutes: int) -> str:
    day = DAY_NAMES[day_index(minutes)]
    minute_of_day = minutes % (24 * 60)
    hour = minute_of_day // 60
    minute = minute_of_day % 60
    return f"{day} {hour:02d}:{minute:02d}"


def format_duration(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    remainder = minutes % 60
    if remainder == 0:
        return f"{hours} hr"
    return f"{hours} hr {remainder} min"


def is_open(opening_hours: dict, at_minutes: int) -> bool:
    day = day_index(at_minutes)
    start = parse_clock_on_day(day, opening_hours["start"])
    end = parse_clock_on_day(day, opening_hours["end"])
    if end <= start:
        end += 24 * 60
    return start <= at_minutes <= end
