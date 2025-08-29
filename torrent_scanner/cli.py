"""
Command line interface for the torrent scanner.

This module provides an improved CLI with clear separation of concerns and consistent
command structure. Commands are organized into logical groups with intuitive naming.
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

from .api import TorrentScanner, database_session
from .models import clean_database


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


def _get_scanner(args) -> TorrentScanner:
    """Create a TorrentScanner instance from command line arguments."""
    db_path = Path(args.db) if args.db else None
    redis_path = Path(args.redis) if args.redis else None
    return TorrentScanner(db_path=db_path, redis_path=redis_path)


def _write_output(content: str, output_path: Optional[str]) -> None:
    """Write content to file or stdout."""
    if output_path:
        with Path(output_path).open('w', encoding='utf-8') as f:
            f.write(content)
    else:
        print(content)


def _print_table(data: List[Dict[str, Any]], headers: List[str], widths: List[int]) -> None:
    """Print data as a formatted table."""
    if not data:
        print("No results found")
        return
    
    # Print header
    header_line = " ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(header_line)
    print("-" * len(header_line))
    
    # Print rows
    for row in data:
        values = []
        for i, header in enumerate(headers):
            key = header.lower().replace(' ', '_')
            value = str(row.get(key, ''))
            if len(value) > widths[i]:
                value = value[:widths[i]-3] + "..."
            values.append(value.ljust(widths[i]))
        print(" ".join(values))


# --- Indexing Commands ---

def cmd_index(args: argparse.Namespace) -> None:
    """Index torrent files into database."""
    scanner = _get_scanner(args)
    directories = [Path(d) for d in args.paths]
    
    try:
        results = scanner.index_torrents(directories, quiet=args.quiet)
        if not args.quiet:
            print(f"Processed {results.get('processed', 0)} torrents, {results.get('new', 0)} new")
    except ImportError as e:
        if "redislite" in str(e):
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        else:
            raise


def cmd_match(args: argparse.Namespace) -> None:
    """Find downloaded data for indexed torrents."""
    scanner = _get_scanner(args)
    directories = [Path(d) for d in args.paths]
    
    try:
        matches = scanner.find_matches(directories, quiet=args.quiet)
        if not args.quiet:
            print(f"Found {len(matches)} matches")
        
        if args.output:
            if args.output.endswith('.jsonl'):
                with Path(args.output).open('w', encoding='utf-8') as f:
                    for match in matches:
                        f.write(json.dumps(match, ensure_ascii=False) + '\n')
            else:
                with Path(args.output).open('w', encoding='utf-8') as f:
                    json.dump(matches, f, ensure_ascii=False, indent=2)
            if not args.quiet:
                print(f"Exported matches to {args.output}")
    except ImportError as e:
        if "redislite" in str(e):
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        else:
            raise


def cmd_update(args: argparse.Namespace) -> None:
    """Update database with torrents and matches."""
    scanner = _get_scanner(args)
    directories = [Path(d) for d in args.paths]
    
    try:
        results = scanner.update(directories, quiet=args.quiet)
        if not args.quiet:
            indexed = results.get('indexed', {})
            print(f"Indexed {indexed.get('new', 0)} new torrents")
            print(f"Found {results.get('match_count', 0)} matches")
        
        if args.output:
            matches = results.get('matches', [])
            if args.output.endswith('.jsonl'):
                with Path(args.output).open('w', encoding='utf-8') as f:
                    for match in matches:
                        f.write(json.dumps(match, ensure_ascii=False) + '\n')
            else:
                with Path(args.output).open('w', encoding='utf-8') as f:
                    json.dump(matches, f, ensure_ascii=False, indent=2)
            if not args.quiet:
                print(f"Exported matches to {args.output}")
    except ImportError as e:
        if "redislite" in str(e):
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        else:
            raise


# --- Query Commands ---

def cmd_check(args: argparse.Namespace) -> None:
    """Check if torrent is downloaded."""
    scanner = _get_scanner(args)
    
    if scanner.is_downloaded(args.torrent):
        if args.verbose:
            locations = scanner.get_data_locations(args.torrent)
            print(f"✓ Downloaded at {len(locations)} location(s):")
            for loc in locations:
                print(f"  - {loc}")
        else:
            print("✓ Downloaded")
        sys.exit(0)
    else:
        print("✗ Not downloaded")
        sys.exit(1)


def cmd_locate(args: argparse.Namespace) -> None:
    """Find where torrent data is stored."""
    scanner = _get_scanner(args)
    locations = scanner.get_data_locations(args.torrent)
    
    if not locations:
        print("Not found", file=sys.stderr)
        sys.exit(1)
    
    if args.format == "json":
        print(json.dumps([str(p) for p in locations], indent=2))
    else:
        for loc in locations:
            print(loc)


def cmd_identify(args: argparse.Namespace) -> None:
    """Identify which torrent a file/folder belongs to."""
    scanner = _get_scanner(args)
    
    with database_session(scanner.db_path):
        from .models import get_torrent_for_data_path
        torrent_info = get_torrent_for_data_path(args.path)
    
    if not torrent_info:
        if args.format != "simple":
            print("null")
        else:
            print("No torrent found for this path", file=sys.stderr)
        sys.exit(1)
    
    if args.format == "json":
        print(json.dumps(torrent_info, indent=2))
    else:
        print(f"Info Hash: {torrent_info['info_hash']}")
        print(f"Name: {torrent_info['name']}")
        print(f"Torrent Path: {torrent_info['torrent_path']}")


# --- List Commands ---

def cmd_list(args: argparse.Namespace) -> None:
    """List torrents in database."""
    scanner = _get_scanner(args)
    torrents = scanner.list_torrents(filter_type=args.filter)
    
    if args.format == "table":
        if args.filter == "matched":
            headers = ["Info Hash", "Matches", "Name", "Path"]
            widths = [40, 8, 42, 50]
        else:
            headers = ["Info Hash", "Name", "Path"]
            widths = [40, 50, 50]
        _print_table(torrents, headers, widths)
    elif args.format == "json":
        output = json.dumps(torrents, indent=2)
        _write_output(output, args.output)
    elif args.format == "jsonl":
        output = "\n".join(json.dumps(t) for t in torrents)
        _write_output(output, args.output)
    elif args.format == "info-hash":
        output = "\n".join(t['info_hash'] for t in torrents)
        _write_output(output, args.output)


# --- Database Commands ---

def cmd_stats(args: argparse.Namespace) -> None:
    """Show database statistics."""
    scanner = _get_scanner(args)
    stats = scanner.get_statistics()
    
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(f"Torrent Scanner Database Statistics:")
        print(f"  Database path: {scanner.db_path}")
        print(f"  Total torrents: {stats['total_torrents']}")
        print(f"  Matched torrents: {stats['matched_torrents']}")
        print(f"  Unmatched torrents: {stats['unmatched_torrents']}")
        print(f"  Total matches: {stats['total_matches']}")
        print(f"  Single-file torrents: {stats['single_file_torrents']}")
        print(f"  Multi-file torrents: {stats['multi_file_torrents']}")
        
        # Format size in human-readable format
        size_bytes = stats['total_size_bytes']
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


def cmd_export(args: argparse.Namespace) -> None:
    """Export database contents."""
    scanner = _get_scanner(args)
    
    if args.matches_only:
        data = scanner.export_matches()
    else:
        data = scanner.list_torrents("all")
    
    if args.format == "json":
        content = json.dumps(data, indent=2)
    elif args.format == "jsonl":
        content = "\n".join(json.dumps(item) for item in data)
    elif args.format == "csv":
        import io
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        content = output.getvalue()
    
    with Path(args.output).open('w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Exported {len(data)} items to {args.output}")


def cmd_reset(args: argparse.Namespace) -> None:
    """Reset database."""
    scanner = _get_scanner(args)
    
    if not args.confirm:
        response = input(f"Reset database at {scanner.db_path}? [y/N]: ")
        if response.lower() not in ('y', 'yes'):
            print("Cancelled")
            return
    
    with database_session(scanner.db_path):
        clean_database()
    
    print(f"Database {scanner.db_path} has been reset")
    
    if scanner.redis_path.exists():
        scanner.redis_path.unlink()
        print(f"Redis database {scanner.redis_path} has been deleted")


def build_arg_parser() -> argparse.ArgumentParser:
    """Build improved command line argument parser."""
    p = argparse.ArgumentParser(
        description="Index .torrent files and match with downloaded data.",
        epilog="Use 'torrent_scanner <command> --help' for command-specific help."
    )
    
    # Global options
    p.add_argument("--db", help="Database path (default: ~/.torrent_scanner/torrents.db)")
    p.add_argument("--redis", help="Redis path (default: ~/.torrent_scanner/redis.db)")
    
    sub = p.add_subparsers(dest="cmd", required=True, help="Commands")
    
    # --- Indexing Commands ---
    
    # Index torrents
    p_index = sub.add_parser(
        "index",
        help="Index torrent files into database",
        description="Scan directories for .torrent files and add them to the database."
    )
    p_index.add_argument("paths", nargs="+", help="Paths to scan for .torrent files")
    p_index.add_argument("-q", "--quiet", action="store_true", help="Suppress progress")
    p_index.set_defaults(func=cmd_index)
    
    # Match data
    p_match = sub.add_parser(
        "match",
        help="Find downloaded data for indexed torrents",
        description="Scan directories to find data that matches indexed torrents."
    )
    p_match.add_argument("paths", nargs="+", help="Paths to scan for data")
    p_match.add_argument("-o", "--output", help="Export matches to JSON/JSONL file")
    p_match.add_argument("-q", "--quiet", action="store_true", help="Suppress progress")
    p_match.set_defaults(func=cmd_match)
    
    # Full scan (index + match)
    p_update = sub.add_parser(
        "update",
        help="Update database with torrents and matches",
        description="Perform full scan: index .torrent files and find matching data."
    )
    p_update.add_argument("paths", nargs="+", help="Paths to scan")
    p_update.add_argument("-o", "--output", help="Export matches to JSON/JSONL file")
    p_update.add_argument("-q", "--quiet", action="store_true", help="Suppress progress")
    p_update.set_defaults(func=cmd_update)
    
    # --- Query Commands ---
    
    # Check torrent status
    p_check = sub.add_parser(
        "check",
        help="Check if torrent is downloaded",
        description="Check download status of a torrent by info_hash or .torrent file."
    )
    p_check.add_argument("torrent", help="Info hash (40 hex) or path to .torrent file")
    p_check.add_argument("-v", "--verbose", action="store_true", help="Show details")
    p_check.set_defaults(func=cmd_check)
    
    # Locate data
    p_locate = sub.add_parser(
        "locate",
        help="Find where torrent data is stored",
        description="Get filesystem paths where torrent data is located."
    )
    p_locate.add_argument("torrent", help="Info hash (40 hex) or path to .torrent file")
    p_locate.add_argument("-f", "--format", choices=["lines", "json"], default="lines")
    p_locate.set_defaults(func=cmd_locate)
    
    # Identify data
    p_identify = sub.add_parser(
        "identify",
        help="Identify which torrent a file/folder belongs to",
        description="Find torrent information for a given data path."
    )
    p_identify.add_argument("path", help="Path to data file or directory")
    p_identify.add_argument("-f", "--format", choices=["simple", "json"], default="simple")
    p_identify.set_defaults(func=cmd_identify)
    
    # --- List Commands ---
    
    p_list = sub.add_parser(
        "list",
        help="List torrents in database",
        description="List torrents with various filters."
    )
    p_list.add_argument(
        "--filter",
        choices=["all", "matched", "unmatched"],
        default="all",
        help="Filter torrents to list"
    )
    p_list.add_argument(
        "--format",
        choices=["table", "json", "jsonl", "info-hash"],
        default="table",
        help="Output format"
    )
    p_list.add_argument("-o", "--output", help="Output file (default: stdout)")
    p_list.set_defaults(func=cmd_list)
    
    # --- Database Commands ---
    
    # Statistics
    p_stats = sub.add_parser(
        "stats",
        help="Show database statistics",
        description="Display statistics about indexed torrents and matches."
    )
    p_stats.add_argument("--json", action="store_true", help="Output as JSON")
    p_stats.set_defaults(func=cmd_stats)
    
    # Export
    p_export = sub.add_parser(
        "export",
        help="Export database contents",
        description="Export torrents and matches in various formats."
    )
    p_export.add_argument(
        "--format",
        choices=["json", "jsonl", "csv"],
        default="json",
        help="Export format"
    )
    p_export.add_argument("-o", "--output", required=True, help="Output file")
    p_export.add_argument("--matches-only", action="store_true", help="Export only matched torrents")
    p_export.set_defaults(func=cmd_export)
    
    # Clean
    p_reset = sub.add_parser(
        "reset",
        help="Reset database",
        description="Remove all torrents and matches from database."
    )
    p_reset.add_argument("--confirm", action="store_true", help="Skip confirmation prompt")
    p_reset.set_defaults(func=cmd_reset)
    
    return p


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0