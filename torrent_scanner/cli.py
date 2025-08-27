"""
Command line interface for the torrent scanner.
Handles argument parsing and command execution.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

from .models import (
    init_database, close_database, fetch_all_matches, clean_database,
    fetch_unmatched_torrents, fetch_matched_torrents, get_data_paths_for_torrent,
    get_torrent_for_data_path, get_all_matches_dict
)
from .scanner import ScanConfig, scan, scan_torrents, scan_files, get_info


def _get_progress_callback(args):
    """Create a progress callback function for the given args."""
    current_pbar = None
    quiet = getattr(args, 'quiet', False)
    
    def progress_callback(message: str, current: int, total: int):
        nonlocal current_pbar
        
        if quiet:
            return
            
        if tqdm is None:
            # Fallback to simple text output if tqdm not available
            if total > 0:
                percent = (current / total) * 100
                print(f"\r{message}: {current}/{total} ({percent:.1f}%)", end="", flush=True)
                if current == total:
                    print()
            else:
                print(f"{message}...")
            return
        
        # Use tqdm for progress bars
        if current == 0 and total > 0:
            # Start new progress bar
            if current_pbar:
                current_pbar.close()
            current_pbar = tqdm(total=total, desc=message, unit="items")
        elif current_pbar and total > 0:
            # Update existing progress bar
            current_pbar.set_description(message)
            current_pbar.n = current
            current_pbar.refresh()
            if current == total:
                current_pbar.close()
                current_pbar = None
        elif total == 0:
            # Status message without progress bar
            if current_pbar:
                current_pbar.close()
                current_pbar = None
            print(f"{message}...")
    
    return progress_callback, lambda: current_pbar.close() if current_pbar else None


def cmd_scan(args: argparse.Namespace) -> None:
    """Handle the scan command."""
    db_path = Path(args.db) if args.db else Path.home() / ".torrent_scanner" / "torrents.db"
    redis_path = Path(args.redis) if args.redis else Path.home() / ".torrent_scanner" / "redis.db"
    
    db_path.parent.mkdir(parents=True, exist_ok=True)
    redis_path.parent.mkdir(parents=True, exist_ok=True)
    
    progress_callback, cleanup_progress = _get_progress_callback(args)
    
    cfg = ScanConfig(
        db_path=db_path,
        redis_path=redis_path,
        directories=[Path(d) for d in args.directories],
        matches_jsonl=Path(args.matches_jsonl).resolve() if args.matches_jsonl else None,
        progress_callback=progress_callback,
    )
    
    try:
        scan(cfg)
    except ImportError as e:
        if "redislite" in str(e):
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        else:
            raise
    finally:
        cleanup_progress()


def cmd_torrents(args: argparse.Namespace) -> None:
    """Handle the torrents command."""
    db_path = Path(args.db) if args.db else Path.home() / ".torrent_scanner" / "torrents.db"
    redis_path = Path(args.redis) if args.redis else Path.home() / ".torrent_scanner" / "redis.db"
    
    db_path.parent.mkdir(parents=True, exist_ok=True)
    redis_path.parent.mkdir(parents=True, exist_ok=True)
    
    progress_callback, cleanup_progress = _get_progress_callback(args)
    
    cfg = ScanConfig(
        db_path=db_path,
        redis_path=redis_path,
        directories=[Path(d) for d in args.directories],
        progress_callback=progress_callback,
    )
    
    try:
        scan_torrents(cfg)
    except ImportError as e:
        if "redislite" in str(e):
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        else:
            raise
    finally:
        cleanup_progress()


def cmd_files(args: argparse.Namespace) -> None:
    """Handle the files command."""
    db_path = Path(args.db) if args.db else Path.home() / ".torrent_scanner" / "torrents.db"
    redis_path = Path(args.redis) if args.redis else Path.home() / ".torrent_scanner" / "redis.db"
    
    db_path.parent.mkdir(parents=True, exist_ok=True)
    redis_path.parent.mkdir(parents=True, exist_ok=True)
    
    progress_callback, cleanup_progress = _get_progress_callback(args)
    
    cfg = ScanConfig(
        db_path=db_path,
        redis_path=redis_path,
        directories=[Path(d) for d in args.directories],
        matches_jsonl=Path(args.matches_jsonl).resolve() if args.matches_jsonl else None,
        progress_callback=progress_callback,
    )
    
    try:
        scan_files(cfg)
    except ImportError as e:
        if "redislite" in str(e):
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        else:
            raise
    finally:
        cleanup_progress()


def cmd_list_matches(args: argparse.Namespace) -> None:
    """Handle the list-matches command."""
    db_path = Path(args.db) if args.db else Path.home() / ".torrent_scanner" / "torrents.db"
    
    init_database(db_path)
    try:
        rows = fetch_all_matches()
        if args.jsonl:
            with Path(args.jsonl).open("w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        else:
            for r in rows:
                print(json.dumps(r, ensure_ascii=False))
    finally:
        close_database()


def cmd_info(args: argparse.Namespace) -> None:
    """Handle the info command."""
    db_path = Path(args.db) if args.db else Path.home() / ".torrent_scanner" / "torrents.db"
    
    if not db_path.exists():
        print(f"Database {db_path} does not exist")
        return
    
    try:
        info = get_info(db_path)
        if args.json:
            print(json.dumps(info, ensure_ascii=False))
        else:
            print(f"Torrent Scanner Database Info:")
            print(f"  Database path: {db_path}")
            print(f"  Total torrents indexed: {info['total_torrents']}")
            print(f"  Matched torrents: {info['matched_torrents']}")
            print(f"  Unmatched torrents: {info['unmatched_torrents']}")
            print(f"  Total matches: {info['total_matches']}")
            print(f"  Single-file torrents: {info['single_file_torrents']}")
            print(f"  Multi-file torrents: {info['multi_file_torrents']}")
            
            # Format size in human-readable format
            size_bytes = info['total_size_bytes']
            if size_bytes >= 1024**4:
                size_str = f"{size_bytes / (1024**4):.1f} TB"
            elif size_bytes >= 1024**3:
                size_str = f"{size_bytes / (1024**3):.1f} GB"
            elif size_bytes >= 1024**2:
                size_str = f"{size_bytes / (1024**2):.1f} MB"
            elif size_bytes >= 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes} bytes"
            
            print(f"  Total size: {size_str}")
    except Exception as e:
        print(f"Error getting info: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_clean(args: argparse.Namespace) -> None:
    """Handle the clean command."""
    db_path = Path(args.db) if args.db else Path.home() / ".torrent_scanner" / "torrents.db"
    redis_path = Path(args.redis) if args.redis else Path.home() / ".torrent_scanner" / "redis.db"
    
    if not db_path.exists():
        print(f"Database {db_path} does not exist")
        return
    
    init_database(db_path)
    try:
        clean_database()
        print(f"Database {db_path} has been reset")
    finally:
        close_database()
    
    if redis_path.exists():
        redis_path.unlink()
        print(f"Redis database {redis_path} has been deleted")


def cmd_list_unmatched(args: argparse.Namespace) -> None:
    """Handle the list-unmatched command."""
    db_path = Path(args.db) if args.db else Path.home() / ".torrent_scanner" / "torrents.db"
    
    if not db_path.exists():
        print(f"Database {db_path} does not exist", file=sys.stderr)
        sys.exit(1)
    
    init_database(db_path)
    try:
        torrents = fetch_unmatched_torrents()
        
        if args.format == 'jsonl':
            for t in torrents:
                print(json.dumps(t, ensure_ascii=False))
        elif args.format == 'json':
            print(json.dumps(torrents, ensure_ascii=False, indent=2))
        elif args.format == 'paths':
            for t in torrents:
                print(t['torrent_path'])
        else:  # table format
            if torrents:
                print(f"{'Info Hash':<40} {'Name':<50} {'Path'}")
                print("-" * 100)
                for t in torrents:
                    name = t['name'][:47] + "..." if len(t['name']) > 50 else t['name']
                    print(f"{t['info_hash']:<40} {name:<50} {t['torrent_path']}")
            else:
                print("No unmatched torrents found")
    finally:
        close_database()


def cmd_list_matched(args: argparse.Namespace) -> None:
    """Handle the list-matched command."""
    db_path = Path(args.db) if args.db else Path.home() / ".torrent_scanner" / "torrents.db"
    
    if not db_path.exists():
        print(f"Database {db_path} does not exist", file=sys.stderr)
        sys.exit(1)
    
    init_database(db_path)
    try:
        torrents = fetch_matched_torrents()
        
        if args.format == 'jsonl':
            for t in torrents:
                print(json.dumps(t, ensure_ascii=False))
        elif args.format == 'json':
            print(json.dumps(torrents, ensure_ascii=False, indent=2))
        elif args.format == 'paths':
            for t in torrents:
                print(t['torrent_path'])
        else:  # table format
            if torrents:
                print(f"{'Info Hash':<40} {'Matches':<8} {'Name':<42} {'Path'}")
                print("-" * 100)
                for t in torrents:
                    name = t['name'][:39] + "..." if len(t['name']) > 42 else t['name']
                    print(f"{t['info_hash']:<40} {t['match_count']:<8} {name:<42} {t['torrent_path']}")
            else:
                print("No matched torrents found")
    finally:
        close_database()


def cmd_get_data(args: argparse.Namespace) -> None:
    """Handle the get-data command."""
    db_path = Path(args.db) if args.db else Path.home() / ".torrent_scanner" / "torrents.db"
    
    if not db_path.exists():
        print(f"Database {db_path} does not exist", file=sys.stderr)
        sys.exit(1)
    
    init_database(db_path)
    try:
        data_paths = get_data_paths_for_torrent(args.torrent)
        
        if args.format == 'json':
            print(json.dumps(data_paths, ensure_ascii=False, indent=2))
        else:  # line format
            for path in data_paths:
                print(path)
            
        if not data_paths and not args.quiet:
            print("No data found for this torrent", file=sys.stderr)
    finally:
        close_database()


def cmd_get_torrent(args: argparse.Namespace) -> None:
    """Handle the get-torrent command."""
    db_path = Path(args.db) if args.db else Path.home() / ".torrent_scanner" / "torrents.db"
    
    if not db_path.exists():
        print(f"Database {db_path} does not exist", file=sys.stderr)
        sys.exit(1)
    
    init_database(db_path)
    try:
        torrent_info = get_torrent_for_data_path(args.data_path)
        
        if torrent_info:
            if args.format == 'json':
                print(json.dumps(torrent_info, ensure_ascii=False, indent=2))
            elif args.format == 'info-hash':
                print(torrent_info['info_hash'])
            elif args.format == 'path':
                print(torrent_info['torrent_path'])
            else:  # full format
                print(f"Info Hash: {torrent_info['info_hash']}")
                print(f"Torrent Path: {torrent_info['torrent_path']}")
                print(f"Name: {torrent_info['name']}")
                print(f"Multi-file: {torrent_info['is_multi']}")
                print(f"Total Size: {torrent_info['total_length']} bytes")
        else:
            if not args.quiet:
                print("No torrent found for this data path", file=sys.stderr)
            sys.exit(1)
    finally:
        close_database()


def cmd_export_matches(args: argparse.Namespace) -> None:
    """Handle the export-matches command."""
    db_path = Path(args.db) if args.db else Path.home() / ".torrent_scanner" / "torrents.db"
    
    if not db_path.exists():
        print(f"Database {db_path} does not exist", file=sys.stderr)
        sys.exit(1)
    
    init_database(db_path)
    try:
        matches_dict = get_all_matches_dict()
        
        if args.output:
            output_path = Path(args.output)
            with output_path.open('w', encoding='utf-8') as f:
                json.dump(matches_dict, f, ensure_ascii=False, indent=2)
            print(f"Exported {len(matches_dict)} matched torrents to {output_path}")
        else:
            print(json.dumps(matches_dict, ensure_ascii=False, indent=2))
    finally:
        close_database()


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command line argument parser."""
    p = argparse.ArgumentParser(description="Index .torrent files and match folders/files.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Scan directories for .torrent files and matching data")
    p_scan.add_argument("directories", nargs="+", help="Directories to scan recursively for .torrent files and data")
    p_scan.add_argument("--db", help="SQLite database path (default: ~/.torrent_scanner/torrents.db)")
    p_scan.add_argument("--redis", help="Redis database path (default: ~/.torrent_scanner/redis.db)")
    p_scan.add_argument("--matches-jsonl", help="Write matched torrents to JSONL file")
    p_scan.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output")
    p_scan.set_defaults(func=cmd_scan)

    p_torrents = sub.add_parser("torrents", help="Scan directories for .torrent files only (no data matching)")
    p_torrents.add_argument("directories", nargs="+", help="Directories to scan recursively for .torrent files")
    p_torrents.add_argument("--db", help="SQLite database path (default: ~/.torrent_scanner/torrents.db)")
    p_torrents.add_argument("--redis", help="Redis database path (default: ~/.torrent_scanner/redis.db)")
    p_torrents.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output")
    p_torrents.set_defaults(func=cmd_torrents)

    p_files = sub.add_parser("files", help="Scan directories for data files that match existing torrents")
    p_files.add_argument("directories", nargs="+", help="Directories to scan recursively for data files")
    p_files.add_argument("--db", help="SQLite database path (default: ~/.torrent_scanner/torrents.db)")
    p_files.add_argument("--redis", help="Redis database path (default: ~/.torrent_scanner/redis.db)")
    p_files.add_argument("--matches-jsonl", help="Write matched torrents to JSONL file")
    p_files.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output")
    p_files.set_defaults(func=cmd_files)

    p_list = sub.add_parser("list-matches", help="List matched torrents as JSONL")
    p_list.add_argument("--db", help="SQLite database path (default: ~/.torrent_scanner/torrents.db)")
    p_list.add_argument("--jsonl", help="Write output to JSONL file instead of stdout")
    p_list.set_defaults(func=cmd_list_matches)

    p_info = sub.add_parser("info", help="Show database statistics and information")
    p_info.add_argument("--db", help="SQLite database path (default: ~/.torrent_scanner/torrents.db)")
    p_info.add_argument("--json", action="store_true", help="Output information as JSON")
    p_info.set_defaults(func=cmd_info)

    p_clean = sub.add_parser("clean", help="Reset the database by removing all torrents and matches")
    p_clean.add_argument("--db", help="SQLite database path (default: ~/.torrent_scanner/torrents.db)")
    p_clean.add_argument("--redis", help="Redis database path (default: ~/.torrent_scanner/redis.db)")
    p_clean.set_defaults(func=cmd_clean)

    p_unmatched = sub.add_parser("list-unmatched", help="List torrents with no data matches")
    p_unmatched.add_argument("--db", help="SQLite database path (default: ~/.torrent_scanner/torrents.db)")
    p_unmatched.add_argument("--format", choices=['table', 'json', 'jsonl', 'paths'], 
                            default='table', help="Output format")
    p_unmatched.set_defaults(func=cmd_list_unmatched)
    
    p_matched = sub.add_parser("list-matched", help="List torrents with data matches")
    p_matched.add_argument("--db", help="SQLite database path (default: ~/.torrent_scanner/torrents.db)")
    p_matched.add_argument("--format", choices=['table', 'json', 'jsonl', 'paths'], 
                          default='table', help="Output format")
    p_matched.set_defaults(func=cmd_list_matched)
    
    p_get_data = sub.add_parser("get-data", help="Get data paths for a torrent")
    p_get_data.add_argument("torrent", help="Info hash (40 hex chars) or torrent file path")
    p_get_data.add_argument("--db", help="SQLite database path (default: ~/.torrent_scanner/torrents.db)")
    p_get_data.add_argument("--format", choices=['lines', 'json'], default='lines', 
                           help="Output format")
    p_get_data.add_argument("-q", "--quiet", action="store_true", 
                           help="Suppress 'not found' messages")
    p_get_data.set_defaults(func=cmd_get_data)
    
    p_get_torrent = sub.add_parser("get-torrent", help="Get torrent info for a data path")
    p_get_torrent.add_argument("data_path", help="Path to data directory or file")
    p_get_torrent.add_argument("--db", help="SQLite database path (default: ~/.torrent_scanner/torrents.db)")
    p_get_torrent.add_argument("--format", choices=['full', 'json', 'info-hash', 'path'], 
                              default='full', help="Output format")
    p_get_torrent.add_argument("-q", "--quiet", action="store_true", 
                              help="Suppress 'not found' messages")
    p_get_torrent.set_defaults(func=cmd_get_torrent)
    
    p_export = sub.add_parser("export-matches", help="Export all matches as JSON dictionary")
    p_export.add_argument("--db", help="SQLite database path (default: ~/.torrent_scanner/torrents.db)")
    p_export.add_argument("-o", "--output", help="Output file path (default: stdout)")
    p_export.set_defaults(func=cmd_export_matches)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0