import os
import sys
import json
import pickle
import struct
import time
import hashlib
from decimal import Decimal
from typing import Any, List, Optional, Dict

import lmdb

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

    def __init__(self, fee_model: Optional["FeeModel"] = None, block_storage=None, block_metadata=None):
        """
        Initialize the TxStorage with LMDB backend and fee model.

        Args:
            fee_model (FeeModel): Instance of FeeModel for transaction fee calculations
            block_storage: Optional BlockStorage instance (for fallback)
            block_metadata: Optional BlockMetadata instance (for indexing support)

        Raises:
            ValueError: If database path is not defined or fee_model is missing
        """
        try:
            print("[TxStorage.__init__] INFO: Initializing transaction storage...")

            txindex_path = Constants.DATABASES.get("txindex")
            if not txindex_path:
                raise ValueError("[TxStorage.__init__] ERROR: Transaction index path not defined in Constants.DATABASES.")

            # Attempt to initialize LMDBManager safely
            try:
                self.txindex_db = LMDBManager(txindex_path)
            except Exception as e:
                print(f"[TxStorage.__init__] ⚠️ Initial LMDB init failed: {e}")
                time.sleep(0.2)
                self.txindex_db = LMDBManager(txindex_path)  # Final retry
                print(f"[TxStorage.__init__] 🔁 Retried and reinitialized LMDB.")

            if not fee_model:
                raise ValueError("[TxStorage.__init__] ERROR: FeeModel instance is required.")
            self.fee_model = fee_model

            # ✅ Backward-compatible support for optional fallback sources
            self.block_storage = block_storage
            self.block_metadata = block_metadata

            print(f"[TxStorage.__init__] ✅ SUCCESS: TxStorage initialized at: {txindex_path}")

        except Exception as e:
            print(f"[TxStorage.__init__] ❌ ERROR: Failed to initialize TxStorage: {e}")
            raise




    def reopen(self):
        """
        Attempt to reopen the LMDB environment if it becomes invalid.
        """
        try:
            if not self.txindex_db.env:
                self.txindex_db._open_env()
            else:
                self.txindex_db.env.stat()  # Check if it's alive
        except Exception as e:
            print(f"[TxStorage.reopen] ⚠️ Detected invalid LMDB state, reopening... Reason: {e}")
            self.txindex_db._open_env()
            print("[TxStorage.reopen] ✅ Reopened LMDB environment.")

    def close(self):
        """
        Close the LMDB environment to prevent lock errors on shutdown.
        """
        try:
            if self.txindex_db and hasattr(self.txindex_db, "env"):
                self.txindex_db.env.close()
                print("[TxStorage.close] ✅ LMDB environment closed successfully.")
        except Exception as e:
            print(f"[TxStorage.close] ❌ Failed to close LMDB: {e}")

    def is_env_closed(self) -> bool:
        """
        Check if the LMDB environment is closed or invalid.
        """
        try:
            self.txindex_db.env.stat()
            return False
        except Exception:
            return True

    def get_transaction_count(self) -> int:
        """
        Returns the total number of stored transactions on a per-block basis.
        Uses metadata via BlockStorage, and falls back to full block store if needed.
        """
        try:
            if not self.block_storage:
                print("[TxStorage] ❌ Error: block_storage not initialized.")
                return 0

            total_count = 0
            seen_blocks = set()

            # Step 1: Use block_storage metadata DB
            with self.block_storage.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.startswith(b"blockmeta:"):
                        try:
                            meta = json.loads(value.decode("utf-8"))
                            height = meta.get("index", "??")
                            tx_count = meta.get("transaction_count", 0)
                            total_count += int(tx_count)
                            seen_blocks.add(height)
                            print(f"[TxStorage] 📘 Block {height} via metadata: {tx_count} txs")
                        except Exception as e:
                            print(f"[TxStorage] ⚠️ Failed to parse metadata for {key}: {e}")

            # Step 2: Fallback to full block store if any are missing
            with self.block_storage.full_block_store.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.startswith(b"block:"):
                        try:
                            block_index = int(key.decode().split(":")[1])
                            if block_index in seen_blocks:
                                continue

                            block_data = json.loads(value.decode("utf-8"))
                            txs = block_data.get("transactions", [])
                            total_count += len(txs)
                            print(f"[TxStorage] 📕 Block {block_index} via full block: {len(txs)} txs")
                        except Exception as e:
                            print(f"[TxStorage] ⚠️ Failed to parse block {key}: {e}")

            print(f"[TxStorage] ✅ Total transaction count: {total_count}")
            return total_count

        except Exception as e:
            print(f"[TxStorage] ❌ Error calculating transaction count: {e}")
            return 0




    def get_transactions_by_block(self, block_hash: str) -> List[Dict[str, Any]]:
        """
        Retrieve all transactions associated with a specific block hash.

        Args:
            block_hash (str): The hash of the block to retrieve transactions for.

        Returns:
            List of transaction dictionaries.
        """
        transactions = []
        try:
            prefix = f"block_tx:{block_hash}:".encode("utf-8")

            with self.txindex_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.startswith(prefix):
                        try:
                            tx_data = json.loads(value.decode("utf-8"))
                            transactions.append(tx_data)
                        except Exception as e:
                            print(f"[TxStorage.get_transactions_by_block] ⚠️ Failed to decode tx: {e}")
            print(f"[TxStorage.get_transactions_by_block] ✅ Retrieved {len(transactions)} transactions for block {block_hash[:12]}...")
            return transactions

        except Exception as e:
            print(f"[TxStorage.get_transactions_by_block] ❌ ERROR: Could not retrieve transactions for block {block_hash}: {e}")
            return []





    def store_transaction(
        self, tx_id: Union[str, bytes], block_hash: str, tx_data: dict, outputs: List[Dict], timestamp: int,
        tx_signature: bytes = b"", falcon_signature: bytes = b""
    ) -> None:
        try:
            if isinstance(tx_id, bytes):
                tx_id = tx_id.hex()

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

            # Use helper for transaction type detection
            tx_type_enum = self._detect_transaction_type(tx_data)
            tx_type = tx_type_enum.name if hasattr(tx_type_enum, "name") else str(tx_type_enum)
            print(f"[TxStorage.store_transaction] INFO: Detected transaction type: {tx_type}")

            # Fee calculation
            if tx_type == "COINBASE":
                tax_fee = miner_fee = Decimal("0.00")
            else:
                try:
                    total_output_amount = sum(Decimal(str(out["amount"])) for out in outputs)
                    fee_details = self.fee_model.calculate_fee_and_tax(
                        block_size=1,
                        payment_type=tx_type,
                        amount=total_output_amount,
                        tx_size=tx_data.get("size", 250)
                    )

                    tax_fee = Decimal(str(fee_details.get("tax_fee", Constants.MIN_TRANSACTION_FEE)))
                    miner_fee = Decimal(str(fee_details.get("miner_fee", Constants.MIN_TRANSACTION_FEE)))

                    print(f"[TxStorage.store_transaction] INFO: Fee Breakdown - Tax Fee: {tax_fee}, Miner Fee: {miner_fee}")
                except Exception as fee_error:
                    print(f"[TxStorage.store_transaction] ERROR: Fee calculation failed - {fee_error}")
                    return

            # Store Falcon Signature Hash
            try:
                txindex_path = Constants.get_db_path("txindex")
                hashed_signature = store_transaction_signature(
                    tx_id=tx_id.encode(),
                    falcon_signature=falcon_signature,
                    txindex_path=txindex_path
                )
            except Exception as sig_error:
                print(f"[TxStorage.store_transaction] WARNING: Failed to hash/store Falcon signature: {sig_error}")
                hashed_signature = b"\x00" * 48  # Fallback empty hash

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

            try:
                with self.txindex_db.env.begin(write=True) as txn:
                    txn.put(f"block_tx:{tx_id}".encode(), json.dumps(transaction_data).encode())
                print(f"[TxStorage.store_transaction] ✅ SUCCESS: Stored transaction {tx_id}.")
            except Exception as lmdb_error:
                print(f"[TxStorage.store_transaction] ⚠️ LMDB write failed: {lmdb_error}")
                print(f"[TxStorage.store_transaction] ⚠️ Attempting to reopen LMDB and retry...")

                # Reopen and retry once
                try:
                    if hasattr(self.txindex_db, "reopen"):
                        self.txindex_db.reopen()
                    with self.txindex_db.env.begin(write=True) as txn:
                        txn.put(f"block_tx:{tx_id}".encode(), json.dumps(transaction_data).encode())
                    print(f"[TxStorage.store_transaction] ✅ SUCCESS after retry: Stored transaction {tx_id}.")
                except Exception as retry_error:
                    print(f"[TxStorage.store_transaction] ❌ FINAL ERROR: Retry failed: {retry_error}")

        except Exception as e:
            print(f"[TxStorage.store_transaction] ❌ EXCEPTION: {e}")


    def _detect_transaction_type(self, tx: Union[Transaction, dict]) -> TransactionType:
        if isinstance(tx, dict):
            # Use 'type' field if available
            tx_type = tx.get("type", "").upper()
            return TransactionType[tx_type] if tx_type in TransactionType.__members__ else TransactionType.STANDARD
        elif isinstance(tx, CoinbaseTx):
            return TransactionType.COINBASE
        elif isinstance(tx, Transaction):
            if tx.tx_id.startswith(b'S-'):
                return TransactionType.SMART
            elif tx.tx_id.startswith(b'PID-') or tx.tx_id.startswith(b'CID-'):
                return TransactionType.INSTANT
        return TransactionType.STANDARD



    def get_transaction(self, tx_id: str) -> Optional[Dict]:
        """
        Retrieve a transaction from txindex.lmdb, and fallback to full_block_chain if missing.

        Args:
            tx_id (str): Transaction ID to look up.

        Returns:
            Optional[Dict]: Transaction data dictionary or None.
        """
        try:
            # ✅ Primary lookup in txindex.lmdb
            key = f"block_tx:{tx_id}".encode()
            data = self.txindex_db.get(key)

            if data:
                try:
                    transaction = json.loads(data.decode("utf-8"))
                    print(f"[TxStorage.get_transaction] ✅ SUCCESS: Retrieved transaction {tx_id} from txindex.lmdb.")
                    return transaction
                except (json.JSONDecodeError, UnicodeDecodeError) as decode_error:
                    print(f"[TxStorage.get_transaction] ❌ ERROR: Decoding failed in txindex: {decode_error}")
                    return None

            # ⚠️ Fallback to full_block_chain if tx is not found
            print(f"[TxStorage.get_transaction] ⚠️ TX {tx_id} not found in txindex.lmdb. Falling back to full_block_chain...")

            from Zyiron_Chain.storage.block_storage import BlockStorage
            from Zyiron_Chain.accounts.key_manager import KeyManager
            from Zyiron_Chain.transactions.coinbase import CoinbaseTx
            from Zyiron_Chain.transactions.tx import Transaction

            fallback_storage = BlockStorage(tx_storage=self, key_manager=KeyManager())
            all_blocks = fallback_storage.get_all_blocks()

            for block_dict in all_blocks:
                transactions = block_dict.get("transactions", [])
                for tx in transactions:
                    if isinstance(tx, dict):
                        tx_dict = tx
                    elif hasattr(tx, "to_dict"):
                        tx_dict = tx.to_dict()
                    else:
                        print("[TxStorage.get_transaction] ⚠️ Skipping invalid TX format in fallback.")
                        continue

                    if tx_dict.get("tx_id") != tx_id:
                        continue

                    print(f"[TxStorage.get_transaction] 🧩 Found TX {tx_id} in block #{block_dict.get('index')} (fallback). Reinserting...")

                    # Normalize Falcon signature
                    falcon_sig = tx_dict.get("falcon_signature", b"")
                    if isinstance(falcon_sig, str):
                        try:
                            falcon_sig = bytes.fromhex(falcon_sig)
                        except ValueError:
                            falcon_sig = b""

                    # Store Falcon-512 signature
                    tx_sig_hash = store_transaction_signature(
                        tx_id=tx_id.encode(),
                        falcon_signature=falcon_sig,
                        txindex_path=Constants.get_db_path("txindex")
                    )

                    # Reconstruct transaction object
                    if tx_dict.get("type") == "COINBASE":
                        tx_obj = CoinbaseTx.from_dict(tx_dict)
                    else:
                        tx_obj = Transaction.from_dict(tx_dict)

                    # Prepare data for reinsertion
                    transaction_data = tx_obj.to_dict()
                    transaction_data.update({
                        "block_hash": block_dict.get("hash"),
                        "outputs": tx_dict.get("outputs", []),
                        "timestamp": tx_dict.get("timestamp", int(time.time())),
                        "type": tx_dict.get("type", "STANDARD"),
                        "tax_fee": tx_dict.get("tax_fee", "0"),
                        "miner_fee": tx_dict.get("miner_fee", "0"),
                        "tx_signature_hash": tx_sig_hash.hex()
                    })

                    # Reinserting into txindex.lmdb
                    try:
                        with self.txindex_db.env.begin(write=True) as txn:
                            txn.put(key, json.dumps(transaction_data).encode("utf-8"))
                        print(f"[TxStorage.get_transaction] ✅ Reinjected TX {tx_id} into txindex.lmdb from full block store.")
                    except Exception as lmdb_error:
                        print(f"[TxStorage.get_transaction] ⚠️ Failed to reinsert TX into txindex.lmdb: {lmdb_error}")

                    return transaction_data

            print(f"[TxStorage.get_transaction] ❌ TX {tx_id} not found in full_block_chain either.")
            return None

        except Exception as e:
            print(f"[TxStorage.get_transaction] ❌ ERROR: Failed to retrieve transaction {tx_id}: {e}")
            return None

    def get_all_transactions(self) -> List[Dict]:
        """
        Retrieve all stored transactions in LMDB under 'block_tx:*' keys.
        Falls back to full_block_chain to recover missing transactions.

        Returns:
            List[Dict]: A list of transaction dictionaries.
        """
        transactions = {}
        try:
            print("[TxStorage.get_all_transactions] INFO: Scanning txindex.lmdb for all transactions...")

            # Step 1: Load from txindex.lmdb
            with self.txindex_db.env.begin() as txn:
                cursor = txn.cursor()
                for key_bytes, value_bytes in cursor:
                    try:
                        key_str = key_bytes.decode("utf-8", errors="ignore")
                        if not key_str.startswith("block_tx:"):
                            continue

                        tx_id = key_str.replace("block_tx:", "")
                        tx_json = value_bytes.decode("utf-8", errors="replace")
                        tx_data = json.loads(tx_json)

                        if isinstance(tx_data, dict):
                            transactions[tx_id] = tx_data
                            print(f"[TxStorage.get_all_transactions] ✅ Loaded TX {tx_id} from txindex.lmdb")
                        else:
                            print(f"[TxStorage.get_all_transactions] ⚠️ Invalid format for TX {tx_id}")
                    except Exception as e:
                        print(f"[TxStorage.get_all_transactions] ⚠️ Skipping malformed TX entry: {e}")
                        continue

            # Step 2: Fallback to full_block_chain for missing TXs
            from Zyiron_Chain.storage.block_storage import BlockStorage
            fallback_store = BlockStorage(self, self.fee_model.key_manager)  # Pass required args

            all_blocks = fallback_store.get_all_blocks()
            print(f"[TxStorage.get_all_transactions] INFO: Scanning {len(all_blocks)} blocks from full_block_chain for missing TXs...")

            for block in all_blocks:
                block_txns = block.get("transactions", []) if isinstance(block, dict) else getattr(block, "transactions", [])

                for tx in block_txns:
                    tx_obj = tx.to_dict() if hasattr(tx, "to_dict") else tx
                    tx_id = tx_obj.get("tx_id")
                    if not tx_id or tx_id in transactions:
                        continue  # Already indexed

                    # Fallback reindex
                    falcon_sig = getattr(tx, "falcon_signature", b"")
                    sig_hash = store_transaction_signature(
                        tx_id=tx_id.encode(),
                        falcon_signature=falcon_sig,
                        txindex_path=Constants.get_db_path("txindex")
                    )

                    transaction_data = {
                        "tx_id": tx_id,
                        "block_hash": block.get("hash", ""),
                        "data": tx_obj,
                        "outputs": tx_obj.get("outputs", []),
                        "timestamp": tx_obj.get("timestamp", int(time.time())),
                        "type": tx_obj.get("type", "STANDARD"),
                        "tax_fee": "0",
                        "miner_fee": "0",
                        "tx_signature_hash": sig_hash.hex()
                    }

                    with self.txindex_db.env.begin(write=True) as txn:
                        txn.put(f"block_tx:{tx_id}".encode(), json.dumps(transaction_data).encode())

                    transactions[tx_id] = transaction_data
                    print(f"[TxStorage.get_all_transactions] 🔁 Fallback indexed TX {tx_id} from full block storage.")

            print(f"[TxStorage.get_all_transactions] ✅ Total Transactions Retrieved: {len(transactions)}")
            return list(transactions.values())

        except Exception as e:
            print(f"[TxStorage.get_all_transactions] ❌ ERROR: Failed to retrieve all transactions: {e}")
            return []


    def create_dir_if_not_exists(path):
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"Created database directory: {path}")
