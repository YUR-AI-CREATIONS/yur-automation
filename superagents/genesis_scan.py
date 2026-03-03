"""
GENESIS SCAN HARNESS
Establishes the baseline Blake Birthmark Ledger for the Cognitive Engine.

This harness:
1. Optimizes the environment for maximum hashing performance
2. Performs the Genesis Scan on the target directory
3. Creates the immutable Ground Truth ledger
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.blake_birthmarking import BlakeVault, EnvironmentOptimizer
import logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger("GenesisHarness")

def main():
    """Execute the Genesis Scan."""
    logger.info("=" * 70)
    logger.info("COGNITIVE ENGINE - GENESIS SCAN HARNESS")
    logger.info("=" * 70)
    
    # Phase 0: Environment Optimization
    logger.info("\n[PHASE 0] Environment Optimization")
    EnvironmentOptimizer.optimize_environment()
    
    # Phase B: Genesis Scan
    logger.info("\n[PHASE B] Genesis Scan - Establishing Ground Truth")
    vault = BlakeVault()
    
    # Determine target directory
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    
    # Exclusion patterns optimized for cognitive engine
    exclude_patterns = [
        ".git*",
        "__pycache__",
        "*.pyc",
        "node_modules",
        ".venv",
        "venv",
        ".egg-info",
        "*.egg-info",
        ".pytest_cache",
        ".mypy_cache",
        "*.swp",
        "*.swo",
        "*~",
        ".DS_Store",
        "thumbs.db"
    ]
    
    # Run the Genesis Scan
    ledger = vault.genesis_scan(target_dir, exclude_patterns=exclude_patterns)
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("GENESIS SCAN COMPLETE")
    logger.info("=" * 70)
    logger.info(f"✅ Birthmarks established for {len(ledger)} files")
    logger.info(f"📊 Ledger saved to: {vault.ledger_path}")
    logger.info(f"🔐 Ground Truth locked at {list(ledger.values())[0].timestamp if ledger else 'N/A'}")
    logger.info("\nThe Cognitive Engine is now initialized with an immutable baseline.")
    logger.info("All future ingestions will be Delta-verified against this ledger.")

if __name__ == "__main__":
    main()
