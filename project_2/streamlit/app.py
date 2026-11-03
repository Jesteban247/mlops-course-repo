import json
import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

API_URL = os.environ.get('API_URL', 'http://diabetes-api-scaled.mlops-project.svc.cluster.local:8000').rstrip('/')
EXAMPLES = json.loads((Path(__file__).parent / 'examples.json').read_text())

st.set_page_config(page_title='Diabetes readmission', page_icon='🩺', layout='wide')
st.title('Diabetes readmission')
st.caption('Explore an example and request a prediction from the current champion model.')
st.info('For project demonstration only. This prediction is not medical advice.')

name = st.selectbox('Choose an example patient', list(EXAMPLES))
example = EXAMPLES[name]
st.caption('Edit any value below before sending the request. “?” means unknown.')

with st.form('prediction'):
    fields = pd.DataFrame({'Feature': list(example), 'Value': list(example.values())})
    edited = st.data_editor(fields, hide_index=True, disabled=['Feature'], width='stretch', height=420, key=f'fields-{name}')
    submitted = st.form_submit_button('Predict readmission', type='primary')

if submitted:
    record = dict(zip(edited['Feature'], edited['Value']))
    try:
        response = requests.post(f'{API_URL}/predict', json={'instances': [record]}, timeout=60)
        if not response.ok:
            try:
                detail = response.json().get('detail', response.text)
            except ValueError:
                detail = response.text
            st.error(f'API error ({response.status_code}): {detail}')
        else:
            result = response.json()
            prediction = result['predictions'][0]
            probability = prediction['probability_readmitted_within_30_days']
            st.subheader('Prediction')
            label = 'Predicted readmission within 30 days' if prediction['prediction'] == 1 else 'Predicted no readmission within 30 days'
            st.success(label)
            st.metric('Probability of readmission within 30 days', f'{probability:.1%}')
            st.caption(f"Model: {result['model_name']} · Version: {result['model_version']} · API pod: {result['instance']}")
    except requests.RequestException:
        st.error('The prediction API is unavailable. Check that it is ready and try again.')
    except (KeyError, IndexError, TypeError, ValueError):
        st.error('The API returned an unexpected response. Please try again.')
