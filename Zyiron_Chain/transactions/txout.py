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
    """Represents a transaction output (UTXO)"""

    def __init__(self, script_pub_key: str, amount: Decimal, locked: bool = False):
        """
        Initialize a Transaction Output.
        
        :param script_pub_key: The address or script receiving funds.
        :param amount: The amount of currency being sent.
        :param locked: Whether the UTXO is locked (e.g., for HTLCs).
        """
        # Validate amount using Constants.COIN to ensure minimum unit and proper type
        if not isinstance(amount, (int, float, Decimal)) or Decimal(amount) < Constants.COIN:
            print(f"[TransactionOut ERROR] Amount must be a valid number and at least {Constants.COIN}. Provided: {amount}")
            raise ValueError(f"Amount must be a valid number and at least {Constants.COIN}.")
        
        # Validate that script_pub_key is a non-empty string
        if not isinstance(script_pub_key, str) or not script_pub_key.strip():
            print("[TransactionOut ERROR] script_pub_key must be a non-empty string.")
            raise ValueError("script_pub_key must be a non-empty string.")

        self.script_pub_key = script_pub_key.strip()
        self.amount = Decimal(amount)
        self.locked = locked

        # Calculate unique UTXO id using single SHA3-384 hashing
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
            print("[TransactionOut from_dict ERROR] Input data must be a dictionary.")
            raise TypeError("Input data must be a dictionary.")
        if "script_pub_key" not in data or "amount" not in data:
            print("[TransactionOut from_dict ERROR] Missing required fields: 'script_pub_key' or 'amount'.")
            raise KeyError("Missing required fields: 'script_pub_key' or 'amount'.")
        
        script_pub_key = data.get("script_pub_key", "").strip()
        try:
            amount = Decimal(str(data.get("amount", "0")))
        except Exception as e:
            print(f"[TransactionOut from_dict ERROR] Invalid amount format: {e}")
            raise ValueError(f"Invalid amount format: {e}")
        
        if not script_pub_key:
            print("[TransactionOut from_dict WARN] script_pub_key is missing. Defaulting to empty string.")
            script_pub_key = ""
        if amount < Constants.COIN:
            print(f"[TransactionOut from_dict WARN] Amount below minimum unit {Constants.COIN}. Adjusting to minimum.")
            amount = Constants.COIN
        
        locked = data.get("locked", False)
        print(f"[TransactionOut from_dict INFO] Parsed TransactionOut from dict with script_pub_key: {script_pub_key}")
        return cls(script_pub_key=script_pub_key, amount=amount, locked=locked)


    @classmethod
    def from_dict(cls, data: Dict) -> "TransactionOut":
        """Deserialize a TransactionOut from a dictionary."""
        deserialized_data = Deserializer().deserialize(data)
        return cls(
            script_pub_key=deserialized_data["script_pub_key"],
            amount=Decimal(str(deserialized_data["amount"])),
            locked=deserialized_data.get("locked", False)
        )