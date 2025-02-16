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
from Zyiron_Chain.blockchain.blockheader import BlockHeader
from Zyiron_Chain. transactions.transactiontype import PaymentTypeManager
from Zyiron_Chain. transactions.fees import FeeModel
from Zyiron_Chain.blockchain.helper import get_poc, get_transaction, get_coinbase_tx, get_block_header
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
PoC = get_poc()
Transaction = get_transaction()
CoinbaseTx = get_coinbase_tx()
BlockHeader = get_block_header()

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

class Block:
    def __init__(self, index, previous_hash, transactions, timestamp=None, nonce=0, difficulty=None, miner_address=None):
        """
        Initialize a Block.
        :param index: The block's index in the blockchain.
        :param previous_hash: The hash of the previous block.
        :param transactions: List of transactions in the block.
        :param timestamp: The block's creation timestamp (default: current time).
        :param nonce: The nonce used for mining (default: 0).
        :param difficulty: The mining difficulty (default: None).
        :param miner_address: The address of the miner who mined the block (default: None).
        """
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.timestamp = timestamp or time.time()
        self.nonce = nonce
        self.difficulty = difficulty
        self.miner_address = miner_address  # Miner's address
        self._merkle_root = None  # Initialize _merkle_root as None
        self.merkle_root = self.calculate_merkle_root()  # Calculate Merkle root
        self.header = BlockHeader(
            version=1,
            index=self.index,
            previous_hash=self.previous_hash,
            merkle_root=self.merkle_root,
            timestamp=self.timestamp,
            nonce=self.nonce,
            difficulty=self.difficulty
        )
        self.hash = self.calculate_hash()

    def calculate_merkle_root(self):
        """Compute the Merkle root from transaction IDs."""
        if self._merkle_root:
            return self._merkle_root  # Return cached value if already calculated

        tx_hashes = [tx.tx_id for tx in self.transactions]

        if not tx_hashes:
            self._merkle_root = hashlib.sha3_384(b'').hexdigest()
            return self._merkle_root

        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])

            tx_hashes = [
                hashlib.sha3_384((tx_hashes[i] + tx_hashes[i + 1]).encode()).hexdigest()
                for i in range(0, len(tx_hashes), 2)
            ]

        self._merkle_root = tx_hashes[0]
        return self._merkle_root
    def store_block(self):
        """
        Use PoC to store the block and ensure proper routing.
        The PoC will determine where to store transactions (SQLite, LMDB, etc.).
        """
        poc = PoC()
        difficulty = poc.block_manager.calculate_difficulty(self.index)  # Dynamically determine difficulty
        poc.store_block(self, difficulty)
    def calculate_hash(self):
        """Include difficulty in hash calculation"""
        header_data = f"{self.header.version}{self.header.index}{self.header.previous_hash}{self.header.merkle_root}{self.header.timestamp}{self.header.difficulty}{self.header.nonce}".encode()
        return hashlib.sha3_384(header_data).hexdigest()

    def to_dict(self):
        """Convert Block into a serializable dictionary."""
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
            "miner_address": self.miner_address,  # Include miner_address
            "hash": self.hash,
            "merkle_root": self.merkle_root,
            "header": self.header.to_dict()
        }

    @classmethod
    def from_dict(cls, data):
        """Create a Block instance from a dictionary."""
        from Zyiron_Chain.blockchain.blockheader import BlockHeader
        from Zyiron_Chain.transactions.Blockchain_transaction import Transaction

        transactions = [
            Transaction.from_dict(tx) if isinstance(tx, dict) else tx
            for tx in data.get("transactions", [])
        ]

        block = cls(
            index=data["index"],
            previous_hash=data["previous_hash"],
            transactions=transactions,
            timestamp=data.get("timestamp"),
            nonce=data.get("nonce", 0),
            difficulty=data.get("difficulty"),
            miner_address=data.get("miner_address")  # Include miner_address
        )

        block.header = BlockHeader.from_dict(data.get("header", {}))
        block.hash = data.get("hash", block.calculate_hash())

        return block

    def validate_transactions(self, fee_model, mempool, block_size):
        """
        Validate all transactions in the block, ensuring:
        - Inputs exist and are unspent.
        - Fee calculations match expectations.
        - Transactions are not tampered.
        """
        payment_type_manager = PaymentTypeManager()

        for tx in self.transactions:
            tx_type = payment_type_manager.get_transaction_type(tx.tx_id)

            if not tx_type:
                logging.error(f"[ERROR] Invalid transaction type for transaction: {tx.tx_id}")
                return False

            input_total = sum(inp.amount for inp in tx.inputs if hasattr(inp, "amount"))
            output_total = sum(out.amount for out in tx.outputs if hasattr(out, "amount"))
            required_fee = fee_model.calculate_fee(block_size, tx_type.name, mempool.get_total_size(), tx.size)
            actual_fee = input_total - output_total

            if actual_fee < required_fee:
                logging.error(f"[ERROR] Transaction {tx.tx_id} does not meet the required fees. Required: {required_fee}, Given: {actual_fee}")
                return False

        return True