# GapWise: Campus Gap-Time Planner

## 0. team members (Name & Student ID)

- Member 1  [@TienNoob](https://github.com/TienNoob)
- Member 4: [@Sean957sean](https://github.com/Sean957sean)
- Member 2: [@DuckFard](https://github.com/DuckFard)
- Member 3: [@SengYee314](https://github.com/SengYee314)


## 1. Problem

Students often have awkward gaps between classes. A 40 to 120 minute break can be useful, but students need to quickly decide whether they should study, eat, attend a short event, or move closer to the next class. The decision depends on campus location, walking or shuttle time, seat availability, food budget, cafeteria congestion, and the next class time.

GapWise helps students turn an empty class gap into a practical plan.

## 2. Target Users

- Students with time gaps between classes
- Exchange students who are less familiar with campus locations
- Students trying to find quiet study time
- Students who want a quick meal without being late to class

## 3. Assumed Campus Data

The program uses mock campus data. It does not require real SNU APIs.

| File | Columns / Fields | Description |
|---|---|---|
| `data/locations.json` | name, area, x, y, nearest_shuttle_stop | Campus places and simple coordinates used for walking-time estimates |
| `data/study_spaces.json` | id, name, location, open, noise_level, capacity, seats_available, tags | Study spaces and current seat availability |
| `data/cafeterias.json` | id, name, location, open, congestion, average_eating_minutes, menu | Cafeterias, menus, prices, dietary tags, and congestion |
| `data/events.json` | id, title, day, start_time, end_time, location, tags, target, description | Campus events that may fit into a student's gap |
| `data/shuttles.json` | route, day, from_stop, to_stop, departure_time, arrival_time | Mock shuttle schedule used when it improves travel time |

## 4. User Input

`sample_input.json` contains the student situation:

```json
{
  "current_time": "Tuesday 13:10",
  "current_location": "Engineering Building 301",
  "next_class_time": "Tuesday 15:00",
  "next_class_location": "Humanities Building 6",
  "priority": "quiet study",
  "budget": 8000,
  "dietary_tags": ["vegetarian"],
  "interests": ["ai", "scholarship", "course"]
}
```

## 5. Pipeline

1. Parse user input: current time, current location, next class time, next class location, priority, budget, dietary tags, and interests.
2. Load mock campus data from the `data/` folder.
3. Estimate walking time from mock campus coordinates.
4. Check shuttle options from mock shuttle schedule.
5. Generate study, meal, and event candidates.
6. Filter candidates that do not fit the available time, opening hours, class arrival buffer, or budget.
7. Score remaining candidates based on priority match, available time, travel time, seat availability, congestion, budget, and interest tags.
8. Print the best plan and backup options.

## 6. How to Run

No external packages are required.

```bash
python main.py
```

To run with another input file:

```bash
python main.py path/to/input.json
```

To print machine-readable JSON:

```bash
python main.py --json
```

## 7. Example Output(s)

```text
GapWise: Campus Gap-Time Planner
=================================

Input Summary
- Current: Tuesday 13:10 at Engineering Building 301
- Next class: Tuesday 15:00 at Humanities Building 6
- Gap: 1 hr 50 min
- Priority: quiet study
- Budget: 8000 KRW

Best Plan
Study at Central Library Reading Room 2 (quiet study, score ...)
Location: Central Library
Reason: Available for ..., 42 seats open, noise level is quiet, matches quiet-study priority.
```

The exact scores may change if the mock data or user input changes.

## 8. Team Contributions

- Member 1: Designed the problem, README, and sample input.
- Member 2: Created mock campus data.
- Member 3: Implemented time, walking, and shuttle calculations.
- Member 4: Implemented scoring, output formatting, and testing.
