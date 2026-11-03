import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import gevent
from locust import HttpUser, between, events, task

PAYLOAD = json.loads((Path(__file__).resolve().parent / 'example-request.json').read_text())
instances = Counter()
versions = Counter()
measuring = True


@events.test_start.add_listener
def reset_distribution(environment, **kwargs):
    global measuring
    instances.clear()
    versions.clear()
    measuring = not bool(os.getenv('LOCUST_RESULT_PREFIX'))


class PredictionUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def predict(self):
        headers = {'Connection': 'close'} if os.getenv('LOCUST_CLOSE_CONNECTIONS', '').lower() == 'true' else {}
        with self.client.post('/predict', json=PAYLOAD, name='POST /predict',
                              headers=headers, timeout=30, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f'HTTP {response.status_code}' if response.status_code else str(response.error))
                return
            try:
                body = response.json()
                if not body.get('model_version') or not body.get('instance') or not body.get('predictions'):
                    raise ValueError('Missing model version, instance or prediction')
                if measuring:
                    instances[body['instance']] += 1
                    versions[body['model_version']] += 1
            except (ValueError, TypeError):
                response.failure('Invalid prediction response')


@events.test_stop.add_listener
def save_distribution(environment, **kwargs):
    if os.getenv('LOCUST_RESULT_PREFIX'):
        return
    result_dir = Path(__file__).resolve().parent / 'results'
    result_dir.mkdir(exist_ok=True)
    filename = datetime.now(timezone.utc).strftime('instances-%Y%m%dT%H%M%SZ.json')
    (result_dir / filename).write_text(json.dumps({'instances': dict(instances), 'model_versions': dict(versions)}, indent=2))


@events.init.add_listener
def timed_experiment(environment, **kwargs):
    prefix = os.getenv('LOCUST_RESULT_PREFIX')
    if not prefix:
        return

    def measure(user_count):
        global measuring
        warmup = float(os.environ['LOCUST_WARMUP'])
        duration = float(os.environ['LOCUST_DURATION'])
        print(f'Warm-up: {warmup:g}s; measurement: {duration:g}s', flush=True)
        gevent.sleep(warmup)
        environment.stats.reset_all()
        instances.clear()
        versions.clear()
        measuring = True
        started = time.monotonic()
        gevent.sleep(duration)
        elapsed = time.monotonic() - started
        measuring = False
        stats = environment.stats.total
        result = {
            'users': user_count,
            'spawn_rate': float(os.environ['LOCUST_SPAWN_RATE']),
            'replica_scenario': os.environ['LOCUST_REPLICAS'],
            'connection_mode': 'fresh' if os.getenv('LOCUST_CLOSE_CONNECTIONS') == 'true' else 'keep-alive',
            'warmup_seconds': warmup,
            'measurement_seconds': round(elapsed, 2),
            'requests': stats.num_requests,
            'successful_requests': stats.num_requests - stats.num_failures,
            'failed_requests': stats.num_failures,
            'failure_percent': round(stats.fail_ratio * 100, 2),
            'requests_per_second': round(stats.num_requests / elapsed, 2),
            'average_latency_ms': round(stats.avg_response_time, 2),
            'p50_latency_ms': stats.get_response_time_percentile(0.50),
            'p95_latency_ms': stats.get_response_time_percentile(0.95),
            'p99_latency_ms': stats.get_response_time_percentile(0.99),
            'pod_responses': dict(instances),
            'model_versions': dict(versions),
        }
        Path(prefix + '_summary.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2), flush=True)
        environment.runner.quit()

    environment.events.spawning_complete.add_listener(lambda user_count, **kwargs: gevent.spawn(measure, user_count))
