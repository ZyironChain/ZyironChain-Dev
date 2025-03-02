import lmdb
import json
import time

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


# Add this at the top with other imports
import shutil  # Required for file operations



import lmdb
import json
import time
import logging

logging.basicConfig(level=logging.INFO)
from Zyiron_Chain.blockchain.constants import Constants


import lmdb
import json
import os
import logging
from Zyiron_Chain.blockchain.constants import Constants
import threading
from lmdb import open

import lmdb



class LMDBManager:
    def __init__(self, db_path=None):
        """Initialize LMDB with network-aware configuration"""
        
        # Use dynamic DB path based on the active network
        db_path = db_path or os.path.join(Constants.BLOCKCHAIN_STORAGE_PATH, Constants.NETWORK_FOLDER)
        
        # Convert to absolute path and validate
        db_path = os.path.abspath(db_path)
        parent_dir = os.path.dirname(db_path)
        
        # Create parent directory only if path contains subdirectories
        if parent_dir and parent_dir != db_path:
            try:
                os.makedirs(parent_dir, exist_ok=True)
                logging.info(f"Created database directory: {parent_dir}")
            except OSError as e:
                logging.error(f"Failed to create directory {parent_dir}: {str(e)}")
                raise

        # Configure environment with error handling
        try:
            self.env = lmdb.open(
                path=db_path,
                map_size=Constants.MEMPOOL_MAX_SIZE_MB * 1024 * 1024,  # Max size based on constants
                create=True,
                readahead=False,
                writemap=True,
                meminit=False,
                max_dbs=Constants.MAX_LMDB_DATABASES  # Use the value from Constants
            )
        except lmdb.Error as e:
            logging.error(f"LMDB environment creation failed: {str(e)}")
            raise

        # Initialize databases with explicit transaction
        try:
            with self.env.begin(write=True) as txn:
                # Open the databases defined in Constants dynamically
                self.mempool_db = self.env.open_db(b"mempool", txn=txn)
                self.blocks_db = self.env.open_db(b"blocks", txn=txn)
                self.transactions_db = self.env.open_db(b"transactions", txn=txn)
                self.metadata_db = self.env.open_db(b"metadata", txn=txn)
            logging.info("Database handles initialized successfully")
        except lmdb.Error as e:
            logging.error(f"Database initialization failed: {str(e)}")
            self.env.close()
            raise

        # State tracking
        self.transaction_active = False
        self._verify_capacity()

    def _initialize_databases(self):
        """Initializes the LMDB databases (block_data, mempool, etc.)"""
        try:
            with self.env.begin(write=True) as txn:
                # Open databases based on the dynamic naming convention
                self.mempool_db = self.env.open_db(b"mempool", txn=txn)
                self.blocks_db = self.env.open_db(b"blocks", txn=txn)
                self.transactions_db = self.env.open_db(b"transactions", txn=txn)
                self.metadata_db = self.env.open_db(b"metadata", txn=txn)
                self.smart_mempool_db = self.env.open_db(b"smart_mempool", txn=txn)  # Add smart_mempool
            logging.info("[INFO] LMDB databases initialized successfully.")
        except lmdb.Error as e:
            logging.error(f"Database initialization failed: {str(e)}")
            self.env.close()
            raise
    def get(self, key, db=None):
        """
        Retrieve a value from LMDB by key.
        
        Args:
            key (str): The key to retrieve.
            db (lmdb._Database): Optional database to query (defaults to blocks_db).
        
        Returns:
            dict: Deserialized data or None if not found.
        """
        try:
            with self.env.begin(db=db or self.blocks_db) as txn:
                value = txn.get(key.encode())
                return json.loads(value.decode()) if value else None
        except Exception as e:
            logging.error(f"Failed to retrieve key {key}: {str(e)}")
            return None

    def get_db_path(self, db_name):
        """Returns the path for the specified database"""
        
        # Ensure the correct network folder and path
        base_path = os.getcwd()  # This ensures the databases are created within your project
        db_path = os.path.join(base_path, "BlockData", db_name)  # Ensure smart_mempool is in BlockData
        logging.debug(f"[DEBUG] Database path for '{db_name}': {db_path}")
        
        return db_path

    def _verify_capacity(self):
        """Check database limits"""
        with self.env.begin() as txn:
            stats = txn.stat()
            capacity = stats["entries"] / Constants.MAX_LMDB_DATABASES  # Adjust this logic if necessary
            if capacity > 0.8:
                logging.warning(f"LMDB at {capacity:.0%} capacity")

    def get_database_status(self):
        """Return current database usage statistics"""
        with self.env.begin() as txn:
            return {
                "max_databases": self.env.info()["max_dbs"],
                "used_databases": txn.stat()["entries"],
                "map_size": self.env.info()["map_size"],
                "free_space": self.env.info()["map_size"] - self.env.info()["last_pgno"] * self.env.info()["psize"]
            }


    def fetch_all_pending_transactions(self):
        """
        Retrieve all pending transactions stored in LMDB.
        - Converts stored binary data into JSON format.
        - Returns a list of transaction dictionaries.
        
        :return: List of pending transaction dictionaries.
        """
        pending_transactions = []

        try:
            with self.env.begin(db=self.mempool_db) as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    key_str = key.decode()
                    if key_str.startswith("mempool:pending_tx:"):  # ✅ Use correct prefix
                        try:
                            tx_data = json.loads(value.decode("utf-8"))  # ✅ Convert binary data to JSON
                            pending_transactions.append(tx_data)
                        except json.JSONDecodeError as e:
                            logging.error(f"[LMDB ERROR] ❌ Failed to decode transaction {key_str}: {e}")

            logging.info(f"[LMDB] ✅ Retrieved {len(pending_transactions)} pending transactions.")
            return pending_transactions

        except lmdb.Error as e:
            logging.error(f"[LMDB ERROR] ❌ LMDB retrieval failed: {e}")
            return []

    def add_pending_transaction(self, transaction):
        """
        Add a pending transaction to LMDB.
        """
        try:
            tx_id = transaction["tx_id"]
            key = f"mempool:pending_tx:{tx_id}".encode()
            value = json.dumps(transaction).encode("utf-8")

            with self.env.begin(write=True, db=self.mempool_db) as txn:
                txn.put(key, value)

            logging.info(f"[LMDB] ✅ Pending transaction {tx_id} stored successfully.")

        except Exception as e:
            logging.error(f"[LMDB ERROR] ❌ Failed to store pending transaction {tx_id}: {e}")

    def delete_pending_transaction(self, tx_id):
        """
        Remove a pending transaction from LMDB mempool.
        """
        try:
            key = f"mempool:pending_tx:{tx_id}".encode()
            with self.env.begin(write=True, db=self.mempool_db) as txn:
                txn.delete(key)

            logging.info(f"[LMDB] ✅ Pending transaction {tx_id} removed from mempool.")

        except Exception as e:
            logging.error(f"[LMDB ERROR] ❌ Failed to remove pending transaction {tx_id}: {e}")

    def _serialize(self, data):
        """Serialize Python dictionary into JSON string."""
        return json.dumps(data).encode()

    def _deserialize(self, data):
        """Deserialize JSON string into Python dictionary."""
        return json.loads(data.decode()) if data else None

    # --------------------- ✅ Transaction Management ---------------------
    def begin_transaction(self):
        """Begin a transaction (simulated, since LMDB uses auto-commit)."""
        if not self.transaction_active:
            logging.info("[INFO] Starting LMDB transaction.")
            self.transaction_active = True

    def commit(self):
        """Commit a transaction (simulated for compatibility)."""
        if self.transaction_active:
            logging.info("[INFO] Committing LMDB transaction.")
            self.transaction_active = False  # Reset flag

    def rollback(self):
        """
        Rollback a transaction (LMDB does not support rollback).
        We log a warning instead of an actual rollback.
        """
        if self.transaction_active:
            logging.warning("[WARNING] LMDB does not support rollback. Manual data correction may be required.")
            self.transaction_active = False  # Reset flag

    # --------------------- ✅ Blockchain Storage ---------------------
    def add_block(self, block_hash, block_header, transactions, size, difficulty):
        """
        Add a block to the blockchain.
        """
        try:
            self.begin_transaction()

            block_data = {
                "block_header": block_header,
                "transactions": [tx.to_dict() if hasattr(tx, 'to_dict') else tx for tx in transactions],
                "size": size,
                "difficulty": difficulty
            }
            with self.env.begin(write=True, db=self.blocks_db) as txn:
                txn.put(f"block:{block_hash}".encode(), json.dumps(block_data).encode("utf-8"))

            self.commit()
            logging.info(f"[INFO] Block {block_hash} stored successfully.")

        except Exception as e:
            self.rollback()
            logging.error(f"[ERROR] Failed to store block {block_hash}: {e}")
            raise

    def get_all_blocks(self):
        """Retrieve all blocks stored in LMDB."""
        blocks = []
        with self.env.begin(db=self.blocks_db) as txn:
            cursor = txn.cursor()
            for key, value in cursor:
                if key.decode().startswith("block:"):
                    blocks.append(json.loads(value.decode("utf-8")))
        logging.info(f"[INFO] Retrieved {len(blocks)} blocks.")
        return blocks

    def delete_block(self, block_hash):
        """Delete a block from the database."""
        with self.env.begin(write=True) as txn:
            txn.delete(f"block:{block_hash}".encode())

    # --------------------- ✅ Transactions ---------------------
    def add_transaction(self, tx_id, block_hash, inputs, outputs, timestamp):
        """
        Store a transaction in LMDB, ensuring consistency and proper key formatting.
        """
        try:
            transaction_data = {
                "block_hash": block_hash,
                "inputs": inputs,
                "outputs": outputs,
                "timestamp": timestamp
            }
            key = f"tx:{tx_id}".encode()
            value = json.dumps(transaction_data).encode("utf-8")

            with self.env.begin(write=True, db=self.transactions_db) as txn:
                txn.put(key, value)

            logging.info(f"[LMDB] ✅ Transaction {tx_id} stored successfully.")

        except Exception as e:
            logging.error(f"[LMDB ERROR] ❌ Failed to store transaction {tx_id}: {e}")
            raise

    def get_transaction(self, tx_id):
        """Retrieve a transaction by its ID from LMDB."""
        try:
            key = f"tx:{tx_id}".encode()
            with self.env.begin(db=self.transactions_db) as txn:
                data = txn.get(key)
            return json.loads(data.decode("utf-8")) if data else None

        except json.JSONDecodeError as e:
            logging.error(f"[LMDB ERROR] ❌ Failed to decode transaction {tx_id}: {e}")
            return None
        except Exception as e:
            logging.error(f"[LMDB ERROR] ❌ Failed to retrieve transaction {tx_id}: {e}")
            return None

    def get_all_transactions(self):
        """Retrieve all stored transactions from LMDB."""
        transactions = []
        try:
            with self.env.begin(db=self.transactions_db) as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.decode().startswith("tx:"):
                        try:
                            transactions.append(json.loads(value.decode("utf-8")))
                        except json.JSONDecodeError as e:
                            logging.error(f"[LMDB ERROR] ❌ Failed to decode transaction {key.decode()}: {e}")

            logging.info(f"[LMDB] ✅ Retrieved {len(transactions)} transactions.")
            return transactions

        except lmdb.Error as e:
            logging.error(f"[LMDB ERROR] ❌ LMDB transaction retrieval failed: {e}")
            return []
