import os
import sys
import json
import pickle
import struct
import time
import hashlib
from decimal import Decimal
from typing import List, Optional, Dict

# Set module search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.utils.hashing import Hashing

def get_block():
    """Lazy import Block to break circular dependency."""
    from Zyiron_Chain.blockchain.block import Block
    return Block

class OrphanBlocks:
    """
    OrphanBlocks manages the storage and retrieval of orphan blocks using LMDB.
    
    Responsibilities:
      - Store orphan block metadata in LMDB.
      - Retrieve, list, and remove orphan blocks.
      - Ensure data is handled in bytes.
      - Use single SHA3‑384 hashing for block verification.
      - Use all relevant constants from Constants.
      - Provide detailed print statements for every major step and error.
    """
    
    def __init__(self):
        try:
            orphan_db_path = Constants.DATABASES.get("orphan_blocks")
            if not orphan_db_path:
                raise ValueError("Orphan blocks database path not defined in Constants.DATABASES.")
            self.orphan_db = LMDBManager(orphan_db_path)
            # (Optional) If needed, a lock can be added:
            # self._db_lock = threading.Lock()
            print(f"[OrphanBlocks.__init__] INFO: OrphanBlocks initialized with LMDB path: {orphan_db_path}")
        except Exception as e:
            print(f"[OrphanBlocks.__init__] ERROR: Failed to initialize OrphanBlocks: {e}")
            raise

    def store_orphan_block(self, block) -> None:
        """
        Store an orphan block in LMDB.
        The block's hash is computed using single SHA3‑384 hashing.
        The block metadata is JSON-serialized and stored as bytes.
        """
        try:
            # Compute the block hash using single SHA3‑384 hashing
            computed_hash = hashlib.sha3_384(block.calculate_hash().encode()).hexdigest()
            block.hash = computed_hash  # Ensure block hash is set
            orphan_metadata = {
                "hash": computed_hash,
                "block_header": block.header.to_dict() if hasattr(block.header, "to_dict") else block.header,
                "timestamp": block.timestamp,
                "data_offset": None  # Set as needed if using block.data files
            }
            serialized_data = json.dumps(orphan_metadata, sort_keys=True).encode("utf-8")
            key = f"orphan:{computed_hash}".encode("utf-8")
            with self.orphan_db.env.begin(write=True) as txn:
                txn.put(key, serialized_data)
            print(f"[OrphanBlocks.store_orphan_block] INFO: Orphan block {computed_hash} stored successfully.")
        except Exception as e:
            print(f"[OrphanBlocks.store_orphan_block] ERROR: Failed to store orphan block: {e}")
            raise

    def get_orphan_block(self, block_hash: str) -> Optional[Dict]:
        """
        Retrieve an orphan block from LMDB by its hash.
        Returns the orphan block metadata as a dictionary, or None if not found.
        """
        try:
            key = f"orphan:{block_hash}".encode("utf-8")
            with self.orphan_db.env.begin() as txn:
                data = txn.get(key)
            if data is None:
                print(f"[OrphanBlocks.get_orphan_block] WARNING: Orphan block {block_hash} not found.")
                return None
            orphan_block = json.loads(data.decode("utf-8"))
            print(f"[OrphanBlocks.get_orphan_block] INFO: Orphan block {block_hash} retrieved successfully.")
            return orphan_block
        except Exception as e:
            print(f"[OrphanBlocks.get_orphan_block] ERROR: Failed to retrieve orphan block {block_hash}: {e}")
            return None

    def remove_orphan_block(self, block_hash: str) -> bool:
        """
        Remove an orphan block from LMDB by its hash.
        Returns True if removal was successful, False otherwise.
        """
        try:
            key = f"orphan:{block_hash}".encode("utf-8")
            with self.orphan_db.env.begin(write=True) as txn:
                if txn.get(key) is None:
                    print(f"[OrphanBlocks.remove_orphan_block] WARNING: Orphan block {block_hash} not found for removal.")
                    return False
                txn.delete(key)
            print(f"[OrphanBlocks.remove_orphan_block] INFO: Orphan block {block_hash} removed successfully.")
            return True
        except Exception as e:
            print(f"[OrphanBlocks.remove_orphan_block] ERROR: Failed to remove orphan block {block_hash}: {e}")
            return False

    def get_all_orphan_blocks(self) -> List[Dict]:
        """
        Retrieve all orphan blocks stored in LMDB.
        Returns a list of orphan block metadata dictionaries.
        """
        orphan_blocks = []
        try:
            with self.orphan_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    key_str = key.decode("utf-8")
                    if key_str.startswith("orphan:"):
                        try:
                            block_data = json.loads(value.decode("utf-8"))
                            orphan_blocks.append(block_data)
                        except Exception as e:
                            print(f"[OrphanBlocks.get_all_orphan_blocks] ERROR: Failed to decode orphan block {key_str}: {e}")
                            continue
            print(f"[OrphanBlocks.get_all_orphan_blocks] INFO: Retrieved {len(orphan_blocks)} orphan blocks.")
            return orphan_blocks
        except Exception as e:
            print(f"[OrphanBlocks.get_all_orphan_blocks] ERROR: Failed to retrieve orphan blocks: {e}")
            return []

    def close(self) -> None:
        """
        Close the LMDB orphan blocks database connection safely.
        """
        try:
            self.orphan_db.env.close()
            print("[OrphanBlocks.close] INFO: LMDB orphan blocks database connection closed successfully.")
        except Exception as e:
            print(f"[OrphanBlocks.close] ERROR: Failed to close LMDB orphan blocks database connection: {e}")
