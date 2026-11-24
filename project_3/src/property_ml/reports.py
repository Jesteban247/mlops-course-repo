"""Store one decision report and its distribution plots in MinIO."""
import io
import json
import os

import boto3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from botocore.exceptions import ClientError
from sqlalchemy import text

from property_ml.settings import GROUP
from property_ml.validation import REQUIRED

BUCKET = 'project-3-batch-reports'


def inspect_schema(db, batch):
    query = text('''SELECT batch_number, payload FROM raw.properties
        WHERE group_number=:g AND batch_number IN
          (:b, (SELECT max(batch_number) FROM raw.batches WHERE group_number=:g AND batch_number<:b))
        AND row_number < 1000 ORDER BY batch_number, row_number''')
    observed = {}
    with db.connect() as conn:
        for number, payload in conn.execute(query, {'g': GROUP, 'b': batch}):
            columns = observed.setdefault(number, {})
            for name, value in payload.items():
                kind = 'null' if value is None else type(value).__name__
                columns.setdefault(name, set()).add(kind)
    current = observed.get(batch, {})
    previous_batches = [n for n in observed if n < batch]
    previous = observed[max(previous_batches)] if previous_batches else {}
    return {'sample_rows_per_batch': 1000, 'columns': sorted(current),
            'missing_required': sorted(REQUIRED - current.keys()),
            'new_columns': sorted(current.keys() - previous.keys()) if previous else [],
            'missing_previous': sorted(previous.keys() - current.keys()) if previous else [],
            'type_changes': {key: {'previous': sorted(previous[key] - {'null'}),
                                   'current': sorted(current[key] - {'null'})}
                             for key in current.keys() & previous.keys()
                             if (current[key] - {'null'}) and (previous[key] - {'null'})
                             and (current[key] - {'null'}) != (previous[key] - {'null'})}}


def save_report(batch, run_id, decision, reason, metrics, reference, current):
    client = boto3.client('s3', endpoint_url=os.getenv('MLFLOW_S3_ENDPOINT_URL', 'http://minio:9000'),
                          region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
    try:
        client.head_bucket(Bucket=BUCKET)
    except ClientError as exc:
        if exc.response.get('Error', {}).get('Code') not in ('404', 'NoSuchBucket', 'NotFound'):
            raise
        client.create_bucket(Bucket=BUCKET)
    prefix = f'group-{GROUP}/batch-{batch}'
    plot_keys = []
    for column in ('bed', 'bath', 'acre_lot', 'house_size'):
        fig, ax = plt.subplots(figsize=(7, 4))
        for data, label in ((reference, 'Earlier batches'), (current, 'Current batch')):
            if not data.empty and column in data:
                values = pd.to_numeric(data[column], errors='coerce').dropna()
                if not values.empty:
                    upper = values.quantile(.99)
                    values[values <= upper].hist(ax=ax, bins=30, density=True, alpha=.5, label=label)
        ax.set_title(column + ' (up to each sample’s 99th percentile)')
        ax.legend()
        fig.tight_layout()
        image = io.BytesIO()
        fig.savefig(image, format='png', dpi=110)
        plt.close(fig)
        key = f'{prefix}/{column}.png'
        client.put_object(Bucket=BUCKET, Key=key, Body=image.getvalue(), ContentType='image/png')
        plot_keys.append(key)
    key = f'{prefix}/report.json'
    report = {'group': GROUP, 'batch': batch, 'run_id': run_id, 'decision': decision,
              'reason': reason, 'metrics': metrics, 'plots': plot_keys}
    client.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(report, allow_nan=False).encode(), ContentType='application/json')
    return key
