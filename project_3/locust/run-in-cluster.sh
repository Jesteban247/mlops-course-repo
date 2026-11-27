#!/usr/bin/env bash
set -euo pipefail

locust_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/project-3-k3s.yaml}"
kube=(kubectl -n project-3)

if (( $# == 0 )); then
  echo 'Usage: bash run-in-cluster.sh --users 20 [--spawn-rate 2] [--duration 120]' >&2
  exit 2
fi

pod="$("${kube[@]}" get pods -l app=locust --field-selector status.phase=Running \
  -o jsonpath='{.items[0].metadata.name}')"
"${kube[@]}" wait --for=condition=Ready "pod/$pod" --timeout=30s

run_dir="$("${kube[@]}" exec "$pod" -- mktemp -d /tmp/locust-run.XXXXXX)"
for file in run.py locustfile.py; do
  "${kube[@]}" exec -i "$pod" -- sh -c 'cat > "$1"' sh "$run_dir/$file" < "$locust_dir/$file"
done

status=0
"${kube[@]}" exec "$pod" -- python "$run_dir/run.py" --replicas auto "$@" \
  --host http://property-api:8000 || status=$?

if "${kube[@]}" exec "$pod" -- test -d "$run_dir/results"; then
  mkdir -p "$locust_dir/results"
  results="$(mktemp -d "$locust_dir/results/run.XXXXXX")"
  if ! "${kube[@]}" exec "$pod" -- tar -C "$run_dir/results" -cf - . | tar -xf - -C "$results"; then
    echo "Could not copy results. They are still in $pod:$run_dir/results" >&2
    exit 1
  fi
  printf 'Results saved in %s\n' "$results"
fi

"${kube[@]}" exec "$pod" -- rm -rf -- "$run_dir"
exit "$status"
