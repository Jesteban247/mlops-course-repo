"""Record data-driven train-or-skip decisions."""
import json
import logging

import numpy as np
import pandas as pd
from sqlalchemy import text

from property_ml.data import _frame
from property_ml.decisions import decide, psi
from property_ml.settings import GROUP, engine

logger = logging.getLogger(__name__)


def decide_batch(batch, run_id):
    db = engine()
    try:
        with db.connect() as conn:
            last = conn.execute(text('SELECT max(batch_number) FROM audit.training_events WHERE group_number=:g'), {'g': GROUP}).scalar()
            valid = conn.execute(text('SELECT count(*) FROM clean.properties WHERE group_number=:g AND batch_number=:b'), {'g':GROUP, 'b':batch}).scalar_one()
            counts = conn.execute(text('''SELECT coalesce(sum(row_count),0), coalesce(sum(row_count - coalesce(duplicate_rows,0)),0)
                FROM raw.batches WHERE group_number=:g AND status='cleaned' AND (:last IS NULL OR batch_number>:last) AND batch_number<=:b'''), {'g':GROUP,'last':last,'b':batch}).one()
            total, novel = map(int, counts)
        pending = _frame(db, after=last, through=batch)
        previous = _frame(db, through=last) if last is not None else pd.DataFrame()
        drift = {}
        categories = {}
        new_category_examples = {}
        if not previous.empty and not pending.empty:
            reference = previous.sample(min(len(previous), 50000), random_state=42)
            recent = pending.sample(min(len(pending), 50000), random_state=42)
            for col in ['bed', 'bath', 'acre_lot', 'house_size']:
                drift[col] = psi(reference[col], recent[col], discrete=col in ('bed', 'bath'))
            for col in ['city', 'state', 'status', 'zip_code', 'brokered_by', 'street']:
                values = pending[col].dropna().astype(str)
                unknown = values[~values.isin(set(previous[col].dropna().astype(str)))]
                categories[col] = float(len(unknown) / len(values)) if len(values) else 0.0
                distinct = sorted(unknown.unique())
                new_category_examples[col] = {'distinct': len(distinct), 'examples': distinct[:20]}
        decision_categories = {key: categories[key] for key in ('city', 'state', 'status') if key in categories}
        decision, reason = decide(len(previous), len(pending), len(pending) / max(novel, 1), drift, decision_categories, new_fraction=novel / max(total, 1))
        metrics = {'pending_total': total, 'pending_novel': novel, 'trained_rows': len(previous),
                   'contribution': len(pending) / len(previous) if len(previous) else None,
                   'valid_fraction': len(pending) / max(novel, 1), 'new_fraction': novel / max(total, 1),
                   'psi': {k: float(v) if np.isfinite(v) else None for k,v in drift.items()}, 'new_category_fractions': categories, 'new_categories': new_category_examples}
        from property_ml.reports import inspect_schema, save_report
        metrics['schema'] = inspect_schema(db, batch)
        historical = pd.concat([previous, pending[pending['batch_number'] < batch]], ignore_index=True)
        current = pending[pending['batch_number'] == batch]
        report_key = save_report(batch, run_id, decision, reason, metrics, historical, current)
        with db.begin() as conn:
            conn.execute(text('''INSERT INTO audit.batch_decisions(group_number,batch_number,valid_rows,pending_rows,decision,reason,run_id,metrics,report_key)
                VALUES(:g,:b,:v,:p,:d,:r,:run,CAST(:metrics AS jsonb),:report_key) ON CONFLICT(group_number,batch_number) DO UPDATE SET
                valid_rows=excluded.valid_rows,pending_rows=excluded.pending_rows,decision=excluded.decision,reason=excluded.reason,run_id=excluded.run_id,metrics=excluded.metrics,report_key=excluded.report_key'''),
                {'g':GROUP,'b':batch,'v':valid,'p':len(pending),'d':decision,'r':reason,'run':run_id,'metrics':json.dumps(metrics), 'report_key':report_key})
        logger.info("Group %s batch %s: %s (%s), report=%s", GROUP, batch, decision, reason, report_key)
        return decision
    finally:
        db.dispose()
