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
from Zyiron_Chain.transactions.fees import FeeModel


class TxStorage:
    """
    TxStorage manages the transaction index (txindex.lmdb) for the blockchain.
    
    Responsibilities:
      - Store transaction metadata in LMDB.
      - Ensure transactions are linked to their block.
      - Use bytes for all storage operations.
      - Store `tx_signature_hash` (48 bytes) and `falcon_signature` (700 bytes).
      - Use single SHA3-384 hashing for transaction IDs.
      - Provide detailed print statements for every operation and error.
    """

    def __init__(self, fee_model: Optional[FeeModel] = None):
        """
        Initializes transaction storage with LMDB and an optional FeeModel for fee calculations.
        """
        try:
            print("[TxStorage.__init__] INFO: Initializing transaction storage...")

            txindex_path = Constants.DATABASES.get("txindex")
            if not txindex_path:
                raise ValueError("[TxStorage.__init__] ERROR: Transaction index database path not defined in Constants.DATABASES.")

            self.txindex_db = LMDBManager(txindex_path)

            if fee_model is None:
                raise ValueError("[TxStorage.__init__] ERROR: FeeModel instance is required.")
            self.fee_model = fee_model

            print(f"[TxStorage.__init__] SUCCESS: Initialized TxStorage with LMDB path: {txindex_path}")

        except Exception as e:
            print(f"[TxStorage.__init__] ERROR: Failed to initialize TxStorage: {e}")
            raise

    def store_transaction(
        self, tx_id: str, block_hash: str, inputs: List[Dict], outputs: List[Dict], timestamp: int, 
        tx_signature: bytes, falcon_signature: bytes
    ) -> None:
        """
        Stores a transaction in LMDB with proper indexing, fee calculations, and metadata.
        Includes:
          - `tx_signature_hash` (48-byte SHA3-384 hash of transaction signature)
          - `falcon_signature` (700-byte Falcon-1024 signature)
        """
        try:
            print(f"[TxStorage.store_transaction] INFO: Storing transaction {tx_id} for block {block_hash}...")

            if not all(isinstance(i, dict) for i in inputs):
                print(f"[TxStorage.store_transaction] ERROR: Invalid inputs for transaction {tx_id}.")
                return
            if not all(isinstance(o, dict) for o in outputs):
                print(f"[TxStorage.store_transaction] ERROR: Invalid outputs for transaction {tx_id}.")
                return
            if not isinstance(timestamp, int):
                print(f"[TxStorage.store_transaction] ERROR: Timestamp must be an integer for transaction {tx_id}.")
                return
            if not all(isinstance(i, str) for i in [tx_id, block_hash]):
                print(f"[TxStorage.store_transaction] ERROR: tx_id and block_hash must be strings for transaction {tx_id}.")
                return

            if not hasattr(self, "fee_model") or not self.fee_model:
                print(f"[TxStorage.store_transaction] ERROR: FeeModel is missing. Cannot calculate fees.")
                return

            tx_type = "STANDARD"
            for t_type, details in Constants.TRANSACTION_MEMPOOL_MAP.items():
                if any(tx_id.startswith(prefix) for prefix in details.get("prefixes", [])):
                    tx_type = t_type
                    break

            print(f"[TxStorage.store_transaction] INFO: Identified transaction type as {tx_type}.")

            try:
                total_output_amount = sum(Decimal(out["amount"]) for out in outputs)
                fee_details = self.fee_model.calculate_fee_and_tax(1, tx_type, total_output_amount, 250)
                tax_fee = fee_details["tax_fee"]
                miner_fee = fee_details["miner_fee"]

                print(f"[TxStorage.store_transaction] INFO: Fee Breakdown - Tax Fee: {tax_fee}, Miner Fee: {miner_fee}")
            except Exception as fee_error:
                print(f"[TxStorage.store_transaction] ERROR: Fee calculation failed for transaction {tx_id}: {fee_error}")
                return

            # Compute SHA3-384 hash of the transaction signature
            tx_signature_hash = Hashing.hash(tx_signature).hex()

            # Ensure Falcon signature is exactly 700 bytes
            falcon_signature_padded = falcon_signature.ljust(700, b'\x00')

            transaction_data = {
                "tx_id": tx_id,
                "block_hash": block_hash,
                "inputs": inputs,
                "outputs": outputs,
                "timestamp": timestamp,
                "type": tx_type,
                "tax_fee": str(tax_fee),
                "miner_fee": str(miner_fee),
                "tx_signature_hash": tx_signature_hash,
                "falcon_signature": falcon_signature_padded.hex()
            }

            serialized_data = json.dumps(transaction_data, sort_keys=True).encode("utf-8")
            tx_key = b"tx:" + tx_id.encode("utf-8")

            with self.txindex_db.env.begin(write=True) as txn:
                existing_tx = txn.get(tx_key)
                if existing_tx:
                    print(f"[TxStorage.store_transaction] WARNING: Transaction {tx_id} already exists in the database.")
                    return

                txn.put(tx_key, serialized_data)
                print(f"[TxStorage.store_transaction] SUCCESS: Transaction {tx_id} stored successfully.")

        except Exception as e:
            print(f"[TxStorage.store_transaction] ERROR: Failed to store transaction {tx_id}: {e}")
            raise

    def get_transaction(self, tx_id: str) -> Optional[Dict]:
        """
        Retrieve a transaction from LMDB, including:
        - `tx_signature_hash` (48-byte hash)
        - `falcon_signature` (700 bytes)
        """
        try:
            tx_key = b"tx:" + tx_id.encode("utf-8")
            with self.txindex_db.env.begin() as txn:
                tx_data = txn.get(tx_key)

            if not tx_data:
                print(f"[TxStorage.get_transaction] WARNING: Transaction {tx_id} not found in LMDB.")
                return None

            transaction = json.loads(tx_data.decode("utf-8"))
            print(f"[TxStorage.get_transaction] INFO: Transaction {tx_id} retrieved successfully.")

            return transaction

        except Exception as e:
            print(f"[TxStorage.get_transaction] ERROR: Failed to retrieve transaction {tx_id}: {e}")
            return None

    def get_all_transactions(self) -> List[Dict]:
        """
        Retrieve all stored transactions from LMDB.
        """
        transactions = []
        try:
            with self.txindex_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.startswith(b"tx:"):
                        try:
                            tx_data = json.loads(value.decode("utf-8"))
                            transactions.append(tx_data)
                        except Exception as e:
                            print(f"[TxStorage.get_all_transactions] ERROR: Failed to process transaction key {key}: {e}")
            print(f"[TxStorage.get_all_transactions] INFO: Retrieved {len(transactions)} transactions from LMDB.")
            return transactions
        except Exception as e:
            print(f"[TxStorage.get_all_transactions] ERROR: Failed to retrieve all transactions: {e}")
            return []
