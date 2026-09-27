"""HTTP helpers for the course data API."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE_URL = os.getenv("COURSE_API_BASE_URL", "http://10.43.97.110:8080").rstrip("/")
API_TIMEOUT_SECONDS = 20


def request_json(path="/", params=None, timeout=API_TIMEOUT_SECONDS):
    query = f"?{urlencode(params)}" if params else ""
    request = Request(
        f"{API_BASE_URL}{path}{query}",
        headers={"Accept": "application/json"},
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else None


def fetch_group_sample(group_number):
    return request_json("/data", {"group_number": group_number})


def reset_group(group_number):
    return request_json("/restart_data_generation", {"group_number": group_number})


def check_api():
    return request_json("/")


__all__ = ["API_BASE_URL", "HTTPError", "URLError", "check_api", "fetch_group_sample", "reset_group"]
