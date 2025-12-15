
# Cycling Stats CLI

This CLI application helps cyclists analyze their Ride With GPS (RWGPS) data to gain insights into their cycling performance, progress, and goals.

## Features

- Analyze total rides, distances, and Eddington numbers.
- Display yearly, monthly, and ride distribution statistics.
- Track cycling goals: distance, ride count, elevation, time, and frequency.
- Manage goals via CLI commands (add, edit, list, delete, progress).
- Supports miles and kilometers with easy toggling; goal progress auto-converts targets/results to the selected display unit (distance and elevation).
- Caches data for efficient processing (single shared cache file, legacy per-unit caches auto-migrate).
- Secure and reusable user authentication.

## Installation

1. Clone the repository.
2. Set up a Python 3.12+ virtual environment.
3. Install required packages:
```bash
pip install -r requirements.txt
```
4. Obtain your RWGPS API key from https://ridewithgps.com/account/privacy and set it in your environment:
```bash
export RWGPS_API_KEY=<your_api_key>
```

## Usage

Run the CLI with Python:

```bash
python cli.py <command> [options]
```

## Commands

### Global options

- `--unit <miles|km>` : Set distance unit.
- `--refresh` : Force data refresh instead of using cache.

### Main commands

- `summary` : Show full cycling statistics summary.

### Individual Stats Commands

- `eddington` : Show overall Eddington number progress.
- `ytd` : Show year-to-date statistics.
- `yearly` : Show yearly Eddington numbers.
- `metrics` : Show ride metrics (longest, average, total).
- `distribution` : Show ride distance distribution.
- `distance` : Show distance milestone achievements.
- `longest` : Show top 5 longest rides.
- `monthly` : Show monthly ride stats.

### Unit and Status

- `unit [<miles|km|toggle>]` : Set or toggle unit of measurement.
- `status` : Show current unit and cache status.

### Goal Management

Use the `goal` subcommands for advanced cycling goal tracking.

```bash
python cli.py goal <subcommand> [options]
```

#### Goal Subcommands

- `add` : Add a new goal.
- `list` : List all configured goals.
- `delete` : Delete a goal by ID.
- `edit` : Edit an existing goal.
- `progress` : Show progress on goals.
- `set` : Set legacy annual distance goal.

#### Adding a Goal

Example:

```bash
python cli.py goal add --type distance --target 5000 --unit miles --start 2025-01-01 --end 2025-12-31 --title "Annual Distance Goal"
```

- `--type` : Type of goal (`distance`, `ride_count`, `elevation`, `time`, `frequency`).
- `--target` : Numeric target to achieve.
- `--unit` : Unit for the goal (e.g. `miles`, `km`, `m`, `ft`, `h`).
- `--start` : Start date for goal (YYYY-MM-DD).
- `--end` : End date for goal (YYYY-MM-DD).
- `--title` : Optional goal title.

#### Viewing Goal Progress

Show progress on all goals:

```bash
python cli.py goal progress --all
```

Show progress on a specific goal by ID:

```bash
python cli.py goal progress --id <goal_id>
```

#### Editing a Goal

Modify goal attributes:

```bash
python cli.py goal edit --id <goal_id> [--title <new_title>] [--target <new_target>] [--unit <new_unit>] [--start <YYYY-MM-DD>] [--end <YYYY-MM-DD>]
```

#### Deleting a Goal

Remove a goal:

```bash
python cli.py goal delete --id <goal_id>
```

## Configuration

- Place your RWGPS API key in environment variable `RWGPS_API_KEY`.
- Default unit is `miles`; can be changed in `.unit_preference` file or via `unit` CLI command.
- Cache uses a single shared file `trips_cache.pkl`; legacy per-unit caches are migrated automatically.

## Authentication

- Credentials (email and password) are securely handled.
- Credentials can be saved in `credentials.json` for convenience.
- Authentication tokens are cached to reduce login calls.

## Dependencies

- Python 3.12+
- requests
- tqdm
- urllib3
- dotenv (for env var loading)

## Example Usage

```bash
python cli.py summary
python cli.py ytd --unit km
python cli.py goal add --type distance --target 2000 --unit km --start 2025-01-01 --end 2025-12-31
python cli.py goal progress --all

## Tests

Pure logic tests (no network/API calls):

```bash
python -m unittest discover -s tests -p "test_*.py"
```
```

## Contribution

Feel free to fork, modify, and open pull requests.
For bugs or feature requests, please open issues.

---

Enjoy your cycling analytics and ride safely!
