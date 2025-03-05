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
from Zyiron_Chain.database.poc import PoC

class TransactionFactory:
    """
    Factory for creating transactions dynamically based on type.
    Uses single SHA3-384 hashing, handles all data as bytes where necessary,
    and prints detailed status messages.
    """

    @staticmethod
    def create_transaction(tx_type: TransactionType, inputs: List[Dict], outputs: List[Dict], poc: PoC = None) -> Transaction:
        print(f"[TransactionFactory.create_transaction] START: Creating transaction of type '{tx_type.name}'.")
        if poc is None:
            poc = PoC()  # Instantiate PoC with default storage configuration
            print(f"[TransactionFactory.create_transaction] INFO: PoC instance created with default storage.")

        # Validate transaction type using Constants mapping
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
            print(f"[TransactionFactory.create_transaction] WARNING: Transaction fee too low ({fee}). Adjusting to minimum: {Constants.MIN_TRANSACTION_FEE}")
            fee = Decimal(Constants.MIN_TRANSACTION_FEE)

        # Generate a unique transaction ID using single SHA3-384 hashing
        base_data = f"{prefix}{','.join(str(Decimal(inp.get('amount', '0'))) for inp in inputs)}{time.time()}"
        tx_id = sha3_384(base_data.encode()).hexdigest()[:64]
        print(f"[TransactionFactory.create_transaction] INFO: Generated transaction ID: {tx_id}")

        # Create the Transaction object with inputs and outputs
        transaction = Transaction(
            inputs=[TransactionIn.from_dict(inp) for inp in inputs],
            outputs=[TransactionOut.from_dict(out) for out in outputs],
            tx_id=tx_id,
            poc=poc
        )

        # Set required confirmations based on the transaction type from Constants
        required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(tx_type.name.upper(), 8)
        transaction.confirmations_required = required_confirmations

        print(f"[TransactionFactory.create_transaction] SUCCESS: Created '{tx_type.name}' transaction {tx_id} with {len(inputs)} inputs and {len(outputs)} outputs. Required confirmations: {required_confirmations}")
        return transaction
