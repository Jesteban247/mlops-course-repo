"""Collect unique rows for group 4 across the ten API batches."""

import time
from datetime import datetime, timedelta, timezone

from airflow.sdk import DAG, task

from common.api_client import HTTPError, URLError, fetch_group_sample
from common.infobip import send_sms
from common.postgres import DATA_COLUMNS, count_batch_rows, insert_sample
from common.settings import (
    BATCH_NUMBERS,
    GROUP_NUMBER,
    POLL_INTERVAL_SECONDS,
    ROTATION_SECONDS,
    UNIQUE_ROWS_PER_BATCH,
)


with DAG(
    dag_id="extract_cover_data",
    description="Collect 58,000 unique rows for group 4 in each of ten batches.",
    start_date=datetime(2026, 9, 22, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["api", "database", "extraction"],
):

    @task(execution_timeout=timedelta(hours=1), retries=0)
    def collect_group_4_batches():
        completed_batches = 0
        current_batch = None
        current_count = 0
        batch_started_at = None

        while True:
            try:
                result = fetch_group_sample(GROUP_NUMBER)
            except HTTPError as error:
                if error.code == 400:
                    raise RuntimeError(
                        f"API rejected group {GROUP_NUMBER} with HTTP 400 after "
                        f"batch {current_batch}; reset group 4 and resume extraction."
                    ) from error
                print(f"Group {GROUP_NUMBER}: API HTTP {error.code}; retrying.")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue
            except URLError as error:
                print(f"Group {GROUP_NUMBER}: API unavailable ({error.reason}); retrying.")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            batch_number = result.get("batch_number")
            rows = result.get("data", [])
            if batch_number not in BATCH_NUMBERS:
                raise RuntimeError(
                    f"Unexpected batch number {batch_number}; expected batches 1-10. "
                    "Run api_reset_group_4 before extraction."
                )

            if current_batch is None or batch_number != current_batch:
                if current_batch is not None:
                    expected_batch = current_batch + 1
                    if batch_number != expected_batch:
                        raise RuntimeError(
                            f"Expected batch {expected_batch}, received {batch_number}. "
                            "Run api_reset_group_4 before starting a fresh extraction."
                        )
                    if current_count < UNIQUE_ROWS_PER_BATCH:
                        print(
                            f"Batch {current_batch} changed at "
                            f"{current_count:,}/{UNIQUE_ROWS_PER_BATCH:,} unique rows."
                        )
                current_batch = batch_number
                completed_batches += 1
                current_count = count_batch_rows(GROUP_NUMBER, current_batch)
                batch_started_at = time.monotonic()
                print(
                    f"Starting batch {current_batch} "
                    f"({completed_batches}/{len(BATCH_NUMBERS)}). "
                    f"Existing unique rows: {current_count:,}."
                )

            valid_rows = [row for row in rows if len(row) == len(DATA_COLUMNS)]
            skipped = len(rows) - len(valid_rows)
            current_count = insert_sample(
                GROUP_NUMBER,
                batch_number,
                valid_rows,
                max_new_rows=UNIQUE_ROWS_PER_BATCH - current_count,
            )
            print(
                f"Group {GROUP_NUMBER} | batch {batch_number} | received {len(rows)} | "
                f"malformed {skipped} | unique stored {current_count:,}/"
                f"{UNIQUE_ROWS_PER_BATCH:,}"
            )
            if current_count >= UNIQUE_ROWS_PER_BATCH:
                print(
                    f"Done: batch {current_batch} reached "
                    f"{current_count:,}/{UNIQUE_ROWS_PER_BATCH:,} unique rows."
                )
                if current_batch == BATCH_NUMBERS[-1]:
                    break
                wait_remaining = max(
                    0,
                    ROTATION_SECONDS - (time.monotonic() - batch_started_at),
                )
                print(
                    f"Waiting for batch {current_batch + 1}; "
                    f"next API request in about {wait_remaining:.0f}s."
                )
                while wait_remaining > 0:
                    wait_chunk = min(30, wait_remaining)
                    time.sleep(wait_chunk)
                    wait_remaining -= wait_chunk
                    if wait_remaining > 0:
                        print(
                            f"Waiting for batch {current_batch + 1}; "
                            f"next API request in about {wait_remaining:.0f}s."
                        )
            else:
                time.sleep(POLL_INTERVAL_SECONDS)

        total_rows = sum(count_batch_rows(GROUP_NUMBER, batch) for batch in BATCH_NUMBERS)
        print(
            f"Group {GROUP_NUMBER}: all {len(BATCH_NUMBERS)} batches complete; "
            f"{total_rows:,} unique rows stored."
        )
        return total_rows

    collected_count = collect_group_4_batches()

    @task
    def send_completion_notification(total_rows):
        message = (
            "Project 1 extraction completed: group 4 reached its target "
            "for all 10 batches. "
            f"Unique rows stored: {total_rows:,}."
        )
        send_sms(message)

    send_completion_notification(collected_count)
