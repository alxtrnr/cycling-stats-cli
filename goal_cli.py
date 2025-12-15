"""
Command-line interface for enhanced cycling goal tracking.
Supports distance, ride count, elevation, time, and frequency goals.
"""

import argparse
import logging
import sys
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional

from auth import get_credentials
from client import RWGPSClient
from config import API_KEY, CACHE_FILE
from goal_tracker import (
    GoalSettings, GoalType, calculate_goal_progress_v2,
    format_goal_display, calculate_goal_progress, get_goal_display_unit
)
from main import update_cache
from utils import get_preferred_unit, save_preferred_unit


def create_goal_parser() -> argparse.ArgumentParser:
    """Create argument parser for enhanced goal tracking commands."""
    parser = argparse.ArgumentParser(
        description='Enhanced Cycling Goal Tracker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Distance goal
  python goal_cli.py add --type distance --target 5000 --unit km --start 2025-01-01 --end 2025-12-31 --title "Annual Distance Goal"
  
  # Ride count goal  
  python goal_cli.py add --type ride_count --target 100 --start 2025-01-01 --end 2025-12-31 --title "Century of Rides"
  
  # Elevation goal
  python goal_cli.py add --type elevation --target 50000 --unit m --start 2025-01-01 --end 2025-12-31 --title "Elevation Challenge"
  
  # Time goal (hours)
  python goal_cli.py add --type time --target 200 --unit h --start 2025-01-01 --end 2025-12-31 --title "200 Hour Goal"
  
  # Frequency goal (rides per period)
  python goal_cli.py add --type frequency --target 52 --start 2025-01-01 --end 2025-12-31 --title "Weekly Ride Goal"
        """
    )

    parser.add_argument(
        '--unit',
        choices=['miles', 'km'],
        help='Distance unit preference (miles or km)'
    )

    parser.add_argument(
        '--refresh',
        action='store_true',
        help='Force refresh data instead of using cache'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Add goal command - Enhanced
    add_parser = subparsers.add_parser('add', help='Add a new goal of any type')
    add_parser.add_argument('--type', required=True,
                           choices=['distance', 'ride_count', 'elevation', 'time', 'frequency'],
                           help='Type of goal to create')
    add_parser.add_argument('--target', required=True, type=str,
                           help='Target value for the goal')
    add_parser.add_argument('--unit', default='',
                           help="Unit: distance(km/miles), elevation(m/ft), time(h), count/frequency('')")
    add_parser.add_argument('--title', default='', help='Optional descriptive title')
    add_parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    add_parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')

    # Progress command - Enhanced
    progress_parser = subparsers.add_parser('progress', help='Show goal progress')
    progress_parser.add_argument('--id', help='Specific goal ID to show')
    progress_parser.add_argument('--all', action='store_true', help='Show all active goals')

    # List command - Enhanced
    subparsers.add_parser('list', help='List all configured goals')

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a goal')
    delete_parser.add_argument('--id', required=True, help='Goal ID to delete')

    # Edit command
    edit_parser = subparsers.add_parser('edit', help='Edit an existing goal')
    edit_parser.add_argument('--id', required=True, help='Goal ID to edit')
    edit_parser.add_argument('--title', help='New title')
    edit_parser.add_argument('--target', help='New target value')
    edit_parser.add_argument('--unit', help='New unit')
    edit_parser.add_argument('--start', help='New start date (YYYY-MM-DD)')
    edit_parser.add_argument('--end', help='New end date (YYYY-MM-DD)')

    # Legacy commands for backward compatibility
    set_parser = subparsers.add_parser('set', help='Set annual distance goal (legacy)')
    set_parser.add_argument('distance', type=str, help='Goal distance')
    set_parser.add_argument('--year', type=int, default=datetime.now().year,
                           help='Year for goal (default: current year)')

    subparsers.add_parser('status', help='Show quick status summary')

    return parser


def validate_goal_input(goal_type: str, target: str, unit: str) -> tuple[Decimal, str]:
    """Validate and process goal input based on type."""
    try:
        target_val = Decimal(target)
        if target_val <= 0:
            raise ValueError("Target must be positive")
    except InvalidOperation as e:
        raise ValueError(f"Invalid target format: {target}") from e

    # Set default units and validate
    if goal_type == 'distance':
        if not unit:
            unit = get_preferred_unit()
        if unit not in ['km', 'miles']:
            raise ValueError("Distance goals require unit: km or miles")
        if target_val > 100000:
            raise ValueError("Distance target seems unreasonably large")

    elif goal_type == 'elevation':
        if not unit:
            unit = 'm'
        if unit not in ['m', 'ft']:
            raise ValueError("Elevation goals require unit: m or ft")
        if target_val > 500000:
            raise ValueError("Elevation target seems unreasonably large")

    elif goal_type == 'time':
        unit = 'h'  # Always hours
        if target_val > 10000:
            raise ValueError("Time target seems unreasonably large")

    elif goal_type in ['ride_count', 'frequency']:
        unit = 'rides'
        if target_val > 1000:
            raise ValueError("Ride count target seems unreasonably large")

    return target_val, unit


def handle_add_goal(args, display_unit: str) -> None:
    """Handle adding a new goal."""
    try:
        # Validate dates
        start_date = date.fromisoformat(args.start)
        end_date = date.fromisoformat(args.end)

        if start_date >= end_date:
            raise ValueError("Start date must be before end date")

        # Validate goal input
        target, unit = validate_goal_input(args.type, args.target, args.unit)

        # Create goal
        settings = GoalSettings()
        goal = settings.add_goal(
            title=args.title or f"{args.type.replace('_', ' ').title()} Goal",
            type=GoalType(args.type),
            target=target,
            unit=unit,
            start_date=start_date,
            end_date=end_date
        )

        print(f"✅ Goal created: {goal.goal_id}")
        print(f"   Title: {goal.title}")
        print(f"   Type: {goal.type.value}")
        print(f"   Target: {goal.target:,.0f} {goal.unit}")
        print(f"   Period: {goal.start_date} to {goal.end_date}")

        # Show immediate progress if goal is currently active
        if start_date <= date.today() <= end_date:
            print("\nFetching current progress...")
            try:
                email, password = get_credentials()
                client = RWGPSClient(API_KEY, email, password)
                trips = update_cache(CACHE_FILE, client)
                progress = calculate_goal_progress_v2(goal, trips, display_unit)
                display_goal_unit = get_goal_display_unit(goal, display_unit)
                print(format_goal_display(progress, display_goal_unit))
            except Exception as e:
                print(f"Could not fetch progress: {e}")

    except (ValueError, InvalidOperation) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def handle_show_progress(args, unit: str, refresh: bool = False) -> None:
    """Handle showing goal progress."""
    try:
        # Get ride data
        email, password = get_credentials()
        client = RWGPSClient(API_KEY, email, password)

        if refresh:
            print("Refreshing ride data...")
        trips = update_cache(CACHE_FILE, client)

        # Get goals to show
        settings = GoalSettings()
        goals = []

        if args.all:
            goals = settings.get_active_goals()
        elif args.id:
            all_goals = settings.list_goals()
            goal = next((g for g in all_goals if g.goal_id == args.id), None)
            if goal:
                goals = [goal]
            else:
                print(f"Goal with ID {args.id} not found")
                return
        else:
            # Default: show active goals
            goals = settings.get_active_goals()

        if not goals:
            print("No matching goals found.")
            return

        # Show progress for each goal
        for i, goal in enumerate(goals):
            if i > 0:
                print("\n" + "="*50 + "\n")

            progress = calculate_goal_progress_v2(goal, trips, unit)
            print(f"Goal: {goal.title} ({goal.goal_id})")
            display_goal_unit = get_goal_display_unit(goal, unit)
            print(format_goal_display(progress, display_goal_unit))

    except Exception as e:
        print(f"❌ Error fetching progress: {e}")
        logging.exception("Error in handle_show_progress")
        sys.exit(1)


def handle_list_goals() -> None:
    """Handle listing all configured goals."""
    settings = GoalSettings()

    # Get both v2 goals and legacy goals
    v2_goals = settings.list_goals()
    legacy_goals = settings._settings.get('goals', {})

    if not v2_goals and not legacy_goals:
        print("No goals configured.")
        return

    print("\n=== CONFIGURED GOALS ===")

    # Show v2 goals
    if v2_goals:
        print("\nEnhanced Goals:")
        for goal in sorted(v2_goals, key=lambda g: g.start_date):
            today = date.today()
            if goal.start_date <= today <= goal.end_date:
                status = "🟢 ACTIVE"
            elif today < goal.start_date:
                status = "🟡 FUTURE"
            else:
                status = "🔴 PAST"

            print(f"  {goal.goal_id}: {goal.title}")
            print(f"    Type: {goal.type.value} | Target: {goal.target:,.0f} {goal.unit}")
            print(f"    Period: {goal.start_date} to {goal.end_date} | Status: {status}")
            print()

    # Show legacy goals
    if legacy_goals:
        print("Legacy Distance Goals:")
        for year, goal_data in sorted(legacy_goals.items()):
            distance = goal_data['distance']
            unit = goal_data['unit']
            marker = " (current year)" if int(year) == datetime.now().year else ""
            print(f"  {year}: {distance} {unit}{marker}")


def handle_delete_goal(args) -> None:
    """Handle deleting a goal."""
    settings = GoalSettings()

    # Check if goal exists first
    all_goals = settings.list_goals()
    goal = next((g for g in all_goals if g.goal_id == args.id), None)

    if not goal:
        print(f"❌ Goal {args.id} not found.")
        return

    # Confirm deletion
    print(f"About to delete goal: {goal.title} ({goal.type.value})")
    confirm = input("Are you sure? (y/N): ").lower()

    if confirm == 'y':
        if settings.delete_goal(args.id):
            print(f"✅ Goal {args.id} deleted successfully.")
        else:
            print(f"❌ Failed to delete goal {args.id}.")
    else:
        print("Delete cancelled.")


def handle_edit_goal(args) -> None:
    """Handle editing a goal."""
    settings = GoalSettings()

    # Check if goal exists
    all_goals = settings.list_goals()
    goal = next((g for g in all_goals if g.goal_id == args.id), None)

    if not goal:
        print(f"❌ Goal {args.id} not found.")
        return

    print(f"Editing goal: {goal.title} ({goal.type.value})")

    updates = {}
    try:
        if args.title:
            updates['title'] = args.title
        if args.target:
            target_val = Decimal(args.target)
            if target_val <= 0:
                raise ValueError("Target must be positive")
            updates['target'] = target_val
        if args.unit:
            updates['unit'] = args.unit
        if args.start:
            updates['start_date'] = date.fromisoformat(args.start)
        if args.end:
            updates['end_date'] = date.fromisoformat(args.end)

        if not updates:
            print("No updates specified.")
            return

        if settings.edit_goal(args.id, **updates):
            print(f"✅ Goal {args.id} updated successfully.")

            # Show updated goal
            updated_goals = settings.list_goals()
            updated_goal = next((g for g in updated_goals if g.goal_id == args.id), None)
            if updated_goal:
                print(f"   Title: {updated_goal.title}")
                print(f"   Target: {updated_goal.target:,.0f} {updated_goal.unit}")
                print(f"   Period: {updated_goal.start_date} to {updated_goal.end_date}")
        else:
            print(f"❌ Failed to update goal {args.id}.")

    except (ValueError, InvalidOperation) as e:
        print(f"❌ Error: {e}")


# Legacy command handlers for backward compatibility
def handle_set_goal_legacy(args, unit: str) -> None:
    """Handle legacy set goal command."""
    try:
        distance = Decimal(args.distance)
        if distance <= 0:
            raise ValueError("Distance must be positive")
        if distance > 100000:
            raise ValueError("Distance seems unreasonably large")

        settings = GoalSettings()
        settings.set_goal(args.year, distance, unit)
        print(f"✅ Legacy goal set: {distance:,.0f} {unit} for {args.year}")

        # Show immediate progress if setting for current year
        if args.year == datetime.now().year:
            print("\nFetching current progress...")
            handle_show_progress_legacy(unit, refresh=False)

    except (ValueError, InvalidOperation) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def handle_show_progress_legacy(unit: str, refresh: bool = False) -> None:
    """Handle legacy progress display."""
    settings = GoalSettings()
    current_goal = settings.get_current_goal()

    if not current_goal:
        print(f"❌ No legacy goal set for {datetime.now().year}")
        return

    goal_distance, goal_unit = current_goal

    # Convert goal to current unit if different
    if goal_unit != unit:
        if goal_unit == 'km' and unit == 'miles':
            goal_distance = goal_distance * Decimal('0.621371192237334')
        elif goal_unit == 'miles' and unit == 'km':
            goal_distance = goal_distance * Decimal('1.609344')

    try:
        email, password = get_credentials()
        client = RWGPSClient(API_KEY, email, password)

        if refresh:
            print("Refreshing ride data...")
        trips = update_cache(CACHE_FILE, client)

        progress = calculate_goal_progress(goal_distance, trips, unit)
        print(format_goal_display(progress, unit))

    except Exception as e:
        print(f"❌ Error fetching ride data: {e}")
        logging.exception("Error in handle_show_progress_legacy")
        sys.exit(1)


def handle_status(unit: str) -> None:
    """Handle quick status display."""
    settings = GoalSettings()

    # Check legacy goal
    current_goal = settings.get_current_goal()

    # Check v2 goals
    active_goals = settings.get_active_goals()

    print(f"\n=== QUICK STATUS ===")
    print(f"Current unit preference: {unit}")

    if current_goal:
        goal_distance, goal_unit = current_goal
        print(f"Legacy goal: {goal_distance} {goal_unit} for {datetime.now().year}")

    if active_goals:
        print(f"Active enhanced goals: {len(active_goals)}")
        for goal in active_goals[:3]:  # Show first 3
            print(f"  - {goal.title} ({goal.type.value}): {goal.target} {goal.unit}")
        if len(active_goals) > 3:
            print(f"  ... and {len(active_goals) - 3} more")

    if not current_goal and not active_goals:
        print("No goals configured.")

    print("Use 'progress' command for detailed analysis")


def main() -> None:
    """Main entry point for enhanced goal CLI."""
    parser = create_goal_parser()
    args = parser.parse_args()

    # Get unit preference
    if args.unit:
        unit = args.unit
        save_preferred_unit(unit)
    else:
        unit = get_preferred_unit()

    # Route to appropriate handler
    try:
        if args.command == 'add':
            handle_add_goal(args, unit)
        elif args.command == 'progress':
            handle_show_progress(args, unit, args.refresh)
        elif args.command == 'list':
            handle_list_goals()
        elif args.command == 'delete':
            handle_delete_goal(args)
        elif args.command == 'edit':
            handle_edit_goal(args)
        elif args.command == 'set':  # Legacy
            handle_set_goal_legacy(args, unit)
        elif args.command == 'status':
            handle_status(unit)
        else:
            parser.print_help()

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
