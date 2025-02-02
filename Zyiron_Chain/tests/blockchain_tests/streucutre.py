import os
import re

def list_files_and_dependencies(directory):
    """
    Recursively lists all Python files, their modules, classes, and dependencies.
    """
    project_structure = {}
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.readlines()
                    modules = []
                    classes = []
                    functions = []
                    dependencies = []
                    
                    for line in content:
                        stripped = line.strip()
                        if stripped.startswith("import") or stripped.startswith("from"):
                            modules.append(stripped)
                        elif stripped.startswith("class"):
                            classes.append(stripped)
                        elif stripped.startswith("def"):
                            functions.append(stripped)
                        
                        # Extract dependencies between modules
                        match = re.search(r'from (\S+) import', stripped)
                        if match:
                            dependencies.append(match.group(1))
                    
                    project_structure[file_path] = {
                        "modules": modules,
                        "classes": classes,
                        "functions": functions,
                        "dependencies": dependencies
                    }
    
    return project_structure

def save_project_source(directory, output_file):
    """
    Saves the entire source code of all Python files in the project into a text file.
    """
    with open(output_file, "w", encoding="utf-8") as out:
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    out.write(f"\n{'='*80}\nFile: {file_path}\n{'='*80}\n")
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        out.write(f.read())
                    out.write("\n")

def save_structure_to_txt(structure, output_file):
    """
    Saves the structured project information including modules, classes, and dependencies to a text file.
    """
    with open(output_file, "w", encoding="utf-8") as out:
        for file, details in structure.items():
            out.write(f"\n{'='*80}\nFile: {file}\n{'='*80}\n")
            out.write("\nModules:\n" + "\n".join(details["modules"]))
            out.write("\n\nClasses:\n" + "\n".join(details["classes"]))
            out.write("\n\nFunctions:\n" + "\n".join(details["functions"]))
            out.write("\n\nDependencies:\n" + "\n".join(details["dependencies"]))
            out.write("\n")

def main():
    project_directory = os.getcwd()  # Change this if needed
    structure_output_file = os.path.join(project_directory, "project_structure.txt")
    source_code_output_file = os.path.join(project_directory, "project_source_code.txt")
    
    print("[INFO] Scanning project structure...")
    structure = list_files_and_dependencies(project_directory)
    
    print("[INFO] Saving structured project information...")
    save_structure_to_txt(structure, structure_output_file)
    
    print("[INFO] Saving full project source code to text file...")
    save_project_source(project_directory, source_code_output_file)
    
    print("[INFO] Project structure and source code saved successfully!")

if __name__ == "__main__":
    main()