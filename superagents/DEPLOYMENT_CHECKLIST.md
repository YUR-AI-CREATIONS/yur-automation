# Trinity Spine — Deployment Checklist

**Complete setup and activation guide for Roosevelt Franklin OS operational backbone**

---

## PHASE 1: LOCAL DEVELOPMENT (Week 1)

### Environment Setup
- [ ] Clone/navigate to `F:\New folder\cognitive_engine`
- [ ] Copy `.env.example` to `.env`
- [ ] Set `SUPABASE_URL` (https://your-project.supabase.co)
- [ ] Set `SUPABASE_SERVICE_KEY` (from Supabase dashboard)
- [ ] Set `STRIPE_SECRET_KEY` (sk_...)
- [ ] Set `STRIPE_WEBHOOK_SECRET` (whsec_...)
- [ ] Generate random 32-byte `TRINITY_API_KEY`
- [ ] Generate random 32-byte `TRINITY_SIGNING_SECRET`

### Dependencies
- [ ] Python 3.11+ installed
- [ ] Docker & Docker Compose v2.20+
- [ ] `pip install -r requirements.txt`
- [ ] Verify liboqs-python installation (for PQC)
  ```bash
  python -c "import liboqs; print('liboqs OK')"
  ```

### Docker Compose Stack
- [ ] Build images: `docker-compose build`
- [ ] Start services: `docker-compose up -d`
- [ ] Wait 30s for services to initialize
- [ ] Check Trinity health: `curl http://localhost:8000/health`
- [ ] Expected: `{"status": "healthy", "pqc_enabled": true}`

### Service Verification
- [ ] Trinity API (8000): curl http://localhost:8000/health
- [ ] Governance Sidecar (8001): curl http://localhost:8001/health
- [ ] PostgreSQL (5432): ping from host
- [ ] Redis (6379): redis-cli -p 6379 ping
- [ ] Prometheus (9091): http://localhost:9091
- [ ] Grafana (3000): http://localhost:3000

### Core Modules
- [ ] Verify `src/core/autonomy_gate.py` exists (250 lines)
- [ ] Verify `src/core/quantum_royalty.py` exists (300 lines)
- [ ] Verify `src/core/ouroboros_spine.py` exists (400 lines)
- [ ] Verify `src/core/system_spawner.py` exists (TBD)

---

## PHASE 2: TESTING & VALIDATION (Week 2)

### Autonomy Gate Tests
```bash
pytest tests/test_autonomy_gate.py -v
```
- [ ] Test governance scopes (internal, external_low, external_high)
- [ ] Test authority levels (MANUAL, SEMI_AUTO, FULL_AUTO)
- [ ] Test evidence gates (blake_birthmark validation)
- [ ] Test rate limiting
- [ ] Test cost controls

### Quantum Royalty Tests
```bash
pytest tests/test_quantum_royalty.py -v
```
- [ ] Keypair generation (Dilithium3)
- [ ] Mission signing
- [ ] Signature verification
- [ ] Kyber768 encapsulation
- [ ] HMAC fallback (if liboqs unavailable)

### Ouroboros Tests
```bash
pytest tests/test_ouroboros_spine.py -v
```
- [ ] System registration
- [ ] Health monitoring loop (5-minute cycles)
- [ ] Healing strategies (retry → restart → rollback → spawn)
- [ ] Regeneration event logging
- [ ] System spawn workflow

### Integration Tests
```bash
pytest tests/test_integration.py -v
```
- [ ] Full mission flow: briefing → autonomy check → execution → audit
- [ ] PQC signature in audit trail
- [ ] Governance rejection for out-of-scope missions
- [ ] Multiple system delegation
- [ ] Cross-system communication

### API Tests
- [ ] GET /health returns 200
- [ ] GET /status returns full system info
- [ ] POST /pqc/generate-keypair returns keypair metadata
- [ ] POST /briefings accepts mission and returns mission_id
- [ ] GET /missions/{id} returns mission status
- [ ] GET /autonomy/report returns governance state
- [ ] GET /ouroboros/report returns health heatmap
- [ ] GET /governance/policies returns all scopes

### Coverage Report
```bash
pytest tests/ --cov=src --cov-report=html
```
- [ ] Overall coverage >80%
- [ ] autonomy_gate.py coverage >85%
- [ ] quantum_royalty.py coverage >85%
- [ ] ouroboros_spine.py coverage >80%

---

## PHASE 3: KUBERNETES DEPLOYMENT (Week 3)

### Image Build & Push
- [ ] Build Trinity API image:
  ```bash
  docker build -f Dockerfile.trinity -t gcr.io/my-project/trinity:latest .
  ```
- [ ] Build Governance image:
  ```bash
  docker build -f Dockerfile.governance -t gcr.io/my-project/trinity-governance:latest .
  ```
- [ ] Build Ouroboros image:
  ```bash
  docker build -f Dockerfile.ouroboros -t gcr.io/my-project/trinity-ouroboros:latest .
  ```
- [ ] Build Spawner image:
  ```bash
  docker build -f Dockerfile.spawner -t gcr.io/my-project/trinity-spawner:latest .
  ```
- [ ] Push all images to registry (Docker Hub, GCR, ECR, etc.)
- [ ] Verify images are accessible:
  ```bash
  docker pull gcr.io/my-project/trinity:latest
  ```

### K8s Manifest Preparation
- [ ] Update image references in `k8s/trinity-k8s-operator.yaml`
- [ ] Replace `trinity:latest` with `gcr.io/my-project/trinity:latest` (4 places)
- [ ] Verify manifest syntax:
  ```bash
  kubectl apply -f k8s/trinity-k8s-operator.yaml --dry-run=client
  ```

### K8s Deployment
- [ ] Create namespace: `kubectl create namespace trinity-spine`
- [ ] Create secrets:
  ```bash
  kubectl create secret generic trinity-secrets \
    --from-literal=TRINITY_API_KEY=... \
    --from-literal=SUPABASE_SERVICE_KEY=... \
    -n trinity-spine
  ```
- [ ] Apply manifest: `kubectl apply -f k8s/trinity-k8s-operator.yaml`
- [ ] Wait for rollout: `kubectl rollout status deployment/trinity-spine -n trinity-spine`

### Pod Verification
- [ ] Check pods: `kubectl get pods -n trinity-spine`
- [ ] Expected: trinity-spine-xxx (3 replicas), governance-sidecar-xxx, ouroboros-monitor-xxx
- [ ] Check pod logs: `kubectl logs deployment/trinity-spine -n trinity-spine`
- [ ] Check init containers: `kubectl describe pod -n trinity-spine`

### Service Verification
- [ ] Check services: `kubectl get svc -n trinity-spine`
- [ ] Expected: trinity-service (LoadBalancer), governance-service (ClusterIP)
- [ ] Get LoadBalancer IP: `kubectl get svc trinity-service -n trinity-spine`
- [ ] Wait for EXTERNAL-IP (may take 1-5 minutes)

### Port Forwarding Test
- [ ] Port forward: `kubectl port-forward -n trinity-spine svc/trinity-service 8000:80 &`
- [ ] Test health: `curl http://localhost:8000/health`
- [ ] Expected: 200 OK with status=healthy

### CronJobs
- [ ] Check cronjobs: `kubectl get cronjobs -n trinity-spine`
- [ ] Expected: trinity-system-spawner-daily, trinity-ouroboros-audit-5min
- [ ] Verify schedule: System spawner @ 0 0 *, Ouroboros @ */5 *

### Horizontal Pod Autoscaling (HPA)
- [ ] Check HPA: `kubectl get hpa -n trinity-spine`
- [ ] Expected: trinity-spine-hpa with min=3, max=10
- [ ] Check current replicas: `kubectl get deployment trinity-spine -n trinity-spine`
- [ ] Generate load and verify scaling:
  ```bash
  # Run load test
  for i in {1..100}; do curl http://localhost:8000/health & done; wait
  ```
- [ ] Check replicas increased: `kubectl get deployment trinity-spine -n trinity-spine`

---

## PHASE 4: MONITORING & OPERATIONS (Week 4+)

### Prometheus Setup
- [ ] Port forward Prometheus: `kubectl port-forward -n trinity-spine svc/prometheus-service 9090:9090`
- [ ] Visit http://localhost:9090
- [ ] Verify scrape targets:
  - [ ] trinity-api (8000/metrics)
  - [ ] governance-sidecar (8001/metrics)
  - [ ] ouroboros-monitor (9090/metrics)
- [ ] Query sample metrics:
  ```
  trinity_missions_total
  trinity_autonomy_gate_decisions_total
  trinity_pqc_signatures_total
  trinity_ouroboros_healing_attempts_total
  ```

### Grafana Setup
- [ ] Port forward Grafana: `kubectl port-forward -n trinity-spine svc/grafana-service 3000:3000`
- [ ] Visit http://localhost:3000
- [ ] Login: admin / trinity
- [ ] Add Prometheus data source: http://prometheus-service:9090
- [ ] Create dashboards:
  - [ ] Autonomy Dashboard (delegations, rejections, rate limits)
  - [ ] Quantum Security Dashboard (PQC signatures, verification failures)
  - [ ] Ouroboros Health Dashboard (system health, healing events)

### Alerting Setup
- [ ] Configure AlertManager (if using Prometheus Operator)
- [ ] Create alerts:
  - [ ] Pod Down (critical)
  - [ ] High Error Rate (warning)
  - [ ] PQC Verification Failures (warning)
  - [ ] Healing Loop Active (warning)
- [ ] Connect to notification channel (Slack, PagerDuty, email)

### Logging & Audit Trail
- [ ] Check Trinity logs: `kubectl logs -f deployment/trinity-spine -n trinity-spine`
- [ ] Verify JSON logging format
- [ ] Check audit trail in Supabase:
  ```sql
  SELECT * FROM audit_events ORDER BY created_at DESC LIMIT 10;
  ```
- [ ] Set up log aggregation (ELK, Loki, CloudWatch, etc.)

### Backup & Disaster Recovery
- [ ] Test backup: `kubectl get pvc -n trinity-spine`
- [ ] Verify persistent volumes are mounted (Redis, PostgreSQL)
- [ ] Test backup restore procedure
- [ ] Document RTO/RPO targets

---

## PHASE 5: ROOSEVELT SYSTEM INTEGRATION (Week 4-5)

### System Spawner Implementation
- [ ] Implement `src/core/system_spawner.py` (auto-creates Roosevelt systems)
- [ ] Add system definitions for all 20 systems (YUR-AI, WAV, WCC, Sentinel, etc.)
- [ ] Create K8s deployment manifests for each system
- [ ] Configure spawn schedule (daily @ midnight or custom)

### System Registration
- [ ] Register YUR-AI: `POST /systems/register` (name=YUR-AI, replicas=3)
- [ ] Register WAV: `POST /systems/register` (name=WAV, replicas=2)
- [ ] Register WCC: `POST /systems/register` (name=WCC, replicas=1)
- [ ] Register Sentinel: `POST /systems/register` (name=Sentinel, replicas=2)
- [ ] Register remaining systems

### PQC Keypair Distribution
- [ ] Generate keypair for each system: `POST /pqc/generate-keypair`
- [ ] Distribute public keys to each system (via K8s ConfigMap or IPFS)
- [ ] Verify cross-system signature validation

### Governance Policy Inheritance
- [ ] All spawned systems inherit Trinity governance scopes
- [ ] Verify external_medium missions require approval
- [ ] Verify cost limits enforced per-system
- [ ] Test rate limiting across systems

### Delegation Chain
- [ ] Test delegation: Trinity → YUR-AI → WAV
- [ ] Verify PQC signature chain: mission signed by Trinity, approved by YUR-AI, executed by WAV
- [ ] Verify audit trail includes all three systems

---

## PHASE 6: PRODUCTION HARDENING (Week 5+)

### Security Audit
- [ ] PQC keys: Verify all keys stored in HSM (not in-memory)
- [ ] API Keys: Rotate TRINITY_API_KEY and TRINITY_SIGNING_SECRET
- [ ] Supabase RLS: Enable row-level security for governance tables
- [ ] Network Policies: Verify K8s NetworkPolicy restricts pod communication
- [ ] RBAC: Verify ServiceAccount has minimal permissions

### Load Testing
```bash
# k6 load test script
while true; do
  curl -X POST http://localhost:8000/briefings \
    -H "X-API-Key: $TRINITY_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"prompt": "test", "scope": "internal"}'
done
```
- [ ] Target: 1000 req/s sustained
- [ ] Verify HPA scales to 10 replicas
- [ ] Monitor error rate (should be <0.1%)
- [ ] Monitor latency (p99 < 500ms)

### Failover Testing
- [ ] Kill trinity-spine pod: `kubectl delete pod -n trinity-spine trinity-spine-xxx`
- [ ] Verify: New pod scheduled, HPA maintains 3 replicas
- [ ] Test governance sidecar failure
- [ ] Test ouroboros monitor failure
- [ ] Verify Ouroboros detects and repairs each failure

### Backup & Recovery
- [ ] Test PostgreSQL backup: `pg_dump`
- [ ] Test restore from backup
- [ ] Test Redis snapshot restore
- [ ] Verify RTO: <5 minutes, RPO: <1 hour

### Compliance & Audit
- [ ] SOC2 audit trail (all operations logged with evidence)
- [ ] GDPR data residency (EU data stays in EU)
- [ ] PCI-DSS (if handling payments directly)
- [ ] HIPAA (if handling health data)

---

## ✅ Deployment Complete Checklist

### Before Go-Live
- [ ] Local development fully tested
- [ ] Integration tests all passing
- [ ] Kubernetes deployment stable (24h uptime)
- [ ] Monitoring and alerting active
- [ ] Backup and disaster recovery tested
- [ ] Documentation complete
- [ ] Team training completed
- [ ] On-call procedures documented

### Launch Approval
- [ ] Security clearance obtained
- [ ] Performance benchmarks met
- [ ] Stakeholder sign-off received
- [ ] Incident response plan ready

### Go-Live Day
- [ ] Early morning deployment (off-peak)
- [ ] Team on-call and monitoring
- [ ] Gradual traffic ramp-up (10% → 50% → 100%)
- [ ] Monitor error rates and latency
- [ ] Have rollback plan ready

### Post-Launch
- [ ] Monitor 24/7 for first week
- [ ] Gradual transition to normal on-call rotation
- [ ] Post-mortem on any incidents
- [ ] Optimize based on metrics
- [ ] Plan next features

---

## 📞 Support & Escalation

**Issues or questions:**
- Slack: #trinity-deployment
- Email: trinity@roosevelt-ventures.io
- PagerDuty: @trinity-oncall

**Critical Issues:**
1. Immediately page on-call engineer
2. Get logs: `kubectl logs deployment/trinity-spine`
3. Check metrics: Prometheus + Grafana
4. Check Ouroboros health: `GET /ouroboros/report`
5. Escalate to security if PQC failure

---

**Trinity Spine Deployment Checklist**  
**Version:** 1.0  
**Last Updated:** February 11, 2026  
**Status:** ✅ Production-Ready
