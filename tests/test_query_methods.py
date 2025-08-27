"""Tests for new query methods."""
import tempfile
from pathlib import Path
import pytest
from torrent_scanner.models import (
    init_database, close_database,
    fetch_unmatched_torrents,
    fetch_matched_torrents,
    get_data_paths_for_torrent,
    get_torrent_for_data_path,
    get_all_matches_dict,
    add_match
)
from torrent_scanner.torrent import TorrentMeta, save_torrent_meta


class TestQueryMethods:
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database with test data."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        init_database(db_path)
        
        # Create test torrents
        matched_meta = TorrentMeta(
            info_hash_hex='a' * 40,
            name='matched_torrent',
            name_hash_hex='b' * 64,
            is_multi=False,
            total_length=1024,
            structure_hash_hex=None,
            files=[('file.txt', 1024)],
            created_unix=None,
            created_by=None,
            comment=None
        )
        
        unmatched_meta = TorrentMeta(
            info_hash_hex='c' * 40,
            name='unmatched_torrent',
            name_hash_hex='d' * 64,
            is_multi=False,
            total_length=2048,
            structure_hash_hex=None,
            files=[('other.txt', 2048)],
            created_unix=None,
            created_by=None,
            comment=None
        )
        
        # Save torrents
        save_torrent_meta(matched_meta, '/path/matched.torrent')
        save_torrent_meta(unmatched_meta, '/path/unmatched.torrent')
        
        # Add match for first torrent
        add_match('a' * 40, '/data/file.txt')
        
        yield db_path
        close_database()
        db_path.unlink()
    
    def test_fetch_unmatched_torrents(self, temp_db):
        unmatched = fetch_unmatched_torrents()
        assert len(unmatched) == 1
        assert unmatched[0]['name'] == 'unmatched_torrent'
        assert unmatched[0]['info_hash'] == 'c' * 40
    
    def test_fetch_matched_torrents(self, temp_db):
        matched = fetch_matched_torrents()
        assert len(matched) == 1
        assert matched[0]['name'] == 'matched_torrent'
        assert matched[0]['info_hash'] == 'a' * 40
        assert matched[0]['match_count'] == 1
    
    def test_get_data_paths_for_torrent(self, temp_db):
        # Test with info_hash
        paths = get_data_paths_for_torrent('a' * 40)
        assert len(paths) == 1
        assert paths[0] == str(Path('/data/file.txt').resolve())
        
        # Test with torrent path
        paths = get_data_paths_for_torrent('/path/matched.torrent')
        assert len(paths) == 1
        
        # Test non-existent
        paths = get_data_paths_for_torrent('z' * 40)
        assert paths == []
    
    def test_get_torrent_for_data_path(self, temp_db):
        data_path = str(Path('/data/file.txt').resolve())
        info = get_torrent_for_data_path(data_path)
        assert info is not None
        assert info['info_hash'] == 'a' * 40
        assert info['name'] == 'matched_torrent'
        
        # Test non-existent
        info = get_torrent_for_data_path('/nonexistent/path')
        assert info is None
    
    def test_get_all_matches_dict(self, temp_db):
        matches = get_all_matches_dict()
        assert len(matches) == 1
        assert 'a' * 40 in matches
        assert matches['a' * 40]['name'] == 'matched_torrent'
        assert len(matches['a' * 40]['data_paths']) == 1
        expected_path = str(Path('/data/file.txt').resolve())
        assert matches['a' * 40]['data_paths'][0] == expected_path


class TestMultipleMatches:
    """Test scenarios with multiple matches per torrent."""
    
    @pytest.fixture
    def temp_db_multi(self):
        """Create temporary database with multiple matches."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        init_database(db_path)
        
        # Create test torrent with multiple matches
        multi_meta = TorrentMeta(
            info_hash_hex='d' * 40,
            name='multi_match_torrent',
            name_hash_hex='e' * 64,
            is_multi=True,
            total_length=4096,
            structure_hash_hex='s' * 64,
            files=[('dir/file1.txt', 2048), ('dir/file2.txt', 2048)],
            created_unix=1234567890,
            created_by='test_creator',
            comment='test comment'
        )
        
        save_torrent_meta(multi_meta, '/path/multi.torrent')
        
        # Add multiple matches
        add_match('d' * 40, '/data/copy1/dir')
        add_match('d' * 40, '/data/copy2/dir')
        
        yield db_path
        close_database()
        db_path.unlink()
    
    def test_torrent_with_multiple_matches(self, temp_db_multi):
        # Test get_data_paths_for_torrent
        paths = get_data_paths_for_torrent('d' * 40)
        assert len(paths) == 2
        expected_paths = {
            str(Path('/data/copy1/dir').resolve()),
            str(Path('/data/copy2/dir').resolve())
        }
        assert set(paths) == expected_paths
        
        # Test get_all_matches_dict
        matches = get_all_matches_dict()
        assert len(matches) == 1
        assert 'd' * 40 in matches
        assert len(matches['d' * 40]['data_paths']) == 2
        assert set(matches['d' * 40]['data_paths']) == expected_paths
    
    def test_reverse_lookup_multiple_matches(self, temp_db_multi):
        # Both paths should return the same torrent
        path1 = str(Path('/data/copy1/dir').resolve())
        path2 = str(Path('/data/copy2/dir').resolve())
        
        info1 = get_torrent_for_data_path(path1)
        info2 = get_torrent_for_data_path(path2)
        
        assert info1 is not None
        assert info2 is not None
        assert info1['info_hash'] == info2['info_hash'] == 'd' * 40
        assert info1['name'] == info2['name'] == 'multi_match_torrent'


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def empty_db(self):
        """Create empty temporary database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        init_database(db_path)
        
        yield db_path
        close_database()
        db_path.unlink()
    
    def test_empty_database_queries(self, empty_db):
        # All queries should return empty results
        assert fetch_unmatched_torrents() == []
        assert fetch_matched_torrents() == []
        assert get_data_paths_for_torrent('a' * 40) == []
        assert get_torrent_for_data_path('/any/path') is None
        assert get_all_matches_dict() == {}
    
    def test_invalid_info_hash_format(self, empty_db):
        # Invalid info hash formats should be treated as paths
        assert get_data_paths_for_torrent('invalid') == []
        assert get_data_paths_for_torrent('too_short') == []
        assert get_data_paths_for_torrent('z' * 39) == []  # Too short
        assert get_data_paths_for_torrent('g' * 40) == []  # Invalid hex chars
    
    def test_path_resolution(self, empty_db):
        """Test that paths are properly resolved."""
        from torrent_scanner.models import Torrent, Match
        
        # Create a test torrent
        meta = TorrentMeta(
            info_hash_hex='f' * 40,
            name='path_test',
            name_hash_hex='a' * 64,
            is_multi=False,
            total_length=512,
            structure_hash_hex=None,
            files=[('test.txt', 512)],
            created_unix=None,
            created_by=None,
            comment=None
        )
        
        save_torrent_meta(meta, '/test/path.torrent')
        
        # Add match with relative path components
        relative_path = './relative/../test/file'
        add_match('f' * 40, relative_path)
        
        # Query should return resolved absolute path
        paths = get_data_paths_for_torrent('f' * 40)
        assert len(paths) == 1
        resolved_path = str(Path(relative_path).resolve())
        assert paths[0] == resolved_path
        
        # Reverse lookup should work with the resolved path
        info = get_torrent_for_data_path(resolved_path)
        assert info is not None
        assert info['info_hash'] == 'f' * 40