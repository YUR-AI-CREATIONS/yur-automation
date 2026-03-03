# Trinity Spine — Complete Deployment Guide
## Full Autonomy, Quantum-Hard, Self-Regenerating Enterprise System

**Date:** February 11, 2026  
**Status:** Production-Ready  
**Version:** 1.0

---

## TABLE OF CONTENTS

1. [System Overview](#system-overview)
2. [Local Development (Docker Compose)](#local-development)
3. [Kubernetes Deployment](#kubernetes-deployment)
4. [Configuration & Environment](#configuration-environment)
5. [Activation Checklist](#activation-checklist)
6. [Monitoring & Operations](#monitoring-operations)
7. [Troubleshooting](#troubleshooting)
8. [Integration with Roosevelt Spine](#integration-roosevelt)

---

## SYSTEM OVERVIEW

Trinity Spine is a **fully autonomous, quantum-hardened, self-regenerating execution engine** with four core capabilities:

### **Tier 1: Autonomy Gate** (Governance-Gated Auto-Execution)
- Missions auto-execute within pre-set governance bounds
- No human approval per task (only governance policy updates)
- Evidence gates ensure proof-of-intent before execution
- Rate limiting & cost controls built-in

### **Tier 2: Quantum Royalty** (Post-Quantum Cryptography)
- Dilithium3 for digital signatures (quantum-resistant)
- Kyber768 for key encapsulation (replaces TLS)
- Hybrid HMAC fallback if liboqs unavailable
- All mission data signed & verified with PQC

### **Tier 3: Ouroboros Spine** (Self-Healing, Self-Spawning)
- Continuous health monitoring of all subsystems
- Auto-retry, restart, rollback, or spawn replacement
- Self-auditing with immutable evidence logs
- Daily regeneration checks (cronjob-based)

### **Tier 4: System Spawner** (Automated System Creation)
- Auto-creates YUR AI, WAV, WCC, and other subsystems
- Inherits governance policies from Trinity
- Register-once, deploy-anywhere architecture
- Self-healing pipeline for failed spawns

---

## LOCAL DEVELOPMENT (Docker Compose)

### Prerequisites

```bash
# Install Docker & Docker Compose
docker --version  # 24.0+
docker-compose --version  # v2.20+

# Install Python & dependencies
python 3.11+
pip install -r requirements.txt

# Install liboqs (optional, for local PQC testing)
brew install liboqs  # macOS
# or
apt-get install liboqs-dev  # Ubuntu
```

### Quick Start

**Step 1: Clone & Setup**

```bash
cd F:\New folder\cognitive_engine
cp .env.example .env
```

**Step 2: Configure .env**

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Trinity Secrets
TRINITY_API_KEY=your-secret-api-key
TRINITY_SIGNING_SECRET=your-pqc-signing-secret
TRINITY_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# Postgres
POSTGRES_PASSWORD=trinity
POSTGRES_USER=postgres
POSTGRES_DB=trinity

# Grafana
GRAFANA_PASSWORD=trinity
```

**Step 3: Start Services**

```bash
docker-compose up -d
```

This brings up:
- ✅ Trinity API (http://localhost:8000)
- ✅ Governance Sidecar (http://localhost:8001)
- ✅ Ouroboros Monitor (background)
- ✅ System Spawner (cron job @ midnight)
- ✅ Redis, PostgreSQL, Prometheus, Grafana

**Step 4: Verify Deployment**

```bash
# Check health
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "trinity_version": "1.0",
  "autonomy_level": "SEMI_AUTO",
  "pqc_enabled": true,
  "ouroboros_enabled": true
}

# View logs
docker-compose logs -f trinity-api
docker-compose logs -f ouroboros-monitor
```

**Step 5: Test Autonomy & PQC**

```bash
# Generate PQC keypair
curl -X POST http://localhost:8000/pqc/generate-keypair \
  -H "X-API-Key: ${TRINITY_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"key_id": "test-key-001"}'

# Expected: 200 OK with keypair metadata

# Submit a mission (auto-executes if within governance bounds)
curl -X POST http://localhost:8000/briefings \
  -H "X-API-Key: ${TRINITY_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Generate a summary of this codebase",
    "context": "src/core/autonomy_gate.py",
    "metadata": {"scope": "internal", "approved": true}
  }'

# Expected: 200 OK with mission_id

# Get autonomy report
curl http://localhost:8000/autonomy/report \
  -H "X-API-Key: ${TRINITY_API_KEY}"

# Expected: Authority level, rate limits, and recent delegations
```

---

## KUBERNETES DEPLOYMENT

### Prerequisites

```bash
# Kubernetes cluster (GKE, EKS, AKS, or local kind)
kubectl version --client
kubectl get nodes

# Create namespace
kubectl create namespace trinity-spine
```

### Step 1: Build & Push Docker Images

```bash
# Build images
docker build -f Dockerfile.trinity -t trinity:latest .
docker build -f Dockerfile.governance -t trinity-governance:latest .
docker build -f Dockerfile.ouroboros -t trinity-ouroboros:latest .
docker build -f Dockerfile.spawner -t trinity-spawner:latest .

# Push to registry (e.g., Docker Hub, GCR, ECR)
docker tag trinity:latest gcr.io/my-project/trinity:latest
docker push gcr.io/my-project/trinity:latest
# (repeat for other images)
```

### Step 2: Create Kubernetes Secrets

```bash
# Create secret with API keys
kubectl create secret generic trinity-secrets \
  --from-literal=TRINITY_API_KEY=$(openssl rand -hex 32) \
  --from-literal=TRINITY_SIGNING_SECRET=$(openssl rand -hex 32) \
  --from-literal=SUPABASE_SERVICE_KEY=your-key \
  --from-literal=STRIPE_SECRET_KEY=your-key \
  --namespace=trinity-spine
```

### Step 3: Deploy to Kubernetes

```bash
# Update image refs in trinity-k8s-operator.yaml
sed -i 's|trinity:latest|gcr.io/my-project/trinity:latest|g' k8s/trinity-k8s-operator.yaml

# Apply manifests
kubectl apply -f k8s/trinity-k8s-operator.yaml

# Verify rollout
kubectl rollout status deployment/trinity-spine -n trinity-spine --timeout=300s

# Expected: "Waiting for deployment \"trinity-spine\" rollout to finish"
# Then: "deployment \"trinity-spine\" successfully rolled out"
```

### Step 4: Verify K8s Deployment

```bash
# Check pods
kubectl get pods -n trinity-spine
# Expected: trinity-spine-xxxx (3 replicas), governance-sidecar, ouroboros-monitor

# Check services
kubectl get svc -n trinity-spine
# Expected: trinity-service (LoadBalancer), governance-service (ClusterIP)

# Get LoadBalancer IP
kubectl get svc trinity-service -n trinity-spine
# EXTERNAL-IP will be assigned in a few moments

# Port-forward for testing
kubectl port-forward -n trinity-spine svc/trinity-service 8000:80 &
curl http://localhost:8000/health
```

### Step 5: Monitor K8s Deployment

```bash
# View logs
kubectl logs -n trinity-spine -f deployment/trinity-spine --all-containers=true

# View CronJob status
kubectl get cronjobs -n trinity-spine
kubectl logs -n trinity-spine -f job/trinity-system-spawner-xxxxx

# Check HPA (autoscaling)
kubectl get hpa -n trinity-spine
kubectl describe hpa trinity-spine-hpa -n trinity-spine
```

---

## CONFIGURATION & ENVIRONMENT

### Autonomy Levels

```env
# TRINITY_AUTONOMY_LEVEL=0 (MANUAL)
#   - All tasks require human approval
#   - Most restrictive, slowest

# TRINITY_AUTONOMY_LEVEL=1 (SEMI_AUTO)
#   - Internal tasks auto-execute (code, tests, logs)
#   - External tasks require approval
#   - Recommended for production

# TRINITY_AUTONOMY_LEVEL=2 (FULL_AUTO)
#   - All tasks auto-execute within governance bounds
#   - Fastest, but requires robust governance policies
#   - Use only in mature deployments
```

### Governance Scopes

```json
{
  "internal": {
    "auto_execute": true,
    "requires_evidence": true,
    "max_retries": 3,
    "timeout_sec": 300
  },
  "external_low": {
    "auto_execute": true,
    "requires_evidence": true,
    "max_retries": 2,
    "timeout_sec": 60
  },
  "external_medium": {
    "auto_execute": false,
    "requires_evidence": true,
    "max_retries": 1,
    "timeout_sec": 120
  },
  "external_high": {
    "auto_execute": false,
    "requires_evidence": true,
    "max_retries": 0,
    "timeout_sec": 0
  }
}
```

### PQC Configuration

```env
# TRINITY_PQC_ENABLED=true
#   Enables Dilithium3 + Kyber768 quantum-resistant crypto
#   Requires: liboqs-python installed
#   Fallback: HMAC-based if liboqs unavailable

# TRINITY_SIGNING_SECRET=...
#   Used for PQC signature key generation
#   Should be 32+ bytes of high-entropy random data
```

### Ouroboros Configuration

```env
# TRINITY_OUROBOROS_ENABLED=true
#   Enables self-healing, self-auditing, self-spawning

# TRINITY_AUDIT_INTERVAL=300
#   Health check interval (seconds)
#   5 minutes = 288 checks/day

# TRINITY_MAX_RETRIES=3
#   Max auto-retry attempts before escalation

# TRINITY_REGENERATION_LOG_LIMIT=1000
#   Keep last N regeneration events in memory
```

---

## ACTIVATION CHECKLIST

### Pre-Launch (This Week)

- [ ] **Environment Setup**
  - [ ] Supabase project created + DB schema deployed
  - [ ] Stripe account set up + webhook configured
  - [ ] .env file populated with all secrets
  - [ ] Redis instance available (local or cloud)

- [ ] **Code & Docker**
  - [ ] All 4 modules implemented (autonomy_gate.py, quantum_royalty.py, ouroboros_spine.py, system_spawner.py)
  - [ ] requirements.txt updated with dependencies
  - [ ] All 4 Dockerfiles built & tested locally
  - [ ] docker-compose.yml verified (logs clean, services respond)

- [ ] **Testing**
  - [ ] Autonomy Gate: Test governance scopes (internal, external_low, external_high)
  - [ ] Quantum Royalty: Keypair generation, signing, verification
  - [ ] Ouroboros: Health check passes, registry endpoints work
  - [ ] System Spawner: Mock spawn (dry-run) succeeds
  - [ ] Integration: Mission submission → auto-execute → audit log

- [ ] **Documentation**
  - [ ] All env vars documented
  - [ ] API endpoints documented
  - [ ] Troubleshooting guide updated
  - [ ] On-call runbook created

### Launch Week

- [ ] **Kubernetes Deployment**
  - [ ] Images pushed to container registry
  - [ ] K8s secrets created
  - [ ] Manifests applied (namespace, RBAC, deployments)
  - [ ] Rollout verified (all pods healthy)
  - [ ] LoadBalancer IP assigned

- [ ] **Monitoring & Alerting**
  - [ ] Prometheus scraping Trinity metrics
  - [ ] Grafana dashboards created (autonomy, PQC, ouroboros)
  - [ ] Alert rules configured (pod down, high error rate, etc.)
  - [ ] On-call escalation wired (PagerDuty, Slack, etc.)

- [ ] **Operational Readiness**
  - [ ] Backup/restore procedures tested
  - [ ] Deployment rollback procedure tested
  - [ ] Incident response playbook drafted
  - [ ] Team training completed

---

## MONITORING & OPERATIONS

### Key Metrics

```
Trinity API:
  - health_check_duration_ms
  - mission_execution_duration_ms
  - governance_gate_rejections_count
  - autonomous_execution_rate
  - pqc_signature_verifications_count

Autonomy Gate:
  - delegations_per_hour
  - governance_overrides_count
  - rate_limit_violations_count
  - cost_limit_violations_count

Quantum Royalty:
  - keypair_generations_count
  - signature_operations_count
  - verification_failures_count
  - pqc_fallback_usage_count

Ouroboros:
  - system_health_checks_count
  - auto_healing_attempts_count
  - regeneration_events_count
  - system_spawn_success_rate
```

### Dashboards

#### Autonomy Dashboard
- Autonomy level (MANUAL / SEMI_AUTO / FULL_AUTO)
- Delegations per hour (trending)
- Governance rejections (by scope)
- Rate limit violations

#### Quantum Security Dashboard
- PQC signature operations (trending)
- Verification failures + recovery
- Keypair generation success rate
- Fallback usage (HMAC vs PQC)

#### Ouroboros Health Dashboard
- System health heatmap (all subsystems)
- Healing attempts + success rate
- Regeneration events timeline
- Spawn success/failure rate

### Alerting Rules

```yaml
# Pod down alert
expr: up{job="trinity-spine"} == 0
for: 2m
severity: critical

# High error rate
expr: rate(trinity_errors_total[5m]) > 0.05
for: 5m
severity: warning

# PQC failures
expr: rate(pqc_verification_failures_total[5m]) > 0.01
for: 10m
severity: warning

# Ouroboros healing loop
expr: rate(ouroboros_healing_attempts_total[1h]) > 10
for: 30m
severity: warning
```

---

## TROUBLESHOOTING

### "PQC not available" Error

```
Symptoms: PQC_AVAILABLE = False, using HMAC fallback

Fix:
1. Install liboqs:
   pip install liboqs-python

2. Or use fallback (logs will warn but system works)
```

### "Governance gate rejections too high"

```
Symptoms: Most missions rejected with "not within bounds"

Fix:
1. Check governance policies:
   GET /governance/policies

2. Review recent rejections:
   GET /missions/{id}/rejection-reason

3. Update policies if needed:
   POST /governance/policies
   {"scope": "external_low", "auto_execute": true}
```

### "Ouroboros healing loop too active"

```
Symptoms: Too many auto-restart events, system thrashing

Fix:
1. Check system health:
   GET /ouroboros/report

2. Identify failing subsystem:
   Increase logging: TRINITY_LOG_LEVEL=DEBUG

3. Manual intervention:
   - Restart problematic pod (K8s)
   - Or scale down (let Ouroboros spawn replacement)
```

### "Supabase connection failing"

```
Symptoms: "Error connecting to supabase" in logs

Fix:
1. Verify env vars:
   echo $SUPABASE_URL
   echo $SUPABASE_SERVICE_KEY

2. Test connectivity:
   curl -X GET "$SUPABASE_URL/rest/v1/" \
     -H "Authorization: Bearer $SUPABASE_SERVICE_KEY"

3. Check firewall/VPC rules (if on private network)
```

---

## INTEGRATION WITH ROOSEVELT SPINE

### Roosevelt Spine Architecture

The Trinity codebase implements the **operational backbone** of the Roosevelt + Franklin OS ecosystem:

```
ROOSEVELT_FRANKLIN_OS_SPINE.md (Architectural blueprint)
           ↓
  Trinity Spine (Operational implementation)
       ├─ Autonomy Gate (governance execution)
       ├─ Quantum Royalty (cryptographic hardening)
       ├─ Ouroboros Spine (self-regeneration)
       └─ System Spawner (20-system creation)
           ├─ YUR-AI (cognitive twin)
           ├─ WAV (regenerative reactor)
           ├─ WCC (charity coin)
           ├─ Sentinel (immune system)
           └─ [+16 more systems]
           ↓
    All systems inherit:
    - Governance policies
    - PQC cryptography
    - Audit logging
    - Self-healing
    - Monitoring
```

### Wiring Trinity to Roosevelt Portfolio

```bash
# 1. Deploy Trinity Spine (this guide)
docker-compose up -d

# 2. Register all 20 systems with Ouroboros
curl POST http://localhost:8000/ouroboros/register-system \
  -H "Content-Type: application/json" \
  -d '{"system_id": "yur_ai_001", "system_name": "YUR-AI", "config": {...}}'

# 3. Generate PQC keypairs for each system
for system in yur_ai wav wcc sentinel construction_wizard; do
  curl POST http://localhost:8000/pqc/generate-keypair \
    -d "{\"key_id\": \"${system}-001\"}"
done

# 4. Deploy Roosevelt governance policies
curl POST http://localhost:8000/governance/policies \
  -d @governance-policies.json

# 5. Start daily regeneration (system spawner)
# Automatically runs via K8s CronJob @ midnight

# 6. Enable autonomous execution (carefully!)
curl POST http://localhost:8000/autonomy/set-level \
  -d '{"authority_level": 2}'  # FULL_AUTO
```

### System Status & Evidence

```bash
# Get full ecosystem status
curl http://localhost:8000/ouroboros/report

# Example output:
{
  "ouroboros_enabled": true,
  "systems_monitored": 20,
  "systems": {
    "yur_ai_001": {"name": "YUR-AI", "health": "healthy"},
    "wav_001": {"name": "WAV", "health": "healthy"},
    ...
  },
  "recent_regeneration_events": [...]
}

# Get PQC status
curl http://localhost:8000/pqc/status

# Get autonomy report
curl http://localhost:8000/autonomy/report
```

---

## NEXT STEPS

1. **Complete Pre-Launch Checklist** (this week)
2. **Deploy to Staging K8s** (week 2)
3. **Integration testing with Roosevelt systems** (week 3)
4. **Go live to production** (week 4)
5. **Monitor, tune, and scale** (ongoing)

---

## SUPPORT & ESCALATION

**Issues:**
- File GitHub issue at `YUR-AI-CREATIONS/trinity`

**On-Call:**
- PagerDuty escalation: @trinity-oncall

**Questions:**
- Slack: #trinity-deployment
- Email: trinity@roosevelt-ventures.io

---

**Deployment Guide Version:** 1.0  
**Last Updated:** February 11, 2026  
**Status:** Production-Ready ✅
