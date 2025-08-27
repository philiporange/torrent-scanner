#!/usr/bin/env python3
"""
torrent_scanner.py

A utility to index .torrent files and match on-disk data folders/files.

This is the main entry point script that uses the torrent_scanner package.
"""

import sys
from torrent_scanner import main

if __name__ == "__main__":
    sys.exit(main())