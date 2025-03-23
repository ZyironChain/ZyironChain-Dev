from decimal import Decimal
import lmdb
import json
import time
import sys
import os

# Adjust Python path for project structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

# Add this at the top with other imports
import shutil  # Required for file operations

import lmdb
import json
import time

from Zyiron_Chain.blockchain.constants import Constants

import lmdb
import json
import os
from Zyiron_Chain.blockchain.constants import Constants
import threading
from lmdb import open

import lmdb

from typing import Union

import lmdb
import json
import time
import os
from typing import Optional
from Zyiron_Chain.blockchain.constants import Constants
from typing import Union, List, Dict
import json

# Optional: If you need the "ParentConstants" folder, etc.

import lmdb
import json
import os
import time
from typing import Optional, List, Dict
from Zyiron_Chain.blockchain.constants import Constants

class LMDBManager:
    def __init__(self, db_path: Optional[str] = None):
        # ✅ Determine database path based on Constants or override
        db_path = db_path or os.path.join(Constants.BLOCKCHAIN_STORAGE_PATH, Constants.NETWORK_FOLDER)
        db_path = os.path.abspath(db_path)
        parent_dir = os.path.dirname(db_path)

        # ✅ Create parent directory if it doesn't exist
        if parent_dir and parent_dir != db_path:
            try:
                os.makedirs(parent_dir, exist_ok=True)
                print(f"Created database directory: {parent_dir}")
            except OSError as e:
                print(f"Failed to create directory {parent_dir}: {str(e)}")
                raise

        # ✅ On Windows, set mutex fix for MDB_BAD_RSLOT
        if os.name == "nt":
            os.environ["LMDB_USE_WINDOWS_MUTEX"] = "1"

        # ✅ Open LMDB environment
        try:
            self.env = lmdb.open(
                path=db_path,
                map_size=Constants.LMDB_MAP_SIZE,
                create=True,
                readahead=False,
                writemap=True,
                meminit=False,
                max_dbs=Constants.MAX_LMDB_DATABASES
            )
        except lmdb.Error as e:
            print(f"LMDB environment creation failed: {str(e)}")
            raise

        # ✅ Initialize named databases inside LMDB
        try:
            with self.env.begin(write=True) as txn:
                self.mempool_db = self.env.open_db(b"mempool", txn=txn)
                self.blocks_db = self.env.open_db(b"blocks", txn=txn)
                self.transactions_db = self.env.open_db(b"transactions", txn=txn)
                self.metadata_db = self.env.open_db(b"metadata", txn=txn)

            print("Database handles initialized successfully.")
        except lmdb.Error as e:
            print(f"Database initialization failed: {str(e)}")
            self.env.close()
            raise

        # ✅ Flag for transaction state (if needed)
        self.transaction_active = False

        # ✅ Capacity check (resizes map if usage exceeds 80%)
        self._verify_capacity()





    def get_all_transactions(self) -> List[Dict]:
        """
        Retrieve all transactions from the LMDB database.
        Returns a list of transaction dictionaries.
        """
        transactions = []
        try:
            with self.env.begin() as txn:
                cursor = txn.cursor(db=self.transactions_db)
                for key, value in cursor:
                    try:
                        key_str = key.decode("utf-8", errors="ignore")
                        if key_str.startswith("tx:"):
                            try:
                                tx_data = value.decode("utf-8", errors="ignore")
                                tx_dict = json.loads(tx_data)
                                transactions.append(tx_dict)
                            except json.JSONDecodeError as json_error:
                                print(f"[LMDBManager.get_all_transactions] WARNING: Skipping corrupt transaction entry {key_str}: {json_error}")
                    except UnicodeDecodeError as decode_error:
                        print(f"[LMDBManager.get_all_transactions] ERROR: Failed to decode key {key}: {decode_error}")

            print(f"[LMDBManager.get_all_transactions] INFO: Retrieved {len(transactions)} valid transactions.")
            return transactions

        except Exception as e:
            print(f"[LMDBManager.get_all_transactions] ERROR: Failed to retrieve transactions: {e}")
            return []




    def _initialize_databases(self):
        """
        Safely initializes all required LMDB database handles for the current network.
        Only opens databases if they are not already opened.
        """
        try:
            print("[LMDBManager] INFO: Initializing LMDB databases...")

            network = Constants.NETWORK
            config = Constants.NETWORK_DATABASES.get(network)

            if not config:
                raise ValueError(f"[LMDBManager] ❌ ERROR: No LMDB config found for network: {network}")

            with self.env.begin(write=True) as txn:
                if not hasattr(self, "mempool_db"):
                    self.mempool_db = self.env.open_db(b"mempool", txn=txn)
                if not hasattr(self, "blocks_db"):
                    self.blocks_db = self.env.open_db(b"blocks", txn=txn)
                if not hasattr(self, "transactions_db"):
                    self.transactions_db = self.env.open_db(b"transactions", txn=txn)
                if not hasattr(self, "metadata_db"):
                    self.metadata_db = self.env.open_db(b"metadata", txn=txn)

                # ✅ Custom Blockchain DBs
                if not hasattr(self, "block_metadata_db"):
                    self.block_metadata_db = self.env.open_db(b"block_metadata", txn=txn)
                if not hasattr(self, "txindex_db"):
                    self.txindex_db = self.env.open_db(b"txindex", txn=txn)
                if not hasattr(self, "utxo_db"):
                    self.utxo_db = self.env.open_db(b"utxo", txn=txn)
                if not hasattr(self, "utxo_history_db"):
                    self.utxo_history_db = self.env.open_db(b"utxo_history", txn=txn)
                if not hasattr(self, "fee_stats_db"):
                    self.fee_stats_db = self.env.open_db(b"fee_stats", txn=txn)
                if not hasattr(self, "orphan_blocks_db"):
                    self.orphan_blocks_db = self.env.open_db(b"orphan_blocks", txn=txn)

            print(f"[LMDBManager] ✅ SUCCESS: All LMDB databases initialized for {network.upper()} (only missing ones opened).")

        except lmdb.Error as e:
            print(f"[LMDBManager] ❌ ERROR: Failed to initialize LMDB databases: {e}")
            self.env.close()
            raise

    def _verify_capacity(self):
        """
        Check database limits and dynamically increase LMDB map_size if usage exceeds 80%.
        """
        try:
            with self.env.begin() as txn:
                stats = txn.stat()
                info = self.env.info()

                total_entries = stats.get("entries", 0)
                map_size = info.get("map_size", 0)
                last_page = info.get("last_pgno", 0)
                page_size = info.get("psize", 4096)

                if total_entries == 0:
                    print("[LMDBManager] INFO: No database entries yet. Capacity check skipped.")
                    return

                file_usage = (last_page * page_size) / map_size if map_size > 0 else 0

                if file_usage > 0.8:
                    new_size = int(map_size * 1.5)  # ✅ Increase map_size by 50%
                    self.env.set_mapsize(new_size)
                    print(f"[LMDBManager] INFO: Increased LMDB map_size to {new_size} bytes.")

            print("[LMDBManager] INFO: Capacity check completed.")

        except lmdb.Error as e:
            print(f"[LMDBManager] ERROR: Failed to verify LMDB capacity: {e}")


    def get_database_status(self):
        """
        Return current database usage statistics such as used databases,
        map size, and free space.
        """
        try:
            with self.env.begin() as txn:
                return {
                    "max_databases": self.env.info().get("max_dbs", 0),
                    "used_databases": txn.stat().get("entries", 0),
                    "map_size": self.env.info().get("map_size", 0),
                    "free_space": self.env.info().get("map_size", 0)
                                 - self.env.info().get("last_pgno", 0) * self.env.info().get("psize", 4096)
                }
        except Exception as e:
            print(f"[LMDBManager] ERROR: Failed to retrieve database status: {e}")
            return {}


    def get_db_path(self, db_name: str) -> str:
        """
        Returns the path for the specified database name.
        """
        db_path = os.path.join(Constants.BLOCKCHAIN_STORAGE_PATH, db_name)
        print(f"[LMDBManager] INFO: Database path for '{db_name}': {db_path}")
        return db_path

    def fetch_all_pending_transactions(self) -> list:
        """
        Retrieve all pending transactions stored in the mempool DB.
        """
        pending_transactions = []
        try:
            with self.env.begin(db=self.mempool_db) as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    key_str = key.decode()
                    if key_str.startswith("mempool:pending_tx:"):
                        try:
                            tx_data = json.loads(value.decode("utf-8"))
                            pending_transactions.append(tx_data)
                        except json.JSONDecodeError as e:
                            print(f"[LMDBManager] ERROR: Failed to decode transaction {key_str}: {e}")

            print(f"[LMDBManager] INFO: Retrieved {len(pending_transactions)} pending transactions.")
            return pending_transactions

        except lmdb.Error as e:
            print(f"[LMDBManager] ERROR: LMDB retrieval failed: {e}")
            return []


    def add_pending_transaction(self, transaction: dict):
        """
        Add a pending transaction to the mempool DB.
        """
        try:
            tx_id = transaction.get("tx_id")
            if not tx_id:
                print("[LMDBManager] ERROR: Transaction missing 'tx_id'.")
                return

            key = f"mempool:pending_tx:{tx_id}".encode()
            value = json.dumps(transaction).encode("utf-8")

            with self.env.begin(write=True, db=self.mempool_db) as txn:
                txn.put(key, value)

            print(f"[LMDBManager] INFO: Pending transaction {tx_id} stored successfully.")
        except Exception as e:
            print(f"[LMDBManager] ERROR: Failed to store pending transaction: {e}")

    def delete_pending_transaction(self, tx_id: str):
        """
        Remove a pending transaction from the mempool DB.
        """
        try:
            key = f"mempool:pending_tx:{tx_id}".encode()
            with self.env.begin(write=True, db=self.mempool_db) as txn:
                txn.delete(key)

            print(f"[LMDBManager] INFO: Pending transaction {tx_id} removed from mempool.")
        except Exception as e:
            print(f"[LMDBManager] ERROR: Failed to remove pending transaction {tx_id}: {e}")



    def begin_transaction(self):
        """Begin a simulated transaction."""
        if not self.transaction_active:
            print("[LMDBManager] INFO: Starting LMDB transaction (simulated).")
            self.transaction_active = True

    def commit(self):
        """Commit a simulated transaction."""
        if self.transaction_active:
            print("[LMDBManager] INFO: Committing LMDB transaction (simulated).")
            self.transaction_active = False

    def rollback(self):
        """
        Roll back a simulated transaction.
        LMDB does not support real rollback from Python once writes are committed.
        """
        if self.transaction_active:
            print("[LMDBManager] WARNING: LMDB rollback is not supported. No changes reverted.")
            self.transaction_active = False


    # -------------------------------------------------------------------------
    # Blockchain Storage: blocks, transactions
    # -------------------------------------------------------------------------
    def add_block(self, block_hash: str, block_header: dict, transactions: list, size: int, difficulty: int):
        """
        Add a block to the 'blocks' DB.
        The block is stored under key: "block:{block_hash}"
        """
        try:
            self.begin_transaction()

            if not isinstance(block_hash, str):
                print(f"[LMDBManager] ERROR: Invalid block_hash type: {type(block_hash)}. Expected str.")
                self.rollback()
                return

            # ✅ Serialize transactions safely
            serialized_transactions = []
            for tx in transactions:
                try:
                    tx_dict = tx.to_dict() if hasattr(tx, "to_dict") else tx
                    serialized_transactions.append(tx_dict)
                except Exception as e:
                    print(f"[LMDBManager] ERROR: Failed to serialize transaction: {e}")
                    self.rollback()
                    return

            # ✅ Block structure (no offset field)
            block_data = {
                "block_header": block_header,
                "transactions": serialized_transactions,
                "size": size,
                "difficulty": difficulty
            }

            key = f"block:{block_hash}".encode("utf-8")

            try:
                value = json.dumps(block_data).encode("utf-8")
            except (TypeError, ValueError) as json_error:
                print(f"[LMDBManager] ERROR: JSON Encoding Failed for block {block_hash}: {json_error}")
                self.rollback()
                return

            # ✅ Store in LMDB
            with self.env.begin(write=True, db=self.blocks_db) as txn:
                txn.put(key, value)

                # ✅ Optional: Store latest block index (if 'index' is part of block_header)
                index = block_header.get("index")
                if index is not None:
                    txn.put(b"latest_block_index", str(index).encode("utf-8"), db=self.metadata_db)

            self.commit()
            print(f"[LMDBManager] SUCCESS: Block {block_hash} stored successfully.")

        except Exception as e:
            self.rollback()
            print(f"[LMDBManager] ERROR: Failed to store block {block_hash}: {e}")
            raise


    def get_block_by_index(self, index: int) -> Optional[dict]:
        try:
            key = f"blockmeta:{index}".encode("utf-8")
            metadata = self.get(key, db=self.metadata_db)
            if not metadata:
                return None
            block_hash = metadata.get("hash")
            if not block_hash:
                return None
            return self.get(f"block:{block_hash}", db=self.blocks_db)
        except Exception as e:
            print(f"[LMDBManager] ERROR: Failed to get block by index {index}: {e}")
            return None

    def put(self, key: Union[str, bytes, bytearray, memoryview], value: dict, db=None) -> bool:
        """
        Store a JSON-serialized value in LMDB by key.

        Args:
            key (Union[str, bytes, bytearray, memoryview]): The key to store.
            value (dict): The data to store (must be JSON-serializable).
            db: The database handle to use (defaults to self.blocks_db).

        Returns:
            bool: True if the data was stored successfully, False otherwise.
        """
        db_handle = db or self.blocks_db

        # ✅ Normalize key to bytes
        if isinstance(key, str):
            key_bytes = key.encode("utf-8")
        elif isinstance(key, (bytes, bytearray)):
            key_bytes = bytes(key)
        elif isinstance(key, memoryview):
            try:
                key_bytes = key.tobytes()
            except Exception as e:
                print(f"[LMDBManager] ❌ ERROR: Failed to convert memoryview to bytes: {e}")
                return False
        else:
            print(f"[LMDBManager] ❌ ERROR: Invalid key type: {type(key)}. Expected str, bytes, bytearray, or memoryview.")
            return False

        # ✅ Safe key string for logs
        try:
            key_str = key_bytes.decode("utf-8", errors="ignore")
        except Exception:
            key_str = str(key_bytes)

        # ✅ Validate value
        if not isinstance(value, dict):
            print(f"[LMDBManager] ❌ ERROR: Invalid value type: {type(value)}. Expected dict.")
            return False

        # ✅ Serialize with fallback for bytes, Decimal, sets, etc.
        try:
            value_json = json.dumps(value, default=lambda x: (
                x.hex() if isinstance(x, bytes)
                else str(x) if isinstance(x, (set, Decimal, Exception))
                else list(x) if isinstance(x, (tuple, range))
                else None  # fallback to None for unknown
            )).encode("utf-8")
        except (TypeError, ValueError) as e:
            print(f"[LMDBManager] ❌ ERROR: Failed to serialize value for key {key_str}: {e}")
            return False

        # ✅ Store in LMDB
        try:
            with self.env.begin(write=True, db=db_handle) as txn:
                txn.put(key_bytes, value_json)
            print(f"[LMDBManager] ✅ SUCCESS: Stored key: {key_str}")
            return True
        except Exception as e:
            print(f"[LMDBManager] ❌ ERROR: Failed to store key {key_str}: {e}")
            return False


    def get(self, key: Union[str, bytes, bytearray, memoryview], db=None):
        """
        Retrieve a JSON-serialized value from LMDB by key.

        Args:
            key (Union[str, bytes, bytearray, memoryview]): The key to retrieve.
            db: The database handle to use (defaults to self.blocks_db).

        Returns:
            dict | None: Deserialized JSON data, or None if the key is invalid or data is corrupted.
        """
        db_handle = db or self.blocks_db

        # ✅ Normalize key to bytes
        if isinstance(key, str):
            key_bytes = key.encode("utf-8")
        elif isinstance(key, (bytes, bytearray)):
            key_bytes = bytes(key)
        elif isinstance(key, memoryview):
            try:
                key_bytes = key.tobytes()
            except Exception as e:
                print(f"[LMDB ERROR] ❌ Failed to convert memoryview to bytes: {e}")
                return None
        else:
            print(f"[LMDB ERROR] ❌ Invalid key type: {type(key)}. Expected str, bytes, bytearray, or memoryview.")
            return None

        # ✅ For logging and fallback decoding
        try:
            key_str = key_bytes.decode("utf-8", errors="ignore")
        except Exception:
            key_str = str(key_bytes)

        try:
            with self.env.begin(db=db_handle) as txn:
                value = txn.get(key_bytes)

                if value is None:
                    print(f"[LMDB WARNING] ⚠️ Key not found: {key_str}")
                    return None

                # ✅ Try UTF-8 JSON decode
                try:
                    return json.loads(value.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    print(f"[LMDB WARNING] ⚠️ Non-UTF-8 or corrupted JSON for key {key_str}. Trying fallback conversions...")

                    # 🛠️ Attempt to repair via fallback decoding
                    try:
                        fallback_str = value.decode("latin1")
                        return json.loads(fallback_str)
                    except Exception as e2:
                        print(f"[LMDB ERROR] ❌ Final fallback decode failed for key {key_str}: {e2}")
                        return None

        except Exception as e:
            print(f"[LMDB ERROR] ❌ Exception while retrieving key {key_str}: {e}")
            return None

        
    def get_all_blocks(self) -> List[dict]:
        """
        Retrieve all blocks stored in the 'blocks' LMDB DB.
        Fallbacks:
        - Use `block_metadata_db` if full block data is incomplete.
        - Ensures robust loading from either LMDB source.
        """
        blocks = []
        try:
            print("[LMDBManager.get_all_blocks] INFO: Scanning full_block_store for all blocks...")

            with self.full_block_store.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    try:
                        key_str = key.decode("utf-8")
                        if not key_str.startswith("block:"):
                            continue

                        block_dict = json.loads(value.decode("utf-8"))

                        if not isinstance(block_dict, dict):
                            print(f"[LMDB WARNING] ⚠️ Malformed block data at {key_str}. Skipping.")
                            continue

                        blocks.append(block_dict)

                    except (UnicodeDecodeError, json.JSONDecodeError) as e:
                        print(f"[LMDB ERROR] ❌ Failed to parse block {key}: {e}")

            if blocks:
                print(f"[LMDBManager.get_all_blocks] ✅ Retrieved {len(blocks)} blocks from full_block_store.")
                return sorted(blocks, key=lambda b: b.get("index", 0))

            print("[LMDBManager.get_all_blocks] ⚠️ No full blocks found. Attempting fallback to block_metadata_db...")

            # Fallback: Scan block_metadata DB
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.startswith(b"blockmeta:"):
                        try:
                            metadata = json.loads(value.decode("utf-8"))
                            if isinstance(metadata, dict):
                                # Fill basic structure if full block is missing
                                fallback_block = {
                                    "header": {
                                        "index": metadata.get("index"),
                                        "timestamp": metadata.get("timestamp"),
                                        "difficulty": metadata.get("difficulty"),
                                        "previous_hash": metadata.get("previous_hash"),
                                        "merkle_root": metadata.get("merkle_root"),
                                        "miner_address": metadata.get("miner_address"),
                                        "transaction_count": metadata.get("transaction_count", 0),
                                        "total_fees": metadata.get("total_fees", "0"),
                                    },
                                    "transactions": [],
                                    "hash": metadata.get("hash"),
                                    "index": metadata.get("index"),
                                }
                                blocks.append(fallback_block)
                        except Exception as fallback_error:
                            print(f"[LMDBManager.get_all_blocks] ⚠️ Failed to parse fallback metadata: {fallback_error}")

            print(f"[LMDBManager.get_all_blocks] ⚠️ Fallback: Retrieved {len(blocks)} blocks from metadata DB.")
            return sorted(blocks, key=lambda b: b.get("index", 0))

        except Exception as e:
            print(f"[LMDBManager.get_all_blocks] ❌ ERROR: Failed to retrieve blocks: {e}")
            return []



    def delete_block(self, block_hash: str):
        """
        Delete a block from the 'blocks' DB by block_hash.
        """
        with self.env.begin(write=True, db=self.blocks_db) as txn:
            txn.delete(f"block:{block_hash}".encode())
        print(f"[LMDB] ✅ Block {block_hash} deleted from 'blocks' DB.")

    # -------------------------------------------------------------------------
    # Transactions Database
    # -------------------------------------------------------------------------


    def add_transaction(self, tx_id: Union[str, bytes], block_hash: str, inputs: List[Dict], outputs: List[Dict], timestamp: int):
        """
        Store a transaction in the 'transactions' DB.
        Key: "tx:{tx_id}"
        Value: JSON with block_hash, inputs, outputs, timestamp.
        """
        try:
            # ✅ Ensure tx_id is properly handled (convert bytes to string safely)
            if isinstance(tx_id, bytes):
                try:
                    tx_id = tx_id.decode("utf-8")  # Convert bytes to string safely
                except UnicodeDecodeError as decode_error:
                    print(f"[LMDB ERROR] ❌ Failed to decode tx_id {tx_id}: {decode_error}")
                    return

            if not isinstance(tx_id, str):
                print(f"[LMDB ERROR] ❌ Invalid tx_id format: Expected str, got {type(tx_id)}")
                return

            # ✅ Convert CoinbaseTx objects in inputs/outputs to dictionaries before storing
            def convert_to_dict(tx):
                return tx.to_dict() if hasattr(tx, "to_dict") else tx

            inputs_converted = [convert_to_dict(tx) for tx in inputs]
            outputs_converted = [convert_to_dict(tx) for tx in outputs]

            # ✅ Prepare transaction data safely
            transaction_data = {
                "block_hash": block_hash,
                "inputs": inputs_converted,
                "outputs": outputs_converted,
                "timestamp": int(timestamp) if isinstance(timestamp, int) else 0
            }

            # ✅ Generate LMDB key correctly
            key = f"tx:{tx_id}".encode("utf-8")  # Always convert `tx_id` to a string before encoding

            try:
                value = json.dumps(transaction_data).encode("utf-8")
            except (TypeError, ValueError) as json_error:
                print(f"[LMDB ERROR] ❌ JSON Encoding Failed for transaction {tx_id}: {json_error}")
                return

            # ✅ Store transaction in LMDB safely
            with self.env.begin(write=True, db=self.transactions_db) as txn:
                txn.put(key, value)

            print(f"[LMDB] ✅ Transaction {tx_id} stored successfully.")

        except Exception as e:
            print(f"[LMDB ERROR] ❌ Unexpected error while storing transaction {tx_id}: {e}")
            raise


    def close(self):
        """Close the LMDB environment."""
        if hasattr(self, 'env'):
            self.env.close()
        print("[LMDBManager] Database environment closed.")


    def create_dir_if_not_exists(path):
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"Created database directory: {path}")
