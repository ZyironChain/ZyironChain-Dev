import os
import sys
import json
import pickle
import struct
import hashlib
import threading
from decimal import Decimal
from typing import List, Optional, Dict, Tuple, Union

import lmdb

from Zyiron_Chain.storage.block_storage import BlockStorage
from Zyiron_Chain.transactions.coinbase import CoinbaseTx
from Zyiron_Chain.transactions.tx import Transaction

# Adjust system path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.utils.deserializer import Deserializer
from Zyiron_Chain.blockchain.block import Block

from decimal import Decimal, InvalidOperation
from typing import List, Dict


from decimal import Decimal
import threading
from typing import Dict
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.utxo_manager import UTXOManager



class UTXOStorage:
    """
    UTXOStorage manages unspent transaction outputs (UTXOs) and UTXO history in LMDB.

    Responsibilities:
      - Update UTXO databases for new blocks.
      - Store individual UTXOs with proper type conversion and standardized precision.
      - Retrieve UTXOs from storage with caching.
      - Export all UTXOs for indexing.
      - Fallback to BlockStorage for UTXO reconstruction if not found in LMDB.

    All operations use LMDB and rely on Constants for configuration.
    Detailed print statements are provided for each operation and error condition.
    """
    def __init__(self, utxo_manager: Optional[UTXOManager] = None, block_storage: Optional["BlockStorage"] = None):
        try:
            if utxo_manager is not None and not isinstance(utxo_manager, UTXOManager):
                raise ValueError("[UTXOStorage.__init__] ERROR: Invalid utxo_manager instance provided.")

            self.utxo_manager = utxo_manager
            self.block_storage = block_storage

            network_flag = Constants.NETWORK
            db_paths = Constants.NETWORK_DATABASES.get(network_flag)

            if not db_paths:
                raise ValueError(f"[UTXOStorage.__init__] ERROR: No database paths found for network '{network_flag}'.")

            utxo_db_path = db_paths.get("utxo")
            utxo_history_db_path = db_paths.get("utxo_history")

            if not utxo_db_path or not utxo_history_db_path:
                raise ValueError(f"[UTXOStorage.__init__] ERROR: Missing UTXO or UTXO History path for network '{network_flag}'.")

            # ✅ Use LMDBManager instead of raw lmdb
            self.utxo_db = LMDBManager(
                utxo_db_path,
                max_readers=200,
                max_dbs=200,
                writemap=True
            )

            self.utxo_history_db = LMDBManager(
                utxo_history_db_path,
                max_readers=200,
                max_dbs=200,
                writemap=True
            )

            self._cache: Dict[str, dict] = {}
            self._db_lock = threading.Lock()

            print(f"[UTXOStorage.__init__] ✅ Initialized for {network_flag}")
            print(f"[UTXOStorage.__init__] INFO: UTXO DB Path: {utxo_db_path}")
            print(f"[UTXOStorage.__init__] INFO: UTXO History DB Path: {utxo_history_db_path}")

            if self.block_storage:
                print("[UTXOStorage.__init__] 🔁 Fallback to BlockStorage enabled.")
            else:
                print("[UTXOStorage.__init__] ⚠️ No BlockStorage fallback provided.")

        except Exception as e:
            print(f"[UTXOStorage.__init__] ❌ ERROR: {e}")
            raise


    @property
    def env(self):
        return self.utxo_db.env  # ✅ gives access to LMDB env from outside

    def validate_utxos(self, transactions: Union[List[Dict], Block]) -> bool:
        """
        Validate that all transactions reference valid, unspent UTXOs.

        :param transactions: A list of transaction dictionaries or a Block object.
        :return: True if all transactions are valid, False otherwise.
        """
        try:
            print("[UTXOStorage.validate_utxos] INFO: Validating UTXOs...")

            # Handle both Block object and list of transactions
            if isinstance(transactions, Block):
                print(f"[UTXOStorage.validate_utxos] INFO: Validating UTXOs for Block {transactions.index}...")
                transactions = transactions.transactions
            elif not isinstance(transactions, list):
                print(f"[UTXOStorage.validate_utxos] ERROR: Invalid input type. Expected Block or list of transactions, got {type(transactions)}.")
                return False

            if not transactions:
                print("[UTXOStorage.validate_utxos] ERROR: No transactions provided.")
                return False

            for tx in transactions:
                if hasattr(tx, "to_dict"):
                    tx = tx.to_dict()

                if not isinstance(tx, dict) or "inputs" not in tx or "tx_id" not in tx:
                    print(f"[UTXOStorage.validate_utxos] ERROR: Invalid transaction format: {tx}")
                    return False

                tx_id = tx["tx_id"]

                for tx_input in tx["inputs"]:
                    if not isinstance(tx_input, dict):
                        print(f"[UTXOStorage.validate_utxos] ERROR: Invalid input format in transaction {tx_id}.")
                        return False

                    tx_out_id = tx_input.get("tx_out_id")
                    if not tx_out_id or not isinstance(tx_out_id, str):
                        print(f"[UTXOStorage.validate_utxos] ERROR: tx_out_id is missing or invalid in transaction {tx_id}.")
                        return False

                    try:
                        parsed_tx_id, output_index = self.parse_tx_out_id(tx_out_id)
                    except Exception as parse_err:
                        print(f"[UTXOStorage.validate_utxos] ERROR: Failed to parse tx_out_id '{tx_out_id}' in tx {tx_id}: {parse_err}")
                        return False

                    utxo = self.get_utxo(parsed_tx_id, output_index)
                    if not utxo:
                        print(f"[UTXOStorage.validate_utxos] ERROR: UTXO {parsed_tx_id}:{output_index} not found for tx {tx_id}.")
                        return False

                    if utxo.get("spent_status"):
                        print(f"[UTXOStorage.validate_utxos] ERROR: UTXO {parsed_tx_id}:{output_index} is already spent in tx {tx_id}.")
                        return False

            print("[UTXOStorage.validate_utxos] ✅ SUCCESS: All UTXOs validated successfully.")
            return True

        except Exception as e:
            print(f"[UTXOStorage.validate_utxos] ❌ ERROR: Failed to validate UTXOs: {e}")
            return False





    def _get_utxo_key(tx_id: str, output_index: int) -> str:
        """
        Generates a key for UTXO storage in LMDB.

        - tx_id: Transaction ID (SHA3-384 hash, stored as a hex string)
        - output_index: Output index as an integer

        Returns:
            A formatted string key: "utxo:{tx_id}:{output_index}"
        """
        try:
            if not isinstance(tx_id, str) or len(tx_id) != 96:
                raise ValueError(f"[UTXOStorage._get_utxo_key] ERROR: Invalid tx_id format. Expected 96-character hex string, got {tx_id}.")

            if not isinstance(output_index, int) or output_index < 0:
                raise ValueError(f"[UTXOStorage._get_utxo_key] ERROR: output_index must be a non-negative integer.")

            utxo_key = f"utxo:{tx_id}:{output_index}"
            print(f"[UTXOStorage._get_utxo_key] INFO: Generated UTXO key for tx_id {tx_id} at index {output_index}.")
            return utxo_key

        except Exception as e:
            print(f"[UTXOStorage._get_utxo_key] ERROR: Failed to generate UTXO key: {e}")
            raise


    def _serialize_utxo(tx_id: str, output_index: int, amount: Decimal, script_pub_key: str, is_locked: bool, block_height: int, spent_status: bool) -> Dict:
        """
        Serializes a UTXO into dictionary format for LMDB storage.

        Fields:
            - tx_id (str)            → SHA3-384 transaction hash (hex)
            - output_index (int)      → Output index of the UTXO
            - amount (Decimal)        → Amount stored with standardized precision
            - script_pub_key (str)    → Locking script as a string
            - is_locked (bool)        → Lock status (True = Locked, False = Unlocked)
            - block_height (int)      → Block height where the UTXO was created
            - spent_status (bool)     → Spent status (True = Spent, False = Unspent)

        Returns:
            - Dictionary representing the serialized UTXO
        """
        try:
            if not isinstance(tx_id, str) or len(tx_id) != 96:
                raise ValueError(f"[UTXOStorage._serialize_utxo] ERROR: Invalid tx_id format. Expected 96-character hex string, got {tx_id}.")

            if not isinstance(script_pub_key, str):
                raise ValueError(f"[UTXOStorage._serialize_utxo] ERROR: Invalid script_pub_key format. Expected string.")

            if not isinstance(amount, Decimal):
                raise ValueError(f"[UTXOStorage._serialize_utxo] ERROR: Amount must be of type Decimal.")

            utxo_data = {
                "tx_id": tx_id,
                "output_index": output_index,
                "amount": str(amount),  # Store amount as a string for precision
                "script_pub_key": script_pub_key,
                "is_locked": is_locked,
                "block_height": block_height,
                "spent_status": spent_status
            }

            print(f"[UTXOStorage._serialize_utxo] INFO: Serialized UTXO {tx_id} at index {output_index}.")
            return utxo_data

        except Exception as e:
            print(f"[UTXOStorage._serialize_utxo] ERROR: Failed to serialize UTXO: {e}")
            raise

    def _deserialize_utxo(utxo_data: str) -> dict:
        """
        Deserializes a UTXO from a JSON string back into a dictionary.

        Returns:
            - Dictionary with UTXO fields.
        """
        try:
            if not isinstance(utxo_data, str):
                raise ValueError(f"[UTXOStorage._deserialize_utxo] ERROR: Expected a JSON string, got {type(utxo_data)}.")

            utxo_dict = json.loads(utxo_data)

            required_fields = {"tx_id", "output_index", "amount", "script_pub_key", "is_locked", "block_height", "spent_status"}
            if not required_fields.issubset(utxo_dict.keys()):
                raise ValueError(f"[UTXOStorage._deserialize_utxo] ERROR: Missing required UTXO fields: {utxo_dict.keys()}.")

            utxo_dict["amount"] = Decimal(utxo_dict["amount"])  # Ensure precision for stored amounts

            print(f"[UTXOStorage._deserialize_utxo] INFO: Deserialized UTXO {utxo_dict['tx_id']} at index {utxo_dict['output_index']}.")
            return utxo_dict

        except json.JSONDecodeError as e:
            print(f"[UTXOStorage._deserialize_utxo] ERROR: JSON decoding failed: {e}")
            return {}

        except Exception as e:
            print(f"[UTXOStorage._deserialize_utxo] ERROR: Failed to deserialize UTXO: {e}")
            return {}


    def store_utxo(self, tx_id: str, output_index: int, amount: Decimal, script_pub_key: str, is_locked: bool, block_height: int) -> bool:
        """
        Stores a UTXO in `utxo.lmdb` with full fallback validation, key standardization, and duplicate protection.

        Args:
            tx_id (str): Transaction ID (SHA3-384 hash as a hex string).
            output_index (int): The index of the output in the transaction.
            amount (Decimal): The amount in smallest units.
            script_pub_key (str): The locking script.
            is_locked (bool): Whether the UTXO is locked.
            block_height (int): The block height in which the UTXO was created.

        Returns:
            bool: True if successfully stored, False otherwise.
        """
        try:
            # ✅ Validate input types
            if not isinstance(tx_id, str) or len(tx_id) != 96:
                raise ValueError(f"[UTXOStorage.store_utxo] ERROR: tx_id must be 96-character hex string. Got: {tx_id}")

            if not isinstance(output_index, int) or output_index < 0:
                raise ValueError(f"[UTXOStorage.store_utxo] ERROR: output_index must be non-negative int.")

            if not isinstance(amount, Decimal):
                try:
                    amount = Decimal(str(amount))  # Fallback casting
                except Exception as e:
                    raise ValueError(f"[UTXOStorage.store_utxo] ERROR: Invalid amount: {amount} | {e}")

            if not isinstance(script_pub_key, str) or not script_pub_key.strip():
                raise ValueError(f"[UTXOStorage.store_utxo] ERROR: script_pub_key must be a non-empty string.")

            # ✅ Construct unique UTXO key
            utxo_key = f"utxo:{tx_id}:{output_index}".encode("utf-8")

            # ✅ Build UTXO dictionary
            utxo_data = {
                "tx_id": tx_id,
                "output_index": output_index,
                "amount": str(amount),
                "script_pub_key": script_pub_key,
                "is_locked": is_locked,
                "block_height": block_height,
                "spent_status": False  # Always unspent at creation
            }

            serialized = json.dumps(utxo_data, sort_keys=True).encode("utf-8")

            with self.utxo_db.env.begin(write=True) as txn:
                # ✅ Check for existing entry before overwrite
                if txn.get(utxo_key):
                    print(f"[UTXOStorage.store_utxo] ⚠️ WARNING: UTXO {tx_id}:{output_index} already exists. Skipping storage.")
                    return False

                txn.put(utxo_key, serialized)

            print(f"[UTXOStorage.store_utxo] ✅ SUCCESS: Stored UTXO {tx_id}:{output_index} for {amount} ZYC.")
            return True

        except Exception as e:
            print(f"[UTXOStorage.store_utxo] ❌ ERROR: Failed to store UTXO {tx_id}:{output_index}: {e}")
            return False



    def get_utxo(self, tx_id: str, output_index: int) -> Optional[Dict]:
        """
        Retrieve a UTXO from LMDB.
        Checks internal cache first, then queries the LMDB database.

        Args:
            tx_id (str): Transaction ID (SHA3-384 hash as a hex string).
            output_index (int): Output index.

        Returns:
            Optional[Dict]: UTXO data if found, otherwise None.
        """
        try:
            # ✅ Validate tx_id and output_index types
            if not isinstance(tx_id, str) or len(tx_id) != 96:
                raise ValueError(f"[UTXOStorage.get_utxo] ❌ Invalid tx_id: {tx_id}")
            if not isinstance(output_index, int) or output_index < 0:
                raise ValueError(f"[UTXOStorage.get_utxo] ❌ Invalid output_index: {output_index}")

            utxo_key = f"utxo:{tx_id}:{output_index}"

            # ✅ Check in-memory cache
            if utxo_key in self._cache:
                print(f"[UTXOStorage.get_utxo] ✅ Retrieved {utxo_key} from cache.")
                return self._cache[utxo_key]

            # ✅ Thread-safe access to LMDB
            with self._db_lock:
                with self.utxo_db.env.begin(write=False) as txn:
                    raw_value = txn.get(utxo_key.encode("utf-8"))
                    if not raw_value:
                        print(f"[UTXOStorage.get_utxo] ⚠️ UTXO {utxo_key} not found in LMDB.")
                        return None

                    try:
                        utxo_dict = json.loads(raw_value.decode("utf-8"))
                        self._cache[utxo_key] = utxo_dict  # Cache it
                        print(f"[UTXOStorage.get_utxo] ✅ Retrieved {utxo_key} from LMDB and cached.")
                        return utxo_dict
                    except json.JSONDecodeError as json_err:
                        print(f"[UTXOStorage.get_utxo] ❌ JSON decode error for {utxo_key}: {json_err}")
                        return None

        except Exception as e:
            print(f"[UTXOStorage.get_utxo] ❌ ERROR: Failed to retrieve {tx_id}:{output_index}: {e}")
            return None



    def get(self, tx_out_id: str) -> Optional[Dict]:
        """
        Retrieve a UTXO from LMDB using the combined tx_out_id format: 'tx_id:output_index'.

        :param tx_out_id: UTXO ID in the format 'tx_id:output_index'.
        :return: Dictionary containing the UTXO data or None if not found.
        """
        try:
            if not isinstance(tx_out_id, str) or ":" not in tx_out_id:
                print(f"[UTXOStorage.get] ❌ ERROR: Invalid tx_out_id format: {tx_out_id}")
                return None

            tx_id, output_index_str = tx_out_id.split(":")
            output_index = int(output_index_str)

            print(f"[UTXOStorage.get] 🔍 Parsed tx_out_id: tx_id={tx_id}, output_index={output_index}")
            return self.get_utxo(tx_id, output_index)

        except ValueError:
            print(f"[UTXOStorage.get] ❌ ERROR: output_index must be an integer in tx_out_id: {tx_out_id}")
            return None

        except Exception as e:
            print(f"[UTXOStorage.get] ❌ ERROR: Failed to retrieve UTXO {tx_out_id}: {e}")
            return None


    def get_all_utxos(self) -> List[dict]:
        """
        Retrieve all UTXOs stored in LMDB.
        Useful for dashboard visualization or indexing.
        """
        results = []
        try:
            with self.utxo_db.env.begin() as txn:
                cursor = txn.cursor()
                for key_bytes, value_bytes in cursor:
                    key_str = key_bytes.decode("utf-8", errors="ignore")
                    if not key_str.startswith("utxo:"):
                        continue

                    try:
                        data = value_bytes.tobytes() if isinstance(value_bytes, memoryview) else value_bytes
                        utxo_dict = json.loads(data.decode("utf-8"))
                        results.append(utxo_dict)
                    except Exception as decode_err:
                        print(f"[get_all_utxos] ⚠️ Skipping invalid entry {key_str}: {decode_err}")
                        continue

            print(f"[get_all_utxos] ✅ Retrieved {len(results)} UTXOs from LMDB.")
            return results

        except Exception as e:
            print(f"[get_all_utxos] ❌ ERROR: Failed to retrieve UTXOs: {e}")
            return []


    def update_utxos(self, block) -> None:
        """
        Update UTXO databases (`utxo.lmdb` & `utxo_history.lmdb`) for the given block.
        """
        try:
            print(f"[UTXOStorage.update_utxos] INFO: Updating UTXOs for Block {block.index}...")

            # ✅ Ensure LMDB environment is open
            if not hasattr(self.utxo_db, "env") or not self.utxo_db.env:
                print("[UTXOStorage.update_utxos] WARNING: LMDB environment is closed. Reopening...")
                self.utxo_db.reopen()

            if not hasattr(self.utxo_history_db, "env") or not self.utxo_history_db.env:
                print("[UTXOStorage.update_utxos] WARNING: LMDB history environment is closed. Reopening...")
                self.utxo_history_db.reopen()

            with self._db_lock:
                with self.utxo_db.env.begin(write=True) as utxo_txn, \
                    self.utxo_history_db.env.begin(write=True) as history_txn:

                    # ✅ Step 1: Archive and remove spent UTXOs
                    for tx in block.transactions:
                        inputs = tx.get("inputs", []) if isinstance(tx, dict) else getattr(tx, "inputs", [])

                        for tx_input in inputs:
                            input_tx_id = tx_input.get("tx_id") if isinstance(tx_input, dict) else getattr(tx_input, "tx_id", None)
                            input_index = tx_input.get("output_index") if isinstance(tx_input, dict) else getattr(tx_input, "output_index", None)

                            if not input_tx_id or input_index is None:
                                print("[UTXOStorage.update_utxos] ⚠️ WARNING: Invalid TX input format. Skipping.")
                                continue

                            utxo_key = f"utxo:{input_tx_id}:{input_index}".encode()
                            spent_utxo = utxo_txn.get(utxo_key)

                            if spent_utxo:
                                history_key = f"spent_utxo:{input_tx_id}:{input_index}:{block.timestamp}".encode()
                                history_txn.put(history_key, spent_utxo)
                                utxo_txn.delete(utxo_key)
                                print(f"[UTXOStorage.update_utxos] ✅ Archived and removed spent UTXO: {input_tx_id}:{input_index}")
                            else:
                                print(f"[UTXOStorage.update_utxos] ⚠️ Spent UTXO not found: {input_tx_id}:{input_index}")

                    # ✅ Step 2: Register new UTXOs
                    for tx in block.transactions:
                        tx_id = tx.get("tx_id") if isinstance(tx, dict) else getattr(tx, "tx_id", None)
                        outputs = tx.get("outputs", []) if isinstance(tx, dict) else getattr(tx, "outputs", [])

                        if not tx_id:
                            print(f"[UTXOStorage.update_utxos] ⚠️ WARNING: Transaction missing tx_id. Skipping.")
                            continue

                        is_coinbase = isinstance(tx, CoinbaseTx) or (isinstance(tx, dict) and tx.get("type") == "COINBASE")

                        for idx, output in enumerate(outputs):
                            try:
                                # Convert output if it's a dict
                                if isinstance(output, dict):
                                    output = TransactionOut.from_dict(output)

                                if not isinstance(output, TransactionOut):
                                    raise ValueError("Invalid TransactionOut format")

                                utxo_key = f"utxo:{tx_id}:{idx}".encode()
                                utxo_data = {
                                    "tx_id": tx_id,
                                    "output_index": idx,
                                    "amount": str(output.amount),
                                    "script_pub_key": output.script_pub_key,
                                    "is_locked": output.locked,
                                    "block_height": block.index,
                                    "spent_status": False
                                }
                                utxo_value = json.dumps(utxo_data, sort_keys=True).encode()

                                # Insert only if not already exists
                                if not utxo_txn.get(utxo_key):
                                    utxo_txn.put(utxo_key, utxo_value)
                                    label = "Coinbase" if is_coinbase else "Standard"
                                    print(f"[UTXOStorage.update_utxos] ✅ Stored {label} UTXO {tx_id}:{idx} amount {output.amount}")
                                else:
                                    print(f"[UTXOStorage.update_utxos] ⚠️ UTXO {tx_id}:{idx} already exists. Skipping.")

                                archive_key = f"new_utxo:{tx_id}:{idx}:{block.timestamp}".encode()
                                history_txn.put(archive_key, utxo_value)

                            except Exception as e:
                                print(f"[UTXOStorage.update_utxos] ❌ ERROR: Failed to process output {idx} in tx {tx_id}: {e}")
                                continue

                    # ✅ Step 3: Fallback UTXO Integrity Check
                    self._verify_utxo_integrity(block)

            print(f"[UTXOStorage.update_utxos] ✅ SUCCESS: All UTXOs updated for Block {block.index}.")

        except Exception as e:
            print(f"[UTXOStorage.update_utxos] ❌ ERROR: Failed to update UTXOs for block {getattr(block, 'index', '?')}: {e}")
            raise


    def validate_utxo(self, tx_id: str, output_index: int, amount: Decimal) -> bool:
        """
        Validate that a UTXO exists, is unlocked, and has sufficient balance.

        :param tx_id: Transaction ID (string, SHA3-384 hash in hex format).
        :param output_index: Output index (integer).
        :param amount: Amount to validate (Decimal).
        :return: True if UTXO is valid, False otherwise.
        """
        try:
            if not isinstance(tx_id, str) or len(tx_id) != 96:  # 96 hex chars = 48 bytes
                print(f"[UTXOStorage.validate_utxo] ERROR: Invalid tx_id format. Expected 96-character hex string, got {len(tx_id)}.")
                return False

            utxo_key = f"utxo:{tx_id}:{output_index}"

            # ✅ Retrieve UTXO from LMDB as JSON
            utxo_data = self.utxo_db.get(utxo_key)
            if not utxo_data:
                print(f"[UTXOStorage.validate_utxo] ERROR: UTXO {tx_id}:{output_index} does not exist.")
                return False

            utxo = json.loads(utxo_data)

            # ✅ Check if UTXO is locked
            if utxo["is_locked"]:
                print(f"[UTXOStorage.validate_utxo] ERROR: UTXO {tx_id}:{output_index} is locked and cannot be spent.")
                return False

            # ✅ Validate sufficient balance
            utxo_amount = Decimal(utxo["amount"])
            if utxo_amount < amount:
                print(f"[UTXOStorage.validate_utxo] ERROR: UTXO {tx_id}:{output_index} has insufficient balance. "
                      f"Required: {amount}, Available: {utxo_amount}")
                return False

            print(f"[UTXOStorage.validate_utxo] INFO: UTXO {tx_id}:{output_index} validated for spending. "
                  f"Required {amount}, Available {utxo_amount}")
            return True

        except Exception as e:
            print(f"[UTXOStorage.validate_utxo] ERROR: Failed to validate UTXO {tx_id}:{output_index}: {e}")
            return False



    def get_all_utxos_by_tx_id(self, tx_id: str) -> List[Dict]:
        """
        Retrieve all UTXOs associated with a given transaction ID.
        Supports fallback to full block storage if LMDB lookup fails.

        Args:
            tx_id (str): Transaction ID to search for.

        Returns:
            List[Dict]: List of UTXO dictionaries associated with the given tx_id.
        """
        results = []
        try:
            # ✅ First, scan active UTXO LMDB
            with self.utxo_db.env.begin() as txn:
                cursor = txn.cursor()
                for key_bytes, value_bytes in cursor:
                    key_str = key_bytes.decode("utf-8", errors="ignore")
                    if not key_str.startswith(f"utxo:{tx_id}:"):
                        continue

                    try:
                        value_raw = value_bytes.tobytes() if isinstance(value_bytes, memoryview) else value_bytes
                        utxo_dict = json.loads(value_raw.decode("utf-8"))
                        results.append(utxo_dict)
                    except Exception as e:
                        print(f"[get_all_utxos_by_tx_id] ⚠️ Skipping corrupted entry {key_str}: {e}")

            if results:
                print(f"[get_all_utxos_by_tx_id] ✅ Found {len(results)} UTXOs in LMDB for tx_id={tx_id}")
                return results

            # 🔁 Fallback: scan full block storage
            if not hasattr(self, "block_storage") or not self.block_storage:
                print("[get_all_utxos_by_tx_id] ❌ ERROR: Block storage not attached. Cannot perform fallback.")
                return []

            print(f"[get_all_utxos_by_tx_id] ⚠️ No LMDB UTXOs found for tx_id={tx_id}. Scanning full block storage...")

            from Zyiron_Chain.blockchain.block import Block
            from Zyiron_Chain.transactions.coinbase import CoinbaseTx
            from Zyiron_Chain.transactions.tx import Transaction
            from Zyiron_Chain.transactions.txout import TransactionOut

            def safe_deserialize_block(blk):
                try:
                    if isinstance(blk, dict):
                        return Block.from_dict(blk)
                    return blk
                except Exception as e:
                    print(f"[safe_deserialize_block] ❌ Failed to deserialize block: {e}")
                    return None

            all_blocks = self.block_storage.get_all_blocks()
            print(f"[get_all_utxos_by_tx_id] ✅ Loaded {len(all_blocks)} blocks from block storage.")

            for blk in all_blocks:
                block_obj = safe_deserialize_block(blk)
                if not block_obj:
                    continue

                for tx in getattr(block_obj, "transactions", []):
                    try:
                        tx_obj = (
                            CoinbaseTx.from_dict(tx)
                            if isinstance(tx, dict) and tx.get("type") == "COINBASE"
                            else Transaction.from_dict(tx)
                            if isinstance(tx, dict)
                            else tx
                        )
                    except Exception as deser:
                        print(f"[get_all_utxos_by_tx_id] ⚠️ Failed to parse tx: {deser}")
                        continue

                    if not hasattr(tx_obj, "tx_id") or tx_obj.tx_id != tx_id:
                        continue

                    for idx, output in enumerate(tx_obj.outputs):
                        try:
                            output_obj = TransactionOut.from_dict(output) if isinstance(output, dict) else output
                            utxo_entry = {
                                "tx_id": tx_id,
                                "output_index": idx,
                                "amount": str(output_obj.amount),
                                "script_pub_key": output_obj.script_pub_key,
                                "is_locked": output_obj.locked,
                                "block_height": getattr(block_obj, "index", 0),
                                "spent_status": False
                            }
                            results.append(utxo_entry)
                        except Exception as output_err:
                            print(f"[get_all_utxos_by_tx_id] ⚠️ Output parse error: {output_err}")
                            continue

            print(f"[get_all_utxos_by_tx_id] ✅ Fallback result: {len(results)} UTXOs recovered from full block storage for tx_id={tx_id}")
            return results

        except Exception as e:
            print(f"[get_all_utxos_by_tx_id] ❌ ERROR: Failed to get UTXOs for tx_id={tx_id}: {e}")
            return []





    def safe_deserialize_block(block_data) -> Optional["Block"]:
        """
        Robustly deserialize a block dict or object.
        Ensures transactions are deserialized into full objects (CoinbaseTx / Transaction).
        """
        from Zyiron_Chain.blockchain.block import Block
        from Zyiron_Chain.transactions.coinbase import CoinbaseTx
        from Zyiron_Chain.transactions.tx import Transaction

        try:
            # If it's already a Block instance, just return it
            if isinstance(block_data, Block):
                return block_data

            block_obj = Block.from_dict(block_data)
            tx_list = getattr(block_obj, "transactions", [])

            new_tx_list = []
            for tx in tx_list:
                if isinstance(tx, dict):
                    if tx.get("type") == "COINBASE":
                        tx_obj = CoinbaseTx.from_dict(tx)
                    else:
                        tx_obj = Transaction.from_dict(tx)
                    new_tx_list.append(tx_obj)
                else:
                    new_tx_list.append(tx)

            block_obj.transactions = new_tx_list
            return block_obj

        except Exception as e:
            print(f"[safe_deserialize_block] ❌ Failed to deserialize block: {e}")
            return None








    def mark_spent(self, tx_id: str, output_index: int) -> bool:
        try:
            utxo_key = f"utxo:{tx_id}:{output_index}".encode()
            with self.utxo_db.env.begin(write=True) as txn:
                raw = txn.get(utxo_key)
                if not raw:
                    print(f"[mark_spent] ⚠️ UTXO {tx_id}:{output_index} not found.")
                    return False

                utxo = json.loads(raw.decode("utf-8"))
                utxo["spent_status"] = True
                txn.put(utxo_key, json.dumps(utxo, sort_keys=True).encode())
                print(f"[mark_spent] ✅ UTXO {tx_id}:{output_index} marked as spent.")
                return True

        except Exception as e:
            print(f"[mark_spent] ❌ ERROR: {e}")
            return False



    def _verify_utxo_integrity(self, block) -> None:
        """
        Verify UTXO integrity against the full block storage as a fallback.

        Args:
            block: The block to verify UTXOs for.
        """
        try:
            print(f"[UTXOStorage._verify_utxo_integrity] INFO: Verifying UTXO integrity for Block {block.index}...")

            # Retrieve all UTXOs from the block
            block_utxos = []
            for tx in block.transactions:
                tx_id = tx.get("tx_id") if isinstance(tx, dict) else getattr(tx, "tx_id", None)
                outputs = tx.get("outputs", []) if isinstance(tx, dict) else getattr(tx, "outputs", [])

                if not tx_id:
                    continue

                for idx, output in enumerate(outputs):
                    utxo_key = f"utxo:{tx_id}:{idx}"
                    block_utxos.append(utxo_key)

            # Verify each UTXO in the block against the full block storage
            for utxo_key in block_utxos:
                with self.utxo_db.env.begin() as txn:
                    utxo_data = txn.get(utxo_key.encode())

                    if not utxo_data:
                        print(f"[UTXOStorage._verify_utxo_integrity] ⚠️ WARNING: UTXO {utxo_key} not found in active UTXO set. Falling back to full block storage...")

                        # Fallback: Retrieve UTXO from full block storage
                        fallback_utxo = self._get_utxo_from_full_block_storage(utxo_key)
                        if fallback_utxo:
                            print(f"[UTXOStorage._verify_utxo_integrity] ✅ FALLBACK: Retrieved UTXO {utxo_key} from full block storage.")
                            with self.utxo_db.env.begin(write=True) as txn:
                                txn.put(utxo_key.encode(), json.dumps(fallback_utxo).encode())
                        else:
                            print(f"[UTXOStorage._verify_utxo_integrity] ❌ ERROR: UTXO {utxo_key} not found in full block storage either.")

            print(f"[UTXOStorage._verify_utxo_integrity] ✅ SUCCESS: UTXO integrity verified for Block {block.index}.")

        except Exception as e:
            print(f"[UTXOStorage._verify_utxo_integrity] ❌ ERROR: Failed to verify UTXO integrity: {e}")



    def _get_utxo_from_full_block_storage(self, utxo_key: str) -> Optional[Dict]:
        """
        Retrieve a UTXO from the full block storage as a fallback.

        Args:
            utxo_key: The UTXO key to retrieve (e.g., "utxo:tx_id:output_index").

        Returns:
            Optional[Dict]: The UTXO data if found, otherwise None.
        """
        try:
            print(f"[UTXOStorage._get_utxo_from_full_block_storage] INFO: Retrieving UTXO {utxo_key} from full block storage...")

            # Parse UTXO key
            _, tx_id, output_index = utxo_key.split(":")
            output_index = int(output_index)

            # Retrieve the block containing the transaction
            block = self.block_storage.get_block_by_tx_id(tx_id)
            if not block:
                print(f"[UTXOStorage._get_utxo_from_full_block_storage] ❌ ERROR: Block containing TX {tx_id} not found.")
                return None

            # Find the UTXO in the block's transactions
            for tx in block.transactions:
                if tx.get("tx_id") == tx_id:
                    outputs = tx.get("outputs", [])
                    if output_index < len(outputs):
                        output = outputs[output_index]
                        return {
                            "tx_id": tx_id,
                            "output_index": output_index,
                            "amount": str(output.get("amount", "0")),
                            "script_pub_key": output.get("script_pub_key", ""),
                            "is_locked": output.get("locked", False),
                            "block_height": block.index,
                            "spent_status": False
                        }

            print(f"[UTXOStorage._get_utxo_from_full_block_storage] ❌ ERROR: UTXO {utxo_key} not found in block.")
            return None

        except Exception as e:
            print(f"[UTXOStorage._get_utxo_from_full_block_storage] ❌ ERROR: Failed to retrieve UTXO {utxo_key}: {e}")
            return None

    def attach_full_block_storage(self, full_block_storage):
        """Attach the full block storage (BlockStorage instance) for UTXO fallback."""
        self.full_block_storage = full_block_storage

    def _get_database(self, db_key: str) -> LMDBManager:
        """
        Retrieve the LMDB database instance for the given key using Constants.
        """
        try:
            db_path = Constants.NETWORK_DATABASES[Constants.NETWORK].get(db_key)
            if not db_path:
                raise ValueError(f"[UTXOStorage._get_database] ERROR: Unknown database key: {db_key}")
            return LMDBManager(db_path)
        except Exception as e:
            print(f"[UTXOStorage._get_database] ERROR: Failed to get database {db_key}: {e}")
            raise


    def create_dir_if_not_exists(path):
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"Created database directory: {path}")


    def set_manager(self, manager):
        self.manager = manager



    def get_utxos_by_address(self, address: str) -> List[dict]:
        """
        Retrieve all unspent UTXOs for a given address from LMDB safely.
        If not found in LMDB, fallback to full block store.
        Ensures every returned UTXO includes tx_out_id via TransactionOut.to_dict().
        """
        results = []
        found_in_lmdb = False

        try:
            # ✅ Try primary LMDB lookup
            with self.utxo_db.env.begin(write=False) as txn:
                cursor = txn.cursor()
                for key_bytes, value_raw in cursor:
                    try:
                        key_str = key_bytes.decode("utf-8", errors="ignore")
                        if not key_str.startswith("utxo:"):
                            continue

                        value_bytes = value_raw.tobytes() if isinstance(value_raw, memoryview) else value_raw
                        utxo_json = value_bytes.decode("utf-8", errors="replace")
                        utxo = json.loads(utxo_json)

                        if not isinstance(utxo, dict):
                            continue

                        if utxo.get("script_pub_key") != address:
                            continue
                        if utxo.get("spent_status", True):
                            continue

                        # ✅ Convert back to TransactionOut to ensure to_dict() includes tx_out_id
                        from Zyiron_Chain.transactions.txout import TransactionOut
                        tx_out = TransactionOut.from_dict(utxo)
                        results.append(tx_out.to_dict())
                        found_in_lmdb = True

                    except Exception as e:
                        print(f"[get_utxos_by_address] ⚠️ Skipping invalid UTXO: {e}")
                        continue

            if found_in_lmdb:
                print(f"[get_utxos_by_address] ✅ Found {len(results)} UTXOs from LMDB for address: {address}")
                return results

            # 🔁 Fallback: scan full block store if nothing found in LMDB
            if not hasattr(self, "block_storage"):
                print(f"[get_utxos_by_address] ❌ ERROR: Block storage fallback not enabled.")
                return []

            print(f"[get_utxos_by_address] ⚠️ No valid UTXOs found in LMDB. Scanning full block storage...")
            all_blocks = self.block_storage.get_all_blocks()

            for block in all_blocks:
                transactions = block.transactions if isinstance(block.transactions, list) else []
                for tx in transactions:
                    outputs = getattr(tx, "outputs", []) if not isinstance(tx, dict) else tx.get("outputs", [])
                    tx_id = getattr(tx, "tx_id", None) if not isinstance(tx, dict) else tx.get("tx_id")

                    for idx, output in enumerate(outputs):
                        try:
                            if isinstance(output, dict):
                                script = output.get("script_pub_key")
                                amount = Decimal(output.get("amount", "0"))
                                locked = output.get("locked", False)
                            else:
                                script = getattr(output, "script_pub_key", None)
                                amount = Decimal(getattr(output, "amount", 0))
                                locked = getattr(output, "locked", False)

                            if script != address:
                                continue

                            utxo_entry = {
                                "tx_out_id": f"{tx_id}:{idx}",
                                "amount": str(amount),
                                "script_pub_key": script,
                                "locked": locked,
                                "spent_status": False,
                                "block_height": block.index
                            }
                            results.append(utxo_entry)

                            # 🔁 Store in LMDB
                            self.store_utxo(
                                tx_id=tx_id,
                                output_index=idx,
                                amount=amount,
                                script_pub_key=script,
                                is_locked=locked,
                                block_height=block.index
                            )

                            print(f"[get_utxos_by_address] ✅ Recovered UTXO from block {block.index} for address: {address}")

                        except Exception as e:
                            print(f"[get_utxos_by_address] ⚠️ Error while processing fallback output: {e}")
                            continue

            print(f"[get_utxos_by_address] ✅ Total UTXOs found (LMDB + fallback): {len(results)}")
            return results

        except Exception as general_error:
            print(f"[get_utxos_by_address] ❌ General Error: {general_error}")
            return []



    def recover_missing_utxos_from_blockchain(self, address: str) -> int:
        """
        Scan full block storage for UTXOs for a given address if they are missing in LMDB.

        Returns:
            int: Count of recovered UTXOs.
        """
        if not hasattr(self, "block_storage"):
            print("[recover_missing_utxos_from_blockchain] ❌ ERROR: Block storage not attached. Use `enable_block_storage_fallback()` first.")
            return 0

        recovered = 0
        try:
            print(f"[recover_missing_utxos_from_blockchain] 🔍 Scanning full block storage for address: {address}")

            all_blocks = self.block_storage.get_all_blocks()
            for block in all_blocks:
                for tx in block.transactions:
                    for idx, output in enumerate(tx.outputs):
                        if output.script_pub_key != address:
                            continue

                        utxo_key = f"utxo:{tx.tx_id}:{idx}".encode("utf-8")

                        with self.utxo_db.env.begin() as txn:
                            if txn.get(utxo_key):
                                continue  # Already stored

                        self.store_utxo(
                            tx_id=tx.tx_id,
                            output_index=idx,
                            amount=Decimal(output.amount),
                            script_pub_key=output.script_pub_key,
                            is_locked=output.locked,
                            block_height=block.index
                        )
                        recovered += 1

            print(f"[recover_missing_utxos_from_blockchain] ✅ Recovered {recovered} missing UTXOs for address: {address}")
            return recovered

        except Exception as e:
            print(f"[recover_missing_utxos_from_blockchain] ❌ ERROR: {e}")
            return 0



    def enable_block_storage_fallback(self, block_storage):
        """
        Attach a reference to BlockStorage for fallback UTXO retrieval.

        Args:
            block_storage: An instance of BlockStorage.
        """
        if not hasattr(block_storage, "get_all_blocks"):
            raise ValueError("[UTXOStorage.enable_block_storage_fallback] ERROR: Invalid block_storage instance provided.")

        self.block_storage = block_storage
        print("[UTXOStorage] ✅ Fallback block storage enabled.")







    def get_all_utxos_by_tx_id(self, tx_id: str) -> List[dict]:
        """
        Retrieve all UTXOs associated with a given tx_id from full block storage.
        """
        results = []
        try:
            if not self.block_storage:
                print("[get_all_utxos_by_tx_id] ❌ ERROR: Block storage not attached.")
                return []

            blocks = self.block_storage.get_all_blocks()
            for block in blocks:
                for tx in block.transactions:
                    if isinstance(tx, dict):
                        if tx.get("tx_id") != tx_id:
                            continue
                        outputs = tx.get("outputs", [])
                    else:
                        if getattr(tx, "tx_id", "") != tx_id:
                            continue
                        outputs = getattr(tx, "outputs", [])

                    for idx, output in enumerate(outputs):
                        utxo_entry = {
                            "tx_id": tx_id,
                            "output_index": idx,
                            "amount": str(output.get("amount") if isinstance(output, dict) else output.amount),
                            "script_pub_key": output.get("script_pub_key") if isinstance(output, dict) else output.script_pub_key,
                            "is_locked": output.get("locked") if isinstance(output, dict) else output.locked,
                            "block_height": block.index,
                            "spent_status": False
                        }
                        results.append(utxo_entry)

            print(f"[get_all_utxos_by_tx_id] ✅ Found {len(results)} UTXOs for tx_id={tx_id}")
            return results

        except Exception as e:
            print(f"[get_all_utxos_by_tx_id] ❌ ERROR: Failed to get UTXOs for tx_id={tx_id}: {e}")
            return []











    @staticmethod
    def parse_tx_out_id(tx_out_id: str) -> Tuple[str, int]:
        """
        Split tx_out_id (e.g., "abc123...:1") into tx_id and output_index
        """
        try:
            tx_id, index_str = tx_out_id.split(":")
            return tx_id, int(index_str)
        except Exception as e:
            print(f"[parse_tx_out_id] ❌ ERROR: {e}")
            raise ValueError("Invalid tx_out_id format. Expected 'tx_id:output_index'")
