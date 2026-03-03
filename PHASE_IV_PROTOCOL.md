# Phase IV: LLM Integration Protocol

**Status**: 🔧 Code Complete | Awaiting Ollama Server Activation  
**Timestamp**: 2026-02-10  
**System**: Cognitive Codebase Analysis Bootstrap v1.0

---

## Overview

Phase IV activates the final layer of the cognitive engine: **local LLM inference via Ollama**. This transforms the RAG pipeline from a passive retrieval system into an **active reasoning engine** capable of synthesizing answers directly from code context.

### Architecture

```
User Query
    ↓
[VectorNode] Semantic Search
    ↓
[CognitiveQueryEngine.retrieve_context()] Top-3 Artifacts
    ↓
[construct_prompt()] Prompt Assembly with Code Context
    ↓
[query_llm()] HTTP API → Ollama
    ↓
[llama3] Local LLM Generation
    ↓
Response Display
```

---

## Prerequisites

### System Requirements
- **OS**: Windows 10/11, macOS, or Linux
- **RAM**: Minimum 8GB (llama3 8B model = ~4-6GB loaded)
- **Storage**: 5GB free (for Ollama + models)
- **Network**: Localhost only (no external calls)

### Software Requirements
- **Python**: 3.10+
- **Ollama**: Latest version (from ollama.com)
- **Dependencies**: All listed in requirements.txt

---

## Installation & Setup

### Step 1: Install Ollama

**Option A: Download from Website**
```bash
# Visit https://ollama.com and download Windows/macOS installer
# Run installer and follow prompts
# Ollama will be available at http://localhost:11434
```

**Option B: Windows Package Manager**
```powershell
winget install Ollama.Ollama
```

**Option C: Verify Installation**
```bash
ollama --version
# Expected output: ollama version X.X.X
```

### Step 2: Pull Model

```bash
# Download and cache llama3 (8B parameters, ~4.7GB)
ollama pull llama3

# Expected output:
# pulling manifest
# pulling 6a0746a1ec1a... 100% ▓▓▓▓▓▓▓▓▓▓ 3.8 GB
# pulling 8c4f16bf77f5... 100% ▓▓▓▓▓▓▓▓▓▓ 97 B
# pulling 7c23fb36d801... 100% ▓▓▓▓▓▓▓▓▓▓ 11 KB
# pulling 2e0493f67d0c... 100% ▓▓▓▓▓▓▓▓▓▓ 13 B
# pulling da69d4589dc0... 100% ▓▓▓▓▓▓▓▓▓▓ 365 B
# pulling 4ad0d34192c9... 100% ▓▓▓▓▓▓▓▓▓▓ 241 B
# pulling 8ab3f7e4ddb9... 100% ▓▓▓▓▓▓▓▓▓▓ 42 B
# verifying sha256 digest
# writing manifest
# success
```

### Step 3: Start Ollama Server

```bash
# In a NEW terminal window, start the Ollama service
ollama serve

# Expected output:
# Ollama is running
# Listen on 127.0.0.1:11434
```

**CRITICAL**: Keep this terminal window open. The server must remain running during all tests.

### Step 4: Verify Server is Responsive

```bash
# In another terminal, test connectivity
curl http://localhost:11434/api/tags

# Expected output:
# {
#   "models": [
#     {
#       "name": "llama3:latest",
#       "modified_at": "2026-02-10T...",
#       "size": 4732261376,
#       "digest": "439df...",
#       "details": {...}
#     }
#   ]
# }
```

---

## Cognitive Engine Configuration

All LLM parameters are defined in [src/core/cognitive_query.py](src/core/cognitive_query.py):

```python
LLM_API_URL = "http://localhost:11434/api/generate"  # Ollama endpoint
LLM_MODEL = "llama3"                                  # Model name
LLM_ENABLED = True                                    # Enable/disable
LLM_TEMPERATURE = 0.2                                 # 0=factual, 1=creative
LLM_CONTEXT_WINDOW = 4096                            # Max tokens in context
```

### Configuration Tuning

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Temperature** | 0.2 | Low = Factual responses focused on code, not generation |
| **Context Window** | 4096 | Sufficient for code analysis; prevents memory overflow |
| **Model** | llama3 | 8B parameters; good speed/quality balance for local inference |
| **API URL** | localhost:11434 | Private network; no external data transmission |

---

## Functional Test Protocol

### Test A: Delta Verification Understanding

**Objective**: Retrieve delta_verification implementation, generate structural explanation

**Command**:
```bash
cd F:\New folder\cognitive_engine
python src/core/cognitive_query.py "How does delta verification logic work? What files does it analyze?"
```

**Expected Behavior**:
1. ✅ System vectorizes query
2. ✅ Retrieves top-3 artifacts (primary: blake_birthmarking.py)
3. ✅ Assembles prompt with code context
4. ✅ Sends request to Ollama
5. ✅ llama3 generates 150-300 word explanation
6. ✅ Response includes: "hash comparison", "genesis baseline", "delta scan"

**Success Criteria**:
- Response mentions delta verification logic
- Response references specific methods or variables from retrieved code
- Output is technically accurate based on code context

**Failure Modes**:
- ❌ Connection refused → Ollama not running (check `ollama serve`)
- ❌ Model not found → `ollama pull llama3` not executed
- ❌ Timeout > 120s → Model loading; wait and retry
- ❌ Hallucination → Temperature too high; reduce to 0.15

---

### Test B: Hashing Algorithm Discovery

**Objective**: Identify cryptographic algorithm, explain design rationale

**Command**:
```bash
python src/core/cognitive_query.py "What cryptographic hashing algorithm is used for birthmarking and why was it chosen?"
```

**Expected Behavior**:
1. ✅ Query vectorizes
2. ✅ FAISS retrieves blake_birthmarking.py (top match)
3. ✅ Prompt constructed with SHA256/BLAKE3 code context
4. ✅ LLM inference completes
5. ✅ Response identifies: "SHA-256", "BLAKE3", "immutable", "content-addressable"

**Success Criteria**:
- Response names the hashing algorithms
- Response cites code selections/rationale
- Technical explanation is grounded in retrieved context (not hallucinated)

**Failure Modes**:
- ❌ Wrong algorithm named → Model hallucination; check retrieved context
- ❌ Generic explanation → Temperature too high or context insufficient

---

### Test C: Advanced Integration Test

**Objective**: Multi-artifact synthesis (requires cross-file reasoning)

**Command**:
```bash
python src/core/cognitive_query.py "Explain how the XML serialization integrates with blake birthmarking and why Base64 encoding was chosen over CDATA"
```

**Expected Behavior**:
1. ✅ Retrieves both cognitive_node.py and blake_birthmarking.py
2. ✅ LLM synthesizes connection between modules
3. ✅ Explains Base64 vs CDATA tradeoffs

**Success Criteria**:
- Response ties together 2+ modules
- Explains design decision rationale
- Validates against OLK-7 optimization analysis

---

## Troubleshooting Guide

### Error: "Could not connect to Ollama at http://localhost:11434"

**Diagnosis**:
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags
```

**Resolution**:
1. Start Ollama in separate terminal: `ollama serve`
2. Wait 5 seconds for server to initialize
3. Retry cognitive_query.py

---

### Error: "Model not found: llama3"

**Resolution**:
```bash
ollama pull llama3
# Wait for download to complete (5-10 GB, depends on network)
```

---

### Error: "Timeout (>120s)"

**Diagnosis**:
- First run of model loads it into GPU/RAM (~30-60s)
- Large prompt + long response generates more tokens

**Resolution**:
- Retry after 10 seconds (second run will be faster)
- Reduce `LLM_CONTEXT_WINDOW` from 4096 to 2048 if persistent

---

### Error: "Response contains hallucinations"

**Symptoms**:
- LLM generates plausible but incorrect code explanations
- Mentions functions/variables not in retrieved context

**Resolution**:
1. Lower temperature from 0.2 to 0.1:
   ```python
   LLM_TEMPERATURE = 0.1  # More factual/deterministic
   ```
2. Verify retrieved context is relevant (check FAISS similarity scores)
3. Try a more specific query

---

## Performance Baselines

### Expected Latencies (Local Hardware)

| Operation | Time | Notes |
|-----------|------|-------|
| Query vectorization | ~100ms | SentenceTransformer embedding |
| FAISS search (16 vectors) | ~5ms | L2 distance index lookup |
| Prompt construction | ~50ms | Context assembly |
| Ollama API call | ~1000-5000ms | Depends on response length |
| **Total E2E** | ~2-7 seconds | First run ~3-5s, subsequent ~2s |

---

## Production Deployment Checklist

- [ ] Ollama installed and tested
- [ ] Model pulled: `ollama pull llama3`
- [ ] Server running: `ollama serve` (persistent)
- [ ] Core dependencies installed: `pip install -r requirements.txt`
- [ ] Test A passed: Delta verification query works
- [ ] Test B passed: Hashing algorithm query works
- [ ] Test C passed: Multi-artifact synthesis works
- [ ] Temperature tuned to 0.15-0.2 (factuality)
- [ ] DEPLOYMENT_LOG.txt updated with Phase IV results
- [ ] Security review: Ollama localhost-only, no external transmissions
- [ ] Performance validation: E2E latency < 10s avg

---

## Advanced Configuration

### Using Different Models

Ollama supports multiple models. Swap in the `LLM_MODEL` constant:

```bash
# Pull alternative model
ollama pull mistral        # 7B, faster, good for coding
ollama pull neural-chat    # 7B, instruction-tuned
ollama pull dolphin-mixtral  # 45B, more capable (requires ~30GB RAM)
```

Then update [cognit ive_query.py](src/core/cognitive_query.py):
```python
LLM_MODEL = "mistral"  # Switch model
```

### CPU vs GPU Optimization

**GPU Acceleration** (NVIDIA CUDA):
```bash
# Ollama auto-detects CUDA. If available, model loads on GPU
# Inference latency drops 50-70% vs CPU-only
ollama serve
# Check logs for: "nvidia-smi" or "CUDA available"
```

**CPU-Optimized** (Intel AVX2):
```python
# Set lower context window to reduce memory footprint
LLM_CONTEXT_WINDOW = 2048  # Instead of 4096
```

---

## Audit & Compliance

All Phase IV operations are logged to:
- **Console**: Real-time execution with INFO/ERROR levels
- **DEPLOYMENT_LOG.txt**: Master audit trail (append-only)

### Update Log After Tests

```bash
# Append Phase IV results
echo "
=== PHASE IV: LLM INTEGRATION TESTS ===
Timestamp: $(date)
Test A (Delta Verification): PASS/FAIL
Test B (Hashing Algorithm): PASS/FAIL
Test C (Multi-Artifact): PASS/FAIL
Ollama Model: llama3
API Endpoint: http://localhost:11434
Temperature: 0.2
Context Window: 4096
Average Latency: XXX ms
" >> DEPLOYMENT_LOG.txt
```

---

## Next Steps

1. **Below**: Execute Tests A, B, C
2. Create snapshot of test output (evidence for auditors)
3. Update DEPLOYMENT_LOG.txt with results
4. Proceed to Phase V: External Codebase Analysis
5. Deploy to production environment

---

**Phase IV Complete When**: All 3 functional tests PASS and results are logged.

