# calculations.py

import logging
from typing import List, Dict, Tuple
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, getcontext

getcontext().prec = 28  # Adjust precision as needed

# Conversion constants
METERS_TO_MILES = Decimal("0.000621371192237334")
METERS_TO_KM = Decimal("0.001")


def calculate_eddington(distances: List[Decimal], unit: str = 'miles') -> int:
    """
    Calculate the Eddington number from a list of ride distances.
    The Eddington number E is the number where you have done E rides of at least E units.

    Args:
        distances: List of ride distances in the specified unit
        unit: The unit of measurement ('miles' or 'km')
    """
    if not distances:
        return 0

    max_possible_e = int(max(distances)) + 1
    rides_above_threshold = [0] * (max_possible_e + 1)

    for distance in distances:
        for e in range(1, int(distance) + 1):
            rides_above_threshold[e] += 1

    E = 0
    for i in range(1, max_possible_e + 1):
        if rides_above_threshold[i] >= i:
            E = i

    return E


def calculate_statistics(distances: List[Decimal], unit: str = 'miles') -> Dict[str, Decimal]:
    """Calculate various statistics from ride distances."""
    if not distances:
        return {
            'longest_ride': Decimal('0'),
            'average_ride': Decimal('0'),
            'total_distance': Decimal('0')
        }

    # Keep full precision throughout calculations
    total_distance = sum(distances)
    return {
        'longest_ride': max(distances),
        'average_ride': total_distance / Decimal(len(distances)),
        'total_distance': total_distance  # No rounding here
    }


def calculate_yearly_eddington(trips: List[Dict], unit: str = 'miles') -> Dict[int, int]:
    """
    Calculate Eddington numbers per year.
    Returns a dictionary with years as keys and Eddington numbers as values.
    """
    yearly_distances = defaultdict(list)
    current_year = datetime.now().year

    # Select the appropriate conversion factor
    conversion_factor = METERS_TO_MILES if unit == 'miles' else METERS_TO_KM

    for trip in trips:
        if 'distance' in trip:
            date_str = trip.get('departed_at')
            if date_str:
                try:
                    date_str = date_str.split('+')[0].rstrip('Z')
                    trip_date = datetime.fromisoformat(date_str)
                    if trip_date.year <= current_year:
                        distance = Decimal(str(trip['distance'])) * conversion_factor
                        yearly_distances[trip_date.year].append(distance)
                except ValueError:
                    continue

    return {year: calculate_eddington(yearly_distances[year], unit)
            for year in yearly_distances.keys()}


def calculate_overall_e_progress(distances: List[Decimal], unit: str = 'miles') -> Tuple[int, int, int, int, int]:
    """
    Calculate current E and progress towards next E numbers.
    Returns (current_e, rides_at_next, rides_needed_next, rides_at_nextnext, rides_needed_nextnext)
    """
    current_e = calculate_eddington(distances, unit)
    next_e = current_e + 1
    nextnext_e = next_e + 1

    rides_at_next = sum(1 for d in distances if d >= next_e)
    rides_needed_next = next_e - rides_at_next
    rides_at_nextnext = sum(1 for d in distances if d >= nextnext_e)
    rides_needed_nextnext = nextnext_e - rides_at_nextnext

    return current_e, rides_at_next, rides_needed_next, rides_at_nextnext, rides_needed_nextnext


def get_highest_yearly_eddington(yearly_eddington: Dict[int, int]) -> Tuple[int, int]:
    """
    Return the year and value of highest Eddington number.
    Returns tuple of (year, eddington_number)
    """
    if not yearly_eddington:
        return (0, 0)
    return max(yearly_eddington.items(), key=lambda x: x[1])


def analyze_ride_distribution(distances: List[Decimal], unit: str = 'miles') -> Dict[int, int]:
    """
    Analyze distribution of rides by distance thresholds.
    Returns dictionary with distance thresholds as keys and number of rides above that threshold as values.
    """
    thresholds = {}
    for threshold in range(0, int(max(distances)) + 10, 10):
        rides_above = sum(1 for d in distances if d >= threshold)
        if rides_above > 0:
            thresholds[threshold] = rides_above
    return thresholds


def verify_eddington(distances: List[Decimal], e_number: int, unit: str = 'miles') -> str:
    """
    Verify Eddington number calculation with detailed breakdown.
    Returns a string with verification details.
    """
    rides_at_e = sum(1 for d in distances if d >= e_number)
    return f"\nEddington verification (E={e_number}):\n" \
           f"Number of rides >= {e_number} {unit}: {rides_at_e}"


def get_milestone_rides(distances: List[Decimal], unit: str = 'miles') -> Dict[str, any]:
    """
    Identify milestone rides (longest, shortest, etc.).
    Returns dictionary with milestone categories and corresponding distances.
    """
    if not distances:
        return {}

    sorted_distances = sorted(distances)

    # Define thresholds based on unit
    if unit == 'miles':
        # Keep existing century-based thresholds for miles
        century = 100
        double_century = 200
        triple_century = 300
        quad_century = 400

        centuries = sum(1 for d in distances if d >= century)
        double_centuries = sum(1 for d in distances if d >= double_century)
        triple_centuries = sum(1 for d in distances if d >= triple_century)
        quad_centuries = sum(1 for d in distances if d >= quad_century)

        milestones = {
            'total_rides': len(distances),
            'longest': sorted_distances[-1],
            'shortest': sorted_distances[0],
            'median': sorted_distances[len(sorted_distances) // 2],
            'centuries': centuries,
            'double_centuries': double_centuries,
            'triple_centuries': triple_centuries,
            'quad_centuries': quad_centuries,
            'longest_rides': sorted(distances, reverse=True)[:5]
        }
    else: # kilometers - use new distance ranges
        # Define new thresholds
        range_50 = 50
        range_100 = 100
        range_150 = 150
        range_200 = 200
        range_300 = 300
        range_400 = 400
        range_600 = 600
        range_1000 = 1000

        # Count rides within specific ranges
        range_50_to_99 = sum(1 for d in distances if range_50 <= d < range_100)
        range_100_to_149 = sum(1 for d in distances if range_100 <= d < range_150)
        range_150_to_199 = sum(1 for d in distances if range_150 <= d < range_200)
        range_200_to_299 = sum(1 for d in distances if range_200 <= d < range_300)
        range_300_to_399 = sum(1 for d in distances if range_300 <= d < range_400)
        range_400_to_599 = sum(1 for d in distances if range_400 <= d < range_600)
        range_600_to_999 = sum(1 for d in distances if range_600 <= d < range_1000)
        range_1000_plus = sum(1 for d in distances if d >= range_1000)

        milestones = {
            'total_rides': len(distances),
            'longest': sorted_distances[-1],
            'shortest': sorted_distances[0],
            'median': sorted_distances[len(sorted_distances) // 2],
            'range_50_to_99': range_50_to_99,
            'range_100_to_149': range_100_to_149,
            'range_150_to_199': range_150_to_199,
            'range_200_to_299': range_200_to_299,
            'range_300_to_399': range_300_to_399,
            'range_400_to_599': range_400_to_599,
            'range_600_to_999': range_600_to_999,
            'range_1000_plus': range_1000_plus,
            'longest_rides': sorted(distances, reverse=True)[:5]
        }

    return milestones


def get_ride_titles(trips: List[Dict], distances: List[Decimal], unit: str = 'miles') -> List[Tuple[Decimal, str]]:
    """Get distances paired with their ride titles, sorted by distance."""
    distance_title_pairs = []

    # Select the appropriate conversion factor
    conversion_factor = METERS_TO_MILES if unit == 'miles' else METERS_TO_KM

    for trip in trips:
        if 'distance' in trip and 'name' in trip and trip['name']:
            try:
                distance = Decimal(str(trip['distance'])) * conversion_factor
                distance_title_pairs.append((distance, trip['name']))
            except (ValueError, TypeError) as e:
                logging.error(f"Error processing ride {trip.get('id', 'unknown')}: {e}")

    return sorted(distance_title_pairs, key=lambda x: x[0], reverse=True)[:5]


def analyze_ride_metrics(trips: List[Dict], unit: str = 'miles') -> Dict:
    """Calculate advanced riding metrics."""
    monthly_totals = defaultdict(Decimal)
    monthly_counts = defaultdict(int)
    processed_ids = set()

    # Select the appropriate conversion factor
    conversion_factor = METERS_TO_MILES if unit == 'miles' else METERS_TO_KM

    for trip in trips:
        if 'distance' in trip and trip['id'] not in processed_ids:
            processed_ids.add(trip['id'])
            date_str = trip.get('departed_at')
            if not date_str:
                continue

            date_str = date_str.split('+')[0].rstrip('Z')
            try:
                date = datetime.fromisoformat(date_str)
                distance = Decimal(str(trip['distance'])) * conversion_factor
                month_key = f"{date.year}-{date.month:02d}"
                monthly_totals[month_key] += distance
                monthly_counts[month_key] += 1
                logging.debug(f"Ride {trip['id']}: {trip['distance']}m = {distance:.2f} {unit}")
                logging.debug(f"Month {month_key} total: {monthly_totals[month_key]:.2f} {unit}")
            except ValueError:
                continue

    # Convert trips to distances with the appropriate unit
    distances = []
    for trip in trips:
        if 'distance' in trip:
            date_str = trip.get('departed_at')
            if date_str:
                try:
                    date_str = date_str.split('+')[0].rstrip('Z')
                    datetime.fromisoformat(date_str)  # Just to validate the date
                    distance = Decimal(str(trip['distance'])) * conversion_factor
                    distances.append(distance)
                except ValueError:
                    continue

    current_e = calculate_eddington(distances, unit)

    return {
        'monthly_totals': dict(monthly_totals),
        'monthly_counts': dict(monthly_counts),
        'rides_needed_next_e': calculate_rides_needed_next(distances, unit),
        'milestone_rides': get_milestone_rides(distances, unit),
        'next_e_target': current_e + 1
    }


def calculate_rides_needed_next(distances: List[Decimal], unit: str = 'miles') -> int:
    """Calculate rides needed for next Eddington number."""
    current_e = calculate_eddington(distances, unit)
    target = current_e + 1
    current_qualifying = sum(1 for d in distances if d >= target)
    return target - current_qualifying


def calculate_next_yearly_e(trips: List[Dict], year: int, unit: str = 'miles') -> Tuple[int, int, int]:
    """
    Calculate the next E number goal for the specified year and rides needed.
    Returns (next_e, rides_at_target, rides_needed)
    """
    # Select the appropriate conversion factor
    conversion_factor = METERS_TO_MILES if unit == 'miles' else METERS_TO_KM

    yearly_distances = []
    for trip in trips:
        if 'distance' in trip:
            date_str = trip.get('departed_at')
            if date_str:
                try:
                    date_str = date_str.split('+')[0].rstrip('Z')
                    trip_date = datetime.fromisoformat(date_str)
                    if trip_date.year == year:
                        distance = Decimal(str(trip['distance'])) * conversion_factor
                        yearly_distances.append(distance)
                except ValueError:
                    continue

    current_e = calculate_eddington(yearly_distances, unit)
    next_e = current_e + 1
    rides_at_next_e = sum(1 for d in yearly_distances if d >= next_e)
    rides_needed = next_e - rides_at_next_e

    return next_e, rides_at_next_e, rides_needed

