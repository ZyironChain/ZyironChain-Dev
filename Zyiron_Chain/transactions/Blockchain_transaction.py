
from Zyiron_Chain.database.poc import PoC

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))




import json
import hashlib
import time
from typing import List, Dict
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.utxo_manager import UTXOManager

import logging

def get_poc():
    """Lazy import PoC to break circular dependencies."""
    from Zyiron_Chain.database.poc import PoC
    return PoC


def get_poc_instance():
    """Dynamically import PoC only when needed to prevent circular imports."""
    return get_poc()


 # Use PoC for routing transactions
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager  # Ensure KeyManager is correctly imported

from decimal import Decimal

import hashlib
import time
from decimal import Decimal
from typing import List, Dict
from Zyiron_Chain.transactions.transactiontype import TransactionType, PaymentTypeManager


    
from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.transactions.txin import TransactionIn
from Zyiron_Chain.blockchain.utils.hashing import sha3_384_hash

import time
import logging
from typing import List, Dict
from hashlib import sha3_384
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager, TransactionType
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction, TransactionIn, TransactionOut
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.blockchain.constants import Constants

class TransactionFactory:
    """Factory for creating transactions dynamically based on type."""

    @staticmethod
    def create_transaction(tx_type: "TransactionType", inputs: List[Dict], outputs: List[Dict], poc=None) -> "Transaction":
        """
        Creates a new transaction based on the specified type.

        :param tx_type: The type of transaction (STANDARD, SMART, INSTANT, COINBASE).
        :param inputs: A list of input dictionaries representing UTXOs being spent.
        :param outputs: A list of output dictionaries specifying recipient addresses and amounts.
        :param poc: Optional PoC instance for blockchain interaction.
        :return: A validated `Transaction` instance.
        """
        if poc is None:
            poc = PoC(storage_type=Constants.DATABASES["blockchain"])  # ✅ Uses correct DB layer dynamically

        # ✅ Validate transaction type
        payment_manager = PaymentTypeManager()
        if tx_type not in payment_manager.TYPE_CONFIG:
            raise ValueError(f"[ERROR] Invalid transaction type: {tx_type}")

        # ✅ Fetch the correct prefix for the transaction type
        prefix = payment_manager.TYPE_CONFIG[tx_type]["prefixes"][0] if tx_type != TransactionType.STANDARD else ""

        # ✅ Validate inputs and outputs before creating the transaction
        if not inputs or not all(isinstance(inp, dict) for inp in inputs):
            raise ValueError("[ERROR] Invalid inputs: Must be a list of dictionaries.")
        if not outputs or not all(isinstance(out, dict) for out in outputs):
            raise ValueError("[ERROR] Invalid outputs: Must be a list of dictionaries.")

        # ✅ Generate a unique transaction ID using SHA3-384 hashing
        base_data = f"{prefix}{','.join(str(i['amount']) for i in inputs)}{str(time.time())}"
        tx_id = sha3_384(base_data.encode()).hexdigest()[:64]  # ✅ Proper hashing

        # ✅ Create the transaction object with validated inputs and outputs
        transaction = Transaction(
            inputs=[TransactionIn.from_dict(inp) for inp in inputs],
            outputs=[TransactionOut.from_dict(out) for out in outputs],
            tx_id=tx_id,
            poc=poc
        )

        logging.info(f"[TRANSACTION FACTORY] ✅ Created new {tx_type.name} transaction: {tx_id} with {len(inputs)} inputs and {len(outputs)} outputs.")

        return transaction
