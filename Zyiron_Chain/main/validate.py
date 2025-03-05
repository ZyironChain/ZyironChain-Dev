#!/usr/bin/env python3
import os
import sys

def search_logging_in_py_files(root_dir):
    """
    Recursively search for the word 'logging' in all .py files under root_dir.
    Returns a list of strings with file path, line number, and matching line.
    """
    results = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                file_path = os.path.join(dirpath, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as file:
                        for i, line in enumerate(file, start=1):
                            if "logging" in line:
                                results.append(f"{file_path} (Line {i}): {line.strip()}")
                except Exception as e:
                    results.append(f"Error reading {file_path}: {e}")
    return results

def write_results_to_file(results, output_file="logging_occurrences.txt"):
    """
    Write the search results to a text file.
    """
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            for result in results:
                f.write(result + "\n")
        print(f"Results written to {output_file}")
    except Exception as e:
        print(f"Error writing to file {output_file}: {e}")

if __name__ == "__main__":
    # Use the first command line argument as the root directory; default to current directory.
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    print(f"Searching for 'logging' in .py files under: {os.path.abspath(root)}\n")
    results = search_logging_in_py_files(root)
    write_results_to_file(results)
