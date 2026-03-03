"""
Cognitive Query Engine: Retrieval-Augmented Generation (RAG) Pipeline
Transforms semantic search into dynamic reasoning interface for code analysis
WITH Local LLM Integration (Ollama)
"""

import json
import os
import sys
import logging
import numpy as np
import faiss
import requests
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Configuration
INDEX_PATH = "data/output/vector_index.bin"
METADATA_PATH = "data/output/vector_index.json"
MODEL_NAME = 'all-MiniLM-L6-v2'
TOP_K = 3

# LLM Configuration (Ollama)
LLM_API_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "llama3"
LLM_ENABLED = True
LLM_TEMPERATURE = 0.2
LLM_CONTEXT_WINDOW = 4096


class CognitiveQueryEngine:
    """
    RAG Pipeline: Query → Vectorization → Retrieval → Context Assembly → Prompt Engineering
    
    Workflow:
    1. Accept natural language query from user
    2. Vectorize using SentenceTransformer
    3. Search FAISS index for top-K similar artifacts
    4. Retrieve raw code content from metadata
    5. Construct LLM prompt with retrieved context
    6. Ready for LLM inference (API integration point)
    """

    def __init__(self):
        logger.info(f"[INIT] Initializing Cognitive Query Engine (RAG Pipeline)...")        
        
        # 1. Load Vector Model
        try:
            self.model = SentenceTransformer(MODEL_NAME)
            logger.info(f"[OK] Model loaded: {MODEL_NAME}")
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            sys.exit(1)

        # 2. Load FAISS Index
        if not os.path.exists(INDEX_PATH):
            logger.error(f"❌ Index not found at {INDEX_PATH}. Run Phase II first.")
            sys.exit(1)
        
        try:
            self.index = faiss.read_index(INDEX_PATH)
            logger.info(f"[OK] FAISS Index loaded: {self.index.ntotal} vectors")
        except Exception as e:
            logger.error(f"[ERROR] Failed to load index: {e}")
            sys.exit(1)

        # 3. Load Metadata (Code Content & Birthmarks)
        if not os.path.exists(METADATA_PATH):
            logger.error(f"❌ Metadata not found at {METADATA_PATH}.")
            sys.exit(1)
            
        try:
            with open(METADATA_PATH, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
            logger.info(f"[OK] Metadata loaded: {len(self.metadata)} artifacts")
        except Exception as e:
            logger.error(f"[ERROR] Failed to load metadata: {e}")
            sys.exit(1)
        
        logger.info("[OK] Cognitive Query Engine ready for inference\n")

    def retrieve_context(self, query: str) -> list:
        """
        Retrieves the top-k most relevant code artifacts for a given query.
        
        Steps:
        1. Vectorize query using SentenceTransformer
        2. Search FAISS index using L2 distance metric
        3. Fetch artifacts from metadata
        4. Calculate normalized similarity scores
        
        Args:
            query (str): Natural language query
            
        Returns:
            list: Top-K results with {path, content, birthmark, score, similarity}
        """
        logger.info(f"[SEARCH] Vectorizing query: '{query}'")
        query_vector = self.model.encode([query])
        logger.info(f"   Query vector shape: {query_vector.shape}")
        
        # Search Index (FAISS expects float32)
        logger.info(f"   Searching FAISS index for top-{TOP_K} neighbors...")
        distances, indices = self.index.search(np.array(query_vector).astype('float32'), TOP_K)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.metadata):
                artifact = self.metadata[idx]
                score = float(distances[0][i])
                
                # Normalize L2 distance to similarity (0-1 range)
                # Lower L2 distance = Higher similarity
                similarity = 1.0 / (1.0 + score)
                
                results.append({
                    "rank": i + 1,
                    "path": artifact.get('path', 'unknown'),
                    "content": artifact.get('content', ''),
                    "birthmark": artifact.get('birthmark', 'N/A'),
                    "score": score,
                    "similarity": similarity
                })
                logger.info(f"   [{i+1}] {artifact.get('path', 'unknown')} → Similarity: {similarity:.4f}")
        
        return results

    def construct_prompt(self, query: str, context_artifacts: list) -> str:
        """
        Builds the prompt for the LLM (system + context + task).
        
        Prompt structure:
        - SYSTEM: Role definition
        - CONTEXT: Retrieved code artifacts with relevance scores
        - TASK: The user's original query
        
        Args:
            query (str): User's question
            context_artifacts (list): Retrieved code blocks
            
        Returns:
            str: Formatted prompt ready for LLM API
        """
        prompt = []
        prompt.append("SYSTEM: You are the Cognitive Engine Architect.")
        prompt.append("Your task: Answer the user's question based STRICTLY on the provided code context.")
        prompt.append("If the context does not address the query, say so explicitly.")
        prompt.append("Keep responses concise and technical.\n")
        prompt.append(f"USER QUERY:\n'{query}'\n")
        prompt.append("=" * 70)
        prompt.append("SOURCE CODE CONTEXT (Ranked by Relevance)")
        prompt.append("=" * 70)
        
        for art in context_artifacts:
            birthmark_preview = art.get('birthmark', 'N/A')[:32] + "..." if art.get('birthmark', 'N/A') != 'N/A' else 'N/A'
            path = art.get('path', 'unknown')
            content = art.get('content', '')
            
            prompt.append(f"\n[FILE]: {path}")
            prompt.append(f"Content Hash: {birthmark_preview}")
            prompt.append("```python")
            
            # Limit context per file to 1500 chars (preserve line structure)
            content_preview = content[:1500]
            prompt.append(content_preview)
            
            if len(content) > 1500:
                prompt.append("... (truncated)")
            
            prompt.append("```")
        
        prompt.append("\n" + "=" * 70)
        prompt.append("ANSWER (based strictly on above context):")
        prompt.append("=" * 70 + "\n")
        
        return "\n".join(prompt)

    def query_llm(self, prompt: str) -> str:
        """
        Sends the constructed prompt to the local Ollama instance.
        
        Args:
            prompt (str): Full prompt with context and task
            
        Returns:
            str: Generated response from LLM
        """
        if not LLM_ENABLED:
            return self._simulate_response(prompt)
        
        logger.info(f"[LLM] Invoking LLM ({LLM_MODEL})...")
        try:
            payload = {
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": LLM_TEMPERATURE,
                    "num_ctx": LLM_CONTEXT_WINDOW
                }
            }
            
            logger.info(f"   Sending request to {LLM_API_URL}")
            response = requests.post(LLM_API_URL, json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            answer = result.get('response', '[ERR] No response field in JSON')
            logger.info(f"   [OK] LLM generation complete ({len(answer)} chars)")
            
            return answer
            
        except requests.exceptions.ConnectionError:
            logger.error(f"[ERROR] Could not connect to Ollama at {LLM_API_URL}")
            logger.error("   Is 'ollama serve' running? (Check http://localhost:11434)")
            return "[CRITICAL] Could not connect to Ollama. Ensure 'ollama serve' is running on localhost:11434"
        except requests.exceptions.Timeout:
            logger.error("[ERROR] Ollama API timeout (>120s). Model may be loading into memory.")
            return "[CRITICAL] Ollama API timeout. Try again in a moment."
        except Exception as e:
            logger.error(f"[ERROR] API Error: {str(e)}")
            return f"[CRITICAL] LLM API Error: {str(e)}"

    def _simulate_response(self, prompt: str):
        """Fallback: Display prompt structure when LLM is not available."""
        print("\n" + "=" * 70)
        print("📋 GENERATED PROMPT (Ready for LLM API Integration)")
        print("=" * 70)
        print(prompt)
        print("=" * 70)
        print("\n[SIMULATION MODE] LLM Integration not active.")
        print("To enable:\n  1. Install Ollama from ollama.com")
        print("  2. Run 'ollama serve' in a terminal")
        print("  3. Pull a model: 'ollama pull llama3'")
        print("  4. Re-run this script\n")
        return None


def main():
    if len(sys.argv) < 2:
        print("\n" + "=" * 70)
        print("COGNITIVE QUERY ENGINE - PHASE IV: LLM INTEGRATION")
        print("=" * 70)
        print("\nUsage: python src/core/cognitive_query.py \"Your question here\"\n")
        print("Example queries:")
        print("  1. python src/core/cognitive_query.py \"How does delta verification work?\"")
        print("  2. python src/core/cognitive_query.py \"What hashing algorithm is used?\"")
        print("  3. python src/core/cognitive_query.py \"Explain the XML serialization strategy\"")
        print("\nPrerequisites:")
        print("  - Ollama installed and running: 'ollama serve'")
        print("  - Model available: 'ollama pull llama3'")
        print("\n" + "=" * 70 + "\n")
        sys.exit(1)
        sys.exit(1)

    query = sys.argv[1]
    
    print("\n" + "=" * 70)
    print("COGNITIVE QUERY ENGINE - PHASE IV: LLM INTEGRATION")
    print("=" * 70)
    
    # Initialize Engine
    engine = CognitiveQueryEngine()
    
    # Retrieve Context
    print(f"\n[QUERY] '{query}'")
    context = engine.retrieve_context(query)
    
    if not context:
        print("\n[WARNING] No relevant context found. Try a different query.")
        sys.exit(0)
        
    print(f"\n[OK] Retrieved {len(context)} artifacts\n")
    
    # Construct Prompt
    prompt = engine.construct_prompt(query, context)
    
    # Query LLM
    response = engine.query_llm(prompt)
    
    if response is None:
        # Simulation mode - prompt was displayed
        pass
    else:
        # LLM response received
        print("\n" + "=" * 70)
        print("[RESPONSE] COGNITIVE ENGINE")
        print("=" * 70)
        print(response.strip())
        print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
