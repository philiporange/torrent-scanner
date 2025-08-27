"""
Tests for CLI commands and argument parsing.
"""

import argparse
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from torrent_scanner.cli import (
    build_arg_parser,
    cmd_scan,
    cmd_list_matches,
    main
)


class TestCLI:
    
    def test_build_arg_parser(self):
        """Test that argument parser is built correctly."""
        parser = build_arg_parser()
        
        # Test scan command
        args = parser.parse_args(['scan', '/path/to/dir1', '/path/to/dir2'])
        assert args.cmd == 'scan'
        assert args.directories == ['/path/to/dir1', '/path/to/dir2']
        assert args.db is None  # Should use default
        assert args.redis is None  # Should use default
        assert args.matches_jsonl is None
        
        # Test scan with optional arguments
        args = parser.parse_args([
            'scan', '/path/to/dir',
            '--db', '/custom/db.db',
            '--redis', '/custom/redis.db',
            '--matches-jsonl', '/output/matches.jsonl'
        ])
        assert args.db == '/custom/db.db'
        assert args.redis == '/custom/redis.db'
        assert args.matches_jsonl == '/output/matches.jsonl'
        
        # Test list-matches command
        args = parser.parse_args(['list-matches'])
        assert args.cmd == 'list-matches'
        assert args.db is None  # Should use default
        assert args.jsonl is None
        
        # Test list-matches with optional arguments
        args = parser.parse_args(['list-matches', '--db', '/custom/db.db', '--jsonl', '/output.jsonl'])
        assert args.db == '/custom/db.db'
        assert args.jsonl == '/output.jsonl'
    
    def test_arg_parser_errors(self):
        """Test argument parser error cases."""
        parser = build_arg_parser()
        
        # Missing command
        with pytest.raises(SystemExit):
            parser.parse_args([])
        
        # Scan without directories
        with pytest.raises(SystemExit):
            parser.parse_args(['scan'])
    
    @patch('torrent_scanner.cli.scan')
    def test_cmd_scan_with_defaults(self, mock_scan):
        """Test cmd_scan with default database paths."""
        # Create a mock args object
        args = argparse.Namespace(
            directories=['/test/dir1', '/test/dir2'],
            db=None,  # Should use default
            redis=None,  # Should use default
            matches_jsonl=None
        )
        
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            cmd_scan(args)
            
            # Verify mkdir was called to create parent directories
            assert mock_mkdir.call_count >= 2  # For both db and redis paths
            
            # Verify scan was called
            mock_scan.assert_called_once()
            config = mock_scan.call_args[0][0]
            
            # Check that default paths were used
            assert config.db_path.name == 'torrents.db'
            assert config.redis_path.name == 'redis.db'
            assert '.torrent_scanner' in str(config.db_path)
            assert '.torrent_scanner' in str(config.redis_path)
            
            # Check directories
            assert len(config.directories) == 2
            assert str(config.directories[0]) == '/test/dir1'
            assert str(config.directories[1]) == '/test/dir2'
    
    @patch('torrent_scanner.cli.scan')
    def test_cmd_scan_with_custom_paths(self, mock_scan):
        """Test cmd_scan with custom database paths."""
        args = argparse.Namespace(
            directories=['/test/dir'],
            db='/custom/torrents.db',
            redis='/custom/redis.db',
            matches_jsonl='/output/matches.jsonl'
        )
        
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            cmd_scan(args)
            
            config = mock_scan.call_args[0][0]
            
            assert str(config.db_path) == '/custom/torrents.db'
            assert str(config.redis_path) == '/custom/redis.db'
            assert str(config.matches_jsonl) == '/output/matches.jsonl'
    
    @patch('torrent_scanner.cli.init_database')
    @patch('torrent_scanner.cli.fetch_all_matches')
    @patch('torrent_scanner.cli.close_database')
    def test_cmd_list_matches_stdout(self, mock_close, mock_fetch, mock_init):
        """Test cmd_list_matches output to stdout."""
        # Setup mocks
        mock_fetch.return_value = [
            {
                'info_hash': 'abc123',
                'name': 'test_torrent',
                'matches': ['/data/file1.txt', '/data/file2.txt']
            }
        ]
        
        args = argparse.Namespace(db=None, jsonl=None)
        
        with patch('builtins.print') as mock_print:
            cmd_list_matches(args)
            
            # Verify database operations
            mock_init.assert_called_once()
            mock_fetch.assert_called_once()
            mock_close.assert_called_once()
            
            # Verify output
            mock_print.assert_called_once()
            printed_json = mock_print.call_args[0][0]
            data = json.loads(printed_json)
            assert data['info_hash'] == 'abc123'
            assert data['name'] == 'test_torrent'
    
    @patch('torrent_scanner.cli.init_database')
    @patch('torrent_scanner.cli.fetch_all_matches')
    @patch('torrent_scanner.cli.close_database')
    def test_cmd_list_matches_jsonl_file(self, mock_close, mock_fetch, mock_init):
        """Test cmd_list_matches output to JSONL file."""
        # Setup mocks
        mock_fetch.return_value = [
            {'info_hash': 'abc123', 'name': 'test1'},
            {'info_hash': 'def456', 'name': 'test2'}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            jsonl_path = f.name
        
        try:
            args = argparse.Namespace(db=None, jsonl=jsonl_path)
            cmd_list_matches(args)
            
            # Verify file contents
            with open(jsonl_path, 'r') as f:
                lines = f.readlines()
            
            assert len(lines) == 2
            data1 = json.loads(lines[0])
            data2 = json.loads(lines[1])
            
            assert data1['info_hash'] == 'abc123'
            assert data2['info_hash'] == 'def456'
            
        finally:
            Path(jsonl_path).unlink()
    
    @patch('torrent_scanner.cli.cmd_scan')
    def test_main_scan_command(self, mock_cmd_scan):
        """Test main function with scan command."""
        result = main(['scan', '/test/dir'])
        
        assert result == 0
        mock_cmd_scan.assert_called_once()
    
    @patch('torrent_scanner.cli.cmd_list_matches')
    def test_main_list_matches_command(self, mock_cmd_list):
        """Test main function with list-matches command."""
        result = main(['list-matches'])
        
        assert result == 0
        mock_cmd_list.assert_called_once()
    
    def test_main_invalid_command(self):
        """Test main function with invalid command."""
        with pytest.raises(SystemExit):
            main(['invalid-command'])
    
    def test_help_text_content(self):
        """Test that help text contains expected information."""
        parser = build_arg_parser()
        
        # Test main help
        help_text = parser.format_help()
        assert 'scan' in help_text
        assert 'list-matches' in help_text
        
        # Test scan subcommand help
        scan_parser = None
        for action in parser._subparsers._actions:
            if hasattr(action, 'choices') and action.choices and 'scan' in action.choices:
                scan_parser = action.choices['scan']
                break
        
        assert scan_parser is not None
        scan_help = scan_parser.format_help()
        assert 'directories' in scan_help
        assert '~/.torrent_scanner' in scan_help  # Default paths mentioned
        
        # Test list-matches subcommand help
        list_parser = None
        for action in parser._subparsers._actions:
            if hasattr(action, 'choices') and action.choices and 'list-matches' in action.choices:
                list_parser = action.choices['list-matches']
                break
        
        assert list_parser is not None
        list_help = list_parser.format_help()
        assert 'JSONL' in list_help