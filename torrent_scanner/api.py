"""
Public API for torrent_scanner library.

This module provides a clean, high-level API for external use of the torrent scanner
functionality. All functions handle database initialization/cleanup automatically.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

from .models import (
    init_database, close_database, get_torrent_by_info_hash, 
    get_data_paths_for_torrent, get_torrent_for_data_path,
    fetch_all_matches, fetch_matched_torrents, fetch_unmatched_torrents,
    fetch_all_torrents, Torrent, Match
)
from .scanner import ScanConfig, scan_torrents, scan_files, get_info
from .torrent import parse_torrent


@contextmanager
def database_session(db_path: Path):
    """Context manager for database operations."""
    init_database(db_path)
    try:
        yield
    finally:
        close_database()


class TorrentScanner:
    """
    High-level API for torrent scanning operations.
    
    This class provides a clean interface for indexing torrents, finding matches,
    and querying the database. It handles database initialization and cleanup
    automatically.
    """
    
    def __init__(self, db_path: Optional[Path] = None, redis_path: Optional[Path] = None):
        """
        Initialize scanner with database paths.
        
        Args:
            db_path: Path to SQLite database (default: ~/.torrent_scanner/torrents.db)
            redis_path: Path to Redis database (default: ~/.torrent_scanner/redis.db)
        """
        self.db_path = db_path or Path.home() / ".torrent_scanner" / "torrents.db"
        self.redis_path = redis_path or Path.home() / ".torrent_scanner" / "redis.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.redis_path.parent.mkdir(parents=True, exist_ok=True)
    
    def index_torrents(self, directories: List[Path], quiet: bool = True) -> Dict[str, int]:
        """
        Index .torrent files from specified directories.
        
        Args:
            directories: List of directories to scan for .torrent files
            quiet: If True, suppress progress output
            
        Returns:
            Dict with 'processed' and 'new' counts
        """
        cfg = ScanConfig(
            db_path=self.db_path,
            redis_path=self.redis_path,
            directories=directories,
            progress_callback=None if quiet else print
        )
        
        return scan_torrents(cfg)
    
    def find_matches(self, directories: List[Path], quiet: bool = True) -> List[Dict[str, Any]]:
        """
        Find data that matches indexed torrents.
        
        Args:
            directories: List of directories to scan for data
            quiet: If True, suppress progress output
            
        Returns:
            List of match dictionaries with torrent metadata and data paths
        """
        cfg = ScanConfig(
            db_path=self.db_path,
            redis_path=self.redis_path,
            directories=directories,
            progress_callback=None if quiet else print
        )
        
        scan_files(cfg)
        
        init_database(self.db_path)
        try:
            return fetch_all_matches()
        finally:
            close_database()
    
    def update(self, directories: List[Path], quiet: bool = True) -> Dict[str, Any]:
        """
        Perform full scan: index torrents and find matches.
        
        Args:
            directories: List of directories to scan
            quiet: If True, suppress progress output
            
        Returns:
            Dict with indexing counts and match results
        """
        index_stats = self.index_torrents(directories, quiet)
        matches = self.find_matches(directories, quiet)
        
        return {
            'indexed': index_stats,
            'matches': matches,
            'match_count': len(matches)
        }
    
    def is_downloaded(self, info_hash: str) -> bool:
        """
        Check if a torrent has any data matches.
        
        Args:
            info_hash: 40-character hexadecimal info hash
            
        Returns:
            True if torrent has at least one data match, False otherwise
        """
        init_database(self.db_path)
        try:
            paths = get_data_paths_for_torrent(info_hash)
            return len(paths) > 0
        finally:
            close_database()
    
    def get_data_locations(self, info_hash: str) -> List[Path]:
        """
        Get all data locations for a torrent.
        
        Args:
            info_hash: 40-character hexadecimal info hash
            
        Returns:
            List of Path objects where torrent data is located
        """
        init_database(self.db_path)
        try:
            paths = get_data_paths_for_torrent(info_hash)
            return [Path(p) for p in paths]
        finally:
            close_database()
    
    def get_torrent_info(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Get torrent information by info_hash or torrent file path.
        
        Args:
            identifier: 40-char info_hash or path to .torrent file
            
        Returns:
            Dict with torrent metadata or None if not found
        """
        init_database(self.db_path)
        try:
            # Try as info_hash first
            if len(identifier) == 40 and all(c in '0123456789abcdef' for c in identifier.lower()):
                torrent = get_torrent_by_info_hash(identifier)
            else:
                # Try as path
                try:
                    torrent_path = str(Path(identifier).resolve())
                    torrent = Torrent.get(Torrent.torrent_path == torrent_path)
                except Torrent.DoesNotExist:
                    return None
            
            if torrent:
                return {
                    'info_hash': torrent.info_hash,
                    'name': torrent.name,
                    'total_length': torrent.total_length,
                    'is_multi': torrent.is_multi,
                    'torrent_path': torrent.torrent_path,
                    'matches': [m.data_path for m in torrent.matches],
                    'created_unix': torrent.created_unix,
                    'created_by': torrent.created_by,
                    'comment': torrent.comment
                }
            return None
        finally:
            close_database()
    
    def check_directory(self, directory: Path) -> List[Dict[str, Any]]:
        """
        Check if a directory contains data for any torrents.
        
        Args:
            directory: Path to directory to check
            
        Returns:
            List of matching torrents with their info
        """
        directory = directory.resolve()
        
        with database_session(self.db_path):
            # Check exact matches first
            torrent_info = get_torrent_for_data_path(str(directory))
            if torrent_info:
                return [torrent_info]
            
            # Check if directory is a parent of any matches
            results = []
            query = Match.select().join(Torrent)
            for match in query:
                match_path = Path(match.data_path)
                try:
                    # Check if directory is parent or child of match
                    if directory in match_path.parents or match_path in directory.parents:
                        torrent = match.torrent
                        results.append({
                            'info_hash': torrent.info_hash,
                            'name': torrent.name,
                            'is_multi': torrent.is_multi,
                            'total_length': torrent.total_length,
                            'torrent_path': torrent.torrent_path,
                            'match_path': match.data_path
                        })
                except (OSError, ValueError):
                    # Skip invalid paths
                    continue
            
            return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dict with database statistics including torrent and match counts
        """
        return get_info(self.db_path)
    
    def list_torrents(self, filter_type: str = "all") -> List[Dict[str, Any]]:
        """
        List torrents with optional filtering.
        
        Args:
            filter_type: "all", "matched", or "unmatched"
            
        Returns:
            List of torrent dictionaries
        """
        init_database(self.db_path)
        try:
            if filter_type == "matched":
                return fetch_matched_torrents()
            elif filter_type == "unmatched":
                return fetch_unmatched_torrents()
            else:
                return fetch_all_torrents()
        finally:
            close_database()
    
    def export_matches(self) -> List[Dict[str, Any]]:
        """
        Export all matches in JSONL format.
        
        Returns:
            List of match dictionaries suitable for export
        """
        init_database(self.db_path)
        try:
            return fetch_all_matches()
        finally:
            close_database()


# Convenience functions for one-off operations

def quick_check(info_hash: str, db_path: Optional[Path] = None) -> bool:
    """
    Quick check if a torrent is downloaded.
    
    Args:
        info_hash: 40-character hexadecimal info hash
        db_path: Optional database path (uses default if not provided)
        
    Returns:
        True if torrent is downloaded, False otherwise
    """
    scanner = TorrentScanner(db_path=db_path)
    return scanner.is_downloaded(info_hash)


def quick_locate(info_hash: str, db_path: Optional[Path] = None) -> List[Path]:
    """
    Quick lookup of torrent data locations.
    
    Args:
        info_hash: 40-character hexadecimal info hash
        db_path: Optional database path (uses default if not provided)
        
    Returns:
        List of Path objects where torrent data is located
    """
    scanner = TorrentScanner(db_path=db_path)
    return scanner.get_data_locations(info_hash)


def quick_identify(data_path: Path, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Quick identification of which torrent a file/folder belongs to.
    
    Args:
        data_path: Path to data file or directory
        db_path: Optional database path (uses default if not provided)
        
    Returns:
        Dict with torrent info or None if no match found
    """
    scanner = TorrentScanner(db_path=db_path)
    
    init_database(scanner.db_path)
    try:
        return get_torrent_for_data_path(str(data_path))
    finally:
        close_database()