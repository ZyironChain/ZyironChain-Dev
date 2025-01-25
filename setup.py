import os
import subprocess

def get_installed_packages():
    """Get a list of installed packages using pip."""
    result = subprocess.run(["pip", "list"], capture_output=True, text=True)
    installed_packages = result.stdout.splitlines()[2:]  # Skip header lines
    return [line.split()[0] for line in installed_packages]

def get_imports_in_file(file_path):
    """Extract imported libraries from a Python file."""
    imports = set()
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                if line.startswith("import ") or line.startswith("from "):
                    # Extract the library name
                    lib = line.split()[1].split(".")[0]
                    imports.add(lib)
    except UnicodeDecodeError:
        print(f"Skipping file due to encoding issues: {file_path}")
    return imports

def get_project_imports(project_dir):
    """Get all imported libraries in the project."""
    imports = set()
    for root, _, files in os.walk(project_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                imports.update(get_imports_in_file(file_path))
    return imports

def get_file_structure(project_dir):
    """Generate the file structure of the project."""
    structure = []
    for root, dirs, files in os.walk(project_dir):
        level = root.replace(project_dir, "").count(os.sep)
        indent = " " * 4 * level
        structure.append(f"{indent}{os.path.basename(root)}/")
        sub_indent = " " * 4 * (level + 1)
        for file in files:
            structure.append(f"{sub_indent}{file}")
    return structure

def main():
    project_dir = os.getcwd()  # Current directory as the project directory
    print("Generating pip install commands and file structure...\n")

    # Get installed packages
    installed_packages = get_installed_packages()

    # Get imported libraries in the project
    project_imports = get_project_imports(project_dir)

    # Filter installed packages that are used in the project
    required_packages = [pkg for pkg in installed_packages if pkg.lower() in project_imports]

    # Generate pip install commands
    print("Pip Install Commands:")
    for pkg in required_packages:
        print(f"pip install {pkg}")

    # Generate file structure
    print("\nFile Structure:")
    for line in get_file_structure(project_dir):
        print(line)

if __name__ == "__main__":
    main()