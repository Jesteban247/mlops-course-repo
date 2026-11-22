# Project 3 commands

## 1. Install K3s

Check that K3s is not installed and that the cluster networks do not overlap local or VPN routes.

```bash
cd /home/estudiante/mlops-course-repo
command -v k3s || true
systemctl is-active k3s || true
ip -4 route
```

```bash
POD_CIDR='10.42.0.0/16'
SERVICE_CIDR='10.44.0.0/16'
SERVICE_DNS='10.44.0.10'
set -o pipefail
curl -sfL https://get.k3s.io | sudo env \
  INSTALL_K3S_VERSION='v1.36.5+k3s1' \
  INSTALL_K3S_EXEC="server --cluster-cidr=$POD_CIDR --service-cidr=$SERVICE_CIDR --cluster-dns=$SERVICE_DNS" \
  sh -
```

```bash
mkdir -p "$HOME/.kube"
sudo install -m 600 -o "$(id -u)" -g "$(id -g)" /etc/rancher/k3s/k3s.yaml "$HOME/.kube/project-3-k3s.yaml"
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl wait --for=condition=Ready nodes --all --timeout=5m
kubectl get nodes
```

Run this in every new terminal before using `kubectl`:

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
```

## 2. Run the API locally

```bash
cd /home/estudiante/mlops-course-repo
set -o pipefail
docker build -t project-3-test-api:1.0 project_3/test-api
docker save project-3-test-api:1.0 | sudo /usr/local/bin/k3s ctr images import -
kubectl create namespace project-3-test-api --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n project-3-test-api -f project_3/k8s/test-api/
kubectl rollout status deployment/test-api -n project-3-test-api --timeout=5m
kubectl get pods -n project-3-test-api
kubectl port-forward -n project-3-test-api service/test-api 8081:8000
```

Open <http://localhost:8081/docs>; stop the port-forward with Ctrl+C. Forward port 8081 in VS Code if using a remote machine.

## 3. Install Argo CD

```bash
mkdir -p "$HOME/.local/share/project-3"
curl -fL --retry 3 https://codeload.github.com/argoproj/argo-cd/tar.gz/refs/tags/stable -o /tmp/project-3-argocd-stable.tar.gz && \
  tar -xOzf /tmp/project-3-argocd-stable.tar.gz argo-cd-stable/manifests/install.yaml > "$HOME/.local/share/project-3/argocd-install.yaml" && \
  test -s "$HOME/.local/share/project-3/argocd-install.yaml"
```

```bash
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd --server-side --force-conflicts -f "$HOME/.local/share/project-3/argocd-install.yaml"
kubectl rollout status deployment/argocd-server -n argocd --timeout=10m
kubectl get pods -n argocd
```

## 4. Push the starter

```bash
cd /home/estudiante/mlops-course-repo
git switch main
git pull --ff-only origin main
git switch -c project-3-starter
git add project_3
git diff --cached -- project_3
git commit --only -m 'Add Project 3 Argo CD starter' -- project_3
git push -u origin project-3-starter
```

Open a PR on GitHub and merge it into `main`.

## 5. Connect and sync Argo CD

For a private repository, add repository credentials in the Argo CD UI.

```bash
kubectl apply -f project_3/argocd/test-api-application.yaml
kubectl get applications -n argocd
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
kubectl port-forward -n argocd service/argocd-server 8080:443
```

Open <https://localhost:8080>, sign in as `admin` with the printed password, and change it. Select `project-3-test-api` → **Sync → Synchronize**. Forward port 8080 in VS Code if using a remote machine.

## 6. Change the pod count

```bash
cd /home/estudiante/mlops-course-repo
git switch main
git pull --ff-only origin main
git switch -c scale-project-3-test-api
```

In `project_3/k8s/test-api/deployment.yaml`, change `replicas: 1` to `replicas: 2`.

```bash
git add project_3/k8s/test-api/deployment.yaml
git commit --only -m 'Scale Project 3 API to two replicas' -- project_3/k8s/test-api/deployment.yaml
git push -u origin scale-project-3-test-api
```

Open and merge the PR into `main`. In Argo CD, refresh the app and select **Sync → Synchronize**.

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl rollout status deployment/test-api -n project-3-test-api --timeout=5m
kubectl get deployment,pods -n project-3-test-api
```
