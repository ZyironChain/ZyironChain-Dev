import sys
import os

# Add the project root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))



import unittest
from Zyiron_Chain.blockchain.block import Block, BlockHeader

def query_block(block_index):
    """Fetch and display a block from UnQLite and LMDB."""
    poc = PoC()

    # ✅ Query UnQLite
    block_data = poc.unqlite_db.get(f"block:{block_index}")
    if block_data:
        print(f"\n[✅ UNQLITE BLOCK {block_index} FOUND]")
        print(json.dumps(block_data, indent=4))
    else:
        print(f"\n[❌ UNQLITE BLOCK {block_index} NOT FOUND]")

    # ✅ Query LMDB for block hash
    block_hash = poc.lmdb_manager.get(f"block_hash:{block_index}")
    if block_hash:
        print(f"\n[✅ LMDB BLOCK HASH {block_index} FOUND]: {block_hash}")
    else:
        print(f"\n[❌ LMDB BLOCK HASH {block_index} NOT FOUND]")

def query_latest_block():
    """Fetch the latest block stored in UnQLite."""
    poc = PoC()

    latest_index = 0
    while poc.unqlite_db.get(f"block:{latest_index}"):
        latest_index += 1

    if latest_index > 0:
        latest_index -= 1  # Last valid block index
        query_block(latest_index)
    else:
        print("\n[❌ NO BLOCKS FOUND IN DATABASE]")

def query_all_blocks():
    """Fetch all blocks and print their details."""
    poc = PoC()
    index = 0

    print("\n[🔍 QUERYING ALL BLOCKS...]")
    while True:
        block_data = poc.unqlite_db.get(f"block:{index}")
        if not block_data:
            break
        print(f"\n[✅ BLOCK {index} DATA]")
        print(json.dumps(block_data, indent=4))
        index += 1

    if index == 0:
        print("\n[❌ NO BLOCKS FOUND IN DATABASE]")

if __name__ == "__main__":
    print("\n[🔍 BLOCKCHAIN QUERY TOOL]")
    print("[1] Query Specific Block")
    print("[2] Query Latest Block")
    print("[3] Query All Blocks")
    print("[4] Exit")

    choice = input("\nEnter your choice (1-4): ")

    if choice == "1":
        block_num = input("Enter block index to query: ")
        query_block(block_num)
    elif choice == "2":
        query_latest_block()
    elif choice == "3":
        query_all_blocks()
    else:
        print("\n[🚀 EXITING QUERY TOOL]")