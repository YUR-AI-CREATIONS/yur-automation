#!/usr/bin/env python3
"""
Universal Bootstrap — Initialize spine for any domain.

Sets up DB, audit system, evidence vault, and ports for new deployment.
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.spine.config.universal_settings import UniversalSettings
from src.spine.integrity.audit_spine import AuditSpine
from src.spine.integrity.evidence_vault import EvidenceVault
from src.spine.orchestration.flow_registry import UniversalFlowRegistry
from src.spine.orchestration.port_manager import PortManager, PortType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> int:
    """Initialize universal spine for a domain."""
    import argparse

    parser = argparse.ArgumentParser(description="Initialize Universal Spine")
    parser.add_argument(
        "--domain",
        default="generic",
        help="Domain to initialize (generic, construction, healthcare, finance)",
    )
    parser.add_argument(
        "--data-dir",
        help="Override data directory",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info(f"Initializing Universal Spine for domain: {args.domain}")

    # Load settings
    try:
        settings = UniversalSettings(
            domain=args.domain,
            profile_overrides={"data_dir": args.data_dir} if args.data_dir else None,
        )
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        return 1

    # Validate startup
    errs = settings.validate_startup()
    if errs:
        for err in errs:
            logger.warning(err)

    logger.info(f"Settings: {settings.to_dict()}")

    # Initialize data directories
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created data directory: {settings.data_dir}")
    except Exception as e:
        logger.error(f"Failed to create data directory: {e}")
        return 1

    # Initialize audit spine
    try:
        audit = AuditSpine(str(settings.db_path), str(settings.audit_jsonl_path))
        logger.info("Initialized audit spine")
    except Exception as e:
        logger.error(f"Failed to initialize audit spine: {e}")
        return 1

    # Initialize evidence vault
    try:
        vault = EvidenceVault(str(settings.db_path))
        logger.info("Initialized evidence vault")
    except Exception as e:
        logger.error(f"Failed to initialize evidence vault: {e}")
        return 1

    # Initialize flow registry
    try:
        registry = UniversalFlowRegistry()
        logger.info("Initialized flow registry")
    except Exception as e:
        logger.error(f"Failed to initialize flow registry: {e}")
        return 1

    # Initialize port manager
    try:
        pm = PortManager()
        logger.info("Initialized port manager")
    except Exception as e:
        logger.error(f"Failed to initialize port manager: {e}")
        return 1

    logger.info(f"Universal Spine bootstrap complete for domain '{args.domain}'")
    logger.info(f"Data directory: {settings.data_dir}")
    logger.info(f"DB path: {settings.db_path}")
    logger.info(f"Audit log: {settings.audit_jsonl_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
