import time
import json
from hashlib import sha3_384
from decimal import Decimal
from typing import List, Dict

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.transactions.txin import TransactionIn
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.transactiontype import TransactionType

class TransactionFactory:
    """
    Factory for creating transactions dynamically based on type.
    Uses single SHA3-384 hashing, handles all data as bytes where necessary,
    and prints detailed status messages.
    """

    @staticmethod
    def create_transaction(tx_type: TransactionType, 
                           inputs: List[Dict], 
                           outputs: List[Dict]) -> Transaction:
        """
        Create a transaction of the specified type, with the provided inputs and outputs.
        Uses single SHA3-384 hashing for the transaction ID and ensures a minimum fee.
        
        :param tx_type: Enum specifying the transaction type (STANDARD, SMART, INSTANT, COINBASE, etc.).
        :param inputs: List of dictionaries describing the inputs. 
                       Each dict typically has {"tx_id": "...", "amount": "..."} or similar.
        :param outputs: List of dictionaries describing the outputs.
                        Each dict typically has {"address": "...", "amount": "..."} or similar.
        :return: A Transaction object (from your Zyiron_Chain.transactions.tx module).
        """
        print(f"[TransactionFactory.create_transaction] START: Creating transaction of type '{tx_type.name}'.")

        # Validate transaction type using Constants mapping
        # (Ensure it exists in TRANSACTION_MEMPOOL_MAP, or handle default)
        if tx_type.name not in Constants.TRANSACTION_MEMPOOL_MAP:
            raise ValueError(f"[TransactionFactory.create_transaction] ERROR: Invalid transaction type: {tx_type.name}")

        # Get prefix for the transaction type if defined
        prefixes = Constants.TRANSACTION_MEMPOOL_MAP[tx_type.name].get("prefixes", [])
        prefix = prefixes[0] if prefixes else ""
        if prefix:
            print(f"[TransactionFactory.create_transaction] INFO: Using prefix '{prefix}' for transaction type '{tx_type.name}'.")

        # Validate inputs and outputs
        if not inputs or not all(isinstance(inp, dict) for inp in inputs):
            raise ValueError("[TransactionFactory.create_transaction] ERROR: Invalid inputs; must be a list of dictionaries.")
        if not outputs or not all(isinstance(out, dict) for out in outputs):
            raise ValueError("[TransactionFactory.create_transaction] ERROR: Invalid outputs; must be a list of dictionaries.")

        # Calculate fee from inputs and outputs
        total_input = sum(Decimal(inp.get("amount", "0")) for inp in inputs)
        total_output = sum(Decimal(out.get("amount", "0")) for out in outputs)
        fee = total_input - total_output
        if fee < Decimal(Constants.MIN_TRANSACTION_FEE):
            print(f"[TransactionFactory.create_transaction] WARNING: Transaction fee too low ({fee}). "
                  f"Adjusting to minimum: {Constants.MIN_TRANSACTION_FEE}")
            fee = Decimal(Constants.MIN_TRANSACTION_FEE)

        # Generate a unique transaction ID using single SHA3-384 hashing
        base_data = f"{prefix}{','.join(str(Decimal(inp.get('amount', '0'))) for inp in inputs)}{time.time()}"
        # First pass of hashing
        tx_id_raw = sha3_384(base_data.encode()).hexdigest()
        # Optionally, you might just use that or slice it:
        tx_id = tx_id_raw[:64]
        print(f"[TransactionFactory.create_transaction] INFO: Generated transaction ID: {tx_id}")

        # Create the Transaction object with inputs and outputs
        transaction = Transaction(
            inputs=[TransactionIn.from_dict(inp) for inp in inputs],
            outputs=[TransactionOut.from_dict(out) for out in outputs],
            tx_id=tx_id
        )

        # If your Transaction class supports "fee" or "confirmations_required", set them
        # For example:
        # transaction.fee = fee
        # transaction.confirmations_required = some_value
        # But that depends on your actual Transaction class definition

        # For demonstration, let's assume there's an attribute "confirmations_required"
        required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(tx_type.name.upper(), 8)
        # If your Transaction class does not have "confirmations_required", remove this:
        if hasattr(transaction, "confirmations_required"):
            transaction.confirmations_required = required_confirmations

        print(f"[TransactionFactory.create_transaction] SUCCESS: Created '{tx_type.name}' transaction {tx_id} "
              f"with {len(inputs)} inputs and {len(outputs)} outputs. "
              f"Required confirmations: {required_confirmations} (if applicable).")

        return transaction