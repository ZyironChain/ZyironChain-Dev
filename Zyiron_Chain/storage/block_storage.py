import os
import re
import string
import sys
import struct
import json
import pickle
import time
from decimal import Decimal
from typing import Optional, List, Dict, Union

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


class BlockStorage:
    """
    BlockStorage is responsible for handling block metadata and full block storage.
    
    Responsibilities:
      - Store block headers (metadata) in LMDB.
      - Store full blocks in LMDB (`full_block_chain.lmdb`).
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

            # ✅ **Step 2: Determine the Latest LMDB File for Blocks**
            lmdb_files = sorted([
                f for f in os.listdir(Constants.BLOCKCHAIN_STORAGE_PATH)
                if f.startswith("full_block_chain")
            ])
            latest_lmdb = lmdb_files[-1] if lmdb_files else "full_block_chain_1.lmdb"
            self.full_block_store = LMDBManager(os.path.join(Constants.BLOCKCHAIN_STORAGE_PATH, latest_lmdb))

            print(f"[BlockStorage.__init__] ✅ Using LMDB file: {latest_lmdb}")

        except Exception as e:
            print(f"[BlockStorage.__init__] ❌ ERROR: Initialization failed: {e}")
            raise



    def _check_and_rollover_lmdb(self):
        """
        Checks if the current LMDB file exceeds 512MB.
        If it does, rolls over to a new LMDB file for storing new blocks.
        """
        try:
            lmdb_path = Constants.DATABASES["full_block_chain"]
            lmdb_file = os.path.join(Constants.BLOCKCHAIN_STORAGE_PATH, lmdb_path)
            
            # ✅ **Check LMDB file size**
            if os.path.exists(lmdb_file) and os.path.getsize(lmdb_file) >= Constants.BLOCK_DATA_FILE_SIZE_BYTES:
                print(f"[BlockStorage] INFO: LMDB file {lmdb_file} exceeds 512MB. Rolling over to a new file.")

                # ✅ **Determine next LMDB file number**
                file_count = len([f for f in os.listdir(Constants.BLOCKCHAIN_STORAGE_PATH) if f.startswith("full_block_chain")])
                new_lmdb_file = os.path.join(Constants.BLOCKCHAIN_STORAGE_PATH, f"full_block_chain_{file_count + 1}.lmdb")

                # ✅ **Close existing LMDB environment before switching**
                self.full_block_store.env.close()

                # ✅ **Switch to new LMDB file**
                self.full_block_store = LMDBManager(new_lmdb_file)
                print(f"[BlockStorage] ✅ New LMDB file created: {new_lmdb_file}")

        except Exception as e:
            print(f"[BlockStorage] ❌ ERROR: Failed to check LMDB rollover: {e}")


    def store_block_securely(self, block: Block):
        """
        Store a block securely with thread safety and proper serialization.
        - Uses `write_lock` to ensure thread safety.
        - Stores the block as structured JSON (no bytes, no struct.pack).
        - No magic number handling or fixed offsets.
        - Ensures the block is appended to the file dynamically.
        """
        try:
            # ✅ Validate block type
            if not isinstance(block, Block):
                print("[BlockStorage.store_block_securely] ❌ ERROR: Invalid block type. Expected a Block instance.")
                return

            with self.write_lock:  # ✅ Prevents concurrent writes
                print(f"[BlockStorage.store_block_securely] INFO: Acquiring lock to store Block {block.index}...")

                # ✅ **Serialize block to JSON**
                block_json = json.dumps(block.to_dict())

                # ✅ **Write block to file**
                with open(self.current_block_file, "a", encoding="utf-8") as f:
                    f.write(block_json + "\n")  # ✅ Append newline for readability
                    f.flush()  # Ensure data is written to disk

                print(f"[BlockStorage.store_block_securely] ✅ SUCCESS: Block {block.index} stored securely.")

        except Exception as e:
            print(f"[BlockStorage.store_block_securely] ❌ ERROR: Failed to store block {block.index}: {e}")



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






    
    def store_block(self, block: Block, difficulty: Union[bytes, int, str]):
        """
        Stores a block in LMDB.
        - Ensures difficulty is stored as an integer.
        - Calls `_check_and_rollover_lmdb()` to prevent LMDB from exceeding 512MB.
        """
        try:
            print(f"[BlockStorage.store_block] INFO: Storing Block {block.index}...")

            # ✅ **Check and Rollover LMDB if needed**
            self._check_and_rollover_lmdb()

            # ✅ **Check If Block Already Exists in `full_block_store`**
            with self.full_block_store.env.begin() as txn:
                existing_block = txn.get(f"block:{block.hash}".encode())

            if existing_block:
                print(f"[BlockStorage.store_block] ⚠️ WARNING: Block {block.index} already exists. Skipping.")
                return

            # ✅ **Ensure Difficulty is Stored as an Integer**
            difficulty_int = self._convert_difficulty_to_int(difficulty)

            # ✅ **Ensure Miner Address is a Proper String**
            miner_address = str(block.miner_address)

            # ✅ **Ensure Previous Hash, Merkle Root, and Block Hash are Strings**
            def ensure_str(value):
                return value.hex() if isinstance(value, bytes) else str(value)

            previous_hash = ensure_str(block.previous_hash)
            merkle_root = ensure_str(block.merkle_root)
            block_hash = ensure_str(block.hash)

            # ✅ **Transaction Validation & ID Extraction**
            tx_ids = []
            valid_transactions = []
            for tx in block.transactions:
                tx_id = self._validate_and_extract_tx_id(tx)  # Helper method
                if tx_id:
                    tx_ids.append(tx_id)
                    valid_transactions.append(tx)

            # ✅ **Build Block Metadata**
            block_metadata = {
                "index": block.index,
                "previous_hash": previous_hash,
                "merkle_root": merkle_root,
                "timestamp": block.timestamp,
                "nonce": block.nonce,
                "difficulty": difficulty_int,  # ✅ Store as int
                "miner_address": miner_address,
                "transaction_signature": getattr(block, "signature", "0" * 96),
                "reward": str(Decimal(block.reward).normalize() if hasattr(block, "reward") else 0),
                "fees": str(Decimal(block.fees).normalize() if hasattr(block, "fees") else 0),
                "version": block.version,
                "transactions": [tx.to_dict() if hasattr(tx, "to_dict") else tx for tx in valid_transactions],
                "hash": block_hash  # ✅ Use the mined hash directly
            }

            # ✅ **Store Full Block in `full_block_store`**
            with self.full_block_store.env.begin(write=True) as txn:
                txn.put(f"block:{block_hash}".encode(), json.dumps(block_metadata).encode())

            # ✅ **Transaction Indexing in `txindex_db`**
            print(f"[BlockStorage.store_block] Indexing {len(valid_transactions)} transactions...")
            with self.txindex_db.env.begin(write=True) as txn:
                for tx in valid_transactions:
                    txn.put(f"tx:{tx.tx_id}".encode(), block_hash.encode())

            print(f"[BlockStorage.store_block] ✅ Block {block.index} stored successfully in LMDB.")

        except Exception as e:
            print(f"[BlockStorage.store_block] ❌ ERROR: Failed to store block {block.index}: {e}")
            raise


    def _block_to_storage_format(self, block: Block) -> Dict:
        """
        Convert a Block object to a dictionary format suitable for LMDB storage.
        - Handles missing attributes with default values.
        - Ensures consistent formatting for all block fields.
        - Includes error handling for serialization issues.
        """
        try:
            # ✅ **Extract Block Header Fields (if available)**
            merkle_root = (
                block.header.merkle_root
                if hasattr(block.header, "merkle_root")
                else Constants.ZERO_HASH  # Default to zero hash if missing
            )
            difficulty = (
                block.header.difficulty
                if hasattr(block.header, "difficulty")
                else Constants.MIN_DIFFICULTY  # Default to minimum difficulty if missing
            )

            # ✅ **Extract Miner Address (if available)**
            miner_address = (
                block.miner_address
                if hasattr(block, "miner_address")
                else Constants.DEFAULT_MINER_ADDRESS  # Default to a known address if missing
            )

            # ✅ **Serialize Transactions**
            transactions = [
                tx.to_dict() if hasattr(tx, "to_dict") else tx
                for tx in block.transactions
            ]

            # ✅ **Calculate Block Size**
            block_size = len(pickle.dumps(block))

            # ✅ **Return Block in Storage Format**
            return {
                "index": block.index,
                "previous_hash": block.previous_hash,
                "hash": block.hash,
                "merkle_root": merkle_root,
                "timestamp": block.timestamp,
                "nonce": block.nonce,
                "difficulty": difficulty,
                "miner_address": miner_address,
                "transactions": transactions,
                "size": block_size
            }

        except Exception as e:
            print(f"[BlockStorage._block_to_storage_format] ❌ ERROR: Failed to format block for storage: {e}")
            return {}  # Return an empty dict in case of errors

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





    def get_block_by_height(self, height: int, include_headers: bool = False) -> Optional[Union[Block, List[Dict]]]:
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
                block_data = txn.get(f"block:{height}".encode("utf-8"))

            if not block_data:
                print(f"[BlockStorage.get_block_by_height] ❌ ERROR: No block found at height {height} in LMDB.")
                return None

            # ✅ **Deserialize Block Data from JSON**
            try:
                block_dict = json.loads(block_data.decode("utf-8"))
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
            block = Block.from_dict(block_dict)

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
                            header = block_meta.get("block_header")
                            if isinstance(header, dict) and "index" in header:
                                headers.append(header)
                            else:
                                print(f"[BlockStorage._get_all_block_headers] WARNING: Invalid header in block {block_meta.get('hash', 'unknown')}")

                        except json.JSONDecodeError as e:
                            print(f"[BlockStorage._get_all_block_headers] ERROR: Failed to parse block metadata: {e}")
                            continue

            if not headers:
                print("[BlockStorage._get_all_block_headers] WARNING: No block headers found in LMDB.")
                return []

            print(f"[BlockStorage._get_all_block_headers] INFO: Retrieved {len(headers)} block headers.")
            return headers

        except Exception as e:
            print(f"[BlockStorage._get_all_block_headers] ERROR: Failed to retrieve block headers: {e}")
            return []




    def validate_block_structure(self, block: Block) -> bool:
        """
        Validate that a block contains all required fields, has a valid hash, and contains properly formatted transactions.
        Also ensures metadata integrity and checks for version mismatches.
        
        - Validates against `full_block_chain.lmdb` instead of file-based metadata.
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

            # ✅ **Ensure Block Exists in LMDB**
            with self.full_block_store.env.begin() as txn:
                stored_block = txn.get(f"block:{block.hash}".encode())

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
        """
        try:
            print("[BlockStorage.load_chain] INFO: Loading full blockchain from LMDB...")

            # ✅ **Ensure LMDB Storage Is Used**
            if not self.full_block_store:
                print("[BlockStorage.load_chain] ❌ ERROR: `full_block_store` is not set. Cannot load blockchain data.")
                return []

            chain_data = []
            
            # ✅ **Retrieve All Blocks from LMDB Using `full_block_store`**
            with self.full_block_store.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if not key.decode().startswith("block:"):
                        continue
                    try:
                        block_data = json.loads(value.decode("utf-8"))
                        if "index" not in block_data:
                            print("[BlockStorage.load_chain] ERROR: Block metadata missing 'index'")
                            continue
                        chain_data.append(block_data)
                    except json.JSONDecodeError as e:
                        print(f"[BlockStorage.load_chain] ERROR: Failed to parse block metadata: {e}")
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

            # ✅ **Ensure Full Block Storage LMDB Instance Is Used**
            if not self.full_block_store:
                print("[BlockStorage.get_all_blocks] ERROR: `full_block_store` is not set. Cannot retrieve blocks.")
                return []

            blocks = []

            # ✅ **Retrieve Blocks from `full_block_chain.lmdb`**
            with self.full_block_store.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.startswith(b"block:"):
                        try:
                            block_data = value.decode("utf-8")
                            block_metadata = json.loads(block_data)

                            # ✅ **Ensure Block Metadata Contains Required Fields**
                            if not isinstance(block_metadata, dict) or "block_header" not in block_metadata:
                                print(f"[BlockStorage.get_all_blocks] ERROR: Invalid block metadata: {block_metadata}")
                                continue

                            header = block_metadata["block_header"]
                            if not isinstance(header, dict) or "index" not in header:
                                print("[BlockStorage.get_all_blocks] ERROR: Block header missing 'index'")
                                continue

                            blocks.append(block_metadata)

                        except json.JSONDecodeError as e:
                            print(f"[BlockStorage.get_all_blocks] ERROR: Failed to parse block metadata: {e}")
                            continue

            # ✅ **Sort Blocks by Height to Ensure Correct Processing Order**
            sorted_blocks = sorted(blocks, key=lambda b: b["block_header"]["index"])

            # ✅ **Validate Chain Continuity**
            prev_hash = Constants.ZERO_HASH
            for block in sorted_blocks:
                current_index = block["block_header"]["index"]
                current_prev_hash = block["block_header"]["previous_hash"]
                current_hash = block["hash"]

                if current_prev_hash != prev_hash:
                    print(f"[BlockStorage.get_all_blocks] ERROR: Chain discontinuity at block {current_index}. "
                          f"Prev hash {current_prev_hash} does not match expected {prev_hash}.")
                    return []  # Return empty list if chain is broken

                prev_hash = current_hash

            print(f"[BlockStorage.get_all_blocks] SUCCESS: Retrieved {len(sorted_blocks)} valid blocks.")
            return sorted_blocks

        except Exception as e:
            print(f"[BlockStorage.get_all_blocks] ERROR: Failed to retrieve blocks: {e}")
            return []





    def get_latest_block(self) -> Optional[Block]:
        """
        Retrieve the latest block from `full_block_chain.lmdb`.
        - Ensures proper validation of block metadata.
        - Checks for chain integrity.
        - Handles errors gracefully.
        """
        try:
            print("[BlockStorage.get_latest_block] INFO: Retrieving latest block from LMDB...")

            # ✅ **Ensure LMDB Instances Exist**
            if not self.full_block_store or not self.block_metadata_db:
                print("[BlockStorage.get_latest_block] ERROR: LMDB instances not set. Cannot retrieve latest block.")
                return None

            latest_block = None
            highest_index = -1

            # ✅ **Retrieve All Blocks from `full_block_chain.lmdb`**
            with self.full_block_store.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.startswith(b"block:"):
                        try:
                            block_metadata = json.loads(value.decode("utf-8"))

                            # ✅ **Validate Block Metadata Structure**
                            if not isinstance(block_metadata, dict) or "block_header" not in block_metadata:
                                print(f"[BlockStorage.get_latest_block] ERROR: Invalid block metadata: {block_metadata}")
                                continue

                            header = block_metadata["block_header"]
                            if not isinstance(header, dict) or "index" not in header:
                                print("[BlockStorage.get_latest_block] ERROR: Block header missing 'index'")
                                continue

                            block_index = header["index"]
                            if block_index > highest_index:
                                highest_index = block_index
                                latest_block = block_metadata

                        except json.JSONDecodeError as e:
                            print(f"[BlockStorage.get_latest_block] ERROR: Corrupt block metadata: {e}")
                            continue

            # ✅ **Ensure At Least One Valid Block Was Found**
            if not latest_block:
                print("[BlockStorage.get_latest_block] WARNING: No blocks found in LMDB. Chain may be empty.")
                return None

            # ✅ **Validate Block Hash Format**
            block_hash = latest_block.get("hash", Constants.ZERO_HASH)
            if not isinstance(block_hash, str) or len(block_hash) != Constants.SHA3_384_HASH_SIZE:
                print(f"[BlockStorage.get_latest_block] ERROR: Invalid block hash format: {block_hash}")
                return None

            # ✅ **Validate Required Header Fields**
            required_keys = {"index", "previous_hash", "timestamp", "nonce", "difficulty"}
            header = latest_block["block_header"]
            if not required_keys.issubset(header):
                print(f"[BlockStorage.get_latest_block] ERROR: Incomplete block metadata: {latest_block}")
                return None

            # ✅ **Validate Timestamp**
            try:
                timestamp = int(header["timestamp"])
                if timestamp <= 0:
                    raise ValueError("Invalid timestamp")
            except (ValueError, TypeError) as e:
                print(f"[BlockStorage.get_latest_block] ERROR: Invalid timestamp: {e}")
                return None

            # ✅ **Verify `block.data` File Exists and Contains Valid Magic Number**
            if not os.path.exists(self.current_block_file):
                print(f"[BlockStorage.get_latest_block] ERROR: `block.data` file not found: {self.current_block_file}")
                return None

            with open(self.current_block_file, "rb") as f:
                if os.path.getsize(self.current_block_file) < 4:
                    print("[BlockStorage.get_latest_block] ERROR: `block.data` file too small to contain magic number.")
                    return None

                file_magic_number = struct.unpack(">I", f.read(4))[0]
                if file_magic_number != Constants.MAGIC_NUMBER:
                    print(f"[BlockStorage.get_latest_block] ERROR: Invalid magic number in `block.data` file: {hex(file_magic_number)}. Expected: {hex(Constants.MAGIC_NUMBER)}")
                    return None

            # ✅ **Retrieve Full Block Data from `block.data`**
            print("[BlockStorage.get_latest_block] INFO: Retrieving full block data from `block.data`...")
            with open(self.current_block_file, "rb") as f:
                f.seek(4)  # Skip magic number
                block_data = f.read()

            if not block_data:
                print("[BlockStorage.get_latest_block] ERROR: No block data found in `block.data`.")
                return None

            # ✅ **Deserialize Latest Block**
            full_block = self._deserialize_block_from_binary(block_data)
            if not full_block:
                print(f"[BlockStorage.get_latest_block] ERROR: Failed to load full block {block_hash} from `block.data`.")
                print(f"[BlockStorage.get_latest_block] ❌ WARNING: Block {latest_block['block_header']['index']} may be corrupt. Consider reindexing the blockchain.")
                return None

            print(f"[BlockStorage.get_latest_block] ✅ SUCCESS: Retrieved Block {full_block.index} (Hash: {full_block.hash}).")
            return full_block

        except Exception as e:
            print(f"[BlockStorage.get_latest_block] ERROR: Failed to retrieve latest block: {e}")
            return None


    def get_total_mined_supply(self) -> Optional[Decimal]:
        """
        Calculate the total mined coin supply by summing all Coinbase rewards from stored blocks.
        - Caches the result in LMDB for fast future retrieval.
        - Returns None if no blocks exist instead of throwing an error.
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

                            # ✅ **Ensure Block Metadata Contains Required Fields**
                            if not isinstance(block_metadata, dict) or "block_header" not in block_metadata:
                                print(f"[BlockStorage.get_total_mined_supply] ERROR: Invalid block metadata: {block_metadata}")
                                continue

                            header = block_metadata["block_header"]
                            if not isinstance(header, dict) or "index" not in header:
                                print("[BlockStorage.get_total_mined_supply] ERROR: Block header missing 'index'")
                                continue

                            # ✅ **Process Coinbase Transactions for Mining Rewards**
                            transactions = block_metadata.get("tx_ids", [])
                            if transactions:
                                blocks_found = True
                                for tx_id in transactions:
                                    tx_key = f"tx:{tx_id}".encode("utf-8")

                                    # ✅ **Retrieve Transaction Data Using `txindex_db`**
                                    with self.txindex_db.env.begin() as txn:
                                        tx_data = txn.get(tx_key)

                                    if not tx_data:
                                        print(f"[BlockStorage.get_total_mined_supply] WARNING: Missing transaction {tx_id} in txindex.")
                                        continue

                                    try:
                                        tx_details = json.loads(tx_data.decode("utf-8"))

                                        # ✅ **Ensure Transaction is a Valid Coinbase Transaction**
                                        if tx_details.get("type") == "COINBASE":
                                            outputs = tx_details.get("outputs", [])
                                            if outputs and isinstance(outputs, list):
                                                for output in outputs:
                                                    if "amount" in output:
                                                        total_supply += Decimal(str(output["amount"]))

                                    except json.JSONDecodeError as json_error:
                                        print(f"[BlockStorage.get_total_mined_supply] ERROR: Failed to parse transaction {tx_id}: {json_error}")
                                        continue

                        except json.JSONDecodeError as e:
                            print(f"[BlockStorage.get_total_mined_supply] ERROR: Failed to parse block metadata: {e}")
                            continue

            # ✅ **Handle Case Where No Blocks Exist**
            if not blocks_found:
                print("[BlockStorage.get_total_mined_supply] WARNING: No blocks found in storage. Returning None.")
                return None

            # ✅ **Cache the Total Mined Supply**
            with self.block_metadata_db.env.begin(write=True) as txn:
                txn.put(b"total_mined_supply", str(total_supply).encode("utf-8"))

            print(f"[BlockStorage.get_total_mined_supply] ✅ SUCCESS: Total mined supply calculated & cached: {total_supply} ZYC")
            return total_supply

        except Exception as e:
            print(f"[BlockStorage.get_total_mined_supply] ERROR: Failed to calculate total mined supply: {e}")
            return None


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