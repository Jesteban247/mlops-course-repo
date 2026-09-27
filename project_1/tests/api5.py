"""Collect a target of unique rows from consecutive server-assigned batches."""

import time
from urllib.error import HTTPError, URLError

import pandas as pd

from api import GROUP_NUMBER, log
from api_common import COLUMNS, fetch_batch, unique_rows


POLL_INTERVAL_SECONDS = 3
ROTATION_SECONDS = 5 * 60 + 5
WAIT_STATUS_INTERVAL_SECONDS = 30
UNIQUE_ROWS_PER_BATCH = 20_000
NUMBER_OF_BATCHES = 3


def main():
    seen_rows = set()
    dataframe_parts = []
    completed_batches = 0
    current_batch = None
    unique_in_batch = 0
    batch_started_at = None
    successful_requests = 0

    log(
        f"Group {GROUP_NUMBER} | target {UNIQUE_ROWS_PER_BATCH:,} unique rows per batch | "
        f"{NUMBER_OF_BATCHES} consecutive batches | poll every {POLL_INTERVAL_SECONDS}s."
    )

    try:
        while True:
            try:
                result = fetch_batch()
            except HTTPError as error:
                log(f"API error {error.code}: {error.reason}")
                if error.code == 400:
                    log("The API rejected further collection; stopping.")
                    break
                time.sleep(POLL_INTERVAL_SECONDS)
                continue
            except URLError as error:
                log(f"Could not reach API: {error.reason}; retrying.")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            successful_requests += 1
            batch_number = result.get("batch_number", "unknown")
            rows = result.get("data", [])

            if current_batch is None:
                current_batch = batch_number
                batch_started_at = time.monotonic()
                completed_batches = 1
                log(f"Starting batch {current_batch} ({completed_batches}/{NUMBER_OF_BATCHES}).")
            elif batch_number != current_batch:
                if unique_in_batch < UNIQUE_ROWS_PER_BATCH:
                    log(
                        f"Batch {current_batch} changed before reaching its target: "
                        f"{unique_in_batch:,}/{UNIQUE_ROWS_PER_BATCH:,} unique rows."
                    )
                current_batch = batch_number
                unique_in_batch = 0
                batch_started_at = time.monotonic()
                completed_batches += 1
                log(f"Detected batch {current_batch} ({completed_batches}/{NUMBER_OF_BATCHES}).")

            valid_rows = [row for row in rows if len(row) == len(COLUMNS)]
            if len(valid_rows) != len(rows):
                log(f"Batch {current_batch}: skipped {len(rows) - len(valid_rows)} malformed rows.")
            new_rows, duplicate_count = unique_rows(valid_rows, seen_rows)
            unique_in_batch += len(new_rows)
            if new_rows:
                dataframe_parts.append(pd.DataFrame(new_rows, columns=COLUMNS, dtype="string"))

            log(
                f"Batch {current_batch} | received {len(rows)} | new {len(new_rows)} | "
                f"duplicates {duplicate_count} | batch unique {unique_in_batch:,}/"
                f"{UNIQUE_ROWS_PER_BATCH:,}"
            )

            if (
                completed_batches >= NUMBER_OF_BATCHES
                and unique_in_batch >= UNIQUE_ROWS_PER_BATCH
            ):
                break

            if unique_in_batch >= UNIQUE_ROWS_PER_BATCH:
                elapsed = time.monotonic() - batch_started_at
                wait_remaining = max(0, ROTATION_SECONDS - elapsed)
                log(
                    f"Target reached for batch {current_batch} "
                    f"({unique_in_batch:,}/{UNIQUE_ROWS_PER_BATCH:,}). "
                    f"Waiting; next API request in about {wait_remaining:.0f}s."
                )
                while wait_remaining > 0:
                    wait_chunk = min(WAIT_STATUS_INTERVAL_SECONDS, wait_remaining)
                    time.sleep(wait_chunk)
                    wait_remaining -= wait_chunk
                    if wait_remaining > 0:
                        log(
                            f"Waiting for the next batch. "
                            f"Next API request in about {wait_remaining:.0f}s."
                        )
            else:
                time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        log("Interrupted by Ctrl+C.")

    all_samples = (
        pd.concat(dataframe_parts, ignore_index=True)
        if dataframe_parts
        else pd.DataFrame(columns=COLUMNS, dtype="string")
    )
    log(
        f"Finished | batches observed {completed_batches}/{NUMBER_OF_BATCHES} | "
        f"successful requests {successful_requests} | unique rows {len(all_samples):,}."
    )


if __name__ == "__main__":
    main()
