import sys
import os
import json
import hashlib
import time
import math
from decimal import Decimal
from threading import Lock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.utils.key_manager import KeyManager
from Zyiron_Chain.utils.hashing import Hashing

def get_transaction():
    """Lazy import to prevent circular dependencies"""
    from Zyiron_Chain.transactions.Blockchain_transaction import Transaction
    return Transaction

def get_coinbase_tx():
    """Lazy import to prevent circular dependencies"""
    from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
    return CoinbaseTx

# =============================================================================
# Combined Block class (merging Block and BlockHeader)
# =============================================================================
class Block:
    def __init__(self, index, previous_hash, transactions, timestamp=None, nonce=0, difficulty=None, miner_address=None):
        """
        Initialize a Block with header fields merged into this class.
        
        - All header fields are stored directly in the Block.
        - Data is processed as bytes; single SHA3-384 hashing is used.
        - Constants are used for defaults.
        """
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.miner_address = miner_address
        self.difficulty = difficulty or Constants.GENESIS_TARGET
        self.nonce = nonce
        self.timestamp = int(timestamp or time.time())
        self.version = Constants.VERSION
        
        print(f"[Block.__init__] INIT: Creating Block {self.index} with previous_hash: {self.previous_hash}.")

        # Compute Merkle root using single hashing (all in bytes)
        self.merkle_root = self._compute_merkle_root()
        print(f"[Block.__init__] INFO: Computed Merkle root: {self.merkle_root}.")

        # Calculate overall block hash using our single hashing method
        self.hash = self.calculate_hash()
        print(f"[Block.__init__] SUCCESS: Block {self.index} hash computed as: {self.hash}.")

    def calculate_hash(self):
        """
        Calculate the block's hash using single SHA3-384 hashing.
        All header fields are concatenated as strings and encoded as bytes.
        Returns the hash as a hex string.
        """
        header_str = (
            f"{self.version}{self.index}{self.previous_hash}"
            f"{self.merkle_root}{self.timestamp}{self.nonce}"
            f"{self.difficulty}{self.miner_address}"
        )
        header_bytes = header_str.encode()
        # Use our Hashing.hash() which returns bytes, then convert to hex for output.
        block_hash = Hashing.hash(header_bytes).hex()
        print(f"[Block.calculate_hash] INFO: Calculated hash from header bytes: {block_hash}.")
        return block_hash

    def _compute_merkle_root(self):
        """
        Compute the Merkle root for the block's transactions using single SHA3-384 hashing.
        - If no transactions exist, returns the hash of Constants.ZERO_HASH.
        - Each transaction is serialized (via to_dict if available) and hashed.
        """
        if not self.transactions:
            zero_hash = Hashing.hash(Constants.ZERO_HASH.encode()).hex()
            print(f"[Block._compute_merkle_root] WARNING: No transactions found. Using ZERO_HASH: {zero_hash}.")
            return zero_hash

        tx_hashes = []
        for tx in self.transactions:
            try:
                to_serialize = tx.to_dict() if hasattr(tx, "to_dict") else tx
                tx_serialized = json.dumps(to_serialize, sort_keys=True).encode()
                # Use single SHA3-384 hashing; returns bytes.
                tx_hash = Hashing.hash(tx_serialized)
                tx_hashes.append(tx_hash)
            except Exception as e:
                print(f"[Block._compute_merkle_root] ERROR: Failed to serialize transaction. Exception: {e}.")
                raise e

        # Build the Merkle tree pairwise
        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])
            new_level = []
            for i in range(0, len(tx_hashes), 2):
                combined = tx_hashes[i] + tx_hashes[i + 1]  # both are bytes
                new_hash = Hashing.hash(combined)
                new_level.append(new_hash)
            tx_hashes = new_level

        merkle_root = tx_hashes[0].hex()
        return merkle_root

    def store_block(self):
        """
        Store the block using PoC (Proof-of-Concept) module.
        Ensures proper routing of block storage.
        """
        from Zyiron_Chain.database.poc import PoC  # Prevent circular import
        poc = PoC()
        difficulty = poc.block_manager.calculate_difficulty(self.index)
        poc.store_block(self, difficulty)
        print(f"[Block.store_block] SUCCESS: Block {self.index} stored with difficulty {hex(difficulty)}.")

    def to_dict(self):
        """
        Convert the Block into a serializable dictionary.
        """
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "transactions": [self._serialize_transaction(tx) for tx in self.transactions],
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
            "miner_address": self.miner_address,
            "hash": self.hash,
            "merkle_root": self.merkle_root,
            "version": self.version
        }

    def _serialize_transaction(self, tx):
        """
        Validate and serialize a transaction.
        """
        from Zyiron_Chain.transactions.tx import Transaction
        from Zyiron_Chain.transactions.coinbase import CoinbaseTx
        if not isinstance(tx, (Transaction, CoinbaseTx)):
            raise TypeError(f"Invalid transaction type: {type(tx)}")
        return tx.to_dict()

    @classmethod
    def from_dict(cls, data: dict):
        """
        Deserialize a Block from a dictionary with enhanced validation.
        """
        try:
            required_fields = ["index", "previous_hash", "timestamp", "nonce"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")

            transactions = []
            for idx, tx_data in enumerate(data.get("transactions", [])):
                if not isinstance(tx_data, dict):
                    raise TypeError(f"Transaction {idx} must be a dict, got {type(tx_data)}")
                tx_type = tx_data.get("type")
                if tx_type == "COINBASE":
                    from Zyiron_Chain.transactions.coinbase import CoinbaseTx
                    transactions.append(CoinbaseTx.from_dict(tx_data))
                else:
                    from Zyiron_Chain.transactions.tx import Transaction
                    transactions.append(Transaction.from_dict(tx_data))

            return cls(
                index=data["index"],
                previous_hash=data["previous_hash"],
                transactions=transactions,
                timestamp=data["timestamp"],
                nonce=data["nonce"],
                difficulty=data.get("difficulty", Constants.GENESIS_TARGET),
                miner_address=data.get("miner_address")
            )
        except KeyError as e:
            raise ValueError(f"Missing required field: {str(e)}") from e

    @property
    def is_coinbase(self) -> bool:
        """
        Check if the first transaction is a coinbase transaction.
        """
        from Zyiron_Chain.transactions.coinbase import CoinbaseTx
        return bool(self.transactions) and isinstance(self.transactions[0], CoinbaseTx)

    def validate_transactions(self, fee_model, mempool, block_size):
        """
        Validate all transactions in the block.
        - Checks input/output totals against fees.
        - Ensures each transaction meets required fee thresholds.
        """
        payment_type_manager = PaymentTypeManager()
        for tx in self.transactions:
            tx_type = payment_type_manager.get_transaction_type(tx.tx_id)
            if not tx_type:
                print(f"[Block.validate_transactions] ERROR: Invalid transaction type for transaction: {tx.tx_id}.")
                return False

            input_total = sum(inp.amount for inp in tx.inputs if hasattr(inp, "amount"))
            output_total = sum(out.amount for out in tx.outputs if hasattr(out, "amount"))
            required_fee = fee_model.calculate_fee(block_size, tx_type.name, mempool.get_total_size(), tx.size)
            min_fee = Decimal(Constants.MIN_TRANSACTION_FEE)
            required_fee = max(required_fee, min_fee)
            actual_fee = input_total - output_total

            if actual_fee < required_fee:
                print(f"[Block.validate_transactions] ERROR: Transaction {tx.tx_id} does not meet required fees. Required: {required_fee}, Given: {actual_fee}.")
                return False

        print("[Block.validate_transactions] SUCCESS: All transactions validated successfully.")
        return True

    def __repr__(self):
        return (
            f"Block(index={self.index}, previous_hash={self.previous_hash[:10]}..., "
            f"merkle_root={self.merkle_root[:10]}..., nonce={self.nonce}, "
            f"timestamp={self.timestamp}, difficulty={hex(self.difficulty)}, "
            f"miner_address={self.miner_address})"
        )
