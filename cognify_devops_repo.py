#!/usr/bin/env python
"""
Cognify a DevOps repository intelligently.

Scans a repo, filters for relevant DevOps files, and ingests into Cognee
with context (file type, purpose, tags). Ignores noise (.venv, .git, etc).

Usage:
    python cognify_devops_repo.py /path/to/repo [--dataset myrepo] [--dry-run]
"""

import asyncio
import argparse
import os
from pathlib import Path
from typing import List, Tuple

# Add cognee to path if running from repo root
import sys
sys.path.insert(0, str(Path(__file__).parent))

import cognee


# File patterns to include (DevOps-relevant)
DEVOPS_PATTERNS = {
    "terraform": ["*.tf", "*.tfvars"],
    "kubernetes": ["*.yaml", "*.yml"],  # k8s manifests
    "ansible": ["*.yaml", "*.yml", "*.j2"],  # Ansible playbooks
    "helm": ["Chart.yaml", "values.yaml", "*.yaml"],
    "scripts": ["*.sh", "*.ps1", "*.bash"],
    "docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
    "iac": ["*.bicep", "*.json"],  # ARM, Bicep
    "ci_cd": [".github/workflows/*.yaml", ".gitlab-ci.yml", "Jenkinsfile", ".circleci/config.yml"],
    "config": ["*.conf", "*.cfg", "*.ini", "*.toml"],
    "python": ["*.py"],  # Infrastructure as code scripts
    "docs": ["README.md", "*.md"],
}

# Paths to ignore (noise/dependencies)
IGNORE_DIRS = {
    ".venv", "venv", ".env",
    ".git", ".github",  # Git history
    "__pycache__", ".pytest_cache", ".mypy_cache",
    "node_modules", "dist", "build",
    ".terraform", ".terraform.lock.hcl",
    ".env", ".env.local", ".env.*.local",
    "secrets", ".secrets",
}

IGNORE_FILES = {
    ".DS_Store", "*.pyc", "*.pyo", "*.egg-info", "*.lock",
}


def should_ignore(path: Path) -> bool:
    """Check if path should be ignored."""
    # Check if any parent directory is in ignore list
    for part in path.parts:
        if part in IGNORE_DIRS:
            return True
    
    # Check filename patterns
    for pattern in IGNORE_FILES:
        if path.match(pattern):
            return True
    
    return False


def find_devops_files(repo_path: Path) -> List[Tuple[Path, str]]:
    """Find relevant DevOps files in repo. Returns list of (path, file_type)."""
    files = []
    
    for pattern_type, patterns in DEVOPS_PATTERNS.items():
        for pattern in patterns:
            for match in repo_path.glob(f"**/{pattern}"):
                if match.is_file() and not should_ignore(match):
                    files.append((match, pattern_type))
    
    return files


async def cognify_repo(
    repo_path: str,
    dataset_name: str = "devops_repo",
    dry_run: bool = False
) -> None:
    """Cognify a DevOps repository."""
    
    repo = Path(repo_path).resolve()
    if not repo.exists():
        print(f"❌ Repo not found: {repo}")
        return
    
    if not repo.is_dir():
        print(f"❌ Not a directory: {repo}")
        return
    
    print(f"📂 Scanning repo: {repo}")
    
    # Find files
    files = find_devops_files(repo)
    if not files:
        print("❌ No DevOps files found. Check repo structure.")
        return
    
    print(f"✅ Found {len(files)} DevOps files:")
    for fpath, ftype in files:
        rel_path = fpath.relative_to(repo)
        print(f"  [{ftype:12}] {rel_path}")
    
    if dry_run:
        print("\n🏃 Dry-run mode: no changes made.")
        return
    
    # Read and cognify each file
    print(f"\n🧠 Cognifying into dataset '{dataset_name}'...")
    
    for fpath, ftype in files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            # Skip empty files
            if not content.strip():
                continue
            
            rel_path = fpath.relative_to(repo)
            context = f"File: {rel_path} | Type: {ftype} | Repo: {repo.name}"
            
            # Truncate very large files
            if len(content) > 50000:
                content = content[:50000] + "\n... [truncated]"
            
            text = f"{context}\n\n{content}"
            
            await cognee.remember(text, dataset_name=dataset_name)
            print(f"  ✓ {rel_path}")
        
        except Exception as e:
            print(f"  ✗ {rel_path}: {e}")
    
    print(f"\n✅ Done! Dataset: {dataset_name}")
    print(f"   Query with: cognee-cli recall 'question' --dataset {dataset_name}")


def main():
    parser = argparse.ArgumentParser(
        description="Cognify a DevOps repository intelligently"
    )
    parser.add_argument(
        "repo_path",
        help="Path to DevOps repository"
    )
    parser.add_argument(
        "--dataset",
        default="devops_repo",
        help="Cognee dataset name (default: devops_repo)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cognified without making changes"
    )
    
    args = parser.parse_args()
    
    asyncio.run(cognify_repo(
        args.repo_path,
        dataset_name=args.dataset,
        dry_run=args.dry_run
    ))


if __name__ == "__main__":
    main()
