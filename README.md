# torrent_scanner

A fast, local utility to index .torrent files and match them against on-disk folders/files. It provides both a high-level API for library use and a comprehensive command-line interface.

## Features

- **High-level Python API** - Clean TorrentScanner class for library integration
- **Improved CLI** - Intuitive commands with consistent naming and clear help
- **Fast torrent parsing** - Precise info dictionary hashing (SHA-1) per BEP-3
- **SQLite database** - Persistent storage with Peewee ORM
- **Redis indexing** - Fast lookups using embedded Redis (redislite)
- **Intelligent matching** - Multi-file and single-file torrent detection
- **Safe scanning** - Skips symlinks, handles permission errors gracefully
- **Multiple export formats** - JSON, JSONL, CSV output options

## Installation

```bash
pip install -r requirements.txt
```

## Requirements

- Python 3.9+
- Dependencies: `peewee` (SQLite ORM), `redislite` (embedded Redis)

## Quick Start

### Library Usage

```python
from torrent_scanner import TorrentScanner

# Initialize scanner
scanner = TorrentScanner()

# Index torrent files
scanner.index_torrents(["/path/to/torrents"])

# Find matching data
matches = scanner.find_matches(["/path/to/data"])

# Check if a specific torrent is downloaded
if scanner.is_downloaded("abc123def456"):
    locations = scanner.get_data_locations("abc123def456")
    print(f"Found at: {locations}")

# One-liner convenience functions
from torrent_scanner import quick_check, quick_locate

if quick_check("abc123def456"):
    print("Downloaded at:", quick_locate("abc123def456"))
```

### Command Line Usage

```bash
# Index torrent files
torrent_scanner index /path/to/torrents

# Find matching data
torrent_scanner match /path/to/data

# Full scan (index + match)
torrent_scanner update /path/to/downloads

# Check if torrent is downloaded
torrent_scanner check abc123def456

# Find where torrent data is stored
torrent_scanner locate abc123def456

# Show database statistics
torrent_scanner stats

# List torrents
torrent_scanner list --filter matched
```

## API Reference

### TorrentScanner Class

The main API class for torrent scanning operations.

```python
from torrent_scanner import TorrentScanner

scanner = TorrentScanner(
    db_path=None,    # Optional: Custom database path
    redis_path=None  # Optional: Custom Redis path
)
```

#### Methods

**`index_torrents(directories, quiet=True)`**
- Index .torrent files from specified directories
- Returns: `{'processed': int, 'new': int}`

**`find_matches(directories, quiet=True)`**
- Find downloaded data matching indexed torrents
- Returns: List of match dictionaries

**`update(directories, quiet=True)`**
- Perform full scan: index torrents + find matches
- Returns: `{'indexed': {...}, 'matches': [...], 'match_count': int}`

**`is_downloaded(info_hash)`**
- Check if a torrent has any data matches
- Returns: `bool`

**`get_data_locations(info_hash)`**
- Get filesystem paths where torrent data is located
- Returns: `List[Path]`

**`get_torrent_info(identifier)`**
- Get torrent info by info_hash or .torrent file path
- Returns: `Dict` with torrent metadata or `None`

**`list_torrents(filter_type="all")`**
- List torrents with optional filtering ("all", "matched", "unmatched")
- Returns: `List[Dict]`

**`get_statistics()`**
- Get database statistics
- Returns: `Dict` with counts and totals

### Convenience Functions

**`quick_check(info_hash, db_path=None)`**
- Quick check if torrent is downloaded
- Returns: `bool`

**`quick_locate(info_hash, db_path=None)`**
- Quick lookup of torrent data locations  
- Returns: `List[Path]`

**`quick_identify(data_path, db_path=None)`**
- Quick identification of torrent for a data path
- Returns: `Dict` with torrent info or `None`

## CLI Reference

The improved CLI provides clear, consistent commands organized into logical groups:

### Indexing Commands

**`index PATHS...`** - Index torrent files into database
```bash
torrent_scanner index /torrents /more_torrents
torrent_scanner index /torrents --quiet
```

**`match PATHS...`** - Find downloaded data for indexed torrents
```bash
torrent_scanner match /downloads /data
torrent_scanner match /downloads -o matches.jsonl
```

**`update PATHS...`** - Update database (index + match)
```bash
torrent_scanner update /downloads
torrent_scanner update /downloads -o matches.json --quiet
```

### Query Commands

**`check TORRENT`** - Check if torrent is downloaded
```bash
torrent_scanner check abc123def456789...  # Returns exit code 0/1
torrent_scanner check /path/to/file.torrent --verbose
```

**`locate TORRENT`** - Find where torrent data is stored
```bash
torrent_scanner locate abc123def456789...
torrent_scanner locate /path/to/file.torrent --format json
```

**`identify PATH`** - Identify which torrent a file/folder belongs to
```bash
torrent_scanner identify /data/ubuntu-20.04
torrent_scanner identify /data/movie.mkv --format json
```

### List Commands

**`list`** - List torrents in database
```bash
torrent_scanner list                           # All torrents
torrent_scanner list --filter matched         # Only matched
torrent_scanner list --filter unmatched       # Only unmatched
torrent_scanner list --format json -o out.json
```

### Database Commands

**`stats`** - Show database statistics
```bash
torrent_scanner stats
torrent_scanner stats --json
```

**`export`** - Export database contents
```bash
torrent_scanner export --format json -o export.json
torrent_scanner export --format csv -o export.csv --matches-only
```

**`reset`** - Reset database
```bash
torrent_scanner reset --confirm
```

### Global Options

All commands support these global options:
- `--db PATH` - Database path (default: `~/.torrent_scanner/torrents.db`)
- `--redis PATH` - Redis path (default: `~/.torrent_scanner/redis.db`)

## How It Works

The scanner operates in three phases:

1. **Torrent Parsing**: Decodes bencode files while tracking the byte span of the `info` dictionary to compute canonical SHA-1 info hashes. Extracts torrent name, file lists, total length, and optional metadata.

2. **Database Storage**: Uses Peewee ORM to manage `Torrent`, `TorrentFile`, and `Match` models in SQLite. Defaults to `~/.torrent_scanner/torrents.db`.

3. **Fast Matching**: Maintains Redis lookup sets for quick matching:
   - `name:<name_hash> -> {info_hash}`
   - `file:<file_hash> -> {info_hash}` (for file-based matching)
   - Metadata cache for quick validation

## Output Format

### JSONL Export Format

Each line is a JSON object with core torrent fields and matched paths:

```json
{
  "info_hash": "abc123def456...",
  "torrent_path": "/path/to/file.torrent",
  "name": "Ubuntu 20.04 LTS",
  "name_hash": "def456abc123...",
  "structure_hash": "789abc123def...",
  "is_multi": true,
  "total_length": 2147483648,
  "created_unix": 1700000000,
  "created_by": "mktorrent 1.1",
  "comment": "Ubuntu 20.04 LTS Desktop",
  "matches": ["/data/ubuntu", "/backup/ubuntu"],
  "first_seen_ts": 1700000001
}
```

### API Response Format

API methods return structured dictionaries:

```python
# get_torrent_info() response
{
    'info_hash': 'abc123def456...',
    'name': 'Ubuntu 20.04 LTS',
    'total_length': 2147483648,
    'is_multi': True,
    'torrent_path': '/path/to/ubuntu.torrent',
    'matches': ['/data/ubuntu'],
    'created_unix': 1700000000,
    'created_by': 'mktorrent 1.1',
    'comment': 'Ubuntu 20.04 LTS Desktop'
}

# get_statistics() response
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

## Project Structure

```
./
├─ torrent_scanner.py            # Entry script
├─ torrent_scanner/
│  ├─ __init__.py                # Package exports + version
│  ├─ api.py                     # High-level TorrentScanner API
│  ├─ cli.py                     # Improved CLI commands
│  ├─ scanner.py                 # Core scanning logic
│  ├─ torrent.py                 # Torrent parsing
│  ├─ bencode.py                 # Bencode decoder
│  ├─ filesystem.py              # File system utilities
│  └─ models.py                  # Database models
├─ tests/                        # Test suite
│  ├─ test_new_api.py           # API and CLI tests
│  └─ ...
├─ requirements.txt
├─ requirements-test.txt
└─ pytest.ini
```

## Development

Run tests:
```bash
./run_tests.py
```

Run specific test file:
```bash
python -m pytest tests/test_new_api.py -v
```

