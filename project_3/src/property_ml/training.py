"""Train, compare, and record candidate models."""
import logging
import os

import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sqlalchemy import text

from property_ml.data import _frame
from property_ml.explain import shap_importance
from property_ml.features import RAW_FEATURES, build_model
from property_ml.settings import GROUP, MODEL_NAME, engine

logger = logging.getLogger(__name__)


def train_candidate(batch):
    db = engine()
    try:
        data = _frame(db, through=batch)
        train = data[data['split'] == 'train']
        validation = data[data['split'] == 'validation']
        test = data[data['split'] == 'test']
        if min(len(train), len(validation), len(test)) < 2:
            raise ValueError('Insufficient independent train, validation, or test rows')
        X_train, X_validation, X_test = (part.reindex(columns=RAW_FEATURES) for part in (train, validation, test))
        mlflow.set_tracking_uri(os.environ['MLFLOW_TRACKING_URI'])
        mlflow.set_experiment('project-3-property-price')
        model = build_model()
        model.fit(X_train, train['price'])
        val_predictions = model.predict(X_validation)
        test_predictions = model.predict(X_test)
        with db.connect() as conn:
            training_reason = conn.execute(text('SELECT reason FROM audit.batch_decisions WHERE group_number=:g AND batch_number=:b'), {'g':GROUP, 'b':batch}).scalar_one()
        with mlflow.start_run(run_name=f'group-{GROUP}-batch-{batch}') as run:
            regressor = model.named_steps['model']
            preprocess = model.named_steps['preprocess']
            numeric = preprocess.named_transformers_['numeric']
            categorical = preprocess.named_transformers_['categorical']
            mlflow.log_params({
                'group': GROUP,
                'batch': batch,
                'algorithm': type(regressor).__name__,
                'split': 'stable property proxy',
                'code_version': os.getenv('CODE_VERSION', 'unknown'),
                'n_estimators': regressor.n_estimators,
                'max_depth': regressor.max_depth,
                'learning_rate': regressor.learning_rate,
                'tree_method': regressor.tree_method,
                'random_state': regressor.random_state,
                'numeric_imputation': numeric.named_steps['impute'].strategy,
                'numeric_scaler': type(numeric.named_steps['scale']).__name__,
                'categorical_encoder': type(categorical).__name__,
                'categorical_handle_unknown': categorical.handle_unknown,
                'categorical_min_frequency': categorical.min_frequency,
                'categorical_max_categories': categorical.max_categories,
            })
            mlflow.log_metrics({'train_mae':float(mean_absolute_error(train['price'], model.predict(X_train))),
                'validation_mae':float(mean_absolute_error(validation['price'], val_predictions)),
                'validation_rmse':float(mean_squared_error(validation['price'], val_predictions)**.5),
                'test_mae':float(mean_absolute_error(test['price'], test_predictions)),
                'test_rmse':float(mean_squared_error(test['price'], test_predictions)**.5),
                'test_r2':float(r2_score(test['price'], test_predictions))})
            mlflow.set_tags({'training_reason':training_reason, 'batch_number':str(batch)})
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            figure, axis = plt.subplots(figsize=(6, 5))
            axis.scatter(validation['price'], val_predictions, alpha=.3, s=8)
            low = min(float(validation['price'].min()), float(val_predictions.min()))
            high = max(float(validation['price'].max()), float(val_predictions.max()))
            axis.plot([low, high], [low, high], 'r--')
            axis.set(xlabel='Actual price', ylabel='Predicted price', title='Validation predictions')
            figure.tight_layout()
            mlflow.log_figure(figure, 'validation_predictions.png')
            plt.close(figure)
            importance = shap_importance(model, X_validation)
            figure, axis = plt.subplots(figsize=(8, 5))
            importance.head(12).sort_values().plot.barh(ax=axis)
            axis.set(xlabel='Mean absolute SHAP value', title='Feature contributions on validation data')
            figure.tight_layout()
            mlflow.log_figure(figure, 'shap_importance.png')
            plt.close(figure)
            mlflow.log_dict(importance.to_dict(), 'shap_importance.json')
            mlflow.log_dict({'group':GROUP, 'through_batch':batch, 'train_rows':len(train),
                'validation_rows':len(validation), 'test_rows':len(test), 'training_reason':training_reason}, 'evaluation.json')
            info = mlflow.sklearn.log_model(model, name='model', serialization_format='cloudpickle',
                signature=infer_signature(X_train.head(5), model.predict(X_train.head(5))))
            version = mlflow.register_model(info.model_uri, MODEL_NAME)
            return {'batch':batch, 'model_version':str(version.version), 'run_id':run.info.run_id, 'train_rows':len(train)}
    finally:
        db.dispose()


def compare_candidate(candidate):
    batch = candidate['batch']
    db = engine()
    try:
        data = _frame(db, through=batch)
        validation = data[data['split'] == 'validation']
        if len(validation) < 2:
            raise ValueError('Insufficient independent validation rows')
        X_validation = validation.reindex(columns=RAW_FEATURES)
        mlflow.set_tracking_uri(os.environ['MLFLOW_TRACKING_URI'])
        client = MlflowClient()
        model = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}/{candidate['model_version']}")
        candidate_mae = float(mean_absolute_error(validation['price'], model.predict(X_validation)))
        # The candidate has already registered the model; an absent alias means baseline.
        champion_version = client.get_registered_model(MODEL_NAME).aliases.get('champion')
        champion_mae = None
        if champion_version is not None:
            champion = mlflow.sklearn.load_model(f'models:/{MODEL_NAME}/{champion_version}')
            champion_mae = float(mean_absolute_error(validation['price'], champion.predict(X_validation)))
        from property_ml.decisions import promotion_decision
        promote, reason = promotion_decision(candidate_mae, champion_mae)
        if champion_mae is not None:
            client.log_metric(candidate['run_id'], 'champion_validation_mae', champion_mae)
        return {**candidate, 'candidate_mae':candidate_mae, 'champion_mae':champion_mae,
                'champion_version':str(champion_version) if champion_version is not None else None,
                'promoted':promote, 'reason':reason}
    finally:
        db.dispose()


def record_model_decision(result):
    mlflow.set_tracking_uri(os.environ['MLFLOW_TRACKING_URI'])
    client = MlflowClient()
    if result['promoted']:
        client.set_registered_model_alias(MODEL_NAME, 'champion', result['model_version'])
    client.set_tag(result['run_id'], 'promotion_decision', result['reason'])
    db = engine()
    try:
        with db.begin() as conn:
            params = {'g':GROUP,'b':result['batch'],'r':result['run_id'],'v':result['model_version'],
                      'c':result['candidate_mae'],'old':result['champion_mae'],
                      'promote':result['promoted'],'reason':result['reason'], 'train_rows':result.get('train_rows')}
            conn.execute(text("""INSERT INTO audit.training_events(group_number,batch_number,mlflow_run_id,model_version,candidate_mae,champion_mae,promoted,reason,train_rows)
                VALUES(:g,:b,:r,:v,:c,:old,:promote,:reason,:train_rows) ON CONFLICT(group_number,batch_number) DO UPDATE SET
                mlflow_run_id=excluded.mlflow_run_id,model_version=excluded.model_version,candidate_mae=excluded.candidate_mae,
                champion_mae=excluded.champion_mae,promoted=excluded.promoted,reason=excluded.reason,train_rows=excluded.train_rows"""), params)
            conn.execute(text("""UPDATE audit.batch_decisions SET model_version=:v,candidate_mae=:c,champion_mae=:old,promotion=:reason
                WHERE group_number=:g AND batch_number=:b"""), params)
        logger.info(
            'Group %s batch %s: %s model %s, candidate MAE=%s, previous champion MAE=%s',
            GROUP, result['batch'], 'promoted' if result['promoted'] else 'rejected',
            result['model_version'], result['candidate_mae'], result['champion_mae'],
        )
        return result
    finally:
        db.dispose()
