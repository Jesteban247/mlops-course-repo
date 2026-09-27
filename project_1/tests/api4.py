"""Collect unique rows for up to one five-minute batch window."""

import time
from urllib.error import HTTPError, URLError

from api import GROUP_NUMBER, log
from api_common import fetch_batch, unique_rows


POLL_INTERVAL_SECONDS = 5
WINDOW_SECONDS = 5 * 60
UNIQUE_ROW_TARGET = 58_000


def main():
    started_at = time.monotonic()
    seen_rows = set()
    successful_requests = 0
    last_batch = "unknown"
    log(
        f"Collecting group {GROUP_NUMBER} every {POLL_INTERVAL_SECONDS}s; "
        f"target {UNIQUE_ROW_TARGET:,} unique rows, limit {WINDOW_SECONDS // 60} min."
    )

    while time.monotonic() - started_at < WINDOW_SECONDS:
        try:
            result = fetch_batch()
        except HTTPError as error:
            log(f"API error {error.code}: {error.reason}")
            if error.code == 400:
                break
        except URLError as error:
            log(f"Could not reach API: {error.reason}")
        else:
            successful_requests += 1
            last_batch = result.get("batch_number", "unknown")
            rows = result.get("data", [])
            new_rows, duplicate_count = unique_rows(rows, seen_rows)
            added = len(new_rows)
            elapsed = int(time.monotonic() - started_at)
            log(
                f"t={elapsed:>3}s | batch {last_batch} | "
                f"received {len(rows)} | new {added} | duplicates {duplicate_count} | "
                f"unique {len(seen_rows):,}/{UNIQUE_ROW_TARGET:,}"
            )
            if len(seen_rows) >= UNIQUE_ROW_TARGET:
                log("Unique row target reached.")
                break

        remaining = WINDOW_SECONDS - (time.monotonic() - started_at)
        if remaining > 0:
            time.sleep(min(POLL_INTERVAL_SECONDS, remaining))

    elapsed = min(time.monotonic() - started_at, WINDOW_SECONDS)
    log(
        f"Finished after {elapsed:.0f}s | batch {last_batch} | "
        f"successful requests {successful_requests} | unique rows {len(seen_rows):,}"
    )


if __name__ == "__main__":
    main()
