"""
torrent_scanner - A utility to index .torrent files and match on-disk data.
"""

from .models import Torrent, TorrentFile, Match, clean_database
from .bencode import BencodeError, bdecode_with_info_span
from .torrent import TorrentMeta, parse_torrent
from .filesystem import iter_torrent_files, compute_structure_hash_for_dir, compute_name_hash_for_file
from .scanner import ScanConfig, scan
from .cli import main

__version__ = "0.1.0"
__author__ = "Philip Orange <git@philiporange.com>"

__all__ = [
    'Torrent', 'TorrentFile', 'Match', 'clean_database',
    'BencodeError', 'bdecode_with_info_span',
    'TorrentMeta', 'parse_torrent',
    'iter_torrent_files', 'compute_structure_hash_for_dir', 'compute_name_hash_for_file',
    'ScanConfig', 'scan',
    'main'
]