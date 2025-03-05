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
from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.utils.deserializer import Deserializer

class TxStorage:
    """
    TxStorage manages the transaction index (txindex.lmdb) for the blockchain.
    
    Responsibilities:
      - Store transaction metadata in LMDB.
      - Ensure transactions are linked to their block.
      - Use bytes for all storage operations.
      - Use single SHA3‑384 hashing for transaction IDs.
      - Provide detailed print statements for every operation and error.
    """
    
    def __init__(self):
        try:
            txindex_path = Constants.DATABASES.get("txindex")
            if not txindex_path:
                raise ValueError("Transaction index database path not defined in Constants.DATABASES.")
            self.txindex_db = LMDBManager(txindex_path)
            print(f"[TxStorage.__init__] INFO: Initialized TxStorage with LMDB path: {txindex_path}")
        except Exception as e:
            print(f"[TxStorage.__init__] ERROR: Failed to initialize TxStorage: {e}")
            raise




    def get_transaction(self, tx_id):
        """Retrieve transaction data and deserialize it if necessary."""
        data = self.txindex_db.get(tx_id.encode("utf-8"))
        return Deserializer().deserialize(data) if data else None


    def store_transaction(self, tx_id: str, block_hash: str, inputs: List[Dict], outputs: List[Dict], timestamp: int) -> None:
        """
        Store a transaction in LMDB.
          - Saves transaction metadata in txindex.lmdb.
          - Ensures transactions are linked to their block.
          - Supports atomic writes.
        """
        try:
            print(f"[TxStorage.store_transaction] INFO: Storing transaction {tx_id} for block {block_hash}...")
            # Validate inputs and outputs
            if not (isinstance(inputs, list) and all(isinstance(i, dict) for i in inputs)):
                print(f"[TxStorage.store_transaction] ERROR: Invalid inputs for transaction {tx_id}.")
                return
            if not (isinstance(outputs, list) and all(isinstance(o, dict) for o in outputs)):
                print(f"[TxStorage.store_transaction] ERROR: Invalid outputs for transaction {tx_id}.")
                return
            if not isinstance(timestamp, int):
                print(f"[TxStorage.store_transaction] ERROR: Timestamp must be an integer for transaction {tx_id}.")
                return
            if not (isinstance(tx_id, str) and isinstance(block_hash, str)):
                print(f"[TxStorage.store_transaction] ERROR: tx_id and block_hash must be strings for transaction {tx_id}.")
                return

            transaction_data = {
                "tx_id": tx_id,
                "block_hash": block_hash,
                "inputs": inputs,
                "outputs": outputs,
                "timestamp": timestamp,
                "type": "UNKNOWN"  # Optional: set transaction type if available
            }
            serialized_data = json.dumps(transaction_data, sort_keys=True).encode("utf-8")
            tx_key = f"tx:{tx_id}".encode("utf-8")
            with self.txindex_db.env.begin(write=True) as txn:
                txn.put(tx_key, serialized_data)
            print(f"[TxStorage.store_transaction] SUCCESS: Transaction {tx_id} stored successfully.")
        except Exception as e:
            print(f"[TxStorage.store_transaction] ERROR: Failed to store transaction {tx_id}: {e}")
            raise

    def get_transaction(self, tx_id: str) -> Optional[Dict]:
        """
        Retrieve a transaction from LMDB.
          - Returns a dictionary with transaction data or None if not found.
        """
        try:
            if not isinstance(tx_id, (str, bytes)):
                print(f"[TxStorage.get_transaction] ERROR: Invalid tx_id format: {tx_id}.")
                return None
            tx_key = f"tx:{tx_id}".encode("utf-8") if isinstance(tx_id, str) else b"tx:" + tx_id
            with self.txindex_db.env.begin() as txn:
                tx_data = txn.get(tx_key)
            if not tx_data:
                print(f"[TxStorage.get_transaction] WARNING: Transaction {tx_id} not found in LMDB.")
                return None
            try:
                transaction = json.loads(tx_data.decode("utf-8"))
                print(f"[TxStorage.get_transaction] INFO: Transaction {tx_id} retrieved successfully.")
                return transaction
            except (json.JSONDecodeError, UnicodeDecodeError) as de:
                print(f"[TxStorage.get_transaction] ERROR: Failed to decode transaction {tx_id}: {de}")
                return None
        except Exception as e:
            print(f"[TxStorage.get_transaction] ERROR: Exception retrieving transaction {tx_id}: {e}")
            return None

    def get_all_transactions(self) -> List[Dict]:
        """
        Retrieve all stored transactions from LMDB.
        Returns a list of transaction dictionaries.
        """
        transactions = []
        try:
            with self.txindex_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    try:
                        key_str = key.decode("utf-8")
                        if key_str.startswith("tx:"):
                            tx_data = value.decode("utf-8")
                            tx_dict = json.loads(tx_data)
                            if isinstance(tx_dict, dict):
                                transactions.append(tx_dict)
                            else:
                                print(f"[TxStorage.get_all_transactions] WARNING: Transaction data for {key_str} is not a dict.")
                    except Exception as e:
                        print(f"[TxStorage.get_all_transactions] ERROR: Failed to process transaction key {key}: {e}")
                        continue
            print(f"[TxStorage.get_all_transactions] INFO: Retrieved {len(transactions)} transactions from LMDB.")
            return transactions
        except Exception as e:
            print(f"[TxStorage.get_all_transactions] ERROR: Failed to retrieve all transactions: {e}")
            return []

    def get_transaction_confirmations(self, tx_id: str, chain_length: int, block_index_lookup: Dict[str, int]) -> Optional[int]:
        """
        Calculate confirmations for a transaction.
          - Confirmations = (current chain length) - (block index where transaction is found)
          - `block_index_lookup` should be a dict mapping transaction IDs to block indexes.
          - Returns the number of confirmations or None if transaction is not found.
        """
        try:
            if tx_id not in block_index_lookup:
                print(f"[TxStorage.get_transaction_confirmations] WARNING: Transaction {tx_id} not found in chain lookup.")
                return None
            confirmations = chain_length - block_index_lookup[tx_id]
            print(f"[TxStorage.get_transaction_confirmations] INFO: Transaction {tx_id} has {confirmations} confirmations.")
            return confirmations
        except Exception as e:
            print(f"[TxStorage.get_transaction_confirmations] ERROR: Failed to calculate confirmations for {tx_id}: {e}")
            return None

    def clear_tx_index(self) -> None:
        """
        Clear all transactions from the txindex LMDB.
        """
        try:
            with self.txindex_db.env.begin(write=True) as txn:
                txn.drop(self.txindex_db.db, delete=True)
            print(f"[TxStorage.clear_tx_index] INFO: txindex LMDB cleared successfully.")
        except Exception as e:
            print(f"[TxStorage.clear_tx_index] ERROR: Failed to clear txindex LMDB: {e}")
            raise

    def close(self) -> None:
        """
        Close the LMDB connection for txindex.
        """
        try:
            self.txindex_db.env.close()
            print(f"[TxStorage.close] INFO: txindex LMDB connection closed successfully.")
        except Exception as e:
            print(f"[TxStorage.close] ERROR: Failed to close txindex LMDB connection: {e}")
