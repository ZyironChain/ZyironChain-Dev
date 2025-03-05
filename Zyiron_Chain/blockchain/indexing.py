import os

def print_structure(root_dir, output_file):
    """
    Recursively walks through the given root_dir and writes
    the folder structure (including files) to output_file.
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        for current_path, dirs, files in os.walk(root_dir):
            # Determine the nesting level based on path depth
            level = current_path.replace(root_dir, '').count(os.sep)
            indent = '    ' * level

            # Write the current directory name
            f.write(f"{indent}{os.path.basename(current_path)}/\n")

            # Write each file within the current directory
            for file in files:
                f.write(f"{indent}    {file}\n")

if __name__ == "__main__":
    # Update this path to point to your project's root directory
    project_root = "C:\\Users\\PC\\Desktop\\Zyiron_Chain"  # Example Windows path
    
    # This is the output file where the structure will be saved
    output_file = "project_structure.txt"
    
    print_structure(project_root, output_file)
    print(f"Project structure saved to {output_file}")
