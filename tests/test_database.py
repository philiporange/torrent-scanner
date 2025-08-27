"""
Tests for database operations using Peewee ORM.
"""

import tempfile
import time
from pathlib import Path

import pytest
from torrent_scanner.torrent import TorrentMeta, save_torrent_meta
from torrent_scanner.models import (
    init_database, close_database, database,
    get_torrent_by_info_hash, add_match, 
    fetch_all_matches, fetch_files_for_torrent, Torrent, TorrentFile, Match
)


class TestDatabase:
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        
        init_database(db_path)
        yield db_path
        close_database()
        db_path.unlink()
    
    @pytest.fixture
    def sample_single_file_torrent(self):
        """Create a sample single-file torrent metadata."""
        return TorrentMeta(
            info_hash_hex='a' * 40,  # 40-char hex string
            name='test_file.txt',
            name_hash_hex='b' * 64,  # 64-char hex string
            is_multi=False,
            total_length=1024,
            structure_hash_hex=None,
            files=[('test_file.txt', 1024)],
            created_unix=int(time.time()),
            created_by='test_client',
            comment='Test torrent'
        )
    
    @pytest.fixture
    def sample_multi_file_torrent(self):
        """Create a sample multi-file torrent metadata."""
        return TorrentMeta(
            info_hash_hex='c' * 40,
            name='test_folder',
            name_hash_hex='d' * 64,
            is_multi=True,
            total_length=2048,
            structure_hash_hex='e' * 64,
            files=[('file1.txt', 1024), ('subdir/file2.txt', 1024)],
            created_unix=int(time.time()),
            created_by='test_client',
            comment='Multi-file test torrent'
        )
    
    def test_init_database_creates_tables(self, temp_db):
        """Test that init_database creates the required tables."""
        # Tables should exist and be queryable
        assert Torrent.table_exists()
        assert TorrentFile.table_exists()
        assert Match.table_exists()
        
        # Should be able to query empty tables
        assert Torrent.select().count() == 0
        assert TorrentFile.select().count() == 0
        assert Match.select().count() == 0
    
    def test_save_single_file_torrent(self, temp_db, sample_single_file_torrent):
        """Test saving a single-file torrent."""
        torrent = save_torrent_meta(sample_single_file_torrent, '/path/to/test.torrent')
        
        assert torrent is not None
        assert torrent.info_hash == sample_single_file_torrent.info_hash_hex
        assert torrent.name == sample_single_file_torrent.name
        assert torrent.is_multi == False
        assert torrent.total_length == 1024
        
        # Verify file was created
        files = list(torrent.files)
        assert len(files) == 1
        assert files[0].path == 'test_file.txt'
        assert files[0].length == 1024
    
    def test_save_multi_file_torrent(self, temp_db, sample_multi_file_torrent):
        """Test saving a multi-file torrent."""
        torrent = save_torrent_meta(sample_multi_file_torrent, '/path/to/multi.torrent')
        
        assert torrent is not None
        assert torrent.is_multi == True
        assert torrent.structure_hash == sample_multi_file_torrent.structure_hash_hex
        assert torrent.total_length == 2048
        
        # Verify both files were created
        files = list(torrent.files.order_by(TorrentFile.file_index))
        assert len(files) == 2
        assert files[0].path == 'file1.txt'
        assert files[0].length == 1024
        assert files[1].path == 'subdir/file2.txt'
        assert files[1].length == 1024
    
    def test_save_duplicate_torrent(self, temp_db, sample_single_file_torrent):
        """Test that saving duplicate torrent returns None."""
        # Save first time
        torrent1 = save_torrent_meta(sample_single_file_torrent, '/path/to/test1.torrent')
        assert torrent1 is not None
        
        # Try to save same info_hash again
        torrent2 = save_torrent_meta(sample_single_file_torrent, '/path/to/test2.torrent')
        assert torrent2 is None
    
    def test_get_torrent_by_info_hash(self, temp_db, sample_single_file_torrent):
        """Test retrieving torrent by info hash."""
        # Save torrent
        saved_torrent = save_torrent_meta(sample_single_file_torrent, '/path/to/test.torrent')
        
        # Retrieve by info hash
        found_torrent = get_torrent_by_info_hash(sample_single_file_torrent.info_hash_hex)
        assert found_torrent is not None
        assert found_torrent.id == saved_torrent.id
        
        # Try non-existent info hash
        not_found = get_torrent_by_info_hash('f' * 40)
        assert not_found is None
    
    def test_add_match(self, temp_db, sample_single_file_torrent):
        """Test adding a data match."""
        # Save torrent first
        save_torrent_meta(sample_single_file_torrent, '/path/to/test.torrent')
        
        # Add match
        success = add_match(sample_single_file_torrent.info_hash_hex, '/data/matched_file.txt')
        assert success is True
        
        # Verify match was added
        matches = Match.select()
        assert matches.count() == 1
        match = matches.first()
        assert '/data/matched_file.txt' in match.data_path
    
    def test_add_match_nonexistent_torrent(self, temp_db):
        """Test adding match for non-existent torrent."""
        success = add_match('nonexistent' + 'a' * 30, '/data/file.txt')
        assert success is False
    
    def test_add_duplicate_match(self, temp_db, sample_single_file_torrent):
        """Test adding duplicate match."""
        # Save torrent
        save_torrent_meta(sample_single_file_torrent, '/path/to/test.torrent')
        
        # Add match twice
        success1 = add_match(sample_single_file_torrent.info_hash_hex, '/data/file.txt')
        success2 = add_match(sample_single_file_torrent.info_hash_hex, '/data/file.txt')
        
        assert success1 is True
        assert success2 is False  # Duplicate should fail
    
    def test_fetch_all_matches(self, temp_db, sample_single_file_torrent):
        """Test fetching all matches."""
        # Save torrent
        save_torrent_meta(sample_single_file_torrent, '/path/to/test.torrent')
        
        # Add some matches
        add_match(sample_single_file_torrent.info_hash_hex, '/data/file1.txt')
        add_match(sample_single_file_torrent.info_hash_hex, '/data/file2.txt')
        
        # Fetch matches
        matches = fetch_all_matches()
        
        assert len(matches) == 1  # One torrent
        match = matches[0]
        
        assert match['info_hash'] == sample_single_file_torrent.info_hash_hex
        assert match['name'] == sample_single_file_torrent.name
        assert match['is_multi'] is False
        assert len(match['matches']) == 2
        assert '/data/file1.txt' in match['matches']
        assert '/data/file2.txt' in match['matches']
    
    def test_fetch_files_for_torrent(self, temp_db, sample_multi_file_torrent):
        """Test fetching file list for a torrent."""
        # Save multi-file torrent
        torrent = save_torrent_meta(sample_multi_file_torrent, '/path/to/multi.torrent')
        
        # Fetch files
        files = fetch_files_for_torrent(torrent)
        
        assert len(files) == 2
        assert files[0] == ('file1.txt', 1024)
        assert files[1] == ('subdir/file2.txt', 1024)
    
    def test_database_wal_mode(self, temp_db):
        """Test that database is created in WAL mode."""
        # Check pragma through database connection
        result = database.execute_sql("PRAGMA journal_mode").fetchone()
        mode = result[0] if result else None
        
        assert mode and mode.lower() == 'wal'