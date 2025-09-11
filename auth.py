# auth.py

import getpass
import json
import sys
from pathlib import Path
from typing import Tuple


def get_credentials() -> Tuple[str, str]:
    """Get user credentials from file or prompt user."""
    credentials_file = Path("credentials.json")

    # First try to load saved credentials
    if credentials_file.exists():
        try:
            with credentials_file.open('r') as f:
                credentials = json.load(f)
                return credentials['email'], credentials['password']
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Invalid credentials file: {e}")
            credentials_file.unlink(missing_ok=True)

    # If no saved credentials, prompt user
    print("🔐 Authentication Required")
    print("Please enter your Ride with GPS credentials:")

    while True:
        email = input("Email: ").strip()
        password = getpass.getpass("Password: ")

        if not email or not password:
            print("❌ Email and password cannot be empty!")
            continue

        # Basic email validation
        if "@" not in email or "." not in email.split("@")[-1]:
            print("❌ Please enter a valid email address!")
            continue

        # Save credentials for future use
        save = input("Save credentials for future use? (y/N): ").lower()
        if save == 'y':
            try:
                with credentials_file.open('w') as f:
                    json.dump({'email': email, 'password': password}, f, indent=2)
                print("✅ Credentials saved.")
            except Exception as e:
                print(f"⚠️ Warning: Could not save credentials: {e}")

        return email, password


def clear_saved_credentials() -> None:
    """Clear saved credentials file."""
    credentials_file = Path("credentials.json")
    if credentials_file.exists():
        credentials_file.unlink()
        print("✅ Saved credentials cleared.")
    else:
        print("ℹ️ No saved credentials to clear.")
