"""
Simulation Engine — Monte Carlo underwriting.

Not "ROI = 22%". Probability ROI ≥ target, probability of loss, VaR, sensitivity.
"""

from .monte_carlo import simulate_roi

__all__ = ["simulate_roi"]
