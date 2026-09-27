"""Poll every 5 seconds and report progress toward unique sample rows."""

import time
from urllib.error import HTTPError, URLError

import pandas as pd

from api import GROUP_NUMBER, log
from api_common import COLUMNS, fetch_batch, unique_rows


POLL_INTERVAL_SECONDS = 5
def main():
    seen_rows = set()
    dataframe_parts = []
    request_count = 0
    log(f"Collecting group {GROUP_NUMBER}; polling every {POLL_INTERVAL_SECONDS} seconds.")
    log("Press Ctrl+C to stop and print the final total.")

    try:
        while True:
            try:
                result = fetch_batch()
            except HTTPError as error:
                log(f"API error {error.code}: {error.reason}; retrying in 5 seconds.")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue
            except URLError as error:
                log(f"Could not reach API: {error.reason}; retrying in 5 seconds.")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            request_count += 1
            rows = result.get("data", [])
            batch_number = result.get("batch_number", "unknown")
            if not rows:
                log(f"Batch {batch_number}: empty response; no samples added.")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            if any(len(row) != len(COLUMNS) for row in rows):
                log(f"Batch {batch_number}: invalid row shape; response skipped.")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            new_rows, duplicate_count = unique_rows(rows, seen_rows)

            if new_rows:
                dataframe_parts.append(
                    pd.DataFrame(new_rows, columns=COLUMNS, dtype="string")
                )

            if not new_rows:
                status = "REPEATED"
            elif duplicate_count:
                status = "PARTIAL"
            else:
                status = "UNIQUE"

            log(
                f"Batch {batch_number}: {status} | received {len(rows)} | "
                f"new {len(new_rows)} | duplicate {duplicate_count} | "
                f"total unique {len(seen_rows)}"
            )
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        pass

    all_samples = (
        pd.concat(dataframe_parts, ignore_index=True)
        if dataframe_parts
        else pd.DataFrame(columns=COLUMNS, dtype="string")
    )
    log(
        f"Stopped by Ctrl+C after {request_count} successful responses. "
        f"DataFrame has {len(all_samples)} unique samples."
    )


if __name__ == "__main__":
    main()
