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
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.miner_address = miner_address
        self._merkle_root = None  # Private cache for Merkle root
        
        # Initialize header with computed values
        self.header = BlockHeader(
            version=1,
            index=self.index,
            previous_hash=self.previous_hash,
            merkle_root=self.merkle_root,  # Uses the property below
            timestamp=int(timestamp or time.time()),
            nonce=nonce,
            difficulty=difficulty or Constants.GENESIS_TARGET
        )
        self.hash = self.calculate_hash()

    @property
    def merkle_root(self):
        """Lazily computed Merkle root property"""
        if self._merkle_root is None:
            self._merkle_root = self._compute_merkle_root()
        return self._merkle_root

    def _compute_merkle_root(self):
        """Internal method to calculate Merkle root"""
        if not self.transactions:
            return hashlib.sha3_384(b'').hexdigest()
            
        tx_hashes = [tx.tx_id for tx in self.transactions]
        
        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])
            tx_hashes = [
                hashlib.sha3_384(f"{a}{b}".encode()).hexdigest()
                for a, b in zip(tx_hashes[::2], tx_hashes[1::2])
            ]
        
        return tx_hashes[0]

    def calculate_hash(self):
        """
        Calculate block hash using SHA3-384.
        """
        header_data = (
            f"{self.header.version}"
            f"{self.header.index}"
            f"{self.header.previous_hash}"
            f"{self.header.merkle_root}"
            f"{self.header.timestamp}"
            f"{self.header.difficulty}"
            f"{self.header.nonce}"
        ).encode()
        return hashlib.sha3_384(header_data).hexdigest()

    @property
    def timestamp(self):
        """Read-only timestamp from header"""
        return self.header.timestamp

    def store_block(self):
        """
        Use PoC to store the block and ensure proper routing.
        The PoC will determine where to store transactions (SQLite, LMDB, etc.).
        """
        poc = PoC()
        difficulty = poc.block_manager.calculate_difficulty(self.index)  # Dynamically determine difficulty
        poc.store_block(self, difficulty)

    def calculate_hash(self):
        """Calculate hash using header data"""
        header_data = (
            f"{self.header.version}"
            f"{self.header.index}"
            f"{self.header.previous_hash}"
            f"{self.header.merkle_root}"
            f"{self.header.timestamp}"
            f"{self.header.difficulty}"
            f"{self.header.nonce}"
        ).encode()
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
    def from_dict(cls, data: dict):
        """Create a Block from stored dictionary data"""
        try:
            transactions = []
            for tx_data in data.get('transactions', []):
                # Handle coinbase transactions properly
                if tx_data.get('type') == 'COINBASE':
                    tx = CoinbaseTx.from_dict(tx_data)
                else:
                    tx = Transaction.from_dict(tx_data)
                transactions.append(tx)
            
            header_data = data['header']
            return cls(
                index=header_data['index'],
                previous_hash=header_data['previous_hash'],
                transactions=transactions,
                timestamp=header_data.get('timestamp'),
                nonce=header_data['nonce'],
                difficulty=header_data['difficulty'],
                miner_address=data.get('miner_address')
            )
        except KeyError as e:
            raise ValueError(f"Missing required field in block data: {str(e)}")
        


    @property
    def is_coinbase(self, tx_index=0) -> bool:
        """Check if transaction is coinbase"""
        return isinstance(self.transactions[tx_index], CoinbaseTx)



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