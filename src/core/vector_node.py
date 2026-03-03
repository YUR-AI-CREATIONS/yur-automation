"""
Vector Node: Semantic Indexing & RAG Architecture
Transforms Base64-encoded XML payload into queryable vector space using FAISS
"""

import base64
import xml.etree.ElementTree as ET
import os
import json
import logging
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class VectorNode:
    """
    Transforms cognitive payload into high-dimensional vector space for semantic search.
    
    Workflow:
    1. Load & parse Base64-encoded XML
    2. Extract file contents & metadata (birthmarks)
    3. Generate embeddings using all-MiniLM-L6-v2 (384-dim)
    4. Build FAISS index for efficient similarity search
    5. Persist index + metadata for retrieval
    """

    def __init__(self, payload_path="data/output/cognitive_payload.xml", 
                 index_path="data/output/vector_index.bin"):
        self.payload_path = payload_path
        self.index_path = index_path
        self.metadata_path = index_path.replace(".bin", ".json")
        
        # Initialize embedding model (optimized for speed/accuracy tradeoff)
        logger.info("Loading SentenceTransformer model: all-MiniLM-L6-v2...")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.dimension = 384
        
        self.index = None
        self.artifacts = []
        logger.info("VectorNode initialized successfully.")

    def load_payload(self):
        """
        Parses XML and decodes Base64 content.
        
        Returns:
            list: Artifacts with {path, birthmark, content}
        """
        if not os.path.exists(self.payload_path):
            raise FileNotFoundError(f"Payload not found: {self.payload_path}")
        
        logger.info(f"Loading cognitive payload from: {self.payload_path}")
        tree = ET.parse(self.payload_path)
        root = tree.getroot()
        
        extracted = []
        for file_elem in root.findall('file'):
            path = file_elem.get('path')
            birthmark = file_elem.get('birthmark')
            b64_content = file_elem.text.strip()
            
            try:
                content = base64.b64decode(b64_content).decode('utf-8')
                extracted.append({
                    "path": path,
                    "birthmark": birthmark,
                    "content": content
                })
                logger.debug(f"  ✓ Decoded {path} ({len(content)} chars)")
            except Exception as e:
                logger.warning(f"  ✗ Failed to decode {path}: {e}")
        
        self.artifacts = extracted
        logger.info(f"Extraction complete: {len(extracted)} artifacts ready for vectorization.")
        return extracted

    def build_index(self):
        """
        Generates embeddings and populates FAISS index.
        
        Steps:
        1. Prepare corpus from artifact contents
        2. Encode using SentenceTransformer
        3. Create FAISS index (L2 distance metric)
        4. Persist index + metadata to disk
        """
        if not self.artifacts:
            raise ValueError("No artifacts loaded. Call load_payload() first.")
        
        logger.info(f"Building vector index for {len(self.artifacts)} artifacts...")
        
        # Step 1: Prepare Corpus
        corpus = [art['content'] for art in self.artifacts]
        logger.info(f"Corpus size: {len(corpus)} documents")
        
        # Step 2: Encode embeddings
        logger.info("Generating embeddings using all-MiniLM-L6-v2 (384-dim)...")
        embeddings = self.model.encode(corpus, show_progress_bar=True)
        logger.info(f"Generated {len(embeddings)} embeddings, each {self.dimension}-dimensional")
        
        # Step 3: Build FAISS Index
        logger.info("Initializing FAISS index (IndexFlatL2)...")
        self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(np.array(embeddings).astype('float32'))
        logger.info(f"Index populated with {self.index.ntotal} vectors")
        
        # Step 4: Persist to disk
        logger.info(f"Persisting index to: {self.index_path}")
        faiss.write_index(self.index, self.index_path)
        
        logger.info(f"Persisting metadata to: {self.metadata_path}")
        with open(self.metadata_path, 'w') as f:
            json.dump(self.artifacts, f, indent=2)
        
        logger.info(f"✅ Index built successfully: {self.index.ntotal} vectors stored")

    def query(self, query_text, k=3):
        """
        Semantic search against the codebase.
        
        Args:
            query_text (str): Query in natural language
            k (int): Number of top results to return
            
        Returns:
            list: Results with {score, path, birthmark, snippet}
        """
        # Load index from disk if not in memory
        if not self.index:
            logger.info(f"Loading index from disk: {self.index_path}")
            self.index = faiss.read_index(self.index_path)
            with open(self.metadata_path, 'r') as f:
                self.artifacts = json.load(f)
        
        # Encode query
        logger.info(f"Query: '{query_text}'")
        vec = self.model.encode([query_text])
        
        # Search
        distances, indices = self.index.search(np.array(vec).astype('float32'), k)
        logger.info(f"Search returned {len(indices[0])} results")
        
        # Format results
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1:
                artifact = self.artifacts[idx]
                results.append({
                    "rank": i + 1,
                    "score": float(distances[0][i]),  # L2 distance
                    "similarity": 1.0 / (1.0 + float(distances[0][i])),  # Normalized
                    "path": artifact['path'],
                    "birthmark": artifact['birthmark'],
                    "snippet": artifact['content'][:300] + "..." if len(artifact['content']) > 300 else artifact['content']
                })
        
        return results


if __name__ == "__main__":
    # Test execution
    print("\n=== VECTOR NODE TEST ===\n")
    
    node = VectorNode()
    node.load_payload()
    node.build_index()
    
    # Validation Query
    print("\n[TEST] Query: 'integrity verification mechanism'")
    hits = node.query("How are birthmarks verified for integrity?")
    
    if hits:
        print(f"\n✅ Semantic search successful (top {len(hits)} results):")
        for h in hits:
            print(f"  [{h['rank']}] {h['path']} (L2: {h['score']:.4f}, Similarity: {h['similarity']:.2%})")
            print(f"      Birthmark: {h['birthmark'][:32]}...")
            print(f"      Snippet: {h['snippet'][:60]}...\n")
    else:
        print("❌ No results found")
