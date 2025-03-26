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
from Zyiron_Chain.utils.diff_conversion import DifficultyConverter

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



    def __init__(self, tx_storage: TxStorage, key_manager: KeyManager, utxo_storage=None):
        """
        Initializes BlockStorage:
        - Uses shared LMDB instances for block metadata, transaction index, and full block storage.
        - Manages transaction storage, UTXO storage, and key manager references.
        - Ensures thread safety with locks.
        - Initializes LMDB file rollover handling.
        """
        try:
            print("[BlockStorage.__init__] INFO: Initializing BlockStorage with LMDB full block storage...")

            # ✅ Validate required dependencies
            if not tx_storage:
                raise ValueError("[BlockStorage.__init__] ❌ ERROR: `tx_storage` instance is required.")
            if not key_manager:
                raise ValueError("[BlockStorage.__init__] ❌ ERROR: `key_manager` instance is required.")

            # ✅ Store core dependencies
            self.tx_storage = tx_storage
            self.key_manager = key_manager
            self.utxo_storage = utxo_storage  # ✅ Inject UTXO storage if provided
            self.write_lock = Lock()

            # ✅ Step 1: Initialize LMDB Databases
            self.block_metadata_db = LMDBManager(Constants.DATABASES["block_metadata"])
            self.txindex_db = LMDBManager(Constants.DATABASES["txindex"])

            # ✅ Step 2: Ensure `full_block_chain/` Directory Exists
            self.blockchain_dir = os.path.join(Constants.BLOCKCHAIN_STORAGE_PATH, "full_block_chain")
            os.makedirs(self.blockchain_dir, exist_ok=True)

            # ✅ Step 3: Determine the Latest LMDB File in `full_block_chain/`
            lmdb_files = sorted([
                f.split(".")[0] for f in os.listdir(self.blockchain_dir)
                if f.endswith(".lmdb") and f.split(".")[0].isdigit()
            ])

            if lmdb_files:
                latest_file_number = int(lmdb_files[-1])
                latest_lmdb = os.path.join(self.blockchain_dir, f"{latest_file_number:04}.lmdb")
            else:
                latest_lmdb = os.path.join(self.blockchain_dir, "0001.lmdb")

            # ✅ Step 4: Initialize LMDB Storage with the latest or new block file
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
        - If `block_hash` is provided: retrieves the metadata.
        - If `block` is provided: stores the metadata.
        """
        try:
            # ✅ Step 1: Retrieve Metadata
            if block_hash:
                print(f"[BlockStorage.block_meta] INFO: Retrieving metadata for Block {block_hash}...")

                if not isinstance(block_hash, str) or len(block_hash) != Constants.SHA3_384_HASH_SIZE:
                    print(f"[BlockStorage.block_meta] ❌ ERROR: Invalid block hash length or type: {block_hash}")
                    return None

                with self.full_block_store.env.begin() as txn:
                    raw_data = txn.get(f"metadata:block:{block_hash}".encode())

                if not raw_data:
                    print(f"[BlockStorage.block_meta] ⚠️ WARNING: No metadata found for block hash: {block_hash}")
                    return None

                try:
                    metadata = json.loads(raw_data.decode("utf-8"))
                    if not isinstance(metadata, dict):
                        print(f"[BlockStorage.block_meta] ❌ ERROR: Decoded metadata is not a dictionary.")
                        return None

                    print(f"[BlockStorage.block_meta] ✅ SUCCESS: Retrieved metadata for Block {block_hash}")
                    return metadata

                except json.JSONDecodeError as e:
                    print(f"[BlockStorage.block_meta] ❌ ERROR: Failed to decode metadata JSON: {e}")
                    return None

            # ✅ Step 2: Store Metadata
            if block:
                block_hash_str = block.hash.hex() if isinstance(block.hash, bytes) else str(block.hash)
                previous_hash_str = block.previous_hash.hex() if isinstance(block.previous_hash, bytes) else str(block.previous_hash)

                print(f"[BlockStorage.block_meta] INFO: Storing metadata for Block {block_hash_str}...")

                metadata = {
                    "index": block.index,
                    "previous_hash": previous_hash_str,
                    "timestamp": block.timestamp,
                    "difficulty": int(block.difficulty) if isinstance(block.difficulty, int) else DifficultyConverter.from_hex(block.difficulty),
                    "miner_address": block.miner_address
                }

                with self.full_block_store.env.begin(write=True) as txn:
                    txn.put(f"metadata:block:{block_hash_str}".encode(), json.dumps(metadata).encode("utf-8"))

                print(f"[BlockStorage.block_meta] ✅ SUCCESS: Metadata stored for Block {block_hash_str}")
                return metadata

            print("[BlockStorage.block_meta] ⚠️ WARNING: No block or block_hash provided.")
            return None

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
        Retrieve a block by height from LMDB with robust fallback mechanisms.
        - Ensures the data is properly decoded as UTF-8 JSON.
        - Validates the block structure.
        - Handles missing or corrupted data gracefully.
        - Enforces Genesis block integrity if height == 0.
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

                # ✅ Fallback for missing or invalid block data
                if not isinstance(block_dict, dict):
                    print(f"[BlockStorage.get_block_by_height] ⚠️ WARNING: Block {height} data is invalid. Attempting to repair...")
                    block_dict = {"header": {}, "transactions": []}  # Fallback to empty block

                # ✅ Deserialize the block from the dictionary
                block = Block.from_dict(block_dict)
                if not block:
                    print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Failed to deserialize Block {height}.")
                    return None

                # ✅ **GENESIS BLOCK SPECIFIC CHECKS**
                if height == 0:
                    print("[BlockStorage.get_block_by_height] INFO: Validating Genesis Block integrity...")

                    # **Ensure Genesis block has correct previous_hash**
                    if block.previous_hash != Constants.ZERO_HASH:
                        print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Genesis Block previous_hash mismatch! Expected: {Constants.ZERO_HASH}, Found: {block.previous_hash}")
                        return None

                    # **Ensure Genesis block index is 0**
                    if block.index != 0:
                        print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Genesis Block index mismatch! Expected: 0, Found: {block.index}")
                        return None

                    # **Ensure stored mined hash matches the expected hash**
                    if block.mined_hash != block_dict.get("hash"):
                        print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Genesis Block hash mismatch! Expected: {block_dict.get('hash')}, Found: {block.mined_hash}")
                        return None

                    print("[BlockStorage.get_block_by_height] ✅ SUCCESS: Genesis Block integrity verified.")

                # ✅ **Validate the block structure**
                if not self.validate_block_structure(block):
                    print(f"[BlockStorage.get_block_by_height] ⚠️ WARNING: Block {height} has an invalid structure. Attempting to repair...")

                    # **Check if mined_hash exists before using fallback**
                    stored_hash = block_dict.get("hash", None)
                    if stored_hash and isinstance(stored_hash, str):
                        block.hash = stored_hash  # ✅ Use stored mined hash
                    else:
                        print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Block {height} missing valid stored hash! Cannot repair.")
                        return None

                    if not self.validate_block_structure(block):
                        print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Block {height} cannot be repaired.")
                        return None

                # ✅ **Ensure the previous block hash is valid**
                if height > 0:
                    prev_block = self.get_block_by_height(height - 1)
                    if not prev_block:
                        print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Previous Block {height - 1} not found! Cannot validate chain consistency.")
                        return None

                    if prev_block.mined_hash != block.previous_hash:
                        print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Block {height} previous_hash does not match previous block's mined hash!")
                        print(f"Expected: {prev_block.mined_hash}, Found: {block.previous_hash}")
                        return None

                print(f"[BlockStorage.get_block_by_height] ✅ SUCCESS: Retrieved Block {height}.")
                return block

        except Exception as e:
            print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Failed to retrieve Block {height}: {e}")
            return None








    def get_block_by_hash(self, block_hash: str) -> Optional[dict]:
        """
        Retrieve a full block dictionary using its hash.

        Args:
            block_hash (str): The hash of the block (hexadecimal).

        Returns:
            Optional[dict]: The block dictionary if found, or None.
        """
        try:
            print(f"[BlockStorage.get_block_by_hash] 🔍 Looking up block hash: {block_hash}")

            # Convert to proper key for LMDB
            key = f"block_hash:{block_hash}".encode()
            metadata_bytes = self.block_metadata_db.get(key)

            if not metadata_bytes:
                print(f"[BlockStorage.get_block_by_hash] ❌ ERROR: No metadata found for block hash {block_hash}.")
                return None

            # Load metadata to get height or offset
            try:
                metadata = json.loads(metadata_bytes.decode())
            except Exception as decode_error:
                print(f"[BlockStorage.get_block_by_hash] ❌ ERROR: Failed to decode metadata: {decode_error}")
                return None

            height = metadata.get("height")
            if height is None:
                print(f"[BlockStorage.get_block_by_hash] ❌ ERROR: Metadata missing block height for hash {block_hash}.")
                return None

            # Retrieve full block from height
            block_data = self.get_block_by_height(height)
            if not block_data:
                print(f"[BlockStorage.get_block_by_hash] ❌ ERROR: Block at height {height} could not be loaded.")
                return None

            print(f"[BlockStorage.get_block_by_hash] ✅ SUCCESS: Block {height} loaded using hash.")
            return block_data

        except Exception as e:
            print(f"[BlockStorage.get_block_by_hash] ❌ ERROR: Unexpected failure during block hash lookup: {e}")
            return None


    def store_block(self, block: Block) -> bool:
        """
        Store a block in the blockchain with robust fallback logic, transaction serialization,
        and total supply cache invalidation. Ensures UTXO updates are synchronized with block storage.
        Also attempts to store metadata and recovers it from full block store if metadata fails.
        """
        try:
            print(f"[BlockStorage.store_block] INFO: Storing Block {block.index}...")
            self._set_latest_block_file()

            if not block.mined_hash:
                print(f"[BlockStorage.store_block] ❌ ERROR: Mined hash missing for Block {block.index}. Cannot store an unverified block!")
                return False

            if not block.hash or block.hash != block.mined_hash:
                print(f"[BlockStorage.store_block] ⚠️ WARNING: Hash mismatch for Block {block.index}. Using mined hash instead.")
                block.hash = block.mined_hash

            if block.index == 0:
                block.previous_hash = Constants.ZERO_HASH
            else:
                prev_block = self.get_block_by_height(block.index - 1)
                if prev_block and prev_block.mined_hash != block.previous_hash:
                    print(f"[BlockStorage.store_block] ❌ ERROR: Block {block.index} previous_hash mismatch.")
                    print(f"Expected: {prev_block.mined_hash}, Found: {block.previous_hash}")
                    return False

            if not hasattr(block, "metadata") or not isinstance(block.metadata, dict):
                block.metadata = {}
                print(f"[BlockStorage.store_block] INFO: Added fallback metadata for Block {block.index}")

            # 🔄 Prepare block data
            try:
                block_data = block.to_dict()
                diff_int = int(block.difficulty, 16) if isinstance(block.difficulty, str) else int(block.difficulty)
                block_data["difficulty"] = DifficultyConverter.to_hex(diff_int)
                block_data["hash"] = block.mined_hash
                block_data["size"] = len(json.dumps(block_data, separators=(',', ':')).encode("utf-8"))
                print(f"[BlockStorage.store_block] INFO: Block size: {block_data['size']} bytes.")
            except Exception as e:
                print(f"[BlockStorage.store_block] ❌ ERROR: Failed block serialization: {e}")
                block_data = {}
                block_data["size"] = 0

            # 🔁 Ensure block_height is attached to all txs
            for tx in block_data.get("transactions", []):
                if isinstance(tx, dict) and tx.get("tx_id"):
                    if "block_height" not in tx or tx["block_height"] != block.index:
                        tx["block_height"] = block.index

            # 🔒 Encode for LMDB
            try:
                block_json = json.dumps(block_data, separators=(',', ':'), ensure_ascii=False)
                block_bytes = block_json.encode("utf-8")
            except Exception as e:
                print(f"[BlockStorage.store_block] ❌ ERROR: Failed to encode block JSON: {e}")
                return False

            block_key = f"block:{block.index}".encode("utf-8")
            block_hash_key = f"block_hash:{block.mined_hash}".encode("utf-8")

            # ❗Prevent overwrite (now returns True if already exists)
            with self.full_block_store.env.begin() as txn:
                if txn.get(block_key):
                    print(f"[BlockStorage.store_block] ⚠️ Block {block.index} already exists. Skipping.")
                    return True  # ✅ CHANGED: Now returns True instead of False

            # 🧾 Index transactions BEFORE UTXO update
            for tx in block.transactions:
                try:
                    if isinstance(tx, dict):
                        from Zyiron_Chain.transactions.coinbase import CoinbaseTx
                        from Zyiron_Chain.transactions.tx import Transaction
                        tx = CoinbaseTx.from_dict(tx) if tx.get("type") == "COINBASE" else Transaction.from_dict(tx)

                    tx_dict = tx.to_dict()
                    self.tx_storage.store_transaction(
                        tx_id=tx_dict.get("tx_id"),
                        block_hash=block.mined_hash,
                        tx_data=tx_dict,
                        outputs=tx_dict.get("outputs", []),
                        timestamp=block.timestamp,
                        tx_signature=getattr(tx, "tx_signature", b""),
                        falcon_signature=getattr(tx, "falcon_signature", b"")
                    )
                    print(f"[BlockStorage.store_block] ✅ Indexed transaction {tx_dict.get('tx_id')}.")
                except Exception as tx_err:
                    print(f"[BlockStorage.store_block] ⚠️ TX indexing failed: {tx_err}")
                    continue

            # 💾 Store full block
            try:
                with self.full_block_store.env.begin(write=True) as txn:
                    txn.put(block_key, block_bytes)
                    txn.put(block_hash_key, block_key)
                    txn.put(b"latest_block_index", str(block.index).encode("utf-8"))

                if self.utxo_storage:
                    if not self.utxo_storage.update_utxos(block):
                        print(f"[BlockStorage.store_block] ❌ ERROR: Failed to update UTXOs for Block {block.index}.")
                        return False
                else:
                    print(f"[BlockStorage.store_block] ⚠️ WARNING: UTXOStorage not attached. Skipping UTXO update.")
            except Exception as e:
                print(f"[BlockStorage.store_block] ❌ ERROR: Failed to store block or update UTXOs: {e}")
                return False

            # 🧠 Store block metadata
            if not self.store_block_metadata(block):
                print(f"[BlockStorage.store_block] ⚠️ WARNING: Failed to store metadata for Block {block.index}.")
                print("[BlockStorage.store_block] 🔁 Attempting fallback to rebuild metadata from full block store...")
                try:
                    fallback_block = self.get_block_by_height(block.index)
                    if fallback_block and self.store_block_metadata(fallback_block):
                        print(f"[BlockStorage.store_block] ✅ Fallback: Metadata restored for Block {block.index}")
                    else:
                        print(f"[BlockStorage.store_block] ❌ Fallback failed: Metadata not restored for Block {block.index}")
                except Exception as rebuild_e:
                    print(f"[BlockStorage.store_block] ❌ Fallback exception during metadata restore: {rebuild_e}")

            # 🔁 Invalidate supply cache
            with self.block_metadata_db.env.begin(write=True) as txn:
                txn.delete(b"total_mined_supply")

            print(f"[BlockStorage.store_block] ✅ SUCCESS: Block {block.index} stored with hash {block.hash}")
            return True

        except Exception as e:
            print(f"[BlockStorage.store_block] ❌ ERROR: Block store exception: {e}")
            return False


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
        Retrieve a block by height, prioritizing metadata and falling back to full block store if needed.

        Args:
            height (int): The height of the block to retrieve.
            include_headers (bool): If True, returns all block headers along with the block.

        Returns:
            - Block object or (Block, Headers) if found.
            - None if not found in either store.
        """
        try:
            print(f"[BlockStorage.get_block_by_height] 🔍 INFO: Attempting to retrieve block at height {height}...")

            block = None
            found_source = None

            # Step 1: Try metadata LMDB first
            if self.block_metadata_db:
                try:
                    with self.block_metadata_db.env.begin() as txn:
                        meta_key = f"block_meta:{height}".encode("utf-8")
                        metadata_bytes = txn.get(meta_key)

                    if metadata_bytes:
                        try:
                            block_dict = json.loads(metadata_bytes.decode("utf-8"))
                            block = Block.from_dict(block_dict)
                            found_source = "block metadata"
                            print(f"[BlockStorage.get_block_by_height] ✅ SUCCESS: Block {height} loaded from metadata.")
                        except Exception as parse_err:
                            print(f"[BlockStorage.get_block_by_height] ⚠️ WARNING: Failed to parse metadata for block {height}: {parse_err}")
                except Exception as meta_err:
                    print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Metadata retrieval failed for block {height}: {meta_err}")

            # Step 2: Fallback to full block store
            if not block and self.full_block_store:
                try:
                    with self.full_block_store.env.begin() as txn:
                        block_key = f"block:{height}".encode("utf-8")
                        block_bytes = txn.get(block_key)

                    if block_bytes:
                        try:
                            block_dict = json.loads(block_bytes.decode("utf-8"))
                            block = Block.from_dict(block_dict)
                            found_source = "full block store"
                            print(f"[BlockStorage.get_block_by_height] ✅ FALLBACK SUCCESS: Block {height} loaded from full block store.")
                        except Exception as fallback_parse_err:
                            print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Failed to parse full block data for block {height}: {fallback_parse_err}")
                    else:
                        print(f"[BlockStorage.get_block_by_height] ❌ INFO: Block {height} not present in full block store.")
                except Exception as fullstore_err:
                    print(f"[BlockStorage.get_block_by_height] ❌ ERROR: Full block store access failed for block {height}: {fullstore_err}")

            # Step 3: Final return
            if block:
                if include_headers:
                    headers = self._get_all_block_headers()
                    return block, headers
                print(f"[BlockStorage.get_block_by_height] 🎯 FOUND: Block {height} retrieved from {found_source}.")
                return block

            print(f"[BlockStorage.get_block_by_height] ❌ NOT FOUND: Block {height} missing from both metadata and full store.")
            return None

        except Exception as e:
            print(f"[BlockStorage.get_block_by_height] ❌ CRITICAL ERROR: Unexpected failure retrieving block {height}: {e}")
            return None



    def _get_all_block_headers(self) -> List[Dict]:
        """
        Retrieve all block headers, prioritizing metadata DB and falling back to full block store.

        Returns:
            List[Dict]: A list of block headers, sorted by block index.
        """
        try:
            print("[BlockStorage._get_all_block_headers] INFO: Retrieving all block headers...")

            headers = []

            # ✅ Attempt from `block_metadata_db` first
            if self.block_metadata_db:
                with self.block_metadata_db.env.begin() as txn:
                    cursor = txn.cursor()
                    for key, value in cursor:
                        if key.startswith(b"block_meta:"):
                            try:
                                meta = json.loads(value.decode("utf-8"))
                                required_keys = {"index", "previous_hash", "timestamp", "nonce", "difficulty", "hash"}
                                if required_keys.issubset(meta.keys()):
                                    headers.append({k: meta[k] for k in required_keys})
                                else:
                                    print(f"[BlockStorage._get_all_block_headers] WARNING: Incomplete metadata header at {key.decode()}")
                            except Exception as e:
                                print(f"[BlockStorage._get_all_block_headers] ERROR: Failed to parse block metadata from {key.decode()}: {e}")

            if headers:
                print(f"[BlockStorage._get_all_block_headers] ✅ SUCCESS: Retrieved {len(headers)} headers from block metadata DB.")
            else:
                print("[BlockStorage._get_all_block_headers] ⚠️ WARNING: Metadata headers missing or incomplete. Falling back to full block store...")

                # 🔁 Fallback to full block store
                if self.full_block_store:
                    with self.full_block_store.env.begin() as txn:
                        cursor = txn.cursor()
                        for key, value in cursor:
                            if key.startswith(b"block:"):
                                try:
                                    full_block = json.loads(value.decode("utf-8"))
                                    required_keys = {"index", "previous_hash", "timestamp", "nonce", "difficulty", "hash"}
                                    if required_keys.issubset(full_block.keys()):
                                        headers.append({k: full_block[k] for k in required_keys})
                                    else:
                                        print(f"[BlockStorage._get_all_block_headers] WARNING: Incomplete header in full block {full_block.get('hash', 'unknown')}")
                                except Exception as e:
                                    print(f"[BlockStorage._get_all_block_headers] ERROR: Failed to parse full block header: {e}")
                    if headers:
                        print(f"[BlockStorage._get_all_block_headers] ✅ FALLBACK: Retrieved {len(headers)} headers from full block store.")
                    else:
                        print("[BlockStorage._get_all_block_headers] ❌ ERROR: No valid block headers found in full block store either.")

            # ✅ Sort by block index before returning
            sorted_headers = sorted(headers, key=lambda h: h["index"])
            print(f"[BlockStorage._get_all_block_headers] ✅ DONE: Returning {len(sorted_headers)} sorted headers.")
            return sorted_headers

        except Exception as e:
            print(f"[BlockStorage._get_all_block_headers] ❌ ERROR: Unexpected failure while retrieving headers: {e}")
            return []





    def validate_block_structure(self, block: Block) -> bool:
        """
        Validate a block using stored LMDB data only (no hash recalculation).

        Ensures:
        - Block is of valid type and structure.
        - All required fields exist.
        - Previous hash matches the previous block's actual stored hash.
        - Block is indexed sequentially.
        - Transactions are well-formed.

        Avoids recomputing block hashes and uses mined data only.
        """
        try:
            block_index = getattr(block, "index", "?")
            print(f"[BlockStorage.validate_block_structure] INFO: Validating structure for Block {block_index}...")

            if not self.full_block_store:
                print("[BlockStorage.validate_block_structure] ❌ ERROR: Full block store not set.")
                return False

            # ✅ Check block type
            if not isinstance(block, Block):
                print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Block is not of type Block: {type(block)}")
                return False

            # ✅ Check required fields
            required_fields = {
                "index", "hash", "previous_hash", "merkle_root",
                "timestamp", "nonce", "difficulty", "miner_address",
                "transactions", "version"
            }
            missing_fields = [field for field in required_fields if not hasattr(block, field)]
            if missing_fields:
                print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Missing fields in block {block_index}: {missing_fields}")
                return False

            # ✅ Check that the block exists in LMDB
            with self.full_block_store.env.begin() as txn:
                stored_block_raw = txn.get(f"block:{block.index}".encode())

            if not stored_block_raw:
                print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Block {block_index} not found in LMDB.")
                return False

            # ✅ Verify previous hash via LMDB
            if block.index > 0:
                with self.full_block_store.env.begin() as txn:
                    prev_raw = txn.get(f"block:{block.index - 1}".encode())
                    if not prev_raw:
                        print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Previous block {block.index - 1} not found in LMDB.")
                        return False

                    try:
                        from Zyiron_Chain.blockchain.block import Block as BlockClass
                        previous_block = BlockClass.deserialize(prev_raw)
                        prev_hash = getattr(previous_block, "hash", None)
                    except Exception as e:
                        print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Failed to deserialize previous block: {e}")
                        return False

                    if block.previous_hash != prev_hash:
                        print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Invalid previous hash at Block {block.index}.\n"
                              f"Expected: {prev_hash}\nFound:    {block.previous_hash}")
                        return False

            # ✅ Transaction structure validation
            txs = getattr(block, "transactions", [])
            if not isinstance(txs, list):
                print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Transactions in block {block_index} must be a list.")
                return False

            for tx in txs:
                if isinstance(tx, dict):
                    if "tx_id" not in tx:
                        print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Missing tx_id in transaction (dict) in Block {block_index}")
                        return False
                elif not hasattr(tx, "tx_id"):
                    print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Invalid transaction type in Block {block_index}: {tx}")
                    return False

            # ✅ Metadata check (optional)
            if hasattr(block, "metadata") and block.metadata:
                if not isinstance(block.metadata, dict):
                    print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Metadata in Block {block_index} must be a dictionary.")
                    return False
                required_meta = {"name", "version", "created_by", "creation_date"}
                missing_meta = [k for k in required_meta if k not in block.metadata]
                if missing_meta:
                    print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Metadata missing in Block {block_index}: {missing_meta}")
                    return False

            # ⚠️ Warn if version mismatches expected constant
            if getattr(block, "version", None) != Constants.VERSION:
                print(f"[BlockStorage.validate_block_structure] ⚠️ WARNING: Block version mismatch at Block {block_index}.\n"
                      f"Expected: {Constants.VERSION}, Found: {block.version}")

            print(f"[BlockStorage.validate_block_structure] ✅ SUCCESS: Block {block_index} passed structural validation.")
            return True

        except Exception as e:
            print(f"[BlockStorage.validate_block_structure] ❌ ERROR: Block {getattr(block, 'index', '?')} structure validation failed: {e}")
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
        Includes multiple layers of fallback logic for handling:
        - Closed LMDB environments
        - Corrupted/malformed blocks
        - Missing required fields
        - Invalid transaction structures
        """
        blocks = []
        attempts = 0
        max_attempts = 3
        
        while attempts < max_attempts:
            try:
                print(f"[BlockStorage.get_all_blocks] Attempt {attempts + 1}/{max_attempts}")

                # Fallback 1: Handle closed LMDB environment
                if not self.full_block_store:
                    print("[BlockStorage.get_all_blocks] ❌ ERROR: Full block store not initialized")
                    break

                try:
                    self.full_block_store.env.stat()
                except Exception as e:
                    print(f"[BlockStorage.get_all_blocks] ⚠️ LMDB environment closed. Reopening... ({e})")
                    self.full_block_store.reopen()
                    continue

                # Fallback 2: Handle corrupted LMDB reads
                with self.full_block_store.env.begin() as txn:
                    cursor = txn.cursor()
                    
                    for key, value in cursor:
                        if not key.startswith(b"block:"):
                            continue

                        try:
                            # Fallback 3: Handle malformed block keys
                            try:
                                block_index = int(key.decode().split(":")[1])
                            except (IndexError, ValueError) as e:
                                print(f"[BlockStorage.get_all_blocks] ⚠️ Malformed block key {key}: {e}")
                                continue

                            # Fallback 4: Handle JSON decode errors
                            try:
                                block_data = json.loads(value.decode('utf-8'))
                            except json.JSONDecodeError as e:
                                print(f"[BlockStorage.get_all_blocks] ⚠️ Corrupted JSON for block {block_index}: {e}")
                                # Attempt raw recovery of critical fields
                                block_data = self._recover_block_from_bytes(value, block_index)
                                if not block_data:
                                    continue

                            # Fallback 5: Handle missing/invalid fields
                            block_data = self._validate_and_repair_block(block_data, block_index)
                            if block_data:
                                blocks.append(block_data)

                        except Exception as e:
                            print(f"[BlockStorage.get_all_blocks] ⚠️ Unexpected error processing block: {e}")
                            continue

                # Success case
                blocks.sort(key=lambda b: b["index"])
                print(f"[BlockStorage.get_all_blocks] ✅ Retrieved {len(blocks)} blocks")
                return blocks

            except Exception as e:
                print(f"[BlockStorage.get_all_blocks] ❌ Attempt {attempts + 1} failed: {e}")
                attempts += 1
                time.sleep(1)  # Backoff before retry

        print(f"[BlockStorage.get_all_blocks] ❌ Failed after {max_attempts} attempts")
        return []

    def _recover_block_from_bytes(self, raw_bytes: bytes, block_index: int) -> Optional[Dict]:
        """Attempt to recover block data from corrupted JSON bytes"""
        try:
            # First try standard JSON decode
            return json.loads(raw_bytes.decode('utf-8'))
        except:
            try:
                # Fallback 1: Try different encodings
                for encoding in ['utf-8', 'latin-1', 'ascii']:
                    try:
                        return json.loads(raw_bytes.decode(encoding))
                    except:
                        continue
                
                # Fallback 2: Try extracting known fields with regex
                import re
                raw_str = str(raw_bytes)
                block_hash = re.search(r'"hash":\s*"([^"]+)"', raw_str)
                transactions = re.findall(r'"transactions":\s*(\[[^\]]+\])', raw_str)
                
                if block_hash or transactions:
                    return {
                        "index": block_index,
                        "hash": block_hash.group(1) if block_hash else Constants.ZERO_HASH,
                        "transactions": json.loads(transactions[0]) if transactions else [],
                        "header": {
                            "timestamp": int(time.time()),
                            "previous_hash": Constants.ZERO_HASH
                        }
                    }
            except Exception as e:
                print(f"[BlockStorage] ⚠️ Failed to recover block {block_index}: {e}")
        
        return None

    def _validate_and_repair_block(self, block_data: Dict, block_index: int) -> Optional[Dict]:
        """Validate and repair block structure with multiple fallbacks"""
        # Fallback 1: Ensure basic structure exists
        if not isinstance(block_data, dict):
            print(f"[BlockStorage] ⚠️ Block {block_index} is not a dictionary")
            return None
        
        # Fallback 2: Handle legacy block formats
        if "header" not in block_data:
            if all(k in block_data for k in ["index", "transactions", "hash"]):
                # Convert legacy format to new format
                block_data = {
                    "header": {k: v for k, v in block_data.items() if k not in ["transactions", "hash"]},
                    "transactions": block_data.get("transactions", []),
                    "hash": block_data.get("hash", Constants.ZERO_HASH),
                    "index": block_index
                }
            else:
                print(f"[BlockStorage] ⚠️ Block {block_index} missing required structure")
                return None
        
        # Fallback 3: Fill missing header fields
        defaults = {
            "version": "1.00",
            "previous_hash": Constants.ZERO_HASH,
            "merkle_root": Constants.ZERO_HASH,
            "timestamp": int(time.time()),
            "nonce": 0,
            "difficulty": Constants.GENESIS_TARGET,
            "miner_address": "UNKNOWN",
            "transaction_signature": Constants.ZERO_HASH,
            "reward": "0",
            "fees": "0"
        }
        
        for field, default in defaults.items():
            if field not in block_data["header"] or block_data["header"][field] in (None, ""):
                block_data["header"][field] = default
        
        # Fallback 4: Validate transactions
        if not isinstance(block_data.get("transactions"), list):
            print(f"[BlockStorage] ⚠️ Block {block_index} has invalid transactions")
            block_data["transactions"] = []
        
        # Final validation
        if len(block_data.get("hash", "")) != Constants.SHA3_384_HASH_SIZE:
            print(f"[BlockStorage] ⚠️ Block {block_index} has invalid hash")
            return None
        
        return block_data

    def get_latest_block(self, retries: int = 5, delay: float = 0.5) -> Optional[Block]:
        """
        Retrieve the latest block from full_block_chain.lmdb using metadata.
        If metadata is missing, falls back to full block store and regenerates metadata.
        Prevents re-mining by ensuring mined_hash is present.
        """
        try:
            print("[BlockStorage.get_latest_block] INFO: Retrieving latest block from LMDB...")

            if not self.full_block_store:
                print("[BlockStorage.get_latest_block] ❌ ERROR: Full block store not initialized.")
                return None

            # ✅ Step 1: Fetch latest block index
            with self.full_block_store.env.begin() as txn:
                latest_block_index_bytes = txn.get(b"latest_block_index")

            if not latest_block_index_bytes:
                print("[BlockStorage.get_latest_block] ⚠️ WARNING: No latest block index found.")
                return None

            latest_block_index = int(latest_block_index_bytes.decode("utf-8"))
            print(f"[BlockStorage.get_latest_block] INFO: Latest block index: {latest_block_index}")

            blockmeta_key = f"blockmeta:{latest_block_index}".encode("utf-8")

            # ✅ Step 2: Attempt to retrieve metadata from block_metadata.lmdb
            metadata = None
            for attempt in range(retries):
                with self.block_metadata_db.env.begin() as txn:
                    metadata_bytes = txn.get(blockmeta_key)

                if metadata_bytes:
                    try:
                        metadata = json.loads(metadata_bytes.decode("utf-8"))
                        break
                    except json.JSONDecodeError:
                        print(f"[BlockStorage.get_latest_block] ❌ ERROR: Metadata corrupted for Block {latest_block_index}")
                        return None
                else:
                    print(f"[BlockStorage.get_latest_block] ⏳ Retry {attempt + 1}/{retries}: Waiting for metadata of Block {latest_block_index}...")
                    time.sleep(delay)
            else:
                print(f"[BlockStorage.get_latest_block] ❌ ERROR: No metadata found for Block {latest_block_index} after {retries} attempts.")
                print(f"[BlockStorage.get_latest_block] ⚠️ FALLBACK: Attempting to reconstruct block from full block store...")

                fallback_block = self.get_block_by_height(latest_block_index)
                if fallback_block:
                    print(f"[BlockStorage.get_latest_block] ✅ FALLBACK: Retrieved block {latest_block_index} from full block store.")

                    # 🔄 Regenerate metadata using the official store function
                    if self.store_block_metadata(fallback_block):
                        print(f"[BlockStorage.get_latest_block] ✅ Metadata reconstructed and stored for Block {latest_block_index}")
                    else:
                        print(f"[BlockStorage.get_latest_block] ❌ ERROR: Failed to store fallback metadata for Block {latest_block_index}")

                    return fallback_block
                else:
                    print(f"[BlockStorage.get_latest_block] ❌ ERROR: Could not retrieve block {latest_block_index} from fallback.")
                    return None

            # ✅ Step 3: Retrieve full block via block_hash
            block_hash = metadata.get("hash")
            if not block_hash or len(block_hash) != 96:
                print(f"[BlockStorage.get_latest_block] ❌ ERROR: Invalid hash in metadata for Block {latest_block_index}")
                return None

            block_pointer_key = f"block_hash:{block_hash}".encode("utf-8")
            with self.full_block_store.env.begin() as txn:
                block_ref_key = txn.get(block_pointer_key)

            if not block_ref_key:
                print(f"[BlockStorage.get_latest_block] ❌ ERROR: Block hash {block_hash} not found in block_hash index.")
                return None

            with self.full_block_store.env.begin() as txn:
                full_block_bytes = txn.get(block_ref_key)

            if not full_block_bytes:
                print(f"[BlockStorage.get_latest_block] ❌ ERROR: Full block data not found at {block_ref_key.decode()}.")
                return None

            try:
                block_dict = json.loads(full_block_bytes.decode("utf-8"))
                block = Block.from_dict(block_dict)

                # ✅ Ensure `mined_hash` is set correctly to avoid re-mining
                if not getattr(block, "mined_hash", None):
                    block.mined_hash = block_dict.get("hash", Constants.ZERO_HASH)

                print(f"[BlockStorage.get_latest_block] ✅ SUCCESS: Retrieved Block {block.index} (Hash: {block.hash})")
                return block
            except Exception as e:
                print(f"[BlockStorage.get_latest_block] ❌ ERROR: Failed to deserialize block: {e}")
                return None

        except Exception as e:
            print(f"[BlockStorage.get_latest_block] ❌ ERROR: Unexpected failure: {e}")
            return None


    def store_block_metadata(self, block) -> bool:
        """
        Store lightweight block metadata in `block_metadata.lmdb`.
        If this fails, fallback to full block store to reconstruct the block and try again.
        """
        try:
            block_height = getattr(block, "height", None) or getattr(block, "index", None)
            block_hash = getattr(block, "hash", None) or getattr(block, "mined_hash", None)

            if block_height is None or block_hash is None:
                print(f"[store_block_metadata] ❌ ERROR: Missing block height or hash.")
                return False
            if not isinstance(block_height, int) or block_height < 0:
                print(f"[store_block_metadata] ❌ ERROR: Invalid block height: {block_height}")
                return False
            if not isinstance(block_hash, str) or len(block_hash) != Constants.SHA3_384_HASH_SIZE:
                print(f"[store_block_metadata] ❌ ERROR: Invalid block hash format: {block_hash}")
                return False

            difficulty = getattr(block, "difficulty", None)
            difficulty_hex = DifficultyConverter.to_hex(
                int(difficulty, 16) if isinstance(difficulty, str) else difficulty or 0
            )

            metadata = {
                "index": block_height,
                "hash": block_hash,
                "timestamp": getattr(block, "timestamp", int(time.time())),
                "difficulty": difficulty_hex,
                "previous_hash": getattr(block, "previous_hash", Constants.ZERO_HASH),
                "merkle_root": getattr(block, "merkle_root", Constants.ZERO_HASH),
                "miner_address": getattr(block, "miner_address", "UNKNOWN"),
                "transaction_count": len(getattr(block, "transactions", [])),
                "total_fees": str(getattr(block, "fees", Decimal("0")))
            }

            key = f"blockmeta:{block_height}".encode("utf-8")
            value = json.dumps(metadata, sort_keys=True).encode("utf-8")

            with self.block_metadata_db.env.begin(write=True) as txn:
                txn.put(key, value)

            print(f"[store_block_metadata] ✅ SUCCESS: Stored metadata for Block #{block_height}")
            return True

        except Exception as e:
            print(f"[store_block_metadata] ❌ ERROR: Metadata storage failed: {e}")
            print("[store_block_metadata] 🔁 Attempting fallback from full block store...")
            try:
                fallback_block = self.get_block_by_height(getattr(block, "index", 0))
                if fallback_block:
                    return self.store_block_metadata(fallback_block)
                print("[store_block_metadata] ❌ Fallback failed: Block not found in full block store.")
                return False
            except Exception as fallback_e:
                print(f"[store_block_metadata] ❌ Fallback exception: {fallback_e}")
                return False




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
        Includes full fallback logic and auto-recovery from LMDB errors.

        :param tx_id: Transaction ID to look up.
        :return: The Block instance containing the transaction, or None.
        """
        try:
            print(f"[BlockStorage.get_block_by_tx_id] INFO: Searching for block containing transaction {tx_id}...")

            # ✅ Ensure all LMDB instances are initialized
            if not self.txindex_db or not self.block_metadata_db or not self.full_block_store:
                print("[BlockStorage.get_block_by_tx_id] ❌ ERROR: Required LMDB instances are not set.")
                return None

            block_hash_bytes = None
            key = f"tx:{tx_id}".encode("utf-8")

            # ✅ Step 1: Try accessing the txindex
            try:
                with self.txindex_db.env.begin() as txn:
                    block_hash_bytes = txn.get(key)
            except Exception as e:
                print(f"[BlockStorage.get_block_by_tx_id] ⚠️ ERROR: Failed to access txindex DB: {e}. Retrying with reopen...")
                try:
                    self.txindex_db.reopen()
                    with self.txindex_db.env.begin() as txn:
                        block_hash_bytes = txn.get(key)
                except Exception as e2:
                    print(f"[BlockStorage.get_block_by_tx_id] ❌ ERROR: Retry failed for txindex DB: {e2}")
                    return None

            if not block_hash_bytes:
                print(f"[BlockStorage.get_block_by_tx_id] ⚠️ WARNING: No block found for transaction {tx_id}.")
                return None

            block_hash = block_hash_bytes.decode("utf-8", errors="ignore")
            print(f"[BlockStorage.get_block_by_tx_id] INFO: Transaction {tx_id} maps to block hash {block_hash}")

            # ✅ Step 2: Retrieve block data from full block store
            block_data_bytes = None
            try:
                with self.full_block_store.env.begin() as txn:
                    block_data_bytes = txn.get(f"block:{block_hash}".encode("utf-8"))
            except Exception as e:
                print(f"[BlockStorage.get_block_by_tx_id] ⚠️ ERROR: Full block store access failed: {e}. Reopening and retrying...")
                try:
                    self.full_block_store.reopen()
                    with self.full_block_store.env.begin() as txn:
                        block_data_bytes = txn.get(f"block:{block_hash}".encode("utf-8"))
                except Exception as e2:
                    print(f"[BlockStorage.get_block_by_tx_id] ❌ ERROR: Full block retry failed: {e2}")
                    return None

            if not block_data_bytes:
                print(f"[BlockStorage.get_block_by_tx_id] ❌ ERROR: Full block data not found for hash {block_hash}.")
                return None

            # ✅ Step 3: Parse block JSON and construct Block instance
            try:
                block_dict = json.loads(block_data_bytes.decode("utf-8"))
                block = Block.from_dict(block_dict)
                print(f"[BlockStorage.get_block_by_tx_id] ✅ SUCCESS: Retrieved Block #{block.index} from full block storage.")
                return block
            except Exception as e:
                print(f"[BlockStorage.get_block_by_tx_id] ❌ ERROR: Failed to deserialize block {block_hash}: {e}")
                return None

        except Exception as e:
            print(f"[BlockStorage.get_block_by_tx_id] ❌ FATAL ERROR: Unexpected failure for TX ID {tx_id}: {e}")
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
        


    def create_dir_if_not_exists(path):
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"Created database directory: {path}")

