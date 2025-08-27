"""
Tests for torrent file parsing functionality.
"""

import hashlib
import pytest
from torrent_scanner.torrent import parse_torrent, TorrentMeta
from torrent_scanner.bencode import BencodeError


class TestTorrentParsing:
    
    def test_parse_single_file_torrent(self):
        # Create a minimal single-file torrent
        info_dict = {
            b'name': b'test_file.txt',
            b'length': 1024
        }
        torrent_dict = {
            b'announce': b'http://tracker.example.com/announce',
            b'info': info_dict
        }
        
        # Manually bencode the torrent data
        torrent_data = self._bencode_dict(torrent_dict)
        
        meta = parse_torrent(torrent_data)
        
        assert meta.name == 'test_file.txt'
        assert meta.is_multi == False
        assert meta.total_length == 1024
        assert meta.structure_hash_hex is None
        assert len(meta.files) == 1
        assert meta.files[0] == ('test_file.txt', 1024)
        assert len(meta.info_hash_hex) == 40  # SHA1 hex length
        assert len(meta.name_hash_hex) == 64  # SHA256 hex length
    
    def test_parse_multi_file_torrent(self):
        # Create a minimal multi-file torrent
        info_dict = {
            b'name': b'test_folder',
            b'files': [
                {b'path': [b'file1.txt'], b'length': 512},
                {b'path': [b'subdir', b'file2.txt'], b'length': 1024}
            ]
        }
        torrent_dict = {
            b'announce': b'http://tracker.example.com/announce',
            b'info': info_dict
        }
        
        torrent_data = self._bencode_dict(torrent_dict)
        
        meta = parse_torrent(torrent_data)
        
        assert meta.name == 'test_folder'
        assert meta.is_multi == True
        assert meta.total_length == 1536  # 512 + 1024
        assert meta.structure_hash_hex is not None
        assert len(meta.structure_hash_hex) == 64  # SHA256 hex length
        assert len(meta.files) == 2
        assert meta.files[0] == ('file1.txt', 512)
        assert meta.files[1] == ('subdir/file2.txt', 1024)
    
    def test_parse_torrent_with_utf8_name(self):
        # Test UTF-8 name handling
        info_dict = {
            b'name': b'regular_name',
            b'name.utf-8': 'тест файл.txt'.encode('utf-8'),
            b'length': 256
        }
        torrent_dict = {
            b'info': info_dict
        }
        
        torrent_data = self._bencode_dict(torrent_dict)
        meta = parse_torrent(torrent_data)
        
        assert meta.name == 'тест файл.txt'
    
    def test_parse_torrent_with_metadata(self):
        # Test parsing of optional metadata fields
        import time
        created_time = int(time.time())
        
        info_dict = {
            b'name': b'test.txt',
            b'length': 100
        }
        torrent_dict = {
            b'info': info_dict,
            b'creation date': created_time,
            b'created by': b'test client v1.0',
            b'comment': b'This is a test torrent'
        }
        
        torrent_data = self._bencode_dict(torrent_dict)
        meta = parse_torrent(torrent_data)
        
        assert meta.created_unix == created_time
        assert meta.created_by == 'test client v1.0'
        assert meta.comment == 'This is a test torrent'
    
    def test_parse_torrent_errors(self):
        # Missing info dict
        with pytest.raises(BencodeError, match="Missing 'info'"):
            parse_torrent(self._bencode_dict({b'announce': b'test'}))
        
        # Info is not a dict
        with pytest.raises(BencodeError, match="'info' is not a dict"):
            parse_torrent(self._bencode_dict({b'info': b'not a dict'}))
        
        # Missing length in single-file torrent
        info_dict = {b'name': b'test.txt'}
        with pytest.raises(BencodeError, match="'length' is missing"):
            parse_torrent(self._bencode_dict({b'info': info_dict}))
    
    def test_structure_hash_consistency(self):
        # Test that structure hash is consistent for same file structure
        files = [
            {b'path': [b'a.txt'], b'length': 100},
            {b'path': [b'b.txt'], b'length': 200}
        ]
        
        info_dict1 = {b'name': b'folder1', b'files': files}
        info_dict2 = {b'name': b'folder2', b'files': files}  # Different name, same files
        
        meta1 = parse_torrent(self._bencode_dict({b'info': info_dict1}))
        meta2 = parse_torrent(self._bencode_dict({b'info': info_dict2}))
        
        # Structure hash should be the same despite different folder names
        assert meta1.structure_hash_hex == meta2.structure_hash_hex
        # But name hash should be different
        assert meta1.name_hash_hex != meta2.name_hash_hex
    
    def test_name_hash_consistency(self):
        # Test that name hash is consistent for same name
        name = 'test_file.txt'
        expected_hash = hashlib.sha256(name.encode('utf-8')).hexdigest()
        
        info_dict = {b'name': name.encode('utf-8'), b'length': 100}
        meta = parse_torrent(self._bencode_dict({b'info': info_dict}))
        
        assert meta.name_hash_hex == expected_hash
    
    def _bencode_int(self, value):
        return f'i{value}e'.encode('ascii')
    
    def _bencode_bytes(self, value):
        if isinstance(value, str):
            value = value.encode('utf-8')
        return f'{len(value)}:'.encode('ascii') + value
    
    def _bencode_list(self, items):
        result = b'l'
        for item in items:
            if isinstance(item, int):
                result += self._bencode_int(item)
            elif isinstance(item, (bytes, str)):
                result += self._bencode_bytes(item)
            elif isinstance(item, list):
                result += self._bencode_list(item)
            elif isinstance(item, dict):
                result += self._bencode_dict(item)
        result += b'e'
        return result
    
    def _bencode_dict(self, d):
        result = b'd'
        # Sort keys for consistent encoding
        for key in sorted(d.keys()):
            result += self._bencode_bytes(key)
            value = d[key]
            if isinstance(value, int):
                result += self._bencode_int(value)
            elif isinstance(value, (bytes, str)):
                result += self._bencode_bytes(value)
            elif isinstance(value, list):
                result += self._bencode_list(value)
            elif isinstance(value, dict):
                result += self._bencode_dict(value)
        result += b'e'
        return result