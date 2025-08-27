#!/usr/bin/env python3
"""
Simple test runner script for the torrent scanner.
"""

import subprocess
import sys


def main():
    """Run all tests with pytest."""
    cmd = [sys.executable, '-m', 'pytest', 'tests/', '-v']
    
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Tests failed with return code: {e.returncode}")
        return e.returncode
    except FileNotFoundError:
        print("pytest not found. Install with: pip install pytest")
        return 1


if __name__ == '__main__':
    sys.exit(main())