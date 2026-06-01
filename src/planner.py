from __future__ import annotations

from dataclasses import dataclass, asdict
from math import ceil, sqrt
from pathlib import Path

from src.data_loader import load_campus_data
from src.time_utils import (
    format_duration,
    format_minutes,
    is_open,
    parse_day_time,
)


SAFETY_BUFFER_MINUTES = 5


@dataclass
class TravelSegment:
    mode: str
    origin: str
    destination: str
    depart: int
    arrive: int
    minutes: int
    detail: str

    def to_output(self) -> dict:
        data = asdict(self)
        data["depart_text"] = format_minutes(self.depart)
        data["arrive_text"] = format_minutes(self.arrive)
        data["duration_text"] = format_duration(self.minutes)
        return data


class GapWisePlanner:
    def __init__(self, data_dir: Path):
        self.data = load_campus_data(data_dir)
        self.locations = {item["name"]: item for item in self.data["locations"]}

    def plan(self, user_input: dict, include_explain: bool = False) -> dict:
        current_time = parse_day_time(user_input["current_time"])
        next_class_time = parse_day_time(user_input["next_class_time"])
        if next_class_time <= current_time:
            raise ValueError("next_class_time must be after current_time in this prototype.")

        current_location = user_input["current_location"]
        next_class_location = user_input["next_class_location"]
        self._require_location(current_location)
        self._require_location(next_class_location)

        allowed_activities = {
            item.lower() for item in user_input.get("allowed_activities", [])
        }
        context = {
            "current_time": current_time,
            "next_class_time": next_class_time,
            "latest_arrival": next_class_time - SAFETY_BUFFER_MINUTES,
            "current_location": current_location,
            "next_class_location": next_class_location,
            "priority": user_input.get("priority", "balanced").lower(),
            "budget": int(user_input.get("budget", 0)),
            "dietary_tags": set(tag.lower() for tag in user_input.get("dietary_tags", [])),
            "interests": set(tag.lower() for tag in user_input.get("interests", [])),
            "allowed_activities": allowed_activities,
            "min_activity_minutes": int(user_input.get("min_activity_minutes", 20)),
            "max_walking_minutes": user_input.get("max_walking_minutes"),
            "avoid_shuttle": bool(user_input.get("avoid_shuttle", False)),
            "include_explain": include_explain,
            "explanations": [],
        }
        if context["max_walking_minutes"] is not None:
            context["max_walking_minutes"] = int(context["max_walking_minutes"])

        candidates = []
        if self._activity_allowed(context, "study"):
            candidates.extend(self._study_candidates(context))
        else:
            self._reject(context, "Study options", "disabled by allowed_activities.")
        if self._activity_allowed(context, "meal"):
            candidates.extend(self._food_candidates(context))
        else:
            self._reject(context, "Meal options", "disabled by allowed_activities.")
        if self._activity_allowed(context, "event"):
            candidates.extend(self._event_candidates(context))
        else:
            self._reject(context, "Event options", "disabled by allowed_activities.")
        candidates.sort(key=lambda item: item["score"], reverse=True)

        result = {
            "project": "GapWise: Campus Gap-Time Planner",
            "input_summary": {
                "current_time": format_minutes(current_time),
                "current_location": current_location,
                "next_class_time": format_minutes(next_class_time),
                "next_class_location": next_class_location,
                "gap_minutes": next_class_time - current_time,
                "priority": context["priority"],
                "budget": context["budget"],
                "min_activity_minutes": context["min_activity_minutes"],
                "max_walking_minutes": context["max_walking_minutes"],
                "avoid_shuttle": context["avoid_shuttle"],
                "allowed_activities": sorted(context["allowed_activities"]),
            },
            "best_plan": candidates[0] if candidates else None,
            "alternatives": candidates[1:4],
            "pipeline": [
                "Parsed user time, location, priority, budget, and preferences.",
                "Loaded mock campus study, cafeteria, event, location, and shuttle data.",
                "Estimated walking and shuttle travel times.",
                "Filtered options by opening hours, time fit, budget, and conflicts.",
                "Scored remaining options by priority, distance, comfort, cost, and relevance.",
                "Returned the best gap-time plan plus backup options.",
            ],
        }
        if include_explain:
            result["explanations"] = context["explanations"]
        return result

    def _study_candidates(self, context: dict) -> list[dict]:
        candidates = []
        for space in self.data["study_spaces"]:
            place = space["location"]
            arrival = self._earliest_travel(
                context["current_location"], place, context["current_time"], context
            )
            departure = self._latest_travel(
                place, context["next_class_location"], context["latest_arrival"], context
            )

            if arrival.arrive >= departure.depart:
                self._reject(context, space["name"], "not enough time after travel.")
                continue
            if self._walking_limit_exceeded(context, arrival, departure):
                self._reject(context, space["name"], "walking time exceeds max_walking_minutes.")
                continue
            if not is_open(space["open"], arrival.arrive) or not is_open(space["open"], departure.depart):
                self._reject(context, space["name"], "study space is closed during the usable window.")
                continue

            usable_minutes = departure.depart - arrival.arrive
            if usable_minutes < context["min_activity_minutes"]:
                self._reject(
                    context,
                    space["name"],
                    f"only {format_duration(usable_minutes)} usable, below minimum activity time.",
                )
                continue

            quiet_match = 1 if "quiet" in context["priority"] and space["noise_level"] == "quiet" else 0
            seat_ratio = space["seats_available"] / max(space["capacity"], 1)
            tag_matches = self._tag_matches(space.get("tags", []), context)
            distance_penalty = arrival.minutes + departure.minutes
            score_breakdown = [
                {"label": "Base study score", "value": 40},
                {"label": "Usable time bonus", "value": round(min(usable_minutes, 90) * 0.35, 1)},
                {"label": "Seat availability bonus", "value": round(seat_ratio * 20, 1)},
                {"label": "Quiet priority bonus", "value": quiet_match * 25},
                {"label": "Preference tag bonus", "value": tag_matches * 8},
                {"label": "Travel time penalty", "value": round(-distance_penalty * 0.55, 1)},
            ]

            score = (
                40
                + min(usable_minutes, 90) * 0.35
                + seat_ratio * 20
                + quiet_match * 25
                + tag_matches * 8
                - distance_penalty * 0.55
            )

            candidates.append(
                {
                    "type": "quiet study" if space["noise_level"] == "quiet" else "study",
                    "title": f"Study at {space['name']}",
                    "score": round(score, 1),
                    "location": place,
                    "usable_minutes": usable_minutes,
                    "reason": self._study_reason(space, usable_minutes, quiet_match, tag_matches),
                    "score_breakdown": score_breakdown,
                    "steps": [
                        self._travel_step(arrival),
                        {
                            "action": f"Study at {space['name']}",
                            "start": format_minutes(arrival.arrive),
                            "end": format_minutes(departure.depart),
                            "duration": format_duration(usable_minutes),
                            "detail": (
                                f"{space['noise_level']} space, "
                                f"{space['seats_available']} of {space['capacity']} seats available"
                            ),
                        },
                        self._travel_step(departure),
                    ],
                }
            )
            self._accept(context, space["name"], "study option fits time, opening hours, and preferences.")
        return candidates

    def _food_candidates(self, context: dict) -> list[dict]:
        candidates = []
        if context["budget"] <= 0:
            self._reject(context, "Meal options", "budget is 0, so meals are skipped.")
            return candidates

        for cafeteria in self.data["cafeterias"]:
            place = cafeteria["location"]
            arrival = self._earliest_travel(
                context["current_location"], place, context["current_time"], context
            )
            departure = self._latest_travel(
                place, context["next_class_location"], context["latest_arrival"], context
            )
            if arrival.arrive >= departure.depart:
                self._reject(context, cafeteria["name"], "not enough time after travel.")
                continue
            if self._walking_limit_exceeded(context, arrival, departure):
                self._reject(context, cafeteria["name"], "walking time exceeds max_walking_minutes.")
                continue
            if not is_open(cafeteria["open"], arrival.arrive):
                self._reject(context, cafeteria["name"], "cafeteria is closed when the student arrives.")
                continue

            best_item = self._best_menu_item(cafeteria["menu"], context)
            if best_item is None:
                self._reject(context, cafeteria["name"], "no menu item fits the budget.")
                continue

            wait = cafeteria["wait_minutes_by_congestion"][cafeteria["congestion"]]
            meal_minutes = wait + cafeteria["average_eating_minutes"]
            usable_minutes = departure.depart - arrival.arrive
            if usable_minutes < meal_minutes:
                self._reject(
                    context,
                    cafeteria["name"],
                    f"meal needs {format_duration(meal_minutes)}, but only "
                    f"{format_duration(usable_minutes)} is available.",
                )
                continue
            if meal_minutes < context["min_activity_minutes"]:
                self._reject(context, cafeteria["name"], "meal duration is below minimum activity time.")
                continue

            congestion_score = {"low": 20, "medium": 10, "high": 0}[cafeteria["congestion"]]
            budget_left = context["budget"] - best_item["price"]
            priority_bonus = 20 if any(word in context["priority"] for word in ["food", "meal", "eat", "cheap"]) else 0
            diet_bonus = 12 if context["dietary_tags"] and context["dietary_tags"].intersection(best_item["tags"]) else 0
            score_breakdown = [
                {"label": "Base meal score", "value": 38},
                {"label": "Food priority bonus", "value": priority_bonus},
                {"label": "Dietary match bonus", "value": diet_bonus},
                {"label": "Congestion bonus", "value": congestion_score},
                {"label": "Budget remaining bonus", "value": round(min(budget_left / 600, 10), 1)},
                {"label": "Travel time penalty", "value": round(-(arrival.minutes + departure.minutes) * 0.45, 1)},
            ]

            score = (
                38
                + priority_bonus
                + diet_bonus
                + congestion_score
                + min(budget_left / 600, 10)
                - (arrival.minutes + departure.minutes) * 0.45
            )

            candidates.append(
                {
                    "type": "meal",
                    "title": f"Eat at {cafeteria['name']}",
                    "score": round(score, 1),
                    "location": place,
                    "usable_minutes": usable_minutes,
                    "reason": (
                        f"{best_item['name']} fits the budget at {best_item['price']} KRW; "
                        f"current congestion is {cafeteria['congestion']}."
                    ),
                    "score_breakdown": score_breakdown,
                    "steps": [
                        self._travel_step(arrival),
                        {
                            "action": f"Order {best_item['name']}",
                            "start": format_minutes(arrival.arrive),
                            "end": format_minutes(arrival.arrive + meal_minutes),
                            "duration": format_duration(meal_minutes),
                            "detail": (
                                f"{best_item['price']} KRW, tags: "
                                f"{', '.join(best_item['tags'])}"
                            ),
                        },
                        self._travel_step(departure),
                    ],
                }
            )
            self._accept(context, cafeteria["name"], "meal option fits budget, travel, and time constraints.")
        return candidates

    def _event_candidates(self, context: dict) -> list[dict]:
        candidates = []
        for event in self.data["events"]:
            event_start = parse_day_time(f"{event['day']} {event['start_time']}")
            event_end = parse_day_time(f"{event['day']} {event['end_time']}")
            if event_end <= context["current_time"] or event_start >= context["next_class_time"]:
                self._reject(context, event["title"], "event does not overlap with the gap.")
                continue

            place = event["location"]
            arrival = self._earliest_travel(
                context["current_location"], place, context["current_time"], context
            )
            departure = self._latest_travel(
                place, context["next_class_location"], context["latest_arrival"], context
            )
            if arrival.arrive >= departure.depart:
                self._reject(context, event["title"], "not enough time after travel.")
                continue
            if self._walking_limit_exceeded(context, arrival, departure):
                self._reject(context, event["title"], "walking time exceeds max_walking_minutes.")
                continue

            attend_start = max(arrival.arrive, event_start)
            attend_end = min(departure.depart, event_end)
            attend_minutes = attend_end - attend_start
            if attend_minutes < context["min_activity_minutes"]:
                self._reject(
                    context,
                    event["title"],
                    f"can attend only {format_duration(attend_minutes)}, below minimum activity time.",
                )
                continue

            tag_matches = self._tag_matches(event.get("tags", []), context)
            priority_bonus = 18 if any(word in context["priority"] for word in ["event", "seminar", "social"]) else 0
            score_breakdown = [
                {"label": "Base event score", "value": 32},
                {"label": "Event priority bonus", "value": priority_bonus},
                {"label": "Preference tag bonus", "value": tag_matches * 12},
                {"label": "Attendable time bonus", "value": round(min(attend_minutes, 60) * 0.35, 1)},
                {"label": "Travel time penalty", "value": round(-(arrival.minutes + departure.minutes) * 0.5, 1)},
            ]
            score = (
                32
                + priority_bonus
                + tag_matches * 12
                + min(attend_minutes, 60) * 0.35
                - (arrival.minutes + departure.minutes) * 0.5
            )

            candidates.append(
                {
                    "type": "event",
                    "title": event["title"],
                    "score": round(score, 1),
                    "location": place,
                    "usable_minutes": attend_minutes,
                    "reason": (
                        f"Matches {tag_matches} preference tag(s) and can be attended "
                        f"for {format_duration(attend_minutes)}."
                    ),
                    "score_breakdown": score_breakdown,
                    "steps": [
                        self._travel_step(arrival),
                        {
                            "action": f"Attend {event['title']}",
                            "start": format_minutes(attend_start),
                            "end": format_minutes(attend_end),
                            "duration": format_duration(attend_minutes),
                            "detail": event["description"],
                        },
                        self._travel_step(departure),
                    ],
                }
            )
            self._accept(context, event["title"], "event overlaps with the gap and fits travel time.")
        return candidates

    def _earliest_travel(self, origin: str, destination: str, depart_at: int, context: dict) -> TravelSegment:
        walking = self._walking_segment(origin, destination, depart_at)
        if context["avoid_shuttle"]:
            return walking
        shuttle = self._earliest_shuttle_segment(origin, destination, depart_at)
        if shuttle and shuttle.arrive < walking.arrive:
            return shuttle
        return walking

    def _latest_travel(self, origin: str, destination: str, arrive_by: int, context: dict) -> TravelSegment:
        walk_minutes = self._walking_minutes(origin, destination)
        detail = (
            "Already at the destination."
            if walk_minutes == 0
            else f"Walk directly for about {walk_minutes} minutes."
        )
        walking = TravelSegment(
            mode="walk",
            origin=origin,
            destination=destination,
            depart=arrive_by - walk_minutes,
            arrive=arrive_by,
            minutes=walk_minutes,
            detail=detail,
        )

        if context["avoid_shuttle"]:
            return walking
        shuttle = self._latest_shuttle_segment(origin, destination, arrive_by)
        if shuttle and shuttle.depart > walking.depart:
            return shuttle
        return walking

    def _walking_segment(self, origin: str, destination: str, depart_at: int) -> TravelSegment:
        minutes = self._walking_minutes(origin, destination)
        detail = (
            "Already at the destination."
            if minutes == 0
            else f"Walk directly for about {minutes} minutes."
        )
        return TravelSegment(
            mode="walk",
            origin=origin,
            destination=destination,
            depart=depart_at,
            arrive=depart_at + minutes,
            minutes=minutes,
            detail=detail,
        )

    def _earliest_shuttle_segment(self, origin: str, destination: str, depart_at: int) -> TravelSegment | None:
        origin_stop = self.locations[origin].get("nearest_shuttle_stop")
        destination_stop = self.locations[destination].get("nearest_shuttle_stop")
        if not origin_stop or not destination_stop or origin_stop == destination_stop:
            return None

        walk_to_stop = self._walking_minutes(origin, origin_stop)
        walk_from_stop = self._walking_minutes(destination_stop, destination)
        stop_arrival = depart_at + walk_to_stop

        best = None
        for trip in self.data["shuttles"]:
            if trip["from_stop"] != origin_stop or trip["to_stop"] != destination_stop:
                continue
            trip_depart = parse_day_time(f"{trip['day']} {trip['departure_time']}")
            trip_arrive = parse_day_time(f"{trip['day']} {trip['arrival_time']}")
            if trip_depart < stop_arrival:
                continue
            final_arrival = trip_arrive + walk_from_stop
            candidate = TravelSegment(
                mode="shuttle",
                origin=origin,
                destination=destination,
                depart=depart_at,
                arrive=final_arrival,
                minutes=final_arrival - depart_at,
                detail=(
                    f"Walk {walk_to_stop} min to {origin_stop}, take {trip['route']} "
                    f"at {trip['departure_time']}, then walk {walk_from_stop} min."
                ),
            )
            if best is None or candidate.arrive < best.arrive:
                best = candidate
        return best

    def _latest_shuttle_segment(self, origin: str, destination: str, arrive_by: int) -> TravelSegment | None:
        origin_stop = self.locations[origin].get("nearest_shuttle_stop")
        destination_stop = self.locations[destination].get("nearest_shuttle_stop")
        if not origin_stop or not destination_stop or origin_stop == destination_stop:
            return None

        walk_to_stop = self._walking_minutes(origin, origin_stop)
        walk_from_stop = self._walking_minutes(destination_stop, destination)
        best = None

        for trip in self.data["shuttles"]:
            if trip["from_stop"] != origin_stop or trip["to_stop"] != destination_stop:
                continue
            trip_depart = parse_day_time(f"{trip['day']} {trip['departure_time']}")
            trip_arrive = parse_day_time(f"{trip['day']} {trip['arrival_time']}")
            final_arrival = trip_arrive + walk_from_stop
            if final_arrival > arrive_by:
                continue
            origin_depart = trip_depart - walk_to_stop
            candidate = TravelSegment(
                mode="shuttle",
                origin=origin,
                destination=destination,
                depart=origin_depart,
                arrive=final_arrival,
                minutes=final_arrival - origin_depart,
                detail=(
                    f"Walk {walk_to_stop} min to {origin_stop}, take {trip['route']} "
                    f"at {trip['departure_time']}, then walk {walk_from_stop} min."
                ),
            )
            if best is None or candidate.depart > best.depart:
                best = candidate
        return best

    def _walking_minutes(self, origin: str, destination: str) -> int:
        self._require_location(origin)
        self._require_location(destination)
        if origin == destination:
            return 0
        start = self.locations[origin]
        end = self.locations[destination]
        distance = sqrt((start["x"] - end["x"]) ** 2 + (start["y"] - end["y"]) ** 2)
        return max(2, ceil(distance * 8))

    def _best_menu_item(self, menu: list[dict], context: dict) -> dict | None:
        affordable = [item for item in menu if item["price"] <= context["budget"]]
        if not affordable:
            return None

        def item_score(item: dict) -> tuple[int, int]:
            item_tags = set(tag.lower() for tag in item.get("tags", []))
            diet_match = len(context["dietary_tags"].intersection(item_tags))
            return diet_match, -item["price"]

        selected = max(affordable, key=item_score).copy()
        selected["tags"] = [tag.lower() for tag in selected.get("tags", [])]
        return selected

    def _tag_matches(self, tags: list[str], context: dict) -> int:
        all_preferences = set(context["priority"].replace("/", " ").split())
        all_preferences.update(context["interests"])
        all_preferences.update(context["dietary_tags"])
        return len(set(tag.lower() for tag in tags).intersection(all_preferences))

    def _study_reason(self, space: dict, usable_minutes: int, quiet_match: int, tag_matches: int) -> str:
        reasons = [
            f"Available for {format_duration(usable_minutes)}",
            f"{space['seats_available']} seats open",
            f"noise level is {space['noise_level']}",
        ]
        if quiet_match:
            reasons.append("matches quiet-study priority")
        if tag_matches:
            reasons.append(f"matches {tag_matches} preference tag(s)")
        return "; ".join(reasons) + "."

    def _travel_step(self, segment: TravelSegment) -> dict:
        action = (
            f"Stay at {segment.destination}"
            if segment.minutes == 0
            else f"Travel to {segment.destination}"
        )
        return {
            "action": action,
            "start": format_minutes(segment.depart),
            "end": format_minutes(segment.arrive),
            "duration": format_duration(segment.minutes),
            "detail": segment.detail,
        }

    def _activity_allowed(self, context: dict, activity: str) -> bool:
        return not context["allowed_activities"] or activity in context["allowed_activities"]

    def _walking_limit_exceeded(
        self, context: dict, arrival: TravelSegment, departure: TravelSegment
    ) -> bool:
        limit = context["max_walking_minutes"]
        if limit is None:
            return False
        walking_segments = [
            segment.minutes
            for segment in [arrival, departure]
            if segment.mode == "walk"
        ]
        return any(minutes > limit for minutes in walking_segments)

    def _accept(self, context: dict, title: str, reason: str) -> None:
        if context["include_explain"]:
            context["explanations"].append(f"Accepted {title}: {reason}")

    def _reject(self, context: dict, title: str, reason: str) -> None:
        if context["include_explain"]:
            context["explanations"].append(f"Rejected {title}: {reason}")

    def _require_location(self, name: str) -> None:
        if name not in self.locations:
            available = ", ".join(sorted(self.locations.keys()))
            raise ValueError(f"Unknown location {name!r}. Available locations: {available}")
