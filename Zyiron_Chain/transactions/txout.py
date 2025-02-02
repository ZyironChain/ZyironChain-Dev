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

class TransactionOut:
    """Represents a transaction output (UTXO)"""
    def __init__(self, script_pub_key: str, amount: float, locked: bool = False):
        self.script_pub_key = script_pub_key
        self.amount = amount
        self.locked = locked
        self.tx_out_id = self._calculate_tx_out_id()

    def _calculate_tx_out_id(self) -> str:
        """Generate SHA3-384 hash for UTXO identification"""
        data = f"{self.script_pub_key}{self.amount}{self.locked}".encode()
        return hashlib.sha3_384(data).hexdigest()

    def to_dict(self) -> Dict:
        return {
            "script_pub_key": self.script_pub_key,
            "amount": self.amount,
            "locked": self.locked,
            "tx_out_id": self.tx_out_id
        }

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(
            script_pub_key=data["script_pub_key"],
            amount=data["amount"],
            locked=data.get("locked", False)
        )
