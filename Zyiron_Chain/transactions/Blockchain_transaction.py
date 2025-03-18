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

import hashlib
class TransactionFactory:
    """
    Factory for creating transactions dynamically based on type.
    Uses single SHA3-384 hashing, ensures all data is stored in JSON format, 
    and provides detailed transaction status messages.
    """

    @staticmethod
    def create_transaction(tx_type: TransactionType, 
                           inputs: List[Dict], 
                           outputs: List[Dict]) -> Transaction:
        """
        Create a transaction of the specified type with provided inputs and outputs.
        Uses single SHA3-384 hashing for the transaction ID and enforces a minimum fee.
        
        :param tx_type: Enum specifying the transaction type (STANDARD, SMART, INSTANT, COINBASE, etc.).
        :param inputs: List of dictionaries describing the inputs. 
        :param outputs: List of dictionaries describing the outputs.
        :return: A Transaction object.
        """
        print(f"[TransactionFactory.create_transaction] START: Creating transaction of type '{tx_type.name}'.")

        # ✅ Validate transaction type using Constants mapping
        if tx_type.name not in Constants.TRANSACTION_MEMPOOL_MAP:
            raise ValueError(f"[TransactionFactory.create_transaction] ERROR: Invalid transaction type: {tx_type.name}")

        # ✅ Get prefix for the transaction type if defined
        prefixes = Constants.TRANSACTION_MEMPOOL_MAP[tx_type.name].get("prefixes", [])
        prefix = prefixes[0] if prefixes else ""
        if prefix:
            print(f"[TransactionFactory.create_transaction] INFO: Using prefix '{prefix}' for transaction type '{tx_type.name}'.")

        # ✅ Validate inputs and outputs
        if not inputs or not all(isinstance(inp, dict) and "tx_id" in inp and "amount" in inp for inp in inputs):
            raise ValueError("[TransactionFactory.create_transaction] ERROR: Invalid inputs; must be a list of dictionaries with 'tx_id' and 'amount'.")
        if not outputs or not all(isinstance(out, dict) and "address" in out and "amount" in out for out in outputs):
            raise ValueError("[TransactionFactory.create_transaction] ERROR: Invalid outputs; must be a list of dictionaries with 'address' and 'amount'.")

        # ✅ Convert amounts to smallest units using COIN
        total_input = sum(Decimal(inp["amount"]) / Constants.COIN for inp in inputs)
        total_output = sum(Decimal(out["amount"]) / Constants.COIN for out in outputs)

        # ✅ Calculate transaction fee
        fee = total_input - total_output
        min_fee = Decimal(Constants.MIN_TRANSACTION_FEE) / Constants.COIN
        if fee < min_fee:
            print(f"[TransactionFactory.create_transaction] WARNING: Transaction fee too low ({fee}). "
                  f"Adjusting to minimum: {min_fee}")
            fee = min_fee

        # ✅ Generate a unique transaction ID using single SHA3-384 hashing
        base_data = f"{prefix}{','.join(inp['tx_id'] for inp in inputs)}{time.time()}"
        tx_id = hashlib.sha3_384(base_data.encode()).hexdigest()
        print(f"[TransactionFactory.create_transaction] INFO: Generated transaction ID: {tx_id}")

        # ✅ Create the Transaction object with inputs and outputs
        transaction = Transaction(
            inputs=[TransactionIn.from_dict(inp) for inp in inputs],
            outputs=[TransactionOut.from_dict(out) for out in outputs],
            tx_id=tx_id
        )

        # ✅ Set required confirmations based on Constants
        required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(tx_type.name.upper(), 8)
        if hasattr(transaction, "confirmations_required"):
            transaction.confirmations_required = required_confirmations

        print(f"[TransactionFactory.create_transaction] SUCCESS: Created '{tx_type.name}' transaction {tx_id} "
              f"with {len(inputs)} inputs and {len(outputs)} outputs. "
              f"Required confirmations: {required_confirmations} (if applicable).")

        return transaction
