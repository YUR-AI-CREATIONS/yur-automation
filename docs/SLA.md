# FranklinOps / Trinity Spine — SLA & SLO Definitions

**Enterprise service level objectives and indicators.**

---

## SLO Definitions

| SLO | Target | Measurement |
|-----|--------|-------------|
| **Availability** | 99.9% | Uptime (excludes planned maintenance) |
| **Latency p50** | < 200ms | API response time (healthz, config, audit list) |
| **Latency p99** | < 2s | API response time |
| **Error rate** | < 0.1% | 5xx responses / total requests |
| **Recovery time** | < 5 min | Ouroboros self-healing detection + recovery |

---

## SLI Metrics (Prometheus)

```
# Availability
trinity_requests_total{status=~"2.."}
trinity_requests_total{status=~"5.."}

# Latency
trinity_request_duration_seconds_bucket
trinity_request_duration_seconds_count

# Healing
trinity_ouroboros_healing_attempts_total
trinity_ouroboros_healing_success_total
trinity_ouroboros_healing_duration_seconds
```

---

## Breach Alerting

- **Availability breach**: < 99.9% over 30-day window → page on-call
- **Error rate spike**: > 1% over 5 min → alert
- **Repeated healing failures**: > 3 in 1 hour → escalate

---

## Credits

- Planned maintenance (announced 48h ahead): excluded from availability
- Force majeure: excluded per contract
