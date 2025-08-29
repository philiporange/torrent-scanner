"""
Tests for the new torrent_scanner API and CLI structure.

These tests verify that the refactored API provides the expected functionality
and that the CLI commands work correctly.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from torrent_scanner import TorrentScanner, quick_check, quick_locate, quick_identify
from torrent_scanner.api import database_session
from torrent_scanner.cli import main, cmd_check, cmd_locate, cmd_identify
from torrent_scanner.models import init_database, close_database, Torrent, Match


class TestTorrentScannerAPI:
    """Test the high-level TorrentScanner API."""
    
    def test_torrent_scanner_initialization(self):
        """Test TorrentScanner initialization with default and custom paths."""
        # Default initialization
        scanner = TorrentScanner()
        assert scanner.db_path == Path.home() / ".torrent_scanner" / "torrents.db"
        assert scanner.redis_path == Path.home() / ".torrent_scanner" / "redis.db"
        
        # Custom paths
        custom_db = Path("/tmp/test.db")
        custom_redis = Path("/tmp/test_redis.db")
        scanner = TorrentScanner(db_path=custom_db, redis_path=custom_redis)
        assert scanner.db_path == custom_db
        assert scanner.redis_path == custom_redis
    
    @patch('torrent_scanner.api.scan_torrents')
    def test_index_torrents(self, mock_scan_torrents):
        """Test the index_torrents method."""
        mock_scan_torrents.return_value = {'processed': 10, 'new': 5}
        
        scanner = TorrentScanner()
        directories = [Path("/test/dir1"), Path("/test/dir2")]
        
        result = scanner.index_torrents(directories, quiet=True)
        
        mock_scan_torrents.assert_called_once()
        call_args = mock_scan_torrents.call_args[0][0]  # Get ScanConfig
        assert call_args.directories == directories
        assert result == {'processed': 10, 'new': 5}
    
    @patch('torrent_scanner.api.scan_files')
    @patch('torrent_scanner.api.fetch_all_matches')
    def test_find_matches(self, mock_fetch_matches, mock_scan_files):
        """Test the find_matches method."""
        mock_matches = [
            {'info_hash': 'abc123', 'name': 'Test Torrent', 'matches': ['/data/test']}
        ]
        mock_fetch_matches.return_value = mock_matches
        
        scanner = TorrentScanner()
        directories = [Path("/test/data")]
        
        result = scanner.find_matches(directories, quiet=True)
        
        mock_scan_files.assert_called_once()
        mock_fetch_matches.assert_called_once()
        assert result == mock_matches
    
    @patch('torrent_scanner.api.scan_torrents')
    def test_update(self, mock_scan_torrents):
        """Test the update method that combines indexing and matching."""
        mock_scan_torrents.return_value = {'processed': 5, 'new': 2}
        
        with patch.object(TorrentScanner, 'find_matches') as mock_find_matches:
            mock_matches = [{'info_hash': 'abc123', 'name': 'Test'}]
            mock_find_matches.return_value = mock_matches
            
            scanner = TorrentScanner()
            directories = [Path("/test")]
            
            result = scanner.update(directories, quiet=True)
            
            expected = {
                'indexed': {'processed': 5, 'new': 2},
                'matches': mock_matches,
                'match_count': 1
            }
            assert result == expected
    
    def test_is_downloaded_with_database(self):
        """Test is_downloaded with actual database operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            
            # Initialize database and create test data
            init_database(db_path)
            
            try:
                # Create a test torrent (with 40-char info hash)
                torrent = Torrent.create(
                    info_hash="abcd1234567890abcdef1234567890abcdef1234",
                    torrent_path="/test.torrent",
                    name="Test Torrent",
                    name_hash="name123",
                    is_multi=False,
                    total_length=1024
                )
                
                # Add a match
                Match.create(torrent=torrent, data_path="/data/test")
                
            finally:
                close_database()
            
            # Now test with scanner using the same database path
            scanner = TorrentScanner(db_path=db_path)
            
            # Now should be downloaded
            assert scanner.is_downloaded("abcd1234567890abcdef1234567890abcdef1234")
            
            # Non-existent torrent should return False
            assert not scanner.is_downloaded("nonexistent1234567890abcdef1234567890abcd")
    
    def test_get_data_locations_with_database(self):
        """Test get_data_locations with actual database operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            
            init_database(db_path)
            try:
                torrent = Torrent.create(
                    info_hash="abcd1234567890abcdef1234567890abcdef1234",
                    torrent_path="/test.torrent",
                    name="Test Torrent",
                    name_hash="name123",
                    is_multi=False,
                    total_length=1024
                )
                
                Match.create(torrent=torrent, data_path="/data/test1")
                Match.create(torrent=torrent, data_path="/data/test2")
                
            finally:
                close_database()
                
            scanner = TorrentScanner(db_path=db_path)
            locations = scanner.get_data_locations("abcd1234567890abcdef1234567890abcdef1234")
            assert len(locations) == 2
            assert Path("/data/test1") in locations
            assert Path("/data/test2") in locations
    
    def test_get_torrent_info_with_database(self):
        """Test get_torrent_info with actual database operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            
            init_database(db_path)
            try:
                torrent = Torrent.create(
                    info_hash="abcd1234567890abcdef1234567890abcdef1234",
                    torrent_path="/test.torrent",
                    name="Test Torrent",
                    name_hash="name123",
                    is_multi=False,
                    total_length=1024,
                    created_by="test client",
                    comment="test comment"
                )
                
                Match.create(torrent=torrent, data_path="/data/test")
                
            finally:
                close_database()
                
            scanner = TorrentScanner(db_path=db_path)
                
            # Test by info hash
            info = scanner.get_torrent_info("abcd1234567890abcdef1234567890abcdef1234")
            assert info is not None
            assert info['info_hash'] == "abcd1234567890abcdef1234567890abcdef1234"
            assert info['name'] == "Test Torrent"
            assert info['torrent_path'] == "/test.torrent"
            assert info['matches'] == ["/data/test"]
            assert info['created_by'] == "test client"
            assert info['comment'] == "test comment"
            
            # Test by torrent path
            info2 = scanner.get_torrent_info("/test.torrent")
            assert info2 == info
            
            # Non-existent should return None
            assert scanner.get_torrent_info("nonexistent1234567890abcdef1234567890abcd") is None
    
    @patch('torrent_scanner.api.get_info')
    def test_get_statistics(self, mock_get_info):
        """Test get_statistics method."""
        mock_stats = {
            'total_torrents': 100,
            'matched_torrents': 75,
            'unmatched_torrents': 25,
            'total_matches': 150,
            'total_size_bytes': 1000000000
        }
        mock_get_info.return_value = mock_stats
        
        scanner = TorrentScanner()
        result = scanner.get_statistics()
        
        assert result == mock_stats
        mock_get_info.assert_called_once_with(scanner.db_path)


class TestConvenienceFunctions:
    """Test the convenience functions for one-off operations."""
    
    @patch.object(TorrentScanner, 'is_downloaded')
    def test_quick_check(self, mock_is_downloaded):
        """Test quick_check function."""
        mock_is_downloaded.return_value = True
        
        result = quick_check("abcd1234567890abcdef1234567890abcdef1234")
        assert result is True
        mock_is_downloaded.assert_called_once_with("abcd1234567890abcdef1234567890abcdef1234")
    
    @patch.object(TorrentScanner, 'get_data_locations')
    def test_quick_locate(self, mock_get_data_locations):
        """Test quick_locate function."""
        mock_locations = [Path("/data/test1"), Path("/data/test2")]
        mock_get_data_locations.return_value = mock_locations
        
        result = quick_locate("abcd1234567890abcdef1234567890abcdef1234")
        assert result == mock_locations
        mock_get_data_locations.assert_called_once_with("abcd1234567890abcdef1234567890abcdef1234")
    
    def test_quick_identify_with_database(self):
        """Test quick_identify with actual database operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            
            init_database(db_path)
            try:
                torrent = Torrent.create(
                    info_hash="abcd1234567890abcdef1234567890abcdef1234",
                    torrent_path="/test.torrent",
                    name="Test Torrent",
                    name_hash="name123",
                    is_multi=False,
                    total_length=1024
                )
                
                Match.create(torrent=torrent, data_path="/data/test")
                
            finally:
                close_database()
                
            result = quick_identify(Path("/data/test"), db_path=db_path)
            assert result is not None
            assert result['info_hash'] == "abcd1234567890abcdef1234567890abcdef1234"
            assert result['name'] == "Test Torrent"
            
            # Non-existent path should return None
            result = quick_identify(Path("/nonexistent"), db_path=db_path)
            assert result is None


class TestCLICommands:
    """Test the new CLI command structure."""
    
    def test_cmd_check_downloaded(self):
        """Test cmd_check with a downloaded torrent."""
        with patch.object(TorrentScanner, 'is_downloaded', return_value=True), \
             patch.object(TorrentScanner, 'get_data_locations', return_value=[Path("/data/test")]):
            
            # Mock args
            args = MagicMock()
            args.db = None
            args.redis = None
            args.torrent = "abcd1234567890abcdef1234567890abcdef1234"
            args.verbose = True
            
            with pytest.raises(SystemExit) as exc_info:
                cmd_check(args)
            assert exc_info.value.code == 0  # Success exit code
    
    def test_cmd_check_not_downloaded(self):
        """Test cmd_check with a torrent that's not downloaded."""
        with patch.object(TorrentScanner, 'is_downloaded', return_value=False):
            
            args = MagicMock()
            args.db = None
            args.redis = None
            args.torrent = "abcd1234567890abcdef1234567890abcdef1234"
            
            with pytest.raises(SystemExit) as exc_info:
                cmd_check(args)
            assert exc_info.value.code == 1  # Error exit code
    
    def test_cmd_locate_found(self):
        """Test cmd_locate with found data."""
        with patch.object(TorrentScanner, 'get_data_locations', 
                         return_value=[Path("/data/test1"), Path("/data/test2")]):
            
            args = MagicMock()
            args.db = None
            args.redis = None
            args.torrent = "abcd1234567890abcdef1234567890abcdef1234"
            args.format = "lines"
            
            # Should not raise SystemExit
            cmd_locate(args)
    
    def test_cmd_locate_not_found(self):
        """Test cmd_locate with no data found."""
        with patch.object(TorrentScanner, 'get_data_locations', return_value=[]):
            
            args = MagicMock()
            args.db = None
            args.redis = None
            args.torrent = "abcd1234567890abcdef1234567890abcdef1234"
            args.format = "lines"
            
            with pytest.raises(SystemExit) as exc_info:
                cmd_locate(args)
            assert exc_info.value.code == 1
    
    def test_cmd_identify_found(self):
        """Test cmd_identify with found torrent."""
        mock_info = {
            'info_hash': 'abcd1234567890abcdef1234567890abcdef1234',
            'name': 'Test Torrent',
            'torrent_path': '/test.torrent'
        }
        
        with patch('torrent_scanner.cli.database_session'), \
             patch('torrent_scanner.models.get_torrent_for_data_path', return_value=mock_info):
            
            args = MagicMock()
            args.db = None
            args.redis = None
            args.path = "/data/test"
            args.format = "simple"
            
            # Should not raise SystemExit
            cmd_identify(args)
    
    def test_cmd_identify_not_found(self):
        """Test cmd_identify with no torrent found."""
        with patch('torrent_scanner.cli.database_session'), \
             patch('torrent_scanner.models.get_torrent_for_data_path', return_value=None):
            
            args = MagicMock()
            args.db = None
            args.redis = None
            args.path = "/data/test"
            args.format = "simple"
            
            with pytest.raises(SystemExit) as exc_info:
                cmd_identify(args)
            assert exc_info.value.code == 1


class TestCommandMigration:
    """Test that the command migration mapping works as expected."""
    
    def test_old_vs_new_commands(self):
        """Test that new commands provide equivalent functionality to old ones."""
        # This is more of a conceptual test - we verify that the new API
        # provides all the functionality that was available in the old CLI
        
        scanner = TorrentScanner()
        
        # Old 'scan' -> New 'update' (index + match)
        assert hasattr(scanner, 'update')
        
        # Old 'torrents' -> New 'index' 
        assert hasattr(scanner, 'index_torrents')
        
        # Old 'files' -> New 'match'
        assert hasattr(scanner, 'find_matches')
        
        # Old 'list-matches' -> New 'list --filter matched'
        assert hasattr(scanner, 'list_torrents')
        
        # Old 'list-unmatched' -> New 'list --filter unmatched'
        assert hasattr(scanner, 'list_torrents')
        
        # Old 'get-data' -> New 'locate'
        assert hasattr(scanner, 'get_data_locations')
        
        # Old 'get-torrent' -> New 'identify'
        # This is handled by quick_identify function
        
        # Old 'info' -> New 'stats'
        assert hasattr(scanner, 'get_statistics')
        
        # Old 'clean' -> New 'reset' (handled in CLI, uses clean_database)


if __name__ == "__main__":
    pytest.main([__file__])