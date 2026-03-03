"""
BLAKE3 BIRTHMARKING ENGINE
Content-Addressable Identity System for the Cognitive Engine

AUTHOR: Cryptographic Architecture Team
PURPOSE: Establish immutable content fingerprints (Birthmarks) to prevent
duplicate processing and enable efficient Delta Verification workflows.
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BlakeEngine")

@dataclass
class BirthMark:
    """Immutable fingerprint of a single artifact."""
    path: str
    hash_blake3: str  # BLAKE3 hash (if available, else SHA256)
    size: int
    modified_at: float
    timestamp_scanned: float

@dataclass
class LedgerEntry:
    """Genesis ledger entry - establishes baseline Ground Truth."""
    path: str
    hash_value: str
    size: int
    timestamp: float
    is_directory: bool = False

class BlakeVault:
    """
    BLAKE3 Cryptographic Container.
    Manages the Genesis Ledger and Delta Verification workflows.
    """
    
    def __init__(self, ledger_path: str = "data/output/genesis_ledger.json"):
        self.ledger_path = ledger_path
        self.genesis_ledger: Dict[str, LedgerEntry] = {}
        self.birthmarks: Dict[str, BirthMark] = {}
        self._load_ledger()
        logger.info(f"BlakeVault initialized. Ledger: {ledger_path}")
    
    def _compute_hash(self, filepath: str) -> str:
        """
        Compute BLAKE3 hash of a file.
        Falls back to SHA256 if BLAKE3 is not available.
        """
        try:
            # Attempt BLAKE3 (if installed via blake3 package)
            import blake3
            with open(filepath, 'rb') as f:
                return blake3.blake3(f.read()).hexdigest()
        except ImportError:
            # Fallback to SHA256 (always available)
            sha256_hash = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
    
    def _load_ledger(self):
        """Load the Genesis Ledger from disk if it exists."""
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for entry_dict in data.get('ledger', []):
                        entry = LedgerEntry(**entry_dict)
                        self.genesis_ledger[entry.path] = entry
                logger.info(f"Genesis Ledger loaded: {len(self.genesis_ledger)} entries")
            except Exception as e:
                logger.warning(f"Failed to load ledger: {e}")
    
    def _save_ledger(self):
        """Persist the Genesis Ledger to disk."""
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        data = {
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'ledger': [asdict(entry) for entry in self.genesis_ledger.values()]
        }
        with open(self.ledger_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Genesis Ledger saved: {len(self.genesis_ledger)} entries")
    
    def genesis_scan(self, root_path: str, exclude_patterns: List[str] = None) -> Dict[str, LedgerEntry]:
        """
        Phase B: Establish the Ground Truth.
        Traverses the directory tree and computes baseline hashes for all files.
        """
        if exclude_patterns is None:
            exclude_patterns = [".git*", "__pycache__", "*.pyc", "node_modules", ".venv", "venv", "*.egg-info"]
        
        logger.info(f"[GENESIS SCAN] Initiating on: {root_path}")
        start_time = time.time()
        
        self.genesis_ledger = {}
        
        for root, dirs, files in os.walk(root_path):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if not self._should_exclude(os.path.join(root, d), exclude_patterns)]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                if self._should_exclude(file_path, exclude_patterns):
                    continue
                
                try:
                    stat = os.stat(file_path)
                    file_hash = self._compute_hash(file_path)
                    
                    # Normalize path for cross-platform consistency
                    rel_path = os.path.relpath(file_path, root_path).replace('\\', '/')
                    
                    entry = LedgerEntry(
                        path=rel_path,
                        hash_value=file_hash,
                        size=stat.st_size,
                        timestamp=time.time(),
                        is_directory=False
                    )
                    self.genesis_ledger[rel_path] = entry
                    
                except Exception as e:
                    logger.warning(f"Failed to hash {file_path}: {e}")
        
        duration = time.time() - start_time
        logger.info(f"[GENESIS SCAN] Complete. {len(self.genesis_ledger)} files hashed in {duration:.2f}s")
        
        # Persist the ledger
        self._save_ledger()
        
        return self.genesis_ledger
    
    def delta_verification(self, root_path: str, exclude_patterns: List[str] = None) -> Dict[str, str]:
        """
        Phase C: Delta Verification
        Compare current file hashes against the Genesis Ledger.
        Return a dictionary of {path: status} where status is:
        - 'NEW': Not in genesis ledger
        - 'MODIFIED': Hash differs from ledger
        - 'UNCHANGED': Hash matches ledger (Skip)
        """
        if not self.genesis_ledger:
            logger.warning("Genesis Ledger is empty. Run genesis_scan() first.")
            return {}
        
        if exclude_patterns is None:
            exclude_patterns = [".git*", "__pycache__", "*.pyc", "node_modules", ".venv", "venv"]
        
        logger.info("[DELTA VERIFICATION] Comparing current state against Genesis Ledger...")
        changes = {}
        
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if not self._should_exclude(os.path.join(root, d), exclude_patterns)]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                if self._should_exclude(file_path, exclude_patterns):
                    continue
                
                try:
                    rel_path = os.path.relpath(file_path, root_path).replace('\\', '/')
                    current_hash = self._compute_hash(file_path)
                    
                    if rel_path not in self.genesis_ledger:
                        changes[rel_path] = 'NEW'
                    elif self.genesis_ledger[rel_path].hash_value != current_hash:
                        changes[rel_path] = 'MODIFIED'
                    # else: UNCHANGED (not added to changes dict, Zero Cost)
                    
                except Exception as e:
                    logger.warning(f"Failed to verify {file_path}: {e}")
        
        # Identify deleted files
        for ledger_path in self.genesis_ledger:
            full_path = os.path.join(root_path, ledger_path.replace('/', os.sep))
            if not os.path.exists(full_path):
                changes[ledger_path] = 'DELETED'
        
        logger.info(f"[DELTA VERIFICATION] Changes detected:")
        logger.info(f"  NEW: {sum(1 for s in changes.values() if s == 'NEW')}")
        logger.info(f"  MODIFIED: {sum(1 for s in changes.values() if s == 'MODIFIED')}")
        logger.info(f"  DELETED: {sum(1 for s in changes.values() if s == 'DELETED')}")
        
        return changes
    
    @staticmethod
    def _should_exclude(path: str, patterns: List[str]) -> bool:
        """Check if a path matches any exclusion pattern."""
        import fnmatch
        name = os.path.basename(path)
        return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)

class EnvironmentOptimizer:
    """
    Configures the system environment for maximum Blake Birthmarking performance.
    """
    
    @staticmethod
    def verify_cpu_capabilities() -> Dict[str, bool]:
        """Check for AVX2/AVX-512 CPU instruction sets."""
        import platform
        import subprocess
        
        capabilities = {
            'avx2': False,
            'avx512': False,
            'platform': platform.machine()
        }
        
        try:
            if platform.system() == "Windows":
                # Windows CPU info check
                result = subprocess.run(
                    ["wmic", "cpu", "get", "name"],
                    capture_output=True,
                    text=True
                )
                cpu_name = result.stdout if result.returncode == 0 else "Unknown"
                logger.info(f"CPU: {cpu_name.strip()}")
                # Note: Detailed AVX detection on Windows requires cpuid libraries
                capabilities['avx2'] = True  # Assume modern CPU
                
            else:
                # Linux/macOS
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'avx2' in line:
                            capabilities['avx2'] = True
                        if 'avx512' in line:
                            capabilities['avx512'] = True
        except Exception as e:
            logger.warning(f"Could not verify CPU capabilities: {e}")
        
        return capabilities
    
    @staticmethod
    def optimize_environment():
        """
        Apply OS-level and Python-level optimizations for hashing performance.
        """
        logger.info("[ENVIRONMENT OPTIMIZATION] Applying tunings...")
        
        # Check CPU capabilities
        caps = EnvironmentOptimizer.verify_cpu_capabilities()
        logger.info(f"CPU Capabilities: {caps}")
        
        # Python environment variables for parallelism
        os.environ['RAYON_NUM_THREADS'] = str(os.cpu_count() or 4)
        logger.info(f"RAYON_NUM_THREADS: {os.environ['RAYON_NUM_THREADS']}")
        
        # Note: On Windows, ulimit doesn't apply. On Unix, it should be set in shell.
        # ulimit -n 65535
        
        logger.info("[ENVIRONMENT OPTIMIZATION] Complete")
