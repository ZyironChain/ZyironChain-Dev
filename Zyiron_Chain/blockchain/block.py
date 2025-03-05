#!/usr/bin/env python3
"""
Block Class

Combines the old Block and BlockHeader into a single class.
- Contains all header fields directly.
- Uses single SHA3-384 hashing (via Hashing.hash).
- Provides a function get_header() that returns header fields in a dictionary.
- Removed references to PoC (no more store_block using PoC).
- Added detailed print statements for debugging and clarity.
"""

import sys
import os
import json
import time
from decimal import Decimal
from typing import List

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager

def get_transaction():
    """Lazy import to prevent circular dependencies (if needed)."""
    from Zyiron_Chain.transactions.tx import Transaction
    return Transaction

def get_coinbase_tx():
    """Lazy import to prevent circular dependencies (if needed)."""
    from Zyiron_Chain.transactions.coinbase import CoinbaseTx
    return CoinbaseTx

from Zyiron_Chain.utils.deserializer import Deserializer



class Block:
    """
    A single Block in the blockchain, containing:
      - index, previous_hash, transactions
      - merged 'header' fields: merkle_root, timestamp, nonce, difficulty, miner_address, version
      - block hash (calculated from all header fields)
    """

    def __init__(
        self,
        index: int,
        previous_hash: str,
        transactions: List,
        timestamp: int = None,
        nonce: int = 0,
        difficulty: int = None,
        miner_address: str = None
    ):
        """
        :param index: The height of this block in the chain.
        :param previous_hash: The hash of the previous block.
        :param transactions: A list of transactions (including coinbase if any).
        :param timestamp: Block creation time (int). Defaults to current time if None.
        :param nonce: The nonce used for Proof-of-Work.
        :param difficulty: The difficulty target (int). Defaults to GENESIS_TARGET if None.
        :param miner_address: The address of the miner who found the block.
        """

        # Basic fields
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions or []
        self.miner_address = miner_address

        # Difficulty & timestamp
        self.difficulty = difficulty if difficulty is not None else Constants.GENESIS_TARGET
        self.nonce = nonce
        self.timestamp = int(timestamp) if timestamp else int(time.time())

        # Version from constants
        self.version = Constants.VERSION

        print(f"[Block.__init__] Creating Block #{self.index}")
        print(f" - Previous Hash: {self.previous_hash}")
        print(f" - Difficulty: {hex(self.difficulty)}")
        print(f" - Miner Address: {self.miner_address}")
        print(f" - Timestamp: {self.timestamp}")
        print(f" - Nonce: {self.nonce}")

        # Compute the Merkle root
        self.merkle_root = self._compute_merkle_root()
        print(f"[Block.__init__] Merkle Root computed: {self.merkle_root}")

        # Calculate the block hash
        self.hash = self.calculate_hash()
        print(f"[Block.__init__] Block #{self.index} hash computed: {self.hash}")

    def get_header(self) -> dict:
        """
        Returns a dictionary of the block header fields, i.e. the data
        that would typically be hashed for Proof-of-Work.
        """
        print("[Block.get_header] Returning header fields as a dictionary.")
        return {
            "version": self.version,
            "index": self.index,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
            "miner_address": self.miner_address
        }


    @classmethod
    def from_bytes(cls, block_bytes):
        """Deserialize a block from bytes."""
        data = Deserializer().deserialize(block_bytes)
        return cls.from_dict(data)

    def calculate_hash(self) -> str:
        """
        Calculate the block's hash by concatenating header fields and applying
        single SHA3-384 hashing. Returns a hex string.
        """
        print("[Block.calculate_hash] Calculating block hash from header fields...")
        header_str = (
            f"{self.version}{self.index}{self.previous_hash}"
            f"{self.merkle_root}{self.timestamp}{self.nonce}"
            f"{self.difficulty}{self.miner_address}"
        )
        header_bytes = header_str.encode("utf-8")

        # Single SHA3-384 hashing (Hashing.hash returns bytes)
        block_hash = Hashing.hash(header_bytes).hex()
        print(f"[Block.calculate_hash] Computed hash: {block_hash}")
        return block_hash

    def _compute_merkle_root(self) -> str:
        """
        Compute the Merkle root for the block's transactions using single SHA3-384 hashing.
         - If no transactions, returns a hash of ZERO_HASH.
         - Otherwise, builds a pairwise tree of transaction hashes.
        """
        print("[Block._compute_merkle_root] Computing Merkle Root...")

        if not self.transactions:
            print("[Block._compute_merkle_root] No transactions; using ZERO_HASH.")
            return Hashing.hash(Constants.ZERO_HASH.encode()).hex()

        # Convert each transaction to a hash
        tx_hashes = []
        for tx in self.transactions:
            try:
                # If the transaction has a to_dict, use it. Otherwise assume it's a dict already
                tx_data = tx.to_dict() if hasattr(tx, "to_dict") else tx
                tx_serialized = json.dumps(tx_data, sort_keys=True).encode("utf-8")
                tx_hash = Hashing.hash(tx_serialized)  # single-hash -> bytes
                tx_hashes.append(tx_hash)
            except Exception as e:
                print(f"[Block._compute_merkle_root] ERROR: Could not serialize transaction: {e}")
                return Hashing.hash(Constants.ZERO_HASH.encode()).hex()

        # Build the tree
        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])  # Duplicate the last one if odd
            new_level = []
            for i in range(0, len(tx_hashes), 2):
                combined = tx_hashes[i] + tx_hashes[i + 1]
                new_hash = Hashing.hash(combined)
                new_level.append(new_hash)
            tx_hashes = new_level

        merkle_root = tx_hashes[0].hex()
        print(f"[Block._compute_merkle_root] Merkle Root is {merkle_root}")
        return merkle_root

    def to_dict(self) -> dict:
        """
        Serialize the block to a dictionary, including all fields.
        """
        print("[Block.to_dict] Serializing block to dictionary.")
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "transactions": [
                tx.to_dict() if hasattr(tx, "to_dict") else tx for tx in self.transactions
            ],
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
            "miner_address": self.miner_address,
            "version": self.version,
            "merkle_root": self.merkle_root,
            "hash": self.hash
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Block":
        """
        Reconstruct a Block from a dictionary. Merges block+header fields.
        Expects data with 'index', 'previous_hash', 'transactions', 'timestamp', etc.
        """
        print("[Block.from_dict] Reconstructing block from dict.")
        # Basic validation
        required_fields = ["index", "previous_hash", "transactions", "timestamp", "nonce"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"[Block.from_dict] ERROR: Missing required field '{field}'.")

        # Rebuild transaction objects if needed
        rebuilt_transactions = []
        for tx_data in data.get("transactions", []):
            if not isinstance(tx_data, dict):
                raise TypeError(f"[Block.from_dict] ERROR: Transaction must be a dict, got {type(tx_data)}.")
            tx_type = tx_data.get("type", "STANDARD")
            if tx_type.upper() == "COINBASE":
                from Zyiron_Chain.transactions.coinbase import CoinbaseTx
                rebuilt_transactions.append(CoinbaseTx.from_dict(tx_data))
            else:
                from Zyiron_Chain.transactions.tx import Transaction
                rebuilt_transactions.append(Transaction.from_dict(tx_data))

        block = cls(
            index=data["index"],
            previous_hash=data["previous_hash"],
            transactions=rebuilt_transactions,
            timestamp=data["timestamp"],
            nonce=data["nonce"],
            difficulty=data.get("difficulty", Constants.GENESIS_TARGET),
            miner_address=data.get("miner_address")
        )

        # The block's hash might have changed if data changed, so we can recalc or trust 'hash' from dict
        # We'll just recalc for consistency:
        if "hash" in data and data["hash"] != block.hash:
            print("[Block.from_dict] WARNING: Provided block hash does not match recalculated hash. Using recalculated.")
        return block

    def __repr__(self) -> str:
        """
        String representation for debugging.
        """
        return (
            f"<Block index={self.index} hash={self.hash[:10]}... "
            f"prev={self.previous_hash[:10]}... merkle={self.merkle_root[:10]}...>"
        )
