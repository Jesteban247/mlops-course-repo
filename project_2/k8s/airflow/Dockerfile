# Developer image: build/push to a registry for final Kubernetes deliverable.
FROM apache/airflow:3.2.2
COPY k8s/airflow/requirements.txt /tmp/diabetes-requirements.txt
RUN pip install --no-cache-dir 'apache-airflow==3.2.2' -r /tmp/diabetes-requirements.txt \
    && pip check
