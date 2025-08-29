"""
Database models using Peewee ORM.
Defines the structure for storing torrent metadata and matches.
Supports file-based matching to handle merged folders where multiple torrents
with identical names are combined into a single directory.
"""

import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import peewee
from peewee import (
    Model, SqliteDatabase, CharField, IntegerField, TextField,
    BooleanField, ForeignKeyField, DateTimeField, fn
)


# Database will be configured later
database = SqliteDatabase(None)


class BaseModel(Model):
    """Base model with database configuration."""
    
    class Meta:
        database = database


class Torrent(BaseModel):
    """Model for storing torrent metadata."""
    
    info_hash = CharField(max_length=40, unique=True, index=True)
    torrent_path = CharField(unique=True)
    name = CharField()
    name_hash = CharField(max_length=64, index=True)
    structure_hash = CharField(max_length=64, null=True, index=True)
    is_multi = BooleanField(index=True)
    total_length = IntegerField(index=True)
    created_unix = IntegerField(null=True)
    created_by = TextField(null=True)
    comment = TextField(null=True)
    added_ts = IntegerField(default=lambda: int(time.time()))


class TorrentFile(BaseModel):
    """Model for storing individual files within torrents."""
    
    torrent = ForeignKeyField(Torrent, backref='files', on_delete='CASCADE')
    file_index = IntegerField()
    path = TextField()
    length = IntegerField()
    file_hash = CharField(max_length=64, index=True)
    
    class Meta:
        primary_key = False
        indexes = (
            (('torrent', 'file_index'), True),  # Unique together
            (('file_hash',), False),  # Index for lookups
        )


class Match(BaseModel):
    """Model for storing matches between torrents and filesystem data."""
    
    torrent = ForeignKeyField(Torrent, backref='matches', on_delete='CASCADE')
    data_path = TextField()
    first_seen_ts = IntegerField(default=lambda: int(time.time()))
    
    class Meta:
        primary_key = False
        indexes = (
            (('torrent', 'data_path'), True),  # Unique together
            (('torrent',), False),
        )


def init_database(db_path: Path) -> None:
    """Initialize the database with the given path."""
    database.init(str(db_path))
    database.pragma('journal_mode', 'WAL')
    database.pragma('synchronous', 'NORMAL')
    database.create_tables([Torrent, TorrentFile, Match], safe=True)


def get_torrent_by_info_hash(info_hash: str) -> Optional[Torrent]:
    """Get torrent by info hash."""
    try:
        return Torrent.get(Torrent.info_hash == info_hash)
    except Torrent.DoesNotExist:
        return None


def add_match(info_hash: str, data_path: str) -> bool:
    """Add a match between a torrent and filesystem data."""
    torrent = get_torrent_by_info_hash(info_hash)
    if not torrent:
        return False
    
    try:
        Match.create(
            torrent=torrent,
            data_path=str(Path(data_path).resolve()),
            first_seen_ts=int(time.time())
        )
        return True
    except Exception:  # Peewee will raise IntegrityError for duplicates
        return False


def fetch_all_matches() -> List[Dict[str, Any]]:
    """Fetch all torrents with their matches."""
    query = (Torrent
             .select()
             .join(Match)
             .group_by(Torrent.id)
             .order_by(Torrent.added_ts.desc()))
    
    results = []
    for torrent in query:
        matches = [match.data_path for match in torrent.matches]
        first_seen = min(match.first_seen_ts for match in torrent.matches) if torrent.matches else None
        
        results.append({
            'info_hash': torrent.info_hash,
            'torrent_path': torrent.torrent_path,
            'name': torrent.name,
            'name_hash': torrent.name_hash,
            'structure_hash': torrent.structure_hash,
            'is_multi': torrent.is_multi,
            'total_length': torrent.total_length,
            'created_unix': torrent.created_unix,
            'created_by': torrent.created_by,
            'comment': torrent.comment,
            'matches': matches,
            'first_seen_ts': first_seen,
        })
    
    return results


def fetch_files_for_torrent(torrent: Torrent) -> List[tuple]:
    """Fetch file list for a torrent."""
    files = (TorrentFile
             .select()
             .where(TorrentFile.torrent == torrent)
             .order_by(TorrentFile.file_index))
    
    return [(f.path, f.length) for f in files]


def clean_database() -> None:
    """Reset the database by dropping all tables and recreating them."""
    if database.is_closed():
        raise RuntimeError("Database is not initialized. Call init_database() first.")
    
    database.drop_tables([Match, TorrentFile, Torrent], safe=True)
    database.create_tables([Torrent, TorrentFile, Match], safe=True)


def close_database() -> None:
    """Close the database connection."""
    if not database.is_closed():
        database.close()


def fetch_unmatched_torrents() -> List[Dict[str, Any]]:
    """Fetch all torrents that have no matches."""
    # Get all torrents that don't have any matches
    matched_torrent_ids = Match.select(Match.torrent).distinct()
    query = (Torrent
             .select()
             .where(Torrent.id.not_in(matched_torrent_ids))
             .order_by(Torrent.added_ts.desc()))
    
    results = []
    for torrent in query:
        results.append({
            'info_hash': torrent.info_hash,
            'torrent_path': torrent.torrent_path,
            'name': torrent.name,
            'is_multi': torrent.is_multi,
            'total_length': torrent.total_length,
            'created_unix': torrent.created_unix,
            'added_ts': torrent.added_ts,
        })
    
    return results


def fetch_matched_torrents() -> List[Dict[str, Any]]:
    """Fetch all torrents that have at least one match."""
    query = (Torrent
             .select()
             .join(Match)
             .distinct()
             .order_by(Torrent.added_ts.desc()))
    
    results = []
    for torrent in query:
        results.append({
            'info_hash': torrent.info_hash,
            'torrent_path': torrent.torrent_path,
            'name': torrent.name,
            'is_multi': torrent.is_multi,
            'total_length': torrent.total_length,
            'match_count': torrent.matches.count(),
        })
    
    return results


def get_data_paths_for_torrent(torrent_identifier: str) -> List[str]:
    """
    Get data paths for a torrent by info_hash or torrent_path.
    
    Args:
        torrent_identifier: Either a 40-char info_hash or path to .torrent file
        
    Returns:
        List of data paths that match this torrent
    """
    # Determine if identifier is info_hash or path
    if len(torrent_identifier) == 40 and all(c in '0123456789abcdef' for c in torrent_identifier.lower()):
        # Looks like info_hash
        torrent = get_torrent_by_info_hash(torrent_identifier)
    else:
        # Treat as path
        torrent_path = str(Path(torrent_identifier).resolve())
        try:
            torrent = Torrent.get(Torrent.torrent_path == torrent_path)
        except Torrent.DoesNotExist:
            torrent = None
    
    if not torrent:
        return []
    
    return [match.data_path for match in torrent.matches]


def get_torrent_for_data_path(data_path: str) -> Optional[Dict[str, Any]]:
    """
    Get torrent info for a given data path.
    
    Args:
        data_path: Path to data directory or file
        
    Returns:
        Dictionary with torrent info or None if no match
    """
    resolved_path = str(Path(data_path).resolve())
    
    try:
        match = Match.get(Match.data_path == resolved_path)
        torrent = match.torrent
        
        return {
            'info_hash': torrent.info_hash,
            'torrent_path': torrent.torrent_path,
            'name': torrent.name,
            'is_multi': torrent.is_multi,
            'total_length': torrent.total_length,
        }
    except Match.DoesNotExist:
        return None


def get_all_matches_dict() -> Dict[str, Dict[str, Any]]:
    """
    Get dictionary of all matched torrents with their data paths.
    
    Returns:
        Dict mapping info_hash -> {torrent_info, data_paths: [...]}
    """
    result = {}
    
    query = (Torrent
             .select()
             .join(Match)
             .distinct())
    
    for torrent in query:
        data_paths = [match.data_path for match in torrent.matches]
        result[torrent.info_hash] = {
            'torrent_path': torrent.torrent_path,
            'name': torrent.name,
            'is_multi': torrent.is_multi,
            'total_length': torrent.total_length,
            'data_paths': data_paths,
        }
    
    return result


def fetch_all_torrents() -> List[Dict[str, Any]]:
    """
    Fetch all torrents in the database (both matched and unmatched).
    
    Returns:
        List of torrent dictionaries with basic metadata
    """
    query = (Torrent
             .select()
             .order_by(Torrent.added_ts.desc()))
    
    results = []
    for torrent in query:
        match_count = torrent.matches.count()
        results.append({
            'info_hash': torrent.info_hash,
            'torrent_path': torrent.torrent_path,
            'name': torrent.name,
            'is_multi': torrent.is_multi,
            'total_length': torrent.total_length,
            'created_unix': torrent.created_unix,
            'created_by': torrent.created_by,
            'comment': torrent.comment,
            'added_ts': torrent.added_ts,
            'match_count': match_count,
        })
    
    return results