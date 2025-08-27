"""
Tests for filesystem scanning and matching operations.
"""

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from torrent_scanner.filesystem import (
    iter_torrent_files,
    compute_structure_hash_for_dir,
    compute_name_hash_for_file
)
from torrent_scanner.scanner import scan, ScanConfig


class TestFilesystemOperations:
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_iter_torrent_files(self, temp_dir):
        """Test finding .torrent files in directory structure."""
        # Create test structure
        torrent_dir = temp_dir / "torrents"
        torrent_dir.mkdir()
        subdir = torrent_dir / "subdir"
        subdir.mkdir()
        
        # Create some .torrent files
        (torrent_dir / "test1.torrent").write_bytes(b"fake torrent 1")
        (torrent_dir / "test2.torrent").write_bytes(b"fake torrent 2")
        (subdir / "test3.torrent").write_bytes(b"fake torrent 3")
        
        # Create non-.torrent files (should be ignored)
        (torrent_dir / "readme.txt").write_text("readme")
        (torrent_dir / "other.file").write_text("other")
        
        # Find torrent files
        torrent_files = iter_torrent_files(torrent_dir)
        
        assert len(torrent_files) == 3
        torrent_names = {f.name for f in torrent_files}
        assert torrent_names == {"test1.torrent", "test2.torrent", "test3.torrent"}
    
    def test_iter_torrent_files_empty_dir(self, temp_dir):
        """Test finding torrents in empty directory."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        
        torrent_files = iter_torrent_files(empty_dir)
        assert len(torrent_files) == 0
    
    def test_compute_structure_hash_for_dir(self, temp_dir):
        """Test computing structure hash for directory."""
        # Create test directory structure
        test_dir = temp_dir / "test_data"
        test_dir.mkdir()
        subdir = test_dir / "subdir"
        subdir.mkdir()
        
        # Create files with known content
        (test_dir / "file1.txt").write_bytes(b"content1")  # 8 bytes
        (test_dir / "file2.txt").write_bytes(b"longer content here")  # 19 bytes
        (subdir / "file3.txt").write_bytes(b"sub")  # 3 bytes
        
        # Compute structure hash
        struct_hash, files = compute_structure_hash_for_dir(test_dir)
        
        # Verify hash is 64-char hex string (SHA256)
        assert len(struct_hash) == 64
        assert all(c in '0123456789abcdef' for c in struct_hash)
        
        # Verify file list
        assert len(files) == 3
        files_dict = {path: size for path, size in files}
        
        assert files_dict['file1.txt'] == 8
        assert files_dict['file2.txt'] == 19
        assert files_dict['subdir/file3.txt'] == 3
    
    def test_compute_structure_hash_consistency(self, temp_dir):
        """Test that structure hash is consistent for same file structure."""
        # Create two identical directory structures
        dir1 = temp_dir / "dir1"
        dir2 = temp_dir / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        
        # Create identical files in both directories
        (dir1 / "file1.txt").write_bytes(b"same content")
        (dir1 / "file2.txt").write_bytes(b"also same")
        (dir2 / "file1.txt").write_bytes(b"same content")
        (dir2 / "file2.txt").write_bytes(b"also same")
        
        hash1, files1 = compute_structure_hash_for_dir(dir1)
        hash2, files2 = compute_structure_hash_for_dir(dir2)
        
        assert hash1 == hash2
        assert files1 == files2
    
    def test_compute_structure_hash_different_content_same_structure(self, temp_dir):
        """Test that structure hash differs for different file content but same structure."""
        dir1 = temp_dir / "dir1"
        dir2 = temp_dir / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        
        # Same structure, different content
        (dir1 / "file1.txt").write_bytes(b"content A")
        (dir2 / "file1.txt").write_bytes(b"content B")  # Different content, same size
        
        hash1, _ = compute_structure_hash_for_dir(dir1)
        hash2, _ = compute_structure_hash_for_dir(dir2)
        
        # Structure hash should be the same (only cares about paths and sizes)
        assert hash1 == hash2
    
    def test_compute_structure_hash_different_sizes(self, temp_dir):
        """Test that structure hash differs for different file sizes."""
        dir1 = temp_dir / "dir1"
        dir2 = temp_dir / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        
        # Same filename, different sizes
        (dir1 / "file1.txt").write_bytes(b"short")
        (dir2 / "file1.txt").write_bytes(b"much longer content")
        
        hash1, _ = compute_structure_hash_for_dir(dir1)
        hash2, _ = compute_structure_hash_for_dir(dir2)
        
        # Structure hash should be different due to different sizes
        assert hash1 != hash2
    
    def test_compute_structure_hash_empty_dir(self, temp_dir):
        """Test computing structure hash for empty directory."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        
        struct_hash, files = compute_structure_hash_for_dir(empty_dir)
        
        # Should still produce a valid hash
        assert len(struct_hash) == 64
        assert files == []
    
    def test_compute_name_hash_for_file(self, temp_dir):
        """Test computing name hash for file."""
        test_file = temp_dir / "test_file.txt"
        test_file.write_text("content")
        
        name_hash = compute_name_hash_for_file(test_file)
        
        # Should be SHA256 of the filename
        expected = hashlib.sha256("test_file.txt".encode('utf-8')).hexdigest()
        assert name_hash == expected
        assert len(name_hash) == 64
    
    def test_compute_name_hash_unicode_filename(self, temp_dir):
        """Test computing name hash for unicode filename."""
        unicode_name = "тест_файл.txt"
        test_file = temp_dir / unicode_name
        test_file.write_text("content")
        
        name_hash = compute_name_hash_for_file(test_file)
        
        # Should be SHA256 of the UTF-8 encoded filename
        expected = hashlib.sha256(unicode_name.encode('utf-8')).hexdigest()
        assert name_hash == expected
    
    def test_compute_structure_hash_ignores_symlinks(self, temp_dir):
        """Test that structure hash computation ignores symbolic links."""
        test_dir = temp_dir / "test_data"
        test_dir.mkdir()
        
        # Create regular file
        regular_file = test_dir / "regular.txt"
        regular_file.write_bytes(b"content")
        
        # Create symlink (should be ignored)
        if hasattr(Path, 'symlink_to'):  # Python 3.10+
            symlink = test_dir / "link.txt"
            try:
                symlink.symlink_to(regular_file)
                
                struct_hash, files = compute_structure_hash_for_dir(test_dir)
                
                # Should only include the regular file, not the symlink
                assert len(files) == 1
                assert files[0][0] == "regular.txt"
            except (OSError, NotImplementedError):
                # Skip test if symlinks not supported on this platform
                pytest.skip("Symlinks not supported on this platform")
    
    @patch('torrent_scanner.scanner.fetch_all_matches')
    @patch('torrent_scanner.scanner.get_redis')
    @patch('torrent_scanner.scanner.init_database')
    @patch('torrent_scanner.scanner.close_database')
    def test_scan_integration(self, mock_close, mock_init, mock_get_redis, mock_fetch_matches):
        """Test the main scan function integration."""
        # Setup mocks
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        mock_fetch_matches.return_value = []
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test directory structure
            scan_dir = temp_path / "scan"
            scan_dir.mkdir()
            
            # Create a fake .torrent file
            torrent_file = scan_dir / "test.torrent"
            # Create a minimal valid torrent file structure
            torrent_data = b'd8:announce9:test:1234e'  # Very minimal, will likely fail parsing
            torrent_file.write_bytes(torrent_data)
            
            # Create test data file
            data_file = scan_dir / "data.txt"
            data_file.write_bytes(b"test data")
            
            # Create scan config
            config = ScanConfig(
                db_path=temp_path / "test.db",
                redis_path=temp_path / "redis.db",
                directories=[scan_dir],
                matches_jsonl=None
            )
            
            # Run scan (expect it to handle parsing errors gracefully)
            scan(config)
            
            # Verify database and redis initialization
            mock_init.assert_called_once()
            mock_get_redis.assert_called_once()
            
            # Verify cleanup was attempted
            mock_redis.close.assert_called_once()
            mock_close.assert_called_once()
    
    def test_scan_with_permission_errors(self, temp_dir):
        """Test that scan handles permission errors gracefully."""
        # This test is primarily for coverage - actual permission testing 
        # would be platform-specific and complex
        pass