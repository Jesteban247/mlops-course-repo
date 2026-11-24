import json

import pandas as pd

from property_ml import reports


def test_report_records_decision_and_plots_without_training(monkeypatch):
    class Storage:
        objects = {}

        def head_bucket(self, **kwargs):
            pass

        def put_object(self, Bucket, Key, Body, ContentType):
            self.objects[Key] = (Body, ContentType)

    storage = Storage()
    monkeypatch.setattr(reports.boto3, 'client', lambda *args, **kwargs: storage)
    current = pd.DataFrame({'bed': [2, 3], 'bath': [1, 2], 'acre_lot': [0.2, 0.3], 'house_size': [900, 1200]})
    key = reports.save_report(2, 'run-2', 'skip', 'no change', {'psi': {}}, pd.DataFrame(), current)
    body, content_type = storage.objects[key]
    report = json.loads(body)
    assert content_type == 'application/json'
    assert report['decision'] == 'skip'
    assert report['run_id'] == 'run-2'
    assert len(report['plots']) == 4
    assert all(storage.objects[plot][1] == 'image/png' for plot in report['plots'])
