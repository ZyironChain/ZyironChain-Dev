import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))



# helper.py
import importlib
import lmdb
import json

import lmdb
import json

def inspect_lmdb(db_path: str):
    """
    Inspect the raw data in an LMDB database.
    Handles both JSON and raw binary data.
    """
    env = lmdb.open(db_path, readonly=True)
    with env.begin() as txn:
        cursor = txn.cursor()
        for key, value in cursor:
            try:
                # Decode key and value as UTF-8 strings
                key_str = key.decode("utf-8", errors="replace")
                value_str = value.decode("utf-8", errors="replace")

                # Try to parse the value as JSON
                try:
                    data = json.loads(value_str)
                    print(f"Key: {key_str}")
                    print(f"Data (JSON): {json.dumps(data, indent=2)}")
                except json.JSONDecodeError:
                    # If JSON parsing fails, print the raw value
                    print(f"Key: {key_str}")
                    print(f"Data (Raw): {value_str}")
            except UnicodeDecodeError:
                # If decoding fails, treat the data as binary
                print(f"Key: {key} (binary)")
                print(f"Data: {value} (binary)")

# Example usage
inspect_lmdb("./blockchain_storage/BlockData/full_block_chain/0001.lmdb")