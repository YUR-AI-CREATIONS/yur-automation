import asyncio
import logging
import fnmatch
import os
from dataclasses import dataclass
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Ingestor")

@dataclass
class FileArtifact:
    path: str
    content: str
    size: int

class IngestionEngine:
    """
    The Sensory Organ of the Oracle.
    Traverses file systems to feed the Cognitive Core.
    """
    def __init__(self, root_path: str, exclude_patterns: List[str] = None):
        self.root_path = root_path
        self.exclude_patterns = exclude_patterns or [".git*", "__pycache__", "*.pyc", "node_modules"]
        self.artifacts: List[FileArtifact] = []

    def _should_exclude(self, path: str) -> bool:
        name = os.path.basename(path)
        return any(fnmatch.fnmatch(name, p) for p in self.exclude_patterns)

    async def ingest(self):
        logger.info(f"Starting ingestion on: {self.root_path}")
        loop = asyncio.get_running_loop()
        
        # Offload blocking IO to thread pool
        await loop.run_in_executor(None, self._walk_and_read)
        
        logger.info(f"Ingestion complete. Captured {len(self.artifacts)} artifacts.")
        return self.artifacts

    def _walk_and_read(self):
        for root, dirs, files in os.walk(self.root_path):
            # In-place filtering of directories to prune traversal
            dirs[:] = [d for d in dirs if not self._should_exclude(os.path.join(root, d))]
            
            for file in files:
                file_path = os.path.join(root, file)
                if self._should_exclude(file_path):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                        self.artifacts.append(FileArtifact(
                            path=file_path,
                            content=content,
                            size=len(content)
                        ))
                except Exception as e:
                    logger.warning(f"Skipping {file_path}: {e}")

if __name__ == "__main__":
    # Quick Test
    engine = IngestionEngine(".")
    asyncio.run(engine.ingest())
