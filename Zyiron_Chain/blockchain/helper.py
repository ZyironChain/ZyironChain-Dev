import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))



# helper.py
import importlib
import lmdb
import json



def inspect_lmdb(db_path: str):
    """
    Inspect the raw data in an LMDB database.
    """
    env = lmdb.open(db_path, readonly=True)
    with env.begin() as txn:
        cursor = txn.cursor()
        for key, value in cursor:
            try:
                key_str = key.decode("utf-8", errors="replace")
                value_str = value.decode("utf-8", errors="replace")
                print(f"Key: {key_str}")
                print(f"Data: {value_str}")
            except UnicodeDecodeError:
                print(f"Key: {key} (binary)")
                print(f"Data: {value} (binary)")

# Example usage
inspect_lmdb("./blockchain_storage/BlockData/full_block_chain/0001.lmdb")