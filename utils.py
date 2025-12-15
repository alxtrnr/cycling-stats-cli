# utils.py

import pickle
import logging
import os
from typing import Any, Optional, List, Tuple


def _legacy_cache_files(filename: str) -> List[str]:
    """Return legacy unit-specific cache filenames for migration."""
    base = filename.split('.')[0]
    return [f"{base}_miles.pkl", f"{base}_km.pkl"]


def _load_cache_file(path: str) -> Optional[Any]:
    """Load a cache file safely, logging failures."""
    try:
        with open(path, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        logging.error(f"Failed to load cache file {path}: {e}")
        return None


def cache_data(data: Any, filename: str) -> None:
    """Cache data to a single shared file (unit-agnostic)."""
    try:
        with open(filename, 'wb') as f:
            pickle.dump(data, f)
        logging.info(f"Data cached to {filename}")
    except Exception as e:
        logging.error(f"Failed to cache data: {str(e)}")


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


def load_cached_data(filename: str) -> Optional[Any]:
    """
    Load cached data from the shared cache file.
    Falls back to legacy unit-specific caches and migrates them if present.
    """
    candidates: List[Tuple[int, float, str, Any]] = []  # (trip_count, timestamp, path, data)

    # Current shared cache
    data = _load_cache_file(filename)
    if data is not None:
        trip_count = len(data.get('trips', [])) if isinstance(data, dict) else 0
        timestamp = float(data.get('timestamp', 0)) if isinstance(data, dict) else 0.0
        candidates.append((trip_count, timestamp, filename, data))

    # Legacy caches (miles/km)
    for legacy_file in _legacy_cache_files(filename):
        legacy_data = _load_cache_file(legacy_file)
        if legacy_data is not None:
            trip_count = len(legacy_data.get('trips', [])) if isinstance(legacy_data, dict) else 0
            timestamp = float(legacy_data.get('timestamp', 0)) if isinstance(legacy_data, dict) else 0.0
            candidates.append((trip_count, timestamp, legacy_file, legacy_data))

    if not candidates:
        logging.info(f"No cache file found: {filename}")
        return None

    # Pick the cache with the most trips; tie-breaker is latest timestamp
    best_count, best_ts, best_path, best_data = max(candidates, key=lambda x: (x[0], x[1]))

    # If best is legacy or differs from current shared cache, migrate
    if best_path != filename:
        logging.info(
            f"Migrating cache from {best_path} to {filename} "
            f"(trips={best_count}, ts={best_ts})"
        )
        cache_data(best_data, filename)
    else:
        logging.info(f"Loaded cached data from {filename} (trips={best_count})")

    return best_data


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


def check_cache_status(cache_file: str) -> bool:
    """Check if the shared cache exists."""
    return os.path.exists(cache_file)


def get_cache_info(cache_file: str) -> dict:
    """Get information about the shared cache file."""
    info = {
        'exists': os.path.exists(cache_file),
        'filename': cache_file,
        'size': 0,
        'last_modified': None
    }

    if info['exists']:
        try:
            info['size'] = os.path.getsize(cache_file)
            info['last_modified'] = os.path.getmtime(cache_file)
        except Exception as e:
            logging.error(f"Failed to get cache file info: {str(e)}")

    return info
