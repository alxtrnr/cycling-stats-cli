import unittest
from decimal import Decimal
from datetime import datetime

from calculations import (
    analyze_ride_distribution,
    analyze_ride_metrics,
    calculate_eddington,
    calculate_next_yearly_e,
    calculate_overall_e_progress,
    calculate_rides_needed_next,
    calculate_statistics,
    calculate_yearly_eddington,
    get_highest_yearly_eddington,
    get_milestone_rides,
    get_ride_titles,
    verify_eddington,
)
from goal_tracker import calculate_goal_progress


def make_trip(distance_m: int, departed_at: str, name: str = "ride", elevation: int = 0):
    return {
        "id": hash((distance_m, departed_at, name)) % 1_000_000,
        "distance": distance_m,
        "departed_at": departed_at,
        "name": name,
        "elevation_gain": elevation,
    }


class CalculationsTests(unittest.TestCase):
    def test_calculate_eddington_basic(self):
        distances = [Decimal("10"), Decimal("20"), Decimal("20"), Decimal("30")]
        self.assertEqual(calculate_eddington(distances), 4)

    def test_calculate_statistics_empty(self):
        stats = calculate_statistics([])
        self.assertEqual(stats["total_distance"], Decimal("0"))

    def test_calculate_statistics_values(self):
        stats = calculate_statistics([Decimal("10"), Decimal("20")])
        self.assertEqual(stats["longest_ride"], Decimal("20"))
        self.assertEqual(stats["average_ride"], Decimal("15"))
        self.assertEqual(stats["total_distance"], Decimal("30"))

    def test_calculate_yearly_eddington(self):
        trips = [
            make_trip(10000, "2025-01-01T00:00:00Z"),
            make_trip(20000, "2025-02-01T00:00:00Z"),
            make_trip(5000, "2024-05-01T00:00:00Z"),
        ]
        yearly = calculate_yearly_eddington(trips, unit="km")
        self.assertIn(2025, yearly)
        self.assertGreaterEqual(yearly[2025], 1)

    def test_calculate_overall_e_progress(self):
        distances = [Decimal("10"), Decimal("20"), Decimal("20"), Decimal("5")]
        current_e, rides_at_next, rides_needed_next, rides_at_nextnext, rides_needed_nextnext = (
            calculate_overall_e_progress(distances)
        )
        self.assertEqual(current_e, 4)
        self.assertEqual(rides_at_next, 4)
        self.assertEqual(rides_needed_next, 1)
        self.assertEqual(rides_at_nextnext, 3)
        self.assertEqual(rides_needed_nextnext, 3)

    def test_get_highest_yearly_eddington(self):
        year, val = get_highest_yearly_eddington({2023: 10, 2024: 12})
        self.assertEqual((year, val), (2024, 12))
        self.assertEqual(get_highest_yearly_eddington({}), (0, 0))

    def test_analyze_ride_distribution(self):
        dist = [Decimal("5"), Decimal("15"), Decimal("25"), Decimal("35")]
        thresholds = analyze_ride_distribution(dist)
        self.assertIn(20, thresholds)
        self.assertGreaterEqual(thresholds[20], 2)

    def test_verify_eddington(self):
        msg = verify_eddington([Decimal("5"), Decimal("10")], 5)
        self.assertIn("E=5", msg)

    def test_get_milestone_rides_miles(self):
        dist = [Decimal("50"), Decimal("120"), Decimal("210")]
        milestones = get_milestone_rides(dist, unit="miles")
        self.assertEqual(milestones["centuries"], 2)
        self.assertEqual(milestones["double_centuries"], 1)

    def test_get_milestone_rides_km(self):
        dist = [Decimal("55"), Decimal("160"), Decimal("220"), Decimal("305")]
        milestones = get_milestone_rides(dist, unit="km")
        self.assertEqual(milestones["range_300_to_399"], 1)
        self.assertEqual(milestones["range_200_to_299"], 1)

    def test_get_ride_titles_sorted(self):
        trips = [
            make_trip(10000, "2025-01-01T00:00:00Z", name="short"),
            make_trip(30000, "2025-01-02T00:00:00Z", name="long"),
        ]
        pairs = get_ride_titles(trips, [Decimal("10"), Decimal("30")], unit="km")
        self.assertEqual(pairs[0][1], "long")

    def test_analyze_ride_metrics(self):
        trips = [
            make_trip(10000, "2025-01-01T00:00:00Z"),
            make_trip(20000, "2025-01-15T00:00:00Z"),
            make_trip(20000, "2025-02-01T00:00:00Z"),
        ]
        metrics = analyze_ride_metrics(trips, unit="km")
        self.assertIn("monthly_totals", metrics)
        self.assertIn("rides_needed_next_e", metrics)
        self.assertEqual(metrics["next_e_target"], 4)

    def test_calculate_rides_needed_next(self):
        dist = [Decimal("10"), Decimal("10"), Decimal("1")]
        self.assertEqual(calculate_rides_needed_next(dist), 1)

    def test_calculate_next_yearly_e(self):
        trips = [
            make_trip(10000, "2025-03-01T00:00:00Z"),
            make_trip(20000, "2025-04-01T00:00:00Z"),
        ]
        next_e, rides_at_target, rides_needed = calculate_next_yearly_e(trips, 2025, unit="km")
        self.assertEqual(next_e, 3)
        self.assertGreaterEqual(rides_needed, 0)

    def test_calculate_goal_progress_legacy(self):
        trips = [
            make_trip(10000, f"2025-01-0{i}T00:00:00Z")
            for i in range(1, 4)
        ]
        progress = calculate_goal_progress(Decimal("100"), trips, unit="km")
        self.assertGreater(progress.percent_goal_completed, 0)


if __name__ == "__main__":
    unittest.main()
