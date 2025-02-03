import lmdb
import json
import time


import lmdb
import json
import time
import logging

logging.basicConfig(level=logging.INFO)


class LMDBManager:
    def __init__(self, db_path="blockchain_lmdb", map_size=10 * 1024 * 1024):  # 10MB
        """
        Initialize the LMDB database.
        :param db_path: Path to the LMDB database directory.
        :param map_size: Maximum size of the database in bytes.
        """
        self.env = lmdb.open(db_path, map_size=map_size, create=True)
        self.transaction_active = False  # ✅ Added transaction tracking

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
            with self.env.begin(write=True) as txn:
                txn.put(f"block:{block_hash}".encode(), self._serialize(block_data))

            self.commit()
            logging.info(f"[INFO] Block {block_hash} stored successfully.")

        except Exception as e:
            self.rollback()
            logging.error(f"[ERROR] Failed to store block {block_hash}: {e}")
            raise

    def get_block(self, block_hash):
        """Retrieve a block by its hash."""
        with self.env.begin() as txn:
            data = txn.get(f"block:{block_hash}".encode())
            return self._deserialize(data)

    def get_all_blocks(self):
        """Retrieve all blocks stored in LMDB."""
        blocks = []
        with self.env.begin() as txn:
            cursor = txn.cursor()
            for key, value in cursor:
                if key.decode().startswith("block:"):
                    blocks.append(self._deserialize(value))
        logging.info(f"[INFO] Retrieved {len(blocks)} blocks.")
        return blocks

    def delete_block(self, block_hash):
        """Delete a block from the database."""
        with self.env.begin(write=True) as txn:
            txn.delete(f"block:{block_hash}".encode())

    # --------------------- ✅ Transactions ---------------------
    def add_transaction(self, tx_id, block_hash, inputs, outputs, timestamp):
        """
        Store a transaction in LMDB.
        """
        try:
            transaction_data = {
                "block_hash": block_hash,
                "inputs": inputs,
                "outputs": outputs,
                "timestamp": timestamp
            }
            with self.env.begin(write=True) as txn:
                txn.put(f"transaction:{tx_id}".encode(), self._serialize(transaction_data))

            logging.info(f"[INFO] Transaction {tx_id} stored.")

        except Exception as e:
            logging.error(f"[ERROR] Failed to store transaction {tx_id}: {e}")
            raise

    def get_transaction(self, tx_id):
        """Retrieve a transaction by its ID."""
        with self.env.begin() as txn:
            data = txn.get(f"transaction:{tx_id}".encode())
            return self._deserialize(data)

    def get_all_transactions(self):
        """Retrieve all transactions."""
        transactions = []
        with self.env.begin() as txn:
            cursor = txn.cursor()
            for key, value in cursor:
                if key.decode().startswith("transaction:"):
                    transactions.append(self._deserialize(value))
        logging.info(f"[INFO] Retrieved {len(transactions)} transactions.")
        return transactions

    def delete_transaction(self, tx_id):
        """Delete a transaction by its ID."""
        with self.env.begin(write=True) as txn:
            txn.delete(f"transaction:{tx_id}".encode())

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
