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

class LMDBManager:
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize LMDB with network-aware configuration.

        :param db_path: Optional path to the LMDB environment. If not provided,
                        defaults to the path derived from Constants.
        """
        # ---------------------------------------------------------------------
        # 1. Construct the DB path from the network folder if no path is given.
        # ---------------------------------------------------------------------
        db_path = db_path or os.path.join(Constants.BLOCKCHAIN_STORAGE_PATH, Constants.NETWORK_FOLDER)
        db_path = os.path.abspath(db_path)
        parent_dir = os.path.dirname(db_path)

        # ---------------------------------------------------------------------
        # 2. Ensure the parent directory exists (if any).
        # ---------------------------------------------------------------------
        if parent_dir and parent_dir != db_path:
            try:
                os.makedirs(parent_dir, exist_ok=True)
                print(f"Created database directory: {parent_dir}")
            except OSError as e:
                print(f"Failed to create directory {parent_dir}: {str(e)}")
                raise

        # ---------------------------------------------------------------------
        # 3. Configure and open the LMDB environment.
        # ---------------------------------------------------------------------
        try:
            self.env = lmdb.open(
                path=db_path,
                map_size=Constants.MEMPOOL_MAX_SIZE_MB * 1024 * 1024,  # Max size in MB from constants
                create=True,
                readahead=False,
                writemap=True,
                meminit=False,
                max_dbs=Constants.MAX_LMDB_DATABASES
            )
        except lmdb.Error as e:
            print(f"LMDB environment creation failed: {str(e)}")
            raise

        # ---------------------------------------------------------------------
        # 4. Initialize named databases in this environment.
        #    We do this once in the constructor to avoid re-opening DBs.
        # ---------------------------------------------------------------------
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

        # ---------------------------------------------------------------------
        # 5. Simulated transaction states. LMDB auto-commits, so these are only
        #    placeholders. We keep them for compatibility if other code calls
        #    them, but you must note they are not real rollback/commit.
        # ---------------------------------------------------------------------
        self.transaction_active = False

        # Run capacity check for warnings if nearing limit.
        self._verify_capacity()

    # -------------------------------------------------------------------------
    # Potentially remove or rename this if you don’t need to re-initialize DBs
    # after the constructor. If no code calls it, you can safely remove it.
    # -------------------------------------------------------------------------


    def get_all_transactions(self) -> List[Dict]:
        """
        Retrieve all transactions from the LMDB database.
        Returns a list of transaction dictionaries.
        """
        transactions = []
        try:
            with self.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    try:
                        key_str = key.decode("utf-8")
                        if key_str.startswith("tx:"):  # Filter for transaction keys
                            tx_data = value.decode("utf-8")
                            tx_dict = json.loads(tx_data)
                            transactions.append(tx_dict)
                    except Exception as e:
                        print(f"[LMDBManager.get_all_transactions] ERROR: Failed to process key {key}: {e}")
            print(f"[LMDBManager.get_all_transactions] INFO: Retrieved {len(transactions)} transactions.")
            return transactions
        except Exception as e:
            print(f"[LMDBManager.get_all_transactions] ERROR: Failed to retrieve transactions: {e}")
            return []




    def _initialize_databases(self):
        """
        (Optional) Re-initializes the LMDB databases.
        NOTE: If called more than once, you might be re-opening DB handles.
        Only use if absolutely necessary after the constructor.
        """
        try:
            with self.env.begin(write=True) as txn:
                self.mempool_db = self.env.open_db(b"mempool", txn=txn)
                self.blocks_db = self.env.open_db(b"blocks", txn=txn)
                self.transactions_db = self.env.open_db(b"transactions", txn=txn)
                self.metadata_db = self.env.open_db(b"metadata", txn=txn)
                # If you need a separate smart mempool DB, you can open it here as well:
                # self.smart_mempool_db = self.env.open_db(b"smart_mempool", txn=txn)

            print("[INFO] LMDB databases re-initialized successfully.")
        except lmdb.Error as e:
            print(f"Database re-initialization failed: {str(e)}")
            self.env.close()
            raise

    def _verify_capacity(self):
        """
        Check database limits. This warns if the number of key entries
        is beyond 80% of the maximum database count. This is approximate
        and may not reflect true file size usage.
        """
        with self.env.begin() as txn:
            stats = txn.stat()
            # This is a simplistic approach: 'entries' vs. MAX_LMDB_DATABASES
            capacity = stats["entries"] / Constants.MAX_LMDB_DATABASES
            if capacity > 0.8:
                print(f"LMDB at {capacity:.0%} capacity (entries vs max_dbs).")

    def get_database_status(self):
        """
        Return current database usage statistics such as used_databases,
        map_size, free_space, etc.
        """
        with self.env.begin() as txn:
            return {
                "max_databases": self.env.info()["max_dbs"],
                "used_databases": txn.stat()["entries"],
                "map_size": self.env.info()["map_size"],
                "free_space": self.env.info()["map_size"]
                             - self.env.info()["last_pgno"] * self.env.info()["psize"]
            }

    # -------------------------------------------------------------------------
    # Basic Key-Value retrieval. For more advanced usage, your StorageManager
    # might wrap these calls with domain logic.
    # -------------------------------------------------------------------------

    def get(self, key: str, db=None):
        """
        Retrieve a JSON-serialized value from LMDB by key.

        :param key: The key (string) to retrieve.
        :param db: Which database handle to use. Defaults to self.blocks_db.
        :return: Deserialized JSON (dict) or None if not found.
        """
        db_handle = db or self.blocks_db
        
        if not isinstance(key, str):
            print(f"[STORAGE ERROR] ❌ Invalid key format: {key}. Expected a string.")
            return None

        key_encoded = key.encode("utf-8")

        try:
            with self.env.begin(db=db_handle) as txn:
                value = txn.get(key_encoded)

            if not value:
                print(f"[STORAGE] ⚠️ Key not found in LMDB: {key}")
                return None

            try:
                return json.loads(value.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as decode_error:
                print(f"[STORAGE ERROR] ❌ Corrupt JSON data for key {key}: {decode_error}")
                return None

        except Exception as e:
            print(f"[STORAGE ERROR] ❌ Failed to retrieve key {key}: {str(e)}")
            return None


    def get_db_path(self, db_name: str) -> str:
        """
        Returns the path for the specified database name.
        This can be used if you want to open a separate environment or
        just track where the base DB folder is, etc.
        """
        base_path = os.getcwd()
        db_path = os.path.join(base_path, "BlockData", db_name)
        print(f"[DEBUG] Database path for '{db_name}': {db_path}")
        return db_path

    # -------------------------------------------------------------------------
    # Mempool / Pending Transactions
    # -------------------------------------------------------------------------
    def fetch_all_pending_transactions(self) -> list:
        """
        Retrieve all pending transactions stored in the mempool DB.
        Each transaction is expected to be JSON-serialized.
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
                            print(f"[LMDB ERROR] ❌ Failed to decode transaction {key_str}: {e}")

            print(f"[LMDB] ✅ Retrieved {len(pending_transactions)} pending transactions.")
            return pending_transactions

        except lmdb.Error as e:
            print(f"[LMDB ERROR] ❌ LMDB retrieval failed: {e}")
            return []

    def add_pending_transaction(self, transaction: dict):
        """
        Add a pending transaction to the mempool DB.
        Transaction must be a dictionary containing at least 'tx_id'.
        """
        try:
            tx_id = transaction["tx_id"]
            key = f"mempool:pending_tx:{tx_id}".encode()
            value = json.dumps(transaction).encode("utf-8")

            with self.env.begin(write=True, db=self.mempool_db) as txn:
                txn.put(key, value)

            print(f"[LMDB] ✅ Pending transaction {tx_id} stored successfully.")
        except Exception as e:
            print(f"[LMDB ERROR] ❌ Failed to store pending transaction: {e}")

    def delete_pending_transaction(self, tx_id: str):
        """
        Remove a pending transaction from the mempool DB by tx_id.
        """
        try:
            key = f"mempool:pending_tx:{tx_id}".encode()
            with self.env.begin(write=True, db=self.mempool_db) as txn:
                txn.delete(key)

            print(f"[LMDB] ✅ Pending transaction {tx_id} removed from mempool.")
        except Exception as e:
            print(f"[LMDB ERROR] ❌ Failed to remove pending transaction {tx_id}: {e}")

    # -------------------------------------------------------------------------
    # Helper JSON (De)Serialization
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Simulated Transaction Methods
    # LMDB auto-commit is used, so these are mostly no-ops, but we keep them
    # for code compatibility if your system calls them.
    # -------------------------------------------------------------------------
    def begin_transaction(self):
        """Begin a simulated transaction."""
        if not self.transaction_active:
            print("[INFO] Starting LMDB transaction (simulated).")
            self.transaction_active = True

    def commit(self):
        """Commit a simulated transaction."""
        if self.transaction_active:
            print("[INFO] Committing LMDB transaction (simulated).")
            self.transaction_active = False

    def rollback(self):
        """
        Roll back a simulated transaction.
        LMDB does not support real rollback from Python once writes are done.
        We log a warning only.
        """
        if self.transaction_active:
            print("[WARNING] LMDB does not support rollback. This is a no-op.")
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

            block_data = {
                "block_header": block_header,
                "transactions": [
                    tx.to_dict() if hasattr(tx, "to_dict") else tx
                    for tx in transactions
                ],
                "size": size,
                "difficulty": difficulty
            }
            with self.env.begin(write=True, db=self.blocks_db) as txn:
                txn.put(f"block:{block_hash}".encode(), json.dumps(block_data).encode("utf-8"))

            self.commit()
            print(f"[INFO] Block {block_hash} stored successfully in LMDB.")
        except Exception as e:
            # If something went wrong, log it and simulate a rollback
            self.rollback()
            print(f"[ERROR] Failed to store block {block_hash}: {e}")
            raise

    def get_all_blocks(self) -> list:
        """
        Retrieve all blocks stored in the 'blocks' DB.
        Each block is expected to be JSON-serialized under "block:{some_hash}" keys.
        """
        blocks = []
        try:
            with self.env.begin(db=self.blocks_db) as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.decode().startswith("block:"):
                        blocks.append(json.loads(value.decode("utf-8")))
            print(f"[INFO] Retrieved {len(blocks)} blocks from LMDB.")
            return blocks
        except Exception as e:
            print(f"[ERROR] Failed to retrieve blocks from LMDB: {e}")
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
        Value: JSON with block_hash, inputs, outputs, timestamp
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

            # ✅ Prepare transaction data safely
            transaction_data = {
                "block_hash": block_hash,
                "inputs": inputs if isinstance(inputs, list) else [],
                "outputs": outputs if isinstance(outputs, list) else [],
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