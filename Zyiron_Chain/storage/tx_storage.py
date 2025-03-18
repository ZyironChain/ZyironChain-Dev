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

from Zyiron_Chain.blockchain.constants import Constants, store_transaction_signature
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.utils.deserializer import Deserializer
from Zyiron_Chain.transactions.fees import FeeModel


import os
import sys
import json
import time
from decimal import Decimal
from typing import List, Optional, Dict, Union

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.utils.hashing import Hashing


class TxStorage:
    """
    TxStorage manages the transaction index (txindex.lmdb) for the blockchain.
    
    Responsibilities:
      - Store transaction metadata in LMDB.
      - Ensure transactions are linked to their block.
      - Store `tx_signature_hash` and `falcon_signature` as JSON.
      - Use single SHA3-384 hashing for transaction IDs.
      - Provide detailed print statements for every operation and error.
    """

    def __init__(self, fee_model: Optional["FeeModel"] = None):
        try:
            print("[TxStorage.__init__] INFO: Initializing transaction storage...")

            txindex_path = Constants.DATABASES.get("txindex")
            if not txindex_path:
                raise ValueError("[TxStorage.__init__] ERROR: Transaction index database path not defined in Constants.DATABASES.")

            self.txindex_db = LMDBManager(txindex_path)

            if not fee_model:
                raise ValueError("[TxStorage.__init__] ERROR: FeeModel instance is required.")
            self.fee_model = fee_model

            print(f"[TxStorage.__init__] SUCCESS: Initialized TxStorage with LMDB path: {txindex_path}")

        except Exception as e:
            print(f"[TxStorage.__init__] ERROR: Failed to initialize TxStorage: {e}")
            raise

    def store_transaction(
        self, tx_id: str, block_hash: str, inputs: List[Dict], outputs: List[Dict],
        timestamp: int, tx_signature: bytes = b"", falcon_signature: bytes = b""
    ) -> None:
        """
        Store a transaction in LMDB.

        :param tx_id: Transaction ID.
        :param block_hash: Block hash where the transaction belongs.
        :param inputs: List of transaction inputs.
        :param outputs: List of transaction outputs.
        :param timestamp: Transaction timestamp.
        :param tx_signature: Transaction signature (SHA3-384 hashed, 48 bytes).
        :param falcon_signature: Falcon-512 digital signature (700 bytes).
        """
        try:
            print(f"[TxStorage.store_transaction] INFO: Storing transaction {tx_id} for block {block_hash}...")

            if not all(isinstance(i, dict) for i in inputs) or not all(isinstance(o, dict) for o in outputs):
                print(f"[TxStorage.store_transaction] ERROR: Invalid inputs or outputs for transaction {tx_id}.")
                return

            if not isinstance(timestamp, int) or not isinstance(tx_id, str) or not isinstance(block_hash, str):
                print(f"[TxStorage.store_transaction] ERROR: Invalid transaction parameters for {tx_id}.")
                return

            # ✅ Ensure FeeModel exists
            if not hasattr(self, "fee_model") or not self.fee_model:
                print(f"[TxStorage.store_transaction] ERROR: FeeModel is missing. Cannot calculate fees.")
                return

            tx_type = Constants.TRANSACTION_MEMPOOL_MAP.get(tx_id[:2], "STANDARD")
            print(f"[TxStorage.store_transaction] INFO: Identified transaction type as {tx_type}.")

            # ✅ Compute Fee Breakdown
            try:
                total_output_amount = sum(Decimal(out["amount"]) for out in outputs)
                fee_details = self.fee_model.calculate_fee_and_tax(1, tx_type, total_output_amount, 250)
                tax_fee, miner_fee = fee_details["tax_fee"], fee_details["miner_fee"]
                print(f"[TxStorage.store_transaction] INFO: Fee Breakdown - Tax Fee: {tax_fee}, Miner Fee: {miner_fee}")
            except Exception as fee_error:
                print(f"[TxStorage.store_transaction] ERROR: Fee calculation failed for transaction {tx_id}: {fee_error}")
                return

            # ✅ **Store Falcon-512 Signature in `txindex.lmdb`**
            txindex_path = Constants.get_db_path("txindex")  
            hashed_signature = store_transaction_signature(
                tx_id=tx_id.encode(),
                falcon_signature=falcon_signature,
                txindex_path=txindex_path
            )

            # ✅ **Transaction data (Stored as JSON)**
            transaction_data = {
                "tx_id": tx_id,
                "block_hash": block_hash,
                "inputs": inputs,
                "outputs": outputs,
                "timestamp": timestamp,
                "type": tx_type,
                "tax_fee": str(tax_fee),
                "miner_fee": str(miner_fee),
                "tx_signature_hash": hashed_signature.hex(),  # ✅ Store only the hashed signature
            }

            # ✅ **Store Hashed Signature in `full_block_chain.lmdb`**
            blockchain_db_path = Constants.get_db_path("full_block_chain")
            success = self.txindex_db.put(f"block_tx:{tx_id}", transaction_data)

            if success:
                print(f"[TxStorage.store_transaction] SUCCESS: Transaction {tx_id} stored successfully.")
            else:
                print(f"[TxStorage.store_transaction] ERROR: Failed to store transaction {tx_id}.")

        except Exception as e:
            print(f"[TxStorage.store_transaction] ERROR: Failed to store transaction {tx_id}: {e}")

    def get_transaction(self, tx_id: str) -> Optional[Dict]:
        """
        Retrieve a transaction from LMDB.

        :param tx_id: Transaction ID to fetch.
        :return: Transaction dictionary or None if not found.
        """
        try:
            transaction = self.txindex_db.get(f"tx:{tx_id}")
            if not transaction:
                print(f"[TxStorage.get_transaction] WARNING: Transaction {tx_id} not found in LMDB.")
                return None
            return transaction
        except Exception as e:
            print(f"[TxStorage.get_transaction] ERROR: Failed to retrieve transaction {tx_id}: {e}")
            return None

    def get_all_transactions(self) -> List[Dict]:
        """
        Retrieve all transactions stored in LMDB.

        :return: List of transaction dictionaries.
        """
        transactions = []
        try:
            all_transactions = self.txindex_db.get_all_transactions()
            if all_transactions:
                transactions.extend(all_transactions)
                print(f"[TxStorage.get_all_transactions] INFO: Retrieved {len(transactions)} transactions from LMDB.")
            else:
                print(f"[TxStorage.get_all_transactions] INFO: No transactions found in LMDB.")
            return transactions
        except Exception as e:
            print(f"[TxStorage.get_all_transactions] ERROR: Failed to retrieve all transactions: {e}")
            return []
