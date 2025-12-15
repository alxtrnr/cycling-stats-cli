# client.py

from __future__ import annotations

import json
import logging
import sys
import time
import math
import getpass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

from config import API_KEY
from utils import load_token, save_token


class RWGPSClient:
    """Client for interacting with the Ride With GPS API."""
    PER_PAGE = 50

    def __init__(self, api_key: str, email: str = None, password: str = None):
        self.base_url = "https://ridewithgps.com/api/v1"
        self.api_key = api_key
        self._session = self._create_session()

        # Store email and password for potential re-authentication
        self.email = email
        self.password = password

        # Try to load existing token first
        self.auth_token = load_token()

        # If no existing token and credentials provided, get a new token
        if not self.auth_token and email and password:
            logging.info("No existing token found, authenticating with provided credentials")
            try:
                self.auth_token = self._get_auth_token()
                if self.auth_token:
                    save_token(self.auth_token)
                    logging.info("✅ Authentication successful, token saved")
                else:
                    raise Exception("Failed to obtain authentication token")
            except Exception as e:
                logging.error(f"Authentication failed: {str(e)}")
                raise Exception("Failed to obtain authentication token")
        elif not self.auth_token:
            raise Exception("No authentication token available and no credentials provided")

    def _log_available_fields(self, trips: List[dict], sample_size: int = 3) -> None:
        """Log available fields in trip data for debugging."""
        if not trips:
            return

        sample_trips = trips[:sample_size]
        all_fields = set()
        for trip in sample_trips:
            all_fields.update(trip.keys())

        logging.info(f"Available trip fields: {sorted(all_fields)}")

    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy."""
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        return session

    def _get_auth_token(self) -> Optional[str]:
        """Get authentication token from RWGPS API."""
        if not self.email or not self.password:
            logging.error("Email or password not provided")
            return None

        auth_url = f"{self.base_url}/auth_tokens.json"
        headers = {
            'x-rwgps-api-key': self.api_key,
            'Content-Type': 'application/json'
        }
        payload = {
            'user': {
                'email': self.email,
                'password': self.password
            }
        }

        try:
            logging.info(f"Attempting authentication for {self.email}")

            # Add a small delay
            time.sleep(1)

            response = self._session.post(
                auth_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            logging.info(f"Auth response status: {response.status_code}")

            if response.status_code == 401:
                logging.error("Authentication failed: Invalid email or password")
                return None

            response.raise_for_status()
            data = response.json()

            logging.info(f"Auth response structure: {list(data.keys())}")

            if 'auth_token' in data:
                if isinstance(data['auth_token'], dict) and 'auth_token' in data['auth_token']:
                    token = data['auth_token']['auth_token']
                    logging.info("✅ Authentication token obtained successfully")
                    return token
                elif isinstance(data['auth_token'], str):
                    # Sometimes the token might be returned directly as a string
                    token = data['auth_token']
                    logging.info("✅ Authentication token obtained successfully")
                    return token

            logging.error(f"Unexpected auth response format: {data}")
            return None

        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP Error during authentication: {e.response.status_code}")
            try:
                error_data = e.response.json()
                logging.error(f"Error details: {error_data}")
            except:
                pass
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error during authentication: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error during authentication: {e}")
            return None

    def get_latest_trip(self) -> Optional[dict]:
        """Fetch the most recent trip from RWGPS."""
        trips_url = f"{self.base_url}/trips.json"
        headers = {
            'x-rwgps-api-key': self.api_key,
            'x-rwgps-auth-token': self.auth_token
        }

        try:
            time.sleep(1)  # Rate limiting
            response = self._session.get(
                trips_url,
                headers=headers,
                params={
                    'page': 1,
                    'version': 2,
                    'per_page': 1,
                    'sub_format': 'detail'
                },
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            # Handle different possible response structures
            if 'trips' in data and data['trips']:
                return data['trips'][0]
            elif 'results' in data and data['results']:
                return data['results'][0]
            elif isinstance(data, list) and data:
                return data[0]
            else:
                logging.warning(f"No trips found or unexpected response structure: {list(data.keys())}")
                return None

        except Exception as e:
            logging.error(f"Failed to fetch latest trip: {str(e)}")
            raise

    def get_trips_page(self, page: int) -> List[dict]:
        """Fetch a single page of trips."""
        trips_url = f"{self.base_url}/trips.json"

        try:
            time.sleep(1)  # Rate limiting
            response = self._session.get(
                trips_url,
                headers={
                    'x-rwgps-api-key': self.api_key,
                    'x-rwgps-auth-token': self.auth_token
                },
                params={
                    'page': page,
                    'version': 2,
                    'per_page': self.PER_PAGE,
                    'sub_format': 'detail'
                },
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            # Handle different response structures
            if 'trips' in data:
                return data['trips']
            elif 'results' in data:
                return data['results']
            elif isinstance(data, list):
                return data
            else:
                logging.warning(f"Unexpected response structure on page {page}")
                return []

        except Exception as e:
            logging.error(f"Failed to fetch page {page}: {str(e)}")
            raise

    def get_missing_trips(self, cached_trips: List[dict], latest_trip: dict) -> List[dict]:
        """Fetch only the trips that aren't in the cache."""
        if not cached_trips:
            return self.get_all_trips()

        latest_cached_id = max(trip['id'] for trip in cached_trips)
        cached_ids = {trip['id'] for trip in cached_trips}
        missing_trips = []

        if latest_trip['id'] <= latest_cached_id:
            return missing_trips

        page = 1
        found_all_new = False

        with tqdm(desc="Fetching new rides") as pbar:
            while not found_all_new and page <= 10:
                try:
                    new_trips = self.get_trips_page(page)

                    if not new_trips:
                        break

                    filtered_trips = [trip for trip in new_trips if trip['id'] not in cached_ids]

                    if filtered_trips:
                        missing_trips.extend(filtered_trips)
                        pbar.update(len(filtered_trips))

                    if any(trip['id'] <= latest_cached_id for trip in new_trips):
                        found_all_new = True
                        break

                    page += 1

                except Exception as e:
                    logging.error(f"Error fetching page {page}: {e}")
                    break

        return missing_trips

    def get_all_trips(self) -> List[Dict[str, Any]]:
        """Fetch all trips from RWGPS."""
        trips_url = f"{self.base_url}/trips.json"
        all_trips = []

        try:
            # Get first page to determine pagination info
            response = self._session.get(
                trips_url,
                headers={
                    'x-rwgps-api-key': self.api_key,
                    'x-rwgps-auth-token': self.auth_token
                },
                params={
                    'page': 1,
                    'version': 2,
                    'per_page': self.PER_PAGE,
                    'sub_format': 'detail'
                },
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            # Handle different response structures
            trips_key = 'trips' if 'trips' in data else 'results'
            if trips_key not in data:
                logging.warning(f"No trips found. Response keys: {list(data.keys())}")
                return []

            # Add first page immediately to avoid refetching it
            first_page_trips = data.get(trips_key, []) or []
            all_trips.extend(first_page_trips)

            # Extract pagination info
            meta = data.get('meta', {})
            pagination = meta.get('pagination', {})
            total_rides = pagination.get('record_count', len(first_page_trips))

            # Prefer a calculation based on the requested per_page to avoid under-fetching
            total_pages_meta = pagination.get('page_count', 1) or 1
            total_pages = max(
                math.ceil(total_rides / self.PER_PAGE) if total_rides else 1,
                total_pages_meta
            )

            # Log available fields from first page
            if first_page_trips:
                self._log_available_fields(first_page_trips)

            logging.info(f"Fetching {total_rides} rides across {total_pages} pages")

            with tqdm(total=total_rides, desc="Retrieving rides", unit=" rides") as pbar:
                # We already grabbed the first page above
                pbar.update(len(first_page_trips))

                for page in range(2, min(total_pages + 1, 500)):  # reasonable upper bound
                    try:
                        trips = self.get_trips_page(page)
                        all_trips.extend(trips)
                        pbar.update(len(trips))

                        if not trips:  # No more trips available
                            logging.warning(f"No trips returned on page {page}; stopping early.")
                            break

                    except Exception as e:
                        logging.error(f"Error on page {page}: {str(e)}")
                        continue

            if total_rides and len(all_trips) < total_rides:
                logging.warning(
                    f"Expected {total_rides} rides but only retrieved {len(all_trips)}."
                )

            logging.info(f"Retrieved {len(all_trips)} rides")
            return all_trips

        except Exception as e:
            logging.error(f"Failed to fetch trips: {str(e)}")
            raise
