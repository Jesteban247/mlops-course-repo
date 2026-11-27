# Project 3 — Locust

## 1. Check the API Service and HPA — NBAM07

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl -n project-3 get svc property-api -o jsonpath='{.spec.clusterIP}{"\n"}'
kubectl -n project-3 get hpa property-api
```

## 2. Open the SSH tunnel — tester’s computer

Replace `API_SERVICE_IP` with the address above and leave this terminal open.

```bash
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:18001:API_SERVICE_IP:8000 estudiante@10.43.97.96
```

## 3. Start Locust — tester’s computer

Open another terminal in the downloaded `project_3/locust` folder and reuse the Project 2 Conda environment.

```bash
conda activate project2-locust
curl -fsS http://127.0.0.1:18001/ready
locust -f locustfile.py --host http://127.0.0.1:18001 --web-host 127.0.0.1
```

Start the test once `/ready` shows a model version and the HPA shows one replica.

## 4. Watch the API scale

On NBAM07:

```bash
kubectl -n project-3 get hpa property-api -w
```

1. Open <http://localhost:8089>. Start with **10 users** and a spawn rate of **5 users per second**.
