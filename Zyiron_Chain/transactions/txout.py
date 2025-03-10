import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import hashlib
import time
import json
from decimal import Decimal
from typing import Dict
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.utils.deserializer import Deserializer


import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import hashlib
import time
import json
from decimal import Decimal
from typing import Dict
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.utils.deserializer import Deserializer

class TransactionOut:
    """Represents a transaction output (UTXO)."""

    def __init__(self, script_pub_key: str, amount: Decimal, locked: bool = False):
        """
        Initialize a Transaction Output.

        :param script_pub_key: The address or script receiving funds.
        :param amount: The amount of currency being sent.
        :param locked: Whether the UTXO is locked (e.g., for HTLCs).
        """
        # ✅ **Validate amount using Constants.COIN to ensure minimum unit**
        try:
            self.amount = Decimal(str(amount))
            if self.amount < Constants.COIN:
                print(f"[TransactionOut WARN] Amount below minimum {Constants.COIN}. Adjusting to minimum.")
                self.amount = Constants.COIN
        except Exception as e:
            print(f"[TransactionOut ERROR] Invalid amount format: {e}")
            raise ValueError(f"Invalid amount format: {e}")

        # ✅ **Ensure `script_pub_key` is a valid non-empty string**
        if not isinstance(script_pub_key, str) or not script_pub_key.strip():
            print("[TransactionOut ERROR] script_pub_key must be a non-empty string.")
            raise ValueError("script_pub_key must be a non-empty string.")

        self.script_pub_key = script_pub_key.strip()
        self.locked = locked

        # ✅ **Generate unique UTXO ID using single SHA3-384 hashing**
        self.tx_out_id = self._calculate_tx_out_id()

        print(f"[TransactionOut INFO] Created UTXO: tx_out_id={self.tx_out_id} | Amount: {self.amount} | Locked: {self.locked}")

    def _calculate_tx_out_id(self) -> str:
        """
        Generate a unique UTXO ID using single SHA3-384 hashing.
        Combines script_pub_key, amount, and locked flag into a bytes object.
        """
        try:
            data = f"{self.script_pub_key}{self.amount}{self.locked}".encode('utf-8')
            tx_out_id = Hashing.hash(data)
            print(f"[TransactionOut INFO] Calculated tx_out_id: {tx_out_id}")
            return tx_out_id
        except Exception as e:
            print(f"[TransactionOut ERROR] Failed to generate tx_out_id: {e}")
            return Constants.ZERO_HASH

    def to_dict(self) -> Dict[str, str]:
        """
        Serialize TransactionOut to a dictionary.

        :return: Dictionary representation of the transaction output.
        """
        return {
            "script_pub_key": self.script_pub_key,
            "amount": str(self.amount),  # Preserve precision as string
            "locked": self.locked,
            "tx_out_id": self.tx_out_id
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TransactionOut":
        """
        Create a TransactionOut instance from a dictionary.

        :param data: Dictionary containing transaction output data.
        :return: A TransactionOut instance.
        """
        if not isinstance(data, dict):
            print("[TransactionOut ERROR] Input data must be a dictionary.")
            raise TypeError("Input data must be a dictionary.")

        # ✅ **Fix: Replace 'address' with 'script_pub_key' if present**
        if "address" in data:
            print("[TransactionOut FIX] Detected 'address'. Converting to 'script_pub_key'.")
            data["script_pub_key"] = data.pop("address")

        if "script_pub_key" not in data or "amount" not in data:
            print("[TransactionOut ERROR] Missing required fields: 'script_pub_key' or 'amount'.")
            raise KeyError("Missing required fields: 'script_pub_key' or 'amount'.")

        script_pub_key = data.get("script_pub_key", "").strip()

        # ✅ **Ensure `amount` is a valid Decimal**
        try:
            amount = Decimal(str(data.get("amount", "0")))
        except Exception as e:
            print(f"[TransactionOut ERROR] Invalid amount format: {e}")
            raise ValueError(f"Invalid amount format: {e}")

        # ✅ **Ensure `amount` is at least `Constants.COIN`**
        if amount < Constants.COIN:
            print(f"[TransactionOut WARN] Amount below minimum {Constants.COIN}. Adjusting to minimum.")
            amount = Constants.COIN

        locked = data.get("locked", False)
        print(f"[TransactionOut INFO] Parsed TransactionOut from dict with script_pub_key: {script_pub_key}")
        return cls(script_pub_key=script_pub_key, amount=amount, locked=locked)

    @classmethod
    def from_serialized(cls, data: Dict) -> "TransactionOut":
        """
        Deserialize a TransactionOut from serialized data.

        :param data: Serialized dictionary.
        :return: TransactionOut instance.
        """
        deserialized_data = Deserializer().deserialize(data)

        # ✅ **Fix: Replace 'address' with 'script_pub_key' if present**
        if "address" in deserialized_data:
            print("[TransactionOut FIX] Detected 'address'. Converting to 'script_pub_key'.")
            deserialized_data["script_pub_key"] = deserialized_data.pop("address")

        return cls(
            script_pub_key=deserialized_data["script_pub_key"],
            amount=Decimal(str(deserialized_data["amount"])),
            locked=deserialized_data.get("locked", False)
        )