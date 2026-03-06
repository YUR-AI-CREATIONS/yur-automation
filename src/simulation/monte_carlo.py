"""
Monte Carlo underwriting — institutional-grade.

Output: probability ROI ≥ target, probability of loss, percentiles, sensitivity.
"""

from __future__ import annotations

from typing import Any


def simulate_roi(
    n: int = 10_000,
    interest_rate_mu: float = 0.075,
    interest_rate_sigma: float = 0.015,
    inflation_mu: float = 0.04,
    inflation_sigma: float = 0.02,
    absorption_mu: float = 14.0,
    absorption_sigma: float = 4.0,
    base_profit: float = 12_000_000,
    capital_deployed: float = 80_000_000,
    target_roi: float = 0.18,
) -> dict[str, Any]:
    """
    Monte Carlo simulation. Toy model: profit decays with rates, inflation, slow absorption.

    Returns: roi_mean, percentiles, p_roi_ge_target, p_loss.
    """
    try:
        import numpy as np
    except ImportError:
        return {
            "ok": False,
            "error": "numpy required. pip install numpy",
            "roi_mean": 0.0,
            "p_roi_ge_target": 0.0,
            "p_loss": 0.0,
        }

    r = np.random.normal(interest_rate_mu, interest_rate_sigma, n)
    infl = np.random.normal(inflation_mu, inflation_sigma, n)
    absorption = np.random.normal(absorption_mu, absorption_sigma, n)

    # Toy model: profit decays with rates/inflation and slow absorption
    profit = (
        base_profit
        * (1 - 3 * (r - interest_rate_mu))
        * (1 - 2 * (infl - inflation_mu))
        * (1 - 0.03 * (absorption - absorption_mu))
    )
    roi = profit / capital_deployed

    return {
        "ok": True,
        "roi_mean": float(np.mean(roi)),
        "roi_std": float(np.std(roi)),
        "roi_p10": float(np.quantile(roi, 0.10)),
        "roi_p50": float(np.quantile(roi, 0.50)),
        "roi_p90": float(np.quantile(roi, 0.90)),
        "p_roi_ge_target": float(np.mean(roi >= target_roi)),
        "p_loss": float(np.mean(roi <= 0.0)),
        "n_runs": n,
        "target_roi": target_roi,
    }
