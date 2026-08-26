"""One-time migration from legacy Receipt-Tracker and finance-tracker data dirs."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.paths import get_bank_dir, get_data_dir, get_receipts_db_path, get_receipts_images_dir, repo_root

logger = logging.getLogger(__name__)


def _copy_tree(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dest / item.name
        if item.is_dir():
            if not target.exists():
                shutil.copytree(item, target)
        elif not target.exists():
            shutil.copy2(item, target)


def migrate_legacy_data() -> None:
    """Copy legacy data into the unified app data dir if destinations are empty."""
    bank_dir = get_bank_dir()
    legacy_bank = Path.home() / ".finance-tracker"
    marker = get_data_dir() / ".migrated"

    if marker.exists():
        return

    bank_empty = not any(bank_dir.iterdir()) if bank_dir.exists() else True
    if bank_empty and legacy_bank.exists():
        logger.info("Migrating bank data from %s -> %s", legacy_bank, bank_dir)
        _copy_tree(legacy_bank, bank_dir)

    receipts_db = get_receipts_db_path()
    if not receipts_db.exists():
        candidates = [
            repo_root() / "data" / "receipts.db",
            Path.home() / "TOBEMOVED" / "GitHubRepos" / "Receipt-Tracker" / "data" / "receipts.db",
            Path.home() / "TOBEMOVED" / "GitHubRepos" / "cuddly-potato" / "data" / "receipts.db",
        ]
        for candidate in candidates:
            if candidate.exists():
                logger.info("Migrating receipts DB from %s", candidate)
                shutil.copy2(candidate, receipts_db)
                images_src = candidate.parent / "receipts"
                if images_src.exists():
                    _copy_tree(images_src, get_receipts_images_dir())
                break

    marker.write_text("ok\n", encoding="utf-8")
