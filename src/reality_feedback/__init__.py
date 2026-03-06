"""
Reality Feedback Engine — validates predictions against actual outcomes.

Records: predicted vs actual. Calculates error. Adjusts model parameters.
Creates learning feedback loop.
"""

from .engine import record_prediction, record_outcome, get_prediction_errors

__all__ = ["record_prediction", "record_outcome", "get_prediction_errors"]
