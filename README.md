# GapWise: Campus Gap-Time Planner

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

Optional fields can be added to make the planner easier to test:

| Field | Type | Description |
|---|---|---|
| `allowed_activities` | list of strings | Limits output to selected activity types such as `study`, `meal`, or `event` |
| `min_activity_minutes` | number | Requires each recommendation to provide at least this much usable activity time |
| `max_walking_minutes` | number | Rejects direct walking segments longer than this limit |
| `avoid_shuttle` | boolean | Forces the planner to use walking instead of shuttle options |

The `samples/` folder contains extra inputs for peer testing:

| File | What it tests |
|---|---|
| `samples/cheap_meal.json` | Meal-only planning with a small budget |
| `samples/event_interest.json` | Event-only planning based on interests |
| `samples/short_gap.json` | A tight schedule with walking limits |
| `samples/no_feasible_plan.json` | A case where all options should be rejected |

## 5. Internal Pipeline and Data Flow

At a high level, GapWise turns one student schedule gap into a ranked list of feasible plans:

```text
JSON user input
  -> command-line entry point
  -> campus data loader
  -> normalized planning context
  -> travel-time model
  -> study / meal / event candidate generators
  -> feasibility filters
  -> scoring and ranking
  -> readable report or JSON output
```

### Step 1: Command-line input selection

**Code:** `main.py`

**Input:**

- Command-line arguments.
- Optional path to an input JSON file.
- Optional `--json` flag.

**Process:**

- If no input path is provided, the program uses `sample_input.json`.
- If a relative input path is provided, it is resolved relative to the project root.
- The program reads the selected JSON file and parses it into a Python dictionary.
- If the file is missing or contains invalid JSON, the program prints an error to `stderr` and exits with status code `1`.

**Output:**

- A `user_input` dictionary such as:

```python
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

**Purpose:**

- This step is the boundary between the user and the planning engine. It converts a file-based request into the in-memory dictionary that the planner can use.

### Step 2: Campus data loading

**Code:** `src/data_loader.py`

**Input:**

- The `data/` directory.
- Required JSON files:
  - `locations.json`
  - `study_spaces.json`
  - `cafeterias.json`
  - `events.json`
  - `shuttles.json`

**Process:**

- `load_campus_data()` checks that every required data file exists.
- Each JSON file is parsed with UTF-8 encoding.
- The parsed datasets are stored in one dictionary, keyed by data type.
- If any required file is missing, the loader raises a `ValueError`.

**Output:**

```python
{
    "locations": [...],
    "study_spaces": [...],
    "cafeterias": [...],
    "events": [...],
    "shuttles": [...]
}
```

**Purpose:**

- This step separates mock campus data from program logic. The planner can stay generic while the JSON files define the available places, menus, events, and shuttle schedules.

### Step 3: Planner initialization

**Code:** `src/planner.py`, `GapWisePlanner.__init__`

**Input:**

- The loaded campus data from Step 2.

**Process:**

- The planner stores all campus datasets in `self.data`.
- It also builds a fast location lookup table:

```python
self.locations = {item["name"]: item for item in self.data["locations"]}
```

**Output:**

- A ready-to-use `GapWisePlanner` instance.
- A `self.locations` dictionary that maps location names to coordinates and shuttle-stop information.

**Purpose:**

- Later pipeline stages repeatedly need location details. The lookup table avoids scanning the full location list every time the program estimates walking time or finds a nearest shuttle stop.

### Step 4: User input normalization and validation

**Code:** `GapWisePlanner.plan()` and `src/time_utils.py`

**Input:**

- The `user_input` dictionary from Step 1.
- Campus locations from Step 3.

**Process:**

- `parse_day_time()` converts strings such as `"Tuesday 13:10"` into integer minutes from the start of the week.
  - Monday starts at minute `0`.
  - Tuesday 13:10 becomes a single comparable integer.
- The planner verifies that `next_class_time` is after `current_time`.
- The planner verifies that both the current location and next class location exist in `locations.json`.
- The program creates a 5-minute safety buffer before the next class:

```python
latest_arrival = next_class_time - SAFETY_BUFFER_MINUTES
```

- User preferences are normalized:
  - `priority` is lowercased.
  - `budget` is converted to an integer.
  - `dietary_tags` and `interests` are converted to lowercase sets.
- Optional constraints are also normalized:
  - `allowed_activities` becomes a lowercase set.
  - `min_activity_minutes` controls the minimum useful activity time.
  - `max_walking_minutes` can reject options with too much direct walking.
  - `avoid_shuttle` disables shuttle routes for the scenario.

**Output:**

- A normalized `context` dictionary:

```python
{
    "current_time": 2230,
    "next_class_time": 2340,
    "latest_arrival": 2335,
    "current_location": "Engineering Building 301",
    "next_class_location": "Humanities Building 6",
    "priority": "quiet study",
    "budget": 8000,
    "dietary_tags": {"vegetarian"},
    "interests": {"ai", "scholarship", "course"},
    "allowed_activities": set(),
    "min_activity_minutes": 20,
    "max_walking_minutes": None,
    "avoid_shuttle": False
}
```

**Purpose:**

- This step makes the rest of the program easier and safer. Times become numbers that can be compared and subtracted, locations are guaranteed to exist, and preferences are normalized for matching.

### Step 5: Travel-time modeling

**Code:** `TravelSegment`, `_walking_minutes()`, `_earliest_travel()`, `_latest_travel()`, `_earliest_shuttle_segment()`, `_latest_shuttle_segment()`

**Input:**

- Origin location.
- Destination location.
- Either a departure time or an arrival deadline.
- Location coordinates from `locations.json`.
- Nearest shuttle stops from `locations.json`.
- Shuttle trips from `shuttles.json`.

**Process:**

- Walking time is estimated from mock coordinates:

```python
distance = sqrt((start["x"] - end["x"]) ** 2 + (start["y"] - end["y"]) ** 2)
walking_minutes = max(2, ceil(distance * 8))
```

- For direct walking, the program creates a `TravelSegment` with:
  - mode: `"walk"`
  - origin and destination
  - departure time
  - arrival time
  - duration in minutes
  - human-readable detail text
- For shuttle travel, the program:
  - finds the nearest shuttle stop to the origin;
  - finds the nearest shuttle stop to the destination;
  - adds walking time from the origin to the origin stop;
  - searches the shuttle schedule for a matching route;
  - adds walking time from the destination stop to the final destination.
- `_earliest_travel()` compares direct walking with shuttle travel and chooses the option that arrives earliest.
- `_latest_travel()` compares direct walking with shuttle travel and chooses the option that lets the student leave the candidate location as late as possible while still arriving before the deadline.
- If `avoid_shuttle` is true, both travel functions skip shuttle checks and return walking segments only.
- If `max_walking_minutes` is set, candidates with direct walking segments above that limit are rejected.

**Output:**

- A `TravelSegment` object. When converted to output, it includes both numeric and readable fields:

```python
{
    "mode": "shuttle",
    "origin": "Engineering Building 301",
    "destination": "Central Library",
    "depart": 2230,
    "arrive": 2249,
    "minutes": 19,
    "detail": "Walk 2 min to Engineering Stop, take Loop A at 13:20, then walk 2 min.",
    "depart_text": "Tuesday 13:10",
    "arrive_text": "Tuesday 13:29",
    "duration_text": "19 min"
}
```

**Purpose:**

- Every plan must include travel to the activity and travel from the activity to the next class. This step makes time feasibility realistic enough for the prototype by considering both walking and shuttle options.

### Step 6: Study candidate generation

**Code:** `_study_candidates()`

**Input:**

- Normalized planning context from Step 4.
- Study spaces from `study_spaces.json`.
- Travel segments from Step 5.

**Process:**

- For each study space, the planner calculates:
  - earliest arrival from the current location;
  - latest possible departure toward the next class location.
- The study space is discarded if:
  - arrival is not before departure;
  - the space is not open when the student arrives;
  - the space is not open when the student would leave;
  - usable study time is under 20 minutes.
- For feasible spaces, the planner computes:
  - usable minutes;
  - seat availability ratio;
  - whether the space is quiet when the user wants quiet study;
  - tag matches against priority, interests, and dietary tags;
  - travel-time penalty.

**Output:**

- Zero or more study candidate dictionaries. Each candidate includes:
  - `type`
  - `title`
  - `score`
  - `location`
  - `usable_minutes`
  - `reason`
  - ordered `steps` for travel, study, and travel to class.

**Purpose:**

- This branch finds places where the student can realistically study during the gap without being late to the next class.

### Step 7: Meal candidate generation

**Code:** `_food_candidates()` and `_best_menu_item()`

**Input:**

- Normalized planning context from Step 4.
- Cafeterias from `cafeterias.json`.
- Travel segments from Step 5.

**Process:**

- If the budget is `0` or lower, the entire meal branch returns no candidates.
- For each cafeteria, the planner calculates:
  - earliest arrival from the current location;
  - latest possible departure toward the next class location.
- The cafeteria is discarded if:
  - arrival is not before departure;
  - the cafeteria is closed when the student arrives;
  - no menu item fits the user's budget;
  - wait time plus eating time does not fit before the student must leave.
- `_best_menu_item()` chooses the best affordable menu item by preferring:
  - more dietary tag matches;
  - lower price as the tie breaker.
- The meal duration is:

```python
meal_minutes = wait_minutes_by_congestion[congestion] + average_eating_minutes
```

**Output:**

- Zero or more meal candidate dictionaries with the same high-level structure as study candidates.
- The middle step describes the selected menu item, price, dietary tags, and eating duration.

**Purpose:**

- This branch checks whether the student can eat within the gap, stay under budget, respect dietary preferences when possible, and still arrive at class on time.

### Step 8: Event candidate generation

**Code:** `_event_candidates()`

**Input:**

- Normalized planning context from Step 4.
- Events from `events.json`.
- Travel segments from Step 5.

**Process:**

- Each event's day, start time, and end time are converted into week-minute integers.
- The event is discarded if it does not overlap with the student's gap.
- The planner calculates:
  - earliest arrival from the current location;
  - latest possible departure toward the next class location.
- The event is discarded if:
  - arrival is not before departure;
  - the student can attend for less than 20 minutes.
- If the student can only attend part of the event, the program keeps the overlapping portion:

```python
attend_start = max(arrival.arrive, event_start)
attend_end = min(departure.depart, event_end)
```

**Output:**

- Zero or more event candidate dictionaries.
- Each candidate includes travel steps plus an event attendance step with the actual attendable time window.

**Purpose:**

- This branch finds short campus activities that overlap with the gap and match the student's interests.

### Step 9: Scoring

**Code:** `_study_candidates()`, `_food_candidates()`, `_event_candidates()`, `_tag_matches()`

**Input:**

- Feasible study, meal, and event candidates.
- User priority, interests, dietary tags, budget, travel times, seat availability, congestion, and usable minutes.

**Process:**

- Study candidates are rewarded for:
  - longer usable study time, capped at 90 minutes;
  - higher seat availability;
  - quiet spaces when the priority mentions quiet study;
  - matching tags;
  - shorter total travel time.
- Meal candidates are rewarded for:
  - food-related priorities;
  - dietary tag matches;
  - lower congestion;
  - more remaining budget;
  - shorter total travel time.
- Event candidates are rewarded for:
  - event-related priorities;
  - matching interest tags;
  - longer attendable time, capped at 60 minutes;
  - shorter total travel time.
- `_tag_matches()` combines words from the priority, interests, and dietary tags, then counts overlap with candidate tags.

**Output:**

- Each candidate receives a rounded numeric `score`.
- Each accepted candidate also receives a `score_breakdown` list showing the positive bonuses and travel penalty that created the final score.

**Purpose:**

- Scoring lets very different options, such as studying, eating, and attending an event, be compared in one ranked list.

### Step 10: Ranking and final result assembly

**Code:** `GapWisePlanner.plan()`

**Input:**

- All scored candidates from the study, meal, and event branches.

**Process:**

- Candidates are combined into one list.
- The list is sorted from highest score to lowest score.
- The highest-scoring candidate becomes `best_plan`.
- The next three candidates become `alternatives`.
- If no candidate survives filtering, `best_plan` is set to `None`.
- When `--explain` is enabled, the result also includes accepted and rejected option messages.

**Output:**

```python
{
    "project": "GapWise: Campus Gap-Time Planner",
    "input_summary": {...},
    "best_plan": {...},
    "alternatives": [...],
    "pipeline": [...]
}
```

**Purpose:**

- This step converts many possible activities into a simple recommendation: one best plan plus backup options.

### Step 11: Output formatting

**Code:** `src/formatter.py` and `main.py`

**Input:**

- The result dictionary from Step 10.
- The `--json` flag from Step 1.
- The `--explain` flag from Step 1.

**Process:**

- If `--json` is used, `main.py` prints the raw result dictionary with `json.dumps()`.
- If `--explain` is used, the readable report includes an "Explain Mode" section with accepted and rejected option messages.
- Otherwise, `format_plan_report()` builds a readable text report with:
  - project title;
  - input summary;
  - best plan;
  - step-by-step schedule;
  - score breakdown;
  - backup options;
  - short pipeline summary.
- If `best_plan` is `None`, the report explains that no feasible plan was found.

**Output:**

- Human-readable terminal output, or machine-readable JSON.

**Purpose:**

- The planner itself returns structured data. The formatter turns that structured data into something easy for a student to read in the terminal, while `--json` keeps the program usable for other tools.

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

To show why options were accepted or rejected:

```bash
python main.py --explain
```

To run several built-in peer-review scenarios:

```bash
python main.py --demo
```

You can also combine flags:

```bash
python main.py samples/cheap_meal.json --explain
python main.py --demo --json
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

Score Breakdown
- Base study score: +40
- Usable time bonus: +...
- Seat availability bonus: +...
- Quiet priority bonus: +25
- Preference tag bonus: +...
- Travel time penalty: -...
```

The exact scores may change if the mock data or user input changes.

## 8. Team Contributions

- Member 1: Designed the problem, README, and sample input.
- Member 2: Created mock campus data.
- Member 3: Implemented time, walking, and shuttle calculations.
- Member 4: Implemented scoring, output formatting, and testing.
