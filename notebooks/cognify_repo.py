"""
cognify_repo.py — Ingest a local repo into Cognee's knowledge graph.

Usage (from notebook):
    from cognify_repo import cognify_repo
    await cognify_repo(r"C:\\dev\\myrepo", dataset_name="my_dataset")
"""

from pathlib import Path
from typing import Optional, Set

import cognee


# Defaults
DEFAULT_IGNORE_DIRS: Set[str] = {
    ".localwork", ".git", "__pycache__", ".ipynb_checkpoints",
    "deprecated", "node_modules", ".venv", "venv",
}
DEFAULT_INCLUDE_EXTENSIONS: Set[str] = {
    ".py", ".ipynb", ".yml", ".yaml", ".json", ".md",
}
DEFAULT_IGNORE_FILES: Set[str] = {
    ".gitignore", "package.json", "package-lock.json",
}
DEFAULT_MAX_FILE_SIZE = 100_000  # 100 KB


def _should_include(
    path: Path,
    repo_root: Path,
    ignore_dirs: Set[str],
    include_extensions: Set[str],
    ignore_files: Set[str],
    max_file_size: int,
) -> bool:
    """Return True if the file should be ingested."""
    for part in path.relative_to(repo_root).parts:
        if part in ignore_dirs:
            return False
    if path.name in ignore_files:
        return False
    if path.suffix.lower() not in include_extensions:
        return False
    try:
        size = path.stat().st_size
        if size == 0 or size > max_file_size:
            return False
    except OSError:
        return False
    return True


async def cognify_repo(
    repo_path: str,
    dataset_name: str = "repo",
    reset: bool = False,
    ignore_dirs: Optional[Set[str]] = None,
    include_extensions: Optional[Set[str]] = None,
    ignore_files: Optional[Set[str]] = None,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
):
    """
    Ingest all matching files from a local repo into Cognee, then cognify.

    Args:
        repo_path: Absolute path to the repo root.
        dataset_name: Cognee dataset name.
        reset: If True, prune all data/system state before ingesting.
        ignore_dirs: Directory names to skip (defaults provided).
        include_extensions: File extensions to include (defaults provided).
        ignore_files: File names to skip (defaults provided).
        max_file_size: Skip files larger than this (bytes).
    """
    root = Path(repo_path)
    if not root.is_dir():
        raise FileNotFoundError(f"Repo path does not exist: {root}")

    _ignore_dirs = ignore_dirs or DEFAULT_IGNORE_DIRS
    _include_ext = include_extensions or DEFAULT_INCLUDE_EXTENSIONS
    _ignore_files = ignore_files or DEFAULT_IGNORE_FILES

    # ── Optional reset ──────────────────────────────────────────────
    if reset:
        print("🗑️  Resetting Cognee data and system state...")
        await cognee.prune.prune_data()
        await cognee.prune.prune_system(metadata=True)
        print("   Done.\n")

    # ── Discover files ──────────────────────────────────────────────
    files = sorted(
        f for f in root.rglob("*")
        if f.is_file()
        and _should_include(f, root, _ignore_dirs, _include_ext, _ignore_files, max_file_size)
    )
    print(f"📂 Repo: {root}")
    print(f"✅ Found {len(files)} files to ingest\n")

    # ── Add files by absolute path ──────────────────────────────────
    # Passing absolute paths lets cognee handle reading/classification
    # natively (avoids the "File:" urlparse bug with raw text).
    added = 0
    for fpath in files:
        abs_str = str(fpath)
        try:
            await cognee.add(abs_str, dataset_name=dataset_name)
            print(f"  ✓ {fpath.relative_to(root)}")
            added += 1
        except Exception as e:
            print(f"  ✗ {fpath.relative_to(root)}  — {e}")

    print(f"\n📥 Added {added}/{len(files)} files")

    # ── Cognify ─────────────────────────────────────────────────────
    print("⚙️  Building Knowledge Graph...")
    await cognee.cognify(datasets=[dataset_name])
    print(f"✅ Done! Dataset: {dataset_name}")
