# Torrent Scanner Usage Guide

## Quick Start

Index your torrent files and find matching data in seconds:

```bash
# Install dependencies
pip install -r requirements.txt

# Scan your downloads folder (indexes torrents + finds matches)
torrent_scanner update ~/Downloads

# Check if a specific torrent is downloaded
torrent_scanner check abc123def456789abcdef0123456789abcdef01
```

Or use the Python API:

```python
from torrent_scanner import TorrentScanner

scanner = TorrentScanner()
scanner.update(["/path/to/downloads"])

if scanner.is_downloaded("abc123def456789abcdef0123456789abcdef01"):
    print("Downloaded at:", scanner.get_data_locations("abc123def456789abcdef0123456789abcdef01"))
```

## Installation

### Prerequisites

- Python 3.9 or higher
- pip package manager

### Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `peewee` - SQLite ORM for database operations
- `redislite` - Embedded Redis for fast lookups

Optional:
- `tqdm` - Progress bars (recommended for better CLI experience)

### Running the Tool

As a command-line tool:
```bash
# Direct execution
python torrent_scanner.py <command> [arguments]

# Or if installed as a module
python -m torrent_scanner <command> [arguments]
```

As a Python library:
```python
from torrent_scanner import TorrentScanner
```

## Basic Usage

### Command Line Interface

The CLI provides intuitive commands organized into logical groups:

#### 1. Index Torrent Files

Scan directories for `.torrent` files and add them to the database:

```bash
torrent_scanner index /path/to/torrents
```

**Example with output:**
```bash
$ torrent_scanner index ~/Downloads/torrents ~/backup/old_torrents
Processed 1250 torrents, 47 new
```

**Options:**
- `-q, --quiet` - Suppress progress output

#### 2. Find Matching Data

Search for downloaded data that matches indexed torrents:

```bash
torrent_scanner match /path/to/data
```

**Example with output:**
```bash
$ torrent_scanner match ~/Downloads ~/Media
Found 982 matches

$ torrent_scanner match ~/Downloads -o matches.json
Found 982 matches
Exported matches to matches.json
```

**Options:**
- `-o FILE` - Export matches to JSON/JSONL file
- `-q, --quiet` - Suppress progress output

#### 3. Full Update (Index + Match)

Perform both operations at once (recommended for most use cases):

```bash
torrent_scanner update ~/Downloads
```

**Example with output:**
```bash
$ torrent_scanner update ~/Downloads ~/Media
Indexed 23 new torrents
Found 1005 matches
```

#### 4. Check Download Status

Check if a specific torrent has been downloaded:

```bash
# Using info hash
torrent_scanner check abc123def456789abcdef0123456789abcdef01

# Using .torrent file path
torrent_scanner check /path/to/ubuntu.torrent
```

**Example with output:**
```bash
$ torrent_scanner check 1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b
✓ Downloaded

$ torrent_scanner check 1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b --verbose
✓ Downloaded at 2 location(s):
  - /home/user/Downloads/Ubuntu 20.04
  - /media/backup/Ubuntu 20.04

$ torrent_scanner check ffffffffffffffffffffffffffffffffffffffff
✗ Not downloaded
```

**Exit codes:**
- `0` - Torrent is downloaded
- `1` - Torrent is not downloaded

**Options:**
- `-v, --verbose` - Show data locations

#### 5. Locate Data

Find filesystem paths where torrent data is stored:

```bash
torrent_scanner locate abc123def456789abcdef0123456789abcdef01
```

**Example with output:**
```bash
$ torrent_scanner locate 1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b
/home/user/Downloads/Ubuntu 20.04
/media/backup/Ubuntu 20.04

$ torrent_scanner locate 1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b --format json
[
  "/home/user/Downloads/Ubuntu 20.04",
  "/media/backup/Ubuntu 20.04"
]
```

**Options:**
- `-f, --format` - Output format: `lines` (default) or `json`

#### 6. Identify Torrent from Data

Find which torrent a file or folder belongs to:

```bash
torrent_scanner identify /path/to/data
```

**Example with output:**
```bash
$ torrent_scanner identify ~/Downloads/ubuntu-20.04.3-desktop-amd64.iso
Info Hash: 1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b
Name: Ubuntu 20.04.3 Desktop
Torrent Path: /home/user/torrents/ubuntu.torrent

$ torrent_scanner identify ~/Downloads/ubuntu-20.04.3-desktop-amd64.iso --format json
{
  "info_hash": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b",
  "name": "Ubuntu 20.04.3 Desktop",
  "torrent_path": "/home/user/torrents/ubuntu.torrent",
  "is_multi": false,
  "total_length": 3379068928
}
```

**Options:**
- `-f, --format` - Output format: `simple` (default) or `json`

#### 7. List Torrents

List torrents in the database with optional filtering:

```bash
# List all torrents
torrent_scanner list

# List only downloaded torrents
torrent_scanner list --filter matched

# List torrents not yet downloaded
torrent_scanner list --filter unmatched
```

**Example with output:**
```bash
$ torrent_scanner list --filter matched
Info Hash                                Matches  Name                                      Path
---------------------------------------- -------- ---------------------------------------- --------------------------------------------------
1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b 2        Ubuntu 20.04.3 Desktop                   /home/user/torrents/ubuntu.torrent
2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1 1        Complete Album Collection                /home/user/torrents/music.torrent

$ torrent_scanner list --filter matched --format json -o matched.json
# Outputs to matched.json

$ torrent_scanner list --format info-hash > hashes.txt
# Outputs just info hashes, one per line
```

**Options:**
- `--filter` - Filter type: `all` (default), `matched`, or `unmatched`
- `--format` - Output format: `table` (default), `json`, `jsonl`, or `info-hash`
- `-o FILE` - Output file (default: stdout)

#### 8. Database Statistics

Show statistics about indexed torrents:

```bash
torrent_scanner stats
```

**Example with output:**
```bash
$ torrent_scanner stats
Torrent Scanner Database Statistics:
  Database path: /home/user/.torrent_scanner/torrents.db
  Total torrents: 1250
  Matched torrents: 980
  Unmatched torrents: 270
  Total matches: 1150
  Single-file torrents: 450
  Multi-file torrents: 800
  Total size: 5.1 TB

$ torrent_scanner stats --json
{
  "total_torrents": 1250,
  "matched_torrents": 980,
  "unmatched_torrents": 270,
  "total_matches": 1150,
  "single_file_torrents": 450,
  "multi_file_torrents": 800,
  "total_size_bytes": 5497558138880
}
```

**Options:**
- `--json` - Output as JSON

#### 9. Export Database

Export database contents in various formats:

```bash
# Export all torrents as JSON
torrent_scanner export --format json -o backup.json

# Export only matched torrents as JSONL
torrent_scanner export --format jsonl -o matched.jsonl --matches-only

# Export as CSV
torrent_scanner export --format csv -o torrents.csv
```

**Options:**
- `--format` - Export format: `json` (default), `jsonl`, or `csv`
- `-o FILE` - Output file (required)
- `--matches-only` - Export only torrents with matches

#### 10. Reset Database

Remove all data from the database:

```bash
# With confirmation prompt
torrent_scanner reset

# Skip confirmation
torrent_scanner reset --confirm
```

**Example with output:**
```bash
$ torrent_scanner reset
Reset database at /home/user/.torrent_scanner/torrents.db? [y/N]: y
Database /home/user/.torrent_scanner/torrents.db has been reset
Redis database /home/user/.torrent_scanner/redis.db has been deleted
```

### Global Options

All commands support these global options:

```bash
# Use custom database path
torrent_scanner --db /custom/path/db.sqlite stats

# Use custom Redis path
torrent_scanner --redis /custom/path/redis.db stats

# Use both custom paths
torrent_scanner --db /custom/db.sqlite --redis /custom/redis.db update ~/Downloads
```

**Default paths:**
- Database: `~/.torrent_scanner/torrents.db`
- Redis: `~/.torrent_scanner/redis.db`

### Python API

#### Initialize Scanner

```python
from torrent_scanner import TorrentScanner

# Use default paths
scanner = TorrentScanner()

# Use custom paths
scanner = TorrentScanner(
    db_path="/custom/path/db.sqlite",
    redis_path="/custom/path/redis.db"
)
```

#### Index Torrents

```python
from pathlib import Path

# Index torrents from directories
result = scanner.index_torrents([
    Path("/home/user/Downloads/torrents"),
    Path("/home/user/backup/torrents")
])

print(f"Processed: {result['processed']}")
print(f"New: {result['new']}")
```

**Output:**
```python
{'processed': 1250, 'new': 47}
```

#### Find Matches

```python
# Find matching data
matches = scanner.find_matches([
    Path("/home/user/Downloads"),
    Path("/media/drive1")
])

print(f"Found {len(matches)} matches")
for match in matches[:3]:  # Print first 3
    print(f"  {match['name']} -> {match['matches'][0]}")
```

**Output:**
```python
[
    {
        'info_hash': '1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b',
        'name': 'Ubuntu 20.04.3 Desktop',
        'torrent_path': '/home/user/torrents/ubuntu.torrent',
        'matches': ['/home/user/Downloads/Ubuntu 20.04.3 Desktop'],
        'is_multi': False,
        'total_length': 3379068928
    },
    # ... more matches
]
```

#### Full Update

```python
# Do both index and match in one call
result = scanner.update([Path("/home/user/Downloads")])

print(f"Indexed: {result['indexed']['new']} new")
print(f"Matches: {result['match_count']}")
```

**Output:**
```python
{
    'indexed': {'processed': 1250, 'new': 23},
    'matches': [...],
    'match_count': 1005
}
```

#### Check if Downloaded

```python
info_hash = "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"

if scanner.is_downloaded(info_hash):
    print("Downloaded!")
else:
    print("Not downloaded")
```

**Output:** `True` or `False`

#### Get Data Locations

```python
locations = scanner.get_data_locations(info_hash)
for loc in locations:
    print(f"Found at: {loc}")
```

**Output:**
```python
[
    Path('/home/user/Downloads/Ubuntu 20.04.3 Desktop'),
    Path('/media/backup/Ubuntu 20.04.3 Desktop')
]
```

#### Get Torrent Info

```python
# By info hash
info = scanner.get_torrent_info("1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b")

# By .torrent file path
info = scanner.get_torrent_info("/path/to/ubuntu.torrent")

if info:
    print(f"Name: {info['name']}")
    print(f"Size: {info['total_length']} bytes")
    print(f"Matches: {len(info['matches'])}")
```

**Output:**
```python
{
    'info_hash': '1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b',
    'name': 'Ubuntu 20.04.3 Desktop',
    'total_length': 3379068928,
    'is_multi': False,
    'torrent_path': '/home/user/torrents/ubuntu.torrent',
    'matches': ['/home/user/Downloads/Ubuntu 20.04.3 Desktop'],
    'created_unix': 1700000000,
    'created_by': 'mktorrent 1.1',
    'comment': 'Ubuntu 20.04.3 LTS Desktop'
}
```

#### List Torrents

```python
# Get all torrents
all_torrents = scanner.list_torrents("all")

# Get only downloaded torrents
matched = scanner.list_torrents("matched")

# Get only torrents not yet downloaded
unmatched = scanner.list_torrents("unmatched")

for torrent in matched[:3]:
    print(f"{torrent['name']}: {torrent['match_count']} locations")
```

**Output:**
```python
[
    {
        'info_hash': '1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b',
        'name': 'Ubuntu 20.04.3 Desktop',
        'torrent_path': '/home/user/torrents/ubuntu.torrent',
        'is_multi': False,
        'total_length': 3379068928,
        'match_count': 2
    },
    # ... more torrents
]
```

#### Get Statistics

```python
stats = scanner.get_statistics()

print(f"Total torrents: {stats['total_torrents']}")
print(f"Downloaded: {stats['matched_torrents']}")
print(f"Total size: {stats['total_size_bytes'] / (1024**3):.1f} GB")
```

**Output:**
```python
{
    'total_torrents': 1250,
    'matched_torrents': 980,
    'unmatched_torrents': 270,
    'total_matches': 1150,
    'single_file_torrents': 450,
    'multi_file_torrents': 800,
    'total_size_bytes': 5497558138880
}
```

#### Export Matches

```python
import json

matches = scanner.export_matches()

# Save to file
with open('matches.json', 'w') as f:
    json.dump(matches, f, indent=2)
```

**Output:** Same format as `find_matches()` result

## API Reference

### TorrentScanner Class

```python
class TorrentScanner:
    def __init__(self, db_path=None, redis_path=None):
        """
        Initialize the torrent scanner.

        Args:
            db_path (Path, optional): Custom database path.
                                     Default: ~/.torrent_scanner/torrents.db
            redis_path (Path, optional): Custom Redis path.
                                        Default: ~/.torrent_scanner/redis.db
        """
```

#### Methods

##### index_torrents

```python
def index_torrents(self, directories, quiet=True):
    """
    Index .torrent files from specified directories.

    Args:
        directories (List[Path]): Directories to scan for .torrent files
        quiet (bool): Suppress progress output

    Returns:
        dict: {'processed': int, 'new': int}
    """
```

##### find_matches

```python
def find_matches(self, directories, quiet=True):
    """
    Find downloaded data matching indexed torrents.

    Args:
        directories (List[Path]): Directories to scan for data
        quiet (bool): Suppress progress output

    Returns:
        List[dict]: List of match dictionaries with torrent metadata
    """
```

##### update

```python
def update(self, directories, quiet=True):
    """
    Perform full scan: index torrents + find matches.

    Args:
        directories (List[Path]): Directories to scan
        quiet (bool): Suppress progress output

    Returns:
        dict: {
            'indexed': {'processed': int, 'new': int},
            'matches': List[dict],
            'match_count': int
        }
    """
```

##### is_downloaded

```python
def is_downloaded(self, info_hash):
    """
    Check if a torrent has any data matches.

    Args:
        info_hash (str): 40-character hex info hash or path to .torrent file

    Returns:
        bool: True if torrent has matches, False otherwise
    """
```

##### get_data_locations

```python
def get_data_locations(self, info_hash):
    """
    Get filesystem paths where torrent data is located.

    Args:
        info_hash (str): 40-character hex info hash or path to .torrent file

    Returns:
        List[Path]: List of paths where data was found
    """
```

##### get_torrent_info

```python
def get_torrent_info(self, identifier):
    """
    Get torrent info by info_hash or .torrent file path.

    Args:
        identifier (str): Info hash or .torrent file path

    Returns:
        dict or None: Torrent metadata dictionary or None if not found
            {
                'info_hash': str,
                'name': str,
                'total_length': int,
                'is_multi': bool,
                'torrent_path': str,
                'matches': List[str],
                'created_unix': int or None,
                'created_by': str or None,
                'comment': str or None
            }
    """
```

##### list_torrents

```python
def list_torrents(self, filter_type="all"):
    """
    List torrents with optional filtering.

    Args:
        filter_type (str): Filter type - "all", "matched", or "unmatched"

    Returns:
        List[dict]: List of torrent dictionaries
    """
```

##### get_statistics

```python
def get_statistics(self):
    """
    Get database statistics.

    Returns:
        dict: {
            'total_torrents': int,
            'matched_torrents': int,
            'unmatched_torrents': int,
            'total_matches': int,
            'single_file_torrents': int,
            'multi_file_torrents': int,
            'total_size_bytes': int
        }
    """
```

##### export_matches

```python
def export_matches(self):
    """
    Export all matched torrents with their data paths.

    Returns:
        List[dict]: List of match dictionaries
    """
```

### Convenience Functions

For one-off operations without creating a TorrentScanner instance:

```python
from torrent_scanner import quick_check, quick_locate, quick_identify
```

##### quick_check

```python
def quick_check(info_hash, db_path=None):
    """
    Quick check if torrent is downloaded.

    Args:
        info_hash (str): 40-character hex info hash
        db_path (Path, optional): Custom database path

    Returns:
        bool: True if downloaded, False otherwise
    """
```

**Example:**
```python
from torrent_scanner import quick_check

if quick_check("1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"):
    print("Downloaded!")
```

##### quick_locate

```python
def quick_locate(info_hash, db_path=None):
    """
    Quick lookup of torrent data locations.

    Args:
        info_hash (str): 40-character hex info hash
        db_path (Path, optional): Custom database path

    Returns:
        List[Path]: List of paths where data was found
    """
```

**Example:**
```python
from torrent_scanner import quick_locate

locations = quick_locate("1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b")
print(f"Found at: {locations}")
```

##### quick_identify

```python
def quick_identify(data_path, db_path=None):
    """
    Quick identification of torrent for a data path.

    Args:
        data_path (Path): Path to data file or directory
        db_path (Path, optional): Custom database path

    Returns:
        dict or None: Torrent info dictionary or None if not found
    """
```

**Example:**
```python
from torrent_scanner import quick_identify
from pathlib import Path

info = quick_identify(Path("/home/user/Downloads/ubuntu.iso"))
if info:
    print(f"This is: {info['name']}")
```

## Configuration

### Database Paths

By default, torrent_scanner stores data in `~/.torrent_scanner/`:

- **SQLite database**: `~/.torrent_scanner/torrents.db`
- **Redis database**: `~/.torrent_scanner/redis.db`

#### Custom Paths (CLI)

```bash
torrent_scanner --db /custom/path/db.sqlite --redis /custom/redis.db stats
```

#### Custom Paths (Python API)

```python
from pathlib import Path
from torrent_scanner import TorrentScanner

scanner = TorrentScanner(
    db_path=Path("/custom/path/db.sqlite"),
    redis_path=Path("/custom/redis.db")
)
```

### Database Schema

The scanner uses three main tables:

#### Torrent Table
- `info_hash` - 40-character SHA-1 hash (unique)
- `torrent_path` - Path to .torrent file (unique)
- `name` - Torrent name
- `name_hash` - SHA-256 hash of name (for fast matching)
- `structure_hash` - SHA-256 hash of file structure (multi-file only)
- `is_multi` - Boolean: multi-file or single-file torrent
- `total_length` - Total size in bytes
- `created_unix` - Creation timestamp (optional)
- `created_by` - Creator string (optional)
- `comment` - Comment field (optional)
- `added_ts` - When torrent was added to database

#### TorrentFile Table
- `torrent` - Foreign key to Torrent
- `file_index` - Index of file within torrent
- `path` - Relative path within torrent
- `length` - File size in bytes
- `file_hash` - SHA-256 hash for file-based matching

#### Match Table
- `torrent` - Foreign key to Torrent
- `data_path` - Absolute path to matched data
- `first_seen_ts` - When match was first found

### Redis Indexes

Redis is used for fast lookups:

- `name:<name_hash>` → Set of info hashes with this name
- `file:<file_hash>` → Set of info hashes containing this file
- Metadata cache for validation

## Common Patterns

### Initial Setup

When setting up torrent_scanner for the first time:

```bash
# 1. Index your torrent collection
torrent_scanner index ~/Downloads/torrents ~/backup/torrents

# 2. Find matching data
torrent_scanner match ~/Downloads ~/Media /external/drive1

# 3. Check statistics
torrent_scanner stats

# 4. Export for backup
torrent_scanner export --format json -o torrent_backup.json
```

### Regular Maintenance

Set up a cron job or systemd timer for regular updates:

```bash
# Daily at 2 AM: index new torrents and find new matches
0 2 * * * /usr/bin/python3 -m torrent_scanner update ~/Downloads --quiet
```

### Scripting with Exit Codes

Use `check` command in shell scripts:

```bash
#!/bin/bash
INFO_HASH="1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"

if torrent_scanner check "$INFO_HASH" --quiet; then
    echo "Already downloaded, skipping"
else
    echo "Need to download"
    # Start download...
fi
```

### Batch Processing

Process multiple torrents:

```bash
# Export unmatched torrent hashes
torrent_scanner list --filter unmatched --format info-hash > to_download.txt

# Process each one
while read hash; do
    echo "Processing $hash"
    # Do something with the hash
done < to_download.txt
```

### Integration with Other Tools

```python
from torrent_scanner import TorrentScanner
import subprocess

scanner = TorrentScanner()

# Find torrents that aren't downloaded
unmatched = scanner.list_torrents("unmatched")

for torrent in unmatched:
    info_hash = torrent['info_hash']
    torrent_path = torrent['torrent_path']

    # Add to download client
    subprocess.run(['transmission-remote', '-a', torrent_path])
```

### Deduplication

Find duplicate data (same torrent in multiple locations):

```python
scanner = TorrentScanner()
matched = scanner.list_torrents("matched")

for torrent in matched:
    if torrent['match_count'] > 1:
        info_hash = torrent['info_hash']
        locations = scanner.get_data_locations(info_hash)
        print(f"{torrent['name']} found at {len(locations)} locations:")
        for loc in locations:
            print(f"  - {loc}")
```

### Migration Between Systems

Export from one system:

```bash
# System A: Export database
torrent_scanner export --format jsonl -o torrents.jsonl
```

Import to another system:

```python
# System B: Import (you'll need to write custom import logic)
# The exported data contains all metadata needed to rebuild
import json

with open('torrents.jsonl') as f:
    for line in f:
        torrent = json.loads(line)
        # Process torrent data...
```

## Examples

### Example 1: Find Large Undownloaded Torrents

```python
from torrent_scanner import TorrentScanner

scanner = TorrentScanner()
unmatched = scanner.list_torrents("unmatched")

# Find torrents larger than 10GB
large_torrents = [
    t for t in unmatched
    if t['total_length'] > 10 * 1024**3
]

# Sort by size
large_torrents.sort(key=lambda t: t['total_length'], reverse=True)

print("Large undownloaded torrents:")
for t in large_torrents[:10]:
    size_gb = t['total_length'] / (1024**3)
    print(f"  {t['name']}: {size_gb:.1f} GB")
```

**Output:**
```
Large undownloaded torrents:
  Complete Movie Collection: 145.2 GB
  Linux ISO Collection: 87.3 GB
  Software Archive: 52.1 GB
  Music Library: 23.4 GB
  Document Archive: 15.7 GB
```

### Example 2: Monitor Download Progress

```python
from torrent_scanner import TorrentScanner
import time

scanner = TorrentScanner()

# Get initial stats
initial_stats = scanner.get_statistics()
print(f"Starting with {initial_stats['matched_torrents']} downloaded")

# Periodic check
while True:
    time.sleep(3600)  # Check every hour

    # Update database
    scanner.update(["/home/user/Downloads"], quiet=True)

    # Get new stats
    stats = scanner.get_statistics()
    new_downloads = stats['matched_torrents'] - initial_stats['matched_torrents']

    if new_downloads > 0:
        print(f"Found {new_downloads} new downloads!")
        initial_stats = stats
```

### Example 3: Generate Download Report

```python
from torrent_scanner import TorrentScanner
from datetime import datetime

scanner = TorrentScanner()
stats = scanner.get_statistics()

print("=" * 60)
print("TORRENT COLLECTION REPORT")
print("=" * 60)
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()
print(f"Total torrents indexed: {stats['total_torrents']}")
print(f"  Downloaded: {stats['matched_torrents']} ({stats['matched_torrents']/stats['total_torrents']*100:.1f}%)")
print(f"  Not downloaded: {stats['unmatched_torrents']} ({stats['unmatched_torrents']/stats['total_torrents']*100:.1f}%)")
print()
print(f"Total data size: {stats['total_size_bytes'] / (1024**4):.2f} TB")
print(f"  Single-file torrents: {stats['single_file_torrents']}")
print(f"  Multi-file torrents: {stats['multi_file_torrents']}")
print()
print(f"Total matches: {stats['total_matches']}")
print()

# Top 10 by size
all_torrents = scanner.list_torrents("all")
all_torrents.sort(key=lambda t: t['total_length'], reverse=True)

print("Largest torrents:")
for t in all_torrents[:10]:
    size_gb = t['total_length'] / (1024**3)
    status = "✓" if t['match_count'] > 0 else "✗"
    print(f"  {status} {t['name'][:50]:50} {size_gb:8.1f} GB")
```

**Output:**
```
============================================================
TORRENT COLLECTION REPORT
============================================================
Generated: 2024-01-15 14:30:22

Total torrents indexed: 1250
  Downloaded: 980 (78.4%)
  Not downloaded: 270 (21.6%)

Total data size: 5.07 TB
  Single-file torrents: 450
  Multi-file torrents: 800

Total matches: 1150

Largest torrents:
  ✓ Complete Movie Collection 4K                     145.2 GB
  ✗ Linux ISO Collection                              87.3 GB
  ✓ Music Archive 1990-2020                           52.1 GB
  ✓ Document Collection                               23.4 GB
  ✓ Ubuntu 20.04.3 Desktop                             3.1 GB
  ✗ Software Development Tools                        45.8 GB
  ✓ Video Tutorial Series                             12.3 GB
  ✓ Game Assets Collection                             8.9 GB
  ✗ Archive.org Mirror                                67.2 GB
  ✓ Scientific Papers 2020                             4.5 GB
```

### Example 4: Web Dashboard Data

```python
from torrent_scanner import TorrentScanner
import json

scanner = TorrentScanner()

# Prepare data for web dashboard
dashboard_data = {
    'stats': scanner.get_statistics(),
    'recent_matches': scanner.list_torrents("matched")[:20],
    'to_download': scanner.list_torrents("unmatched")[:20],
}

# Save as JSON for web app
with open('/var/www/dashboard/data.json', 'w') as f:
    json.dump(dashboard_data, f, indent=2)
```

### Example 5: Cleanup Duplicates

Find and optionally remove duplicate data:

```python
from torrent_scanner import TorrentScanner
from pathlib import Path
import shutil

scanner = TorrentScanner()
matched = scanner.list_torrents("matched")

duplicates = [t for t in matched if t['match_count'] > 1]

print(f"Found {len(duplicates)} torrents with duplicates")

for torrent in duplicates:
    info_hash = torrent['info_hash']
    locations = scanner.get_data_locations(info_hash)

    print(f"\n{torrent['name']}:")
    print(f"  Found at {len(locations)} locations:")

    for i, loc in enumerate(locations):
        size_on_disk = sum(
            f.stat().st_size
            for f in Path(loc).rglob('*')
            if f.is_file()
        )
        print(f"  [{i}] {loc}")
        print(f"      Size: {size_on_disk / (1024**3):.2f} GB")

    # Optionally remove duplicates (commented out for safety)
    # keep_index = 0  # Keep first location
    # for i, loc in enumerate(locations):
    #     if i != keep_index:
    #         print(f"  Removing: {loc}")
    #         shutil.rmtree(loc)
```

## Troubleshooting

### Common Errors

#### Error: `redislite` module not found

**Cause:** Missing dependency

**Solution:**
```bash
pip install redislite
```

#### Error: Database is locked

**Cause:** Another process is using the database

**Solution:**
```bash
# Check for other running processes
ps aux | grep torrent_scanner

# If none found, the lock might be stale
rm ~/.torrent_scanner/torrents.db-wal
rm ~/.torrent_scanner/torrents.db-shm
```

#### Error: Permission denied when scanning directory

**Cause:** Insufficient permissions to read directory

**Solution:**
```bash
# Run with appropriate permissions
sudo torrent_scanner index /root/torrents

# Or fix permissions
sudo chmod -R +r /path/to/torrents
```

#### No matches found but data exists

**Cause:** Data directory name doesn't match torrent name exactly

**Solution:** The scanner matches by:
1. Name matching (directory name matches torrent name)
2. Structure matching (for multi-file torrents)
3. File-based matching (individual file hashes)

Try:
```bash
# Re-index and re-match
torrent_scanner update ~/Downloads --quiet

# Check torrent name
torrent_scanner list --filter all | grep -i "expected name"
```

#### Info hash not accepted

**Cause:** Info hash must be exactly 40 hexadecimal characters

**Solution:**
```bash
# Valid format (40 hex chars)
torrent_scanner check 1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b

# Invalid formats
torrent_scanner check 1a2b3c4d  # Too short
torrent_scanner check 1A2B3C4D5E6F7A8B9C0D1E2F3A4B5C6D7E8F9A0B  # Use lowercase
```

### Performance Issues

#### Slow indexing

**Cause:** Large number of .torrent files

**Solution:**
- Use `--quiet` flag to disable progress output
- Consider splitting into multiple smaller scans
- Index files are cached in Redis for faster subsequent scans

#### Slow matching

**Cause:** Large directory trees to scan

**Solution:**
- Scan specific subdirectories instead of entire drives
- Exclude system directories
- Use SSD for database storage

```bash
# Instead of scanning entire home directory
torrent_scanner match ~

# Scan specific download folders
torrent_scanner match ~/Downloads ~/Media
```

#### High memory usage

**Cause:** Redis cache in memory

**Solution:** Redis database is file-based and memory-mapped. Memory usage should be moderate. If issues persist:

```bash
# Reset Redis database
rm ~/.torrent_scanner/redis.db

# Re-index
torrent_scanner update ~/Downloads
```

### Debugging

Enable verbose output:

```python
from torrent_scanner import TorrentScanner

scanner = TorrentScanner()

# Set quiet=False for detailed output
scanner.index_torrents(["/path/to/torrents"], quiet=False)
scanner.find_matches(["/path/to/data"], quiet=False)
```

Check database directly:

```bash
sqlite3 ~/.torrent_scanner/torrents.db

# Show tables
.tables

# Count torrents
SELECT COUNT(*) FROM torrent;

# Show recent torrents
SELECT name, info_hash FROM torrent ORDER BY added_ts DESC LIMIT 10;

# Show matches
SELECT t.name, m.data_path FROM torrent t JOIN match m ON t.id = m.torrent_id;

# Exit
.quit
```

### FAQ

**Q: Can I use this with multiple torrent clients?**

A: Yes! torrent_scanner works with `.torrent` files from any client (qBittorrent, Transmission, Deluge, etc.). Just point it at your torrent directories.

**Q: Does it modify my torrent files or data?**

A: No. torrent_scanner is read-only. It never modifies torrent files or downloaded data.

**Q: How accurate is the matching?**

A: Very accurate. Matching uses:
- SHA-1 info hashes (per BEP-3 specification)
- SHA-256 name hashes
- SHA-256 structure hashes for multi-file torrents
- Individual file hashes for merged directories

**Q: Can it handle merged torrent folders?**

A: Yes! If multiple torrents with the same name are merged into one directory, file-based matching will detect all of them.

**Q: What about symbolic links?**

A: The scanner skips symbolic links by default for safety and to avoid infinite loops.

**Q: Can I run multiple instances?**

A: Yes, but they should use different database paths to avoid locking issues:

```python
scanner1 = TorrentScanner(db_path="/tmp/db1.sqlite")
scanner2 = TorrentScanner(db_path="/tmp/db2.sqlite")
```

**Q: How do I backup my database?**

A: Simply copy the database files:

```bash
cp ~/.torrent_scanner/torrents.db ~/backups/
cp ~/.torrent_scanner/redis.db ~/backups/
```

Or export as JSON:
```bash
torrent_scanner export --format json -o backup.json
```

**Q: Does it support magnet links?**

A: No. torrent_scanner requires actual `.torrent` files to extract the info hash and metadata. Magnet links don't contain enough information.

**Q: Can I use it on Windows?**

A: Yes! The code is cross-platform. Paths will use Windows format automatically:

```bash
torrent_scanner index "C:\Users\YourName\Downloads\torrents"
```

**Q: How do I clear the database and start over?**

A: Use the reset command:

```bash
torrent_scanner reset --confirm