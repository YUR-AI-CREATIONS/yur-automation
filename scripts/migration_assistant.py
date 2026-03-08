#!/usr/bin/env python3
"""
Migration Assistant — Migrate existing FranklinOps data to spine-compatible layout.

Transforms existing deployments into universal spine structure.
"""

from __future__ import annotations

import sys
import logging
import shutil
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.spine.config.universal_settings import UniversalSettings
from src.spine.integrity.audit_spine import AuditSpine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> int:
    """Migrate existing FranklinOps deployment to spine."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate FranklinOps deployment to Universal Spine"
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Source FranklinOps data directory (data/franklinops)",
    )
    parser.add_argument(
        "--target-domain",
        default="construction",
        help="Target domain (default: construction)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("\n" + "=" * 60)
    print("Universal Spine — Migration Assistant")
    print("=" * 60 + "\n")

    source_dir = Path(args.source)
    if not source_dir.exists():
        logger.error(f"Source directory not found: {source_dir}")
        return 1

    logger.info(f"Source: {source_dir}")
    logger.info(f"Target domain: {args.target_domain}")

    # Create target settings
    try:
        settings = UniversalSettings(domain=args.target_domain)
        logger.info(f"Target directory: {settings.data_dir}")
    except Exception as e:
        logger.error(f"Failed to create target settings: {e}")
        return 1

    if args.dry_run:
        print("DRY RUN - No changes will be made\n")

    # Migrate directories
    try:
        _migrate_data(source_dir, settings.data_dir, dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1

    print("\n" + "=" * 60)
    if args.dry_run:
        print("Dry run complete. Review above and run without --dry-run to migrate.")
    else:
        print("Migration complete!")
        print(f"\nNext steps:")
        print(f"1. Run universal bootstrap:")
        print(f"   python scripts/universal_bootstrap.py --domain {args.target_domain}")
        print(f"2. Verify data in {settings.data_dir}")
    print("=" * 60 + "\n")

    return 0


def _migrate_data(source: Path, target: Path, dry_run: bool = False) -> None:
    """Migrate data from source to target."""
    logger.info("Starting data migration...")

    # Create target directory
    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created target directory: {target}")
    else:
        logger.info(f"Would create target directory: {target}")

    # Migrate key files
    files_to_migrate = [
        "ops.db",
        "audit.jsonl",
        "doc_index.json",
    ]

    for filename in files_to_migrate:
        source_file = source / filename
        target_file = target / filename

        if source_file.exists():
            if dry_run:
                logger.info(f"Would copy: {source_file} -> {target_file}")
            else:
                try:
                    shutil.copy2(source_file, target_file)
                    logger.info(f"Copied: {filename}")
                except Exception as e:
                    logger.warning(f"Failed to copy {filename}: {e}")
        else:
            logger.debug(f"Source file not found: {source_file}")

    # Migrate subdirectories
    subdirs = ["cache", "indexes"]
    for subdir in subdirs:
        source_subdir = source / subdir
        target_subdir = target / subdir

        if source_subdir.exists():
            if dry_run:
                logger.info(f"Would copy directory: {source_subdir} -> {target_subdir}")
            else:
                try:
                    if target_subdir.exists():
                        shutil.rmtree(target_subdir)
                    shutil.copytree(source_subdir, target_subdir)
                    logger.info(f"Copied directory: {subdir}")
                except Exception as e:
                    logger.warning(f"Failed to copy {subdir}: {e}")
        else:
            logger.debug(f"Source directory not found: {source_subdir}")

    logger.info("Data migration complete")


if __name__ == "__main__":
    sys.exit(main())
