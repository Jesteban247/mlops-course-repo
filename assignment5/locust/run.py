import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from client import PAYLOAD, validate_prediction

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Must be positive")
    return number


def smoke(host, timeout):
    health = requests.get(f"{host}/health", timeout=timeout)
    health.raise_for_status()
    if health.json().get("status") != "ok":
        raise ValueError("Health check did not return status=ok")
    prediction = requests.post(f"{host}/predict", json=PAYLOAD, timeout=timeout)
    prediction.raise_for_status()
    validate_prediction(prediction.json())
    print("PASS: health and prediction are valid")
    print(json.dumps(prediction.json(), indent=2))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("smoke")
    load = sub.add_parser("load")
    load.add_argument("--users", type=positive_int, required=True)
    load.add_argument("--replicas", type=int, choices=[1, 3], required=True)
    load.add_argument("--spawn-rate", type=positive_int, default=5)
    args = parser.parse_args()
    host = os.getenv("TARGET_HOST", "").rstrip("/")
    if not host.startswith(("http://", "https://")):
        parser.error("Set TARGET_HOST in .env to an http(s) URL")
    timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))
    smoke(host, timeout)
    if args.command == "smoke":
        return 0
    for key, default in (("WARMUP_SECONDS", "15"), ("MEASURE_SECONDS", "120")):
        if float(os.getenv(key, default)) <= 0:
            parser.error(f"{key} must be positive")
    wait_min = float(os.getenv("WAIT_MIN_SECONDS", "0.5"))
    wait_max = float(os.getenv("WAIT_MAX_SECONDS", "1.5"))
    if timeout <= 0 or wait_min < 0 or wait_max < wait_min:
        parser.error("Invalid timeout or wait interval")
    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    prefix = results / f"rep{args.replicas}_u{args.users}_{stamp}"
    env = os.environ.copy()
    env.update(TEST_REPLICAS=str(args.replicas), RESULT_PREFIX=str(prefix))
    command = [
        sys.executable, "-m", "locust", "-f", str(ROOT / "locustfile.py"),
        "--headless", "--host", host, "--users", str(args.users),
        "--spawn-rate", str(args.spawn_rate), "--csv", str(prefix),
        "--csv-full-history", "--only-summary", "--stop-timeout", "0",
    ]
    return subprocess.call(command, cwd=ROOT, env=env)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (requests.RequestException, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(2)
