# NYSE Simulation — Operational Excellence

**Zero-error handling. Vast predictability. Deterministic market simulation.**

---

## Overview

The NYSE simulation plugs into the Universal Flow Interface as `nyse_sim`. It provides:

- **Deterministic prices** — Seed-based, reproducible. Same seed → same prices.
- **Zero-error design** — Every code path returns a predictable dict. No unhandled exceptions.
- **Vast predictability** — Moving averages, volatility bounds, Sharpe ratio, predictability score.

---

## API

Invoke via flow:

```
POST /api/flows/nyse_sim/invoke
```

### Request Body

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `action` | string | `quote` | `quote` \| `ohlcv` \| `optimize` \| `predict` |
| `symbols` | list | `["AAPL","MSFT","GOOGL","JPM","V"]` | Ticker symbols |
| `seed` | int | 42 | Deterministic seed |
| `days` | int | 30 | Simulation horizon |
| `base_price` | float | 100 | Base price |
| `volatility` | float | 0.02 | Volatility factor |
| `trend` | float | 0.0001 | Drift per day |

### Actions

- **quote** — Current simulated price, change %, volume per symbol
- **ohlcv** — OHLCV bars for each symbol over `days`
- **optimize** — Sharpe ratio, volatility, predictability score, zero_error flag
- **predict** — Forward price predictions (deterministic)

---

## Example

```json
{
  "action": "optimize",
  "symbols": ["AAPL", "MSFT"],
  "seed": 42,
  "days": 30
}
```

Response includes `optimization.predictability_score` and `optimization.zero_error: true`.

---

## UI

Navigate to `/ui/nyse` for the interactive simulation dashboard.
