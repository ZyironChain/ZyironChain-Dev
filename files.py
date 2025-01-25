import os

def generate_file_structure(start_path, output_file):
    """
    Generate the file structure of a directory and save it to a file.

    Args:
        start_path (str): Path to the root directory of the project.
        output_file (str): Path to the output file to save the structure.
    """
    with open(output_file, 'w') as f:
        for root, dirs, files in os.walk(start_path):
            level = root.replace(start_path, '').count(os.sep)
            indent = ' ' * 4 * level
            f.write(f"{indent}{os.path.basename(root)}/\n")
            subindent = ' ' * 4 * (level + 1)
            for file in files:
                f.write(f"{subindent}{file}\n")

# Replace '/path/to/your/project' with the root directory of your project
project_root = r"C:\Users\PC\Desktop\Zyiron_Chain"
output_file = r"C:\Users\PC\Desktop\file_structure.txt"

generate_file_structure(project_root, output_file)
print(f"File structure saved to {output_file}")
