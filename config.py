import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
API_KEY = os.environ.get('RWGPS_API_KEY')

# Unit Configuration
DEFAULT_UNIT = os.environ.get('RWGPS_DEFAULT_UNIT', 'miles')  # 'miles' or 'km'

# Cache Configuration
CACHE_FILE = 'trips_cache.pkl'
CACHE_DURATION = 31 * 24 * 60 * 60  # 31 days in seconds
TOKEN_FILE = os.path.expanduser('~/.rwgps/token')
TOKEN_DURATION = 24 * 60 * 60  # 24 hours in seconds
