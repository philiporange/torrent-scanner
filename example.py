#!/usr/bin/env python3
"""
Comprehensive example demonstrating the full functionality of torrent_scanner.

This example shows how to use both the high-level API and low-level functions
to index torrent files, find matching data, and query the database.

Expected setup:
- Some .torrent files in a directory (we'll simulate this)
- Some downloaded data that matches those torrents (we'll simulate this too)
- The torrent_scanner library installed

Run with: python example.py
"""

import os
import tempfile
import json
from pathlib import Path

# Import the high-level API (recommended for most use cases)
from torrent_scanner import TorrentScanner, quick_check, quick_locate, quick_identify

# Import low-level functions for advanced usage
from torrent_scanner.models import (
    init_database, close_database, Torrent, TorrentFile, Match,
    fetch_matched_torrents, fetch_unmatched_torrents
)
from torrent_scanner.torrent import TorrentMeta


def create_sample_torrent_file(torrent_path: Path, name: str, files: list) -> str:
    """
    Create a minimal .torrent file for demonstration.
    In real usage, you'd have actual .torrent files from BitTorrent clients.
    
    Returns the info_hash of the created torrent.
    """
    # This is a simplified torrent creation for demo purposes
    # Real .torrent files are bencoded dictionaries with more complex structure
    
    print(f"📁 Creating sample .torrent file: {torrent_path}")
    
    # For this demo, we'll create a mock torrent and manually add it to the database
    # In real usage, scan_torrents() would parse actual .torrent files
    
    # Generate a fake but valid 40-character SHA-1 hash
    import hashlib
    info_hash = hashlib.sha1(name.encode()).hexdigest()
    
    # Create a dummy .torrent file (just for demonstration)
    with torrent_path.open('w') as f:
        f.write(f"# Mock torrent file for: {name}\n")
        f.write(f"# Info hash: {info_hash}\n")
        for file_info in files:
            f.write(f"# File: {file_info['path']} ({file_info['size']} bytes)\n")
    
    return info_hash


def create_sample_data(base_path: Path, files: list):
    """
    Create sample data files that match our torrents.
    In real usage, these would be files you've actually downloaded.
    """
    print(f"📂 Creating sample data in: {base_path}")
    
    for file_info in files:
        file_path = base_path / file_info['path']
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create a file with the specified size
        with file_path.open('wb') as f:
            # Write some dummy data
            content = f"Sample content for {file_info['path']}\n" * (file_info['size'] // 50 + 1)
            f.write(content.encode()[:file_info['size']])
        
        print(f"  ✓ Created: {file_path} ({file_info['size']} bytes)")


def demo_high_level_api():
    """
    Demonstrate the high-level TorrentScanner API.
    This is the recommended way to use torrent_scanner as a library.
    """
    print("\n" + "="*60)
    print("🚀 HIGH-LEVEL API DEMONSTRATION")
    print("="*60)
    
    # Create temporary directories for our demo
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        torrent_dir = temp_path / "torrents"
        data_dir = temp_path / "downloads"
        db_path = temp_path / "scanner.db"
        
        torrent_dir.mkdir()
        data_dir.mkdir()
        
        print(f"📍 Working in temporary directory: {temp_path}")
        
        # 1. CREATE SAMPLE TORRENTS AND DATA
        print("\n1️⃣  Setting up sample torrents and data...")
        
        # Sample torrent 1: Ubuntu ISO (single file)
        ubuntu_files = [{"path": "ubuntu-20.04.3-desktop-amd64.iso", "size": 3379068928}]
        ubuntu_hash = create_sample_torrent_file(
            torrent_dir / "ubuntu.torrent", 
            "Ubuntu 20.04.3 Desktop", 
            ubuntu_files
        )
        create_sample_data(data_dir / "Ubuntu 20.04.3 Desktop", ubuntu_files)
        
        # Sample torrent 2: Music album (multi-file)
        album_files = [
            {"path": "01-intro.mp3", "size": 5242880},
            {"path": "02-main_song.mp3", "size": 8388608},
            {"path": "03-outro.mp3", "size": 4194304},
            {"path": "album_art.jpg", "size": 102400}
        ]
        album_hash = create_sample_torrent_file(
            torrent_dir / "music_album.torrent",
            "Awesome Music Album",
            album_files
        )
        create_sample_data(data_dir / "Awesome Music Album", album_files)
        
        # Sample torrent 3: Software package (not downloaded)
        software_files = [{"path": "installer.exe", "size": 50331648}]
        software_hash = create_sample_torrent_file(
            torrent_dir / "software.torrent",
            "Software Package v2.1",
            software_files
        )
        # Note: We're NOT creating data for this one to demo unmatched torrents
        
        # 2. INITIALIZE THE SCANNER
        print(f"\n2️⃣  Initializing TorrentScanner with database: {db_path}")
        scanner = TorrentScanner(db_path=db_path)
        
        # The scanner automatically uses these default paths if not specified:
        # - Database: ~/.torrent_scanner/torrents.db  
        # - Redis: ~/.torrent_scanner/redis.db
        print("💡 In production, you can use: scanner = TorrentScanner()")
        print("   This will use default paths in ~/.torrent_scanner/")
        
        # 3. INDEX TORRENT FILES
        print(f"\n3️⃣  Indexing .torrent files from: {torrent_dir}")
        
        # For this demo, we'll manually add torrents since we created mock files
        # In real usage: index_stats = scanner.index_torrents([torrent_dir])
        
        # Manually add our demo torrents to the database
        init_database(db_path)
        try:
            # Add Ubuntu torrent
            ubuntu_torrent = Torrent.create(
                info_hash=ubuntu_hash,
                torrent_path=str(torrent_dir / "ubuntu.torrent"),
                name="Ubuntu 20.04.3 Desktop",
                name_hash=ubuntu_hash[:16],
                is_multi=False,
                total_length=ubuntu_files[0]['size']
            )
            
            # Add music album torrent  
            album_torrent = Torrent.create(
                info_hash=album_hash,
                torrent_path=str(torrent_dir / "music_album.torrent"),
                name="Awesome Music Album", 
                name_hash=album_hash[:16],
                is_multi=True,
                total_length=sum(f['size'] for f in album_files)
            )
            
            # Add software torrent
            software_torrent = Torrent.create(
                info_hash=software_hash,
                torrent_path=str(torrent_dir / "software.torrent"),
                name="Software Package v2.1",
                name_hash=software_hash[:16], 
                is_multi=False,
                total_length=software_files[0]['size']
            )
            
            print(f"  ✓ Indexed 3 torrents")
            print(f"    - Ubuntu ISO: {ubuntu_hash}")
            print(f"    - Music Album: {album_hash}")  
            print(f"    - Software: {software_hash}")
            
        finally:
            close_database()
        
        # 4. FIND MATCHING DATA
        print(f"\n4️⃣  Finding data that matches indexed torrents in: {data_dir}")
        
        # For this demo, we'll manually add matches since we created mock data
        # In real usage: matches = scanner.find_matches([data_dir])
        
        init_database(db_path)
        try:
            # Add match for Ubuntu
            Match.create(
                torrent=ubuntu_torrent,
                data_path=str(data_dir / "Ubuntu 20.04.3 Desktop")
            )
            
            # Add match for music album
            Match.create(
                torrent=album_torrent, 
                data_path=str(data_dir / "Awesome Music Album")
            )
            
            # No match for software (it's not downloaded)
            
            print("  ✓ Found 2 matches:")
            print(f"    - Ubuntu data at: {data_dir / 'Ubuntu 20.04.3 Desktop'}")
            print(f"    - Music data at: {data_dir / 'Awesome Music Album'}")
            print("    - Software not found (as expected)")
            
        finally:
            close_database()
        
        # 5. QUERY INDIVIDUAL TORRENTS
        print(f"\n5️⃣  Querying individual torrents...")
        
        # Check if torrents are downloaded
        print(f"\n📊 Download status:")
        for name, hash_val in [("Ubuntu", ubuntu_hash), ("Music", album_hash), ("Software", software_hash)]:
            is_downloaded = scanner.is_downloaded(hash_val)
            status = "✅ Downloaded" if is_downloaded else "❌ Not downloaded"
            print(f"  {name}: {status}")
        
        # Get data locations for downloaded torrents
        print(f"\n📂 Data locations:")
        ubuntu_locations = scanner.get_data_locations(ubuntu_hash)
        if ubuntu_locations:
            print(f"  Ubuntu found at: {ubuntu_locations[0]}")
        
        album_locations = scanner.get_data_locations(album_hash)  
        if album_locations:
            print(f"  Music found at: {album_locations[0]}")
        
        # Get detailed torrent information
        print(f"\n📋 Torrent details:")
        ubuntu_info = scanner.get_torrent_info(ubuntu_hash)
        if ubuntu_info:
            print(f"  Ubuntu: {ubuntu_info['name']}")
            print(f"    Size: {ubuntu_info['total_length']:,} bytes")
            print(f"    Multi-file: {ubuntu_info['is_multi']}")
            print(f"    Matches: {len(ubuntu_info['matches'])}")
        
        # 6. LIST AND FILTER TORRENTS  
        print(f"\n6️⃣  Listing and filtering torrents...")
        
        all_torrents = scanner.list_torrents("all")
        matched_torrents = scanner.list_torrents("matched")
        unmatched_torrents = scanner.list_torrents("unmatched")
        
        print(f"  📊 Summary:")
        print(f"    Total torrents: {len(all_torrents)}")
        print(f"    Downloaded: {len(matched_torrents)}")  
        print(f"    Not downloaded: {len(unmatched_torrents)}")
        
        print(f"\n  📋 Downloaded torrents:")
        for torrent in matched_torrents:
            print(f"    - {torrent['name']} ({torrent['match_count']} locations)")
        
        print(f"\n  📋 Not downloaded torrents:")
        for torrent in unmatched_torrents:
            print(f"    - {torrent['name']}")
        
        # 7. GET DATABASE STATISTICS
        print(f"\n7️⃣  Database statistics...")
        
        stats = scanner.get_statistics()
        print(f"  📈 Database stats:")
        print(f"    Total torrents: {stats['total_torrents']}")
        print(f"    Matched torrents: {stats['matched_torrents']}")
        print(f"    Total matches: {stats['total_matches']}")
        print(f"    Single-file torrents: {stats['single_file_torrents']}")
        print(f"    Multi-file torrents: {stats['multi_file_torrents']}")
        
        # Format total size in human-readable format
        size_bytes = stats['total_size_bytes']
        if size_bytes >= 1024**3:
            size_str = f"{size_bytes / (1024**3):.1f} GB"
        elif size_bytes >= 1024**2:
            size_str = f"{size_bytes / (1024**2):.1f} MB"
        else:
            size_str = f"{size_bytes:,} bytes"
        print(f"    Total size: {size_str}")
        
        # 8. EXPORT MATCHES  
        print(f"\n8️⃣  Exporting matches...")
        
        matches = scanner.export_matches()
        export_file = temp_path / "matches.json"
        
        with export_file.open('w') as f:
            json.dump(matches, f, indent=2)
            
        print(f"  💾 Exported {len(matches)} matches to: {export_file}")
        print(f"  📄 Sample match data:")
        if matches:
            sample = matches[0]
            print(f"    Info hash: {sample['info_hash']}")
            print(f"    Name: {sample['name']}")
            print(f"    Data paths: {sample['matches']}")


def demo_convenience_functions():
    """
    Demonstrate the convenience functions for one-off operations.
    These are useful for quick checks without creating a TorrentScanner instance.
    """
    print("\n" + "="*60)
    print("⚡ CONVENIENCE FUNCTIONS DEMONSTRATION")  
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        db_path = temp_path / "convenience.db"
        
        # Create a sample torrent in the database
        print("📋 Setting up sample data...")
        
        init_database(db_path)
        try:
            sample_hash = "1234567890abcdef1234567890abcdef12345678"
            
            torrent = Torrent.create(
                info_hash=sample_hash,
                torrent_path="/path/to/sample.torrent",
                name="Sample Torrent",
                name_hash="sample123",
                is_multi=False,
                total_length=1048576
            )
            
            Match.create(
                torrent=torrent,
                data_path="/downloads/sample_data"
            )
            
        finally:
            close_database()
        
        # 1. QUICK CHECK
        print(f"\n1️⃣  Quick check if torrent is downloaded:")
        print(f"  Code: quick_check('{sample_hash}', db_path)")
        
        is_downloaded = quick_check(sample_hash, db_path)
        result = "✅ Yes" if is_downloaded else "❌ No"
        print(f"  Result: {result}")
        
        # 2. QUICK LOCATE
        print(f"\n2️⃣  Quick locate torrent data:")
        print(f"  Code: quick_locate('{sample_hash}', db_path)")
        
        locations = quick_locate(sample_hash, db_path)
        print(f"  Result: Found at {len(locations)} location(s)")
        for loc in locations:
            print(f"    - {loc}")
        
        # 3. QUICK IDENTIFY
        print(f"\n3️⃣  Quick identify torrent from data path:")
        print(f"  Code: quick_identify('/downloads/sample_data', db_path)")
        
        torrent_info = quick_identify(Path("/downloads/sample_data"), db_path)
        if torrent_info:
            print(f"  Result: Found torrent '{torrent_info['name']}'")
            print(f"    Info hash: {torrent_info['info_hash']}")
        else:
            print("  Result: No torrent found for this path")


def demo_cli_usage():
    """
    Demonstrate CLI usage with examples.
    This shows how to use torrent_scanner from the command line.
    """
    print("\n" + "="*60)
    print("💻 CLI USAGE DEMONSTRATION")
    print("="*60)
    
    print("The torrent_scanner CLI provides intuitive commands for all operations:")
    
    print(f"\n📥 INDEXING COMMANDS:")
    print("  # Index .torrent files from directories")
    print("  torrent_scanner index /path/to/torrents /more/torrents")
    print("  torrent_scanner index ~/Downloads --quiet")
    print("")
    print("  # Find data that matches indexed torrents")  
    print("  torrent_scanner match /path/to/data /more/data")
    print("  torrent_scanner match ~/Downloads -o matches.json")
    print("")
    print("  # Do both operations at once (recommended)")
    print("  torrent_scanner update /path/to/downloads")
    print("  torrent_scanner update ~/Downloads --quiet -o matches.jsonl")
    
    print(f"\n🔍 QUERY COMMANDS:")
    print("  # Check if a torrent is downloaded (exit code 0 = yes, 1 = no)")
    print("  torrent_scanner check 1234567890abcdef1234567890abcdef12345678")
    print("  torrent_scanner check /path/to/file.torrent --verbose")
    print("")
    print("  # Find where torrent data is stored")
    print("  torrent_scanner locate 1234567890abcdef1234567890abcdef12345678")
    print("  torrent_scanner locate /path/to/file.torrent --format json")
    print("")
    print("  # Identify which torrent a file/folder belongs to")
    print("  torrent_scanner identify /path/to/data")
    print("  torrent_scanner identify ~/Downloads/ubuntu.iso --format json")
    
    print(f"\n📋 LIST COMMANDS:")
    print("  # List all torrents in database")
    print("  torrent_scanner list")
    print("  torrent_scanner list --filter matched")  
    print("  torrent_scanner list --filter unmatched --format json")
    print("  torrent_scanner list --format info-hash > hashes.txt")
    
    print(f"\n🗃️  DATABASE COMMANDS:")
    print("  # Show database statistics")
    print("  torrent_scanner stats")
    print("  torrent_scanner stats --json")
    print("")
    print("  # Export database contents")
    print("  torrent_scanner export --format json -o backup.json")
    print("  torrent_scanner export --format csv -o matches.csv --matches-only")
    print("")  
    print("  # Reset database (remove all data)")
    print("  torrent_scanner reset --confirm")
    
    print(f"\n⚙️  GLOBAL OPTIONS:")
    print("  # Use custom database paths")
    print("  torrent_scanner --db /custom/db.sqlite stats")
    print("  torrent_scanner --db /custom/db.sqlite --redis /custom/redis.db update ~/Downloads")
    
    print(f"\n📖 MIGRATION FROM OLD COMMANDS:")
    print("  # Old -> New command mappings")
    print("  scan          -> update    # Full scan (index + match)")
    print("  torrents      -> index     # Index .torrent files only") 
    print("  files         -> match     # Find matching data only")
    print("  list-matches  -> list --filter matched")
    print("  get-data      -> locate    # Find data locations") 
    print("  get-torrent   -> identify  # Identify torrent from data")
    print("  info          -> stats     # Show statistics")
    print("  clean         -> reset     # Clear database")


def demo_real_world_workflow():
    """
    Demonstrate a realistic workflow for using torrent_scanner.
    This shows how you might use it in practice.
    """
    print("\n" + "="*60)
    print("🌍 REAL-WORLD WORKFLOW DEMONSTRATION")
    print("="*60)
    
    print("Here's how you might use torrent_scanner in real scenarios:")
    
    print(f"\n📁 SCENARIO 1: Organizing Downloads")
    print("You have torrents scattered across multiple directories and want to")
    print("find what you've actually downloaded:")
    print("")
    print("  # Index all your .torrent files")  
    print("  torrent_scanner index ~/Downloads ~/Torrents ~/Desktop")
    print("")
    print("  # Find matching data across all your drives")
    print("  torrent_scanner match /media/drive1 /media/drive2 ~/Downloads")
    print("")
    print("  # See what's downloaded vs not downloaded")
    print("  torrent_scanner list --filter matched    # What you have")
    print("  torrent_scanner list --filter unmatched  # What you're missing")
    
    print(f"\n🔄 SCENARIO 2: Automation & Scripting")
    print("You want to automate torrent management:")
    print("")
    print("  # Check if specific torrents are downloaded (in a script)")
    print("  if torrent_scanner check $INFO_HASH --quiet; then")
    print("    echo 'Already downloaded'")
    print("  else") 
    print("    echo 'Need to download'")
    print("  fi")
    print("")
    print("  # Export unmatched torrents for batch downloading")
    print("  torrent_scanner list --filter unmatched --format info-hash > to_download.txt")
    
    print(f"\n📊 SCENARIO 3: Library Integration")
    print("You're building a larger application that manages torrents:")
    
    print("""
  # Python code example:
  from torrent_scanner import TorrentScanner
  
  scanner = TorrentScanner()  # Uses default paths
  
  # Periodic updates
  scanner.update(['/downloads', '/media/torrents'])
  
  # Query interface 
  def is_available(info_hash):
      return scanner.is_downloaded(info_hash)
  
  def get_file_locations(info_hash):
      return scanner.get_data_locations(info_hash)
  
  # Bulk operations
  all_downloaded = scanner.list_torrents('matched')
  missing_torrents = scanner.list_torrents('unmatched')
  
  # Statistics for UI
  stats = scanner.get_statistics()
  print(f"Managing {stats['total_torrents']} torrents")
  print(f"{stats['matched_torrents']} downloaded")
""")
    
    print(f"\n🚀 SCENARIO 4: Initial Setup")
    print("Setting up torrent_scanner for the first time:")
    print("")
    print("  # 1. Scan your existing collection")
    print("  torrent_scanner update ~/Downloads ~/Media /external/drive")
    print("")
    print("  # 2. See what you've got")  
    print("  torrent_scanner stats")
    print("")
    print("  # 3. Export everything for backup")
    print("  torrent_scanner export --format json -o torrent_backup.json")
    print("")
    print("  # 4. Set up monitoring (add to cron/systemd)")
    print("  # Check for new torrents and data daily:")
    print("  torrent_scanner update ~/Downloads --quiet")


def main():
    """
    Main function that runs all demonstrations.
    """
    print("🎯 TORRENT SCANNER - COMPREHENSIVE EXAMPLE")
    print("="*60)
    print("This example demonstrates the full functionality of torrent_scanner,")
    print("including both the high-level API and CLI usage patterns.")
    print("")
    print("💡 Note: This creates temporary files and databases for demonstration.")
    print("   In real usage, you'd work with actual .torrent files and data.")
    
    try:
        # Run all demonstrations
        demo_high_level_api()
        demo_convenience_functions()
        demo_cli_usage()
        demo_real_world_workflow()
        
        print("\n" + "="*60)
        print("✅ DEMONSTRATION COMPLETE")
        print("="*60)
        print("🎉 All examples completed successfully!")
        print("")
        print("📚 Next steps:")
        print("  - Try the CLI commands shown above")
        print("  - Integrate the API into your own projects")
        print("  - Check the README.md for detailed documentation")
        print("  - Run the test suite with: python -m pytest tests/")
        
    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        print("🔧 This might happen if:")
        print("  - Dependencies are missing (pip install -r requirements.txt)")
        print("  - Permissions issues with temporary directories")
        print("  - Other environment issues")
        raise


if __name__ == "__main__":
    main()