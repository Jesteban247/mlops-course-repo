# Project 3 — Locust

Download the entire `project_3/locust` folder to your computer. The API must have a champion model loaded before running the test.

## 1. API Service IP — NBAM07

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl get svc property-api -n project-3 -o jsonpath='{.spec.clusterIP}{"\n"}'
```

## 2. SSH tunnel — your computer

Replace `API_SERVICE_IP` with the IP from step 1. Leave this terminal open.

```bash
ssh -L 18001:API_SERVICE_IP:8000 estudiante@10.43.97.96
```

In another terminal on your computer:

```bash
curl -f http://127.0.0.1:18001/health
curl -f http://127.0.0.1:18001/ready
```

`/ready` must succeed before testing predictions.

## 3. Conda environment — your computer

Open a terminal in the downloaded `locust` folder:

```bash
conda create -n project3-locust python=3.14 pip -y
conda activate project3-locust
python -m pip install -r requirements.txt
```

## 4. Run experiments — your computer

Keep the SSH tunnel open. In the downloaded `locust` folder:

```bash
conda activate project3-locust
python run.py --replicas 1 --users 5
```

The defaults are 1 new user per second, 15 seconds of warm-up after all users start, and 120 seconds of measurement. Change them when needed:

```bash
python run.py --replicas auto --users 40 --spawn-rate 5 --warmup 30 --duration 180
```

Each run saves a summary JSON and Locust CSV files in `results/`. The summary includes requests, failures, latency, model versions, and responses by pod. The CSV history may include warm-up samples. Each request creates an application database audit record.

`--replicas` is a label for the results; it does not change the HPA. Every request uses a fresh connection to help distribute traffic across pods.

## 5. Select a scenario and observe — NBAM07

For one pod:

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl patch hpa property-api -n project-3 --type merge -p '{"spec":{"minReplicas":1,"maxReplicas":1}}'
kubectl get pods -n project-3 -l app=property-api -w
```

For three pods:

```bash
kubectl patch hpa property-api -n project-3 --type merge -p '{"spec":{"minReplicas":3,"maxReplicas":3}}'
kubectl get pods -n project-3 -l app=property-api -w
```

Restore autoscaling after fixed-pod tests:

```bash
kubectl patch hpa property-api -n project-3 --type merge -p '{"spec":{"minReplicas":1,"maxReplicas":3}}'
kubectl get hpa,pods -n project-3 -w
```

Wait until the expected pods are ready before starting each experiment. For the three-pod scenario use `--replicas 3`; for autoscaling use `--replicas auto`. Open the Project 3 API dashboard in Grafana to compare requests by pod, latency, errors, and resources.

## 6. Remove the Conda environment — your computer

```bash
conda deactivate
conda env remove -n project3-locust
```
