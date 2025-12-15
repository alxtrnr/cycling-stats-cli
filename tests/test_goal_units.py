import unittest
from datetime import date
from decimal import Decimal

from goal_tracker import (
    Goal,
    GoalType,
    calculate_goal_progress_v2,
    get_goal_display_unit,
)


def make_trip(distance_m: int, elevation_m: int, departed_at: str = "2025-06-01T00:00:00Z") -> dict:
    return {
        "id": hash(departed_at) % 10_000_000,
        "distance": distance_m,
        "elevation_gain": elevation_m,
        "departed_at": departed_at,
    }


class GoalUnitConversionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.window_start = date(2025, 1, 1)
        self.window_end = date(2025, 12, 31)

    def _build_goal(self, *, goal_type: GoalType, target: Decimal, unit: str) -> Goal:
        return Goal(
            goal_id="test-goal",
            title="Test Goal",
            type=goal_type,
            target=target,
            unit=unit,
            start_date=self.window_start,
            end_date=self.window_end,
            created_at=self.window_start,
        )

    def test_distance_goal_converts_target_and_current_to_miles(self):
        trips = [
            make_trip(distance_m=10_000, elevation_m=0),  # 10 km
            make_trip(distance_m=5_000, elevation_m=0),   # 5 km
        ]
        goal = self._build_goal(goal_type=GoalType.DISTANCE, target=Decimal("100"), unit="km")

        progress = calculate_goal_progress_v2(goal, trips, distance_unit_for_display="miles")

        # 15 km -> 9.320567 miles
        self.assertAlmostEqual(float(progress.current_distance), 9.320567, places=5)
        # Target 100 km -> 62.137119 miles
        self.assertAlmostEqual(float(progress.goal_distance), 62.137119, places=5)

    def test_distance_goal_stays_in_km_when_display_is_km(self):
        trips = [make_trip(distance_m=10_000, elevation_m=0)]
        goal = self._build_goal(goal_type=GoalType.DISTANCE, target=Decimal("50"), unit="km")

        progress = calculate_goal_progress_v2(goal, trips, distance_unit_for_display="km")

        self.assertAlmostEqual(float(progress.current_distance), 10.0, places=3)
        self.assertAlmostEqual(float(progress.goal_distance), 50.0, places=3)

    def test_elevation_goal_converts_to_feet_when_displaying_miles(self):
        trips = [make_trip(distance_m=0, elevation_m=200)]
        goal = self._build_goal(goal_type=GoalType.ELEVATION, target=Decimal("1000"), unit="m")

        display_unit = get_goal_display_unit(goal, distance_unit_for_display="miles")
        self.assertEqual(display_unit, "ft")

        progress = calculate_goal_progress_v2(goal, trips, distance_unit_for_display="miles")

        # 200 m -> 656.16798 ft
        self.assertAlmostEqual(float(progress.current_distance), 656.16798, places=4)
        # 1000 m -> 3280.839895 ft
        self.assertAlmostEqual(float(progress.goal_distance), 3280.839895, places=4)

    def test_elevation_goal_stays_in_meters_when_displaying_km(self):
        trips = [make_trip(distance_m=0, elevation_m=500)]
        goal = self._build_goal(goal_type=GoalType.ELEVATION, target=Decimal("2000"), unit="m")

        display_unit = get_goal_display_unit(goal, distance_unit_for_display="km")
        self.assertEqual(display_unit, "m")

        progress = calculate_goal_progress_v2(goal, trips, distance_unit_for_display="km")

        self.assertAlmostEqual(float(progress.current_distance), 500.0, places=3)
        self.assertAlmostEqual(float(progress.goal_distance), 2000.0, places=3)

    def test_ride_count_goal_uses_rides(self):
        trips = [
            make_trip(distance_m=1000, elevation_m=0),
            make_trip(distance_m=1000, elevation_m=0, departed_at="2025-02-01T00:00:00Z"),
        ]
        goal = self._build_goal(goal_type=GoalType.RIDE_COUNT, target=Decimal("5"), unit="")
        progress = calculate_goal_progress_v2(goal, trips, distance_unit_for_display="miles")
        self.assertEqual(progress.current_distance, Decimal("2"))
        self.assertEqual(progress.goal_distance, Decimal("5"))

    def test_time_goal_uses_hours(self):
        trips = [
            {
                "id": 1,
                "distance": 0,
                "departed_at": "2025-01-01T00:00:00Z",
                "moving_time": 3600,
            }
        ]
        goal = self._build_goal(goal_type=GoalType.TIME, target=Decimal("10"), unit="h")
        progress = calculate_goal_progress_v2(goal, trips, distance_unit_for_display="km")
        self.assertAlmostEqual(float(progress.current_distance), 1.0, places=3)
        self.assertEqual(progress.goal_distance, Decimal("10"))


if __name__ == "__main__":
    unittest.main()
