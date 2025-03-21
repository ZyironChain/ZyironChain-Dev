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
from Zyiron_Chain.transactions.coinbase import CoinbaseTx
from Zyiron_Chain.transactions.transactiontype import TransactionType

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
        self, tx_id: str, block_hash: str, tx_data: dict, outputs: List[Dict], timestamp: int,
        tx_signature: bytes = b"", falcon_signature: bytes = b""
    ) -> None:
        try:
            print(f"[TxStorage.store_transaction] INFO: Storing transaction {tx_id} for block {block_hash}...")

            if not isinstance(tx_data, dict):
                print(f"[TxStorage.store_transaction] ERROR: Transaction data must be a dictionary.")
                return

            if not outputs or not all(isinstance(o, dict) for o in outputs):
                print(f"[TxStorage.store_transaction] ERROR: Outputs must be a list of dictionaries.")
                return

            if not isinstance(timestamp, int) or not isinstance(tx_id, str) or not isinstance(block_hash, str):
                print(f"[TxStorage.store_transaction] ERROR: Invalid transaction parameters.")
                return

            if not hasattr(self, "fee_model") or not self.fee_model:
                print(f"[TxStorage.store_transaction] ERROR: FeeModel is missing.")
                return

            tx_type = "STANDARD"
            for t_type, config in Constants.TRANSACTION_MEMPOOL_MAP.items():
                if any(tx_id.startswith(prefix) for prefix in config.get("prefixes", [])):
                    tx_type = t_type
                    break

            print(f"[TxStorage.store_transaction] INFO: Identified transaction type as {tx_type}.")

            try:
                total_output_amount = sum(Decimal(str(out["amount"])) for out in outputs)
                fee_details = self.fee_model.calculate_fee_and_tax(
                    block_size=1,
                    payment_type=tx_type,
                    amount=total_output_amount,
                    tx_size=250
                )

                tax_fee = fee_details.get("tax_fee", Constants.MIN_TRANSACTION_FEE)
                miner_fee = fee_details.get("miner_fee", Constants.MIN_TRANSACTION_FEE)

                if any(str(f).upper() == "LOW" for f in [tax_fee, miner_fee]):
                    print(f"[TxStorage.store_transaction] WARN: Low fee detected. Using minimums.")
                    tax_fee = miner_fee = Decimal(Constants.MIN_TRANSACTION_FEE)
                else:
                    tax_fee = Decimal(str(tax_fee))
                    miner_fee = Decimal(str(miner_fee))

                print(f"[TxStorage.store_transaction] INFO: Fee Breakdown - Tax Fee: {tax_fee}, Miner Fee: {miner_fee}")

            except Exception as fee_error:
                print(f"[TxStorage.store_transaction] ERROR: Fee calculation failed - {fee_error}")
                return

            # Store Falcon Signature
            txindex_path = Constants.get_db_path("txindex")
            hashed_signature = store_transaction_signature(
                tx_id=tx_id.encode(),
                falcon_signature=falcon_signature,
                txindex_path=txindex_path
            )

            transaction_data = {
                "tx_id": tx_id,
                "block_hash": block_hash,
                "data": tx_data,
                "outputs": outputs,
                "timestamp": timestamp,
                "type": tx_type,
                "tax_fee": str(tax_fee),
                "miner_fee": str(miner_fee),
                "tx_signature_hash": hashed_signature.hex()
            }

            with self.txindex_db.env.begin(write=True) as txn:
                txn.put(f"block_tx:{tx_id}".encode(), json.dumps(transaction_data).encode())

            print(f"[TxStorage.store_transaction] ✅ SUCCESS: Stored {tx_id}.")

        except Exception as e:
            print(f"[TxStorage.store_transaction] EXCEPTION: {e}")


    def _detect_transaction_type(self, tx):
        if isinstance(tx, CoinbaseTx):
            return TransactionType.COINBASE
        elif tx.tx_id.startswith(b'S-'):
            return TransactionType.SMART
        elif tx.tx_id.startswith(b'PID-') or tx.tx_id.startswith(b'CID-'):
            return TransactionType.INSTANT
        else:
            return TransactionType.STANDARD


    def get_transaction(self, tx_id: str) -> Optional[Dict]:
        """
        Retrieve a transaction from LMDB using 'block_tx:<tx_id>' key.

        :param tx_id: Transaction ID to fetch.
        :return: Transaction dictionary or None if not found or invalid.
        """
        try:
            key = f"block_tx:{tx_id}".encode()
            data = self.txindex_db.get(key)

            if not data:
                print(f"[TxStorage.get_transaction] ⚠️ WARNING: Transaction {tx_id} not found in LMDB.")
                return None

            try:
                transaction = json.loads(data.decode())
                print(f"[TxStorage.get_transaction] ✅ SUCCESS: Retrieved transaction {tx_id}.")
                return transaction
            except (json.JSONDecodeError, UnicodeDecodeError) as decode_error:
                print(f"[TxStorage.get_transaction] ❌ ERROR: Failed to decode transaction {tx_id}: {decode_error}")
                return None

        except Exception as e:
            print(f"[TxStorage.get_transaction] ❌ ERROR: Failed to retrieve transaction {tx_id}: {e}")
            return None

    def get_all_transactions(self) -> List[Dict]:
        """
        Retrieve all stored transactions in LMDB under 'block_tx:*' keys.

        :return: List of transaction dictionaries.
        """
        transactions = []
        try:
            all_entries = self.txindex_db.get_all_transactions()
            if not all_entries:
                print(f"[TxStorage.get_all_transactions] ℹ️ INFO: No transactions found in LMDB.")
                return []

            for raw in all_entries:
                try:
                    tx_data = json.loads(raw.decode())
                    if isinstance(tx_data, dict):
                        transactions.append(tx_data)
                except Exception as parse_error:
                    print(f"[TxStorage.get_all_transactions] ⚠️ WARNING: Skipping invalid transaction entry: {parse_error}")

            print(f"[TxStorage.get_all_transactions] ✅ Retrieved {len(transactions)} valid transactions.")
            return transactions

        except Exception as e:
            print(f"[TxStorage.get_all_transactions] ❌ ERROR: Failed to retrieve all transactions: {e}")
            return []


    def create_dir_if_not_exists(path):
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"Created database directory: {path}")
