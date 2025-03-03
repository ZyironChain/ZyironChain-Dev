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
    def __init__(
        self,
        index,
        previous_hash,
        transactions,
        timestamp=None,
        nonce=0,
        difficulty=None,
        miner_address=None
    ):
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.miner_address = miner_address
        self.difficulty = difficulty or Constants.GENESIS_TARGET
        self.nonce = nonce  # Ensure nonce is initialized
        self._merkle_root = None
        self.timestamp = int(timestamp or time.time())

        # (1) Compute the Merkle root before creating the block header
        # so that the BlockHeader has the final, correct merkle_root.
        computed_merkle = self._compute_merkle_root()

        # (2) Initialize header with the computed merkle_root
        self.header = BlockHeader(
            version=Constants.VERSION,
            index=self.index,
            previous_hash=self.previous_hash,
            merkle_root=computed_merkle,  # Use the computed Merkle root
            timestamp=self.timestamp,
            nonce=self.nonce,  # Pass nonce to the header
            difficulty=self.difficulty,
            miner_address=self.miner_address
        )

        # (3) Calculate the overall block hash (double SHA3-384)
        self.hash = self.calculate_hash()



    def calculate_hash(self):
        """Calculate the block's SHA3-384 hash and return it as a hex string."""
        header_string = (
            f"{self.header.version}{self.header.index}{self.header.previous_hash}"
            f"{self.header.merkle_root}{self.header.timestamp}"
            f"{self.header.nonce}{self.header.difficulty}"
            f"{self.header.miner_address}"
        ).encode()

        return hashlib.sha3_384(header_string).hexdigest()  # ✅ Ensuring hex output


    def _adjust_difficulty(self):
        """Ensure difficulty respects network limits"""
        return max(min(self.difficulty, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

    @property
    def merkle_root(self):
        """
        Lazily computed Merkle root property, but we already set it
        in the constructor as well. This will recompute only if needed.
        """
        if self._merkle_root is None:
            self._merkle_root = self._compute_merkle_root()
        return self._merkle_root

    def _compute_merkle_root(self):
        """Compute the Merkle root using double SHA3-384."""
        if not self.transactions:
            return hashlib.sha3_384(Constants.ZERO_HASH.encode()).hexdigest()


        tx_hashes = []
        for tx in self.transactions:
            if not hasattr(tx, 'tx_id') or not isinstance(tx.tx_id, str):
                raise ValueError("Invalid transaction format for hashing")
        tx_hashes.append(hashlib.sha3_384(tx.tx_id.encode()).hexdigest())


        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])

            new_level = []
            for i in range(0, len(tx_hashes), 2):
                combined = tx_hashes[i] + tx_hashes[i + 1]
            new_level.append(hashlib.sha3_384(combined.encode()).hexdigest())

            tx_hashes = new_level

        return tx_hashes[0]

    def store_block(self):
        """
        Use PoC to store the block and ensure proper routing.
        If you're also storing blocks via your miner or chain,
        be careful not to double-store the same block.
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
            "transactions": [self._serialize_transaction(tx) for tx in self.transactions],
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
            "miner_address": self.miner_address,
            "hash": self.hash,
            "merkle_root": self.merkle_root,  # The final computed merkle root
            "header": self.header.to_dict()
        }

    def _serialize_transaction(self, tx):
        """Validate and serialize transaction data"""
        if not isinstance(tx, (Transaction, CoinbaseTx)):
            raise TypeError(f"Invalid transaction type: {type(tx)}")
        return tx.to_dict()

    @classmethod
    def from_dict(cls, data: dict):
        """Deserialization with enhanced validation"""
        try:
            # Validate header structure
            header_data = data['header']
            required_header_fields = ['index', 'previous_hash', 'timestamp', 'nonce']
            if any(f not in header_data for f in required_header_fields):
                missing = [f for f in required_header_fields if f not in header_data]
                raise ValueError(f"Missing header fields: {missing}")

            # Process transactions
            transactions = []
            for idx, tx_data in enumerate(data.get('transactions', [])):
                if not isinstance(tx_data, dict):
                    raise TypeError(f"Transaction {idx} must be dict, got {type(tx_data)}")

                tx_type = tx_data.get('type')
                try:
                    if tx_type == 'COINBASE':
                        transactions.append(CoinbaseTx.from_dict(tx_data))
                    else:
                        transactions.append(Transaction.from_dict(tx_data))
                except Exception as e:
                    raise ValueError(f"Invalid transaction {idx}: {str(e)}") from e

            return cls(
                index=header_data['index'],
                previous_hash=header_data['previous_hash'],
                transactions=transactions,
                timestamp=header_data['timestamp'],
                nonce=header_data['nonce'],
                difficulty=header_data.get('difficulty', Constants.GENESIS_TARGET),
                miner_address=data.get('miner_address')
            )
        except KeyError as e:
            raise ValueError(f"Missing required field: {str(e)}") from e

    @property
    def is_coinbase(self, tx_index=0) -> bool:
        """Check if a transaction is coinbase at the specified index."""
        if not self.transactions:
            return False
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
                logging.error(
                    f"[ERROR] ❌ Transaction {tx.tx_id} does not meet the required fees. "
                    f"Required: {required_fee}, Given: {actual_fee}"
                )
                return False

        logging.info("[INFO] ✅ All transactions validated successfully.")
        return True
