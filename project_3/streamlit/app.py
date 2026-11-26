import json
import logging
import os
from pathlib import Path

import boto3
import pandas as pd
import requests
import streamlit as st
from sqlalchemy import URL, create_engine, text

st.set_page_config(page_title='Property prices', layout='wide')
st.title('Property prices')
logger = logging.getLogger(__name__)
api = os.getenv('API_URL', 'http://property-api:8000')


@st.cache_resource
def database():
    return create_engine(URL.create('postgresql+psycopg2', username=os.environ['APP_DB_USER'],
        password=os.environ['APP_DB_PASSWORD'], host=os.getenv('APP_DB_HOST', 'property-postgres'),
        database=os.environ['APP_DB_NAME'], port=5432), pool_pre_ping=True)


@st.cache_resource
def storage():
    return boto3.client('s3', endpoint_url=os.getenv('MLFLOW_S3_ENDPOINT_URL', 'http://minio:9000'),
                        region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))


def show_history():
    try:
        query = text('''SELECT b.batch_number,b.received_at,b.row_count,b.valid_rows,b.rejected_rows,
          b.duplicate_rows,d.decision,d.reason,d.promotion,d.candidate_mae,d.champion_mae,
          d.model_version,d.run_id,d.metrics,d.report_key,t.mlflow_run_id,t.promoted,(to_jsonb(t)->>'train_rows')::int AS train_rows
          FROM raw.batches b LEFT JOIN audit.batch_decisions d USING(group_number,batch_number)
          LEFT JOIN audit.training_events t USING(group_number,batch_number)
          WHERE b.group_number=:g ORDER BY b.batch_number DESC''')
        with database().connect() as connection:
            group = {'g': int(os.getenv('DATA_API_GROUP', '4'))}
            rows = pd.read_sql_query(query, connection, params=group)
            clean_count = connection.execute(text(
                'SELECT count(*) FROM clean.properties WHERE group_number=:g'), group).scalar_one()
        if rows.empty:
            st.info('No batches have been processed yet.')
        else:
            promoted = rows.loc[rows['promoted'].eq(True)]
            champion = promoted.iloc[0] if not promoted.empty else None
            totals = st.columns(4)
            totals[0].metric('Raw rows received', f"{rows['row_count'].sum():,}")
            totals[1].metric('Clean rows available', f'{clean_count:,}')
            totals[2].metric('Last promoted version', champion['model_version'] if champion is not None else '—')
            train_rows = champion['train_rows'] if champion is not None else None
            share = f'{train_rows / clean_count:.1%}' if clean_count and pd.notna(train_rows) else '—'
            totals[3].metric('Clean rows used to fit it', share)
            if pd.notna(train_rows):
                st.caption(f'{int(train_rows):,} training rows divided by {clean_count:,} current clean rows.')
            elif champion is not None:
                st.caption('The training row count was unavailable for this earlier run.')

            number = st.selectbox('Inspect a batch', rows['batch_number'].tolist())
            row = rows.loc[rows['batch_number'] == number].iloc[0]
            decision = {'train': 'Train candidate', 'skip': 'Skip training'}.get(row['decision'], 'Awaiting decision')
            st.subheader(decision)
            if pd.notna(row['reason']):
                st.write(row['reason'])
            if pd.notna(row['promoted']):
                outcome = 'Promoted' if row['promoted'] else 'Rejected'
                st.write(f"**{outcome}** · {row['promotion']}")
            if pd.notna(row['candidate_mae']):
                candidate, previous = st.columns(2)
                delta = (f"{row['candidate_mae'] - row['champion_mae']:+,.2f}"
                         if pd.notna(row['champion_mae']) else None)
                candidate.metric('Candidate validation MAE', f"{row['candidate_mae']:,.2f}",
                                 delta=delta, delta_color='inverse')
                if pd.notna(row['champion_mae']):
                    previous.metric('Previous champion validation MAE', f"{row['champion_mae']:,.2f}")
            if pd.notna(row['mlflow_run_id']):
                st.caption('MLflow run · ' + str(row['mlflow_run_id']))
            with st.expander('Batch history table'):
                st.dataframe(rows[['batch_number', 'row_count', 'valid_rows', 'decision', 'reason',
                                   'promotion', 'model_version']], hide_index=True, width='stretch')
            if isinstance(row['metrics'], dict):
                with st.expander('Data quality and drift metrics'):
                    st.json(row['metrics'])
            if isinstance(row['report_key'], str) and row['report_key']:
                try:
                    report = json.loads(storage().get_object(Bucket='project-3-batch-reports', Key=row['report_key'])['Body'].read())
                    for key in report.get('plots', []):
                        st.image(storage().get_object(Bucket='project-3-batch-reports', Key=key)['Body'].read(), caption=Path(key).stem)
                except Exception as exc:
                    st.warning(f'Batch report unavailable: {exc}')
            else:
                st.info('No report is available for this batch yet.')
    except Exception:
        logger.exception('Could not query batch history')
        st.warning('Batch history is unavailable. Check the application logs.')


prediction_tab, history_tab = st.tabs(['Prediction', 'Batch history'])
with prediction_tab:
    try:
        health = requests.get(api + '/ready', timeout=5)
        if health.status_code == 503:
            st.warning('The API is waiting for a model.')
        else:
            health.raise_for_status()
            version = health.json().get('version')
            if version is None:
                st.warning('The API is running and waiting for a champion model.')
            else:
                st.caption(f'API ready · model version {version}')
    except (requests.RequestException, ValueError):
        st.warning('The API is unavailable.')

    with st.form('prediction'):
        rooms, size, location = st.columns(3)
        payload = {
            'bed': rooms.number_input('Bedrooms', min_value=0, value=3),
            'bath': rooms.number_input('Bathrooms', min_value=0.0, value=2.0),
            'brokered_by': rooms.text_input('Broker', value='33714'),
            'acre_lot': size.number_input('Lot size (acres)', min_value=0.0, value=0.23),
            'house_size': size.number_input('House size (sq ft)', min_value=1, value=1837),
            'street': size.text_input('Street code', value='1758218'),
            'city': location.text_input('City', value='East Windsor'),
            'state': location.text_input('State', value='Connecticut'),
            'zip_code': location.text_input('ZIP code', value='6016'),
        }
        submitted = st.form_submit_button('Predict')

    if submitted:
        try:
            response = requests.post(api + '/predict', json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            st.metric('Predicted price', f"${result['prediction']:,.2f}")
            st.caption(f"Model {result['model_version']} · pod {result['pod']}")
        except (requests.RequestException, ValueError, KeyError):
            logger.exception('Prediction failed')
            st.error('Prediction failed. Check the API status and application logs.')

with history_tab:
    show_history()
