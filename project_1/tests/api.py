"""Fetch once and print a compact summary of the sample."""

import json
from datetime import datetime
from statistics import mean
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "http://10.43.97.110:8080/data"
GROUP_NUMBER = 4


def log(message):
    """Print a timestamped log line."""
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"[{timestamp}] {message}", flush=True)


def print_stats(result):
    rows = result.get("data", [])
    log(
        f"Group {result.get('group_number', GROUP_NUMBER)} | "
        f"Batch {result.get('batch_number', 'unknown')} | Cases: {len(rows)}"
    )
    if not rows:
        return

    elevations = [float(row[0]) for row in rows if len(row) > 0]
    slopes = [float(row[2]) for row in rows if len(row) > 2]
    if elevations:
        log(
            f"Elevation: avg {mean(elevations):.1f}, "
            f"range {min(elevations):.0f}-{max(elevations):.0f}"
        )
    if slopes:
        log(f"Slope: avg {mean(slopes):.1f} degrees")


def fetch_data(group_number=GROUP_NUMBER, timeout=15):
    """Fetch one sample for a group; the API assigns its current batch."""
    url = f"{API_URL}?{urlencode({'group_number': group_number})}"
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    try:
        result = fetch_data()
    except HTTPError as error:
        log(f"API returned HTTP {error.code}: {error.reason}")
        return
    except URLError as error:
        log(f"Could not reach the API: {error.reason}")
        return

    print_stats(result)


if __name__ == "__main__":
    main()
