import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import hashlib
import time
from typing import List, Dict

import json  

from decimal import Decimal



import json
import logging
from Zyiron_Chain.transactions.transactiontype import TransactionType
from BTrees.OOBTree import OOBTree # type: ignore
from decimal import Decimal
import hashlib
logging.basicConfig(level=logging.INFO)

import hashlib
from decimal import Decimal
from typing import Dict
from Zyiron_Chain.blockchain.constants import Constants
class TransactionOut:
    """Represents a transaction output (UTXO)"""

    def __init__(self, script_pub_key: str, amount: Decimal, locked: bool = False):
        """
        Initialize a Transaction Output.

        :param script_pub_key: The address or script receiving funds.
        :param amount: The amount of currency being sent.
        :param locked: Whether the UTXO is locked (e.g., for HTLCs).
        """
        # ✅ Validate amount format and ensure it meets the minimum unit
        if not isinstance(amount, (int, float, Decimal)) or Decimal(amount) < Constants.COIN:
            raise ValueError(f"[ERROR] Amount must be a valid number and at least {Constants.COIN}.")

        # ✅ Ensure script_pub_key is a valid string
        if not isinstance(script_pub_key, str) or not script_pub_key.strip():
            raise ValueError("[ERROR] script_pub_key must be a non-empty string.")

        self.script_pub_key = script_pub_key.strip()  # ✅ Clean up input
        self.amount = Decimal(amount)  # ✅ Store as Decimal for precision
        self.locked = locked  # ✅ Mark if funds are locked (e.g., HTLCs)
        self.tx_out_id = self._calculate_tx_out_id()  # ✅ Unique UTXO ID

        logging.info(f"[TRANSACTION OUTPUT] ✅ Created UTXO: {self.tx_out_id} | Amount: {self.amount} | Locked: {self.locked}")

    def _calculate_tx_out_id(self) -> str:
        """Generate SHA3-384 hash for UTXO identification, ensuring a unique identifier."""
        try:
            data = f"{self.script_pub_key}{self.amount}{self.locked}".encode()
            return hashlib.sha3_384(data).hexdigest()
        except Exception as e:
            logging.error(f"[ERROR] Failed to generate tx_out_id: {e}")
            return Constants.ZERO_HASH  # ✅ Fallback to ZERO_HASH if generation fails

    def to_dict(self) -> Dict:
        """Serialize TransactionOut to a dictionary."""
        return {
            "script_pub_key": self.script_pub_key,
            "amount": str(self.amount),  # ✅ Store as string to avoid precision loss
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
            raise TypeError("[ERROR] Input data must be a dictionary.")

        # ✅ Ensure required fields exist
        if "script_pub_key" not in data or "amount" not in data:
            raise KeyError("[ERROR] Missing required fields: 'script_pub_key' or 'amount'.")

        script_pub_key = data.get("script_pub_key", "").strip()
        amount = Decimal(str(data.get("amount", "0")))

        # ✅ Ensure script_pub_key is valid
        if not script_pub_key:
            logging.warning("[WARNING] script_pub_key is missing. Defaulting to empty.")
            script_pub_key = ""

        # ✅ Validate amount before instantiating the object
        if amount < Constants.COIN:
            logging.warning(f"[WARNING] Amount below minimum unit {Constants.COIN}. Adjusting to minimum.")
            amount = Constants.COIN

        return cls(
            script_pub_key=script_pub_key,
            amount=amount,
            locked=data.get("locked", False)
        )