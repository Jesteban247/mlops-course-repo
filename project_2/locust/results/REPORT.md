# Load test results

Model 14; fresh connections; 1 CPU limit per API pod. Fixed-pod tests ran for 60 seconds; autoscaling ran for 150 seconds. Locust ran on NBAM07.

| Scenario | Users | Successes | Failures | Successful req/s | Mean latency | p95 |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 5 | 404 | 0 (0.00%) | 6.73 | 0.45 s | 0.67 s |
| 1 | 10 | 419 | 0 (0.00%) | 6.98 | 1.14 s | 1.40 s |
| 1 | 20 | 409 | 0 (0.00%) | 6.82 | 2.61 s | 3.10 s |
| 1 | 40 | 409 | 0 (0.00%) | 6.82 | 5.49 s | 6.70 s |
| 1 | 60 | 392 | 25 (6.00%) | 6.53 | 8.69 s | 21.00 s |
| 1 | 80 | 362 | 30 (7.65%) | 6.03 | 11.37 s | 24.00 s |
| 5 | 20 | 1471 | 0 (0.00%) | 24.52 | 0.51 s | 1.00 s |
| 5 | 40 | 1581 | 0 (0.00%) | 26.35 | 1.22 s | 2.60 s |
| 5 | 80 | 1456 | 0 (0.00%) | 24.27 | 2.96 s | 8.20 s |
| 5 | 120 | 1473 | 0 (0.00%) | 24.55 | 4.64 s | 9.70 s |
| 5 | 170 | 1330 | 0 (0.00%) | 22.17 | 7.44 s | 14.00 s |
| auto | 80 | 3491 | 0 (0.00%) | 23.27 | 3.22 s | 8.60 s |

## Conclusions

- One pod handled about 6–7 successful requests per second. Latency increased as users increased; the first failures appeared at 60 users.
- Five pods handled about 22–26 successful requests per second. All five received traffic. No failures were recorded through 170 users, but p95 reached 14 seconds.
- With autoscaling and 80 users, the HPA scaled from one to five pods. Latency improved after scaling but remained several seconds.
- As an example target of p95 under 2 seconds and fewer than 1% failures, the highest tested passing levels were 10 users for one pod and 20 for five pods. The PDF does not set these thresholds.
- These are short, single-run results, not exact capacity limits. HTTP 0 failures had no recorded underlying cause; long in-flight requests at the end of a run might not be counted.
