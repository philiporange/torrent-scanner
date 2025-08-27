# torrent_scanner

A fast, local utility to index .torrent files and match them against on-disk folders/files. It parses torrent metadata (BEP-3), stores it in a SQLite database via Peewee, builds lightweight indexes in an embedded Redis (via redislite), and scans directories to find data that corresponds to known torrents.

## Installation

```bash
pip install -r requirements.txt
```

## Features

- Parse .torrent files with precise info dictionary hashing (SHA-1)
- Store metadata in SQLite database with Peewee ORM
- Fast lookups using embedded Redis (redislite) for name/structure matching
- Multi-file matching via structure hash of relative paths and sizes
- Single-file matching via filename hash and exact file size
- CLI tools to scan directories and export matches as JSONL
- Safe scanning that skips symlinks and tolerates permission errors

## How It Works

The scanner operates in three phases:

1. **Torrent Parsing**: Decodes bencode files while tracking the byte span of the `info` dictionary to compute canonical SHA-1 info hashes. Extracts torrent name, file lists, total length, and optional metadata.

2. **Database Storage**: Uses Peewee ORM to manage `Torrent`, `TorrentFile`, and `Match` models in SQLite. Defaults to `~/.torrent_scanner/torrents.db`.

3. **Fast Matching**: Maintains Redis lookup sets for quick matching:
   - `name:<name_hash> -> {info_hash}`
   - `structure:<structure_hash> -> {info_hash}` (multi-file torrents)
   - `single:<name_hash>:<size> -> {info_hash}` (single-file torrents)

## Requirements

- Python 3.9+
- Dependencies: `peewee` (SQLite ORM), `redislite` (embedded Redis)

## Quick Start

**Scan directories for torrents and matches:**

```bash
python torrent_scanner.py scan /path/to/downloads
```

**Scan only for .torrent files (no data matching):**

```bash
python torrent_scanner.py torrents /path/to/downloads
```

**Scan only for data files that match existing torrents:**

```bash
python torrent_scanner.py files /path/to/downloads
```

**View database statistics:**

```bash
python torrent_scanner.py info
```

**Export matches to JSONL:**

```bash
python torrent_scanner.py scan /path/to/downloads --matches-jsonl matches.jsonl
```

**List all existing matches:**

```bash
python torrent_scanner.py list-matches
```

The scanner recursively finds `*.torrent` files and attempts to match them against data in the same directories. Database files are automatically created in `~/.torrent_scanner/` if not specified.

## CLI Reference

**scan** - Scan directories for torrents and matches
- `directories...` - One or more directories to recursively scan
- `--db <path>` - SQLite database path (default: `~/.torrent_scanner/torrents.db`)
- `--redis <path>` - Redis database path (default: `~/.torrent_scanner/redis.db`)
- `--matches-jsonl <path>` - Export matched torrents to JSONL file
- `-q, --quiet` - Suppress progress output

**torrents** - Scan directories for .torrent files only (no data matching)
- `directories...` - One or more directories to recursively scan for .torrent files
- `--db <path>` - SQLite database path (default: `~/.torrent_scanner/torrents.db`)
- `--redis <path>` - Redis database path (default: `~/.torrent_scanner/redis.db`)
- `-q, --quiet` - Suppress progress output

**files** - Scan directories for data files that match existing torrents
- `directories...` - One or more directories to recursively scan for data files
- `--db <path>` - SQLite database path (default: `~/.torrent_scanner/torrents.db`)
- `--redis <path>` - Redis database path (default: `~/.torrent_scanner/redis.db`)
- `--matches-jsonl <path>` - Export matched torrents to JSONL file
- `-q, --quiet` - Suppress progress output

**info** - Show database statistics and information
- `--db <path>` - SQLite database path (default: `~/.torrent_scanner/torrents.db`)
- `--json` - Output information as JSON

**list-matches** - List existing matches
- `--db <path>` - SQLite database path (default: `~/.torrent_scanner/torrents.db`)
- `--jsonl <path>` - Export to JSONL file instead of stdout

**clean** - Reset the database by removing all torrents and matches
- `--db <path>` - SQLite database path (default: `~/.torrent_scanner/torrents.db`)
- `--redis <path>` - Redis database path (default: `~/.torrent_scanner/redis.db`)

Alternative usage:
```bash
python -m torrent_scanner.cli scan /path/to/dir
python -m torrent_scanner.cli torrents /path/to/dir
python -m torrent_scanner.cli files /path/to/dir
python -m torrent_scanner.cli info
python -m torrent_scanner.cli list-matches
```

## Output Format (JSONL)

Each line is a JSON object with core torrent fields and matched paths, for example:

```json
{
  "info_hash": "<40-hex>",
  "torrent_path": "/path/to/file.torrent",
  "name": "Ubuntu ISO",
  "name_hash": "<64-hex>",
  "structure_hash": "<64-hex or null>",
  "is_multi": true,
  "total_length": 2147483648,
  "created_unix": 1700000000,
  "created_by": "mktorrent 1.1",
  "comment": null,
  "matches": ["/data/ubuntu"],
  "first_seen_ts": 1700000001
}
```

## Project Structure

```
./
├─ torrent_scanner.py            # Entry script (delegates to package CLI)
├─ torrent_scanner/
│  ├─ __init__.py                # Package exports + version
│  ├─ cli.py                     # CLI: scan, torrents, files, info, list-matches, clean
│  ├─ scanner.py                 # Orchestrates ingest + matching
│  ├─ torrent.py                 # Torrent parsing and DB ingest
│  ├─ bencode.py                 # Minimal bencode decoder with info span
│  ├─ filesystem.py              # Discovery + structure/name hashing
│  └─ models.py                  # Peewee models and DB helpers
├─ tests/                        # Pytest suite
├─ requirements.txt
├─ requirements-test.txt
└─ pytest.ini
```

## Development

Run tests:
```bash
./run_tests.py
```

## Limitations

- Matching is metadata-based (names, sizes, structure) and does not verify torrent piece hashes
- Symlinks are skipped during scanning; permission errors are ignored
- Only `.torrent` files are supported; magnet URIs are not supported

