# utils.py

import pickle
import logging
import os
from typing import Any, Optional


def cache_data(data: Any, filename: str, unit: str = 'miles') -> None:
    """Cache data to a file with unit-specific naming."""
    unit_filename = f"{filename.split('.')[0]}_{unit}.pkl"
    try:
        with open(unit_filename, 'wb') as f:
            pickle.dump(data, f)
        logging.info(f"Data cached to {unit_filename}")
    except Exception as e:
        logging.error(f"Failed to cache data: {str(e)}")


def load_cached_data(filename: str, unit: str = 'miles') -> Optional[Any]:
    """Load cached data from a unit-specific file."""
    unit_filename = f"{filename.split('.')[0]}_{unit}.pkl"
    try:
        with open(unit_filename, 'rb') as f:
            data = pickle.load(f)
            logging.info(f"Loaded cached data from {unit_filename}")
            return data
    except FileNotFoundError:
        logging.info(f"No cache file found: {unit_filename}")
        return None
    except Exception as e:
        logging.error(f"Failed to load cached data: {str(e)}")
        return None


def save_token(token: str) -> None:
    """Save authentication token to file."""
    if not token:
        return

    token_file = os.path.expanduser('~/.rwgps/token')
    os.makedirs(os.path.dirname(token_file), exist_ok=True)

    try:
        with open(token_file, 'w') as f:
            f.write(token)
        logging.info("Authentication token saved")
    except Exception as e:
        logging.error(f"Failed to save token: {str(e)}")


def load_token() -> Optional[str]:
    """Load authentication token from file."""
    token_file = os.path.expanduser('~/.rwgps/token')
    try:
        with open(token_file, 'r') as f:
            token = f.read().strip()
            if token:
                logging.info("Loaded existing authentication token")
                return token
    except FileNotFoundError:
        logging.info("No authentication token found")
    except Exception as e:
        logging.error(f"Failed to load token: {str(e)}")

    return None


def save_preferred_unit(unit: str) -> None:
    """Save the user's preferred unit to file."""
    try:
        # Ensure we only save valid units
        if unit not in ['miles', 'km']:
            raise ValueError(f"Invalid unit: {unit}")

        with open('.unit_preference', 'w') as f:
            f.write(unit)
        logging.info(f"Unit preference saved: {unit}")
    except Exception as e:
        logging.error(f"Failed to save unit preference: {str(e)}")


def get_preferred_unit() -> str:
    """Load the user's preferred unit from file."""
    from config import DEFAULT_UNIT

    try:
        with open('.unit_preference', 'r') as f:
            unit = f.read().strip()
            if unit in ['miles', 'km']:
                return unit
            else:
                # If we find an invalid unit, log it and return the default
                logging.warning(f"Invalid unit found in preference file: {unit}")
    except FileNotFoundError:
        # Create the file with the default unit if it doesn't exist
        save_preferred_unit(DEFAULT_UNIT)
    except Exception as e:
        logging.error(f"Failed to load unit preference: {str(e)}")

    return DEFAULT_UNIT


def check_cache_status(cache_file: str, unit: str = 'miles') -> bool:
    """Check if cache exists for the specified unit."""
    unit_filename = f"{cache_file.split('.')[0]}_{unit}.pkl"
    return os.path.exists(unit_filename)


def get_cache_info(cache_file: str, unit: str = 'miles') -> dict:
    """Get information about the cache file."""
    unit_filename = f"{cache_file.split('.')[0]}_{unit}.pkl"

    info = {
        'exists': os.path.exists(unit_filename),
        'filename': unit_filename,
        'size': 0,
        'last_modified': None
    }

    if info['exists']:
        try:
            info['size'] = os.path.getsize(unit_filename)
            info['last_modified'] = os.path.getmtime(unit_filename)
        except Exception as e:
            logging.error(f"Failed to get cache file info: {str(e)}")

    return info
