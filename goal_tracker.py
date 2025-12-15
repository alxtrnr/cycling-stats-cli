# goal_tracker.py

"""
Goal tracking module for cycling distance goals.
Calculates progress and pacing requirements for annual distance targets.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4
from datetime import datetime, date
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, TypedDict, Literal

getcontext().prec = 28

# Conversion constants (reusing from existing app)
METERS_TO_MILES = Decimal("0.000621371192237334")
METERS_TO_KM = Decimal("0.001")
KM_TO_MILES = Decimal("0.621371192237334")
MILES_TO_KM = Decimal("1.609344")
METERS_TO_FEET = Decimal("3.280839895013123")
FEET_TO_METERS = Decimal("0.3048")


class GoalType(str, Enum):
    DISTANCE = "distance"
    RIDE_COUNT = "ride_count"
    ELEVATION = "elevation"
    TIME = "time"
    FREQUENCY = "frequency"


class ElevationUnit(str, Enum):
    METERS = "m"
    FEET = "ft"


class GoalDict(TypedDict, total=False):
    goal_id: str
    title: str
    type: Literal['distance', 'ride_count', 'elevation', 'time', 'frequency']
    target: str  # Decimal as string or int-like
    unit: str  # 'km'|'miles' for distance; 'm'|'ft' for elevation; 'h' for time; '' for counts
    start_date: str  # 'YYYY-MM-DD'
    end_date: str  # 'YYYY-MM-DD'
    created_at: str


@dataclass(frozen=True)
class Goal:
    goal_id: str
    title: str
    type: GoalType
    target: Decimal
    unit: str
    start_date: date
    end_date: date
    created_at: datetime


class GoalProgress(NamedTuple):
    """Data structure for goal progress and pacing information."""
    goal_distance: Decimal
    current_distance: Decimal
    days_passed: int
    days_remaining: int
    total_days: int
    percent_year_elapsed: float
    percent_goal_completed: float
    status: str  # "ahead", "behind", "on_track"
    pace_difference: float
    daily_target: float
    weekly_target: float
    monthly_target: float


class GoalSettings:
    """Manages goal settings persistence."""

    def __init__(self, config_file: str = '.goal_config.json'):
        self.config_file = Path(config_file)
        self._settings = self._load_settings()

    def _load_settings(self) -> Dict:
        """Load goal settings from file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Failed to load goal settings: {e}")

        return {
            'goals': {},  # legacy: {year: {'distance': str, 'unit': 'km'|'miles'}}
            'goals_v2': {},  # new: {goal_id: { ... }}
            'default_unit': 'km'
        }

    def save_settings(self) -> None:
        """Save current settings to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2, default=str)
        except IOError as e:
            logging.error(f"Failed to save goal settings: {e}")

    def set_goal(self, year: int, distance: Decimal, unit: str) -> None:
        """Set annual distance goal for specified year."""
        if unit not in ['km', 'miles']:
            raise ValueError(f"Invalid unit: {unit}")

        self._settings['goals'][str(year)] = {
            'distance': str(distance),
            'unit': unit
        }
        self.save_settings()

    def get_goal(self, year: int) -> Optional[tuple[Decimal, str]]:
        """Get goal for specified year. Returns (distance, unit) or None."""
        goal_data = self._settings['goals'].get(str(year))
        if goal_data:
            return Decimal(goal_data['distance']), goal_data['unit']
        return None

    def get_current_goal(self) -> Optional[tuple[Decimal, str]]:
        """Get goal for current year."""
        return self.get_goal(datetime.now().year)

    def add_goal(self, *, title: str, type: GoalType, target: Decimal,
                 unit: str, start_date: date, end_date: date) -> Goal:
        """Add a new goal and return the created Goal object."""
        gid = str(uuid4())
        g: GoalDict = {
            'goal_id': gid,
            'title': title,
            'type': type.value,
            'target': str(target),
            'unit': unit,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'created_at': datetime.utcnow().isoformat()
        }

        self._settings['goals_v2'][gid] = g
        self.save_settings()
        return self._as_goal(g)

    def list_goals(self) -> list[Goal]:
        """List all enhanced goals."""
        return [self._as_goal(g) for g in self._settings.get('goals_v2', {}).values()]

    def delete_goal(self, goal_id: str) -> bool:
        """Delete a goal by ID."""
        removed = self._settings.get('goals_v2', {}).pop(goal_id, None) is not None
        if removed:
            self.save_settings()
        return removed

    def edit_goal(self, goal_id: str, **updates) -> bool:
        """Edit an existing goal."""
        g = self._settings.get('goals_v2', {}).get(goal_id)
        if not g:
            return False

        for k, v in updates.items():
            if k == 'target' and isinstance(v, Decimal):
                v = str(v)
            if k in ('start_date', 'end_date') and isinstance(v, (date, datetime)):
                v = v.date().isoformat() if isinstance(v, datetime) else v.isoformat()
            g[k] = v

        self.save_settings()
        return True

    def get_active_goals(self, ref: date | None = None) -> list[Goal]:
        """Get goals that are currently active."""
        r = ref or date.today()
        return [g for g in self.list_goals() if g.start_date <= r <= g.end_date]

    def _as_goal(self, g: GoalDict) -> Goal:
        """Convert GoalDict to Goal dataclass."""
        return Goal(
            goal_id=g['goal_id'],
            title=g.get('title', g['goal_id']),
            type=GoalType(g['type']),
            target=Decimal(g['target']),
            unit=g.get('unit', ''),
            start_date=date.fromisoformat(g['start_date']),
            end_date=date.fromisoformat(g['end_date']),
            created_at=datetime.fromisoformat(g['created_at'])
        )


def calculate_year_progress() -> tuple[int, int, int, float]:
    """Calculate year progress statistics."""
    today = date.today()
    start_of_year = date(today.year, 1, 1)
    end_of_year = date(today.year, 12, 31)

    days_passed = (today - start_of_year).days + 1
    days_remaining = (end_of_year - today).days
    total_days = (end_of_year - start_of_year).days + 1
    percent_elapsed = (days_passed / total_days) * 100

    return days_passed, days_remaining, total_days, percent_elapsed


def get_ytd_distance(trips: List[Dict], unit: str = 'km') -> Decimal:
    """Calculate year-to-date distance from trips."""
    conversion_factor = METERS_TO_KM if unit == 'km' else METERS_TO_MILES
    current_year = datetime.now().year
    ytd_distance = Decimal('0')

    for trip in trips:
        date_str = trip.get('departed_at')
        if not date_str or 'distance' not in trip:
            continue

        try:
            # Parse date
            date_str_clean = date_str.split('+')[0].rstrip('Z')
            trip_date = datetime.fromisoformat(date_str_clean)

            # Only include current year trips
            if trip_date.year == current_year:
                distance_meters = Decimal(str(trip['distance']))
                ytd_distance += distance_meters * conversion_factor

        except (ValueError, TypeError) as e:
            logging.debug(f"Error processing trip {trip.get('id', 'unknown')}: {e}")
            continue

    return ytd_distance


def calculate_goal_progress(
    goal_distance: Decimal,
    trips: List[Dict],
    unit: str = 'km'
) -> GoalProgress:
    """Calculate comprehensive goal progress and pacing information."""
    # Get year progress
    days_passed, days_remaining, total_days, percent_year_elapsed = calculate_year_progress()

    # Get current distance
    current_distance = get_ytd_distance(trips, unit)

    # Calculate goal completion percentage
    percent_goal_completed = (
        float((current_distance / goal_distance) * 100)
        if goal_distance > 0 else 0.0
    )

    # Determine status (ahead/behind/on track)
    pace_difference = percent_goal_completed - percent_year_elapsed
    if abs(pace_difference) <= 2.0:  # Within 2% is "on track"
        status = "on_track"
    elif pace_difference > 0:
        status = "ahead"
    else:
        status = "behind"

    # Calculate pacing targets
    remaining_distance = max(float(goal_distance - current_distance), 0.0)
    if days_remaining > 0:
        daily_target = remaining_distance / days_remaining
        weekly_target = daily_target * 7
        # Approximate months remaining
        months_remaining = days_remaining / 30.44
        monthly_target = remaining_distance / months_remaining if months_remaining > 0 else 0.0
    else:
        daily_target = weekly_target = monthly_target = 0.0

    return GoalProgress(
        goal_distance=goal_distance,
        current_distance=current_distance,
        days_passed=days_passed,
        days_remaining=days_remaining,
        total_days=total_days,
        percent_year_elapsed=percent_year_elapsed,
        percent_goal_completed=percent_goal_completed,
        status=status,
        pace_difference=pace_difference,
        daily_target=daily_target,
        weekly_target=weekly_target,
        monthly_target=monthly_target
    )


def format_goal_display(progress: GoalProgress, unit: str) -> str:
    """Format goal progress for display."""
    status_emoji = {
        "ahead": "🚀",
        "behind": "⚠️",
        "on_track": "✅"
    }

    status_text = {
        "ahead": f"Ahead of pace by {abs(progress.pace_difference):.1f}%",
        "behind": f"Behind pace by {abs(progress.pace_difference):.1f}%",
        "on_track": "On track"
    }

    return f"""
=== ANNUAL GOAL PROGRESS ({datetime.now().year}) ===
Goal: {progress.goal_distance:,.0f} {unit}
Current: {progress.current_distance:,.1f} {unit} ({progress.percent_goal_completed:.1f}% complete)
Year Progress: {progress.percent_year_elapsed:.1f}% elapsed
Days passed: {progress.days_passed} | Days remaining: {progress.days_remaining}
Status: {status_emoji[progress.status]} {status_text[progress.status]}

=== PACING TARGETS ===
To reach your goal, you need:
• Daily: {progress.daily_target:.1f} {unit}/day
• Weekly: {progress.weekly_target:.1f} {unit}/week
• Monthly: {progress.monthly_target:.1f} {unit}/month
"""


def _trips_in_window(trips: List[Dict], start: date, end: date) -> list[Dict]:
    """Filter trips within date window."""
    out: list[Dict] = []
    for t in trips:
        ds = t.get('departed_at')
        if not ds:
            continue
        try:
            d = datetime.fromisoformat(ds.split('+')[0].rstrip('Z')).date()
        except ValueError:
            continue
        if start <= d <= end:
            out.append(t)
    return out


def _sum_distance(trips: list[Dict], unit: str) -> Decimal:
    """Sum distance from trips in specified unit."""
    factor = METERS_TO_KM if unit == 'km' else METERS_TO_MILES
    total = Decimal('0')
    for t in trips:
        if 'distance' in t:
            total += Decimal(str(t['distance'])) * factor
    return total


def _convert_distance(value: Decimal, from_unit: str, to_unit: str) -> Decimal:
    """Convert a distance value between km and miles."""
    if from_unit == to_unit:
        return value
    if from_unit == 'km' and to_unit == 'miles':
        return value * KM_TO_MILES
    if from_unit == 'miles' and to_unit == 'km':
        return value * MILES_TO_KM
    # Fallback: if units are missing/unknown, return original
    return value


def get_goal_display_unit(goal: Goal, distance_unit_for_display: str) -> str:
    """Determine the display unit for a goal based on goal type and selected distance unit."""
    if goal.type == GoalType.DISTANCE:
        return distance_unit_for_display
    if goal.type == GoalType.ELEVATION:
        return 'ft' if distance_unit_for_display == 'miles' else 'm'
    if goal.type in (GoalType.RIDE_COUNT, GoalType.FREQUENCY):
        return 'rides'
    if goal.type == GoalType.TIME:
        return 'h'
    return goal.unit or distance_unit_for_display


def _sum_elevation(trips: list[Dict], unit: ElevationUnit) -> Decimal:
    """Sum elevation gain from trips."""
    total_m = Decimal('0')
    for t in trips:
        eg = t.get('elevation_gain') or t.get('elevation') or 0
        try:
            total_m += Decimal(str(eg))
        except Exception:
            continue

    if unit == ElevationUnit.FEET:
        return total_m * METERS_TO_FEET
    return total_m


def _convert_elevation(value: Decimal, from_unit: str, to_unit: str) -> Decimal:
    """Convert elevation between meters and feet."""
    if from_unit == to_unit:
        return value
    if from_unit == 'm' and to_unit == 'ft':
        return value * METERS_TO_FEET
    if from_unit == 'ft' and to_unit == 'm':
        return value * FEET_TO_METERS
    return value


def _sum_time_hours(trips: list[Dict]) -> Decimal:
    """Sum riding time in hours."""
    secs = Decimal('0')
    for t in trips:
        s = t.get('moving_time') or t.get('duration') or 0
        try:
            secs += Decimal(str(s))
        except Exception:
            continue
    return secs / Decimal('3600')


def _count_rides(trips: list[Dict]) -> int:
    """Count unique rides."""
    return len({t['id'] for t in trips if 'id' in t})


def calculate_goal_progress_v2(goal: Goal, trips: List[Dict], distance_unit_for_display: str) -> GoalProgress:
    """Calculate comprehensive goal progress for any goal type."""
    window_trips = _trips_in_window(trips, goal.start_date, goal.end_date)
    days_total = (goal.end_date - goal.start_date).days + 1
    days_passed = max((min(date.today(), goal.end_date) - goal.start_date).days + 1, 0)
    days_remaining = max(days_total - days_passed, 0)
    percent_elapsed = (days_passed / days_total) * 100 if days_total > 0 else 100.0

    display_unit = distance_unit_for_display or goal.unit or 'miles'

    target = goal.target

    if goal.type == GoalType.DISTANCE:
        base_unit = goal.unit or display_unit
        current = _sum_distance(window_trips, display_unit)
        target = _convert_distance(goal.target, base_unit, display_unit)
        unit = display_unit
    elif goal.type == GoalType.RIDE_COUNT:
        current = Decimal(str(_count_rides(window_trips)))
        unit = 'rides'
    elif goal.type == GoalType.ELEVATION:
        display_elev_unit = get_goal_display_unit(goal, display_unit)
        base_unit = goal.unit or display_elev_unit
        current_base = _sum_elevation(window_trips, ElevationUnit(base_unit))
        current = _convert_elevation(current_base, base_unit, display_elev_unit)
        target = _convert_elevation(goal.target, base_unit, display_elev_unit)
        unit = display_elev_unit
    elif goal.type == GoalType.TIME:
        current = _sum_time_hours(window_trips)
        unit = 'h'
    elif goal.type == GoalType.FREQUENCY:
        current = Decimal(str(_count_rides(window_trips)))
        unit = 'rides'
    else:
        current = Decimal('0')
        unit = ''

    # target may have been converted above for distance/elevation
    if goal.type not in (GoalType.DISTANCE, GoalType.ELEVATION):
        target = goal.target
    pct_completed = float((current / target) * 100) if target > 0 else 0.0
    pace_diff = pct_completed - percent_elapsed

    if abs(pace_diff) <= 2.0:
        status = "on_track"
    elif pace_diff > 0:
        status = "ahead"
    else:
        status = "behind"

    remaining = max(float(target - current), 0.0)
    daily = remaining / days_remaining if days_remaining > 0 else 0.0
    weekly = daily * 7
    months_remaining = days_remaining / 30.44
    monthly = remaining / months_remaining if months_remaining > 0 else 0.0

    return GoalProgress(
        goal_distance=target,
        current_distance=current,
        days_passed=days_passed,
        days_remaining=days_remaining,
        total_days=days_total,
        percent_year_elapsed=percent_elapsed,
        percent_goal_completed=pct_completed,
        status=status,
        pace_difference=pace_diff,
        daily_target=daily,
        weekly_target=weekly,
        monthly_target=monthly
    )
