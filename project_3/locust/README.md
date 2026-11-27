# Project 3 — Locust

## 1. Connect to the API Service — NBAM07

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl -n project-3 get svc property-api -o jsonpath='{.spec.clusterIP}{"\n"}'
```

## 2. Set up Locust — tester’s computer

Download the `project_3/locust` folder. Replace `API_SERVICE_IP` with the address from step 1 and leave this terminal open.

```bash
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:18001:API_SERVICE_IP:8000 estudiante@10.43.97.96
```

In another terminal, open the downloaded folder.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
curl -fsS http://127.0.0.1:18001/ready
```

## 3. Single-pod capacity

**NBAM07**

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl -n project-3 patch hpa property-api --type merge -p '{"spec":{"minReplicas":1,"maxReplicas":1}}' &&
kubectl -n project-3 wait --for=jsonpath='{.spec.replicas}'=1 deployment/property-api --timeout=6m &&
kubectl -n project-3 rollout status deployment/property-api --timeout=5m
```

**Tester’s computer**

```bash
for users in 5 10 20 40; do
  python run.py --replicas 1 --users "$users" --spawn-rate 2 --duration 120 || break
done
```

## 4. Autoscaling from 1 to 3

**NBAM07**

```bash
cd /home/estudiante/mlops-course-repo
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl apply -f project_3/k8s/api/hpa.yaml &&
mkdir -p project_3/locust/results &&
kubectl -n project-3 get hpa property-api -w | tee "project_3/locust/results/hpa-watch-$(date +%Y%m%d-%H%M%S).txt"
```

**Tester’s computer**

```bash
python run.py --replicas auto --users 40 --spawn-rate 2 --duration 180
ls -lh results/
```

Stop the HPA watch with Ctrl+C after the API returns to one replica. Keep the summary JSON and CSV files from the tester’s computer and the HPA watch log from NBAM07 together for the experiment.
