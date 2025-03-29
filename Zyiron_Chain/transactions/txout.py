import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import hashlib
import time
import json
from decimal import Decimal, InvalidOperation
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

from typing import Dict
from decimal import Decimal

class TransactionOut:
    """Represents a transaction output (UTXO)."""

    def __init__(self, script_pub_key: str, amount: Decimal, locked: bool = False, tx_out_id: str = None):
        """
        Initialize a Transaction Output.

        :param script_pub_key: The address or script receiving funds.
        :param amount: The amount of currency being sent.
        :param locked: Whether the UTXO is locked (e.g., for HTLCs).
        :param tx_out_id: Optional precomputed UTXO ID (used during deserialization).
        """
        try:
            self.amount = Decimal(str(amount))
            if self.amount < Constants.COIN:
                print(f"[TransactionOut WARN] ⚠️ Amount below minimum {Constants.COIN}. Adjusting to minimum.")
                self.amount = Constants.COIN
        except Exception as e:
            print(f"[TransactionOut ERROR] ❌ Invalid amount format: {e}")
            raise ValueError(f"Invalid amount format: {e}")

        if not isinstance(script_pub_key, str) or not script_pub_key.strip():
            print("[TransactionOut ERROR] ❌ script_pub_key must be a non-empty string.")
            raise ValueError("script_pub_key must be a non-empty string.")

        self.script_pub_key = script_pub_key.strip()
        self.locked = locked

        if tx_out_id:
            self.tx_out_id = tx_out_id
            print(f"[TransactionOut INFO] ✅ Loaded UTXO from existing ID: {self.tx_out_id}")
        else:
            self.tx_out_id = self._calculate_tx_out_id()
            print(f"[TransactionOut INFO] ✅ Created UTXO: tx_out_id={self.tx_out_id} | Amount: {self.amount} | Locked: {self.locked}")

    def _calculate_tx_out_id(self) -> str:
        """
        Generate a unique UTXO ID using single SHA3-384 hashing.
        Combines script_pub_key, amount, locked flag, and a nanosecond timestamp.
        """
        try:
            salt = str(time.time_ns())  # ✅ Add high-resolution salt for uniqueness
            data = f"{self.script_pub_key}{self.amount}{self.locked}{salt}".encode("utf-8")
            tx_out_id_bytes = Hashing.hash(data)
            tx_out_id = tx_out_id_bytes.hex()  # ✅ Return hex string for LMDB/storage
            print(f"[TransactionOut INFO] ✅ Calculated tx_out_id with salt: {tx_out_id}")
            return tx_out_id
        except Exception as e:
            print(f"[TransactionOut ERROR] ❌ Failed to generate tx_out_id: {e}")
            return Constants.ZERO_HASH  # Return fallback on failure


    def to_dict(self) -> Dict[str, str]:
        """
        Serialize TransactionOut to a dictionary.

        :return: Dictionary representation of the transaction output.
        """
        result = {
            "script_pub_key": self.script_pub_key,
            "amount": str(self.amount),  # ✅ Preserve precision as string
            "locked": self.locked,
            "tx_out_id": self.tx_out_id  # ✅ Ensure UTXO ID is included
        }

        # ✅ Fallback: include tx_out_index if available
        if hasattr(self, "tx_out_index"):
            result["tx_out_index"] = self.tx_out_index

        return result


    @classmethod
    def from_dict(cls, data: Dict) -> "TransactionOut":
        """
        Create a TransactionOut instance from a dictionary with robust error handling
        and backward compatibility support.
        
        Args:
            data: Dictionary containing transaction output data. Supports both new and legacy formats.
            
        Returns:
            TransactionOut: A properly initialized TransactionOut instance.
            
        Raises:
            TypeError: If input is not a dictionary
            ValueError: If required fields are missing or invalid
        """
        # Input validation
        if not isinstance(data, dict):
            error_msg = f"Expected dictionary, got {type(data).__name__}"
            print(f"[TransactionOut.from_dict] ❌ {error_msg}")
            raise TypeError(error_msg)

        try:
            # Field normalization and backward compatibility
            normalized_data = cls._normalize_input_data(data)
            
            # Validate required fields
            cls._validate_required_fields(normalized_data)
            
            # Parse and validate amount
            amount = cls._parse_and_validate_amount(normalized_data['amount'])
            
            # Create instance with core fields
            obj = cls(
                script_pub_key=normalized_data['script_pub_key'],
                amount=amount,
                locked=normalized_data.get('locked', False)
            )
            
            # Set optional fields if present
            cls._set_optional_fields(obj, normalized_data)
            
            print(f"[TransactionOut.from_dict] ✅ Created TransactionOut: "
                f"script={normalized_data['script_pub_key'][:20]}..., "
                f"amount={amount}, locked={obj.locked}")
            return obj
            
        except Exception as e:
            print(f"[TransactionOut.from_dict] ❌ Failed to create TransactionOut: {e}")
            print(f"[TransactionOut.from_dict] 📌 Problematic data: {data}")
            raise

    @classmethod
    def _normalize_input_data(cls, data: Dict) -> Dict:
        """Normalize input data and handle backward compatibility."""
        normalized = data.copy()
        
        # Handle legacy field names
        if 'address' in normalized and 'script_pub_key' not in normalized:
            print("[TransactionOut] 🔄 Converting legacy 'address' to 'script_pub_key'")
            normalized['script_pub_key'] = normalized.pop('address')
            
        # Handle both 'locked' and 'is_locked' for backward compatibility
        if 'is_locked' in normalized and 'locked' not in normalized:
            normalized['locked'] = normalized['is_locked']
            
        return normalized

    @classmethod
    def _validate_required_fields(cls, data: Dict):
        """Validate that required fields exist and are valid."""
        required_fields = {
            'script_pub_key': (str, "Non-empty string"),
            'amount': (object, "Numeric or string representation of number")
        }
        
        missing = []
        invalid = []
        
        for field, (type_hint, description) in required_fields.items():
            if field not in data:
                missing.append(field)
                continue
                
            if type_hint is str and not isinstance(data[field], str):
                invalid.append(f"{field} (expected {description})")
            elif type_hint is object and data[field] is None:
                invalid.append(f"{field} (cannot be None)")
                
        if missing or invalid:
            error_msg = []
            if missing:
                error_msg.append(f"Missing fields: {', '.join(missing)}")
            if invalid:
                error_msg.append(f"Invalid fields: {', '.join(invalid)}")
            full_msg = ". ".join(error_msg)
            print(f"[TransactionOut] ❌ Validation failed: {full_msg}")
            raise ValueError(full_msg)

    @classmethod
    def _parse_and_validate_amount(cls, amount) -> Decimal:
        """Parse and validate amount field."""
        try:
            amount_decimal = Decimal(str(amount))
            if amount_decimal < Constants.COIN:
                print(f"[TransactionOut] ⚠️ Amount {amount_decimal} below minimum {Constants.COIN}. Adjusting.")
                amount_decimal = Constants.COIN
            return amount_decimal
        except (ValueError, TypeError, InvalidOperation) as e:
            print(f"[TransactionOut] ❌ Invalid amount '{amount}': {e}")
            raise ValueError(f"Invalid amount format: {amount}") from e

    @classmethod
    def _set_optional_fields(cls, obj: "TransactionOut", data: Dict):
        """Set optional fields if they exist in the input data."""
        if 'tx_out_id' in data and data['tx_out_id'] is not None:
            obj.tx_out_id = str(data['tx_out_id'])
            
        if 'tx_out_index' in data and data['tx_out_index'] is not None:
            try:
                obj.tx_out_index = int(data['tx_out_index'])
            except (ValueError, TypeError) as e:
                print(f"[TransactionOut] ⚠️ Invalid tx_out_index: {e}. Skipping.")

    @classmethod
    def from_serialized(cls, data: Dict) -> "TransactionOut":
        """
        Deserialize a TransactionOut from serialized data.

        :param data: Serialized dictionary.
        :return: TransactionOut instance.
        """
        try:
            deserialized_data = Deserializer().deserialize(data)

            # ✅ Fix: Replace 'address' with 'script_pub_key' if present
            if "address" in deserialized_data:
                print("[TransactionOut FIX] 🔄 Detected 'address'. Converting to 'script_pub_key'.")
                deserialized_data["script_pub_key"] = deserialized_data.pop("address")

            return cls(
                script_pub_key=deserialized_data["script_pub_key"],
                amount=Decimal(str(deserialized_data["amount"])),
                locked=deserialized_data.get("locked", False)
            )
        except Exception as e:
            print(f"[TransactionOut ERROR] ❌ Failed to deserialize TransactionOut: {e}")
            raise ValueError("Deserialization failed.")
