"""Shared model utilities for training and inference."""


class XGBoostWrapper:
    """Give the XGBoost model the same prediction interface as other models."""

    def __init__(self, pipeline, label_encoder):
        self.pipeline = pipeline
        self.label_encoder = label_encoder

    def predict(self, features):
        """Return predictions using the original string class labels."""
        numeric_predictions = self.pipeline.predict(features)
        return self.label_encoder.inverse_transform(numeric_predictions)
