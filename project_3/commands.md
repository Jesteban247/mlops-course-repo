# Project 3 commands

Run in order. Stop if a command fails. These commands use NBAM07 `10.43.97.96`, NBAM19 `10.43.97.108`, interface `ens192`, and the existing `project_3/.env`. Test locally first; GitHub and Argo CD come afterward.

## 1. K3s server — NBAM07

```bash
ip -4 route
df -h /var
command -v k3s || true
systemctl is-active k3s || true
```

Install only if the server is not already installed:

```bash
POD_CIDR='10.42.0.0/16'
SERVICE_CIDR='10.44.0.0/16'
SERVICE_DNS='10.44.0.10'
set -o pipefail
curl -sfL https://get.k3s.io | sudo env \
  INSTALL_K3S_VERSION='v1.36.5+k3s1' \
  INSTALL_K3S_EXEC="server --cluster-cidr=$POD_CIDR --service-cidr=$SERVICE_CIDR --cluster-dns=$SERVICE_DNS" sh -
```

```bash
sudo systemctl enable --now k3s
mkdir -p "$HOME/.kube"
sudo install -m 600 -o "$(id -u)" -g "$(id -g)" /etc/rancher/k3s/k3s.yaml "$HOME/.kube/project-3-k3s.yaml"
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl wait --for=condition=Ready nodes --all --timeout=5m
kubectl get nodes -o wide
```

## 2. Firewall and join token — NBAM07

```bash
sudo systemctl enable --now firewalld
mkdir -p "$HOME/.local/state/project_3"
ZONE="$(sudo firewall-cmd --get-zone-of-interface=ens192)"
[ "$ZONE" != 'no zone' ] || ZONE="$(sudo firewall-cmd --get-default-zone)"
printf '%s\n' "$ZONE" > "$HOME/.local/state/project_3/firewall-zone"
for CIDR in 10.42.0.0/16 10.44.0.0/16; do
  if ! sudo firewall-cmd --permanent --zone=trusted --query-source="$CIDR" >/dev/null; then
    sudo firewall-cmd --permanent --zone=trusted --add-source="$CIDR"
    printf '%s\n' "$CIDR" >> "$HOME/.local/state/project_3/firewall-sources"
  fi
done
for PORT in 6443/tcp 8472/udp 10250/tcp 2049/tcp; do
  RULE="rule family=\"ipv4\" source address=\"10.43.97.108/32\" port port=\"${PORT%/*}\" protocol=\"${PORT#*/}\" accept"
  if ! sudo firewall-cmd --permanent --zone="$ZONE" --query-rich-rule="$RULE" >/dev/null; then
    sudo firewall-cmd --permanent --zone="$ZONE" --add-rich-rule="$RULE"
    printf '%s\n' "$RULE" >> "$HOME/.local/state/project_3/firewall-rules"
  fi
done
sudo firewall-cmd --reload
sudo cat /var/lib/rancher/k3s/server/node-token
```

## 3. Firewall and K3s worker — NBAM19

```bash
sudo systemctl enable --now firewalld
mkdir -p "$HOME/.local/state/project_3"
ZONE="$(sudo firewall-cmd --get-zone-of-interface=ens192)"
[ "$ZONE" != 'no zone' ] || ZONE="$(sudo firewall-cmd --get-default-zone)"
printf '%s\n' "$ZONE" > "$HOME/.local/state/project_3/firewall-zone"
for CIDR in 10.42.0.0/16 10.44.0.0/16; do
  if ! sudo firewall-cmd --permanent --zone=trusted --query-source="$CIDR" >/dev/null; then
    sudo firewall-cmd --permanent --zone=trusted --add-source="$CIDR"
    printf '%s\n' "$CIDR" >> "$HOME/.local/state/project_3/firewall-sources"
  fi
done
for PORT in 8472/udp 10250/tcp; do
  RULE="rule family=\"ipv4\" source address=\"10.43.97.96/32\" port port=\"${PORT%/*}\" protocol=\"${PORT#*/}\" accept"
  if ! sudo firewall-cmd --permanent --zone="$ZONE" --query-rich-rule="$RULE" >/dev/null; then
    sudo firewall-cmd --permanent --zone="$ZONE" --add-rich-rule="$RULE"
    printf '%s\n' "$RULE" >> "$HOME/.local/state/project_3/firewall-rules"
  fi
done
sudo firewall-cmd --reload
```

Install only if the agent is not already installed:

```bash
timeout 5 bash -c '</dev/tcp/10.43.97.96/6443'
read -rs -p 'K3s join token: ' PROJECT3_JOIN_TOKEN; echo
set -o pipefail
curl -sfL https://get.k3s.io | sudo env \
  INSTALL_K3S_VERSION='v1.36.5+k3s1' \
  K3S_URL='https://10.43.97.96:6443' K3S_TOKEN="$PROJECT3_JOIN_TOKEN" sh -
unset PROJECT3_JOIN_TOKEN
```

```bash
sudo systemctl enable --now k3s-agent
sudo systemctl status k3s-agent --no-pager
```

## 4. Shared files — NBAM07

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl get nodes -o wide
cd /home/estudiante/mlops-course-repo
rpm -q nfs-utils >/dev/null 2>&1 || sudo dnf install -y nfs-utils
rpm -q acl >/dev/null 2>&1 || sudo dnf install -y acl
mkdir -p project_3/data
sudo setfacl -R -m u:50000:rwX project_3/data
find project_3/data -type d -exec sudo setfacl -m d:u:50000:rwX,d:u:1001:rwX {} +
```

```bash
if [ "$(getenforce)" != Disabled ] && [ "$(getsebool nfs_export_all_rw | awk '{print $3}')" = off ]; then
  echo off > "$HOME/.local/state/project_3/nfs-export-selinux"
  sudo setsebool -P nfs_export_all_rw on
fi
PROJECT3_UID="$(id -u)"
PROJECT3_GID="$(id -g)"
printf '%s 10.43.97.108(rw,sync,all_squash,anonuid=%s,anongid=%s,no_subtree_check)\n' \
  /home/estudiante/mlops-course-repo/project_3 "$PROJECT3_UID" "$PROJECT3_GID" | sudo tee /etc/exports.d/project3.exports >/dev/null
sudo systemctl enable --now nfs-server
sudo exportfs -ra
sudo exportfs -v
```

## 5. NFS client — NBAM19

```bash
rpm -q nfs-utils >/dev/null 2>&1 || sudo dnf install -y nfs-utils
if [ "$(getenforce)" != Disabled ] && [ "$(getsebool virt_use_nfs | awk '{print $3}')" = off ]; then
  echo off > "$HOME/.local/state/project_3/nfs-client-selinux"
  sudo setsebool -P virt_use_nfs on
fi
sudo mkdir -p /mnt/project3-nfs-check
sudo mount -t nfs -o vers=4.2 10.43.97.96:/home/estudiante/mlops-course-repo/project_3 /mnt/project3-nfs-check
ls /mnt/project3-nfs-check/notebooks
sudo umount /mnt/project3-nfs-check
sudo rmdir /mnt/project3-nfs-check
```

## 6. Project Secrets and core services — NBAM07

```bash
cd /home/estudiante/mlops-course-repo && \
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml" && \
bash project_3/scripts/apply-secrets.sh && \
kubectl apply -k project_3/k8s && \
kubectl get pods,pvc,svc -n project-3 -o wide
```

```bash
kubectl rollout status deployment/property-postgres -n project-3 --timeout=10m
kubectl rollout status deployment/minio -n project-3 --timeout=10m
kubectl rollout status deployment/mlflow -n project-3 --timeout=10m
kubectl rollout status deployment/jupyter -n project-3 --timeout=10m
```

## 7. Airflow — NBAM07

```bash
mkdir -p "$HOME/.local/bin"
curl -fsSL https://get.helm.sh/helm-v3.19.0-linux-amd64.tar.gz -o /tmp/project-3-helm.tar.gz && \
tar -xzf /tmp/project-3-helm.tar.gz -C /tmp linux-amd64/helm && \
install -m 755 /tmp/linux-amd64/helm "$HOME/.local/bin/helm"
```

```bash
cd /home/estudiante/mlops-course-repo && \
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml" && \
"$HOME/.local/bin/helm" repo add apache-airflow https://airflow.apache.org && \
"$HOME/.local/bin/helm" repo update apache-airflow && \
"$HOME/.local/bin/helm" upgrade --install airflow apache-airflow/airflow --version 1.22.0 -n project-3 -f project_3/k8s/airflow/values.yaml
```

```bash
kubectl rollout status statefulset/airflow-scheduler -n project-3 --timeout=20m
kubectl rollout status deployment/airflow-dag-processor -n project-3 --timeout=20m
kubectl rollout status deployment/airflow-api-server -n project-3 --timeout=20m
kubectl get pods -n project-3 -o wide
```

## 8. Service access — NBAM07

Run each port-forward in its own terminal. Stop it with Ctrl+C.

Airflow — <http://localhost:8082> (`AIRFLOW_USERNAME` and `AIRFLOW_PASSWORD` in `.env`):

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl port-forward -n project-3 svc/airflow-api-server 8082:8080
```

MLflow — <http://localhost:5000>:

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl port-forward -n project-3 svc/mlflow 5000:5000
```

Jupyter — <http://localhost:8888> (`JUPYTER_TOKEN` in `.env`):

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl port-forward -n project-3 svc/jupyter 8888:8888
```

MinIO console — <http://localhost:9001> (`MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` in `.env`):

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl port-forward -n project-3 svc/minio 9001:9001
```

## 9. Build the API image — NBAM07

```bash
cd /home/estudiante/mlops-course-repo && \
docker build -f project_3/api/Dockerfile -t project-3-property-api:local project_3 && \
docker save -o project_3/data/project-3-property-api-local.tar project-3-property-api:local
```

## 10. Import the API image — NBAM19

Run on NBAM19, not NBAM07:

```bash
[ "$(hostname -s | tr '[:upper:]' '[:lower:]')" = nbam19 ] && \
sudo mkdir -p /mnt/project3-image && \
sudo mount -t nfs -o vers=4.2 10.43.97.96:/home/estudiante/mlops-course-repo/project_3 /mnt/project3-image && \
sudo /usr/local/bin/k3s ctr images import /mnt/project3-image/data/project-3-property-api-local.tar && \
sudo umount /mnt/project3-image && \
sudo rmdir /mnt/project3-image
```

## 11. Deploy and test the API — NBAM07

After the DAG has registered a champion:

```bash
cd /home/estudiante/mlops-course-repo && \
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml" && \
kubectl apply -f project_3/k8s/api/api.yaml && \
kubectl set image deployment/property-api api=project-3-property-api:local -n project-3 && \
kubectl patch deployment/property-api -n project-3 --type=strategic -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","imagePullPolicy":"IfNotPresent"}]}}}}' && \
kubectl rollout status deployment/property-api -n project-3 --timeout=10m
```

API — <http://localhost:8000/docs>:

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl port-forward -n project-3 svc/property-api 8000:8000
```

```bash
cd /home/estudiante/mlops-course-repo
curl -fsS http://127.0.0.1:8000/health; echo
curl -fsS http://127.0.0.1:8000/ready; echo
curl -fsS http://127.0.0.1:8000/predict -H 'Content-Type: application/json' --data-binary @project_3/api/example-request.json; echo
```

## 12. GitHub and Docker Hub — NBAM07

```bash
cd /home/estudiante/mlops-course-repo
git status
git switch -c YOUR_BRANCH
git add project_3 .github/workflows/project-3-ci.yml
git diff --cached --stat
git commit -m 'YOUR COMMIT MESSAGE'
git push -u origin YOUR_BRANCH
```

Open a PR to `main`. Wait for the checks and the automatic image-tag commit before merging.

```bash
git switch main && git pull --ff-only origin main
git branch -d YOUR_BRANCH
```

## 13. Argo CD — NBAM07

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
mkdir -p "$HOME/.local/share/project-3"
curl -fL --retry 3 https://codeload.github.com/argoproj/argo-cd/tar.gz/refs/tags/stable -o /tmp/project-3-argocd-stable.tar.gz && \
  tar -xOzf /tmp/project-3-argocd-stable.tar.gz argo-cd-stable/manifests/install.yaml > "$HOME/.local/share/project-3/argocd-install.yaml" && \
  test -s "$HOME/.local/share/project-3/argocd-install.yaml"
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd --server-side --force-conflicts -f "$HOME/.local/share/project-3/argocd-install.yaml"
kubectl rollout status deployment/argocd-server -n argocd --timeout=10m
```

## 14. Argo CD applications — NBAM07

After the GitHub PR is merged, stop using `helm upgrade` for this release and let Argo CD manage its resources:

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl apply -f project_3/argocd/
kubectl get applications -n argocd
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
kubectl port-forward -n argocd svc/argocd-server 8080:443
```

Open <https://localhost:8080> and review the applications before syncing. The API manifest uses the published Docker Hub image.

## 15. Remove the old test API — NBAM07

```bash
kubectl delete application project-3-test-api -n argocd --ignore-not-found
kubectl delete namespace project-3-test-api --ignore-not-found
```

## 16. Project cleanup — NBAM07

**This removes Project 3 workloads and persistent database/MinIO data.**

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl delete application project-3-api project-3-airflow project-3-core -n argocd --ignore-not-found
kubectl delete namespace project-3 --wait --ignore-not-found
```

## 17. Full cluster cleanup — NBAM19

**This uninstalls the K3s worker.**

```bash
sudo /usr/local/bin/k3s-agent-uninstall.sh
if [ -f "$HOME/.local/state/project_3/nfs-client-selinux" ]; then
  sudo setsebool -P virt_use_nfs off
fi
ZONE="$(cat "$HOME/.local/state/project_3/firewall-zone")"
if [ -f "$HOME/.local/state/project_3/firewall-rules" ]; then
  while IFS= read -r RULE; do sudo firewall-cmd --permanent --zone="$ZONE" --remove-rich-rule="$RULE"; done < "$HOME/.local/state/project_3/firewall-rules"
fi
if [ -f "$HOME/.local/state/project_3/firewall-sources" ]; then
  while IFS= read -r CIDR; do sudo firewall-cmd --permanent --zone=trusted --remove-source="$CIDR"; done < "$HOME/.local/state/project_3/firewall-sources"
fi
sudo firewall-cmd --reload
rm -rf "$HOME/.local/state/project_3"
```

## 18. Full cluster cleanup — NBAM07

**This uninstalls the entire K3s server, including Argo CD and other cluster workloads.**

```bash
kubectl delete node nbam19 --ignore-not-found
sudo /usr/local/bin/k3s-uninstall.sh
sudo rm -f /etc/exports.d/project3.exports
sudo exportfs -ra
sudo setfacl -R -x u:50000 /home/estudiante/mlops-course-repo/project_3/data
find /home/estudiante/mlops-course-repo/project_3/data -type d -exec sudo setfacl -x d:u:50000,d:u:1001 {} +
if [ -f "$HOME/.local/state/project_3/nfs-export-selinux" ]; then
  sudo setsebool -P nfs_export_all_rw off
fi
ZONE="$(cat "$HOME/.local/state/project_3/firewall-zone")"
if [ -f "$HOME/.local/state/project_3/firewall-rules" ]; then
  while IFS= read -r RULE; do sudo firewall-cmd --permanent --zone="$ZONE" --remove-rich-rule="$RULE"; done < "$HOME/.local/state/project_3/firewall-rules"
fi
if [ -f "$HOME/.local/state/project_3/firewall-sources" ]; then
  while IFS= read -r CIDR; do sudo firewall-cmd --permanent --zone=trusted --remove-source="$CIDR"; done < "$HOME/.local/state/project_3/firewall-sources"
fi
sudo firewall-cmd --reload
rm -rf "$HOME/.local/state/project_3"
rm -f "$HOME/.local/share/project-3/argocd-install.yaml"
rm -f "$HOME/.kube/project-3-k3s.yaml" /tmp/project-3-argocd-stable.tar.gz
unset KUBECONFIG
```

The repository, `.env`, and locally saved batch files remain.
