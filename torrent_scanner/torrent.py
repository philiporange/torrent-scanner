"""
Torrent file parsing and metadata extraction.
Implements BEP-3 torrent file format parsing with hash computation.
"""

import hashlib
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union, Dict, Any

from .bencode import bdecode_with_info_span, BencodeError
from .models import Torrent, TorrentFile
from .filesystem import compute_file_hash


def _to_str(b: Union[bytes, str]) -> str:
    """Safely convert bytes to string with fallback encoding."""
    if isinstance(b, str):
        return b
    try:
        return b.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return b.decode("utf-8", errors="replace")


def _to_str_pref_utf8(value: Dict[Union[str, bytes], Any], key: str) -> Optional[str]:
    """Prefer <key>.utf-8 if present; fall back to <key> if not."""
    utf8_key = f"{key}.utf-8"
    # Normalize keys to str for lookup
    str_map = {(_to_str(k)): v for k, v in value.items()}
    
    if utf8_key in str_map:
        v = str_map[utf8_key]
        if isinstance(v, (bytes, str)):
            return _to_str(v)
    
    if key in str_map:
        v = str_map[key]
        if isinstance(v, (bytes, str)):
            return _to_str(v)
    
    return None


@dataclass
class TorrentMeta:
    """Metadata extracted from a torrent file."""
    info_hash_hex: str
    name: str
    name_hash_hex: str
    is_multi: bool
    total_length: int
    structure_hash_hex: Optional[str]  # only for multi-file; None for single
    files: List[Tuple[str, int]]       # relative path, size
    created_unix: Optional[int]
    created_by: Optional[str]
    comment: Optional[str]


def parse_torrent(torrent_bytes: bytes) -> TorrentMeta:
    """Parse a torrent file and extract metadata."""
    top, info_span = bdecode_with_info_span(torrent_bytes)
    if info_span is None:
        raise BencodeError("Missing 'info' dict")

    info_bytes = torrent_bytes[info_span[0]:info_span[1]]
    info_hash = hashlib.sha1(info_bytes).hexdigest()

    info_dict = top.get(b"info", {})
    if not isinstance(info_dict, dict):
        raise BencodeError("'info' is not a dict")

    name = _to_str_pref_utf8(info_dict, "name") or "unnamed"
    name_hash = hashlib.sha256(name.encode("utf-8")).hexdigest()

    files_list = info_dict.get(b"files", None)
    is_multi = isinstance(files_list, list)

    files: List[Tuple[str, int]] = []
    total_length = 0

    if is_multi:
        for f in files_list:  # type: ignore[assignment]
            if not isinstance(f, dict):
                raise BencodeError("files entry is not a dict")
            
            # Path can be 'path.utf-8' or 'path'
            path_components = None
            if b"path.utf-8" in f:
                path_components = f[b"path.utf-8"]
            else:
                path_components = f.get(b"path", None)
            
            if not isinstance(path_components, list):
                raise BencodeError("file path is not a list")
            
            rel = "/".join(_to_str(comp) for comp in path_components)
            length = f.get(b"length", None)
            if not isinstance(length, int):
                raise BencodeError("file length is not int")
            
            files.append((rel, length))
            total_length += length

        # Canonicalize structure: sort by relative path, format "path\tlength"
        lines = [f"{p}\t{l}" for (p, l) in files]
        lines.sort()
        blob = ("\n".join(lines)).encode("utf-8")
        structure_hash = hashlib.sha256(blob).hexdigest()
    else:
        # Single-file torrent: length is under info.length
        length = info_dict.get(b"length", None)
        if not isinstance(length, int):
            raise BencodeError("single-file 'length' is missing or not int")
        
        total_length = length
        files = [(name, length)]
        structure_hash = None

    # Extract optional metadata
    created_unix = None
    if isinstance(top.get(b"creation date"), int):
        created_unix = int(top[b"creation date"])  # type: ignore[index]
    
    created_by = None
    if isinstance(top.get(b"created by"), (bytes, str)):
        created_by = _to_str(top[b"created by"])  # type: ignore[index]
    
    comment = None
    if isinstance(top.get(b"comment"), (bytes, str)):
        comment = _to_str(top[b"comment"])  # type: ignore[index]

    return TorrentMeta(
        info_hash_hex=info_hash,
        name=name,
        name_hash_hex=name_hash,
        is_multi=is_multi,
        total_length=total_length,
        structure_hash_hex=structure_hash,
        files=files,
        created_unix=created_unix,
        created_by=created_by,
        comment=comment,
    )


def save_torrent_meta(meta: TorrentMeta, torrent_path: str) -> Optional[Torrent]:
    """Save torrent metadata to database using Peewee ORM."""
    try:
        torrent = Torrent.create(
            info_hash=meta.info_hash_hex,
            torrent_path=torrent_path,
            name=meta.name,
            name_hash=meta.name_hash_hex,
            structure_hash=meta.structure_hash_hex,
            is_multi=meta.is_multi,
            total_length=meta.total_length,
            created_unix=meta.created_unix,
            created_by=meta.created_by,
            comment=meta.comment,
            added_ts=int(time.time())
        )
        
        # Save individual files with their hashes
        for idx, (path, length) in enumerate(meta.files):
            file_hash = compute_file_hash(path, length)
            TorrentFile.create(
                torrent=torrent,
                file_index=idx,
                path=path,
                length=length,
                file_hash=file_hash
            )
        
        return torrent
    except Exception:  # Peewee will raise IntegrityError for duplicates
        return None