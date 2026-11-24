"""Run a timed, headless Locust experiment and save its results."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('must be positive')
    return number


def main():
    parser = argparse.ArgumentParser(description='Run a timed property API experiment')
    parser.add_argument('--users', type=positive, required=True)
    parser.add_argument('--replicas', choices=['1', '2', '3', 'auto'], required=True,
                        help='scenario label; set the HPA separately')
    parser.add_argument('--spawn-rate', type=positive, default=1)
    parser.add_argument('--warmup', type=positive, default=15)
    parser.add_argument('--duration', type=positive, default=120)
    parser.add_argument('--host', default='http://127.0.0.1:18001')
    args = parser.parse_args()
    try:
        with urlopen(args.host.rstrip('/') + '/ready', timeout=10) as response:
            ready = json.load(response)
        print(f"API ready: model version {ready.get('version')}", flush=True)
    except Exception as exc:
        sys.exit(f'API is not ready: {exc}')

    results = ROOT / 'results'
    results.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    prefix = results / f'{args.replicas}pods_{args.users}users_{stamp}'
    env = os.environ.copy()
    env.update(LOCUST_RESULT_PREFIX=str(prefix), LOCUST_WARMUP=str(args.warmup),
               LOCUST_DURATION=str(args.duration), LOCUST_SCENARIO=args.replicas,
               LOCUST_SPAWN_RATE=str(args.spawn_rate))
    print(f'Scenario {args.replicas}: set and verify the HPA separately.', flush=True)
    print(f'Results: {prefix}_summary.json and CSV files', flush=True)
    command = [sys.executable, '-m', 'locust', '-f', str(ROOT / 'locustfile.py'),
               '--headless', '--host', args.host, '--users', str(args.users),
               '--spawn-rate', str(args.spawn_rate), '--csv', str(prefix),
               '--csv-full-history', '--only-summary']
    result = subprocess.run(command, cwd=ROOT, env=env)
    summary = Path(str(prefix) + '_summary.json')
    if result.returncode == 0 and not summary.exists():
        sys.exit('Experiment ended without a summary.')
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
