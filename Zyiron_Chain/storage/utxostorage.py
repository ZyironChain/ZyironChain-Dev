import os
import sys
import json
import pickle
import struct
import hashlib
import threading
from decimal import Decimal
from typing import Optional, Dict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.database.lmdatabase import LMDBManager
from Zyiron_Chain.transactions.txout import TransactionOut

class UTXOStorage:
    """
    UTXOStorage manages unspent transaction outputs (UTXOs) and UTXO history in LMDB.
    
    Responsibilities:
      - Update UTXO databases for new blocks.
      - Store individual UTXOs with proper type conversion and standardized precision.
      - Retrieve UTXOs from storage with caching.
      - Export all UTXOs for indexing.
      
    All operations use data in bytes, reference Constants for configuration, and use single SHA3‑384 hashing where needed.
    Detailed print statements are provided for each operation and error condition.
    """
    
    def __init__(self, utxo_db: LMDBManager, utxo_history_db: LMDBManager, utxo_manager):
        try:
            self.utxo_db = utxo_db
            self.utxo_history_db = utxo_history_db
            self.utxo_manager = utxo_manager  # Provides get_all_utxos()
            self._cache: Dict[str, dict] = {}
            self._db_lock = threading.Lock()
            print("[UTXOStorage.__init__] SUCCESS: UTXOStorage initialized successfully.")
        except Exception as e:
            print(f"[UTXOStorage.__init__] ERROR: Failed to initialize UTXOStorage: {e}")
            raise

    def update_utxos(self, block) -> None:
        """
        Update UTXO databases for a new block.
        For each transaction in the block:
          - Remove spent UTXOs.
          - Add new UTXOs.
        """
        try:
            with self._db_lock:
                with self.utxo_db.env.begin(write=True) as utxo_txn, \
                     self.utxo_history_db.env.begin(write=True) as history_txn:
                    for tx in block.transactions:
                        if not hasattr(tx, "inputs") or not hasattr(tx, "outputs"):
                            print(f"[UTXOStorage.update_utxos] ERROR: Transaction {tx.tx_id} is malformed. Skipping update.")
                            continue

                        for inp in tx.inputs:
                            key = f"utxo:{inp.tx_out_id}".encode("utf-8")
                            if utxo_txn.get(key):
                                utxo_txn.delete(key)
                                print(f"[UTXOStorage.update_utxos] INFO: Removed spent UTXO {inp.tx_out_id}.")
                            else:
                                print(f"[UTXOStorage.update_utxos] WARNING: Tried to remove non-existent UTXO {inp.tx_out_id}.")

                        for idx, output in enumerate(tx.outputs):
                            utxo_id = f"{tx.tx_id}:{idx}"
                            utxo_entry = {
                                "tx_out_id": utxo_id,
                                "amount": float(output.amount),
                                "script_pub_key": output.script_pub_key,
                                "block_index": block.index
                            }
                            key = f"utxo:{utxo_id}".encode("utf-8")
                            utxo_txn.put(key, pickle.dumps(utxo_entry))
                            history_key = f"history:{utxo_id}:{block.timestamp}".encode("utf-8")
                            history_txn.put(history_key, pickle.dumps(utxo_entry))
                            print(f"[UTXOStorage.update_utxos] INFO: Added new UTXO {utxo_id} with amount {output.amount}.")
            print(f"[UTXOStorage.update_utxos] SUCCESS: UTXOs updated for Block {block.index}.")
        except Exception as e:
            print(f"[UTXOStorage.update_utxos] ERROR: Failed to update UTXOs for Block {block.index}: {e}")
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
            utxo_db = self._get_database("utxo")
            key = tx_out_id.encode("utf-8")
            if utxo_db.get(key):
                print(f"[UTXOStorage.store_utxo] WARNING: UTXO {tx_out_id} exists. Replacing entry.")
            utxo_db.put(key, json.dumps(utxo_entry).encode("utf-8"), replace=True)
            print(f"[UTXOStorage.store_utxo] SUCCESS: Stored UTXO {utxo_id}.")
            return True
        except (KeyError, TypeError, ValueError, Decimal.InvalidOperation) as e:
            print(f"[UTXOStorage.store_utxo] ERROR: Failed to store UTXO {utxo_id}: {e}")
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
            utxo_db = self._get_database("utxo")
            data = utxo_db.get(tx_out_id.encode("utf-8"))
            if not data:
                print(f"[UTXOStorage.get_utxo] WARNING: UTXO {tx_out_id} not found.")
                return None
            utxo_entry = json.loads(data.decode("utf-8"))
            self._cache[tx_out_id] = utxo_entry
            print(f"[UTXOStorage.get_utxo] INFO: Retrieved UTXO {tx_out_id} from LMDB.")
            return TransactionOut.from_dict(utxo_entry)
        except Exception as e:
            print(f"[UTXOStorage.get_utxo] ERROR: UTXO retrieval failed for {tx_out_id}: {e}")
            return None

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
