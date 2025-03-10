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
from typing import List, Optional

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
        previous_hash: bytes,
        transactions: List,
        timestamp: int = None,
        nonce: int = 0,
        difficulty: bytes = None,
        miner_address: str = None
    ):
        """
        Initializes a new block.
        - Ensures all required fields are present.
        - Computes the Merkle root and block hash.
        """
        print(f"[Block.__init__] Initializing Block #{index}")

        # ✅ **Ensure previous_hash is bytes**
        self.index = index
        self.previous_hash = previous_hash if isinstance(previous_hash, bytes) else bytes.fromhex(previous_hash)

        # ✅ **Ensure difficulty is bytes**
        self.difficulty = difficulty if isinstance(difficulty, bytes) else difficulty.to_bytes(48, 'big')

        self.transactions = transactions or []
        self.miner_address = miner_address.ljust(128, "\x00").encode() if miner_address else b"\x00" * 128  # ✅ Ensure consistent 128-byte padding
        self.nonce = nonce
        self.timestamp = int(timestamp) if timestamp else int(time.time())

        # ✅ **Version from constants**
        self.version = Constants.VERSION

        print(f"[Block.__init__] Creating Block #{self.index}")
        print(f" - Previous Hash: {self.previous_hash.hex()}")
        print(f" - Difficulty: {hex(int.from_bytes(self.difficulty, 'big'))}")  # ✅ Convert bytes to int for printing
        print(f" - Miner Address: {self.miner_address.decode().strip()}")
        print(f" - Timestamp: {self.timestamp}")
        print(f" - Nonce: {self.nonce}")

        # ✅ **Compute the Merkle root**
        self.merkle_root = self._compute_merkle_root()
        print(f"[Block.__init__] Merkle Root computed: {self.merkle_root.hex()}")

        # ✅ **Assign Coinbase TX ID**
        self.tx_id = self._get_coinbase_tx_id()
        print(f"[Block.__init__] Assigned Coinbase TX ID: {self.tx_id}")

        # ✅ **Hash is assigned only when mined**
        self.hash = None
        print(f"[Block.__init__] Block initialized successfully.")
              
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
        print("[Block.from_bytes] Deserializing block from bytes.")
        data = Deserializer().deserialize(block_bytes)
        return cls.from_dict(data)

    def calculate_hash(self) -> str:
        """
        Calculate the block's hash using single SHA3-384.
        """
        header_bytes = (
            self.version.to_bytes(4, 'big') +
            self.index.to_bytes(8, 'big') +
            self.previous_hash +
            self.merkle_root +
            self.timestamp.to_bytes(8, 'big') +
            self.nonce.to_bytes(8, 'big') +
            self.difficulty +
            self.miner_address
        )
        return Hashing.hash(header_bytes).hex()  # ✅ Properly hash bytes




    def _compute_merkle_root(self) -> str:
        """
        Compute the Merkle root for the block's transactions using single SHA3-384 hashing.
        - If no transactions, returns a hash of ZERO_HASH.
        - Validates each transaction before hashing.
        - Builds a pairwise tree of transaction hashes to derive the root.
        """
        try:
            print("[Block._compute_merkle_root] INFO: Computing Merkle Root...")

            # Handle Empty Transaction List
            if not self.transactions:
                print("[Block._compute_merkle_root] WARNING: No transactions found; using ZERO_HASH.")
                return Hashing.hash(Constants.ZERO_HASH.encode()).hex()  # ✅ Always return a hex string

            # Convert Transactions to Hashes
            tx_hashes = []
            for tx in self.transactions:
                try:
                    # Ensure transaction is serializable
                    tx_data = tx.to_dict() if hasattr(tx, "to_dict") else tx
                    tx_serialized = json.dumps(tx_data, sort_keys=True).encode("utf-8")
                    tx_hash = Hashing.hash(tx_serialized).hex()  # ✅ Ensure it returns a hex string
                    tx_hashes.append(tx_hash)

                except Exception as e:
                    print(f"[Block._compute_merkle_root] ❌ ERROR: Failed to serialize transaction: {e}")

            # Ensure We Have Valid Transactions
            if not tx_hashes:
                print("[Block._compute_merkle_root] ERROR: No valid transactions found. Using ZERO_HASH.")
                return Hashing.hash(Constants.ZERO_HASH.encode()).hex()

            # Build Merkle Tree
            while len(tx_hashes) > 1:
                if len(tx_hashes) % 2 != 0:
                    tx_hashes.append(tx_hashes[-1])  # Duplicate last hash if odd

                new_level = [Hashing.hash((tx_hashes[i] + tx_hashes[i + 1]).encode()).hex() for i in range(0, len(tx_hashes), 2)]
                tx_hashes = new_level  # Move to next Merkle tree level

            # Final Merkle Root
            merkle_root = tx_hashes[0]  # ✅ Ensure it remains a hex string
            print(f"[Block._compute_merkle_root] ✅ SUCCESS: Merkle Root computed: {merkle_root}")
            return merkle_root

        except Exception as e:
            print(f"[Block._compute_merkle_root] ❌ ERROR: Merkle root computation failed: {e}")
            return Hashing.hash(Constants.ZERO_HASH.encode()).hex()  # Return ZERO_HASH on failure



    def to_dict(self) -> dict:
        """
        Serialize block to a dictionary with standardized field formatting.
        """
        print("[Block.to_dict] Serializing block to dictionary.")

        return {
            "header": {
                "version": self.version,
                "index": self.index,
                "previous_hash": self.previous_hash.hex(),  # ✅ Ensure bytes are stored as hex
                "merkle_root": self.merkle_root.hex(),  # ✅ Ensure bytes are stored as hex
                "timestamp": self.timestamp,
                "nonce": self.nonce,
                "difficulty": self.difficulty.hex(),  # ✅ Store difficulty as a hex string
                "miner_address": self.miner_address.decode().strip(),  # ✅ Convert bytes to string and strip padding
                "transaction_signature": self.transaction_signature.hex() if hasattr(self, "transaction_signature") else "00" * 48,
                "reward": getattr(self, "reward", 0),
                "fees": getattr(self, "fees", 0),
            },
            "transactions": [
                tx.to_dict() if hasattr(tx, "to_dict") else tx for tx in self.transactions
            ],
            "tx_id": self.tx_id,
            "hash": self.hash
        }


    @classmethod
    def from_dict(cls, data: dict) -> "Block":
        """
        Deserialize a block from a dictionary.
        """
        print("[Block.from_dict] Reconstructing block from dict.")

        # ✅ Validate required fields
        required_fields = ["index", "previous_hash", "transactions", "timestamp", "nonce", "difficulty", "miner_address"]
        for field in required_fields:
            if field not in data["header"]:
                raise ValueError(f"[Block.from_dict] ERROR: Missing required field '{field}'.")

        # ✅ Convert difficulty back to bytes from hex
        difficulty_bytes = bytes.fromhex(data["header"]["difficulty"])

        # ✅ Ensure previous_hash and merkle_root are properly decoded from hex
        previous_hash_bytes = bytes.fromhex(data["header"]["previous_hash"])
        merkle_root_bytes = bytes.fromhex(data["header"]["merkle_root"])

        # ✅ Ensure miner address is trimmed to 128 bytes
        miner_address_clean = data["header"]["miner_address"].ljust(128, "\x00").encode()

        # ✅ Rebuild transaction objects
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
            index=data["header"]["index"],
            previous_hash=previous_hash_bytes,  # ✅ Ensure previous_hash is bytes
            transactions=rebuilt_transactions,
            timestamp=data["header"]["timestamp"],
            nonce=data["header"]["nonce"],
            difficulty=difficulty_bytes,  # ✅ Ensure difficulty is bytes
            miner_address=miner_address_clean  # ✅ Ensure miner_address is bytes
        )

        block.tx_id = data.get("tx_id")
        block.transaction_signature = bytes.fromhex(data["header"].get("transaction_signature", "00" * 48))
        block.reward = data["header"].get("reward", 0)
        block.fees = data["header"].get("fees", 0)
        block.version = data["header"].get("version", 1)  # Default version

        # ✅ Ensure Hash Consistency (Preserve Mined Hash)
        block.hash = data.get("hash", block.calculate_hash())

        print(f"[Block.from_dict] Block #{block.index} reconstructed successfully.")
        return block



    def __repr__(self) -> str:
        """
        String representation for debugging.
        """
        return (
            f"<Block index={self.index} hash={self.hash[:10]}... "
            f"prev={self.previous_hash[:10]}... merkle={self.merkle_root[:10]}...>"
        )

    def _get_coinbase_tx_id(self) -> Optional[str]:
        """
        Retrieves the `tx_id` of the Coinbase transaction, if present.
        """
        for tx in self.transactions:
            if hasattr(tx, "tx_type") and tx.tx_type == "COINBASE":
                print(f"[Block._get_coinbase_tx_id] Found Coinbase TX with ID: {tx.tx_id}")
                return tx.tx_id  # Get `tx_id` from the Coinbase transaction
        print("[Block._get_coinbase_tx_id] No Coinbase TX found.")
        return None  # If no Coinbase TX exists