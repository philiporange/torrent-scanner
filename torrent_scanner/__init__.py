"""
torrent_scanner - A utility to index .torrent files and match on-disk data.

This package provides both a high-level API for library use and a command-line interface.
For library use, import TorrentScanner or the convenience functions.
For command-line use, use the main() function or run as a module.
"""

from .api import TorrentScanner, quick_check, quick_locate, quick_identify
from .models import (
    Torrent, TorrentFile, Match, clean_database,
    fetch_unmatched_torrents, fetch_matched_torrents, fetch_all_torrents,
    get_data_paths_for_torrent, get_torrent_for_data_path, get_all_matches_dict
)
from .bencode import BencodeError, bdecode_with_info_span
from .torrent import TorrentMeta, parse_torrent
from .filesystem import iter_torrent_files, compute_structure_hash_for_dir, compute_name_hash_for_file
from .scanner import ScanConfig, scan, scan_torrents, scan_files, get_info
from .cli import main

__version__ = "0.1.0"
__author__ = "Philip Orange <git@philiporange.com>"

__all__ = [
    # High-level API
    'TorrentScanner', 'quick_check', 'quick_locate', 'quick_identify',
    # Database models and queries
    'Torrent', 'TorrentFile', 'Match', 'clean_database',
    'fetch_unmatched_torrents', 'fetch_matched_torrents', 'fetch_all_torrents',
    'get_data_paths_for_torrent', 'get_torrent_for_data_path', 'get_all_matches_dict',
    # Torrent parsing
    'BencodeError', 'bdecode_with_info_span', 'TorrentMeta', 'parse_torrent',
    # Filesystem utilities
    'iter_torrent_files', 'compute_structure_hash_for_dir', 'compute_name_hash_for_file',
    # Low-level scanning
    'ScanConfig', 'scan', 'scan_torrents', 'scan_files', 'get_info',
    # CLI entry point
    'main'
]