"""
DELTA VERIFICATION HARNESS
Compares current state against the Genesis Ledger to identify changes.

This harness:
1. Loads the existing Genesis Ledger
2. Scans the current state of files
3. Identifies NEW, MODIFIED, and DELETED artifacts
4. Reports changes for targeted processing
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.blake_birthmarking import BlakeVault
import logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger("DeltaVerification")

def main():
    """Execute Delta Verification."""
    logger.info("=" * 70)
    logger.info("COGNITIVE ENGINE - DELTA VERIFICATION")
    logger.info("=" * 70)
    
    vault = BlakeVault()
    
    if not vault.genesis_ledger:
        logger.error("❌ No Genesis Ledger found. Run genesis_scan.py first.")
        return
    
    # Determine target directory
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    
    # Exclusion patterns
    exclude_patterns = [
        ".git*",
        "__pycache__",
        "*.pyc",
        "node_modules",
        ".venv",
        "venv",
        ".egg-info",
        "*.egg-info"
    ]
    
    # Run Delta Verification
    logger.info("\n[PHASE C] Delta Verification - Comparing against Genesis Ledger")
    changes = vault.delta_verification(target_dir, exclude_patterns=exclude_patterns)
    
    # Detailed reporting
    logger.info("\n" + "=" * 70)
    logger.info("DELTA VERIFICATION RESULTS")
    logger.info("=" * 70)
    
    if not changes:
        logger.info("✅ No changes detected. System in consistent state.")
    else:
        # Group by status
        new_files = {p: s for p, s in changes.items() if s == 'NEW'}
        modified_files = {p: s for p, s in changes.items() if s == 'MODIFIED'}
        deleted_files = {p: s for p, s in changes.items() if s == 'DELETED'}
        
        if new_files:
            logger.info("\n📝 NEW FILES:")
            for path in sorted(new_files.keys()):
                logger.info(f"  + {path}")
        
        if modified_files:
            logger.info("\n✏️  MODIFIED FILES:")
            for path in sorted(modified_files.keys()):
                logger.info(f"  ~ {path}")
        
        if deleted_files:
            logger.info("\n🗑️  DELETED FILES:")
            for path in sorted(deleted_files.keys()):
                logger.info(f"  - {path}")
    
    # Implementation directive
    logger.info("\n" + "=" * 70)
    logger.info("IMPLEMENTATION DIRECTIVE")
    logger.info("=" * 70)
    logger.info("✅ Only modified/new artifacts require processing.")
    logger.info(f"⏭️  Skip processing for {len(vault.genesis_ledger) - len(changes)} unchanged files (Zero Cost).")
    logger.info("🔄 Forward {" + str(len(new_files) + len(modified_files)) + "} artifacts to cognitive pipeline.")

if __name__ == "__main__":
    main()
