import os
import pickle
import tempfile
import unittest
from decimal import Decimal

from utils import cache_data, load_cached_data, check_cache_status, get_cache_info


class UtilsCacheTests(unittest.TestCase):
    def test_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = os.path.join(tmp, "cache.pkl")
            payload = {"trips": [{"id": 1}], "timestamp": 123.0}

            cache_data(payload, cache_file)
            self.assertTrue(os.path.exists(cache_file))

            loaded = load_cached_data(cache_file)
            self.assertEqual(loaded, payload)
            self.assertTrue(check_cache_status(cache_file))
            info = get_cache_info(cache_file)
            self.assertTrue(info["exists"])
            self.assertGreater(info["size"], 0)

    def test_load_prefers_largest_legacy_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = os.path.join(tmp, "cache.pkl")
            base = cache_file.split(".")[0]
            miles_cache = f"{base}_miles.pkl"
            km_cache = f"{base}_km.pkl"

            legacy_small = {"trips": [{"id": 1}], "timestamp": 50.0}
            legacy_big = {"trips": [{"id": 1}, {"id": 2}], "timestamp": 10.0}

            with open(miles_cache, "wb") as f:
                pickle.dump(legacy_small, f)
            with open(km_cache, "wb") as f:
                pickle.dump(legacy_big, f)

            loaded = load_cached_data(cache_file)
            self.assertEqual(len(loaded["trips"]), 2)
            # Migrated to shared cache
            self.assertTrue(os.path.exists(cache_file))


if __name__ == "__main__":
    unittest.main()
