import os
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import os

def export_source_code_to_txt(root_dir, output_file, exclude_folders=None):
    """
    Recursively scans a directory for .py files and writes their contents to a text file,
    excluding specified folders.

    Args:
        root_dir (str): The root directory to scan.
        output_file (str): The output text file to save the source code.
        exclude_folders (list): List of folder names to exclude.
    """
    if exclude_folders is None:
        exclude_folders = []

    with open(output_file, "w", encoding="utf-8") as outfile:
        for root, dirs, files in os.walk(root_dir):
            # Remove excluded folders from the directory list
            dirs[:] = [d for d in dirs if d not in exclude_folders]

            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, root_dir)

                    # Write file path as a header
                    outfile.write(f"\n\n=== File: {relative_path} ===\n\n")

                    # Write file contents
                    with open(file_path, "r", encoding="utf-8") as infile:
                        outfile.write(infile.read())

if __name__ == "__main__":
    # Set the root directory of your project
    project_root = "C:/Users/PC/Desktop/Zyiron_Chain"  # Update this path

    # Set the output file
    output_file = "source_code.txt"

    # Set folders to exclude
    exclude_folders = ["falcon", "falcon", "frontend"]  # Add any other folders to exclude here

    # Export the source code
    export_source_code_to_txt(project_root, output_file, exclude_folders)
    print(f"Source code exported to {output_file} (excluding folders: {exclude_folders})")