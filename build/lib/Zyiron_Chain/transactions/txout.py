import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)


import hashlib
import time
from typing import List, Dict

import json  

from decimal import Decimal




import leveldb
from BTrees.OOBTree import OOBTree # type: ignore
from decimal import Decimal
import hashlib


class TransactionOut:
    def __init__(self, script_pub_key: str, amount: float, locked=False, prefix=None):
        if amount < 0:
            raise ValueError("Amount cannot be negative.")
        if not isinstance(script_pub_key, str) or not script_pub_key:
            raise ValueError("script_pub_key must be a non-empty string.")

        self.script_pub_key = script_pub_key
        self.amount = Decimal(amount)
        self.locked = locked
        self.prefix = prefix  # Added prefix to track transaction types
        self.tx_out_id = self.calculate_tx_out_id()

    def calculate_tx_out_id(self) -> str:
        tx_out_data = f"{self.script_pub_key}{self.amount}{self.prefix}"
        return hashlib.sha3_384(tx_out_data.encode()).hexdigest()

    def to_dict(self):
        return {
            "script_pub_key": self.script_pub_key,
            "amount": float(self.amount),
            "tx_out_id": self.tx_out_id,
            "locked": self.locked,
            "prefix": self.prefix,
        }

    @staticmethod
    def from_dict(data):
        return TransactionOut(
            script_pub_key=data["script_pub_key"],
            amount=float(data["amount"]),
            locked=data.get("locked", False),
            prefix=data.get("prefix"),
        )


class UTXOManager:
    def __init__(self, db_path="utxo_db"):
        """
        Initialize the UTXO Manager with LevelDB.
        """
        try:
            self.db = leveldb.LevelDB(db_path, create_if_missing=True)
        except leveldb.LevelDBException:
            print(f"[INFO] Creating a new LevelDB database at {db_path}.")
            self.db = leveldb.LevelDB(db_path, create_if_missing=True)


    def import_utxos_from_leveldb(self):
        """
        Import all UTXOs from LevelDB.
        """
        try:
            for key, value in self.db.RangeIter(prefix=b"utxo:"):
                utxo_key = key.decode().split("utxo:")[1]
                utxo_value = json.loads(value.decode())
                self.add_utxo(utxo_key, utxo_value)
            print("[INFO] Imported UTXOs from LevelDB.")
        except Exception as e:
            print(f"[ERROR] Failed to import UTXOs from LevelDB: {e}")

    def is_utxo_valid(self, tx_id, index):
        """
        Verify if a UTXO exists and is unlocked in LevelDB.
        """
        utxo_key = f"{tx_id}:{index}".encode()
        try:
            utxo_data = self.db.Get(utxo_key)
            return not json.loads(utxo_data.decode()).get("locked", False)
        except KeyError:
            return False
        except Exception as e:
            print(f"[ERROR] Failed to validate UTXO {tx_id}:{index}: {e}")
            return False

    def add_utxo(self, tx_id, index, output: TransactionOut):
        """
        Add a UTXO to the manager, ensuring proper handling of transaction prefixes.
        """
        utxo_key = f"{tx_id}:{index}"
        try:
            if self.db.Get(utxo_key.encode()):
                print(f"[WARN] UTXO {utxo_key} already exists.")
                return
        except KeyError:
            pass

        # Validate transaction ID prefix before adding
        prefix = tx_id.split('-')[0] if '-' in tx_id else "Standard"
        if prefix not in ["S", "PID", "CID", "Standard"]:
            raise ValueError(f"[ERROR] Invalid transaction prefix: {prefix}")

        self.db.Put(utxo_key.encode(), json.dumps(output.to_dict()).encode())
        print(f"[INFO] Added UTXO: {utxo_key} with prefix: {prefix}")

    def consume_utxo(self, tx_id, index):
        """
        Mark a UTXO as consumed and validate prefix.
        """
        utxo_key = f"{tx_id}:{index}"
        try:
            self.db.Delete(utxo_key.encode())
            print(f"[INFO] Consumed UTXO: {utxo_key}")
        except KeyError:
            print(f"[ERROR] UTXO {utxo_key} does not exist.")

    def get_utxo(self, tx_id, index):
        """
        Fetch a UTXO by transaction ID and index, verifying prefix compatibility.
        """
        utxo_key = f"{tx_id}:{index}"
        try:
            utxo_data = self.db.Get(utxo_key.encode())
            return TransactionOut.from_dict(json.loads(utxo_data.decode()))
        except KeyError:
            print(f"[INFO] UTXO {utxo_key} not found.")
            return None

    def lock_utxo(self, utxo_id, transaction_id):
        """
        Lock a UTXO for a specific transaction, with prefix validation.
        """
        try:
            utxo_data = self.db.Get(utxo_id.encode())
            utxo = json.loads(utxo_data.decode())
            if utxo.get("locked", False):
                raise ValueError(f"UTXO {utxo_id} is already locked.")

            # Validate transaction prefix
            prefix = transaction_id.split('-')[0] if '-' in transaction_id else "Standard"
            if prefix not in ["S", "PID", "CID", "Standard"]:
                raise ValueError(f"[ERROR] Invalid transaction prefix: {prefix}")

            utxo["locked"] = True
            self.db.Put(utxo_id.encode(), json.dumps(utxo).encode())
            print(f"[INFO] Locked UTXO: {utxo_id} for transaction: {transaction_id}")
        except KeyError:
            print(f"[ERROR] UTXO {utxo_id} does not exist.")

    def unlock_utxo(self, utxo_id):
        """
        Unlock a previously locked UTXO.
        """
        try:
            utxo_data = self.db.Get(utxo_id.encode())
            utxo = json.loads(utxo_data.decode())
            utxo["locked"] = False
            self.db.Put(utxo_id.encode(), json.dumps(utxo).encode())
            print(f"[INFO] Unlocked UTXO: {utxo_id}")
        except KeyError:
            print(f"[ERROR] UTXO {utxo_id} does not exist.")

    def get_all_utxos(self):
        """
        Retrieve all UTXOs from LevelDB.
        """
        utxos = {}
        try:
            for key in self.db.RangeIter():
                if key.decode().startswith("utxo:"):
                    utxo_key = key.decode().split("utxo:")[1]
                    utxos[utxo_key] = json.loads(self.db.get(key).decode())
        except Exception as e:
            print(f"[ERROR] Failed to list UTXOs: {e}")
        return utxos


    def clear(self):
        """
        Clear all UTXO data from LevelDB.
        """
        try:
            keys_to_delete = [key for key in self.db.RangeIter() if key.decode().startswith("utxo:")]
            for key in keys_to_delete:
                self.db.Delete(key)
            print("[INFO] Cleared all UTXOs.")
        except Exception as e:
            print(f"[ERROR] Failed to clear UTXOs: {e}")

    def register_output(self, tx_id, index, output):
        """
        Store transaction output (UTXO) in LevelDB.
        """
        try:
            self.add_utxo(tx_id, index, output)
            print(f"[INFO] Registered output for transaction {tx_id}:{index}.")
        except Exception as e:
            print(f"[ERROR] Failed to register output: {e}")
