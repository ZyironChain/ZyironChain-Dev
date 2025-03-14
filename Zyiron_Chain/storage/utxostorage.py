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
class UTXOStorage:
    """
    UTXOStorage manages unspent transaction outputs (UTXOs) and UTXO history in LMDB.
    
    Responsibilities:
      - Update UTXO databases for new blocks.
      - Store individual UTXOs with proper type conversion and standardized precision.
      - Retrieve UTXOs from storage with caching.
      - Export all UTXOs for indexing.
    
    All operations use data in bytes and rely on Constants for configuration.
    Detailed print statements are provided for each operation and error condition.
    """





    def __init__(self, utxo_db: LMDBManager, utxo_history_db: LMDBManager, utxo_manager):
        try:
            self.utxo_db = utxo_db
            self.utxo_history_db = utxo_history_db
            self.utxo_manager = utxo_manager  # Expects utxo_manager to have methods like get_all_utxos()
            self._cache: Dict[str, dict] = {}
            self._db_lock = threading.Lock()
            print("[UTXOStorage.__init__] SUCCESS: UTXOStorage initialized successfully.")
        except Exception as e:
            print(f"[UTXOStorage.__init__] ERROR: Failed to initialize UTXOStorage: {e}")
            raise




    def validate_utxos(self, transactions: Union[List[Dict], Block]) -> bool:
        """
        Validate that all transactions reference valid, unspent UTXOs.

        :param transactions: A list of transaction dictionaries or a Block object.
        :return: True if all transactions are valid, False otherwise.
        """
        try:
            print(f"[UTXOStorage.validate_utxos] INFO: Validating UTXOs...")

            # Handle both Block object and list of transactions
            if isinstance(transactions, Block):
                print(f"[UTXOStorage.validate_utxos] INFO: Validating UTXOs for Block {transactions.index}...")
                transactions = transactions.transactions
            elif not isinstance(transactions, list):
                print(f"[UTXOStorage.validate_utxos] ERROR: Invalid input type. Expected Block or list of transactions, got {type(transactions)}.")
                return False

            # Ensure transactions exist
            if not transactions:
                print(f"[UTXOStorage.validate_utxos] ERROR: No transactions provided.")
                return False

            for tx in transactions:
                # Serialize transaction if it's an object
                if hasattr(tx, "to_dict"):
                    tx = tx.to_dict()

                # Ensure transaction is a dictionary
                if not isinstance(tx, dict):
                    print(f"[UTXOStorage.validate_utxos] ERROR: Invalid transaction format: {tx}")
                    return False

                # Ensure required fields exist
                if "inputs" not in tx or "tx_id" not in tx:
                    print(f"[UTXOStorage.validate_utxos] ERROR: Missing required fields in transaction: {tx}")
                    return False

                tx_id = tx["tx_id"]  # Extract transaction ID

                # Validate inputs
                for tx_input in tx["inputs"]:
                    if not isinstance(tx_input, dict):
                        print(f"[UTXOStorage.validate_utxos] ERROR: Invalid input format in transaction {tx_id}.")
                        return False

                    tx_out_id = tx_input.get("tx_out_id")
                    output_index = tx_input.get("output_index", 0)

                    # Validate tx_out_id
                    if not tx_out_id or not isinstance(tx_out_id, str):
                        print(f"[UTXOStorage.validate_utxos] ERROR: Missing or invalid tx_out_id in transaction {tx_id}.")
                        return False

                    # Retrieve UTXO from storage
                    utxo = self.get_utxo(tx_out_id, output_index)
                    if not utxo:
                        print(f"[UTXOStorage.validate_utxos] ERROR: UTXO {tx_out_id} at index {output_index} not found for tx {tx_id}.")
                        return False

                    # Ensure UTXO is unspent
                    if utxo.get("spent_status"):
                        print(f"[UTXOStorage.validate_utxos] ERROR: UTXO {tx_out_id}:{output_index} is already spent in tx {tx_id}.")
                        return False

            print(f"[UTXOStorage.validate_utxos] ✅ SUCCESS: All UTXOs validated successfully.")
            return True

        except Exception as e:
            print(f"[UTXOStorage.validate_utxos] ❌ ERROR: Failed to validate UTXOs: {e}")
            return False





    def _get_utxo_key(tx_id: bytes, output_index: int) -> bytes:
        """
        Generates a binary key for UTXO storage in LMDB.

        - tx_id: 48-byte transaction ID (SHA3-384 hash)
        - output_index: 4-byte unsigned integer (big-endian)

        Returns:
            A binary key formatted as: b"utxo:" + tx_id (48B) + output_index (4B)
        """
        try:
            # ✅ Ensure tx_id is exactly 48 bytes
            if not isinstance(tx_id, bytes) or len(tx_id) != 48:
                raise ValueError(f"[UTXOStorage._get_utxo_key] ERROR: Invalid tx_id format. Expected 48 bytes, got {len(tx_id)}.")

            # ✅ Ensure output_index is a valid integer
            if not isinstance(output_index, int) or output_index < 0:
                raise ValueError(f"[UTXOStorage._get_utxo_key] ERROR: output_index must be a non-negative integer.")

            # ✅ Format key: Prefix + Transaction ID (48B) + Output Index (4B)
            utxo_key = b"utxo:" + tx_id + struct.pack(">I", output_index)

            print(f"[UTXOStorage._get_utxo_key] INFO: Generated UTXO key for tx_id {tx_id.hex()} at index {output_index}.")
            return utxo_key

        except Exception as e:
            print(f"[UTXOStorage._get_utxo_key] ERROR: Failed to generate UTXO key: {e}")
            raise


    def _serialize_utxo(tx_id: bytes, output_index: int, amount: int, script_pub_key: bytes, is_locked: bool, block_height: int, spent_status: bool) -> bytes:
        """
        Serializes a UTXO into binary format for storage in LMDB.

        Fields:
            - tx_id (48B)            → SHA3-384 transaction hash
            - output_index (4B)       → 4-byte unsigned integer
            - amount (8B)             → 8-byte unsigned integer (smallest unit)
            - script_pub_key_length (2B) → Length of the scriptPubKey (max 512B)
            - script_pub_key (Variable)  → Locking script
            - is_locked (1B)          → 1-byte flag (0 = Unlocked, 1 = Locked)
            - block_height (4B)       → 4-byte unsigned integer (block number)
            - spent_status (1B)       → 1-byte flag (0 = Unspent, 1 = Spent)

        Returns:
            - Binary serialized UTXO (bytes)
        """
        try:
            # ✅ Ensure transaction ID is exactly 48 bytes
            if not isinstance(tx_id, bytes) or len(tx_id) != 48:
                raise ValueError(f"[UTXOStorage._serialize_utxo] ERROR: Invalid tx_id length. Expected 48 bytes, got {len(tx_id)}.")

            # ✅ Ensure scriptPubKey is within the allowed length
            script_length = len(script_pub_key)
            if script_length > 512:
                raise ValueError(f"[UTXOStorage._serialize_utxo] ERROR: script_pub_key too long. Max 512B, got {script_length}B.")

            # ✅ Pack data into binary format
            utxo_data = (
                tx_id +  # 48 bytes
                struct.pack(">I", output_index) +  # 4 bytes
                struct.pack(">Q", amount) +  # 8 bytes
                struct.pack(">H", script_length) +  # 2 bytes (script length)
                script_pub_key +  # Variable length (max 512B)
                struct.pack(">B", int(is_locked)) +  # 1 byte (locked flag)
                struct.pack(">I", block_height) +  # 4 bytes (block height)
                struct.pack(">B", int(spent_status))  # 1 byte (spent flag)
            )

            print(f"[UTXOStorage._serialize_utxo] INFO: Serialized UTXO {tx_id.hex()} at index {output_index} into {len(utxo_data)} bytes.")
            return utxo_data

        except Exception as e:
            print(f"[UTXOStorage._serialize_utxo] ERROR: Failed to serialize UTXO: {e}")
            raise


    def _deserialize_utxo(utxo_data: bytes) -> dict:
        """
        Deserializes binary UTXO data back into a dictionary format.

        Returns:
            - Dictionary with UTXO fields
        """
        try:
            # ✅ Minimum expected length: 48B (tx_id) + 4B (output_index) + 8B (amount) + 2B (script_len) + 1B (locked) + 4B (block_height) + 1B (spent) = 68B
            if len(utxo_data) < 68:
                raise ValueError(f"[UTXOStorage._deserialize_utxo] ERROR: UTXO data too short. Expected at least 68B, got {len(utxo_data)}B.")

            # ✅ Extract fixed-length fields
            offset = 0
            tx_id = utxo_data[offset:offset+48]
            offset += 48
            output_index = struct.unpack(">I", utxo_data[offset:offset+4])[0]
            offset += 4
            amount = struct.unpack(">Q", utxo_data[offset:offset+8])[0]
            offset += 8
            script_length = struct.unpack(">H", utxo_data[offset:offset+2])[0]
            offset += 2

            # ✅ Extract scriptPubKey (Variable-length)
            script_pub_key = utxo_data[offset:offset+script_length]
            offset += script_length

            # ✅ Extract remaining fields
            is_locked = bool(struct.unpack(">B", utxo_data[offset:offset+1])[0])
            offset += 1
            block_height = struct.unpack(">I", utxo_data[offset:offset+4])[0]
            offset += 4
            spent_status = bool(struct.unpack(">B", utxo_data[offset:offset+1])[0])

            # ✅ Construct UTXO dictionary
            utxo_dict = {
                "tx_id": tx_id,
                "output_index": output_index,
                "amount": amount,
                "script_pub_key": script_pub_key,
                "is_locked": is_locked,
                "block_height": block_height,
                "spent_status": spent_status
            }

            print(f"[UTXOStorage._deserialize_utxo] INFO: Deserialized UTXO {tx_id.hex()} at index {output_index}.")
            return utxo_dict

        except Exception as e:
            print(f"[UTXOStorage._deserialize_utxo] ERROR: Failed to deserialize UTXO: {e}")
            raise

    def store_utxo(self, tx_id: bytes, output_index: int, amount: Decimal, script_pub_key: bytes, is_locked: bool, block_height: int) -> bool:
        """
        Stores a UTXO in `utxo.lmdb` with proper validation and binary serialization.

        Args:
            tx_id (bytes): Transaction ID (48 bytes, SHA3-384 hash).
            output_index (int): The index of the output in the transaction.
            amount (Decimal): The amount in smallest units.
            script_pub_key (bytes): The locking script (max 512B).
            is_locked (bool): Whether the UTXO is locked.
            block_height (int): The block height in which the UTXO was created.

        Returns:
            bool: True if successfully stored, False otherwise.
        """
        try:
            # ✅ **Ensure Transaction ID is Exactly 48 Bytes**
            if not isinstance(tx_id, bytes) or len(tx_id) != 48:
                raise ValueError(f"[UTXOStorage.store_utxo] ERROR: Invalid tx_id length. Expected 48B, got {len(tx_id)}B.")

            # ✅ **Ensure ScriptPubKey is Within Allowed Length**
            script_length = len(script_pub_key)
            if script_length > 512:
                raise ValueError(f"[UTXOStorage.store_utxo] ERROR: script_pub_key too long. Max 512B, got {script_length}B.")

            # ✅ **Serialize UTXO in Binary Format**
            utxo_data = (
                tx_id +  # 48 bytes (Transaction ID)
                struct.pack(">I", output_index) +  # 4 bytes (Output Index)
                struct.pack(">Q", int(amount)) +  # 8 bytes (Amount in smallest unit)
                struct.pack(">H", script_length) +  # 2 bytes (Script Length)
                script_pub_key +  # Variable length (Locking Script)
                struct.pack(">B", int(is_locked)) +  # 1 byte (Locked Flag)
                struct.pack(">I", block_height) +  # 4 bytes (Block Height)
                struct.pack(">B", 0)  # 1 byte (Spent Status - 0 = Unspent)
            )

            # ✅ **Generate Binary UTXO Key**
            utxo_key = b"utxo:" + tx_id + struct.pack(">I", output_index)

            # ✅ **Store UTXO in LMDB**
            with self.utxo_db.env.begin(write=True) as txn:
                txn.put(utxo_key, utxo_data)

            print(f"[UTXOStorage.store_utxo] ✅ SUCCESS: Stored UTXO {tx_id.hex()} at index {output_index}, amount {amount}.")
            return True

        except Exception as e:
            print(f"[UTXOStorage.store_utxo] ❌ ERROR: Failed to store UTXO {tx_id.hex()} at index {output_index}: {e}")
            return False





    def get_utxo(self, tx_out_id: str) -> Optional[TransactionOut]:
        """
        Retrieve a UTXO from LMDB.
        Checks internal cache first, then queries the LMDB database.
        """
        try:
            if tx_out_id in self._cache:
                print(f"[UTXOStorage.get_utxo] INFO: Retrieved UTXO {tx_out_id} from cache.")
                return TransactionOut.from_dict(self._cache[tx_out_id])
            key = tx_out_id.encode("utf-8")
            data = self.utxo_db.get(key)
            if not data:
                print(f"[UTXOStorage.get_utxo] WARNING: UTXO {tx_out_id} not found.")
                return None
            utxo_entry = json.loads(data.decode("utf-8"))
            self._cache[tx_out_id] = utxo_entry
            print(f"[UTXOStorage.get_utxo] INFO: Retrieved UTXO {tx_out_id} from storage and cached it.")
            return TransactionOut.from_dict(utxo_entry)
        except Exception as e:
            print(f"[UTXOStorage.get_utxo] ERROR: UTXO retrieval failed for {tx_out_id}: {e}")
            return None

    def update_utxos(self, block) -> None:
        """
        Update UTXO databases (`utxo.lmdb` & `utxo_history.lmdb`) for the given block.

        Steps:
        1. Validate and remove spent UTXOs, archiving them in `utxo_history.lmdb`.
        2. Validate and add new UTXOs from block transactions.
        """
        try:
            print(f"[UTXOManager.update_utxos] INFO: Updating UTXOs for Block {block.index}...")

            with self._db_lock:
                with self.utxo_db.env.begin(write=True) as utxo_txn, \
                    self.utxo_history_db.env.begin(write=True) as history_txn:

                    # ✅ **Step 1: Remove Spent UTXOs**
                    for tx in block.transactions:
                        if hasattr(tx, "inputs"):
                            for tx_input in tx.inputs:
                                utxo_key = b"utxo:" + bytes.fromhex(tx_input.tx_id) + struct.pack(">I", tx_input.output_index)
                                spent_utxo = utxo_txn.get(utxo_key)

                                if spent_utxo:
                                    # ✅ **Move Spent UTXO to History**
                                    history_key = (b"spent_utxo:" + bytes.fromhex(tx_input.tx_id) +
                                                struct.pack(">I", tx_input.output_index) +
                                                struct.pack(">I", block.timestamp))
                                    history_txn.put(history_key, spent_utxo)

                                    # ✅ **Delete Spent UTXO**
                                    utxo_txn.delete(utxo_key)
                                    print(f"[UTXOManager.update_utxos] ✅ INFO: Spent UTXO {tx_input.tx_id}:{tx_input.output_index} archived.")

                                else:
                                    print(f"[UTXOManager.update_utxos] ⚠️ WARNING: Spent UTXO {tx_input.tx_id}:{tx_input.output_index} not found.")

                    # ✅ **Step 2: Add New UTXOs**
                    for tx in block.transactions:
                        for idx, output in enumerate(tx.outputs):
                            # ✅ **Validate Required Fields in UTXO**
                            if not all(hasattr(output, attr) for attr in ["amount", "script_pub_key", "locked"]):
                                print(f"[UTXOManager.update_utxos] ❌ ERROR: Invalid UTXO format in transaction {tx.tx_id}, skipping.")
                                continue

                            # ✅ **Convert Dictionary Outputs to `TransactionOut` Objects**
                            if isinstance(output, dict):
                                try:
                                    output = TransactionOut.from_dict(output)
                                except Exception as e:
                                    print(f"[UTXOManager.update_utxos] ❌ ERROR: Failed to convert output at index {idx}: {e}")
                                    continue

                            # ✅ **Serialize UTXO in Binary Format**
                            serialized_utxo = self._serialize_utxo(
                                tx_id=tx.tx_id,
                                output_index=idx,
                                amount=Decimal(output.amount),
                                script_pub_key=output.script_pub_key.encode('utf-8'),
                                is_locked=output.locked,
                                block_height=block.index,
                                spent_status=False
                            )
                            utxo_key = b"utxo:" + bytes.fromhex(tx.tx_id) + struct.pack(">I", idx)
                            utxo_txn.put(utxo_key, serialized_utxo)

                            # ✅ **Store New UTXO in `utxo_history.lmdb`**
                            history_key = (b"new_utxo:" + bytes.fromhex(tx.tx_id) +
                                        struct.pack(">I", idx) +
                                        struct.pack(">I", block.timestamp))
                            history_txn.put(history_key, serialized_utxo)

                            print(f"[UTXOManager.update_utxos] ✅ INFO: Added new UTXO {tx.tx_id}:{idx}, amount {output.amount}.")

            print(f"[UTXOManager.update_utxos] ✅ SUCCESS: UTXOs updated successfully for Block {block.index}.")

        except Exception as e:
            print(f"[UTXOManager.update_utxos] ❌ ERROR: Failed updating UTXOs: {e}")
            raise



    def export_utxos(self) -> None:
        """
        Export all unspent UTXOs to LMDB.
        Serializes each UTXO in binary and performs a bulk put operation.
        """
        try:
            all_utxos = self.utxo_manager.get_all_utxos()
            if not all_utxos:
                print("[UTXOStorage.export_utxos] WARNING: No UTXOs available for export.")
                return
            batch_data = {}
            with self.utxo_db.env.begin(write=True) as txn:
                for key, value in all_utxos.items():
                    try:
                        batch_data[f"utxo:{key}"] = pickle.dumps(value)
                    except pickle.PicklingError as e:
                        print(f"[UTXOStorage.export_utxos] ERROR: Failed to serialize UTXO {key}: {e}")
                        continue
                self.utxo_db.bulk_put(batch_data, txn)
            print(f"[UTXOStorage.export_utxos] SUCCESS: Exported {len(all_utxos)} UTXOs.")
        except Exception as e:
            print(f"[UTXOStorage.export_utxos] ERROR: Failed to export UTXOs: {e}")

    def validate_utxo(self, tx_id: bytes, output_index: int, amount: Decimal) -> bool:
        """
        Validate that a UTXO exists, is unlocked, and has sufficient balance.

        :param tx_id: Transaction ID (48 bytes, SHA3-384 hash).
        :param output_index: Output index (4 bytes, unsigned int).
        :param amount: Amount to validate (Decimal).
        :return: True if UTXO is valid, False otherwise.
        """
        try:
            # ✅ Ensure valid transaction ID length (48 bytes)
            if not isinstance(tx_id, bytes) or len(tx_id) != 48:
                raise ValueError(f"[UTXOStorage.validate_utxo] ERROR: Invalid tx_id length. Expected 48B, got {len(tx_id)}B.")

            # ✅ Generate Binary Key
            utxo_key = b"utxo:" + tx_id + struct.pack(">I", output_index)

            # ✅ Retrieve UTXO from LMDB
            with self.utxo_db.env.begin() as txn:
                utxo_data = txn.get(utxo_key)

            if not utxo_data:
                print(f"[UTXOStorage.validate_utxo] ERROR: UTXO {tx_id.hex()}:{output_index} does not exist.")
                return False

            # ✅ Deserialize Binary UTXO Data
            utxo = self._deserialize_utxo(utxo_data)

            # ✅ Check if UTXO is locked
            if utxo["is_locked"]:
                print(f"[UTXOStorage.validate_utxo] ERROR: UTXO {tx_id.hex()}:{output_index} is locked and cannot be spent.")
                return False

            # ✅ Validate sufficient balance
            utxo_amount = Decimal(str(utxo["amount"]))
            if utxo_amount < amount:
                print(f"[UTXOStorage.validate_utxo] ERROR: UTXO {tx_id.hex()}:{output_index} has insufficient balance. "
                    f"Required: {amount}, Available: {utxo_amount}")
                return False

            print(f"[UTXOStorage.validate_utxo] INFO: UTXO {tx_id.hex()}:{output_index} validated for spending. "
                f"Required {amount}, Available {utxo_amount}")
            return True

        except Exception as e:
            print(f"[UTXOStorage.validate_utxo] ERROR: Failed to validate UTXO {tx_id.hex()}:{output_index}: {e}")
            return False


    def _get_database(self, db_key: str) -> LMDBManager:
        """
        Retrieve the LMDB database instance for the given key using Constants.
        """
        try:
            db_path = Constants.DATABASES.get(db_key)
            if not db_path:
                raise ValueError(f"[UTXOStorage._get_database] ERROR: Unknown database key: {db_key}")
            return LMDBManager(db_path)
        except Exception as e:
            print(f"[UTXOStorage._get_database] ERROR: Failed to get database {db_key}: {e}")
            raise
