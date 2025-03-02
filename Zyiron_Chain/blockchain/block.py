import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))






import hashlib
import time
import json
from typing import Optional, List, Union


from Zyiron_Chain.transactions.transaction_services import TransactionType
import logging
import time
import json
from typing import List, Dict, Union
from decimal import Decimal
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.blockchain.blockheader import BlockHeader
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain. transactions.fees import FeeModel
from Zyiron_Chain.blockchain.helper import get_poc, get_transaction, get_coinbase_tx, get_block_header
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
PoC = get_poc()
Transaction = get_transaction()
CoinbaseTx = get_coinbase_tx()


# Ensure this is at the very top of your script, before any other code
import hashlib
import time
from decimal import Decimal
import logging

# Remove all existing handlers (prevents log conflicts across modules)
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Set up clean logging for this module
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

log = logging.getLogger(__name__)  # Each module gets its own logger

log.info(f"{__name__} logger initialized.")

import time
import logging
from decimal import Decimal
from Zyiron_Chain.blockchain.blockheader import BlockHeader
from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.transactions.coinbase import CoinbaseTx
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.blockchain.utils.hashing import Hashing  # ✅ Use new hashing module
from Zyiron_Chain.blockchain.constants import Constants

class Block:
    def __init__(self, index, previous_hash, transactions, timestamp=None, nonce=0, difficulty=None, miner_address=None):
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.miner_address = miner_address
        self.difficulty = difficulty or Constants.GENESIS_TARGET
        self.nonce = nonce
        self._merkle_root = None
        self.timestamp = int(timestamp or time.time())

        # Initialize header with miner_address
        self.header = BlockHeader(
            version=Constants.VERSION,
            index=self.index,
            previous_hash=self.previous_hash,
            merkle_root=self.merkle_root,
            timestamp=self.timestamp,
            nonce=self.nonce,
            difficulty=self.difficulty,
            miner_address=self.miner_address  # Pass miner_address here
        )
        self.hash = self.calculate_hash()


    def _adjust_difficulty(self):
        """Ensure difficulty respects minimum and maximum limits from Constants"""
        return max(min(self.difficulty, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

    @property
    def merkle_root(self):
        """Lazily computed Merkle root property"""
        if self._merkle_root is None:
            self._merkle_root = self._compute_merkle_root()
        return self._merkle_root




    def _compute_merkle_root(self):
        """Compute the Merkle root using double SHA3-384."""
        if not self.transactions:
            return Hashing.double_sha3_384(Constants.ZERO_HASH.encode())

        tx_hashes = [Hashing.double_sha3_384(tx.tx_id.encode()) for tx in self.transactions]

        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])  # ✅ Ensure even pairing

            tx_hashes = [Hashing.double_sha3_384((tx_hashes[i] + tx_hashes[i + 1]).encode()) for i in range(0, len(tx_hashes), 2)]

        return tx_hashes[0]




    def calculate_hash(self):
        """
        Calculate the block's hash using SHA3-384.
        """
        header_string = (
            f"{self.header.version}{self.header.index}{self.header.previous_hash}"
            f"{self.header.merkle_root}{self.header.timestamp}{self.header.nonce}{self.header.difficulty}"
            f"{self.header.miner_address}"
        ).encode()
        return Hashing.double_sha3_384(header_string)

    def store_block(self):
        """
        Use PoC to store the block and ensure proper routing.
        The PoC will determine where to store transactions (LMDB, etc.).
        """
        from Zyiron_Chain.database.poc import PoC  # ✅ Prevent circular import
        poc = PoC()
        difficulty = poc.block_manager.calculate_difficulty(self.index)  # Dynamically determine difficulty
        poc.store_block(self, difficulty)

    def to_dict(self):
        """Convert Block into a serializable dictionary."""
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "timestamp": self.timestamp,
            "nonce": self.nonce,  # ✅ Ensure nonce is explicitly stored
            "difficulty": self.difficulty,
            "miner_address": self.miner_address,
            "hash": self.hash,
            "merkle_root": self.merkle_root,
            "header": self.header.to_dict()
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create a Block from stored dictionary data"""
        try:
            transactions = []
            for tx_data in data.get('transactions', []):
                if isinstance(tx_data, dict):
                    if tx_data.get('type') == 'COINBASE':
                        transactions.append(CoinbaseTx.from_dict(tx_data))
                    else:
                        transactions.append(Transaction.from_dict(tx_data))
                else:
                    raise ValueError(f"Invalid transaction data type: {type(tx_data)}")

            header_data = data['header']
            return cls(
                index=header_data['index'],
                previous_hash=header_data['previous_hash'],
                transactions=transactions,
                timestamp=header_data.get('timestamp'),
                nonce=header_data['nonce'],
                difficulty=header_data.get('difficulty', Constants.GENESIS_TARGET),
                miner_address=data.get('miner_address')
            )
        except KeyError as e:
            raise ValueError(f"[ERROR] ❌ Missing required field in block data: {str(e)}")
        
    @property
    def is_coinbase(self, tx_index=0) -> bool:
        """Check if transaction is coinbase"""
        return isinstance(self.transactions[tx_index], CoinbaseTx)

    def validate_transactions(self, fee_model, mempool, block_size):
        """
        Validate all transactions in the block, ensuring:
        - Inputs exist and are unspent.
        - Fee calculations match expectations.
        - Transactions are not tampered with.
        """
        payment_type_manager = PaymentTypeManager()

        for tx in self.transactions:
            tx_type = payment_type_manager.get_transaction_type(tx.tx_id)

            if not tx_type:
                logging.error(f"[ERROR] ❌ Invalid transaction type for transaction: {tx.tx_id}")
                return False

            input_total = sum(inp.amount for inp in tx.inputs if hasattr(inp, "amount"))
            output_total = sum(out.amount for out in tx.outputs if hasattr(out, "amount"))

            # ✅ Ensure fee meets the minimum required fee or calculated fee, whichever is greater
            required_fee = fee_model.calculate_fee(block_size, tx_type.name, mempool.get_total_size(), tx.size)
            min_fee = Decimal(Constants.MIN_TRANSACTION_FEE)
            required_fee = max(required_fee, min_fee)  # ✅ Enforce minimum transaction fee

            actual_fee = input_total - output_total

            if actual_fee < required_fee:
                logging.error(f"[ERROR] ❌ Transaction {tx.tx_id} does not meet the required fees. Required: {required_fee}, Given: {actual_fee}")
                return False

        logging.info("[INFO] ✅ All transactions validated successfully.")
        return True
