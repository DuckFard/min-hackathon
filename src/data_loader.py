from pathlib import Path
import json


REQUIRED_FILES = {
    "locations": "locations.json",
    "study_spaces": "study_spaces.json",
    "cafeterias": "cafeterias.json",
    "events": "events.json",
    "shuttles": "shuttles.json",
}


def load_campus_data(data_dir: Path) -> dict:
    datasets = {}
    missing = []

    for key, filename in REQUIRED_FILES.items():
        path = data_dir / filename
        if not path.exists():
            missing.append(str(path))
            continue
        datasets[key] = json.loads(path.read_text(encoding="utf-8"))

    if missing:
        raise ValueError("Missing data file(s): " + ", ".join(missing))

    return datasets
