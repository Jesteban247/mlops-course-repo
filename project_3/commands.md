# Project 3 commands

## 1. Build local test images — NBAM07

```bash
cd /home/estudiante/mlops-course-repo && \
mkdir -p project_3/data && \
docker build -f project_3/api/Dockerfile -t project-3-property-api:local-test project_3 && \
docker build -f project_3/streamlit/Dockerfile -t project-3-property-ui:local-test project_3 && \
docker save -o project_3/data/project-3-test-images.tar project-3-property-api:local-test project-3-property-ui:local-test && \
tar -tf project_3/data/project-3-test-images.tar >/dev/null
```

## 2. K3s server — NBAM07

```bash
ip -4 route
df -h /var
command -v k3s || true
systemctl is-active k3s || true
```

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
(
  set -euo pipefail
  df -h /var
  timeout 5 bash -c '</dev/tcp/10.43.97.96/6443'
  read -rs -p 'K3s join token: ' PROJECT3_JOIN_TOKEN
  echo
  test -n "$PROJECT3_JOIN_TOKEN"
  curl -sfL https://get.k3s.io | sudo env \
    INSTALL_K3S_VERSION='v1.36.5+k3s1' \
    K3S_URL='https://10.43.97.96:6443' K3S_TOKEN="$PROJECT3_JOIN_TOKEN" sh -
  systemctl is-active k3s-agent
)
```

## 5. Shared files — NBAM07

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl wait --for=condition=Ready node/nbam19 --timeout=5m
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

## 7. Import local test images — NBAM19

Copy the archive from NFS to local storage before importing. Both expected image tags should print at the end.

```bash
(
  set -euo pipefail
  [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" = nbam19 ]
  df -h /var /tmp
  project3_archive="$(mktemp /tmp/project3-images.XXXXXX.tar)"
  trap 'rm -f "$project3_archive"' EXIT
  sudo mkdir -p /mnt/project3-image
  project3_export='10.43.97.96:/home/estudiante/mlops-course-repo/project_3'
  if ! mountpoint -q /mnt/project3-image; then
    sudo mount -t nfs -o vers=4.2 "$project3_export" /mnt/project3-image
  fi
  test "$(findmnt -n -M /mnt/project3-image -o SOURCE)" = "$project3_export"
  trap 'sudo umount /mnt/project3-image && sudo rmdir /mnt/project3-image; rm -f "$project3_archive"' EXIT
  cp /mnt/project3-image/data/project-3-test-images.tar "$project3_archive"
  sudo umount /mnt/project3-image
  trap 'rm -f "$project3_archive"' EXIT
  sudo rmdir /mnt/project3-image
  sudo /usr/local/bin/k3s ctr -n k8s.io images import "$project3_archive"
  project3_images="$(sudo /usr/local/bin/k3s ctr -n k8s.io images ls -q)"
  grep -Fx 'docker.io/library/project-3-property-api:local-test' <<< "$project3_images"
  grep -Fx 'docker.io/library/project-3-property-ui:local-test' <<< "$project3_images"
)
```

## 8. Secrets and local services — NBAM07

```bash
cd /home/estudiante/mlops-course-repo && \
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml" && \
bash project_3/scripts/apply-secrets.sh && \
kubectl apply -k project_3/k8s && \
kubectl rollout status deployment/property-postgres -n project-3 --timeout=10m && \
kubectl rollout status deployment/airflow-postgres -n project-3 --timeout=10m && \
kubectl rollout status deployment/mlflow-postgres -n project-3 --timeout=10m && \
kubectl rollout status deployment/minio -n project-3 --timeout=10m && \
kubectl wait --for=condition=complete job/create-mlflow-bucket -n project-3 --timeout=10m && \
kubectl rollout status deployment/mlflow -n project-3 --timeout=20m && \
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
set -o pipefail
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
mkdir -p "$HOME/.local/share/project-3" && \
curl -fL --retry 3 https://codeload.github.com/argoproj/argo-cd/tar.gz/refs/tags/stable -o /tmp/project-3-argocd-stable.tar.gz && \
  tar -xOzf /tmp/project-3-argocd-stable.tar.gz argo-cd-stable/manifests/install.yaml > "$HOME/.local/share/project-3/argocd-install.yaml" && \
  test -s "$HOME/.local/share/project-3/argocd-install.yaml" && \
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f - && \
kubectl apply -n argocd --server-side --force-conflicts -f "$HOME/.local/share/project-3/argocd-install.yaml" && \
kubectl rollout status deployment/argocd-server -n argocd --timeout=10m && \
kubectl rollout status deployment/argocd-repo-server -n argocd --timeout=10m && \
kubectl rollout status statefulset/argocd-application-controller -n argocd --timeout=10m && \
cd /home/estudiante/mlops-course-repo && \
python3 project_3/scripts/apply-argocd-login.py
```

## 11. Local API, Streamlit and autoscaling — NBAM07

```bash
cd /home/estudiante/mlops-course-repo && \
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml" && \
sed -e 's|image: docker.io/.*/project-3-property-api:.*|image: project-3-property-api:local-test|' -e 's|imagePullPolicy: Always|imagePullPolicy: IfNotPresent|' project_3/k8s/api/api.yaml | kubectl apply -f -
```

```bash
sed 's|image: docker.io/.*/project-3-property-ui:.*|image: project-3-property-ui:local-test|' project_3/k8s/streamlit/streamlit.yaml | kubectl apply -f - && \
kubectl apply -f project_3/k8s/api/hpa.yaml
```

## 12. Local status — NBAM07

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl rollout status deployment/property-api -n project-3 --timeout=10m
kubectl rollout status deployment/property-ui -n project-3 --timeout=10m
kubectl rollout status deployment/prometheus -n project-3 --timeout=10m
kubectl rollout status deployment/grafana -n project-3 --timeout=10m
kubectl rollout status deployment/locust -n project-3 --timeout=10m
kubectl rollout status deployment/jupyter -n project-3 --timeout=20m
```  
 
```bash
kubectl get pods,pvc,svc,hpa -n project-3 -o wide
kubectl top nodes
```

## 13. Service access and first pipeline run — NBAM07

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
```

```bash
cd /home/estudiante/mlops-course-repo
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

The Locust load test runs on a local computer outside the cluster nodes. The tester downloads the entire `project_3/locust` folder, opens it locally, and follows the [Locust setup and run instructions](locust/README.md) after verifying a prediction.

```bash
kubectl get hpa -n project-3 -w
```

## 14. Publish the tested changes — NBAM07

Create a branch for the local changes, stage Project 3 including the evidence, and review the staged files. If a branch already exists, use that branch and skip `git switch -c`.

```bash
cd /home/estudiante/mlops-course-repo
git switch -c project-3-clean-install
git add -A -- project_3 .github/workflows/project-3-ci.yml
git diff --cached --stat
```

Check that `project_3/evidence/` is staged and that screenshots and terminal logs contain no credentials. Then commit and push.

```bash
git commit -m "Prepare Project 3 for deployment and add evidence" &&
git push -u origin HEAD
```

Open the PR to `main` on GitHub. Wait for the tests and image publishing to pass before merging. After the PR is merged, update the checkout used by Airflow and delete the local branch.

```bash
git switch main &&
git pull --ff-only origin main &&
git branch -d project-3-clean-install &&
git status --short --branch
```

## 15. Enable Argo CD sync — NBAM07

After pulling the merged `main`, register the API application. Argo CD automatically syncs the API Deployment, Service, and HPA from `main`. Manage the remaining workloads with the local deployment commands in steps 8, 9, and 11. After publishing a Streamlit change, apply its versioned manifest from the updated checkout.

```bash
cd /home/estudiante/mlops-course-repo &&
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml" &&
kubectl apply -f project_3/argocd/api.yaml
```

Open the Argo CD UI from step 13 and check that `project-3-api` becomes `Synced` and `Healthy`. Verify that it uses the published image and repeat the prediction check from step 13.

### Verify autosync and collect evidence

For the autosync demo, change the API Deployment CPU request in `project_3/k8s/api/api.yaml` through a second PR. The HPA uses this request when calculating CPU utilization. After merging, check the revision in Argo CD under **History and Rollback** and verify the rollout on NBAM07.

```bash
kubectl rollout status deployment/property-api -n project-3 --timeout=10m
kubectl get deployment property-api -n project-3 -o jsonpath='{.spec.template.spec.containers[0].resources.requests.cpu}{"\n"}'
```

Run these checks after the first model is promoted. Use Jupyter notebook 09 for PostgreSQL evidence.

```bash
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml"
kubectl get nodes -o wide
kubectl get deploy,sts,pods,jobs,pvc,svc,hpa -n project-3 -o wide
kubectl get pv
kubectl get events -n project-3 --sort-by=.metadata.creationTimestamp
kubectl get applications,pods -n argocd
kubectl get deploy property-api property-ui -n project-3 -o custom-columns=NAME:.metadata.name,IMAGE:.spec.template.spec.containers[0].image
kubectl top pods -n project-3 --containers
kubectl logs -n project-3 deployment/property-api --tail=30
```

## Maintenance after installation — NBAM07

Airflow mounts the checkout on NBAM07. After updating training code, reapply the Secrets from the same checkout and restart the scheduler before triggering another batch so the run logs the new commit.

```bash
cd /home/estudiante/mlops-course-repo && \
export KUBECONFIG="$HOME/.kube/project-3-k3s.yaml" && \
kubectl get statefulset/airflow-scheduler -n project-3 && \
bash project_3/scripts/apply-secrets.sh && \
kubectl rollout restart statefulset/airflow-scheduler -n project-3 && \
kubectl rollout status statefulset/airflow-scheduler -n project-3 --timeout=20m
```

## 16. Full cluster cleanup — NBAM19

**This deletes the K3s worker and its local persistent volumes.**

```bash
(
  set -euo pipefail
  [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" = nbam19 ]
  for PROJECT3_MOUNT in /mnt/project3-image /mnt/project3-nfs-check; do
    if mountpoint -q "$PROJECT3_MOUNT"; then sudo umount "$PROJECT3_MOUNT"; fi
  done
  sudo rmdir /mnt/project3-image /mnt/project3-nfs-check 2>/dev/null || true
  if [ -x /usr/local/bin/k3s-agent-uninstall.sh ]; then sudo /usr/local/bin/k3s-agent-uninstall.sh; fi
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
)
```

## 17. Full cluster cleanup — NBAM07

**This deletes the K3s cluster and its local persistent volumes.**

```bash
(
  set -euo pipefail
  [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" = nbam07 ]
  if [ -x /usr/local/bin/k3s-uninstall.sh ]; then sudo /usr/local/bin/k3s-uninstall.sh; fi
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
  rm -f "$HOME/.local/share/project-3/argocd-install.yaml"
  rmdir "$HOME/.local/share/project-3" 2>/dev/null || true
  rm -f "$HOME/.kube/project-3-k3s.yaml" /tmp/project-3-argocd-stable.tar.gz
  rm -f /home/estudiante/mlops-course-repo/project_3/data/{project-3-test-images.tar,project-3-property-api-local.tar}
) && unset KUBECONFIG
```

## 18. Optional Docker cleanup and disk check — NBAM19 and NBAM07

Run this on each node after K3s cleanup if you want to clear its local Docker daemon. It removes **all** Docker containers on that node, including running containers, then prunes images, unused networks, volumes, and build cache. Save any Docker data needed by other projects first.

```bash
(
  set -euo pipefail
  if command -v docker >/dev/null 2>&1 && [ -S /var/run/docker.sock ]; then
    project3_docker=(sudo docker --host unix:///var/run/docker.sock)
    "${project3_docker[@]}" ps -aq | xargs -r "${project3_docker[@]}" rm -f
    "${project3_docker[@]}" system prune --all --force
    "${project3_docker[@]}" volume prune --all --force
    "${project3_docker[@]}" system df
  fi
  df -h / /var /tmp
)
```

To check disk space without removing anything:

```bash
df -h / /var /tmp
```
