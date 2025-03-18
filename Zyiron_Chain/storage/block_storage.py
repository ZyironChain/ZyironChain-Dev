import os
import re
import string
import sys
import struct
import json
import pickle
import time
from decimal import Decimal
from typing import Optional, List, Dict, Tuple, Union

# Ensure module path is set correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.storage.tx_storage import TxStorage
import struct
import os
from threading import Lock
from Zyiron_Chain.accounts.key_manager import KeyManager
import struct

import os
from threading import Lock
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.blockchain.constants import Constants

class BlockStorage:
    """
    BlockStorage is responsible for handling block metadata and full block storage.
    
    Responsibilities:
      - Store block headers (metadata) in LMDB.
      - Store full blocks in LMDB (`full_block_chain/0001.lmdb`, `0002.lmdb`, etc.).
      - Use single SHA3-384 hashing.
      - Provide detailed print statements for every major step and error.
      - Ensure thread safety with locks.
    """

    def __init__(self, tx_storage: TxStorage, key_manager: KeyManager):
        """
        Initializes BlockStorage:
        - Uses shared LMDB instances for block metadata, transaction index, and full block storage.
        - Manages transaction storage and key manager references.
        - Ensures thread safety with locks.
        - Initializes LMDB file rollover handling.
        """
        try:
            print("[BlockStorage.__init__] INFO: Initializing BlockStorage with LMDB full block storage...")

            # ✅ **Ensure `tx_storage` and `key_manager` are provided**
            if not tx_storage:
                raise ValueError("[BlockStorage.__init__] ❌ ERROR: `tx_storage` instance is required.")
            if not key_manager:
                raise ValueError("[BlockStorage.__init__] ❌ ERROR: `key_manager` instance is required.")

            self.tx_storage = tx_storage
            self.key_manager = key_manager
            self.write_lock = Lock()

            # ✅ **Step 1: Initialize LMDB Databases**
            self.block_metadata_db = LMDBManager(Constants.DATABASES["block_metadata"])
            self.txindex_db = LMDBManager(Constants.DATABASES["txindex"])

            # ✅ **Step 2: Ensure `full_block_chain/` Directory Exists**
            self.blockchain_dir = os.path.join(Constants.BLOCKCHAIN_STORAGE_PATH, "full_block_chain")
            os.makedirs(self.blockchain_dir, exist_ok=True)  # ✅ Create if missing

            # ✅ **Step 3: Determine the Latest LMDB File in `full_block_chain/`**
            lmdb_files = sorted([
                f for f in os.listdir(self.blockchain_dir) if f.endswith(".lmdb") and f.isdigit()
            ])

            if lmdb_files:
                latest_lmdb = os.path.join(self.blockchain_dir, lmdb_files[-1])  # ✅ Use last numbered LMDB file
            else:
                latest_lmdb = os.path.join(self.blockchain_dir, "0001.lmdb")  # ✅ Start with "0001.lmdb"

            # ✅ **Initialize LMDB Storage with the latest or new block file**
            self.full_block_store = LMDBManager(latest_lmdb)

            print(f"[BlockStorage.__init__] ✅ Using LMDB file: {latest_lmdb}")

        except Exception as e:
            print(f"[BlockStorage.__init__] ❌ ERROR: Initialization failed: {e}")
            raise

    def _set_latest_block_file(self):
        """
        ✅ Ensures full_block_chain/ directory exists inside BLOCKCHAIN_STORAGE_PATH.
        ✅ Scans full_block_chain/ for the latest LMDB file.
        ✅ If no files exist, creates 0001.lmdb as the first file.
        ✅ Stores the latest LMDB file path in self.current_block_file.
        """
        try:
            # ✅ **Ensure `full_block_chain/` Directory Exists**
            self.blockchain_dir = os.path.join(Constants.BLOCKCHAIN_STORAGE_PATH, "full_block_chain")
            os.makedirs(self.blockchain_dir, exist_ok=True)

            # ✅ **Scan for existing LMDB files inside `full_block_chain/`**
            existing_files = sorted([
                f for f in os.listdir(self.blockchain_dir) if f.endswith(".lmdb") and f[:-5].isdigit()
            ])

            if existing_files:
                # ✅ **Get the latest LMDB file based on number sequence**
                latest_file = existing_files[-1]
            else:
                # ✅ **If no files exist, create `0001.lmdb`**
                latest_file = "0001.lmdb"

            # ✅ **Set the path for the latest LMDB file**
            self.current_block_file = os.path.join(self.blockchain_dir, latest_file)

            print(f"[BlockStorage._set_latest_block_file] ✅ Using block storage file: {self.current_block_file}")

        except Exception as e:
            print(f"[BlockStorage._set_latest_block_file] ❌ ERROR: Failed to set latest block file: {e}")



    def _check_and_rollover_lmdb(self):
        """
        Checks if the current LMDB file exceeds the size limit.
        If it does, rolls over to a new sequential LMDB file inside `full_block_chain/`.
        """
        try:
            # ✅ **Ensure `full_block_chain/` Directory Exists**
            if not os.path.exists(self.blockchain_dir):
                os.makedirs(self.blockchain_dir, exist_ok=True)

            # ✅ **Check the current LMDB file size**
            current_lmdb_file = self.full_block_store.env.path()
            if os.path.exists(current_lmdb_file) and os.path.getsize(current_lmdb_file) >= Constants.BLOCK_DATA_FILE_SIZE_BYTES:
                print(f"[BlockStorage] INFO: LMDB file {current_lmdb_file} exceeded {Constants.BLOCK_DATA_FILE_SIZE_BYTES} bytes. Rolling over...")

                # ✅ **Determine the next available file number inside `full_block_chain/`**
                existing_files = sorted([
                    f for f in os.listdir(self.blockchain_dir) if f.endswith(".lmdb") and f.isdigit()
                ])
                
                if existing_files:
                    next_file_number = int(existing_files[-1]) + 1  # ✅ Increment the last file number
                else:
                    next_file_number = 1  # ✅ Start from 1 if no files exist

                new_lmdb_file = os.path.join(self.blockchain_dir, f"{next_file_number:04d}.lmdb")  # Format as "0001.lmdb"

                # ✅ **Close the existing LMDB environment before switching**
                self.full_block_store.env.close()

                # ✅ **Switch to the new LMDB file**
                self.full_block_store = LMDBManager(new_lmdb_file)

                print(f"[BlockStorage] ✅ Rolled over to new LMDB file: {new_lmdb_file}")

        except Exception as e:
            print(f"[BlockStorage] ❌ ERROR: Failed to check LMDB rollover: {e}")


    def store_block(self, block: Block):
        """
        Stores a block in LMDB.
        - Ensures the block hash is correctly computed and stored.
        - Calls `_check_and_rollover_lmdb()` to prevent exceeding LMDB size limits.
        - Uses `full_block_chain/` directory for storage.
        - Ensures the latest block index is stored separately for quick retrieval.
        """
        try:
            print(f"[BlockStorage.store_block] INFO: Storing Block {block.index}...")

            # ✅ Ensure latest block file path is set
            self._set_latest_block_file()

            # ✅ Ensure SHA3-384 hash consistency
            calculated_hash = block.calculate_hash()

            # ✅ If block.hash is missing or incorrect, fix it before storing
            if not block.hash or block.hash != calculated_hash:
                print(f"[BlockStorage.store_block] ⚠️ WARNING: Hash mismatch for Block {block.index}. Fixing before storage.")
                block.hash = calculated_hash  # ✅ Assign correct hash

            # ✅ Check if block already exists in `full_block_store`
            block_key = f"block:{block.index}".encode("utf-8")
            block_hash_key = f"block_hash:{block.hash}".encode("utf-8")

            with self.full_block_store.env.begin() as txn:
                existing_block = txn.get(block_key)

            if existing_block:
                print(f"[BlockStorage.store_block] ⚠️ WARNING: Block {block.index} already exists. Skipping.")
                return

            # ✅ Serialize block using its to_dict method for consistent formatting
            block_data = block.to_dict()

            # ✅ Ensure correct JSON formatting before writing to LMDB
            try:
                block_json = json.dumps(block_data, separators=(',', ':'), ensure_ascii=False)
                block_bytes = block_json.encode("utf-8")
            except (TypeError, ValueError) as e:
                print(f"[BlockStorage.store_block] ❌ ERROR: Failed to serialize block {block.index} to JSON: {e}")
                raise

            # ✅ Store full block in `full_block_chain/` LMDB file
            with self.full_block_store.env.begin(write=True) as txn:
                txn.put(block_key, block_bytes)  # ✅ Store block data
                txn.put(block_hash_key, block_key)  # ✅ Store block hash for quick lookup
                txn.put(b"latest_block_index", str(block.index).encode("utf-8"))  # ✅ Store latest block index separately

            print(f"[BlockStorage.store_block] ✅ Block {block.index} stored successfully with hash: {block.hash}")

        except Exception as e:
            print(f"[BlockStorage.store_block] ❌ ERROR: Failed to store block {block.index}: {e}")
            raise



    def verify_stored_block(self, block: Block):
        """
        Verify that a block was correctly stored in LMDB.
        """
        try:
            block_key = f"block:{block.index}".encode("utf-8")
            with self.full_block_store.env.begin() as txn:
                stored_data = txn.get(block_key)

                if not stored_data:
                    print(f"[BlockStorage.verify_stored_block] ❌ ERROR: Block {block.index} not found in LMDB.")
                    return False

                try:
                    stored_json = stored_data.decode("utf-8")
                    stored_dict = json.loads(stored_json)
                    print(f"[BlockStorage.verify_stored_block] ✅ Block {block.index} verified: {stored_dict}")
                    return True
                except (UnicodeDecodeError, json.JSONDecodeError) as e:
                    print(f"[BlockStorage.verify_stored_block] ❌ ERROR: Failed to decode stored block {block.index}: {e}")
                    return False

        except Exception as e:
            print(f"[BlockStorage.verify_stored_block] ❌ ERROR: Failed to verify block {block.index}: {e}")
            return False




    def block_meta(self, block_hash: str = None, block: Block = None):
        """
        Retrieves or stores block metadata in `full_block_store.lmdb`.
        - Retrieves metadata for a given block hash.
        - Stores metadata for a given block.
        """
        try:
            # ✅ **Step 1: Retrieve Metadata if Block Hash is Provided**
            if block_hash:
                print(f"[BlockStorage.block_meta] INFO: Retrieving metadata for Block {block_hash}...")

                # ✅ **Ensure Block Hash is Valid**
                if not isinstance(block_hash, str) or len(block_hash) != Constants.SHA3_384_HASH_SIZE:
                    print(f"[BlockStorage.block_meta] ERROR: Invalid block hash format: {block_hash}")
                    return None

                # ✅ **Retrieve Metadata from `full_block_store`**
                with self.full_block_store.env.begin() as txn:
                    data = txn.get(f"metadata:block:{block_hash}".encode())

                if not data:
                    print(f"[BlockStorage.block_meta] WARNING: No metadata found for block hash: {block_hash}")
                    return None

                # ✅ **Deserialize and Validate Metadata**
                try:
                    metadata = json.loads(data.decode("utf-8"))
                    if not isinstance(metadata, dict):
                        print(f"[BlockStorage.block_meta] ERROR: Invalid metadata structure for block {block_hash}")
                        return None

                    print(f"[BlockStorage.block_meta] SUCCESS: Retrieved metadata for block {block_hash}.")
                    return metadata

                except json.JSONDecodeError as e:
                    print(f"[BlockStorage.block_meta] ERROR: Failed to decode metadata for block {block_hash}: {e}")
                    return None

            # ✅ **Step 2: Store Metadata if Block is Provided**
            if block:
                print(f"[BlockStorage.block_meta] INFO: Storing metadata for Block {block.hash}...")

                # ✅ **Ensure Block Hash is a Valid String**
                block_hash_str = block.hash.hex() if isinstance(block.hash, bytes) else block.hash

                # ✅ **Prepare Metadata for Storage**
                metadata = {
                    "index": block.index,
                    "previous_hash": block.previous_hash.hex() if isinstance(block.previous_hash, bytes) else block.previous_hash,
                    "timestamp": block.timestamp,
                    "difficulty": int(block.difficulty),  # ✅ Store difficulty as an integer
                    "miner_address": block.miner_address,
                }

                # ✅ **Store Metadata in `full_block_store.lmdb`**
                with self.full_block_store.env.begin(write=True) as txn:
                    txn.put(f"metadata:block:{block_hash_str}".encode(), json.dumps(metadata).encode())

                print(f"[BlockStorage.block_meta] INFO: Stored metadata for block {block_hash_str}: {metadata}")

                return metadata  # ✅ Return stored metadata

        except Exception as e:
            print(f"[BlockStorage.block_meta] ❌ ERROR: Unexpected error: {e}")
            return None

    def _convert_difficulty_to_int(self, difficulty) -> int:
        """
        Convert difficulty to an integer.
        - Handles bytes, hex strings, and integers.
        - Raises ValueError for invalid formats.
        """
        if isinstance(difficulty, int):
            return difficulty
        elif isinstance(difficulty, str):
            return int(difficulty, 16)  # ✅ Properly handle hex strings
        elif isinstance(difficulty, bytes):
            return int.from_bytes(difficulty, byteorder='big')
        else:
            raise ValueError(f"Invalid difficulty format: {difficulty}")

    def get_block_by_height(self, height: int) -> Optional[Block]:
        """
        Retrieve a block by height from LMDB.
        Ensures the data is properly decoded as UTF-8 JSON and validates the block structure.
        """
        try:
            print(f"[BlockStorage.get_block_by_height] INFO: Retrieving Block {height}...")

            # ✅ Generate the block key for LMDB
            block_key = f"block:{height}".encode("utf-8")

            # ✅ Retrieve block data from LMDB
            with self.full_block_store.env.begin() as txn:
                block_data = txn.get(block_key)

                if not block_data:
                    print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Block {height} not found in LMDB.")
                    return None

                # ✅ Decode the data as UTF-8 JSON
                try:
                    block_dict = json.loads(block_data.decode("utf-8"))
                except json.JSONDecodeError as e:
                    print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Failed to decode JSON for Block {height}: {e}")
                    return None

                # ✅ Deserialize the block from the dictionary
                block = Block.from_dict(block_dict)
                if not block:
                    print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Failed to deserialize Block {height}.")
                    return None

                # ✅ Validate the block structure
                if not self.validate_block_structure(block):
                    print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Block {height} has an invalid structure.")
                    return None

                print(f"[BlockStorage.get_block_by_height] ✅ SUCCESS: Retrieved Block {height}.")
                return block

        except Exception as e:
            print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Failed to retrieve Block {height}: {e}")
            return None
                
    def store_block(self, block: Block):
        """
        Stores a block in LMDB.
        - Ensures the block hash is correctly computed and stored.
        - Calls `_check_and_rollover_lmdb()` to prevent exceeding LMDB size limits.
        - Uses `full_block_chain/` directory for storage.
        - Ensures the latest block index is stored separately for quick retrieval.
        """
        try:
            print(f"[BlockStorage.store_block] INFO: Storing Block {block.index}...")

            # ✅ Ensure latest block file path is set
            self._set_latest_block_file()

            # ✅ Ensure SHA3-384 hash consistency
            calculated_hash = block.calculate_hash()

            # ✅ If block.hash is missing or incorrect, fix it before storing
            if not block.hash or block.hash != calculated_hash:
                print(f"[BlockStorage.store_block] ⚠️ WARNING: Hash mismatch for Block {block.index}. Fixing before storage.")
                block.hash = calculated_hash  # ✅ Assign correct hash

            # ✅ Check if block already exists in `full_block_store`
            block_key = f"block:{block.index}".encode("utf-8")
            block_hash_key = f"block_hash:{block.hash}".encode("utf-8")

            with self.full_block_store.env.begin() as txn:
                existing_block = txn.get(block_key)

            if existing_block:
                print(f"[BlockStorage.store_block] ⚠️ WARNING: Block {block.index} already exists. Skipping.")
                return

            # ✅ Serialize block using its to_dict method for consistent formatting
            block_data = block.to_dict()

            # ✅ Ensure correct JSON formatting before writing to LMDB
            try:
                block_json = json.dumps(block_data, separators=(',', ':'), ensure_ascii=False)
                block_bytes = block_json.encode("utf-8")
            except (TypeError, ValueError) as e:
                print(f"[BlockStorage.store_block] ❌ ERROR: Failed to serialize block {block.index} to JSON: {e}")
                raise

            # ✅ Store full block in `full_block_chain/` LMDB file
            with self.full_block_store.env.begin(write=True) as txn:
                txn.put(block_key, block_bytes)  # ✅ Store block data
                txn.put(block_hash_key, block_key)  # ✅ Store block hash for quick lookup
                txn.put(b"latest_block_index", str(block.index).encode("utf-8"))  # ✅ Store latest block index separately

            print(f"[BlockStorage.store_block] ✅ Block {block.index} stored successfully with hash: {block.hash}")

        except Exception as e:
            print(f"[BlockStorage.store_block] ❌ ERROR: Failed to store block {block.index}: {e}")
            raise



    def initialize_txindex(self):
        """
        Ensures the `txindex_db` is properly initialized.
        - If already initialized, it does nothing.
        - If missing, it logs an error and prevents reinitialization.
        """
        try:
            # ✅ **Ensure Shared Instance Is Used**
            if not self.txindex_db:
                print("[BlockStorage.initialize_txindex] ERROR: `txindex_db` is not set. Cannot initialize transaction index.")
                return

            # ✅ **Prevent Redundant Initialization**
            print("[BlockStorage.initialize_txindex] INFO: Using shared `txindex_db` instance.")

            with self.txindex_db.env.begin(write=True) as txn:
                txn.put(b"txindex_initialized", b"true")

            print("[BlockStorage.initialize_txindex] SUCCESS: Transaction index database verified.")

        except Exception as e:
            print(f"[BlockStorage.initialize_txindex] ERROR: Failed to initialize `txindex_db`: {e}")
            raise

    def _validate_and_extract_tx_id(self, tx) -> Optional[str]:
        """
        Validate transaction and extract TX ID with multiple format support.
        
        - Ensures TX ID is valid and properly formatted before storing.
        - Converts byte-based TX IDs to hex format.
        - Returns a properly formatted TX ID or None if invalid.
        """
        try:
            if isinstance(tx, dict):
                tx_id = tx.get('tx_id', '')
            elif hasattr(tx, 'tx_id'):
                tx_id = tx.tx_id
            else:
                return None

            # ✅ Convert bytes to hex if needed
            if isinstance(tx_id, bytes):
                return tx_id.hex()

            # ✅ Ensure TX ID is 96-character hex
            if isinstance(tx_id, str) and len(tx_id) == 96 and all(c in string.hexdigits for c in tx_id):
                return tx_id

            return None  # Invalid TX ID

        except Exception as e:
            print(f"[BlockStorage._validate_and_extract_tx_id] ❌ ERROR: Invalid TX ID: {e}")
            return None

    def _index_transaction(self, tx, block_hash: str):
        """
        Index transaction safely with validation.

        - Stores transactions in `txindex.lmdb`.
        - Validates required fields (TX ID, inputs, outputs).
        - Ensures TX ID is properly formatted before storing.
        """
        try:
            # ✅ Convert Transaction to Dictionary
            tx_data = tx.to_dict() if hasattr(tx, "to_dict") else tx
            if not isinstance(tx_data, dict):
                raise ValueError("Invalid transaction format")

            # ✅ Ensure Required Fields Exist
            required_fields = ["tx_id", "inputs", "outputs"]
            if not all(field in tx_data for field in required_fields):
                raise ValueError("Missing required transaction fields")

            # ✅ Convert TX ID to Hex if Needed
            tx_id = tx_data["tx_id"]
            if isinstance(tx_id, bytes):
                tx_id = tx_id.hex()
            if not isinstance(tx_id, str) or len(tx_id) != 96:
                raise ValueError("Invalid TX_ID format")

            # ✅ Store Transaction in `txindex.lmdb`
            with self.txindex_db.env.begin(write=True) as txn:
                txn.put(f"tx:{tx_id}".encode(), json.dumps({
                    "block_hash": block_hash,
                    "inputs": tx_data.get("inputs", []),
                    "outputs": tx_data.get("outputs", []),
                    "timestamp": tx_data.get("timestamp", int(time.time())),
                    "signatures": {
                        "tx": tx_data.get("tx_signature", "00" * 48)[:48],
                        "falcon": tx_data.get("falcon_signature", "00" * 48)[:48]
                    }
                }).encode())

            print(f"[BlockStorage._index_transaction] ✅ Indexed transaction {tx_id} in block {block_hash}.")

        except Exception as e:
            print(f"[BlockStorage._index_transaction] ❌ ERROR: Failed to index transaction {tx_id}: {e}")

    def _deserialize_block (self, block_data: str) -> Optional[Block]:
        """
        Deserialize block data from JSON format into a Block object.
        - Ensures valid JSON structure.
        - Parses transactions safely.
        - Returns None if deserialization fails.
        """
        try:
            print("[BlockStorage._deserialize_block_from_binary] INFO: Starting block deserialization...")

            # ✅ **Ensure block data is not empty**
            if not block_data:
                print("[BlockStorage._deserialize_block_from_binary] ❌ ERROR: Block data is empty.")
                return None

            # ✅ **Parse JSON Data**
            try:
                block_dict = json.loads(block_data)
            except json.JSONDecodeError as e:
                print(f"[BlockStorage._deserialize_block_from_binary] ❌ ERROR: Failed to parse block JSON: {e}")
                return None

            # ✅ **Ensure Required Fields Exist**
            required_keys = {
                "index", "previous_hash", "merkle_root", "difficulty",
                "nonce", "miner_address", "transaction_signature",
                "falcon_signature", "reward", "fees", "version", "transactions"
            }
            if not required_keys.issubset(block_dict.keys()):
                print(f"[BlockStorage._deserialize_block_from_binary] ❌ ERROR: Block data missing required fields: {required_keys - block_dict.keys()}")
                return None

            # ✅ **Parse Transactions Safely**
            transactions = []
            for i, tx in enumerate(block_dict.get("transactions", [])):
                if not isinstance(tx, dict) or "tx_id" not in tx:
                    print(f"[BlockStorage._deserialize_block_from_binary] ❌ ERROR: Transaction {i} missing 'tx_id'. Skipping.")
                    continue
                transactions.append(tx)

            # ✅ **Reconstruct Block Object**
            block = Block(
                index=block_dict["index"],
                previous_hash=block_dict["previous_hash"],
                merkle_root=block_dict["merkle_root"],
                difficulty=block_dict["difficulty"],
                nonce=block_dict["nonce"],
                miner_address=block_dict["miner_address"],
                transaction_signature=block_dict["transaction_signature"],
                falcon_signature=block_dict["falcon_signature"],
                reward=block_dict["reward"],
                fees=block_dict["fees"],
                version=block_dict["version"],
                transactions=transactions,
            )

            print(f"[BlockStorage._deserialize_block_from_binary] ✅ SUCCESS: Block {block.index} deserialized with {len(transactions)} transaction(s).")
            return block

        except Exception as e:
            print(f"[BlockStorage._deserialize_block_from_binary] ❌ ERROR: Failed to deserialize block: {e}")
            return None






    def get_block_by_height(self, height: int, include_headers: bool = False) -> Optional[Union[Block, Tuple[Block, List[Dict]]]]:
        """
        Retrieve a block by height and optionally fetch all block headers.

        Args:
            height (int): The height of the block to retrieve.
            include_headers (bool): If True, returns all block headers along with the block.

        Returns:
            - If `include_headers` is False: The block at the specified height (or None if not found).
            - If `include_headers` is True: A tuple containing the block and a list of all block headers.
        """
        try:
            print(f"[BlockStorage.get_block_by_height] INFO: Searching for block at height {height}...")

            # ✅ **Ensure LMDB Instance Exists**
            if not self.full_block_store:
                print("[BlockStorage.get_block_by_height] ❌ ERROR: `full_block_store` (full_block_chain.lmdb) is not set. Cannot retrieve block.")
                return None

            # ✅ **Retrieve Block by Height**
            with self.full_block_store.env.begin() as txn:
                block_data_bytes = txn.get(f"block:{height}".encode("utf-8"))

            if not block_data_bytes:
                print(f"[BlockStorage.get_block_by_height] ❌ ERROR: No block found at height {height} in LMDB.")
                return None

            # ✅ **Deserialize Block Data from JSON**
            try:
                block_dict = json.loads(block_data_bytes.decode("utf-8"))
            except json.JSONDecodeError:
                print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Failed to parse block data for height {height}.")
                return None

            # ✅ **Ensure Block Metadata Contains Required Fields**
            required_fields = {"index", "previous_hash", "merkle_root", "timestamp", "nonce", "difficulty", "hash"}
            if not required_fields.issubset(block_dict.keys()):
                print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Block {height} metadata is incomplete.")
                return None

            # ✅ **Validate Block Hash Format (SHA3-384)**
            block_hash = block_dict["hash"]
            if not isinstance(block_hash, str) or len(block_hash) != Constants.SHA3_384_HASH_SIZE:
                print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Block {height} has an invalid hash format.")
                return None

            # ✅ **Validate Merkle Root Format**
            merkle_root = block_dict["merkle_root"]
            if not isinstance(merkle_root, str) or len(merkle_root) != Constants.SHA3_384_HASH_SIZE:
                print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Block {height} has an invalid Merkle root.")
                return None

            print(f"[BlockStorage.get_block_by_height] ✅ SUCCESS: Block {height} retrieved and validated.")

            # ✅ **Convert Block Dictionary to Block Object**
            try:
                block = Block.from_dict(block_dict)
            except Exception as e:
                print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Failed to reconstruct block object: {e}")
                return None

            # ✅ **Optionally Fetch All Block Headers**
            if include_headers:
                headers = self._get_all_block_headers()
                return block, headers

            return block

        except Exception as e:
            print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Failed to retrieve block by height {height}: {e}")
            return None

    def _get_all_block_headers(self) -> List[Dict]:
        """
        Retrieve all block headers from `full_block_chain.lmdb`.

        Returns:
            List[Dict]: A list of block headers, where each header is a dictionary.
        """
        try:
            print("[BlockStorage._get_all_block_headers] INFO: Retrieving all block headers...")

            headers = []

            # ✅ **Retrieve All Block Headers from `full_block_chain.lmdb`**
            with self.full_block_store.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.startswith(b"block:"):
                        try:
                            block_meta = json.loads(value.decode("utf-8"))

                            # ✅ **Extract and Validate Block Header**
                            required_keys = {"index", "previous_hash", "timestamp", "nonce", "difficulty", "hash"}
                            if isinstance(block_meta, dict) and required_keys.issubset(block_meta.keys()):
                                headers.append({key: block_meta[key] for key in required_keys})
                            else:
                                print(f"[BlockStorage._get_all_block_headers] WARNING: Invalid header structure in block {block_meta.get('hash', 'unknown')}")

                        except json.JSONDecodeError as e:
                            print(f"[BlockStorage._get_all_block_headers] ERROR: Failed to parse block metadata: {e}")
                            continue

            if not headers:
                print("[BlockStorage._get_all_block_headers] WARNING: No block headers found in LMDB.")
                return []

            # ✅ **Sort Headers by Block Index for Ordered Retrieval**
            sorted_headers = sorted(headers, key=lambda h: h["index"])

            print(f"[BlockStorage._get_all_block_headers] INFO: Retrieved {len(sorted_headers)} block headers.")
            return sorted_headers

        except Exception as e:
            print(f"[BlockStorage._get_all_block_headers] ERROR: Failed to retrieve block headers: {e}")
            return []




    def validate_block_structure(self, block: Block) -> bool:
        """
        Validate that a block contains all required fields, has a valid hash, and contains properly formatted transactions.
        Also ensures metadata integrity and checks for version mismatches.

        - Validates against `full_block_chain.lmdb` instead of file-based metadata.
        - Uses `latest_block_index` for additional validation checks.
        """
        try:
            print(f"[BlockStorage.validate_block_structure] INFO: Validating structure for Block {block.index}...")

            # ✅ **Ensure LMDB Storage Is Used**
            if not self.full_block_store:
                print("[BlockStorage.validate_block_structure] ❌ ERROR: `full_block_store` is not set. Cannot validate block.")
                return False

            # ✅ **Required Block Fields**
            required_fields = {
                "index", "hash", "previous_hash", "merkle_root",
                "timestamp", "nonce", "difficulty", "miner_address",
                "transactions", "version"
            }

            # ✅ **Ensure Block Object is Valid**
            if not isinstance(block, Block):
                print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Invalid block type: {type(block)}")
                return False

            # ✅ **Check for Missing Fields**
            missing_fields = [field for field in required_fields if not hasattr(block, field)]
            if missing_fields:
                print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Block {block.index} is missing fields: {missing_fields}")
                return False

            # ✅ **Verify Block Hash Integrity**
            calculated_hash = block.calculate_hash()
            if block.hash != calculated_hash:
                print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Block {block.index} has an invalid hash.\n"
                    f"Expected: {calculated_hash}\n"
                    f"Found: {block.hash}")
                return False

            # ✅ **Retrieve Latest Block Index for Additional Validation**
            with self.full_block_store.env.begin() as txn:
                latest_block_index_bytes = txn.get(b"latest_block_index")

            if latest_block_index_bytes:
                latest_block_index = int(latest_block_index_bytes.decode("utf-8"))
                if block.index > latest_block_index + 1:
                    print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Block {block.index} is ahead of the expected chain index {latest_block_index + 1}.")
                    return False

            # ✅ **Ensure Block Exists in LMDB**
            with self.full_block_store.env.begin() as txn:
                stored_block = txn.get(f"block:{block.index}".encode())

            if not stored_block:
                print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Block {block.index} not found in LMDB.")
                return False

            # ✅ **Validate Transactions Structure**
            if not isinstance(block.transactions, list) or not all(isinstance(tx, dict) for tx in block.transactions):
                print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Block {block.index} contains invalid transactions.")
                return False

            # ✅ **Validate Metadata Structure**
            if hasattr(block, "metadata") and block.metadata:
                if not isinstance(block.metadata, dict):
                    print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Metadata in Block {block.index} is not a valid dictionary.")
                    return False

                required_metadata_keys = {"name", "version", "created_by", "creation_date"}
                missing_metadata = [key for key in required_metadata_keys if key not in block.metadata]

                if missing_metadata:
                    print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Metadata in Block {block.index} is missing fields: {missing_metadata}")
                    return False

            # ✅ **Check Version Compatibility**
            if block.version != Constants.VERSION:
                print(f"[BlockStorage.validate_block_structure] ⚠️ WARNING: Block {block.index} version mismatch.\n"
                    f"Expected: {Constants.VERSION}, Found: {block.version}")

            print(f"[BlockStorage.validate_block_structure] ✅ SUCCESS: Block {block.index} passed structure validation.")
            return True

        except Exception as e:
            print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Block structure validation failed for Block {block.index}: {e}")
            return False


    def load_chain(self) -> List[Dict]:
        """
        Load all blocks from `full_block_chain.lmdb` and return as a list of dictionaries.

        - Fetches full blocks instead of just metadata.
        - Ensures blocks are retrieved in correct order.
        - Uses `latest_block_index` for efficient retrieval.
        """
        try:
            print("[BlockStorage.load_chain] INFO: Loading full blockchain from LMDB...")

            # ✅ **Ensure LMDB Storage Is Used**
            if not self.full_block_store:
                print("[BlockStorage.load_chain] ❌ ERROR: `full_block_store` is not set. Cannot load blockchain data.")
                return []

            chain_data = []

            # ✅ **Retrieve Latest Block Index for Faster Retrieval**
            with self.full_block_store.env.begin() as txn:
                latest_block_index_bytes = txn.get(b"latest_block_index")

            if not latest_block_index_bytes:
                print("[BlockStorage.load_chain] WARNING: No latest block index found. Blockchain may be empty.")
                return []

            latest_block_index = int(latest_block_index_bytes.decode("utf-8"))

            # ✅ **Retrieve Blocks from LMDB Using Index**
            with self.full_block_store.env.begin() as txn:
                for block_index in range(latest_block_index + 1):
                    block_key = f"block:{block_index}".encode()
                    block_data_bytes = txn.get(block_key)

                    if not block_data_bytes:
                        print(f"[BlockStorage.load_chain] WARNING: Block {block_index} not found in LMDB.")
                        continue

                    try:
                        block_data = json.loads(block_data_bytes.decode("utf-8"))
                        if "index" not in block_data:
                            print(f"[BlockStorage.load_chain] ERROR: Block {block_index} metadata missing 'index'. Skipping.")
                            continue
                        chain_data.append(block_data)
                    except json.JSONDecodeError as e:
                        print(f"[BlockStorage.load_chain] ERROR: Failed to parse block metadata for block {block_index}: {e}")
                        continue

            # ✅ **Sort Blocks by Height to Ensure Correct Chain Order**
            sorted_chain = sorted(chain_data, key=lambda b: b["index"])

            if not sorted_chain:
                print("[BlockStorage.load_chain] WARNING: No blocks found in LMDB. Chain may be empty.")
                return []

            print(f"[BlockStorage.load_chain] ✅ SUCCESS: Loaded {len(sorted_chain)} blocks from LMDB.")
            return sorted_chain

        except Exception as e:
            print(f"[BlockStorage.load_chain] ❌ ERROR: Failed to load blockchain: {e}")
            return []


    def get_all_blocks(self) -> List[Dict]:
        """
        Retrieve all stored blocks from `full_block_chain.lmdb` as a list of dictionaries.
        - Ensures metadata validation.
        - Checks for chain continuity.
        - Handles errors gracefully.
        """
        try:
            print("[BlockStorage.get_all_blocks] INFO: Retrieving all blocks from LMDB...")

            if not self.full_block_store:
                print("[BlockStorage.get_all_blocks] ERROR: `full_block_store` is not set. Cannot retrieve blocks.")
                return []

            blocks = []

            # ✅ Retrieve Blocks from LMDB
            with self.full_block_store.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.startswith(b"block:") and not key.startswith(b"block_hash:"):
                        try:
                            block_metadata = json.loads(value.decode("utf-8"))

                            # ✅ Ensure Block Metadata Contains Required Fields
                            required_fields = {"index", "previous_hash", "merkle_root", "timestamp", "nonce", "difficulty", "hash"}
                            if not isinstance(block_metadata, dict) or not required_fields.issubset(block_metadata.keys()):
                                print(f"[BlockStorage.get_all_blocks] ERROR: Invalid block metadata structure: {block_metadata}")
                                continue

                            blocks.append(block_metadata)

                        except json.JSONDecodeError as e:
                            print(f"[BlockStorage.get_all_blocks] ERROR: Failed to parse block metadata: {e}")
                            continue

            if not blocks:
                print("[BlockStorage.get_all_blocks] WARNING: No blocks found in LMDB.")

            print(f"[BlockStorage.get_all_blocks] ✅ SUCCESS: Retrieved {len(blocks)} valid blocks.")
            return blocks

        except Exception as e:
            print(f"[BlockStorage.get_all_blocks] ❌ ERROR: Failed to retrieve blocks: {e}")
            return []






    def get_latest_block(self) -> Optional[Block]:
        """
        Retrieve the latest block from `full_block_chain.lmdb`.
        - Ensures proper validation of block metadata.
        - Handles errors gracefully.
        - Uses a dedicated `latest_block_index` key for quick lookup.
        """
        try:
            print("[BlockStorage.get_latest_block] INFO: Retrieving latest block from LMDB...")

            # ✅ Ensure LMDB instances exist
            if not self.full_block_store or not self.block_metadata_db:
                print("[BlockStorage.get_latest_block] ERROR: LMDB instances not set. Cannot retrieve latest block.")
                return None

            # ✅ Retrieve latest block index for lookup
            with self.full_block_store.env.begin() as txn:
                latest_block_index_bytes = txn.get(b"latest_block_index")

            if not latest_block_index_bytes:
                print("[BlockStorage.get_latest_block] WARNING: No latest block index found. Blockchain may be empty.")
                return None

            latest_block_index = int(latest_block_index_bytes.decode("utf-8"))

            # ✅ Retrieve block metadata using index
            block_key = f"block:{latest_block_index}".encode()
            with self.full_block_store.env.begin() as txn:
                block_metadata_bytes = txn.get(block_key)

            if not block_metadata_bytes:
                print(f"[BlockStorage.get_latest_block] ERROR: Block {latest_block_index} metadata not found in LMDB.")
                return None

            try:
                latest_block_metadata = json.loads(block_metadata_bytes.decode("utf-8"))
            except json.JSONDecodeError:
                print(f"[BlockStorage.get_latest_block] ERROR: Corrupted block metadata for index {latest_block_index}.")
                return None

            # ✅ Ensure block metadata contains required fields
            required_keys = {"index", "previous_hash", "timestamp", "nonce", "difficulty", "hash"}
            if not required_keys.issubset(latest_block_metadata.keys()):
                print(f"[BlockStorage.get_latest_block] ERROR: Block metadata missing required fields: {latest_block_metadata}")
                return None

            # ✅ Retrieve block hash
            block_hash = latest_block_metadata.get("hash")
            if not block_hash or len(block_hash) != 96:
                print(f"[BlockStorage.get_latest_block] ERROR: Invalid block hash in metadata for index {latest_block_index}.")
                return None

            # ✅ Retrieve full block data using hash
            with self.full_block_store.env.begin() as txn:
                block_data_bytes = txn.get(f"block_hash:{block_hash}".encode())

            if not block_data_bytes:
                print(f"[BlockStorage.get_latest_block] ERROR: Block {block_hash} data not found in LMDB.")
                return None

            # ✅ Ensure block data is valid
            block_data_str = block_data_bytes.decode("utf-8").strip()
            if not block_data_str:
                print(f"[BlockStorage.get_latest_block] ERROR: Block {block_hash} contains empty data in LMDB.")
                return None

            # ✅ Deserialize block from LMDB
            try:
                full_block = Block.from_dict(json.loads(block_data_str))
                print(f"[BlockStorage.get_latest_block] ✅ SUCCESS: Retrieved Block {full_block.index} (Hash: {full_block.hash}).")
                return full_block

            except json.JSONDecodeError as e:
                print(f"[BlockStorage.get_latest_block] ERROR: Failed to deserialize latest block: {e}")
                return None

        except Exception as e:
            print(f"[BlockStorage.get_latest_block] ERROR: Failed to retrieve latest block: {e}")
            return None



    def get_total_mined_supply(self) -> Decimal:
        """
        Retrieve and update the total mined coin supply by summing all Coinbase rewards from stored blocks.
        - Uses a cached value for performance but updates it dynamically after each mined block.
        - Ensures the total supply is always valid (returns `Decimal(0)` instead of `None`).
        """
        try:
            print("[BlockStorage.get_total_mined_supply] INFO: Retrieving total mined supply...")

            # ✅ **Check Cached Supply in LMDB**
            with self.block_metadata_db.env.begin() as txn:
                cached_supply = txn.get(b"total_mined_supply")

            if cached_supply:
                try:
                    total_supply = Decimal(cached_supply.decode("utf-8"))
                    print(f"[BlockStorage.get_total_mined_supply] INFO: Cached total mined supply retrieved: {total_supply} ZYC")
                    return total_supply
                except (UnicodeDecodeError, ValueError) as decode_error:
                    print(f"[BlockStorage.get_total_mined_supply] WARNING: Failed to decode cached total supply: {decode_error}")

            # ✅ **Initialize Total Supply Counter**
            total_supply = Decimal("0")
            blocks_found = False

            # ✅ **Iterate Through Stored Blocks**
            with self.full_block_store.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.startswith(b"block:"):
                        try:
                            block_metadata = json.loads(value.decode("utf-8"))

                            # ✅ **Ensure Block Metadata is Valid**
                            if not isinstance(block_metadata, dict):
                                print(f"[BlockStorage.get_total_mined_supply] ERROR: Skipping invalid block metadata: {block_metadata}")
                                continue

                            # ✅ **Check for `header` Format & Handle Legacy Blocks**
                            header = block_metadata.get("header", block_metadata)
                            if not isinstance(header, dict) or "index" not in header:
                                print(f"[BlockStorage.get_total_mined_supply] ERROR: Block metadata missing 'header' or 'index'. Skipping...")
                                continue

                            block_index = header["index"]
                            print(f"[BlockStorage.get_total_mined_supply] INFO: Processing Block {block_index}...")

                            # ✅ **Process Coinbase Transactions for Mining Rewards**
                            transactions = block_metadata.get("transactions", [])
                            if not transactions:
                                print(f"[BlockStorage.get_total_mined_supply] WARNING: Block {block_index} has no transactions.")
                                continue

                            blocks_found = True
                            for tx in transactions:
                                if tx.get("type") == "COINBASE":
                                    outputs = tx.get("outputs", [])
                                    if outputs and isinstance(outputs, list):
                                        for output in outputs:
                                            if "amount" in output:
                                                try:
                                                    reward_amount = Decimal(str(output["amount"]))
                                                    total_supply += reward_amount
                                                except (ValueError, TypeError) as e:
                                                    print(f"[BlockStorage.get_total_mined_supply] ERROR: Invalid reward amount in Block {block_index}: {e}")

                        except json.JSONDecodeError as e:
                            print(f"[BlockStorage.get_total_mined_supply] ERROR: Failed to parse block metadata: {e}")
                            continue

            # ✅ **Ensure We Don't Return None**
            if not blocks_found:
                print("[BlockStorage.get_total_mined_supply] WARNING: No blocks found in storage. Returning 0.")
                return Decimal(0)  # ✅ Ensure it always returns a valid value

            # ✅ **Cache the Total Mined Supply for Faster Access**
            with self.block_metadata_db.env.begin(write=True) as txn:
                txn.put(b"total_mined_supply", str(total_supply).encode("utf-8"))

            print(f"[BlockStorage.get_total_mined_supply] ✅ SUCCESS: Total mined supply calculated & cached: {total_supply} ZYC")
            return total_supply

        except Exception as e:
            print(f"[BlockStorage.get_total_mined_supply] ERROR: Failed to calculate total mined supply: {e}")
            return Decimal(0)  # ✅ Fallback to 0 instead of None


    def get_block_by_tx_id(self, tx_id: str) -> Optional[Block]:
        """
        Retrieve a block using a transaction ID from the `txindex.lmdb` database.
        - Uses shared LMDB instances for efficient retrieval.
        - Ensures proper validation of block metadata and transaction ID.

        :param tx_id: Transaction ID to look up.
        :return: The block containing the transaction, or None if not found.
        """
        try:
            print(f"[BlockStorage.get_block_by_tx_id] INFO: Searching for block containing transaction {tx_id}...")

            # ✅ **Ensure Shared LMDB Instances Are Used**
            if not self.txindex_db or not self.block_metadata_db or not self.full_block_store:
                print("[BlockStorage.get_block_by_tx_id] ERROR: LMDB instances are not set. Cannot retrieve block.")
                return None

            # ✅ **Retrieve Block Hash Associated with Transaction ID**
            with self.txindex_db.env.begin() as txn:
                block_hash_bytes = txn.get(f"tx:{tx_id}".encode("utf-8"))

            if not block_hash_bytes:
                print(f"[BlockStorage.get_block_by_tx_id] WARNING: No block found for transaction {tx_id}.")
                return None

            block_hash = block_hash_bytes.decode("utf-8")
            print(f"[BlockStorage.get_block_by_tx_id] INFO: Transaction {tx_id} found in block {block_hash}.")

            # ✅ **Retrieve Block Metadata Using Shared `block_metadata_db`**
            with self.block_metadata_db.env.begin() as txn:
                block_metadata_bytes = txn.get(f"block:{block_hash}".encode("utf-8"))

            if not block_metadata_bytes:
                print(f"[BlockStorage.get_block_by_tx_id] WARNING: Block metadata missing for hash {block_hash}.")
                return None

            try:
                block_metadata = json.loads(block_metadata_bytes.decode("utf-8"))
            except json.JSONDecodeError:
                print(f"[BlockStorage.get_block_by_tx_id] ERROR: Failed to decode block metadata for hash {block_hash}.")
                return None

            # ✅ **Ensure Block Metadata Contains Required Fields**
            required_keys = {"index", "previous_hash", "merkle_root", "timestamp", "nonce", "difficulty", "hash"}
            block_header = block_metadata.get("block_header", {})

            if not isinstance(block_header, dict) or not required_keys.issubset(block_header.keys()):
                print(f"[BlockStorage.get_block_by_tx_id] ERROR: Block metadata missing required fields: {block_header}")
                return None

            # ✅ **Retrieve Full Block Data from `full_block_chain.lmdb`**
            with self.full_block_store.env.begin() as txn:
                block_data_bytes = txn.get(f"block:{block_hash}".encode("utf-8"))

            if not block_data_bytes:
                print(f"[BlockStorage.get_block_by_tx_id] ERROR: Block {block_hash} not found in full block storage (full_block_chain.lmdb).")
                return None

            # ✅ **Deserialize Block from LMDB**
            block = Block.from_dict(json.loads(block_data_bytes.decode("utf-8")))
            print(f"[BlockStorage.get_block_by_tx_id] ✅ SUCCESS: Retrieved Block {block.index} containing transaction {tx_id}.")
            return block

        except Exception as e:
            print(f"[BlockStorage.get_block_by_tx_id] ❌ ERROR: Failed to retrieve block by transaction ID {tx_id}: {e}")
            return None

    def get_transaction_id(self, tx_label: str) -> Optional[str]:
        """
        Retrieves a stored transaction ID using a label (e.g., "GENESIS_COINBASE").
        - Uses shared LMDB instances for efficient retrieval.
        - Ensures proper validation of the transaction ID.

        :param tx_label: A string label for the transaction to retrieve.
        :return: The stored transaction ID as a hex string, or None if not found.
        """
        try:
            print(f"[BlockStorage.get_transaction_id] INFO: Retrieving transaction ID for label '{tx_label}'...")

            # ✅ **Ensure Shared LMDB Instance Is Used**
            if not self.txindex_db:
                print("[BlockStorage.get_transaction_id] ERROR: `txindex_db` is not set. Cannot retrieve transaction ID.")
                return None

            # ✅ **Retrieve Transaction ID Using `txindex.lmdb`**
            with self.txindex_db.env.begin() as txn:
                tx_id_bytes = txn.get(f"label:{tx_label}".encode("utf-8"))

            if not tx_id_bytes:
                print(f"[BlockStorage.get_transaction_id] WARNING: No transaction ID found for label '{tx_label}'.")
                return None

            tx_id = tx_id_bytes.decode("utf-8")

            # ✅ **Ensure Transaction ID is Valid**
            if not isinstance(tx_id, str) or len(tx_id) != Constants.SHA3_384_HASH_SIZE:
                print(f"[BlockStorage.get_transaction_id] ERROR: Invalid transaction ID format retrieved for '{tx_label}': {tx_id}")
                return None

            print(f"[BlockStorage.get_transaction_id] ✅ SUCCESS: Retrieved transaction ID: {tx_id}")
            return tx_id

        except Exception as e:
            print(f"[BlockStorage.get_transaction_id] ERROR: Failed to retrieve transaction ID for '{tx_label}': {e}")
            return None