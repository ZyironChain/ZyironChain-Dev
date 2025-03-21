import os
import sys
import json
import pickle
import struct
import time
import hashlib
from decimal import Decimal
from typing import List, Optional, Dict

# Set module search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.utils.hashing import Hashing

class MempoolStorage:
    """
    MempoolStorage handles pending transaction storage using LMDB.
    
    Responsibilities:
      - Store pending transactions in LMDB mempool.
      - Retrieve and remove transactions.
      - Clear mempool when needed.
      - Uses all available constants.
      - Processes data as bytes.
      - Uses single SHA3-384 hashing.
      - Provides detailed print statements for every major step and error.
    """

    def __init__(self, transaction_manager):
        try:
            self.transaction_manager = transaction_manager  
            
            mempool_db_path = Constants.DATABASES.get("mempool")
            if not mempool_db_path:
                raise ValueError("Mempool database path not defined in Constants.DATABASES.")

            self.mempool_db = LMDBManager(mempool_db_path)
            print(f"[MempoolStorage] INFO: Initialized with LMDB path: {mempool_db_path}")

            self._load_and_validate_mempool()

        except Exception as e:
            print(f"[MempoolStorage] ERROR: Initialization failed: {e}")
            raise

    def _load_and_validate_mempool(self):
        """
        Loads transactions from LMDB and validates them using TransactionManager.
        Removes invalid transactions from the mempool.
        """
        try:
            print("[MempoolStorage] INFO: Loading transactions from mempool...")

            pending_txs = self.get_pending_transactions()
            if not pending_txs:
                print("[MempoolStorage] INFO: No transactions found in mempool.")
                return

            for tx in pending_txs:
                if not self.transaction_manager.validate_transaction(tx):
                    print(f"[MempoolStorage] WARNING: Removing invalid transaction {tx.get('tx_id')}.")
                    self.remove_transaction(tx.get("tx_id"))

            print(f"[MempoolStorage] INFO: Loaded {len(pending_txs)} transactions into mempool.")

        except Exception as e:
            print(f"[MempoolStorage] ERROR: Failed to load and validate mempool transactions: {e}")

    def add_transaction(self, transaction: Dict) -> bool:
        """
        Store a pending transaction in LMDB mempool.
        - The transaction must have a 'tx_id' field.
        - Transaction data is JSON-serialized and stored.
        - Uses single SHA3‑384 hashing to verify the transaction ID.
        """
        try:
            tx_id = transaction.get("tx_id")

            if not tx_id or not isinstance(tx_id, str):
                print("[MempoolStorage] ERROR: Transaction missing valid 'tx_id'.")
                return False

            if not self.transaction_manager.validate_transaction(transaction):
                print(f"[MempoolStorage] ERROR: Transaction {tx_id} failed validation. Not adding to mempool.")
                return False

            tx_key = f"tx:{tx_id}".encode("utf-8")
            serialized_data = json.dumps(transaction, sort_keys=True).encode("utf-8")

            with self.mempool_db.env.begin(write=True) as txn:
                txn.put(tx_key, serialized_data)

            print(f"[MempoolStorage] INFO: Transaction {tx_id} stored in mempool.")
            return True

        except Exception as e:
            print(f"[MempoolStorage] ERROR: Failed to add transaction {tx_id}: {e}")
            return False

    def get_pending_transactions(self) -> List[Dict]:
        """
        Retrieve all pending transactions from the LMDB mempool.
        Returns a list of transaction dictionaries.
        """
        transactions = []
        try:
            with self.mempool_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.startswith(b"tx:"):
                        try:
                            transaction = json.loads(value.decode("utf-8"))
                            transactions.append(transaction)
                        except json.JSONDecodeError:
                            print(f"[MempoolStorage] WARNING: Skipping corrupt transaction entry {key.decode('utf-8', errors='ignore')}")
                        except UnicodeDecodeError:
                            print(f"[MempoolStorage] WARNING: Failed to decode transaction key {key}")
            
            print(f"[MempoolStorage] INFO: Retrieved {len(transactions)} pending transactions.")
            return transactions

        except Exception as e:
            print(f"[MempoolStorage] ERROR: Failed to retrieve pending transactions: {e}")
            return []


    def remove_transaction(self, tx_id: str) -> bool:
        """
        Remove a transaction from the mempool by its transaction ID.
        """
        try:
            if not isinstance(tx_id, str):
                print("[MempoolStorage.remove_transaction] ERROR: Invalid transaction ID format.")
                return False

            tx_key = f"tx:{tx_id}".encode("utf-8")

            with self.mempool_db.env.begin(write=True) as txn:
                if not txn.delete(tx_key):
                    print(f"[MempoolStorage.remove_transaction] WARNING: Transaction {tx_id} not found in mempool.")
                    return False

            print(f"[MempoolStorage.remove_transaction] INFO: Transaction {tx_id} removed successfully.")
            return True

        except Exception as e:
            print(f"[MempoolStorage.remove_transaction] ERROR: Failed to remove transaction {tx_id}: {e}")
            return False

    def clear_mempool(self) -> None:
        """
        Clear all transactions from the mempool.
        """
        try:
            with self.mempool_db.env.begin(write=True) as txn:
                txn.drop(self.mempool_db.mempool_db, delete=True)

            print("[MempoolStorage.clear_mempool] INFO: Mempool cleared successfully.")

        except Exception as e:
            print(f"[MempoolStorage.clear_mempool] ERROR: Failed to clear mempool: {e}")

    def close(self) -> None:
        """
        Close the LMDB mempool database connection safely.
        """
        try:
            self.mempool_db.env.close()
            print("[MempoolStorage.close] INFO: Mempool LMDB connection closed.")
        except Exception as e:
            print(f"[MempoolStorage.close] ERROR: Failed to close mempool LMDB connection: {e}")


    def create_dir_if_not_exists(path):
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"Created database directory: {path}")
