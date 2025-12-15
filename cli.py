# cli.py

from __future__ import annotations

import argparse
import os
from datetime import datetime, date
from typing import List, Dict
from pathlib import Path
from decimal import Decimal

from main import update_cache, process_trips, RWGPSClient
from calculations import (
    calculate_statistics, calculate_yearly_eddington,
    analyze_ride_distribution, analyze_ride_metrics,
    calculate_overall_e_progress, get_ride_titles,
    calculate_next_yearly_e
)
from config import API_KEY, CACHE_FILE, DEFAULT_UNIT
from auth import get_credentials
from goal_tracker import (
    GoalSettings, GoalType,
    calculate_goal_progress, calculate_goal_progress_v2,
    format_goal_display, get_goal_display_unit
)


def get_preferred_unit() -> str:
    """Load the user's preferred unit from file."""
    try:
        with open('.unit_preference', 'r') as f:
            unit = f.read().strip()
            if unit in ['miles', 'km']:
                return unit
    except FileNotFoundError:
        pass
    return DEFAULT_UNIT


def save_preferred_unit(unit: str) -> None:
    """Save the user's preferred unit to file."""
    with open('.unit_preference', 'w') as f:
        f.write(unit)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Cycling Statistics Analysis')

    # Global options
    parser.add_argument('--unit', choices=['miles', 'km'], default=None,
                       help='Distance unit (miles or km)')
    parser.add_argument('--refresh', action='store_true',
                       help='Force refresh data instead of using cache')

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Full summary command
    subparsers.add_parser('summary', help='Display full statistics summary')

    add_goal_commands_to_parser(subparsers)

    # Individual section commands
    subparsers.add_parser('eddington', help='Show Eddington number progress')
    subparsers.add_parser('ytd', help='Show year-to-date statistics')
    subparsers.add_parser('yearly', help='Show yearly Eddington numbers')
    subparsers.add_parser('metrics', help='Show ride metrics')
    subparsers.add_parser('distribution', help='Show ride distribution')
    subparsers.add_parser('distance', help='Show distance achievements')
    subparsers.add_parser('longest', help='Show top 5 longest rides')
    subparsers.add_parser('monthly', help='Show monthly statistics')

    # Unit command
    unit_parser = subparsers.add_parser('unit', help='Set or toggle distance unit')
    unit_parser.add_argument('value', nargs='?', choices=['miles', 'km', 'toggle'],
                           default='toggle',
                           help='Unit to use (miles, km) or toggle between them')

    # Status command
    subparsers.add_parser('status', help='Show current unit setting and stats')

    return parser


def display_eddington(trips: List[dict], distances: List[Decimal], unit: str = 'miles') -> None:
    current_e, rides_at_next, rides_needed_next, rides_at_nextnext, rides_needed_nextnext = \
        calculate_overall_e_progress(distances, unit)

    print("\n=== OVERALL EDDINGTON PROGRESS ===")
    print(f"Current overall Eddington: {current_e}")
    print(f"In progress: E={current_e + 1} ({rides_at_next} rides of {current_e + 1}+ {unit})")
    print(f"Need {rides_needed_next} more rides of {current_e + 1}+ {unit} for E={current_e + 1}")
    print(f"Next goal after that: E={current_e + 2} ({rides_at_nextnext} rides of {current_e + 2}+ {unit})")
    print(f"Will need {rides_needed_nextnext} more rides of {current_e + 2}+ {unit} for E={current_e + 2}")


def display_ytd(trips: List[dict], yearly_eddington: Dict[int, int], unit: str = 'miles') -> None:
    current_year = datetime.now().year
    if current_year in yearly_eddington:
        ytd_rides = []
        for trip in trips:
            date_str = trip.get('departed_at')
            if date_str:
                try:
                    date_str = date_str.split('+')[0].rstrip('Z')
                    trip_date = datetime.fromisoformat(date_str)
                    if trip_date.year == current_year:
                        ytd_rides.append(trip)
                except ValueError:
                    continue

        ytd_distances = process_trips(ytd_rides, unit)
        ytd_stats = calculate_statistics(ytd_distances, unit)
        next_e, rides_at_target, rides_needed = calculate_next_yearly_e(trips, current_year, unit)

        print(f"\n=== EDDINGTON YEAR TO DATE ({current_year}) ===")
        print(f"Rides this year: {len(ytd_rides)}")
        print(f"Distance this year: {ytd_stats['total_distance']:,.1f} {unit}")
        print(f"Current year Eddington: {yearly_eddington[current_year]}")
        print(f"In progress: E={next_e} ({rides_at_target} rides of {next_e}+ {unit})")
        print(f"Need {rides_needed} more rides of {next_e}+ {unit} for E={next_e}")


def display_yearly(yearly_eddington: Dict[int, int]) -> None:
    print("\n=== YEARLY EDDINGTON NUMBERS ===")
    highest_e = max(yearly_eddington.values()) if yearly_eddington else 0
    for year in sorted(yearly_eddington.keys(), reverse=True):
        suffix = " *Highest*" if yearly_eddington[year] == highest_e else ""
        print(f"{year}: {yearly_eddington[year]}{suffix}")


def display_metrics(stats: Dict[str, Decimal], unit: str = 'miles') -> None:
    print("\n=== RIDE METRICS ===")
    print(f"Longest ride: {stats['longest_ride']:.1f} {unit}")
    print(f"Average ride: {stats['average_ride']:.1f} {unit}")
    print(f"Total distance: {stats['total_distance']:.1f} {unit}")


def display_distribution(distances: List[Decimal], unit: str = 'miles') -> None:
    print(f"\n=== RIDE DISTRIBUTION ===")

    # Create range buckets
    buckets = {}
    bucket_size = 50
    max_distance = max(distances) if distances else 0

    for i in range(0, int(max_distance) + bucket_size, bucket_size):
        lower = i
        upper = i + bucket_size
        count = sum(1 for d in distances if lower <= d < upper)
        if count > 0:
            buckets[f"{lower}-{upper}"] = count

    # Display as table with percentages
    total = len(distances)
    print(f"{'Range':<15} | {'Count':<6} | {'Percentage':<10}")
    print(f"{'-' * 15}-|{'-' * 8}|{'-' * 10}")
    for range_label, count in buckets.items():
        percentage = (count / total) * 100
        print(f"{range_label:<15} | {count:<6} | {percentage:.2f}%")


def display_milestones(metrics: Dict, unit: str = 'miles') -> None:
    print("\n=== DISTANCE ACHIEVEMENTS ===")
    milestones = metrics['milestone_rides']

    if unit == 'miles':
        print(f"Century rides (100+ {unit}): {milestones['centuries']}")
        print(f"Double centuries (200+ {unit}): {milestones['double_centuries']}")
        print(f"Triple centuries (300+ {unit}): {milestones['triple_centuries']}")
        print(f"Quad centuries (400+ {unit}): {milestones['quad_centuries']}")
    else:  # kilometers
        print(f"Randonneur 50 {unit}: {milestones['range_50_to_99']}")
        print(f"Randonneur 100 {unit}: {milestones['range_100_to_149']}")
        print(f"Randonneur 150 {unit}: {milestones['range_150_to_199']}")
        print(f"Randonneur 200 {unit}: {milestones['range_200_to_299']}")
        print(f"Randonneur 300 {unit}: {milestones['range_300_to_399']}")
        print(f"Randonneur 400 {unit}: {milestones['range_400_to_599']}")
        print(f"Randonneur 600 {unit}: {milestones['range_600_to_999']}")
        print(f"Randonneur 1000 {unit}: {milestones['range_1000_plus']}")


def display_longest(trips: List[dict], distances: List[Decimal], unit: str = 'miles') -> None:
    print("\n=== TOP 5 LONGEST RIDES ===")
    distance_titles = get_ride_titles(trips, distances, unit)
    for i, (distance, title) in enumerate(distance_titles[:5], 1):
        print(f"{i}. {distance:.1f} {unit} - {title}")


def display_monthly(metrics: Dict, unit: str = 'miles') -> None:
    print("\n=== MONTHLY STATISTICS ===")
    current_date = datetime.now()

    month_tuples = []
    for month in metrics['monthly_totals'].keys():
        year, month_num = map(int, month.split('-'))
        month_tuples.append((datetime(year, month_num, 1), month))

    sorted_months = [month for _, month in sorted(month_tuples, reverse=True)][:12]

    for month in sorted_months:
        rides = metrics['monthly_counts'][month]
        distance = metrics['monthly_totals'][month]
        print(f"{month}: {rides} rides, {distance:.1f} {unit}")


def display_status(unit: str = 'miles') -> None:
    print(f"\n=== CURRENT SETTINGS ===")
    print(f"Distance unit: {unit}")
    cache_file = CACHE_FILE
    print(f"Cache file: {cache_file}")

    if os.path.exists(cache_file):
        print("Cache status: Available")
    else:
        print("Cache status: Not available")


def handle_unit_command(args) -> str:
    current_unit = args.unit if args.unit else get_preferred_unit()
    new_unit = args.value

    if new_unit == 'toggle':
        new_unit = 'km' if current_unit == 'miles' else 'miles'

    save_preferred_unit(new_unit)
    print(f"Unit changed to: {new_unit}")
    return new_unit


def add_goal_commands_to_parser(subparsers) -> None:
    """Add enhanced goal tracking commands to existing CLI parser."""
    goal_parser = subparsers.add_parser('goal', help='Manage cycling goals (enhanced)')
    goal_subparsers = goal_parser.add_subparsers(dest='goal_command', required=True)

    # Legacy set command
    set_parser = goal_subparsers.add_parser('set', help='Set annual distance goal (legacy)')
    set_parser.add_argument('distance', help='Goal distance')

    # Enhanced add command
    add_parser = goal_subparsers.add_parser('add', help='Add a new goal (any type)')
    add_parser.add_argument('--type', required=True,
                           choices=['distance', 'ride_count', 'elevation', 'time', 'frequency'],
                           help='Type of goal')
    add_parser.add_argument('--target', required=True, help='Target value')
    add_parser.add_argument('--unit', default='', help='Unit (km/miles/m/ft/h)')
    add_parser.add_argument('--title', default='', help='Goal title')
    add_parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    add_parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')

    # Progress command
    progress_parser = goal_subparsers.add_parser('progress', help='Show goal progress')
    progress_parser.add_argument('--id', help='Goal ID to show')
    progress_parser.add_argument('--all', action='store_true', help='Show all active goals')

    # List
    goal_subparsers.add_parser('list', help='List all goals')

    # Delete
    delete_parser = goal_subparsers.add_parser('delete', help='Delete a goal')
    delete_parser.add_argument('--id', required=True, help='Goal ID')

    # Edit
    edit_parser = goal_subparsers.add_parser('edit', help='Edit a goal')
    edit_parser.add_argument('--id', required=True, help='Goal ID')
    edit_parser.add_argument('--title', help='New title')
    edit_parser.add_argument('--target', help='New target')
    edit_parser.add_argument('--unit', help='New unit')
    edit_parser.add_argument('--start', help='New start date')
    edit_parser.add_argument('--end', help='New end date')


def handle_goal_commands(args, trips: List[dict], unit: str) -> None:
    """Handle enhanced goal-related commands in main CLI."""
    settings = GoalSettings()

    if args.goal_command == 'set':
        distance = Decimal(args.distance)
        settings.set_goal(datetime.now().year, distance, unit)
        print(f"✅ Legacy goal set: {distance} {unit}")

    elif args.goal_command == 'add':
        try:
            target = Decimal(args.target)
            start_date = date.fromisoformat(args.start)
            end_date = date.fromisoformat(args.end)
            title = args.title or f"{args.type.replace('_', ' ').title()} Goal"
            goal_unit = args.unit or (unit if args.type == 'distance' else '')

            goal = settings.add_goal(
                title=title,
                type=GoalType(args.type),
                target=target,
                unit=goal_unit,
                start_date=start_date,
                end_date=end_date
            )
            print(f"✅ Goal created: {goal.goal_id} - {goal.title}")
            print(f" Type: {goal.type.value} | Target: {goal.target} {goal.unit}")
            print(f" Period: {goal.start_date} to {goal.end_date}")
        except Exception as e:
            print(f"❌ Error creating goal: {e}")

    elif args.goal_command == 'progress':
        if args.all:
            active_goals = settings.get_active_goals()
            if not active_goals:
                print("No active goals found.")
            else:
                for i, goal in enumerate(active_goals):
                    if i > 0:
                        print("\n" + "="*50 + "\n")
                    progress = calculate_goal_progress_v2(goal, trips, unit)
                    display_unit = get_goal_display_unit(goal, unit)
                    print(f"Goal: {goal.title} ({goal.goal_id})")
                    print(format_goal_display(progress, display_unit))

        elif args.id:
            all_goals = settings.list_goals()
            goal = next((g for g in all_goals if g.goal_id == args.id), None)
            if goal:
                progress = calculate_goal_progress_v2(goal, trips, unit)
                display_unit = get_goal_display_unit(goal, unit)
                print(f"Goal: {goal.title} ({goal.goal_id})")
                print(format_goal_display(progress, display_unit))
            else:
                print(f"Goal {args.id} not found.")
        else:
            # Legacy summary
            current_goal = settings.get_current_goal()
            if current_goal:
                goal_distance, goal_unit = current_goal
                if goal_unit != unit:
                    if goal_unit == 'km' and unit == 'miles':
                        goal_distance *= Decimal('0.621371192237334')
                    elif goal_unit == 'miles' and unit == 'km':
                        goal_distance *= Decimal('1.609344')
                progress = calculate_goal_progress(goal_distance, trips, unit)
                print(format_goal_display(progress, unit))
            else:
                print("No legacy goal set for current year")

    elif args.goal_command == 'list':
        v2_goals = settings.list_goals()
        legacy_goals = settings._settings.get('goals', {})

        if not v2_goals and not legacy_goals:
            print("No goals configured.")
            return

        print("\n=== CONFIGURED GOALS ===")

        if v2_goals:
            print("\nEnhanced Goals:")
            today = date.today()
            for goal in v2_goals:
                if goal.start_date <= today <= goal.end_date:
                    status = "🟢 ACTIVE"
                elif today < goal.start_date:
                    status = "🟡 FUTURE"
                else:
                    status = "🔴 PAST"
                print(f" {goal.goal_id}: {goal.title}")
                print(f"  Type: {goal.type.value} | Target: {goal.target} {goal.unit} | {status}")

        if legacy_goals:
            print("\nLegacy Distance Goals:")
            for year, goal_data in sorted(legacy_goals.items()):
                marker = " (current)" if int(year) == datetime.now().year else ""
                print(f" {year}: {goal_data['distance']} {goal_data['unit']}{marker}")

    elif args.goal_command == 'delete':
        if settings.delete_goal(args.id):
            print(f"✅ Goal {args.id} deleted.")
        else:
            print(f"❌ Goal {args.id} not found.")

    elif args.goal_command == 'edit':
        updates = {}
        if args.title:
            updates['title'] = args.title
        if args.target:
            updates['target'] = Decimal(args.target)
        if args.unit:
            updates['unit'] = args.unit
        if args.start:
            updates['start_date'] = date.fromisoformat(args.start)
        if args.end:
            updates['end_date'] = date.fromisoformat(args.end)

        if updates and settings.edit_goal(args.id, **updates):
            print(f"✅ Goal {args.id} updated.")
        else:
            print(f"❌ Failed to update goal {args.id}.")


def display_goal_summary(trips: List[dict], unit: str) -> None:
    """Display enhanced goal summary in main CLI output."""
    try:
        settings = GoalSettings()

        # Legacy goal
        current_goal = settings.get_current_goal()
        if current_goal:
            goal_distance, goal_unit = current_goal
            if goal_unit != unit:
                if goal_unit == 'km' and unit == 'miles':
                    goal_distance *= Decimal('0.621371192237334')
                elif goal_unit == 'miles' and unit == 'km':
                    goal_distance *= Decimal('1.609344')
            progress = calculate_goal_progress(goal_distance, trips, unit)

            print(f"\n=== ANNUAL GOAL SUMMARY (Legacy) ===")
            print(f"Target: {progress.goal_distance:,.0f} {unit}")
            print(f"Current: {progress.current_distance:,.1f} {unit} ({progress.percent_goal_completed:.1f}%)")

            status_text = {
                "ahead": f"🚀 Ahead by {abs(progress.pace_difference):.1f}%",
                "behind": f"⚠️ Behind by {abs(progress.pace_difference):.1f}%",
                "on_track": "✅ On track"
            }
            print(f"Status: {status_text[progress.status]}")
            print(f"Daily target: {progress.daily_target:.1f} {unit}")

        # Active enhanced goals (with error handling)
        try:
            active_goals = settings.get_active_goals()
            if active_goals:
                print(f"\n=== ACTIVE ENHANCED GOALS ({len(active_goals)}) ===")
                for goal in active_goals[:3]:
                    try:
                        progress = calculate_goal_progress_v2(goal, trips, unit)
                        display_unit = get_goal_display_unit(goal, unit)
                        pct = progress.percent_goal_completed
                        if progress.status == "on_track":
                            status_icon = "🟢"
                        elif progress.status == "ahead":
                            status_icon = "🚀"
                        else:
                            status_icon = "⚠️"
                        print(f"{status_icon} {goal.title}: {progress.current_distance:,.0f}/{progress.goal_distance:,.0f} {display_unit} ({pct:.1f}%)")
                    except Exception as e:
                        print(f"⚠️ {goal.title}: Error calculating progress - {str(e)}")

                if len(active_goals) > 3:
                    print(f" ... and {len(active_goals) - 3} more (use 'goal progress --all' to see all)")
        except AttributeError:
            # Fallback if get_active_goals method is not available
            print("\n=== ENHANCED GOALS ===")
            print("Enhanced goal tracking available - use 'python cli.py goal list' to see goals")

    except Exception as e:
        print(f"\n=== GOAL SUMMARY ===")
        print(f"Goal tracking unavailable: {str(e)}")


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    # Get the unit from args or saved preference
    if args.unit:
        unit = args.unit
        save_preferred_unit(unit)
    else:
        unit = get_preferred_unit()

    # Handle unit command
    if args.command == 'unit':
        unit = handle_unit_command(args)
        display_status(unit)
        return

    # Handle status command
    if args.command == 'status':
        display_status(unit)
        return

    # Get credentials and create client
    email, password = get_credentials()
    client = RWGPSClient(API_KEY, email, password)

    # Handle cache
    cache_file = CACHE_FILE
    if args.refresh and os.path.exists(cache_file):
        os.remove(cache_file)
        print("Cache cleared. Fetching fresh data...")

    trips = update_cache(CACHE_FILE, client)
    distances = process_trips(trips, unit)
    yearly_eddington = calculate_yearly_eddington(trips, unit)
    stats = calculate_statistics(distances, unit)
    metrics = analyze_ride_metrics(trips, unit)

    # Handle goal command
    if args.command == 'goal':
        handle_goal_commands(args, trips, unit)
        return

    # Display header
    print(f"\n=== CYCLING STATISTICS (distances in {unit}) ===")
    print(f"Current unit: {unit} (use --unit option to change)")

    if args.command == 'summary':
        print(f"Total rides analyzed: {len(distances)}")
        display_goal_summary(trips, unit)
        display_eddington(trips, distances, unit)
        display_ytd(trips, yearly_eddington, unit)
        display_yearly(yearly_eddington)
        display_metrics(stats, unit)
        display_distribution(distances, unit)
        display_milestones(metrics, unit)
        display_longest(trips, distances, unit)
        display_monthly(metrics, unit)
    elif args.command == 'eddington':
        display_eddington(trips, distances, unit)
    elif args.command == 'ytd':
        display_ytd(trips, yearly_eddington, unit)
    elif args.command == 'yearly':
        display_yearly(yearly_eddington)
    elif args.command == 'metrics':
        display_metrics(stats, unit)
    elif args.command == 'distribution':
        display_distribution(distances, unit)
    elif args.command == 'distance':
        display_milestones(metrics, unit)
    elif args.command == 'longest':
        display_longest(trips, distances, unit)
    elif args.command == 'monthly':
        display_monthly(metrics, unit)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
