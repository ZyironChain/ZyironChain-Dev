import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from typing import Dict
from decimal import Decimal
from hashlib import sha3_384
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.deserializer import Deserializer

from typing import Dict
class TransactionIn:
    """
    Represents a transaction input, referencing a previous UTXO.
    """

    def __init__(self, tx_out_id: str, script_sig: str):
        """
        Initialize a Transaction Input.

        :param tx_out_id: The UTXO being referenced.
        :param script_sig: The unlocking script (signature) or placeholder.
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print("[TransactionIn ERROR] ❌ tx_out_id must be a non-empty string.")
            raise ValueError("tx_out_id must be a non-empty string.")

        if not isinstance(script_sig, str):
            print("[TransactionIn ERROR] ❌ script_sig must be a string.")
            raise ValueError("script_sig must be a string.")

        script_sig = script_sig.strip()

        # ✅ Allow "SIGN_PENDING" as a temporary placeholder (will be replaced later)
        if not script_sig:
            print("[TransactionIn ERROR] ❌ script_sig must be a non-empty string.")
            raise ValueError("script_sig must be a non-empty string.")

        self.tx_out_id = tx_out_id.strip()
        self.script_sig = script_sig

        print(f"[TransactionIn INFO] ✅ Created TransactionIn: tx_out_id={self.tx_out_id}")

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
        try:
            if not isinstance(data, dict):
                print("[TransactionIn.from_dict] ❌ Input data must be a dictionary.")
                raise TypeError("Input data must be a dictionary.")

            required_fields = ["tx_out_id", "script_sig"]
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                print(f"[TransactionIn.from_dict] ❌ Missing required fields: {', '.join(missing_fields)}")
                raise KeyError(f"Missing required fields: {', '.join(missing_fields)}")

            tx_out_id = str(data.get("tx_out_id", "")).strip()
            script_sig = str(data.get("script_sig", "")).strip()

            # ⚠️ Fallback to ZERO_HASH if tx_out_id is missing
            if not tx_out_id:
                print("[TransactionIn.from_dict] ⚠️ tx_out_id is empty. Using Constants.ZERO_HASH.")
                tx_out_id = Constants.ZERO_HASH

            if not script_sig:
                print("[TransactionIn.from_dict] ❌ script_sig cannot be empty.")
                raise ValueError("script_sig must be a non-empty string.")

            print(f"[TransactionIn.from_dict] ✅ Parsed TransactionIn: tx_out_id={tx_out_id}")
            return cls(tx_out_id=tx_out_id, script_sig=script_sig)

        except Exception as e:
            print(f"[TransactionIn.from_dict] ❌ Failed to create TransactionIn: {e}")
            raise

    def validate(self) -> bool:
        """
        Validates the Transaction Input format and integrity.

        :return: True if the input is valid, False otherwise.
        """
        try:
            # ✅ Ensure tx_out_id is a valid string
            if not self.tx_out_id or not isinstance(self.tx_out_id, str):
                print(f"[TransactionIn VALIDATION ERROR] ❌ Invalid tx_out_id: {self.tx_out_id}")
                return False

            # ✅ Ensure script_sig is a valid non-empty string
            if not self.script_sig or not isinstance(self.script_sig, str):
                print(f"[TransactionIn VALIDATION ERROR] ❌ Invalid script_sig: {self.script_sig}")
                return False

            # ✅ Special case: Coinbase transactions allow ZERO_HASH
            if self.tx_out_id == Constants.ZERO_HASH and self.script_sig == "COINBASE":
                print("[TransactionIn VALIDATION INFO] ✅ Coinbase transaction detected. Validation passed.")
                return True

            # ✅ Validate script_sig format (must be **96-character SHA3-384 hex string**)
            if len(self.script_sig) != 96 or not all(c in "0123456789abcdef" for c in self.script_sig.lower()):
                print(f"[TransactionIn VALIDATION ERROR] ❌ Invalid script_sig format: {self.script_sig}")
                return False

            print(f"[TransactionIn VALIDATION INFO] ✅ Validation successful for tx_out_id={self.tx_out_id}")
            return True

        except Exception as e:
            print(f"[TransactionIn VALIDATION ERROR] ❌ Unexpected validation failure: {e}")
            return False
