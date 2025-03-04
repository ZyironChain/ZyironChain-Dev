import os

def search_tx_id(directory):
    """Search for `.encode(` or `bytes(` occurrences in Python files to identify tx_id formatting issues."""
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):  # Only search Python files
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for i, line in enumerate(f):
                            if "tx_id.encode(" in line or "bytes(tx_id)" in line:
                                print(f"🔎 Found in {file_path}, Line {i+1}: {line.strip()}")
                except Exception as e:
                    print(f"⚠️ Skipping {file_path} due to error: {e}")

# Change to your project root
search_tx_id(r"C:\Users\PC\Desktop\Zyiron_Chain")
