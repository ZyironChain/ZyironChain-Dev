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
        print("[TXValidation] ✅ Initialized with block_manager, block_metadata, and fee_model.")

    def _validate_coinbase(self, tx: Any) -> bool:
        """
        Validate a coinbase transaction:
         - Must have no inputs, exactly one output, type == 'COINBASE', fee == 0.
         - Transaction ID is verified with single SHA3-384 hashing.
        :param tx: Transaction object (CoinbaseTx).
        :return: True if valid coinbase transaction, False otherwise.
        """
        print(f"[TXValidation] 🔍 Validating Coinbase transaction {getattr(tx, 'tx_id', 'UNKNOWN')}...")

        if not hasattr(tx, "tx_id") or not isinstance(tx.tx_id, str):
            print("[TXValidation ERROR] ❌ Coinbase transaction missing or invalid 'tx_id'.")
            return False

        # ✅ Verify transaction ID with single SHA3-384 hashing
        try:
            single_hashed_tx_id = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()
            print(f"[TXValidation] 🔑 Coinbase tx_id hash: {single_hashed_tx_id[:24]}...")
        except Exception as e:
            print(f"[TXValidation ERROR] ❌ Failed to hash tx_id: {e}")
            return False

        # ✅ Ensure valid Coinbase transaction structure
        if not isinstance(tx, CoinbaseTx) or len(tx.inputs) > 0 or len(tx.outputs) != 1:
            print("[TXValidation ERROR] ❌ Invalid Coinbase transaction structure.")
            return False

        if tx.type.upper() != "COINBASE" or Decimal(tx.fee) != Decimal("0"):
            print("[TXValidation ERROR] ❌ Coinbase transaction type must be 'COINBASE' and fee must be 0.")
            return False

        print(f"[TXValidation] ✅ Coinbase transaction {tx.tx_id} is valid.")
        return True

    def validate_transaction_fee(self, transaction: Any) -> bool:
        """
        Validate a transaction's fee using FeeModel:
         - Computes required fee based on transaction type and amount.
         - Compares required fee with actual (inputs - outputs).
        :param transaction: The transaction object to check.
        :return: True if fee is sufficient, False otherwise.
        """
        try:
            tx_id = getattr(transaction, "tx_id", "UNKNOWN")
            print(f"[TXValidation] 🔍 Validating fee for transaction {tx_id}...")

            # ✅ Ensure transaction structure is valid
            if not hasattr(transaction, "inputs") or not hasattr(transaction, "outputs") or not hasattr(transaction, "type"):
                print("[TXValidation ERROR] ❌ Invalid transaction structure.")
                return False

            # ✅ Compute total input and output amounts
            try:
                input_sum = sum(Decimal(inp.amount) for inp in transaction.inputs if hasattr(inp, "amount"))
                output_sum = sum(Decimal(out.amount) for out in transaction.outputs if hasattr(out, "amount"))
                actual_fee = input_sum - output_sum
                print(f"[TXValidation] 💰 Actual fee calculated from I/O: {actual_fee}")
            except Exception as e:
                print(f"[TXValidation ERROR] ❌ Failed to compute transaction amounts: {e}")
                return False

            # ✅ Compute required fee from FeeModel
            try:
                required_fee = self.fee_model.calculate_fee_and_tax(
                    block_size=Constants.MAX_BLOCK_SIZE_MB,
                    payment_type=transaction.type,
                    amount=input_sum,
                    tx_size=0  # ✅ Transaction size no longer used
                )["base_fee"]
                print(f"[TXValidation] 🔑 Required fee: {required_fee}")
            except Exception as e:
                print(f"[TXValidation ERROR] ❌ Failed to compute required fee: {e}")
                return False

            # ✅ Compare actual vs. required fee
            if actual_fee < required_fee:
                print(f"[TXValidation WARNING] ⚠️ Insufficient fee for {tx_id}. Required: {required_fee}, Provided: {actual_fee}")
                return False

            print(f"[TXValidation] ✅ Transaction {tx_id} has a valid fee.")
            return True

        except Exception as e:
            print(f"[TXValidation ERROR] ❌ Fee validation failed for transaction {tx_id}: {e}")
            return False
