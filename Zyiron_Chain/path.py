import os
import shutil
import sys
import subprocess

# Paths
project_dir = os.getcwd()
venv_path = os.path.join(project_dir, ".venv")
requirements_file = os.path.join(project_dir, "requirements.txt")

# Remove existing virtual environment
if os.path.exists(venv_path):
    print("Removing existing virtual environment...")
    shutil.rmtree(venv_path)

# Create a new virtual environment
print("Creating new virtual environment...")
subprocess.run([sys.executable, "-m", "venv", venv_path])

# Activate the virtual environment
activate_script = os.path.join(venv_path, "Scripts", "activate_this.py")
exec(open(activate_script).read(), {'__file__': activate_script})
print("Virtual environment activated.")

# Install dependencies
if os.path.exists(requirements_file):
    print("Installing dependencies from requirements.txt...")
    subprocess.run([os.path.join(venv_path, "Scripts", "pip"), "install", "-r", requirements_file])
else:
    print("No requirements.txt found. Skipping dependency installation.")

# Run the Python script
print("Running the database synchronization script...")
subprocess.run([os.path.join(venv_path, "Scripts", "python"), "-m", "Zyiron_Chain.database.dbsync"])
