
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.ingestor import IngestionEngine, FileArtifact
from src.core.blake_birthmarking import BlakeVault
import asyncio
import base64
import hashlib

class CognitiveNode:
    """
    The Logic Core.
    Orchestrates the 'Harmonized DNA Chain' (Oracle -> Cipher -> Flow).
    """
    
    @staticmethod
    def _escape_xml_attr(text: str) -> str:
        """Escape XML attribute values."""
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    
    @staticmethod
    def _compute_hash(content: str) -> str:
        """Compute SHA256 hash of content as birthmark."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    @staticmethod
    def serialize_context(artifacts: list) -> str:
        """
        Serialize artifacts into well-formed XML with base64-encoded content.
        Each artifact includes its Blake Birthmark (SHA256 hash) for verification.
        Base64 ensures NO possible XML injection or escaping issues.
        """
        buffer = ['<?xml version="1.0" encoding="UTF-8"?>']
        buffer.append('<cognitive_context>')
        
        for art in artifacts:
            # Escape the path attribute
            safe_path = CognitiveNode._escape_xml_attr(art.path)
            
            # Compute the Blake Birthmark (content hash)
            birthmark = CognitiveNode._compute_hash(art.content)
            
            # Base64 encode the content for maximum safety
            encoded_content = base64.b64encode(art.content.encode('utf-8')).decode('ascii')
            
            buffer.append(f'  <file path="{safe_path}" size="{art.size}" encoding="base64" birthmark="{birthmark}">')
            buffer.append(f'    {encoded_content}')
            buffer.append('  </file>')
        
        buffer.append('</cognitive_context>')
        return '\n'.join(buffer)
    
    async def run_bootstrap(self, target_dir: str):
        print(f"⚡ Bootstrapping Cognitive Node on: {target_dir}")
        
        # 1. Ingest (Sensory Input)
        engine = IngestionEngine(target_dir)
        artifacts = await engine.ingest()
        
        # 1b. Compute Birthmarks (Blake Identity)
        print(f"🔐 Computing Blake Birthmarks for {len(artifacts)} artifacts...")
        for art in artifacts:
            birthmark = self._compute_hash(art.content)
            print(f"   ✓ {art.path[:40]:40} → {birthmark[:16]}...")
        
        # 2. Process (Cognitive Digestion)
        payload = self.serialize_context(artifacts)
        
        # 3. Output (State Persistence)
        output_path = "data/output/cognitive_payload.xml"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(payload)
            
        print(f"✅ Context Serialized: {len(payload)} chars.")
        print(f"💾 Payload saved to: {output_path}")
        print(f"📊 Birthmarks embedded in XML for content-addressable verification.")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    node = CognitiveNode()
    asyncio.run(node.run_bootstrap(target))
