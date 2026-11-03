# Locust — scaled API

## 1. Check Prometheus

On NBAM07, keep this terminal open:

```bash
kubectl port-forward -n mlops-project svc/prometheus --address 0.0.0.0 9090:9090
```

Open Prometheus and enter this expression, then click **Execute**:

```promql
up{job="diabetes-api-scaled"}
```

Each discovered API pod should show `1`, meaning Prometheus can collect its metrics. Grafana is already configured to use Prometheus.

To see prediction requests per second for each API pod while Locust runs, use:

```promql
sum by (pod) (rate(diabetes_predictions_total{job="diabetes-api-scaled"}[2m]))
```

Open Prometheus through your usual browser connection to NBAM07 on port 9090. You can also watch the Diabetes API dashboard in Grafana.

## 2. Connect from your Mac

Download the `locust` folder. On NBAM07, find the scaled API Service IP:

```bash
kubectl get svc diabetes-api-scaled -n mlops-project -o jsonpath='{.spec.clusterIP}{"\n"}'
```

On your Mac, replace the IP below if it changed, and keep this terminal open:

```bash
ssh -L 18001:10.44.242.43:8000 estudiante@10.43.97.96
```

In another Mac terminal, check the connection:

```bash
curl http://127.0.0.1:18001/ready
```

## 3. Run Locust on your Mac

Open a terminal in the downloaded `locust` folder. Install once:

```bash
conda create -n project2-locust python=3.11 pip -y
conda activate project2-locust
python -m pip install -r requirements.txt
```

Start Locust with a fresh connection for each request:

```bash
conda activate project2-locust
LOCUST_CLOSE_CONNECTIONS=true locust -f locustfile.py --host http://127.0.0.1:18001
```

Open **http://localhost:8089**, enter 5 users and a spawn rate of 1, then click **Start swarming**. Check Locust and Grafana or Prometheus; click **Stop** when finished. Five users are simulated clients, not five requests per second. Fresh connections help demonstrate distribution but add connection overhead.

## 4. Compare one pod, five pods and autoscaling

On NBAM07, select a scenario and wait for the desired number of ready pods:

```bash
kubectl patch hpa diabetes-api-scaled -n mlops-project --type merge -p '{"spec":{"minReplicas":1,"maxReplicas":1}}'
kubectl get pods -n mlops-project -l app=diabetes-api-scaled -w
```

For five pods:

```bash
kubectl patch hpa diabetes-api-scaled -n mlops-project --type merge -p '{"spec":{"minReplicas":5,"maxReplicas":5}}'
kubectl get pods -n mlops-project -l app=diabetes-api-scaled -w
```

Restore autoscaling after fixed-pod tests:

```bash
kubectl patch hpa diabetes-api-scaled -n mlops-project --type merge -p '{"spec":{"minReplicas":1,"maxReplicas":5}}'
kubectl get hpa diabetes-api-scaled -n mlops-project -w
```

For a timed experiment, run on your Mac using the matching scenario label (`1`, `5` or `auto`):

```bash
python run.py --replicas 1 --users 5 --spawn-rate 1 --fresh-connections
```

Change `--users` to test other loads. The label does not change the HPA; set that separately. Results are saved in `locust/results/`. Each successful prediction also creates an application database audit record.
