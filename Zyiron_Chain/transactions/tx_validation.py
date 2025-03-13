import sys
import os
import time
import hashlib
import json
from decimal import Decimal
from typing import Any, List

# Adjust Python path if needed
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

# Import your project constants and modules
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.coinbase import CoinbaseTx
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.utils.hashing import Hashing

import hashlib
import json
import time
from decimal import Decimal
from typing import Any



import hashlib
import json
from decimal import Decimal
from typing import Any

class TXValidation:
    """
    A dedicated class for validating transactions according to protocol rules.
    - Uses single SHA3-384 hashing (via hashlib or Hashing.hash).
    - Relies on block_manager and block_metadata for chain info (e.g., total mined supply).
    - Prints detailed messages for debugging rather than using logging.
    """

    def __init__(self, block_manager: Any, block_metadata: Any, fee_model: FeeModel):
        """
        Initialize TXValidation with references to:
          - block_manager: Provides chain and block-level data (e.g., chain length).
          - block_metadata: Provides additional metadata (e.g., total mined supply).
          - fee_model: FeeModel instance for transaction fee calculations.
        """
        self.block_manager = block_manager
        self.block_metadata = block_metadata
        self.fee_model = fee_model
        print("[TXVALIDATION] Initialized TXValidation instance with block_manager, block_metadata, and fee_model.")

    def _validate_coinbase(self, tx: Any) -> bool:
        """
        Validate a coinbase transaction:
         - Must have no inputs, exactly one output, type == 'COINBASE', fee == 0.
         - Transaction ID is verified with single SHA3-384 hashing.
        :param tx: Transaction object (CoinbaseTx).
        :return: True if valid coinbase transaction, False otherwise.
        """
        print(f"[TXVALIDATION] Validating potential Coinbase transaction with tx_id: {getattr(tx, 'tx_id', 'UNKNOWN')}")

        if not hasattr(tx, "tx_id") or not isinstance(tx.tx_id, str):
            print("[TXVALIDATION ERROR] Coinbase transaction missing or invalid 'tx_id'.")
            return False

        # ✅ Ensure tx_id is properly formatted
        try:
            single_hashed_tx_id = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()
            print(f"[TXVALIDATION] Single hashed coinbase tx_id: {single_hashed_tx_id[:24]}...")
        except Exception as e:
            print(f"[TXVALIDATION ERROR] Failed to hash coinbase tx_id: {e}")
            return False

        # ✅ Ensure transaction follows Coinbase structure
        if not isinstance(tx, CoinbaseTx) or not hasattr(tx, "inputs") or not hasattr(tx, "outputs"):
            print("[TXVALIDATION ERROR] Coinbase transaction structure is invalid.")
            return False

        if len(tx.inputs) > 0 or len(tx.outputs) != 1 or tx.type.upper() != "COINBASE" or Decimal(tx.fee) != Decimal("0"):
            print("[TXVALIDATION ERROR] Coinbase transaction does not meet required structure.")
            return False

        print(f"[TXVALIDATION] Coinbase transaction {tx.tx_id} validated successfully.")
        return True

    def validate_transaction_fee(self, transaction: Any) -> bool:
        """
        Validate a transaction's fee using FeeModel:
         - Calculates transaction size (via a local or external method).
         - Asks fee_model for required fee.
         - Compares required fee with actual (inputs - outputs).
        :param transaction: The transaction object to check.
        :return: True if fee is sufficient, False otherwise.
        """
        try:
            tx_id = getattr(transaction, "tx_id", "UNKNOWN")
            print(f"[TXVALIDATION] Validating fee for transaction {tx_id}.")

            # ✅ Ensure transaction object has required attributes
            if not hasattr(transaction, "inputs") or not hasattr(transaction, "outputs") or not hasattr(transaction, "type"):
                print("[TXVALIDATION ERROR] Transaction structure is invalid.")
                return False

            # ✅ Compute transaction size safely
            tx_size = self._calculate_transaction_size(transaction)
            if tx_size < 0:
                print("[TXVALIDATION ERROR] Failed to compute transaction size. Fee validation aborted.")
                return False
            print(f"[TXVALIDATION] Computed transaction size: {tx_size} bytes.")

            # ✅ Ensure inputs and outputs contain valid amounts
            try:
                input_sum = sum(Decimal(inp.amount) for inp in transaction.inputs if hasattr(inp, "amount"))
                output_sum = sum(Decimal(out.amount) for out in transaction.outputs if hasattr(out, "amount"))
                actual_fee = input_sum - output_sum
                print(f"[TXVALIDATION] Actual fee from I/O: {actual_fee}")
            except Exception as e:
                print(f"[TXVALIDATION ERROR] Failed to compute transaction amounts: {e}")
                return False

            # ✅ Compute required fee from FeeModel
            try:
                required_fee = self.fee_model.calculate_fee(
                    block_size=Constants.MAX_BLOCK_SIZE_BYTES,
                    payment_type=transaction.type,
                    amount=input_sum,
                    tx_size=tx_size
                )
                print(f"[TXVALIDATION] Required fee from FeeModel: {required_fee}")
            except Exception as e:
                print(f"[TXVALIDATION ERROR] Failed to compute required fee: {e}")
                return False

            # ✅ Compare actual vs. required fee
            if actual_fee < required_fee:
                print(f"[TXVALIDATION WARNING] Insufficient fee for transaction {tx_id}. Required: {required_fee}, Provided: {actual_fee}")
                return False

            print(f"[TXVALIDATION] Transaction {tx_id} meets or exceeds the required fee.")
            return True

        except Exception as e:
            print(f"[TXVALIDATION ERROR] Fee validation failed for transaction: {e}")
            return False

    def _calculate_transaction_size(self, tx: Any) -> int:
        """
        Compute transaction size using single SHA3-384 hashing approach
        or naive JSON-based size. Adjust as needed for your environment.
        :param tx: The transaction object.
        :return: Size in bytes, or -1 on error.
        """
        try:
            # ✅ Ensure tx_id is converted if stored as bytes
            if hasattr(tx, "tx_id") and isinstance(tx.tx_id, bytes):
                tx.tx_id = tx.tx_id.decode("utf-8")

            # ✅ Ensure transaction is serializable
            if hasattr(tx, "to_dict"):
                to_serialize = tx.to_dict()
            else:
                print("[TXVALIDATION ERROR] Transaction object does not support serialization.")
                return -1

            # ✅ Serialize transaction data and calculate size
            serialized = json.dumps(to_serialize, sort_keys=True).encode("utf-8")
            size_in_bytes = len(serialized)

            print(f"[TXVALIDATION] Computed transaction size: {size_in_bytes} bytes.")
            return size_in_bytes

        except Exception as e:
            print(f"[TXVALIDATION ERROR] Failed to calculate transaction size: {e}")
            return -1
