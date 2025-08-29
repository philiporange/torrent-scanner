"""
Main scanning logic for torrent indexing and data matching.
Orchestrates the scanning process using Redis for fast lookups.
Supports file-based matching to handle merged folders where multiple torrents
with identical names are combined into a single directory.
"""

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Callable

from .models import init_database, close_database, add_match, fetch_all_matches, fetch_files_for_torrent, Torrent, Match
from .torrent import parse_torrent, save_torrent_meta
from .filesystem import iter_torrent_files, compute_structure_hash_for_dir, compute_name_hash_for_file, compute_file_hash


def get_redis(redis_path: str):
    """Get Redis client for fast lookups."""
    try:
        from redislite import Redis  # type: ignore
    except Exception as e:
        raise ImportError(f"redislite is required. Install with `pip install redislite`. Import error: {e}")
    return Redis(redis_path)


def redis_index_torrent(rds, torrent: Torrent):
    """Index a torrent in Redis for fast matching."""
    # Name hash -> set of info_hashes (for quick filtering)
    rds.sadd(f"name:{torrent.name_hash}", torrent.info_hash)
    
    # For each file in the torrent, index file_hash -> info_hash
    for file in torrent.files:
        rds.sadd(f"file:{file.file_hash}", torrent.info_hash)
    
    # Store file count for quick validation
    rds.set(f"filecount:{torrent.info_hash}", len(list(torrent.files)))
    
    # Store metadata
    small = {
        "name": torrent.name,
        "is_multi": torrent.is_multi,
    }
    rds.set(f"info:{torrent.info_hash}", json.dumps(small))


def redis_record_match(rds, info_hash: str, data_path: str):
    """Record a match in Redis."""
    rds.sadd(f"matched:{info_hash}", str(Path(data_path).resolve()))


def redis_lookup_structure(rds, structure_hash: str) -> List[str]:
    """Look up torrents by structure hash."""
    return [s.decode("utf-8") if isinstance(s, (bytes, bytearray)) else s
            for s in rds.smembers(f"structure:{structure_hash}")]


def redis_lookup_single(rds, name_hash: str, size: int) -> List[str]:
    """Look up single-file torrents by name hash and size."""
    return [s.decode("utf-8") if isinstance(s, (bytes, bytearray)) else s
            for s in rds.smembers(f"single:{name_hash}:{size}")]


def check_directory_for_matches(rds, directory: Path) -> List[tuple]:
    """
    Check if a directory contains all files for any torrents.
    Returns list of (info_hash, directory_path) for complete matches.
    """
    matches = []
    
    # First, check if this directory name matches any torrent names
    dir_name_hash = hashlib.sha256(directory.name.encode('utf-8')).hexdigest()
    candidate_info_hashes = rds.smembers(f"name:{dir_name_hash}")
    
    if not candidate_info_hashes:
        return matches  # No torrents with this name, skip expensive checks
    
    # Collect all files in the directory with their hashes
    present_files = {}  # file_hash -> (path, size)
    for entry in directory.rglob("*"):
        if entry.is_file() and not entry.is_symlink():
            try:
                rel_path = entry.relative_to(directory).as_posix()
                size = entry.stat().st_size
                file_hash = compute_file_hash(rel_path, size)
                present_files[file_hash] = (rel_path, size)
            except (OSError, PermissionError):
                continue
    
    # For each candidate torrent, check if ALL its files are present
    for info_hash_bytes in candidate_info_hashes:
        info_hash = info_hash_bytes.decode('utf-8') if isinstance(info_hash_bytes, bytes) else info_hash_bytes
        
        # Get expected file count
        expected_count = rds.get(f"filecount:{info_hash}")
        if not expected_count:
            continue
        expected_count = int(expected_count)
        
        # Get torrent from database to check files
        try:
            torrent = Torrent.get(Torrent.info_hash == info_hash)
            torrent_files = list(torrent.files)
            
            # Check if all files are present
            all_present = True
            for tf in torrent_files:
                if tf.file_hash not in present_files:
                    all_present = False
                    break
            
            if all_present and len(torrent_files) == expected_count:
                matches.append((info_hash, directory))
        except Torrent.DoesNotExist:
            continue
    
    return matches


@dataclass
class ScanConfig:
    """Configuration for a scan operation."""
    db_path: Path
    redis_path: Path
    directories: List[Path]
    matches_jsonl: Optional[Path] = None
    progress_callback: Optional[Callable[[str, int, int], None]] = None


def get_info(db_path: Path) -> dict:
    """
    Get information about the torrent database.
    
    Returns a dictionary with statistics including:
    - total_torrents: Number of torrents indexed
    - matched_torrents: Number of torrents that have matches
    - unmatched_torrents: Number of torrents with no matches
    - total_matches: Total number of matches (can be > matched_torrents due to multiple paths)
    - single_file_torrents: Number of single-file torrents
    - multi_file_torrents: Number of multi-file torrents
    - total_size_bytes: Total size of all indexed torrents
    """
    init_database(db_path)
    
    try:
        from peewee import fn
        
        # Get total torrent count
        total_torrents = Torrent.select().count()
        
        # Get count of torrents with matches vs without
        matched_torrent_ids = (Torrent
                              .select(Torrent.id)
                              .join(Match)
                              .distinct())
        matched_count = matched_torrent_ids.count()
        unmatched_count = total_torrents - matched_count
        
        # Get total match count
        total_matches = Match.select().count()
        
        # Get single vs multi file counts
        single_file_count = Torrent.select().where(Torrent.is_multi == False).count()
        multi_file_count = Torrent.select().where(Torrent.is_multi == True).count()
        
        # Get total size
        total_size = (Torrent
                     .select(fn.SUM(Torrent.total_length))
                     .scalar()) or 0
        
        return {
            'total_torrents': total_torrents,
            'matched_torrents': matched_count,
            'unmatched_torrents': unmatched_count,
            'total_matches': total_matches,
            'single_file_torrents': single_file_count,
            'multi_file_torrents': multi_file_count,
            'total_size_bytes': int(total_size),
        }
    
    finally:
        close_database()


def scan_torrents(cfg: ScanConfig, _skip_init: bool = False, _rds=None) -> dict:
    """
    Scan for .torrent files and ingest them into the database.
    
    This function:
    1) Discovers all .torrent files in the specified directories
    2) Parses them and extracts metadata
    3) Saves new torrents to the database and indexes them in Redis
    """
    # Initialize database (unless already done)
    if not _skip_init:
        init_database(cfg.db_path)
    # Use provided Redis connection or create new one
    rds = _rds if _rds is not None else get_redis(str(cfg.redis_path))

    def progress(message: str, current: int, total: int):
        if cfg.progress_callback:
            cfg.progress_callback(message, current, total)

    try:
        # 1) Ingest new .torrent files from all directories
        progress("Discovering torrent files", 0, 0)
        all_torrent_paths = []
        for directory in cfg.directories:
            all_torrent_paths.extend(iter_torrent_files(directory))
        
        progress("Processing torrent files", 0, len(all_torrent_paths))
        processed = 0
        new_torrents = 0
        
        for i, tp in enumerate(all_torrent_paths, 1):
            name = tp.name[:40] + "..." if len(tp.name) > 43 else tp.name
            name = name.ljust(43)  # Pad to consistent width
            progress(f"Processing {name} ({new_torrents} new)", i, len(all_torrent_paths))
            try:
                b = tp.read_bytes()
            except Exception as e:
                progress(f"Warning: failed to read {name}", i, len(all_torrent_paths))
                continue
            
            try:
                meta = parse_torrent(b)
            except Exception as e:
                progress(f"Warning: failed to parse {name}", i, len(all_torrent_paths))
                continue

            # Save to database if new
            torrent = save_torrent_meta(meta, str(tp.resolve()))
            if torrent is not None:
                redis_index_torrent(rds, torrent)
                new_torrents += 1
            processed += 1

        progress(f"Torrent scan complete - {processed} processed, {new_torrents} new", 1, 1)

        return {
            'processed': processed,
            'new': new_torrents
        }

    finally:
        # Cleanup (only if we created our own Redis connection)
        if _rds is None:
            try:
                rds.close()
            except Exception:
                pass
            close_database()


def scan_files(cfg: ScanConfig, _skip_init: bool = False, _rds=None) -> None:
    """
    Scan for data files that match existing torrents in the database.
    
    This function:
    1) Scans directories for data matches against existing torrents
    2) Records matches between torrents and filesystem data
    3) Writes JSONL output if requested
    """
    # Initialize database (unless already done)
    if not _skip_init:
        init_database(cfg.db_path)
    # Use provided Redis connection or create new one
    rds = _rds if _rds is not None else get_redis(str(cfg.redis_path))

    def progress(message: str, current: int, total: int):
        if cfg.progress_callback:
            cfg.progress_callback(message, current, total)
    
    # Track matches found during scan
    matches_found = 0

    try:
        # Scan all directories for data matches
        progress("Scanning for matches", 0, 0)
        
        # Collect all directories (not files) to check
        directories_to_check = set()
        for scan_dir in cfg.directories:
            for entry in scan_dir.rglob("*"):
                if entry.is_dir() and not entry.is_symlink():
                    directories_to_check.add(entry)
        
        directories_list = list(directories_to_check)
        progress("Checking directories for matches", 0, len(directories_list))
        
        for i, directory in enumerate(directories_list, 1):
            # Handle invalid UTF-8 characters in directory names
            try:
                raw_name = directory.name
                # Try to encode/decode to catch surrogate characters
                raw_name.encode('utf-8')
                dir_name = raw_name
            except UnicodeEncodeError:
                # Replace invalid characters with safe alternatives
                dir_name = directory.name.encode('utf-8', errors='replace').decode('utf-8')
            
            dir_name = dir_name[:40] + "..." if len(dir_name) > 43 else dir_name
            dir_name = dir_name.ljust(43)
            progress(f"Checking {dir_name} ({matches_found} matches)", i, len(directories_list))
            
            try:
                # Check this directory for complete torrent matches
                dir_matches = check_directory_for_matches(rds, directory)
                
                for info_hash, matched_dir in dir_matches:
                    added = add_match(info_hash, str(matched_dir))
                    if added:
                        matches_found += 1
                        redis_record_match(rds, info_hash, str(matched_dir))
            except Exception as e:
                continue
        
        # Also check for single-file torrents at the root level of scan directories
        progress("Checking for single-file torrents", 0, len(cfg.directories))
        for scan_dir in cfg.directories:
            for entry in scan_dir.iterdir():
                if entry.is_file() and not entry.is_symlink():
                    try:
                        size = entry.stat().st_size
                        name_hash = compute_name_hash_for_file(entry)
                        file_hash = compute_file_hash(entry.name, size)
                        
                        # Check if this matches any single-file torrent
                        candidates = rds.smembers(f"file:{file_hash}")
                        for info_hash_bytes in candidates:
                            info_hash = info_hash_bytes.decode('utf-8') if isinstance(info_hash_bytes, bytes) else info_hash_bytes
                            
                            # Verify it's actually a single-file torrent with matching name
                            try:
                                torrent = Torrent.get(Torrent.info_hash == info_hash)
                                if not torrent.is_multi and torrent.name_hash == name_hash:
                                    added = add_match(info_hash, str(entry))
                                    if added:
                                        matches_found += 1
                                        redis_record_match(rds, info_hash, str(entry))
                            except Torrent.DoesNotExist:
                                continue
                    except (OSError, PermissionError):
                        continue

        # Output JSONL of matches if requested
        if cfg.matches_jsonl:
            progress("Writing matches", 0, 0)
            matches = fetch_all_matches()
            with cfg.matches_jsonl.open("w", encoding="utf-8") as f:
                for row in matches:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

        # Get final match count
        matches = fetch_all_matches()
        match_count = len(matches)
        progress(f"File scan complete - {match_count} total matches found", 1, 1)

    finally:
        # Cleanup (only if we created our own Redis connection)
        if _rds is None:
            try:
                rds.close()
            except Exception:
                pass
            close_database()


def scan(cfg: ScanConfig) -> dict:
    """
    Main scan function that combines torrent and file scanning.

    1) Ingest new .torrent files from all directories.
    2) Scan all directories for data matches against existing torrents.
    3) Write JSONL of matches if cfg.matches_jsonl is provided.
    """
    # Initialize database and Redis once for both phases
    init_database(cfg.db_path)
    rds = get_redis(str(cfg.redis_path))
    
    try:
        # Run both phases of scanning (with shared resources)
        torrent_stats = scan_torrents(cfg, _skip_init=True, _rds=rds)
        scan_files(cfg, _skip_init=True, _rds=rds)
        return torrent_stats  # Return torrent indexing stats
    finally:
        # Clean up shared resources
        try:
            rds.close()
        except Exception:
            pass
        close_database()