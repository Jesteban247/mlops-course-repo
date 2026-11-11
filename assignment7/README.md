```bash
# Install Minikube on Linux x86-64; Docker must already be installed and running
curl -LO https://github.com/kubernetes/minikube/releases/latest/download/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
rm minikube-linux-amd64

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
rm kubectl
kubectl version --client

# Start a local Kubernetes cluster
minikube start --driver=docker --cpus=4 --memory=6g
kubectl config use-context minikube
kubectl config current-context
kubectl get nodes -o wide

# Build the local API image and load it into Minikube
cd /home/estudiante/mlops-course-repo
docker pull python:3.11-slim
docker build -t jesteban247/assignment7-api:local assignment7/api
minikube image load jesteban247/assignment7-api:local

# Deploy two API replicas and their Kubernetes Service
kubectl create namespace assignment7 --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n assignment7 -f assignment7/k8s/api/
kubectl rollout status deployment/assignment7-api -n assignment7 --timeout=5m
kubectl get pods,svc -n assignment7 -o wide

# On NBAM07: replace 192.168.49.2 below if minikube ip is different
minikube ip
curl http://192.168.49.2:32302/random

# On your computer: replace 192.168.49.2 below if minikube ip is different
ssh -L 8080:192.168.49.2:32302 estudiante@10.43.97.96

# Open http://127.0.0.1:8080/docs and call GET /random several times

# Stop the SSH tunnel with Ctrl+C before cleanup
kubectl config use-context minikube
kubectl delete namespace assignment7 --ignore-not-found
minikube delete --all --purge
docker image rm -f jesteban247/assignment7-api:local jesteban247/assignment7-api:local-v2 jesteban247/assignment7-api:local-v3
docker image rm -f gcr.io/k8s-minikube/kicbase:v0.0.51
sudo rm -f /usr/local/bin/minikube
# Keep kubectl installed because Project 2 also uses it with K3s
```
