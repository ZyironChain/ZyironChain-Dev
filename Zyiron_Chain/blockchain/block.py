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
from typing import List, Optional, Union

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

from Zyiron_Chain.blockchain.constants import Constants, store_transaction_signature
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


import time
import json
from decimal import Decimal
from typing import List, Union, Optional
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.hashing import Hashing

class Block:
    def __init__(
        self,
        index: int,
        previous_hash: str,
        transactions: List,
        timestamp: Optional[int] = None,
        nonce: int = 0,
        difficulty: Union[int, str] = None,
        miner_address: str = None,
        fees: Union[int, float, Decimal] = 0,
        version: str = Constants.VERSION  # ✅ Default to Constants.VERSION
    ):
        """
        Initializes a Block object with:
        - Optimized metadata storage (prevents oversized LMDB maps).
        - No redundant offsets or magic numbers.
        - JSON-compatible storage for seamless integration.
        """
        try:
            print(f"[Block.__init__] INFO: Initializing Block #{index}")

            # ✅ Validate `previous_hash`
            if not isinstance(previous_hash, str) or len(previous_hash) != 96:
                print(f"[DEBUG] previous_hash received: {previous_hash}")
                raise ValueError("[Block.__init__] ❌ ERROR: `previous_hash` must be a valid SHA3-384 hex string")

            self.previous_hash = previous_hash

            # ✅ Validate and Convert `difficulty`
            if difficulty is None:
                raise ValueError("[Block.__init__] ❌ ERROR: `difficulty` cannot be None")

            if isinstance(difficulty, int):
                # Convert integer difficulty to 96-character hex string
                self.difficulty = f"{difficulty:0>96x}"
            elif isinstance(difficulty, str) and len(difficulty) == 96:
                # Use as-is if already a 96-character hex string
                self.difficulty = difficulty
            else:
                raise ValueError(
                    f"[Block.__init__] ❌ ERROR: `difficulty` must be a 96-character hex string or integer. Got: {difficulty}"
                )

            # ✅ Assign block properties
            self.index = index
            self.transactions = transactions or []
            self.nonce = nonce
            self.timestamp = int(timestamp) if timestamp else int(time.time())

            # ✅ Validate `miner_address`
            if not isinstance(miner_address, str) or len(miner_address) > 128:
                raise ValueError("[Block.__init__] ❌ ERROR: `miner_address` must be a valid string (max 128 chars).")

            self.miner_address = miner_address

            # ✅ Store fees as Decimal
            self.fees = Decimal(fees)

            # ✅ Compute Merkle root
            self.merkle_root = self._compute_merkle_root()

            # ✅ Initialize block hash (set when mined)
            self.hash = None

            # ✅ Assign Coinbase TX ID
            self.tx_id = self._get_coinbase_tx_id()

            # ✅ Assign version (ensures compatibility with `Constants.VERSION`)
            self.version = version

            print(f"[Block.__init__] ✅ SUCCESS: Block #{self.index} initialized with version {self.version}.")

        except Exception as e:
            print(f"[Block.__init__] ❌ ERROR: Block initialization failed: {e}")
            raise

    def _compute_merkle_root(self) -> str:
        """
        Compute the Merkle root for the block's transactions using single SHA3-384 hashing.
        - If no transactions, returns a hash of ZERO_HASH.
        - Ensures all transactions are serializable before hashing.
        - Uses a pairwise tree structure to derive the final root.
        - Returns a hex string for LMDB compatibility.
        """
        try:
            # ✅ If no transactions, return a default Merkle root
            if not self.transactions:
                return Constants.ZERO_HASH  # ✅ Return default hash if no transactions exist

            # ✅ Convert transactions into SHA3-384 hashes (stored as hex)
            tx_hashes = []
            for tx in self.transactions:
                try:
                    # Ensure transaction has a serializable format
                    tx_serialized = json.dumps(tx.to_dict(), sort_keys=True).encode("utf-8") if hasattr(tx, "to_dict") else tx
                    tx_hash = Hashing.hash(tx_serialized).hex()
                    tx_hashes.append(tx_hash)
                except Exception as e:
                    print(f"[Block._compute_merkle_root] ❌ ERROR: Failed to process transaction: {e}")
                    return Constants.ZERO_HASH

            # ✅ If no valid transactions exist, return ZERO_HASH
            if not tx_hashes:
                return Constants.ZERO_HASH  # ✅ Return default hash

            # ✅ Compute Merkle tree
            while len(tx_hashes) > 1:
                if len(tx_hashes) % 2 != 0:
                    tx_hashes.append(tx_hashes[-1])  # Duplicate last hash if odd

                new_level = [Hashing.hash((tx_hashes[i] + tx_hashes[i + 1]).encode("utf-8")).hex() for i in range(0, len(tx_hashes), 2)]
                tx_hashes = new_level

            return tx_hashes[0]

        except Exception as e:
            print(f"[Block._compute_merkle_root] ❌ ERROR: Merkle root computation failed: {e}")
            return Constants.ZERO_HASH

    def calculate_hash(self) -> str:
        """
        Calculate the block's hash using single SHA3-384.
        - Ensures correct conversion of all fields.
        - Handles edge cases with proper type checking.
        - Returns the hash as a hex string for LMDB storage.
        """
        try:
            # ✅ **Ensure previous_hash and merkle_root are valid hex strings**
            previous_hash_hex = self.previous_hash if isinstance(self.previous_hash, str) else Constants.ZERO_HASH
            merkle_root_hex = self.merkle_root if isinstance(self.merkle_root, str) else Constants.ZERO_HASH

            # ✅ **Ensure difficulty is properly formatted**
            difficulty_hex = self.difficulty if isinstance(self.difficulty, str) else "00" * 48  # Default 48-byte hex

            # ✅ **Ensure miner_address is valid**
            miner_address_hex = self.miner_address if isinstance(self.miner_address, str) else "00" * 128  # Default 128-byte hex

            # ✅ **Concatenate all fields as a string before hashing**
            header_str = f"{self.index}|{previous_hash_hex}|{merkle_root_hex}|{self.timestamp}|{self.nonce}|{difficulty_hex}|{miner_address_hex}"

            # ✅ **Compute SHA3-384 hash and return as hex**
            return Hashing.hash(header_str.encode("utf-8")).hex()

        except Exception as e:
            print(f"[Block.calculate_hash] ❌ ERROR: Failed to compute block hash: {e}")
            return Constants.ZERO_HASH  # ✅ Return zero hash on failure

    def get_header(self) -> dict:
        """
        Returns a dictionary of the block header fields, formatted for LMDB storage.
        Ensures all fields are stored as properly formatted hex strings or default values.
        """
        return {
            "version": str(self.version) if hasattr(self, "version") else "1.00",
            "index": int(self.index),
            "previous_hash": str(self.previous_hash) if isinstance(self.previous_hash, str) else Constants.ZERO_HASH,
            "merkle_root": str(self.merkle_root) if isinstance(self.merkle_root, str) else Constants.ZERO_HASH,
            "timestamp": int(self.timestamp),
            "nonce": int(self.nonce),
            "difficulty": str(self.difficulty) if isinstance(self.difficulty, str) else "00" * 48,  # Default 48-byte hex
            "miner_address": str(self.miner_address) if isinstance(self.miner_address, str) else "00" * 128,  # Default 128-byte hex
            "transaction_signature": str(getattr(self, "transaction_signature", "00" * 48)),  # Ensure valid hex
            "reward": str(getattr(self, "reward", 0)),  # Convert reward to string for JSON storage
            "fees": str(getattr(self, "fees", 0))  # Convert fees to string for consistency
        }


    def to_dict(self) -> dict:
        """
        Serialize block to a dictionary with standardized field formatting.
        Ensures all fields are converted to proper formats for LMDB storage.
        """
        print("[Block.to_dict] INFO: Serializing block to dictionary for LMDB storage.")

        return {
            "header": {  # ✅ Ensure header is included
                "version": str(self.version) if hasattr(self, "version") else "1.00",
                "index": int(self.index),
                "previous_hash": str(self.previous_hash) if isinstance(self.previous_hash, str) else Constants.ZERO_HASH,
                "merkle_root": str(self.merkle_root) if isinstance(self.merkle_root, str) else Constants.ZERO_HASH,
                "timestamp": int(self.timestamp),
                "nonce": int(self.nonce),
                "difficulty": str(self.difficulty) if isinstance(self.difficulty, str) else "00" * 48,  
                "miner_address": str(self.miner_address) if isinstance(self.miner_address, str) else "00" * 128,
                "transaction_signature": str(getattr(self, "transaction_signature", "00" * 48)), 
                "reward": str(getattr(self, "reward", 0)),  
                "fees": str(getattr(self, "fees", 0)),  
            },
            "transactions": [
                tx.to_dict() if hasattr(tx, "to_dict") else tx for tx in self.transactions
            ],
            "hash": str(self.hash) if isinstance(self.hash, str) else Constants.ZERO_HASH
        }


    @classmethod
    def from_dict(cls, data: dict) -> "Block":
        """
        Deserialize a block from a dictionary, ensuring proper type conversions and safety checks.
        - Handles edge cases for missing or invalid fields.
        - Ensures proper type conversion for all fields.
        - Preserves the original hash if available; otherwise, computes it.
        """
        try:
            print("[Block.from_dict] INFO: Reconstructing block from dict.")

            # ✅ Check if block uses new structure (has 'header')
            if "header" in data:
                header = data["header"]
            else:
                # ✅ Handle legacy format where header fields are at root level
                header = data
                print("[Block.from_dict] ⚠️ WARNING: Missing 'header' field. Using legacy format.")

            required_fields = {"index", "previous_hash", "merkle_root", "timestamp", "nonce", "difficulty", "miner_address"}

            if not required_fields.issubset(header.keys()):
                missing_fields = required_fields - set(header.keys())
                raise ValueError(f"[Block.from_dict] ❌ ERROR: Missing required fields in 'header': {missing_fields}")

            # ✅ Ensure proper field conversion
            difficulty_hex = str(header.get("difficulty", "00" * 48))  # Default 48-byte hex
            previous_hash = str(header.get("previous_hash", Constants.ZERO_HASH))
            merkle_root = str(header.get("merkle_root", Constants.ZERO_HASH))
            miner_address = str(header.get("miner_address", "00" * 128))  # Default 128-byte hex

            # ✅ Rebuild transactions safely
            rebuilt_transactions = []
            for tx_data in data.get("transactions", []):
                if not isinstance(tx_data, dict):
                    print(f"[Block.from_dict] ❌ ERROR: Transaction must be a dict, got {type(tx_data)}. Skipping.")
                    continue  

                tx_type = tx_data.get("type", "STANDARD").upper()
                try:
                    if tx_type == "COINBASE":
                        from Zyiron_Chain.transactions.coinbase import CoinbaseTx
                        rebuilt_transactions.append(CoinbaseTx.from_dict(tx_data))
                    else:
                        from Zyiron_Chain.transactions.tx import Transaction
                        rebuilt_transactions.append(Transaction.from_dict(tx_data))
                except Exception as tx_error:
                    print(f"[Block.from_dict] ❌ ERROR: Failed to parse transaction {tx_data.get('tx_id', 'UNKNOWN')}: {tx_error}")
                    continue  

            # ✅ Construct Block object with properly formatted fields
            try:
                block = cls(
                    index=int(header["index"]),
                    previous_hash=previous_hash,
                    transactions=rebuilt_transactions,
                    timestamp=int(header["timestamp"]),
                    nonce=int(header["nonce"]),
                    difficulty=difficulty_hex,
                    miner_address=miner_address
                )
            except (ValueError, TypeError) as e:
                print(f"[Block.from_dict] ❌ ERROR: Failed to construct block: {e}")
                raise

            # ✅ Assign optional fields with proper conversion
            try:
                block.transaction_signature = str(header.get("transaction_signature", "00" * 48))
                block.reward = Decimal(str(header.get("reward", "0")))
                block.fees = Decimal(str(header.get("fees", "0")))
                block.version = str(header.get("version", "1.00"))
            except (ValueError, TypeError) as e:
                print(f"[Block.from_dict] ❌ ERROR: Failed to assign optional fields: {e}")
                raise

            # ✅ Preserve hash if already mined; otherwise, compute it
            try:
                block.hash = str(data.get("hash", block.calculate_hash()))
            except (ValueError, TypeError) as e:
                print(f"[Block.from_dict] ❌ ERROR: Failed to process block hash: {e}")
                raise

            print(f"[Block.from_dict] ✅ SUCCESS: Block #{block.index} reconstructed successfully.")
            return block

        except Exception as e:
            print(f"[Block.from_dict] ❌ ERROR: Failed to deserialize block: {e}")
            raise


    def __repr__(self) -> str:
        """
        String representation for debugging.
        """
        hash_display = self.hash[:10] + "..." if isinstance(self.hash, str) else "UNKNOWN"
        prev_hash_display = self.previous_hash[:10] + "..." if isinstance(self.previous_hash, str) else "UNKNOWN"
        merkle_display = self.merkle_root[:10] + "..." if isinstance(self.merkle_root, str) else "UNKNOWN"

        return (
            f"<Block index={self.index} hash={hash_display} "
            f"prev={prev_hash_display} merkle={merkle_display} "
            f"tx_count={len(self.transactions)}>"
        )

    def _get_coinbase_tx_id(self) -> Optional[str]:
        """
        Retrieves the `tx_id` of the Coinbase transaction, if present.
        """
        print("[Block._get_coinbase_tx_id] INFO: Searching for Coinbase TX.")

        for tx in self.transactions:
            # Ensure transaction has a dictionary representation
            tx_dict = tx.to_dict() if hasattr(tx, "to_dict") else tx

            # Validate transaction format
            if not isinstance(tx_dict, dict):
                print(f"[Block._get_coinbase_tx_id] ❌ ERROR: Invalid transaction format in Block {self.index}. Skipping.")
                continue

            tx_type = tx_dict.get("type", "").upper()
            tx_id = tx_dict.get("tx_id", None)

            if tx_type == "COINBASE" and tx_id:
                print(f"[Block._get_coinbase_tx_id] ✅ Found Coinbase TX with ID: {tx_id}")
                return tx_id  # Return Coinbase transaction ID

        print("[Block._get_coinbase_tx_id] ❌ ERROR: No Coinbase TX found in this block.")
        return None  # If no Coinbase TX exists
