"""
Minimal bencode decoder with offset tracking for torrent files.
Implements BEP-3 bencode specification with info span extraction.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union


class BencodeError(Exception):
    """Exception raised for bencode parsing errors."""
    pass


@dataclass
class Decoded:
    """Result of a bencode decode operation."""
    value: Any
    pos: int


def _bdecode_int(data: bytes, pos: int) -> Decoded:
    """Decode a bencoded integer starting at position pos."""
    # data[pos] == ord('i')
    end = data.find(b'e', pos + 1)
    if end == -1:
        raise BencodeError("Invalid bencode int: missing 'e'")
    
    num_bytes = data[pos + 1 : end]
    if not num_bytes:
        raise BencodeError("Invalid bencode int: empty")
    
    if num_bytes == b"-0":
        raise BencodeError("Invalid bencode int: -0")
    
    # Leading zeros not allowed unless the number is zero
    if num_bytes[0:1] == b'0' and len(num_bytes) > 1:
        raise BencodeError("Invalid bencode int: leading zero")
    
    try:
        val = int(num_bytes.decode("ascii"))
    except ValueError:
        raise BencodeError("Invalid bencode int: non-digit")
    
    return Decoded(val, end + 1)


def _bdecode_bytes(data: bytes, pos: int) -> Decoded:
    """Decode a bencoded byte string starting at position pos."""
    # Format: <length>:<data>
    colon = data.find(b':', pos)
    if colon == -1:
        raise BencodeError("Invalid bencode bytes: missing ':'")
    
    try:
        length = int(data[pos:colon].decode("ascii"))
    except ValueError:
        raise BencodeError("Invalid bencode bytes length")
    
    start = colon + 1
    end = start + length
    if end > len(data):
        raise BencodeError("Invalid bencode bytes: truncated")
    
    return Decoded(data[start:end], end)


def _bdecode_list(data: bytes, pos: int) -> Decoded:
    """Decode a bencoded list starting at position pos."""
    # data[pos] == ord('l')
    items = []
    pos += 1
    
    while pos < len(data):
        t = data[pos:pos+1]
        if t == b'e':
            return Decoded(items, pos + 1)
        elif t == b'i':
            d = _bdecode_int(data, pos)
        elif t == b'l':
            d = _bdecode_list(data, pos)
        elif t == b'd':
            d = _bdecode_dict(data, pos)
        elif t.isdigit():
            d = _bdecode_bytes(data, pos)
        else:
            raise BencodeError("Invalid bencode list element")
        
        items.append(d.value)
        pos = d.pos
    
    raise BencodeError("Invalid bencode list: unterminated")


def _bdecode_dict(data: bytes, pos: int) -> Decoded:
    """Decode a bencoded dictionary starting at position pos."""
    # data[pos] == ord('d')
    mapping: Dict[bytes, Any] = {}
    pos += 1
    last_key: Optional[bytes] = None
    
    while pos < len(data):
        t = data[pos:pos+1]
        if t == b'e':
            return Decoded(mapping, pos + 1)
        
        # Key must be a bencoded bytes string
        key_dec = _bdecode_bytes(data, pos)
        key = key_dec.value
        if not isinstance(key, (bytes, bytearray)):
            raise BencodeError("Dictionary key is not bytes")
        
        if last_key is not None and key < last_key:
            # Spec requires lexicographically sorted keys; we're tolerant
            pass
        last_key = key
        pos = key_dec.pos
        
        # Decode value
        t = data[pos:pos+1]
        if t == b'i':
            val_dec = _bdecode_int(data, pos)
        elif t == b'l':
            val_dec = _bdecode_list(data, pos)
        elif t == b'd':
            val_dec = _bdecode_dict(data, pos)
        elif t.isdigit():
            val_dec = _bdecode_bytes(data, pos)
        else:
            raise BencodeError("Invalid bencode dict value")
        
        mapping[key] = val_dec.value
        pos = val_dec.pos
    
    raise BencodeError("Invalid bencode dict: unterminated")


def bdecode_with_info_span(data: bytes) -> Tuple[Dict[bytes, Any], Optional[Tuple[int, int]]]:
    """
    Decode top-level bencoded object and return the parsed object plus info span.
    
    Returns:
        - The decoded object as nested Python structures using bytes for raw strings
        - (start, end) byte positions for the 'info' key's value, if present
          The slice data[start:end] is the raw bencoded info dictionary for SHA1 hashing
    """
    if not data:
        raise BencodeError("Empty data")
    
    if data[0:1] != b'd':
        raise BencodeError("Top-level is not a dictionary")

    pos = 1
    top: Dict[bytes, Any] = {}
    info_span: Optional[Tuple[int, int]] = None
    last_key: Optional[bytes] = None

    while pos < len(data):
        t = data[pos:pos+1]
        if t == b'e':
            return top, info_span
        
        # Decode key
        key_dec = _bdecode_bytes(data, pos)
        key = key_dec.value
        if last_key is not None and key < last_key:
            pass
        last_key = key
        pos = key_dec.pos

        # For the value, if key == b'info', record the span
        t = data[pos:pos+1]
        if key == b'info':
            start = pos
        
        if t == b'i':
            val_dec = _bdecode_int(data, pos)
        elif t == b'l':
            val_dec = _bdecode_list(data, pos)
        elif t == b'd':
            val_dec = _bdecode_dict(data, pos)
        elif t.isdigit():
            val_dec = _bdecode_bytes(data, pos)
        else:
            raise BencodeError("Invalid bencode top-level value")

        if key == b'info':
            info_span = (start, val_dec.pos)
            
        top[key] = val_dec.value
        pos = val_dec.pos

    raise BencodeError("Top-level dict unterminated")