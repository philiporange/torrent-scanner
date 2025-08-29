"""
Tests for CLI commands and argument parsing.
Updated for the new improved CLI structure.
"""

import argparse
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from torrent_scanner.cli import (
    build_arg_parser,
    cmd_update,
    cmd_list,
    main
)


class TestCLI:
    
    def test_build_arg_parser(self):
        """Test that argument parser is built correctly."""
        parser = build_arg_parser()
        
        # Test update command (replaces old scan)
        args = parser.parse_args(['update', '/path/to/dir1', '/path/to/dir2'])
        assert args.cmd == 'update'
        assert args.paths == ['/path/to/dir1', '/path/to/dir2']
        assert args.db is None  # Should use default
        assert args.redis is None  # Should use default
        assert args.output is None
        
        # Test update with optional arguments (global args must come first)
        args = parser.parse_args([
            '--db', '/custom/db.db',
            '--redis', '/custom/redis.db',
            'update', '/path/to/dir',
            '--output', '/output/matches.jsonl'
        ])
        assert args.db == '/custom/db.db'
        assert args.redis == '/custom/redis.db'
        assert args.output == '/output/matches.jsonl'
        
        # Test list command
        args = parser.parse_args(['list'])
        assert args.cmd == 'list'
        assert args.filter == 'all'  # Default filter
        assert args.format == 'table'  # Default format
        assert args.output is None
        
        # Test list with filters
        args = parser.parse_args(['list', '--filter', 'matched', '--format', 'json'])
        assert args.filter == 'matched'
        assert args.format == 'json'
        
        # Test index command
        args = parser.parse_args(['index', '/torrents'])
        assert args.cmd == 'index'
        assert args.paths == ['/torrents']
        
        # Test check command
        args = parser.parse_args(['check', 'abc123def456'])
        assert args.cmd == 'check'
        assert args.torrent == 'abc123def456'
        
        # Test locate command
        args = parser.parse_args(['locate', 'abc123def456'])
        assert args.cmd == 'locate'
        assert args.torrent == 'abc123def456'
        assert args.format == 'lines'  # Default
        
        # Test stats command
        args = parser.parse_args(['stats'])
        assert args.cmd == 'stats'
    
    def test_arg_parser_errors(self):
        """Test argument parser error cases."""
        parser = build_arg_parser()
        
        # Missing command
        with pytest.raises(SystemExit):
            parser.parse_args([])
        
        # Update without paths
        with pytest.raises(SystemExit):
            parser.parse_args(['update'])
        
        # Check without torrent identifier
        with pytest.raises(SystemExit):
            parser.parse_args(['check'])
    
    @patch('torrent_scanner.cli.TorrentScanner')
    def test_cmd_update_with_defaults(self, mock_scanner_class):
        """Test cmd_update with default database paths."""
        # Create a mock scanner instance
        mock_scanner = MagicMock()
        mock_scanner_class.return_value = mock_scanner
        mock_scanner.update.return_value = {
            'indexed': {'processed': 5, 'new': 2},
            'matches': [],
            'match_count': 0
        }
        
        args = argparse.Namespace(
            paths=['/test/dir1', '/test/dir2'],
            db=None,  # Should use default
            redis=None,  # Should use default
            output=None,
            quiet=False
        )
        
        cmd_update(args)
        
        # Verify scanner was created with default paths
        mock_scanner_class.assert_called_once_with(db_path=None, redis_path=None)
        
        # Verify update was called with correct directories
        mock_scanner.update.assert_called_once()
        call_args = mock_scanner.update.call_args
        directories = call_args[0][0]  # First positional argument
        assert len(directories) == 2
        assert str(directories[0]) == '/test/dir1'
        assert str(directories[1]) == '/test/dir2'
        assert call_args[1]['quiet'] == False  # quiet keyword argument
    
    @patch('torrent_scanner.cli.TorrentScanner')
    def test_cmd_update_with_custom_paths(self, mock_scanner_class):
        """Test cmd_update with custom database paths."""
        mock_scanner = MagicMock()
        mock_scanner_class.return_value = mock_scanner
        mock_scanner.update.return_value = {
            'indexed': {'processed': 3, 'new': 1},
            'matches': [{'info_hash': 'abc123', 'name': 'test'}],
            'match_count': 1
        }
        
        args = argparse.Namespace(
            paths=['/test/dir'],
            db='/custom/torrents.db',
            redis='/custom/redis.db',
            output='/output/matches.json',
            quiet=True
        )
        
        with patch('pathlib.Path.open', create=True) as mock_open, \
             patch('json.dump') as mock_json_dump:
            
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            cmd_update(args)
            
            # Verify scanner was created with custom paths
            mock_scanner_class.assert_called_once()
            call_args = mock_scanner_class.call_args
            assert str(call_args[1]['db_path']) == '/custom/torrents.db'
            assert str(call_args[1]['redis_path']) == '/custom/redis.db'
            
            # Verify output was written
            mock_open.assert_called_once()
            mock_json_dump.assert_called_once()
    
    @patch('torrent_scanner.cli.TorrentScanner')
    def test_cmd_list_default(self, mock_scanner_class):
        """Test cmd_list with default parameters."""
        mock_scanner = MagicMock()
        mock_scanner_class.return_value = mock_scanner
        mock_scanner.list_torrents.return_value = [
            {
                'info_hash': 'abc123',
                'name': 'test_torrent',
                'torrent_path': '/path/test.torrent'
            }
        ]
        
        args = argparse.Namespace(
            db=None,
            redis=None,
            filter='all',
            format='table',
            output=None
        )
        
        with patch('torrent_scanner.cli._print_table') as mock_print_table:
            cmd_list(args)
            
            mock_scanner.list_torrents.assert_called_once_with(filter_type='all')
            mock_print_table.assert_called_once()
    
    @patch('torrent_scanner.cli.TorrentScanner')
    def test_cmd_list_json_output(self, mock_scanner_class):
        """Test cmd_list with JSON output."""
        mock_scanner = MagicMock()
        mock_scanner_class.return_value = mock_scanner
        mock_scanner.list_torrents.return_value = [
            {'info_hash': 'abc123', 'name': 'test1'},
            {'info_hash': 'def456', 'name': 'test2'}
        ]
        
        args = argparse.Namespace(
            db=None,
            redis=None,
            filter='matched',
            format='json',
            output=None
        )
        
        with patch('builtins.print') as mock_print:
            cmd_list(args)
            
            mock_scanner.list_torrents.assert_called_once_with(filter_type='matched')
            # Verify JSON was printed
            mock_print.assert_called_once()
            printed_data = mock_print.call_args[0][0]
            parsed = json.loads(printed_data)
            assert len(parsed) == 2
            assert parsed[0]['info_hash'] == 'abc123'
    
    def test_main_with_new_commands(self):
        """Test main function with new command structure."""
        # Test with update command
        with patch('torrent_scanner.cli.cmd_update') as mock_cmd_update:
            result = main(['update', '/test/dir'])
            assert result == 0
            mock_cmd_update.assert_called_once()
        
        # Test with list command
        with patch('torrent_scanner.cli.cmd_list') as mock_cmd_list:
            result = main(['list'])
            assert result == 0
            mock_cmd_list.assert_called_once()
        
        # Test with stats command
        with patch('torrent_scanner.cli.cmd_stats') as mock_cmd_stats:
            result = main(['stats'])
            assert result == 0
            mock_cmd_stats.assert_called_once()
    
    def test_main_invalid_command(self):
        """Test main function with invalid command."""
        with pytest.raises(SystemExit):
            main(['invalid-command'])
    
    def test_help_text_content(self):
        """Test that help text contains expected information for new commands."""
        parser = build_arg_parser()
        
        # Test main help
        help_text = parser.format_help()
        assert 'index' in help_text
        assert 'match' in help_text
        assert 'update' in help_text
        assert 'check' in help_text
        assert 'locate' in help_text
        assert 'list' in help_text
        assert 'stats' in help_text
        
        # Test update subcommand help
        update_parser = None
        for action in parser._subparsers._actions:
            if hasattr(action, 'choices') and action.choices and 'update' in action.choices:
                update_parser = action.choices['update']
                break
        
        assert update_parser is not None
        update_help = update_parser.format_help()
        assert 'paths' in update_help
        # Default paths are mentioned in global help, not subcommand help
        assert 'paths' in update_help
        
        # Test list subcommand help
        list_parser = None
        for action in parser._subparsers._actions:
            if hasattr(action, 'choices') and action.choices and 'list' in action.choices:
                list_parser = action.choices['list']
                break
        
        assert list_parser is not None
        list_help = list_parser.format_help()
        assert 'filter' in list_help
        assert 'format' in list_help
    
    def test_command_migration_coverage(self):
        """Test that all old commands have new equivalents."""
        parser = build_arg_parser()
        
        # Get list of available commands
        commands = []
        for action in parser._subparsers._actions:
            if hasattr(action, 'choices') and action.choices:
                commands.extend(action.choices.keys())
        
        # Verify new command structure
        expected_commands = [
            'index',     # replaces 'torrents'
            'match',     # replaces 'files'  
            'update',    # replaces 'scan'
            'check',     # new query command
            'locate',    # replaces 'get-data'
            'identify',  # replaces 'get-torrent'
            'list',      # replaces 'list-matches', 'list-unmatched'
            'stats',     # replaces 'info'
            'export',    # replaces 'export-matches'
            'reset'      # replaces 'clean'
        ]
        
        for cmd in expected_commands:
            assert cmd in commands, f"Command '{cmd}' not found in parser"
    
    def test_global_options_available(self):
        """Test that global options are available for all commands."""
        parser = build_arg_parser()
        
        # Test that --db and --redis are global options
        # Parse a command with global options
        args = parser.parse_args(['--db', '/test.db', '--redis', '/test.redis', 'stats'])
        assert args.db == '/test.db'
        assert args.redis == '/test.redis'
        assert args.cmd == 'stats'
        
        # Test with different command
        args = parser.parse_args(['--db', '/other.db', 'list'])
        assert args.db == '/other.db'
        assert args.cmd == 'list'