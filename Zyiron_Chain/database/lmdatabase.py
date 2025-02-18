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
DB_PATH = "ZYCDB/MEMPOOLDB"
os.makedirs(DB_PATH, exist_ok=True)
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LMDBManager")

class LMDBManager:
    def __init__(self, db_path="ZYCDB/MEMPOOLDB"):
        """Initialize LMDB with network-aware configuration"""
        # Validate Constants configuration
        if not hasattr(Constants, "MAX_LMDB_DATABASES"):
            raise AttributeError("Constants missing MAX_LMDB_DATABASES")
        if not hasattr(Constants, "MEMPOOL_MAX_SIZE_MB"):
            raise AttributeError("Constants missing MEMPOOL_MAX_SIZE_MB")

        # ✅ Convert to absolute path and validate
        db_path = os.path.abspath(db_path)
        parent_dir = os.path.dirname(db_path)
        
        # ✅ Create parent directory only if path contains subdirectories
        if parent_dir and parent_dir != db_path:
            try:
                os.makedirs(parent_dir, exist_ok=True)
                logger.info(f"Created database directory: {parent_dir}")
            except OSError as e:
                logger.error(f"Failed to create directory {parent_dir}: {str(e)}")
                raise

        # Configure environment with error handling
        try:
            self.env = lmdb.open(
                path=db_path,
                map_size=Constants.MEMPOOL_MAX_SIZE_MB * 1024 * 1024,
                max_dbs=Constants.MAX_LMDB_DATABASES,
                mode=0o755,
                create=True,
                readahead=False,
                writemap=True,
                meminit=False
            )
        except lmdb.Error as e:
            logger.error(f"LMDB environment creation failed: {str(e)}")
            raise

        # Initialize databases with explicit transaction
        try:
            with self.env.begin(write=True) as txn:
                self.mempool_db = self.env.open_db(b"mempool", txn=txn)
                self.blocks_db = self.env.open_db(b"blocks", txn=txn)
                self.transactions_db = self.env.open_db(b"transactions", txn=txn)
                self.metadata_db = self.env.open_db(b"metadata", txn=txn)
            logger.info("Database handles initialized successfully")
        except lmdb.Error as e:
            logger.error(f"Database initialization failed: {str(e)}")
            self.env.close()
            raise

        # State tracking
        self.transaction_active = False
        self._verify_capacity()

    def _verify_capacity(self):
        """Check database limits"""
        with self.env.begin() as txn:
            stats = txn.stat()
            capacity = stats["entries"] / Constants.MAX_LMDB_DATABASES
            if capacity > 0.8:
                logger.warning(f"LMDB at {capacity:.0%} capacity")

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


    def cleanup_dbs():
        """Delete existing database files to apply new settings"""
        import shutil
        db_paths = [
            "ZYCDB/MEMPOOLDB",
            "ZYCDB",
            "UTXOSDB"
        ]
        
        for path in db_paths:
            if os.path.exists(path):
                shutil.rmtree(path)
                print(f"Deleted: {path}")
        
        print("✅ Database cleanup complete. Restart your node.")

def verify_database_capacity(self):
    """Check database limits and current usage"""
    with self.env.begin() as txn:
        stats = txn.stat()
        print(f"Database Status:\n"
              f"- Max DBs Allowed: {self.env.info()['max_dbs']}\n"
              f"- DBs Used: {stats['entries']}\n"
              f"- Free Space: {self.env.info()['map_size'] - stats['psize'] * stats['entries']} bytes")

    # --------------------- ✅ General Utilities ---------------------
    @staticmethod
    def cleanup_dbs():
        """Remove existing database files"""
        paths = ["ZYCDB", "UTXOSDB"]
        for path in paths:
            if os.path.exists(path):
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                    else:
                        shutil.rmtree(path)
                    logger.info(f"Cleaned: {path}")
                except Exception as e:
                    logger.error(f"Cleanup failed for {path}: {str(e)}")
        logger.info("Database cleanup complete")


    def cleanup():
        paths = ["ZYCDB", "UTXOSDB"]
        for path in paths:
            if os.path.exists(path):
                shutil.rmtree(path)
        print("✅ Deleted corrupted databases")

    cleanup()

    def close(self):
        """Close the LMDB environment."""
        self.env.close()
class Constants:
    MAX_LMDB_DATABASES = 10  # Must be ≥4
    MEMPOOL_MAX_SIZE_MB = 2048  # 2GB
    NETWORK = "mainnet"  # ✅ Critical for path resolution