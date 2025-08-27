"""
Filesystem operations for scanning directories and computing hashes.
Handles torrent file discovery and data structure analysis.
"""

import hashlib
import os
from pathlib import Path
from typing import List, Tuple


def iter_torrent_files(root: Path) -> List[Path]:
    """Recursively find all .torrent files in a directory."""
    return [p for p in root.rglob("*.torrent") if p.is_file()]


def compute_structure_hash_for_dir(root: Path) -> Tuple[str, List[Tuple[str, int]]]:
    """
    Compute structure hash for a directory.
    
    Builds canonical list of (relative posix path, size) for all regular files under `root`.
    Returns (structure_hash_hex, files_list).
    """
    items: List[Tuple[str, int]] = []
    
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            fp = Path(dirpath) / name
            try:
                if not fp.is_file() or fp.is_symlink():
                    continue
                rel = fp.relative_to(root).as_posix()
                size = fp.stat().st_size
                items.append((rel, int(size)))
            except (OSError, PermissionError):
                continue
    
    # Sort items for canonical representation
    lines = [f"{p}\t{l}" for (p, l) in items]
    lines.sort()
    blob = ("\n".join(lines)).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()
    
    return digest, items


def compute_name_hash_for_file(path: Path) -> str:
    """Compute name hash for a file (SHA256 of filename)."""
    return hashlib.sha256(path.name.encode("utf-8")).hexdigest()


def compute_file_hash(relative_path: str, size: int) -> str:
    """
    Compute hash for a single file entry.
    Hash is SHA256 of "relative_path\tsize" for consistent identification.
    """
    canonical = f"{relative_path}\t{size}".encode('utf-8')
    return hashlib.sha256(canonical).hexdigest()