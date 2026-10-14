import json
import logging
import os
import time
from collections import Counter
from pathlib import Path

import gevent
import psutil
from dotenv import load_dotenv
from locust import HttpUser, between, events, task

from client import PAYLOAD, validate_prediction

load_dotenv(Path(__file__).parent / ".env")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))
WAIT_MIN = float(os.getenv("WAIT_MIN_SECONDS", "0.5"))
WAIT_MAX = float(os.getenv("WAIT_MAX_SECONDS", "1.5"))
WARMUP = float(os.getenv("WARMUP_SECONDS", "15"))
DURATION = float(os.getenv("MEASURE_SECONDS", "120"))
FAILURE_LIMIT = float(os.getenv("MAX_FAILURE_RATIO", "0.01"))
P95_LIMIT = float(os.getenv("MAX_P95_MS", "500"))
logger = logging.getLogger(__name__)
instances = Counter()
models = Counter()
measuring = False


class InferenceUser(HttpUser):
    wait_time = between(WAIT_MIN, WAIT_MAX)
    host = os.getenv("TARGET_HOST")

    @task
    def predict(self):
        with self.client.post("/predict", json=PAYLOAD, timeout=TIMEOUT, catch_response=True, name="POST /predict") as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}" if response.status_code else str(response.error))
                return
            try:
                data = response.json()
                validate_prediction(data)
            except (ValueError, TypeError, KeyError) as exc:
                response.failure(f"Invalid response: {exc}")
                return
            if measuring:
                instances[data["instance_id"]] += 1
                models[data["model_uri"]] += 1


@events.init.add_listener
def initialize(environment, **kwargs):
    state = {"started": False, "finished": False}

    def measure_window():
        global measuring
        logger.info("All users spawned; warming up for %.1f seconds", WARMUP)
        gevent.sleep(WARMUP)
        environment.stats.reset_all()
        instances.clear()
        models.clear()
        measuring = True
        start = time.monotonic()
        process = psutil.Process()
        process.cpu_percent()
        psutil.cpu_percent(percpu=True)
        host_cpu, core_cpu, process_cpu, rss = [], [], [], []
        history = []
        logger.info("Stable measurement started: %.1f seconds", DURATION)
        while time.monotonic() - start < DURATION:
            gevent.sleep(min(1, max(0, DURATION - (time.monotonic() - start))))
            cores = psutil.cpu_percent(percpu=True)
            host_cpu.append(sum(cores) / len(cores))
            core_cpu.append(max(cores))
            process_cpu.append(process.cpu_percent())
            rss.append(process.memory_info().rss)
            total = environment.stats.total
            history.append({
                "elapsed_seconds": round(time.monotonic() - start, 3),
                "users": environment.runner.user_count,
                "requests": total.num_requests,
                "failures": total.num_failures,
                "p95_ms": total.get_response_time_percentile(0.95),
                "generator_cpu_percent": host_cpu[-1],
                "generator_busiest_core_percent": core_cpu[-1],
            })
        measuring = False
        elapsed = time.monotonic() - start
        total = environment.stats.total
        p95 = total.get_response_time_percentile(0.95)
        expected_replicas = int(os.environ["TEST_REPLICAS"])
        topology_verified = len(instances) == expected_replicas
        passed = (total.num_requests > 0 and total.fail_ratio < FAILURE_LIMIT and p95 < P95_LIMIT and len(models) == 1 and topology_verified)
        summary = {
            "host": environment.host,
            "replicas": expected_replicas,
            "observed_replicas": len(instances),
            "topology_verified": topology_verified,
            "users": environment.parsed_options.num_users,
            "spawn_rate": environment.parsed_options.spawn_rate,
            "warmup_seconds": WARMUP,
            "measurement_seconds": round(elapsed, 3),
            "wait_min_seconds": WAIT_MIN,
            "wait_max_seconds": WAIT_MAX,
            "timeout_seconds": TIMEOUT,
            "requests": total.num_requests,
            "failures": total.num_failures,
            "failure_percent": total.fail_ratio * 100,
            "rps": total.num_requests / elapsed,
            "successful_rps": (total.num_requests - total.num_failures) / elapsed,
            "p95_ms": p95,
            "failure_limit_percent": FAILURE_LIMIT * 100,
            "p95_limit_ms": P95_LIMIT,
            "criterion_passed": passed,
            "model_responses": dict(models),
            "instance_responses": dict(instances),
            "generator_cpu_average_percent": sum(host_cpu) / len(host_cpu),
            "generator_cpu_peak_percent": max(host_cpu),
            "generator_busiest_core_peak_percent": max(core_cpu),
            "generator_process_cpu_peak_percent": max(process_cpu),
            "generator_process_rss_peak_bytes": max(rss),
            "generator_cpu_warning": max(core_cpu) >= 90,
        }
        prefix = Path(os.environ["RESULT_PREFIX"])
        prefix.with_name(prefix.name + "_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        prefix.with_name(prefix.name + "_window.json").write_text(json.dumps(history, indent=2) + "\n")
        state["finished"] = True
        environment.process_exit_code = 0 if passed else 1
        logger.info("Stable result: %s", json.dumps(summary))
        environment.runner.quit()

    def all_spawned(user_count, **kwargs):
        if not state["started"]:
            state["started"] = True
            gevent.spawn(measure_window)

    def stopped(**kwargs):
        if not state["finished"]:
            environment.process_exit_code = 2
            logger.error("Measurement incomplete; no capacity result was recorded")

    environment.events.spawning_complete.add_listener(all_spawned)
    environment.events.test_stop.add_listener(stopped)
