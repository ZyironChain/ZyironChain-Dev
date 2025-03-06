import os
import sys
import json
import pickle
import struct
import hashlib
import threading
from decimal import Decimal
from typing import Optional, Dict

# Adjust system path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.utils.deserializer import Deserializer

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
        Update UTXO databases (utxo.lmdb & utxo_history.lmdb) for the given block.

        Steps:
        1. Remove spent UTXOs.
        2. Add new UTXOs from block transactions.
        3. Record UTXO changes in the history database.
        """
        try:
            print(f"[UTXOStorage.update_utxos] INFO: Updating UTXOs for Block {block.index}...")

            with self._db_lock:
                with self.utxo_db.env.begin(write=True) as utxo_txn, \
                        self.utxo_history_db.env.begin(write=True) as history_txn:

                    # Step 1: Remove spent UTXOs
                    for tx in block.transactions:
                        if hasattr(tx, "inputs"):
                            for tx_input in tx.inputs:
                                spent_key = f"utxo:{tx_input.tx_out_id}".encode("utf-8")
                                spent_utxo = utxo_txn.get(spent_key)
                                if spent_utxo:
                                    history_key = f"spent_utxo:{tx_input.tx_out_id}:{block.timestamp}".encode("utf-8")
                                    history_txn.put(history_key, spent_utxo)
                                    utxo_txn.delete(spent_key)
                                    print(f"[UTXOStorage.update_utxos] INFO: Removed spent UTXO {tx_input.tx_out_id}.")
                                else:
                                    print(f"[UTXOStorage.update_utxos] WARNING: Spent UTXO {tx_input.tx_out_id} not found.")

                    # Step 2: Add new UTXOs from transactions explicitly
                    for tx in block.transactions:
                        for idx, output in enumerate(tx.outputs):
                            utxo_id = f"{tx.tx_id}:{idx}"

                            # Explicitly handle dict vs object outputs
                            if isinstance(output, dict):
                                amount = float(output.get("amount", 0))
                                script_pub_key = output.get("script_pub_key", "")
                                locked = output.get("locked", False)
                            else:
                                amount = float(getattr(output, "amount", 0))
                                script_pub_key = getattr(output, "script_pub_key", "")
                                locked = getattr(output, "locked", False)

                            utxo_data = {
                                "tx_out_id": utxo_id,
                                "amount": amount,
                                "script_pub_key": script_pub_key,
                                "locked": locked,
                                "block_index": block.index
                            }

                            serialized_utxo = json.dumps(utxo_data).encode("utf-8")
                            utxo_key = f"utxo:{utxo_id}".encode("utf-8")

                            utxo_txn.put(utxo_key, serialized_utxo)

                            history_key = f"new_utxo:{utxo_id}:{block.timestamp}".encode("utf-8")
                            history_txn.put(history_key, serialized_utxo)

                            print(f"[UTXOStorage.update_utxos] INFO: Added new UTXO {utxo_id}, amount {amount}")

            print(f"[UTXOStorage.update_utxos] SUCCESS: UTXOs updated successfully for Block {block.index}.")

        except Exception as e:
            print(f"[UTXOStorage.update_utxos] ERROR: Failed updating UTXOs: {e}")
            raise



    def store_utxo(self, utxo_id: str, utxo_data: dict) -> bool:
        """
        Store an individual UTXO in LMDB.
        Converts values to appropriate types and preserves precision.
        """
        try:
            if not isinstance(utxo_data, dict):
                raise TypeError("[UTXOStorage.store_utxo] ERROR: UTXO data must be a dictionary.")

            required_keys = {"tx_out_id", "amount", "script_pub_key", "block_index"}
            missing = required_keys - utxo_data.keys()
            if missing:
                raise KeyError(f"[UTXOStorage.store_utxo] ERROR: Missing keys in UTXO data: {missing}")

            tx_out_id = str(utxo_data["tx_out_id"])
            amount = Decimal(str(utxo_data["amount"])).quantize(Decimal(Constants.COIN))
            script_pub_key = str(utxo_data["script_pub_key"])
            locked = bool(utxo_data.get("locked", False))
            block_index = int(utxo_data.get("block_index", 0))

            utxo_entry = {
                "tx_out_id": tx_out_id,
                "amount": str(amount),
                "script_pub_key": script_pub_key,
                "locked": locked,
                "block_index": block_index
            }
            key = tx_out_id.encode("utf-8")
            existing = self.utxo_db.get(key)
            if existing:
                print(f"[UTXOStorage.store_utxo] WARNING: UTXO {tx_out_id} exists. Replacing entry.")
            self.utxo_db.put(key, json.dumps(utxo_entry).encode("utf-8"), replace=True)
            print(f"[UTXOStorage.store_utxo] SUCCESS: Stored UTXO {utxo_id}.")
            return True
        except (KeyError, TypeError, ValueError, Decimal.InvalidOperation) as e:
            print(f"[UTXOStorage.store_utxo] ERROR: Failed to store UTXO {utxo_id}: {e}")
            return False




    def get_utxos(self, tx_out_id):
        """Retrieve UTXO data and deserialize if necessary."""
        data = self.utxo_db.get(tx_out_id.encode("utf-8"))
        return Deserializer().deserialize(data) if data else None



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

    def validate_utxo(self, tx_out_id: str, amount: Decimal) -> bool:
        """
        Validate that a UTXO exists, is unlocked, and has sufficient balance.
        """
        utxo = self.get_utxo(tx_out_id)
        if not utxo:
            print(f"[UTXOStorage.validate_utxo] ERROR: UTXO {tx_out_id} does not exist.")
            return False
        if utxo.locked:
            print(f"[UTXOStorage.validate_utxo] ERROR: UTXO {tx_out_id} is locked and cannot be spent.")
            return False
        utxo_amount = Decimal(str(utxo.amount))
        if utxo_amount < amount:
            print(f"[UTXOStorage.validate_utxo] ERROR: UTXO {tx_out_id} has insufficient balance. Required: {amount}, Available: {utxo.amount}")
            return False
        print(f"[UTXOStorage.validate_utxo] INFO: UTXO {tx_out_id} validated for spending: Required {amount}, Available {utxo.amount}")
        return True


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
