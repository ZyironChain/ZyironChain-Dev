import lmdb
import json
import time

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))





import lmdb
import json
import time
import logging

logging.basicConfig(level=logging.INFO)
from Zyiron_Chain.blockchain.constants import Constants
DB_PATH = "ZYCDB/MEMPOOLDB"
os.makedirs(DB_PATH, exist_ok=True)

class LMDBManager:
    def __init__(self, db_path=DB_PATH):

        """
        Initialize the LMDB database.
        :param db_path: Path to the LMDB database directory.
        """
        # ✅ Fetch storage settings from Constants
        map_size = Constants.MEMPOOL_MAX_SIZE_MB * 1024 * 1024  # Convert MB to bytes
        max_dbs = Constants.MAX_LMDB_DATABASES  # ✅ Use Constants for max databases

        # ✅ Open LMDB environment with the correct settings
        self.env = lmdb.open(db_path, map_size=map_size, max_dbs=max_dbs, create=True)

        # ✅ Open separate databases inside LMDB
        self.mempool_db = self.env.open_db(b"mempool")  # Store pending transactions
        self.blocks_db = self.env.open_db(b"blocks")  # Store blocks separately
        self.transactions_db = self.env.open_db(b"transactions")  # Store transactions separately

        self.transaction_active = False  # ✅ Added transaction tracking
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



    # --------------------- ✅ General Utilities ---------------------
    def clear_database(self):
        """Clear all data (for testing purposes)."""
        with self.env.begin(write=True) as txn:
            cursor = txn.cursor()
            for key, _ in cursor:
                txn.delete(key)
        logging.info("[INFO] LMDB database cleared.")

    def close(self):
        """Close the LMDB environment."""
        self.env.close()
