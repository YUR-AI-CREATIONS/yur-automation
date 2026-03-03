"""
PHASE II Bootstrap: Cognitive Vectorization Pipeline
Orchestrates the transformation of static XML payload into queryable vector space
"""

import sys
import os
import time
import logging

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.core.vector_node import VectorNode

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def main():
    print("=" * 70)
    print(" PHASE II: COGNITIVE VECTORIZATION & SEMANTIC INDEXING")
    print(" Transform Static XML → Queryable Vector Space (RAG Architecture)")
    print("=" * 70)
    print()
    
    t_start = time.time()
    
    # ==========================================
    # STEP 1: Initialize Vector Node
    # ==========================================
    print("[STEP 1] Initializing Vector Node...")
    try:
        vn = VectorNode(
            payload_path="data/output/cognitive_payload.xml",
            index_path="data/output/vector_index.bin"
        )
        print("         ✅ Vector Node ready\n")
    except Exception as e:
        logger.error(f"Failed to initialize Vector Node: {e}")
        return False
    
    # ==========================================
    # STEP 2: Load Cognitive Payload
    # ==========================================
    print("[STEP 2] Loading Cognitive Payload...")
    try:
        artifacts = vn.load_payload()
        print(f"         ✅ Loaded {len(artifacts)} artifacts\n")
    except Exception as e:
        logger.error(f"Failed to load payload: {e}")
        return False
    
    # ==========================================
    # STEP 3: Generate Embeddings & Build Index
    # ==========================================
    print("[STEP 3] Generating Embeddings (all-MiniLM-L6-v2, 384-dim)...")
    try:
        vn.build_index()
        print("         ✅ Vector index built and persisted\n")
    except Exception as e:
        logger.error(f"Failed to build index: {e}")
        return False
    
    # ==========================================
    # STEP 4: Verification Query
    # ==========================================
    print("[STEP 4] Verification Query: 'How is the genesis ledger verified?'")
    try:
        results = vn.query("How is the genesis ledger verified?", k=3)
        
        if results:
            print("         ✅ Semantic recall SUCCESS\n")
            print("         Top Matches:")
            for r in results:
                print(f"           [{r['rank']}] {r['path']}")
                print(f"               L2 Distance: {r['score']:.4f} | Similarity: {r['similarity']:.2%}")
                print(f"               Birthmark: {r['birthmark'][:40]}...")
                print()
        else:
            print("         ⚠️  No results returned (index may be empty)\n")
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return False
    
    # ==========================================
    # STEP 5: Additional Test Queries
    # ==========================================
    print("[STEP 5] Running additional semantic tests...\n")
    
    test_queries = [
        "Blake3 cryptographic hashing",
        "XML serialization strategy",
        "Delta verification changes"
    ]
    
    for query in test_queries:
        try:
            results = vn.query(query, k=1)
            if results:
                top = results[0]
                print(f"   Query: '{query}'")
                print(f"   → Top Result: {top['path']} (similarity: {top['similarity']:.2%})")
            else:
                print(f"   Query: '{query}' → No results")
        except Exception as e:
            logger.warning(f"   Query '{query}' failed: {e}")
    
    print()
    
    # ==========================================
    # SUMMARY
    # ==========================================
    elapsed = time.time() - t_start
    print("=" * 70)
    print(" PHASE II COMPLETE")
    print("=" * 70)
    print(f"\n✅ Vectorization Pipeline Successful")
    print(f"   - Index Location: data/output/vector_index.bin")
    print(f"   - Metadata Location: data/output/vector_index.json")
    print(f"   - Total Runtime: {elapsed:.2f}s")
    print(f"   - Model: all-MiniLM-L6-v2 (384-dim)")
    print(f"   - Index Type: FAISS IndexFlatL2")
    print(f"   - Vectors Stored: {len(artifacts)}")
    print(f"\n🔍 RAG System Ready for Cognitive Queries\n")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
