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

class TransactionOut:
    """Represents a transaction output (UTXO)"""

    def __init__(self, script_pub_key: str, amount: Decimal, locked: bool = False):
        if not isinstance(amount, (int, float, Decimal)):
            raise ValueError("[ERROR] Amount must be a valid number.")

        self.script_pub_key = script_pub_key  # ✅ Address receiving funds
        self.amount = Decimal(amount)  # ✅ Store as Decimal for precision
        self.locked = locked  # ✅ If funds are locked (e.g., HTLCs)
        self.tx_out_id = self._calculate_tx_out_id()  # ✅ Unique UTXO ID

    def _calculate_tx_out_id(self) -> str:
        """Generate SHA3-384 hash for UTXO identification"""
        data = f"{self.script_pub_key}{self.amount}{self.locked}".encode()
        return hashlib.sha3_384(data).hexdigest()

    def to_dict(self) -> Dict:
        """Serialize TransactionOut to a dictionary"""
        return {
            "script_pub_key": self.script_pub_key,
            "amount": str(self.amount),  # ✅ Store as string to avoid precision loss
            "locked": self.locked,
            "tx_out_id": self.tx_out_id
        }


    @classmethod
    def from_dict(cls, data):
        """Create a TransactionOut instance from a dictionary"""
        if isinstance(data, cls):
            return data  

        return cls(
            script_pub_key=data.get("script_pub_key", ""),
            amount=Decimal(str(data.get("amount", "0"))),  # ✅ Convert back from string
            locked=data.get("locked", False)
        )
