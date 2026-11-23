"""Fetch, validate, and store each incoming batch."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import requests
from psycopg2.extras import Json, execute_values
from sqlalchemy import text

from property_ml.features import RAW_FEATURES
from property_ml.settings import GROUP, engine
from property_ml.splitting import split_for_property as _split
from property_ml.validation import NUMERIC, CATEGORICAL, validate, possible_extreme


def initialize():
    sql = Path(os.getenv('SCHEMA_PATH', '/opt/airflow/sql/01_schema.sql')).read_text()
    db = engine()
    try:
        with db.begin() as conn:
            conn.exec_driver_sql(sql)
    finally:
        db.dispose()


def fetch_and_store(run_id):
    db = engine()
    try:
        with db.connect() as conn:
            existing = conn.execute(text('SELECT batch_number FROM raw.batches WHERE run_id=:run'), {'run': run_id}).scalar()
        if existing is not None:
            return int(existing)
        url = os.environ['DATA_API_URL'].rstrip('/') + '/data'
        stage_dir = Path(os.getenv('DATA_STAGING_DIR', '/opt/airflow/data/ingestion'))
        stage_dir.mkdir(parents=True, exist_ok=True)
        run_key = hashlib.sha256(run_id.encode()).hexdigest()[:20]
        staged = stage_dir / f'group-{GROUP}-{run_key}.json'
        partial = staged.with_suffix('.partial')
        # A saved response is reused after a DB failure; never retry an incomplete fetch automatically.
        if not staged.exists():
            if partial.exists():
                raise RuntimeError(f'Incomplete fetch at {partial}; inspect the source before retrying')
            with partial.open('xb') as tmp:
                with requests.get(url, params={'group_number': GROUP}, stream=True, timeout=(10, 180)) as response:
                    response.raise_for_status()
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            tmp.write(chunk)
                tmp.flush()
                os.fsync(tmp.fileno())
            partial.replace(staged)
        with staged.open('rb') as tmp:
            payload = json.load(tmp)
        batch = payload.get('batch_number')
        items = payload.get('data')
        if payload.get('group_number') != GROUP or not isinstance(batch, int) or not isinstance(items, list) or not items:
            raise ValueError('Unexpected or empty data API response; inspect the source before retrying')
        connection = db.raw_connection()
        try:
            with connection.cursor() as cur:
                cur.execute('INSERT INTO raw.batches (group_number,batch_number,run_id,row_count,received_columns) VALUES (%s,%s,%s,%s,%s)',
                            (GROUP, batch, run_id, len(items), Json(sorted(items[0].keys()) if isinstance(items[0], dict) else [])))
                for start in range(0, len(items), 2000):
                    values = [(GROUP, batch, i, Json(item)) for i, item in enumerate(items[start:start+2000], start)]
                    execute_values(cur, 'INSERT INTO raw.properties (group_number,batch_number,row_number,payload) VALUES %s', values)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return batch
    finally:
        db.dispose()


def clean_batch(batch):
    db = engine()
    connection = db.raw_connection()
    valid = rejected = duplicates = 0
    quality = {'missing': {k: 0 for k in NUMERIC + CATEGORICAL}, 'reasons': {}, 'possible_extreme_rows': 0}
    try:
        with connection.cursor() as check:
            check.execute('SELECT status FROM raw.batches WHERE group_number=%s AND batch_number=%s', (GROUP, batch))
            status = check.fetchone()
            if status and status[0] == 'cleaned':
                return batch
        with connection.cursor(name='property_raw_cursor') as reader:
            reader.itersize = 2000
            reader.execute('SELECT id,payload FROM raw.properties WHERE group_number=%s AND batch_number=%s ORDER BY id', (GROUP, batch))
            with connection.cursor() as writer:
                while True:
                    rows = reader.fetchmany(2000)
                    if not rows:
                        break
                    values = []
                    for row_id, item in rows:
                        try:
                            if isinstance(item, dict):
                                for field in quality['missing']:
                                    if item.get(field) is None:
                                        quality['missing'][field] += 1
                            is_valid, why = validate(item)
                            if not is_valid:
                                quality['reasons'][why] = quality['reasons'].get(why, 0) + 1
                                rejected += 1
                                continue
                            price = float(item['price'])
                            if possible_extreme(item):
                                quality['possible_extreme_rows'] += 1
                            # Duplicate only exact rows; changed prices remain new.
                            content_hash = hashlib.sha256(json.dumps(item, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
                            key, split = _split(item, row_id)
                            values.append((row_id, GROUP, batch, key, split, price, content_hash, Json({k:item.get(k) for k in RAW_FEATURES + ['status']})))
                        except (TypeError, ValueError):
                            rejected += 1
                            quality['reasons']['serialization'] = quality['reasons'].get('serialization', 0) + 1
                    if values:
                        inserted = execute_values(writer, '''INSERT INTO clean.properties
                            (raw_id,group_number,batch_number,property_key,split,price,content_hash,features)
                            VALUES %s ON CONFLICT DO NOTHING RETURNING raw_id''', values, fetch=True)
                        valid += len(inserted)
                        duplicates += len(values) - len(inserted)
                writer.execute("UPDATE raw.batches SET status='cleaned',valid_rows=%s,rejected_rows=%s,duplicate_rows=%s,quality=%s WHERE group_number=%s AND batch_number=%s", (valid,rejected,duplicates,Json(quality),GROUP,batch))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
        db.dispose()
    print(f'Batch {batch}: valid={valid}, rejected={rejected}, exact duplicates={duplicates}')
    return batch
