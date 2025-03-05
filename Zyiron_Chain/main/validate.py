#!/usr/bin/env python3
import os
import sys

def search_logging_in_py_files(root_dir):
    """
    Recursively search for the word 'logging' in all .py files under root_dir.
    
    :param root_dir: The directory to start searching from.
    """
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                file_path = os.path.join(dirpath, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as file:
                        for i, line in enumerate(file, start=1):
                            if "logging" in line:
                                print(f"Found in {file_path} (Line {i}): {line.strip()}")
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

if __name__ == "__main__":
    # Use the first command line argument as the root directory; default to current directory.
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    print(f"Searching for 'logging' in .py files under: {os.path.abspath(root)}\n")
    search_logging_in_py_files(root)
