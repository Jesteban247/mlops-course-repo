# Project 3 commands

For local testing, follow sections 1–13 before opening the PR. For a fresh deployment after the PR is merged, follow sections 2–6, 10, and 15, then open the services in section 13. This path uses the published images through Argo CD.

## 1. Build local test images — NBAM07

```bash
cd /home/estudiante/mlops-course-repo && \
mkdir -p project_3/data && \
docker build -f project_3/api/Dockerfile -t project-3-property-api:local-test project_3 && \
docker build -f project_3/streamlit/Dockerfile -t project-3-property-ui:local-test project_3 && \
docker save -o project_3/data/project-3-test-images.tar project-3-property-api:local-test project-3-property-ui:local-test && \
tar -tf project_3/data/project-3-test-images.tar >/dev/null
```

After the archive is saved, free the local images and Docker build cache. This deletes the Docker build cache for all projects.

```bash
docker image rm project-3-property-api:local-test project-3-property-ui:local-test
docker image rm project-3-property-api:local-test-20261123 project-3-property-ui:local-test-20261123 project-3-property-api:local 2>/dev/null || true
docker builder prune -af
df -h /var
```

## 2. K3s server — NBAM07

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

## 3. Firewall and join token — NBAM07

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

## 4. Firewall and K3s worker — NBAM19

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

## 5. Shared files — NBAM07

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

## 6. NFS client — NBAM19

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

## 7. Import images — NBAM19

```bash
[ "$(hostname -s | tr '[:upper:]' '[:lower:]')" = nbam19 ] && \
sudo mkdir -p /mnt/project3-image && \
sudo mount -t nfs -o vers=4.2 10.43.97.96:/home/estudiante/mlops-course-repo/project_3 /mnt/project3-image && \
sudo /usr/local/bin/k3s ctr -n k8s.io images import /mnt/project3-image/data/project-3-test-images.tar && \
sudo umount /mnt/project3-image && \
sudo rmdir /mnt/project3-image
```

## 8. Secrets and local services — NBAM07

```bash
cd /home/estudiante/mlops-course-repo && \
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml" && \
bash project_3/scripts/apply-secrets.sh && \
kubectl apply -k project_3/k8s && \
kubectl rollout status deployment/property-postgres -n project-3 --timeout=10m && \
kubectl rollout status deployment/airflow-postgres -n project-3 --timeout=10m && \
kubectl rollout status deployment/minio -n project-3 --timeout=10m && \
kubectl wait --for=condition=complete job/create-mlflow-bucket -n project-3 --timeout=10m && \
kubectl rollout status deployment/mlflow -n project-3 --timeout=10m && \
kubectl exec -i -n project-3 deployment/property-postgres -- sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < project_3/sql/01_schema.sql
```

## 9. Airflow — NBAM07

```bash
mkdir -p "$HOME/.local/share/project-3" && \
curl -fsSL https://get.helm.sh/helm-v3.19.0-linux-amd64.tar.gz -o /tmp/project-3-helm.tar.gz && \
tar -xzf /tmp/project-3-helm.tar.gz -C /tmp linux-amd64/helm && \
install -m 755 /tmp/linux-amd64/helm "$HOME/.local/share/project-3/helm"
```

```bash
cd /home/estudiante/mlops-course-repo && \
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml" && \
"$HOME/.local/share/project-3/helm" repo add apache-airflow https://airflow.apache.org && \
"$HOME/.local/share/project-3/helm" repo update apache-airflow && \
"$HOME/.local/share/project-3/helm" upgrade --install airflow apache-airflow/airflow --version 1.22.0 -n project-3 -f project_3/k8s/airflow/values.yaml && \
kubectl rollout status statefulset/airflow-scheduler -n project-3 --timeout=20m && \
kubectl rollout status deployment/airflow-dag-processor -n project-3 --timeout=20m && \
kubectl rollout status deployment/airflow-api-server -n project-3 --timeout=20m
```

## 10. Argo CD — NBAM07

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
mkdir -p "$HOME/.local/share/project-3"
curl -fL --retry 3 https://codeload.github.com/argoproj/argo-cd/tar.gz/refs/tags/stable -o /tmp/project-3-argocd-stable.tar.gz && \
  tar -xOzf /tmp/project-3-argocd-stable.tar.gz argo-cd-stable/manifests/install.yaml > "$HOME/.local/share/project-3/argocd-install.yaml" && \
  test -s "$HOME/.local/share/project-3/argocd-install.yaml"
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd --server-side --force-conflicts -f "$HOME/.local/share/project-3/argocd-install.yaml"
kubectl rollout status deployment/argocd-server -n argocd --timeout=10m
cd /home/estudiante/mlops-course-repo
python3 project_3/scripts/apply-argocd-login.py
```

Register the applications in section 15 after merging the tested code into `main`.

## 11. Local API, Streamlit and autoscaling — NBAM07

```bash
cd /home/estudiante/mlops-course-repo && \
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml" && \
sed -e 's|image: docker.io/.*/project-3-property-api:.*|image: project-3-property-api:local-test|' -e 's|imagePullPolicy: Always|imagePullPolicy: IfNotPresent|' project_3/k8s/api/api.yaml | kubectl apply -f -
```

```bash
sed 's|image: docker.io/.*/project-3-property-ui:.*|image: project-3-property-ui:local-test|' project_3/k8s/streamlit/streamlit.yaml | kubectl apply -f - && \
kubectl apply -f project_3/k8s/api/hpa.yaml && \
kubectl get pods,pvc,svc,hpa -n project-3 -o wide
```

The API becomes ready after the first successful DAG run creates a champion in MLflow.

## 12. Local status — NBAM07

```bash
kubectl rollout status deployment/property-ui -n project-3 --timeout=10m
kubectl rollout status deployment/prometheus -n project-3 --timeout=10m
kubectl rollout status deployment/grafana -n project-3 --timeout=10m
kubectl rollout status deployment/locust -n project-3 --timeout=10m
kubectl rollout status deployment/jupyter -n project-3 --timeout=10m
kubectl get pods,pvc,svc,hpa -n project-3 -o wide
kubectl top nodes
```

## 13. Service access and testing — NBAM07

Run each port-forward in a separate terminal. Stop it with Ctrl+C.

Argo CD — <https://localhost:8080> (`ARGOCD_USERNAME`, `ARGOCD_PASSWORD` in `.env`):

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl port-forward -n argocd svc/argocd-server 8080:443
```

Airflow — <http://localhost:8082> (`AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD` in `.env`):

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl port-forward -n project-3 svc/airflow-api-server 8082:8080
```

Open Airflow and run `project_3_check_teacher_api`. If necessary and permitted, run `project_3_reset_teacher_batches`, then trigger `project_3_property_pipeline`. Each pipeline run consumes one batch.

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

MinIO — <http://localhost:9001> (`MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` in `.env`):

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl port-forward -n project-3 svc/minio 9001:9001
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

Streamlit — <http://localhost:8501>:

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl port-forward -n project-3 svc/property-ui 8501:8501
```

Prometheus — <http://localhost:9090>:

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl port-forward -n project-3 svc/prometheus 9090:9090
```

Grafana — <http://localhost:3000> (`GRAFANA_USERNAME`, `GRAFANA_PASSWORD` in `.env`):

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl port-forward -n project-3 svc/grafana 3000:3000
```

Locust runs locally; see [locust/README.md](locust/README.md).

```bash
kubectl get hpa,pods -n project-3 -w
```

## 14. GitHub — NBAM07

After local testing:

```bash
cd /home/estudiante/mlops-course-repo
git status
git switch -c YOUR_BRANCH
git add project_3 .github/workflows/project-3-ci.yml
git diff --cached --stat
git commit -m 'YOUR COMMIT MESSAGE'
git push -u origin YOUR_BRANCH
```

Open a PR to `main`. Wait for GitHub Actions to publish the API and Streamlit images when their sources change. Verify the SHA tags in the bot commit and wait for the final checks before merging.

```bash
git switch main && git pull --ff-only origin main
git branch -d YOUR_BRANCH
```

## 15. Argo CD applications — NBAM07

After the PR is merged:

```bash
cd /home/estudiante/mlops-course-repo && \
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml" && \
bash project_3/scripts/apply-secrets.sh && \
kubectl apply -f project_3/argocd/ && \
kubectl get applications -n argocd
```

The four applications now sync automatically from `main`. Check **Details → Sync Policy → Automated**. On a fresh database, wait for Airflow and MLflow, then run the pipeline from section 13. The API becomes **Healthy** after loading the first promoted model. Use Argo CD for further Airflow deployment changes.

For the autosync demo, change the Streamlit CPU request from `100m` to `150m` in `project_3/k8s/streamlit/streamlit.yaml` through a second PR. After merging, refresh the application and check **History and Rollback** for the revision. Verify on NBAM07.

```bash
kubectl rollout status deployment/property-ui -n project-3 --timeout=10m
kubectl get deployment property-ui -n project-3 -o jsonpath='{.spec.template.spec.containers[0].resources.requests.cpu}{"\n"}'
```

## Final status and evidence — NBAM07

Run after the first model has been promoted. Use notebook 09 in Jupyter for PostgreSQL evidence.

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl get nodes -o wide
kubectl get deploy,sts,pods,jobs,pvc,svc,hpa -n project-3 -o wide
kubectl get applications,pods -n argocd
kubectl get deploy property-api property-ui -n project-3 -o custom-columns=NAME:.metadata.name,IMAGE:.spec.template.spec.containers[0].image
kubectl top pods -n project-3 --containers
kubectl logs -n project-3 deployment/property-api --tail=30
```

## 16. Project cleanup — NBAM07

This removes the project workloads and their database/MinIO data.

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl delete application project-3-streamlit project-3-api project-3-airflow project-3-core -n argocd --ignore-not-found
kubectl delete namespace project-3 --wait --ignore-not-found
```

## 17. Full cluster cleanup — NBAM19

**This uninstalls the K3s worker and removes unused Docker images and build cache.**

```bash
sudo /usr/local/bin/k3s-agent-uninstall.sh
if [ -f "$HOME/.local/state/project_3/nfs-client-selinux" ]; then
  sudo setsebool -P virt_use_nfs off
fi
if [ -f "$HOME/.local/state/project_3/firewall-zone" ] && [ -f "$HOME/.local/state/project_3/firewall-rules" ]; then
  ZONE="$(cat "$HOME/.local/state/project_3/firewall-zone")"
  while IFS= read -r RULE; do sudo firewall-cmd --permanent --zone="$ZONE" --remove-rich-rule="$RULE"; done < "$HOME/.local/state/project_3/firewall-rules"
fi
if [ -f "$HOME/.local/state/project_3/firewall-sources" ]; then
  while IFS= read -r CIDR; do sudo firewall-cmd --permanent --zone=trusted --remove-source="$CIDR"; done < "$HOME/.local/state/project_3/firewall-sources"
fi
sudo firewall-cmd --reload
rm -rf "$HOME/.local/state/project_3"
if command -v docker >/dev/null 2>&1; then
  docker image prune -a -f
  docker builder prune -a -f
  docker image ls
fi
df -h /var
```

## 18. Full cluster cleanup — NBAM07

**This uninstalls the entire K3s server, including Argo CD and other cluster workloads, and removes unused Docker images and build cache.**

```bash
sudo /usr/local/bin/k3s-uninstall.sh
sudo rm -f /etc/exports.d/project3.exports
sudo exportfs -ra
sudo setfacl -R -x u:50000 /home/estudiante/mlops-course-repo/project_3/data
find /home/estudiante/mlops-course-repo/project_3/data -type d -exec sudo setfacl -x d:u:50000,d:u:1001 {} +
if [ -f "$HOME/.local/state/project_3/nfs-export-selinux" ]; then
  sudo setsebool -P nfs_export_all_rw off
fi
if [ -f "$HOME/.local/state/project_3/firewall-zone" ] && [ -f "$HOME/.local/state/project_3/firewall-rules" ]; then
  ZONE="$(cat "$HOME/.local/state/project_3/firewall-zone")"
  while IFS= read -r RULE; do sudo firewall-cmd --permanent --zone="$ZONE" --remove-rich-rule="$RULE"; done < "$HOME/.local/state/project_3/firewall-rules"
fi
if [ -f "$HOME/.local/state/project_3/firewall-sources" ]; then
  while IFS= read -r CIDR; do sudo firewall-cmd --permanent --zone=trusted --remove-source="$CIDR"; done < "$HOME/.local/state/project_3/firewall-sources"
fi
sudo firewall-cmd --reload
rm -rf "$HOME/.local/state/project_3"
rm -f "$HOME/.local/share/project-3/argocd-install.yaml" "$HOME/.local/share/project-3/helm"
rmdir "$HOME/.local/share/project-3" 2>/dev/null || true
rm -f "$HOME/.kube/project-3-k3s.yaml" /tmp/project-3-argocd-stable.tar.gz
rm -f /tmp/project-3-helm.tar.gz /tmp/linux-amd64/helm
rmdir /tmp/linux-amd64 2>/dev/null || true
rm -f /home/estudiante/mlops-course-repo/project_3/data/{project-3-test-images.tar,project-3-property-api-local.tar}
if command -v docker >/dev/null 2>&1; then
  docker image prune -a -f
  docker builder prune -a -f
  docker system df
fi
df -h /var
unset KUBECONFIG
```

The repository, `.env`, saved exploration batches, and system packages remain. For a fresh run, the old Airflow staging directory can be removed after preserving any files needed for evidence.

```bash
sudo rm -rf /home/estudiante/mlops-course-repo/project_3/data/ingestion
```
