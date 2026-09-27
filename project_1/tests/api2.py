"""Poll the course API every 30 seconds and print a compact summary."""

import time
from urllib.error import HTTPError, URLError

from api import GROUP_NUMBER, log, print_stats
from api_common import fetch_batch


POLL_INTERVAL_SECONDS = 30


def main():
    while True:
        try:
            print_stats(fetch_batch())
        except HTTPError as error:
            log(f"API returned HTTP {error.code}: {error.reason}")
            if error.code == 400:
                log("The API rejected further collection; stopping.")
                break
        except URLError as error:
            log(f"Could not reach the API: {error.reason}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
