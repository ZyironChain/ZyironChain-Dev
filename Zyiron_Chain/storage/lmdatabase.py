from contextlib import contextmanager
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



import os
import lmdb
from typing import Optional

class LMDBManager:
    _environments = {}  # Singleton registry for environments

    def __init__(self, db_path: Optional[str] = None, max_readers: int = 200, max_dbs: int = 10, writemap: bool = False):
        """
        Initialize the LMDB environment.

        Args:
            db_path (Optional[str]): Path to the LMDB database directory.
            max_readers (int): Maximum number of readers for the LMDB environment.
            max_dbs (int): Maximum number of sub-databases.
            writemap (bool): Use writemap for faster writes (requires sufficient memory).
        """
        db_path = db_path or os.path.join(Constants.BLOCKCHAIN_STORAGE_PATH, Constants.NETWORK_FOLDER)
        self.db_path = os.path.abspath(db_path)
        self.max_readers = max_readers
        self.max_dbs = max_dbs
        self.writemap = writemap
        self.path = self.db_path  # Store for future reference

        parent_dir = os.path.dirname(self.db_path)
        if parent_dir and parent_dir != self.db_path:
            try:
                os.makedirs(parent_dir, exist_ok=True)
                print(f"[LMDBManager] Created database directory: {parent_dir}")
            except OSError as e:
                print(f"[LMDBManager] ❌ ERROR: Failed to create directory {parent_dir}: {str(e)}")
                raise

        if os.name == "nt":
            os.environ["LMDB_USE_WINDOWS_MUTEX"] = "1"

        # ✅ Check for reused environment or open new one
        existing_env = LMDBManager._environments.get(self.db_path)
        if existing_env:
            try:
                with existing_env.begin():  # Try to open a read txn
                    self.env = existing_env
                    print(f"[LMDBManager] Reused existing LMDB environment at {self.db_path}")
            except lmdb.Error as reuse_error:
                print(f"[LMDBManager] ⚠️ WARNING: Existing LMDB env at {self.db_path} is invalid. Reopening... ({reuse_error})")
                try:
                    del LMDBManager._environments[self.db_path]
                except Exception:
                    pass
                self.env = self._open_env()
        else:
            self.env = self._open_env()

        LMDBManager._environments[self.db_path] = self.env

        # ✅ Initialize DB handles with fallback
        try:
            with self.env.begin(write=True) as txn:
                self.mempool_db = self.env.open_db(b"mempool", txn=txn)
                self.blocks_db = self.env.open_db(b"blocks", txn=txn)
                self.transactions_db = self.env.open_db(b"transactions", txn=txn)
                self.metadata_db = self.env.open_db(b"metadata", txn=txn)

            print("[LMDBManager] ✅ Database handles initialized successfully.")
        except lmdb.Error as e:
            print(f"[LMDBManager] ❌ ERROR: Database handle initialization failed: {str(e)}")
            self.close()
            raise

        # ✅ Perform capacity verification
        try:
            self._verify_capacity()
            print("[LMDBManager] INFO: Capacity check completed.")
        except Exception as e:
            print(f"[LMDBManager] ⚠️ WARNING: Capacity check failed: {e}")


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
                    print(f"[LMDBManager] INFO: Increased LMDB map_size to {new_size} bytes due to high usage ({file_usage * 100:.2f}%).")

            print("[LMDBManager] INFO: Capacity check completed.")

        except lmdb.Error as e:
            print(f"[LMDBManager] ERROR: Failed to verify LMDB capacity: {e}")


    def get_all_transactions(self) -> List[Dict]:
        """
        Retrieve all transactions from the LMDB database.
        Returns a list of transaction dictionaries.
        """
        transactions = []

        try:
            with self.safe_transaction(db=self.transactions_db) as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    try:
                        key_str = key.decode("utf-8", errors="ignore")
                        if key_str.startswith("tx:"):
                            try:
                                tx_data = value.decode("utf-8", errors="ignore")
                                tx_dict = json.loads(tx_data)
                                if isinstance(tx_dict, dict):
                                    transactions.append(tx_dict)
                                else:
                                    print(f"[LMDBManager] WARNING: Skipping invalid transaction entry {key_str}: Not a dictionary.")
                            except json.JSONDecodeError as json_error:
                                print(f"[LMDBManager] WARNING: Skipping corrupt transaction entry {key_str}: {json_error}")
                    except UnicodeDecodeError as decode_error:
                        print(f"[LMDBManager] ERROR: Failed to decode key {key}: {decode_error}")

            print(f"[LMDBManager] INFO: Retrieved {len(transactions)} valid transactions.")
            return transactions

        except lmdb.Error as e:
            if "closed" in str(e).lower() or "bad" in str(e).lower():
                print(f"[LMDBManager] WARNING: Transactions DB closed. Attempting recovery: {e}")
                self._open_env()  # Reopen the environment safely
                return self.get_all_transactions()  # 🔁 Retry once
            print(f"[LMDBManager] ERROR: LMDB failure: {e}")
            return []

        except Exception as e:
            print(f"[LMDBManager] ERROR: Unexpected error while retrieving transactions: {e}")
            return []






    def _initialize_databases(self):
        """
        Safely initializes all required LMDB database handles for the current network.
        Only opens databases if they are not already opened.
        Includes retry and environment recovery logic if the LMDB is closed or invalid.
        """
        try:
            print("[LMDBManager] INFO: Initializing LMDB databases...")

            network = Constants.NETWORK
            config = Constants.NETWORK_DATABASES.get(network)

            if not config:
                raise ValueError(f"[LMDBManager] ❌ ERROR: No LMDB config found for network: {network}")

            try:
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

                print(f"[LMDBManager] ✅ SUCCESS: All LMDB databases initialized for {network.upper()}.")

            except lmdb.Error as inner_e:
                if "closed" in str(inner_e).lower() or "bad" in str(inner_e).lower():
                    print(f"[LMDBManager] WARNING: LMDB was closed or invalid. Attempting environment recovery: {inner_e}")
                    self._open_env()  # 🔄 Recover LMDB
                    self._initialize_databases()  # 🔁 Retry once
                else:
                    raise inner_e

        except Exception as e:
            print(f"[LMDBManager] ❌ ERROR: Failed to initialize LMDB databases: {e}")
            try:
                self.env.close()
            except:
                pass
            raise


    def get_database_status(self) -> dict:
        """
        Return current database usage statistics such as used databases,
        map size, and free space. Recovers from closed environments.
        """
        try:
            with self.safe_transaction() as txn:
                env_info = self.env.info()
                txn_stats = txn.stat()

                map_size = env_info.get("map_size", 0)
                used_pages = env_info.get("last_pgno", 0)
                page_size = env_info.get("psize", 4096)

                free_space = map_size - (used_pages * page_size)

                return {
                    "max_databases": env_info.get("max_dbs", 0),
                    "used_entries": txn_stats.get("entries", 0),
                    "map_size_bytes": map_size,
                    "free_space_bytes": free_space
                }

        except Exception as e:
            print(f"[LMDBManager] ❌ ERROR: Failed to retrieve database status: {e}")
            return {}


    def get_db_path(self, db_name: str) -> str:
        """
        Returns the full path for the specified database name.
        """
        try:
            db_path = os.path.join(Constants.BLOCKCHAIN_STORAGE_PATH, db_name)
            print(f"[LMDBManager] INFO: Database path for '{db_name}': {db_path}")
            return db_path
        except Exception as e:
            print(f"[LMDBManager] ❌ ERROR: Failed to construct path for {db_name}: {e}")
            return ""


    def fetch_all_pending_transactions(self) -> list:
        """
        Retrieve all pending transactions stored in the mempool DB.
        Includes fallback for JSON decoding issues and env recovery.
        """
        pending_transactions = []

        try:
            with self.safe_transaction(db=self.mempool_db) as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    try:
                        key_str = key.decode("utf-8", errors="ignore")
                        if key_str.startswith("mempool:pending_tx:"):
                            try:
                                tx_data = json.loads(value.decode("utf-8"))
                                pending_transactions.append(tx_data)
                            except json.JSONDecodeError as e:
                                print(f"[LMDBManager] ⚠️ Skipping corrupt transaction {key_str}: {e}")
                    except UnicodeDecodeError as key_err:
                        print(f"[LMDBManager] ❌ ERROR decoding key in mempool: {key_err}")

            print(f"[LMDBManager] ✅ Retrieved {len(pending_transactions)} pending transactions.")
            return pending_transactions

        except lmdb.Error as e:
            print(f"[LMDBManager] ❌ ERROR: LMDB retrieval failed: {e}")
            return []


    def add_pending_transaction(self, transaction: dict):
        """
        Add a pending transaction to the mempool DB using safe_transaction.
        """
        try:
            tx_id = transaction.get("tx_id")
            if not tx_id:
                print("[LMDBManager] ❌ ERROR: Transaction missing 'tx_id'.")
                return

            key = f"mempool:pending_tx:{tx_id}".encode("utf-8")

            try:
                value = json.dumps(transaction).encode("utf-8")
            except (TypeError, ValueError) as json_error:
                print(f"[LMDBManager] ❌ ERROR: Failed to encode transaction {tx_id}: {json_error}")
                return

            with self.safe_transaction(db=self.mempool_db) as txn:
                txn.put(key, value)

            print(f"[LMDBManager] ✅ INFO: Pending transaction {tx_id} stored successfully.")
        except Exception as e:
            print(f"[LMDBManager] ❌ ERROR: Failed to store pending transaction: {e}")


    def delete_pending_transaction(self, tx_id: str):
        """
        Remove a pending transaction from the mempool DB using safe_transaction.
        """
        try:
            key = f"mempool:pending_tx:{tx_id}".encode("utf-8")

            with self.safe_transaction(db=self.mempool_db) as txn:
                txn.delete(key)

            print(f"[LMDBManager] ✅ INFO: Pending transaction {tx_id} removed from mempool.")
        except Exception as e:
            print(f"[LMDBManager] ❌ ERROR: Failed to remove pending transaction {tx_id}: {e}")


    def begin_transaction(self):
        """
        Begin a simulated transaction for tracking transaction state.
        """
        if not hasattr(self, "transaction_active"):
            self.transaction_active = False

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

            # ✅ Block structure
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

            # ✅ Safe write transaction with auto-reopen support
            with self.safe_transaction(write=True, db=self.blocks_db) as txn:
                txn.put(key, value)

                # ✅ Optional: Store latest block index (if present)
                index = block_header.get("index")
                if index is not None:
                    txn.put(b"latest_block_index", str(index).encode("utf-8"), db=self.metadata_db)

            self.commit()
            print(f"[LMDBManager] ✅ SUCCESS: Block {block_hash} stored successfully.")

        except Exception as e:
            self.rollback()
            print(f"[LMDBManager] ❌ ERROR: Failed to store block {block_hash}: {e}")
            raise



    def get_block_by_index(self, index: int) -> Optional[dict]:
        """
        Retrieve a block by its index from metadata and then fetch the full block using its hash.

        Args:
            index (int): Block height/index to retrieve.

        Returns:
            dict | None: The full block data if found, else None.
        """
        try:
            key = f"blockmeta:{index}".encode("utf-8")
            metadata = self.get(key, db=self.metadata_db)

            if not metadata or not isinstance(metadata, dict):
                print(f"[LMDBManager] ⚠️ WARNING: Metadata missing or invalid for block index {index}.")
                return None

            block_hash = metadata.get("hash")
            if not block_hash or not isinstance(block_hash, str):
                print(f"[LMDBManager] ⚠️ WARNING: Block hash not found in metadata for index {index}.")
                return None

            full_block = self.get(f"block:{block_hash}", db=self.blocks_db)

            if full_block is None:
                print(f"[LMDBManager] ⚠️ WARNING: Full block not found for hash {block_hash}.")
            else:
                print(f"[LMDBManager] ✅ SUCCESS: Retrieved block at index {index} with hash {block_hash}.")

            return full_block

        except Exception as e:
            print(f"[LMDBManager] ❌ ERROR: Failed to get block by index {index}: {e}")
            return None


    def put(self, key: Union[str, bytes, bytearray, memoryview], value: dict, db=None) -> bool:
        """
        Store a JSON-serializable value in LMDB under the given key.

        Args:
            key: Key to store the value under.
            value: Dictionary to store.
            db: Optional LMDB DB handle. Defaults to self.blocks_db.

        Returns:
            bool: True if successful, False otherwise.
        """
        db_handle = db or getattr(self, "blocks_db", None)

        # ✅ Normalize key
        try:
            if isinstance(key, str):
                key_bytes = key.encode("utf-8")
            elif isinstance(key, (bytes, bytearray)):
                key_bytes = bytes(key)
            elif isinstance(key, memoryview):
                key_bytes = key.tobytes()
            else:
                print(f"[LMDBManager.put] ❌ ERROR: Invalid key type: {type(key)}")
                return False
        except Exception as e:
            print(f"[LMDBManager.put] ❌ ERROR: Failed to normalize key: {e}")
            return False

        # ✅ Serialize value to JSON
        try:
            value_json = json.dumps(value, sort_keys=True).encode("utf-8")
        except Exception as e:
            print(f"[LMDBManager.put] ❌ ERROR: Failed to serialize value: {e}")
            return False

        # 🔁 Auto-reopen if env is stale
        if not self.env or not getattr(self.env, "_handle", None):
            print("[LMDBManager.put] ⚠️ LMDB environment appears closed. Reopening...")
            try:
                self.reopen()
            except Exception as reopen_error:
                print(f"[LMDBManager.put] ❌ ERROR: Failed to reopen LMDB before put: {reopen_error}")
                return False

        # 🚀 Attempt write transaction
        try:
            with self.env.begin(write=True, db=db_handle) as txn:
                txn.put(key_bytes, value_json)
            print(f"[LMDBManager.put] ✅ SUCCESS: Stored key: {key_bytes[:50]}")
            return True
        except lmdb.Error as e:
            print(f"[LMDBManager.put] ❌ ERROR: LMDB write error: {e}")
            print("[LMDBManager.put] ⚠️ Attempting to reopen environment and retry...")

            try:
                self.reopen()
                with self.env.begin(write=True, db=db_handle) as txn:
                    txn.put(key_bytes, value_json)
                print(f"[LMDBManager.put] ✅ SUCCESS: Retried and stored key: {key_bytes[:50]}")
                return True
            except Exception as retry_e:
                print(f"[LMDBManager.put] ❌ Retried put failed: {retry_e}")
                return False



    def get(self, key: Union[str, bytes, bytearray, memoryview], db=None):
        """
        Retrieve a JSON-serialized value from LMDB by key, with maximum fallback logic.

        Args:
            key (Union[str, bytes, bytearray, memoryview]): The key to retrieve.
            db: Optional LMDB database handle. Defaults to self.blocks_db.

        Returns:
            dict | None: Deserialized JSON object if found and valid; otherwise None.
        """
        db_handle = db or getattr(self, "blocks_db", None)

        # ✅ Normalize key to bytes
        try:
            if isinstance(key, str):
                key_bytes = key.encode("utf-8")
            elif isinstance(key, (bytes, bytearray)):
                key_bytes = bytes(key)
            elif isinstance(key, memoryview):
                key_bytes = key.tobytes()
            else:
                print(f"[LMDB.get] ❌ ERROR: Invalid key type: {type(key)}. Must be str, bytes, bytearray, or memoryview.")
                return None
        except Exception as e:
            print(f"[LMDB.get] ❌ ERROR: Failed to normalize key: {e}")
            return None

        key_str = key_bytes.decode("utf-8", errors="ignore")

        # 🔄 Auto-reopen LMDB if env is closed or stale
        if not self.env or not getattr(self.env, "_handle", None):
            print(f"[LMDB.get] ⚠️ LMDB environment appears closed. Reopening before transaction...")
            try:
                self.reopen()
            except Exception as reopen_error:
                print(f"[LMDB.get] ❌ ERROR: Failed to reopen LMDB before read: {reopen_error}")
                return None

        # 🛡️ Attempt to read from LMDB
        try:
            with self.env.begin(db=db_handle) as txn:
                value = txn.get(key_bytes)

                if value is None:
                    print(f"[LMDB.get] ⚠️ WARNING: Key not found: {key_str}")
                    return None

                # ✅ Try decoding as UTF-8 JSON
                try:
                    return json.loads(value.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    print(f"[LMDB.get] ⚠️ WARNING: UTF-8 decode failed for key: {key_str}. Trying fallback decodes...")

                    # 🧪 Try Latin-1 decode
                    try:
                        return json.loads(value.decode("latin1"))
                    except Exception as e2:
                        print(f"[LMDB.get] ⚠️ Fallback Latin-1 decode failed for key {key_str}: {e2}")

                        # 🧱 Last-ditch fallback: show partial bytes
                        print(f"[LMDB.get] ❌ ERROR: All decode attempts failed for key {key_str}. Raw bytes preview: {value[:30]}...")
                        return None

        except Exception as e:
            error_text = str(e)

            if "MDB_BAD_RSLOT" in error_text or "closed" in error_text.lower():
                print(f"[LMDB.get] ⚠️ LMDB reader error: {error_text}. Attempting to reopen environment...")

                try:
                    self.reopen()
                    with self.env.begin(db=db_handle) as txn:
                        value = txn.get(key_bytes)
                        if value is None:
                            print(f"[LMDB.get] ⚠️ Retried: Key not found: {key_str}")
                            return None
                        return json.loads(value.decode("utf-8"))
                except Exception as re_e:
                    print(f"[LMDB.get] ❌ ERROR: Retry after reopen failed for key {key_str}: {re_e}")
                    return None
            else:
                print(f"[LMDB.get] ❌ ERROR: Unexpected LMDB exception for key {key_str}: {e}")
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


    def create_dir_if_not_exists(path):
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"Created database directory: {path}")


    @staticmethod
    def close_all():
        print("[LMDBManager] INFO: Closing all LMDB environments globally...")
        for path, env in list(LMDBManager._environments.items()):
            try:
                env.close()
                print(f"[LMDBManager] Closed LMDB environment at {path}")
            except Exception as e:
                print(f"[LMDBManager] ERROR closing {path}: {e}")
        LMDBManager._environments.clear()

    def _open_env(self):
        """
        Fallback method to reinitialize LMDB environment if it is missing or closed.
        """
        if not hasattr(self, "env") or self.env is None:
            print("[LMDBManager._open_env] WARNING: Environment not found. Reinitializing LMDB environment.")
            try:
                self.env = lmdb.open(
                    path=self.db_path,
                    map_size=Constants.LMDB_MAP_SIZE,
                    max_readers=self.max_readers,
                    max_dbs=self.max_dbs,
                    writemap=self.writemap,
                    create=True,
                    readahead=False,
                    meminit=False
                )
                LMDBManager._environments[self.db_path] = self.env
                print(f"[LMDBManager._open_env] ✅ SUCCESS: Reopened LMDB environment at {self.db_path}")
            except Exception as e:
                print(f"[LMDBManager._open_env] ❌ ERROR: Failed to reopen LMDB: {e}")
                self.env = None
                raise RuntimeError("LMDB reinitialization failed.") from e
        else:
            print(f"[LMDBManager._open_env] INFO: Environment already active at {self.db_path}")
        
        return self.env



    @contextmanager
    def safe_transaction(self, write=False, db=None):
        """
        Ensures the LMDB environment is open before performing any transaction.
        Automatically reopens if needed.
        """
        try:
            # If env is closed or invalid, reopen it
            if not hasattr(self, "env") or self.env is None:
                print("[LMDBManager.safe_transaction] 🔄 Reinitializing LMDB environment...")
                self.env = self._open_env()

            db_handle = db or self.blocks_db
            with self.env.begin(write=write, db=db_handle) as txn:
                yield txn
        except lmdb.Error as e:
            print(f"[LMDBManager.safe_transaction] ❌ LMDB error during transaction: {e}")
            self._open_env()
            raise

    @staticmethod
    def reopen_all():
        """
        Reopen any closed or inactive LMDB environments.
        """
        print("[LMDBManager] 🔄 Attempting to reopen all LMDB environments...")
        for path, env in list(LMDBManager._environments.items()):
            try:
                with env.begin():
                    print(f"[LMDBManager] ✅ Environment active at {path}")
            except lmdb.Error:
                print(f"[LMDBManager] ⚠️ Environment at {path} is closed or invalid. Reopening...")
                try:
                    reopened_env = lmdb.open(
                        path=path,
                        map_size=Constants.LMDB_MAP_SIZE,
                        max_readers=200,
                        max_dbs=200,
                        writemap=False,
                        create=True,
                        readahead=False,
                        meminit=False
                    )
                    LMDBManager._environments[path] = reopened_env
                    print(f"[LMDBManager] ✅ Reopened LMDB environment at {path}")
                except Exception as e:
                    print(f"[LMDBManager] ❌ ERROR: Failed to reopen environment at {path}: {e}")
