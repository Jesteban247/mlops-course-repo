# Project 3 — Locust

## 1. Single-pod capacity — NBAM07

```bash
cd /home/estudiante/mlops-course-repo/project_3/locust &&
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml" &&
kubectl -n project-3 patch hpa property-api --type merge -p '{"spec":{"minReplicas":1,"maxReplicas":1}}' &&
kubectl -n project-3 wait --for=jsonpath='{.spec.replicas}'=1 deployment/property-api --timeout=6m &&
kubectl -n project-3 rollout status deployment/property-api --timeout=5m &&
for users in 5 10 20 40; do
  bash run-in-cluster.sh --replicas 1 --users "$users" --spawn-rate 2 --duration 120 || break
done
```

## 2. Autoscaling from 1 to 3 — NBAM07

**Terminal 1**

```bash
cd /home/estudiante/mlops-course-repo/project_3/locust
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
mkdir -p results
kubectl -n project-3 get hpa property-api -w | tee "results/hpa-watch-$(date +%Y%m%d-%H%M%S).txt"
```

**Terminal 2**

```bash
cd /home/estudiante/mlops-course-repo/project_3/locust &&
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml" &&
kubectl apply -f ../k8s/api/hpa.yaml &&
bash run-in-cluster.sh --replicas auto --users 40 --spawn-rate 2 --duration 180
```

**After the load stops**

```bash
kubectl -n project-3 wait --for=jsonpath='{.spec.replicas}'=1 deployment/property-api --timeout=8m
kubectl -n project-3 get hpa property-api
```

## Results — NBAM07

```bash
find /home/estudiante/mlops-course-repo/project_3/locust/results -type f | sort
```
