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
            # ✅ Connect Mempool to `TransactionManager` for automatic validation
            self.transaction_manager = transaction_manager  # Ensures transactions are validated before being added
            
            # ✅ Initialize LMDB for mempool using database path from Constants
            mempool_db_path = Constants.DATABASES.get("mempool")
            if not mempool_db_path:
                raise ValueError("Mempool database path not defined in Constants.DATABASES.")
            self.mempool_db = LMDBManager(mempool_db_path)
            self._db_lock = None  # (If needed, you can add a threading.Lock here)
            print(f"[MempoolStorage.__init__] INFO: MempoolStorage initialized with LMDB path: {mempool_db_path}")

            # ✅ Load and Validate Transactions on Startup
            self._load_and_validate_mempool()

        except Exception as e:
            print(f"[MempoolStorage.__init__] ERROR: Failed to initialize MempoolStorage: {e}")
            raise

    def _load_and_validate_mempool(self):
        """
        Load transactions from LMDB and validate them using TransactionManager.
        Ensures that invalid transactions do not remain in mempool.
        """
        try:
            print("[MempoolStorage._load_and_validate_mempool] INFO: Loading transactions from mempool...")

            pending_txs = self.get_pending_transactions()
            if not pending_txs:
                print("[MempoolStorage._load_and_validate_mempool] INFO: No transactions found in mempool.")
                return

            valid_txs = []
            for tx in pending_txs:
                if self.transaction_manager.validate_transaction(tx):
                    valid_txs.append(tx)
                else:
                    print(f"[MempoolStorage._load_and_validate_mempool] WARNING: Invalid transaction {tx.get('tx_id')} removed from mempool.")
                    self.remove_transaction(tx.get("tx_id"))

            print(f"[MempoolStorage._load_and_validate_mempool] INFO: Loaded {len(valid_txs)} valid transactions into mempool.")

        except Exception as e:
            print(f"[MempoolStorage._load_and_validate_mempool] ERROR: Failed to load and validate mempool transactions: {e}")

    def add_transaction(self, transaction: Dict) -> bool:
        """
        Store a pending transaction in LMDB mempool.
        - The transaction must have a 'tx_id' field.
        - Transaction data is JSON-serialized and stored as bytes.
        - Uses single SHA3‑384 hashing to verify the transaction ID.
        """
        try:
            if "tx_id" not in transaction or not isinstance(transaction["tx_id"], str):
                print("[MempoolStorage.add_transaction] ERROR: Transaction missing valid 'tx_id'.")
                return False

            # ✅ Validate Transaction Before Adding
            if not self.transaction_manager.validate_transaction(transaction):
                print(f"[MempoolStorage.add_transaction] ERROR: Transaction {transaction['tx_id']} failed validation. Not adding to mempool.")
                return False

            # ✅ Ensure Transaction ID Consistency
            tx_id = transaction["tx_id"]
            computed_tx_id = hashlib.sha3_384(tx_id.encode()).hexdigest()
            if computed_tx_id != tx_id:
                print(f"[MempoolStorage.add_transaction] ERROR: Transaction ID mismatch. Expected {computed_tx_id}, got {tx_id}.")
                return False

            tx_key = f"tx:{tx_id}".encode("utf-8")
            serialized_data = json.dumps(transaction, sort_keys=True).encode("utf-8")

            with self.mempool_db.env.begin(write=True) as txn:
                txn.put(tx_key, serialized_data)

            print(f"[MempoolStorage.add_transaction] INFO: Transaction {tx_id} stored successfully in mempool.")
            return True
        except Exception as e:
            print(f"[MempoolStorage.add_transaction] ERROR: Failed to add transaction {transaction.get('tx_id')}: {e}")
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
                    key_str = key.decode("utf-8")
                    if key_str.startswith("tx:"):
                        try:
                            tx_data = value.decode("utf-8")
                            transaction = json.loads(tx_data)
                            transactions.append(transaction)
                        except Exception as e:
                            print(f"[MempoolStorage.get_pending_transactions] ERROR: Failed to decode transaction {key_str}: {e}")
                            continue
            print(f"[MempoolStorage.get_pending_transactions] INFO: Retrieved {len(transactions)} pending transactions.")
            return transactions
        except Exception as e:
            print(f"[MempoolStorage.get_pending_transactions] ERROR: Failed to retrieve pending transactions: {e}")
            return []

    def remove_transaction(self, tx_id: str) -> bool:
        """
        Remove a transaction from the mempool by its transaction ID.
        """
        try:
            tx_key = f"tx:{tx_id}".encode("utf-8")
            with self.mempool_db.env.begin(write=True) as txn:
                if txn.get(tx_key) is None:
                    print(f"[MempoolStorage.remove_transaction] WARNING: Transaction {tx_id} not found in mempool.")
                    return False
                txn.delete(tx_key)
            print(f"[MempoolStorage.remove_transaction] INFO: Transaction {tx_id} removed from mempool.")
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
                txn.drop(self.mempool_db.db, delete=True)
            print("[MempoolStorage.clear_mempool] INFO: Mempool cleared successfully.")
        except Exception as e:
            print(f"[MempoolStorage.clear_mempool] ERROR: Failed to clear mempool: {e}")
            raise

    def close(self) -> None:
        """
        Close the LMDB mempool database connection safely.
        """
        try:
            self.mempool_db.env.close()
            print("[MempoolStorage.close] INFO: Mempool LMDB connection closed successfully.")
        except Exception as e:
            print(f"[MempoolStorage.close] ERROR: Failed to close mempool LMDB connection: {e}")
