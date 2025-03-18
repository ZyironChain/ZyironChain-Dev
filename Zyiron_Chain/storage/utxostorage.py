import os
import sys
import json
import pickle
import struct
import hashlib
import threading
from decimal import Decimal
from typing import List, Optional, Dict, Union

# Adjust system path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.utils.deserializer import Deserializer
from Zyiron_Chain.blockchain.block import Block




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
    
    All operations use LMDB and rely on Constants for configuration.
    Detailed print statements are provided for each operation and error condition.
    """

    def __init__(self, utxo_manager: UTXOManager):
        """
        Initialize UTXOStorage.

        Args:
            utxo_manager: An instance of UTXOManager.
        """
        try:
            # ✅ Ensure utxo_manager is valid
            if not isinstance(utxo_manager, UTXOManager):
                raise ValueError("[UTXOStorage.__init__] ERROR: Invalid utxo_manager instance provided.")

            self.utxo_manager = utxo_manager  # ✅ Store UTXOManager reference

            # ✅ Determine the correct database paths based on the active network
            network_flag = Constants.NETWORK
            db_paths = Constants.NETWORK_DATABASES.get(network_flag)

            if not db_paths:
                raise ValueError(f"[UTXOStorage.__init__] ERROR: No database paths found for network {network_flag}.")

            utxo_db_path = db_paths.get("utxo")
            utxo_history_db_path = db_paths.get("utxo_history")

            if not utxo_db_path or not utxo_history_db_path:
                raise ValueError(f"[UTXOStorage.__init__] ERROR: Missing UTXO database paths for {network_flag}.")

            # ✅ Initialize LMDB for UTXO storage
            self.utxo_db = LMDBManager(utxo_db_path)
            self.utxo_history_db = LMDBManager(utxo_history_db_path)

            # ✅ Local Cache for UTXO Lookups
            self._cache: Dict[str, dict] = {} # type: ignore
            self._db_lock = threading.Lock()

            print(f"[UTXOStorage.__init__] ✅ SUCCESS: UTXOStorage initialized for {network_flag}.")
            print(f"[UTXOStorage.__init__] INFO: UTXO Database Path: {utxo_db_path}")
            print(f"[UTXOStorage.__init__] INFO: UTXO History Database Path: {utxo_history_db_path}")

        except Exception as e:
            print(f"[UTXOStorage.__init__] ❌ ERROR: Failed to initialize UTXOStorage: {e}")
            raise


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
                    output_index = tx_input.get("output_index")

                    if not tx_out_id or not isinstance(tx_out_id, str) or not isinstance(output_index, int):
                        print(f"[UTXOStorage.validate_utxos] ERROR: Missing or invalid UTXO reference in transaction {tx_id}.")
                        return False

                    # ✅ Retrieve UTXO from storage (calls LMDB database)
                    utxo = self.utxo_db.get(f"utxo:{tx_out_id}:{output_index}")

                    if not utxo:
                        print(f"[UTXOStorage.validate_utxos] ERROR: UTXO {tx_out_id} at index {output_index} not found for tx {tx_id}.")
                        return False

                    if utxo.get("spent_status"):
                        print(f"[UTXOStorage.validate_utxos] ERROR: UTXO {tx_out_id}:{output_index} is already spent in tx {tx_id}.")
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
        Stores a UTXO in `utxo.lmdb` with proper validation and JSON serialization.

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
            # ✅ Ensure Transaction ID is a valid hex string
            if not isinstance(tx_id, str) or len(tx_id) != 96:  
                raise ValueError(f"[UTXOStorage.store_utxo] ERROR: Invalid tx_id format. Expected 96-character hex, got {tx_id}.")

            # ✅ Ensure Output Index is Valid
            if not isinstance(output_index, int) or output_index < 0:
                raise ValueError(f"[UTXOStorage.store_utxo] ERROR: Invalid output_index. Must be a non-negative integer.")

            # ✅ Ensure Amount is a Decimal
            if not isinstance(amount, Decimal):
                raise ValueError(f"[UTXOStorage.store_utxo] ERROR: Amount must be a Decimal.")

            # ✅ Ensure ScriptPubKey is a String
            if not isinstance(script_pub_key, str):
                raise ValueError(f"[UTXOStorage.store_utxo] ERROR: script_pub_key must be a string.")

            # ✅ Construct UTXO Dictionary
            utxo_data = {
                "tx_id": tx_id,
                "output_index": output_index,
                "amount": str(amount),  
                "script_pub_key": script_pub_key,
                "is_locked": is_locked,
                "block_height": block_height,
                "spent_status": False  
            }

            # ✅ Convert UTXO Data to JSON
            serialized_data = json.dumps(utxo_data, sort_keys=True)

            # ✅ Generate Key for LMDB Storage
            utxo_key = f"utxo:{tx_id}:{output_index}"

            # ✅ Store UTXO in LMDB
            with self.utxo_db.env.begin(write=True) as txn:
                txn.put(utxo_key.encode("utf-8"), serialized_data.encode("utf-8"))

            print(f"[UTXOStorage.store_utxo] ✅ SUCCESS: Stored UTXO {tx_id} at index {output_index}, amount {amount}.")
            return True

        except Exception as e:
            print(f"[UTXOStorage.store_utxo] ❌ ERROR: Failed to store UTXO {tx_id} at index {output_index}: {e}")
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
            utxo_key = f"utxo:{tx_id}:{output_index}"

            # ✅ Check Cache First
            if utxo_key in self._cache:
                print(f"[UTXOStorage.get_utxo] INFO: Retrieved UTXO {utxo_key} from cache.")
                return self._cache[utxo_key]

            # ✅ Retrieve from LMDB
            utxo_data = self.utxo_db.get(utxo_key)

            if not utxo_data:
                print(f"[UTXOStorage.get_utxo] WARNING: UTXO {utxo_key} not found.")
                return None

            # ✅ Parse JSON Data
            utxo_entry = json.loads(utxo_data)
            self._cache[utxo_key] = utxo_entry  # Cache the retrieved UTXO

            print(f"[UTXOStorage.get_utxo] INFO: Retrieved UTXO {utxo_key} from storage and cached it.")
            return utxo_entry

        except Exception as e:
            print(f"[UTXOStorage.get_utxo] ERROR: UTXO retrieval failed for {tx_id}:{output_index}: {e}")
            return None


    def update_utxos(self, block) -> None:
        """
        Update UTXO databases (`utxo.lmdb` & `utxo_history.lmdb`) for the given block.

        Steps:
        1. Validate and remove spent UTXOs, archiving them in `utxo_history.lmdb`.
        2. Validate and add new UTXOs from block transactions.
        """
        try:
            print(f"[UTXOStorage.update_utxos] INFO: Updating UTXOs for Block {block.index}...")

            with self._db_lock:
                with self.utxo_db.env.begin(write=True) as utxo_txn, \
                    self.utxo_history_db.env.begin(write=True) as history_txn:

                    # ✅ **Step 1: Remove Spent UTXOs**
                    for tx in block.transactions:
                        # ✅ Handle transaction as a dictionary
                        if isinstance(tx, dict):
                            inputs = tx.get("inputs", [])
                        else:
                            inputs = getattr(tx, "inputs", [])

                        for tx_input in inputs:
                            # ✅ Handle input as a dictionary
                            if isinstance(tx_input, dict):
                                input_tx_id = tx_input.get("tx_id")
                                input_index = tx_input.get("output_index")
                            else:
                                input_tx_id = getattr(tx_input, "tx_id", None)
                                input_index = getattr(tx_input, "output_index", None)

                            if input_tx_id is None or input_index is None:
                                print(f"[UTXOStorage.update_utxos] ⚠️ WARNING: Invalid input format in transaction {tx.get('tx_id', 'UNKNOWN')}.")
                                continue

                            utxo_key = f"utxo:{input_tx_id}:{input_index}"
                            spent_utxo = utxo_txn.get(utxo_key.encode())

                            if spent_utxo:
                                # ✅ **Move Spent UTXO to History**
                                history_key = f"spent_utxo:{input_tx_id}:{input_index}:{block.timestamp}"
                                history_txn.put(history_key.encode(), spent_utxo)

                                # ✅ **Delete Spent UTXO**
                                utxo_txn.delete(utxo_key.encode())
                                print(f"[UTXOStorage.update_utxos] ✅ INFO: Spent UTXO {input_tx_id}:{input_index} archived.")
                            else:
                                print(f"[UTXOStorage.update_utxos] ⚠️ WARNING: Spent UTXO {input_tx_id}:{input_index} not found.")

                    # ✅ **Step 2: Add New UTXOs**
                    for tx in block.transactions:
                        # ✅ Handle transaction as a dictionary
                        if isinstance(tx, dict):
                            tx_id = tx.get("tx_id")
                            outputs = tx.get("outputs", [])
                        else:
                            tx_id = getattr(tx, "tx_id", None)
                            outputs = getattr(tx, "outputs", [])

                        if not tx_id:
                            print(f"[UTXOStorage.update_utxos] ⚠️ WARNING: Transaction missing 'tx_id'. Skipping.")
                            continue

                        for idx, output in enumerate(outputs):
                            # ✅ Handle output as a dictionary
                            if isinstance(output, dict):
                                try:
                                    output = TransactionOut.from_dict(output)  # Convert to TransactionOut
                                except Exception as e:
                                    print(f"[UTXOStorage.update_utxos] ❌ ERROR: Failed to convert output at index {idx} in transaction {tx_id}: {e}")
                                    continue

                            # ✅ Ensure output has required fields
                            if not isinstance(output, TransactionOut) or not all(hasattr(output, attr) for attr in ["amount", "script_pub_key", "locked"]):
                                print(f"[UTXOStorage.update_utxos] ❌ ERROR: Invalid UTXO format in transaction {tx_id}, skipping output {idx}.")
                                continue

                            # ✅ Format UTXO data as JSON
                            utxo_data = json.dumps({
                                "tx_id": tx_id,
                                "output_index": idx,
                                "amount": str(output.amount),
                                "script_pub_key": output.script_pub_key,
                                "is_locked": output.locked,
                                "block_height": block.index,
                                "spent_status": False
                            }, sort_keys=True)

                            utxo_key = f"utxo:{tx_id}:{idx}".encode()
                            utxo_txn.put(utxo_key, utxo_data.encode())

                            # ✅ Store new UTXO in `utxo_history.lmdb`
                            history_key = f"new_utxo:{tx_id}:{idx}:{block.timestamp}".encode()
                            history_txn.put(history_key, utxo_data.encode())

                            print(f"[UTXOStorage.update_utxos] ✅ INFO: Added new UTXO {tx_id}:{idx}, amount {output.amount}.")

            print(f"[UTXOStorage.update_utxos] ✅ SUCCESS: UTXOs updated successfully for Block {block.index}.")

        except Exception as e:
            print(f"[UTXOStorage.update_utxos] ❌ ERROR: Failed updating UTXOs: {e}")
            raise



    def export_utxos(self) -> None:
        """
        Export all unspent UTXOs to LMDB.
        Serializes each UTXO as JSON and performs a bulk put operation.
        """
        try:
            all_utxos = self.utxo_manager.get_all_utxos()
            if not all_utxos:
                print("[UTXOStorage.export_utxos] WARNING: No UTXOs available for export.")
                return

            with self.utxo_db.env.begin(write=True) as txn:
                for key, utxo in all_utxos.items():
                    try:
                        # ✅ Ensure UTXO data is formatted as JSON
                        utxo_data = json.dumps({
                            "tx_id": utxo["tx_id"],
                            "output_index": utxo["output_index"],
                            "amount": str(utxo["amount"]),
                            "script_pub_key": utxo["script_pub_key"],
                            "is_locked": utxo["is_locked"],
                            "block_height": utxo["block_height"],
                            "spent_status": utxo["spent_status"]
                        }, sort_keys=True)

                        utxo_key = f"utxo:{key}"
                        txn.put(utxo_key.encode("utf-8"), utxo_data.encode("utf-8"))

                    except (TypeError, ValueError, KeyError) as e:
                        print(f"[UTXOStorage.export_utxos] ERROR: Failed to serialize UTXO {key}: {e}")
                        continue

            print(f"[UTXOStorage.export_utxos] SUCCESS: Exported {len(all_utxos)} UTXOs.")

        except Exception as e:
            print(f"[UTXOStorage.export_utxos] ERROR: Failed to export UTXOs: {e}")

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
