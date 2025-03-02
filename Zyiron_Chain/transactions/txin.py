import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))








import logging
from typing import Dict

import logging
from typing import Dict
from decimal import Decimal
from hashlib import sha3_384
from Zyiron_Chain.blockchain.constants import Constants

import logging
from typing import Dict
from Zyiron_Chain.blockchain.constants import Constants

class TransactionIn:
    """
    Represents a transaction input, referencing a previous UTXO.
    """

    def __init__(self, tx_out_id: str, script_sig: str):
        """
        Initialize a Transaction Input.
        
        :param tx_out_id: The UTXO being referenced.
        :param script_sig: The unlocking script (signature).
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            raise ValueError("[ERROR] tx_out_id must be a non-empty string.")
        if not isinstance(script_sig, str) or not script_sig.strip():
            raise ValueError("[ERROR] script_sig must be a non-empty string.")

        # Enforce consistent transaction input format (fallback to ZERO_HASH if needed)
        self.tx_out_id = tx_out_id.strip() if tx_out_id.strip() else Constants.ZERO_HASH
        self.script_sig = script_sig.strip()

        logging.info(f"[TRANSACTION INPUT] ✅ Created TransactionIn: tx_out_id={self.tx_out_id}")

    def to_dict(self) -> Dict[str, str]:
        """
        Convert the Transaction Input to a dictionary format.
        
        :return: Dictionary representation of the transaction input.
        """
        return {
            "tx_out_id": self.tx_out_id,
            "script_sig": self.script_sig
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TransactionIn":
        """
        Create a TransactionIn instance from a dictionary.
        
        :param data: Dictionary containing transaction input data.
        :return: A TransactionIn instance.
        """
        if not isinstance(data, dict):
            raise TypeError("[ERROR] Input data must be a dictionary.")

        # Validate required fields
        required_fields = ["tx_out_id", "script_sig"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise KeyError(f"[ERROR] Missing required fields: {', '.join(missing_fields)}")

        tx_out_id = data.get("tx_out_id", "").strip()
        script_sig = data.get("script_sig", "").strip()

        if not tx_out_id:
            logging.warning("[WARNING] tx_out_id missing, using ZERO_HASH as fallback.")
            tx_out_id = Constants.ZERO_HASH
        if not script_sig:
            raise ValueError("[ERROR] script_sig must be a non-empty string.")

        logging.info(f"[TRANSACTION INPUT] ✅ Parsed TransactionIn from dict: tx_out_id={tx_out_id}")
        return cls(tx_out_id=tx_out_id, script_sig=script_sig)

    def validate(self) -> bool:
        """
        Validates the Transaction Input format and integrity.
        
        :return: True if the input is valid, False otherwise.
        """
        # Ensure tx_out_id is a valid string and not the ZERO_HASH (unless it's for a coinbase transaction)
        if not self.tx_out_id or not isinstance(self.tx_out_id, str) or \
           (self.tx_out_id == Constants.ZERO_HASH and self.script_sig != "COINBASE"):
            logging.error(f"[VALIDATION ERROR] ❌ Invalid tx_out_id: {self.tx_out_id}")
            return False

        # Ensure script_sig follows proper security constraints (e.g., valid SHA3-384 hash format)
        if not self.script_sig or not isinstance(self.script_sig, str):
            logging.error(f"[VALIDATION ERROR] ❌ Invalid script_sig: {self.script_sig}")
            return False

        # For our purposes, we assume a valid SHA3-384 hash is 96 lowercase hexadecimal characters
        if len(self.script_sig) != 96 or not all(c in "0123456789abcdef" for c in self.script_sig.lower()):
            logging.error(f"[VALIDATION ERROR] ❌ Invalid script_sig format: {self.script_sig}")
            return False

        logging.info(f"[TRANSACTION INPUT] ✅ Validation successful for tx_out_id={self.tx_out_id}")
        return True
