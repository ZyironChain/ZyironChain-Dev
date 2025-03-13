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
    def __init__(
        self,
        index: int,
        previous_hash: Union[str, bytes],  # Can be hex string or bytes
        transactions: List,
        timestamp: int = None,
        nonce: int = 0,
        difficulty: Union[str, bytes, int] = None,  # Can be hex string, bytes, or int
        miner_address: Union[str, bytes] = None,  # Can be string or bytes
        fees: Union[int, float, Decimal] = 0,  # Add fees attribute
    ):
        """
        Initializes a new block.
        - Ensures all required fields are present.
        - Computes the Merkle root and block hash.
        - Handles multiple data formats (bytes, hex, int) with proper conversions.
        """
        print(f"[Block.__init__] Initializing Block #{index}")

        # ✅ **Ensure previous_hash is bytes**
        if isinstance(previous_hash, str):  
            self.previous_hash = bytes.fromhex(previous_hash)  # Convert hex string to bytes
        elif isinstance(previous_hash, bytes):
            self.previous_hash = previous_hash
        else:
            raise TypeError("previous_hash must be a hex string or bytes")

        # ✅ **Ensure difficulty is bytes**
        if isinstance(difficulty, str):  
            self.difficulty = bytes.fromhex(difficulty)
        elif isinstance(difficulty, bytes):  
            self.difficulty = difficulty
        elif isinstance(difficulty, int):
            self.difficulty = difficulty.to_bytes(48, 'big')  # Convert int to bytes
        else:
            raise TypeError("difficulty must be a hex string, bytes, or int")

        self.index = index
        self.transactions = transactions or []

        # ✅ **Ensure miner_address is bytes**
        if isinstance(miner_address, str):  
            self.miner_address = miner_address.ljust(128, "\x00").encode('utf-8')
        elif isinstance(miner_address, bytes):
            self.miner_address = miner_address
        else:
            self.miner_address = b"\x00" * 128  # Default to 128 null bytes

        self.nonce = nonce
        self.timestamp = int(timestamp) if timestamp else int(time.time())

        # ✅ **Ensure version is set from constants**
        self.version = Constants.VERSION  # Example: "1.00"

        # ✅ **Compute Merkle root internally**
        self.merkle_root = self._compute_merkle_root()

        # ✅ **Ensure fees are handled properly**
        self.fees = Decimal(fees)  

        # ✅ **Initialize hash as None (set when mined)**
        self.hash = None  

        print(f"[Block.__init__] Creating Block #{self.index}")
        print(f" - Previous Hash: {self.previous_hash.hex()}")
        print(f" - Difficulty: {hex(int.from_bytes(self.difficulty, 'big'))}")  
        print(f" - Miner Address: {self.miner_address.decode(errors='ignore').strip()}")
        print(f" - Timestamp: {self.timestamp}")
        print(f" - Nonce: {self.nonce}")
        print(f" - Merkle Root: {self.merkle_root.hex()}")
        print(f" - Fees: {self.fees}")

        # ✅ **Assign Coinbase TX ID**
        self.tx_id = self._get_coinbase_tx_id()
        print(f"[Block.__init__] Assigned Coinbase TX ID: {self.tx_id}")

        print(f"[Block.__init__] Block initialized successfully.")

    def to_json(self) -> str:
        """Serializes the Block to a JSON string with proper conversions."""
        return json.dumps(self.to_dict(), indent=4)
        
    def _compute_merkle_root(self) -> bytes:
        """
        Compute the Merkle root for the block's transactions using single SHA3-384 hashing.
        - If no transactions, returns a hash of ZERO_HASH.
        - Ensures all transactions are serializable before hashing.
        - Uses a pairwise tree structure to derive the final root.
        """
        try:
            print("[Block._compute_merkle_root] INFO: Computing Merkle Root...")

            # ✅ Handle case where there are no transactions
            if not self.transactions:
                print("[Block._compute_merkle_root] WARNING: No transactions found; using ZERO_HASH.")
                return Hashing.hash(Constants.ZERO_HASH.encode())  # ✅ Return bytes

            # ✅ Convert transactions into hashes
            tx_hashes = []
            for tx in self.transactions:
                try:
                    # Ensure transaction is in a serializable format
                    if isinstance(tx, bytes):
                        tx_serialized = tx  # Already bytes, use as-is
                    elif isinstance(tx, str):
                        tx_serialized = tx.encode("utf-8")  # Convert hex string to bytes
                    elif hasattr(tx, "to_dict"):
                        tx_serialized = json.dumps(tx.to_dict(), sort_keys=True).encode("utf-8")  # Convert dict to JSON bytes
                    else:
                        print(f"[Block._compute_merkle_root] ❌ ERROR: Unsupported transaction type: {type(tx)}")
                        continue  # Skip invalid transactions

                    # ✅ Hash the serialized transaction data
                    tx_hash = Hashing.hash(tx_serialized)
                    tx_hashes.append(tx_hash)

                except Exception as e:
                    print(f"[Block._compute_merkle_root] ❌ ERROR: Failed to serialize transaction: {e}")

            # ✅ Ensure valid transactions exist
            if not tx_hashes:
                print("[Block._compute_merkle_root] ERROR: No valid transactions found. Using ZERO_HASH.")
                return Hashing.hash(Constants.ZERO_HASH.encode())

            # ✅ Build Merkle tree
            while len(tx_hashes) > 1:
                if len(tx_hashes) % 2 != 0:
                    tx_hashes.append(tx_hashes[-1])  # Duplicate last hash if odd number

                new_level = []
                for i in range(0, len(tx_hashes), 2):
                    combined = tx_hashes[i] + tx_hashes[i + 1]  # Concatenate bytes
                    new_hash = Hashing.hash(combined)  # Hash the combined bytes
                    new_level.append(new_hash)

                tx_hashes = new_level  # Move to next Merkle tree level

            # ✅ Final Merkle Root (Always bytes)
            merkle_root = tx_hashes[0]
            print(f"[Block._compute_merkle_root] ✅ SUCCESS: Merkle Root computed: {merkle_root.hex()}")
            return merkle_root

        except Exception as e:
            print(f"[Block._compute_merkle_root] ❌ ERROR: Merkle root computation failed: {e}")
            return Hashing.hash(Constants.ZERO_HASH.encode())  # Return ZERO_HASH on failure




    def calculate_hash(self) -> bytes:
        """
        Calculate the block's hash using single SHA3-384.
        """
        # Convert version to integer if it's a string
        version_int = int(float(self.version) * 100)  # Convert "1.00" to 100

        # Ensure previous_hash is bytes
        previous_hash_bytes = (
            bytes.fromhex(self.previous_hash) if isinstance(self.previous_hash, str)
            else self.previous_hash
        )

        # Ensure merkle_root is bytes
        merkle_root_bytes = (
            bytes.fromhex(self.merkle_root) if isinstance(self.merkle_root, str)
            else self.merkle_root
        )

        # Ensure difficulty is bytes
        difficulty_bytes = (
            bytes.fromhex(self.difficulty) if isinstance(self.difficulty, str)
            else self.difficulty
        )

        # Ensure miner_address is bytes
        miner_address_bytes = (
            self.miner_address if isinstance(self.miner_address, bytes)
            else self.miner_address.encode('utf-8')  # Only encode if it's a string
        )

        # Convert all fields to bytes
        header_bytes = (
            version_int.to_bytes(4, 'big') +  # ✅ Convert version to bytes
            self.index.to_bytes(8, 'big') +
            previous_hash_bytes +  # ✅ Use bytes directly
            merkle_root_bytes +  # ✅ Use bytes directly
            self.timestamp.to_bytes(8, 'big') +
            self.nonce.to_bytes(8, 'big') +
            difficulty_bytes +  # ✅ Use bytes directly
            miner_address_bytes  # ✅ Use bytes directly
        )

        return Hashing.hash(header_bytes)  # ✅ Return bytes directly (no .hex())


    def get_header(self) -> dict:
        """
        Returns a dictionary of the block header fields, i.e. the data
        that would typically be hashed for Proof-of-Work.
        """
        print("[Block.get_header] Returning header fields as a dictionary.")
        return {
            "version": self.version,
            "index": self.index,
            "previous_hash": self.previous_hash.hex() if isinstance(self.previous_hash, bytes) else self.previous_hash,
            "merkle_root": self.merkle_root.hex() if isinstance(self.merkle_root, bytes) else self.merkle_root,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "difficulty": self.difficulty.hex() if isinstance(self.difficulty, bytes) else self.difficulty,
            "miner_address": self.miner_address.hex() if isinstance(self.miner_address, bytes) else self.miner_address
        }

    @classmethod
    def from_bytes(cls, block_bytes):
        """Deserialize a block from bytes, ensuring all fields are converted properly."""
        print("[Block.from_bytes] Deserializing block from bytes.")
        data = Deserializer().deserialize(block_bytes)

        # Convert hex fields back to bytes where needed
        data["previous_hash"] = bytes.fromhex(data["previous_hash"]) if isinstance(data["previous_hash"], str) else data["previous_hash"]
        data["merkle_root"] = bytes.fromhex(data["merkle_root"]) if isinstance(data["merkle_root"], str) else data["merkle_root"]
        data["difficulty"] = bytes.fromhex(data["difficulty"]) if isinstance(data["difficulty"], str) else data["difficulty"]
        data["miner_address"] = bytes.fromhex(data["miner_address"]) if isinstance(data["miner_address"], str) else data["miner_address"]

        return cls.from_dict(data)

    def to_dict(self) -> dict:
        """
        Serialize block to a dictionary with standardized field formatting.
        Converts bytes objects to hex strings for JSON serialization.
        """
        print("[Block.to_dict] INFO: Serializing block to dictionary.")

        return {
            "header": {
                "version": self.version,
                "index": self.index,
                "previous_hash": self.previous_hash.hex() if isinstance(self.previous_hash, bytes) else self.previous_hash,
                "merkle_root": self.merkle_root.hex() if isinstance(self.merkle_root, bytes) else self.merkle_root,
                "timestamp": self.timestamp,
                "nonce": self.nonce,
                "difficulty": self.difficulty.hex() if isinstance(self.difficulty, bytes) else self.difficulty,
                "miner_address": self.miner_address.hex() if isinstance(self.miner_address, bytes) else self.miner_address,
                "transaction_signature": self.transaction_signature.hex() if hasattr(self, "transaction_signature") and isinstance(self.transaction_signature, bytes) else "00" * 48,
                "reward": str(getattr(self, "reward", 0)),  # Convert reward to string for safe JSON serialization
                "fees": str(getattr(self, "fees", 0)),  # Convert fees to string for precision
            },
            "transactions": [
                tx.to_dict() if hasattr(tx, "to_dict") else tx for tx in self.transactions
            ],
            "tx_id": self.tx_id.hex() if isinstance(self.tx_id, bytes) else self.tx_id,
            "hash": self.hash.hex() if self.hash else None  # Convert bytes to hex string if hash exists
        }



    @classmethod
    def from_dict(cls, data: dict) -> "Block":
        """
        Deserialize a block from a dictionary, ensuring proper type conversions and safety checks.
        """
        print("[Block.from_dict] Reconstructing block from dict.")

        # ✅ Validate required fields
        required_fields = ["index", "previous_hash", "transactions", "timestamp", "nonce", "difficulty", "miner_address"]
        if "header" not in data:
            raise ValueError("[Block.from_dict] ERROR: 'header' section missing in input data.")

        for field in required_fields:
            if field not in data["header"]:
                raise ValueError(f"[Block.from_dict] ERROR: Missing required field '{field}' in 'header'.")

        # ✅ Convert difficulty back to bytes from hex (handle if it's already bytes)
        difficulty_bytes = bytes.fromhex(data["header"]["difficulty"]) if isinstance(data["header"]["difficulty"], str) else data["header"]["difficulty"]

        # ✅ Ensure previous_hash and merkle_root are properly decoded from hex
        previous_hash_bytes = bytes.fromhex(data["header"]["previous_hash"]) if isinstance(data["header"]["previous_hash"], str) else data["header"]["previous_hash"]
        merkle_root_bytes = bytes.fromhex(data["header"]["merkle_root"]) if isinstance(data["header"]["merkle_root"], str) else data["header"]["merkle_root"]

        # ✅ Ensure miner address is properly encoded
        miner_address_str = data["header"]["miner_address"]
        miner_address_bytes = bytes.fromhex(miner_address_str) if isinstance(miner_address_str, str) else miner_address_str

        # ✅ Rebuild transaction objects safely
        rebuilt_transactions = []
        for tx_data in data.get("transactions", []):
            if not isinstance(tx_data, dict):
                raise TypeError(f"[Block.from_dict] ERROR: Transaction must be a dict, got {type(tx_data)}.")
            tx_type = tx_data.get("type", "STANDARD").upper()
            if tx_type == "COINBASE":
                from Zyiron_Chain.transactions.coinbase import CoinbaseTx
                rebuilt_transactions.append(CoinbaseTx.from_dict(tx_data))
            else:
                from Zyiron_Chain.transactions.tx import Transaction
                rebuilt_transactions.append(Transaction.from_dict(tx_data))

        # ✅ Construct Block object with properly formatted fields
        block = cls(
            index=data["header"]["index"],
            previous_hash=previous_hash_bytes,
            transactions=rebuilt_transactions,
            timestamp=data["header"]["timestamp"],
            nonce=data["header"]["nonce"],
            difficulty=difficulty_bytes,
            miner_address=miner_address_bytes
        )

        # ✅ Assign optional fields with proper conversion
        block.tx_id = data.get("tx_id")
        block.transaction_signature = bytes.fromhex(data["header"].get("transaction_signature", "00" * 48))
        block.reward = Decimal(str(data["header"].get("reward", "0")))  # Convert to Decimal for precision
        block.fees = Decimal(str(data["header"].get("fees", "0")))  # Convert to Decimal for safe handling
        block.version = data["header"].get("version", "1.00")  # Default version

        # ✅ Preserve hash if already mined; otherwise, compute it
        block.hash = bytes.fromhex(data.get("hash")) if data.get("hash") else block.calculate_hash()

        print(f"[Block.from_dict] Block #{block.index} reconstructed successfully.")
        return block

    def __repr__(self) -> str:
        """
        String representation for debugging.
        """
        return (
            f"<Block index={self.index} hash={self.hash.hex()[:10] + '...'} "
            f"prev={self.previous_hash.hex()[:10] + '...'} "
            f"merkle={self.merkle_root.hex()[:10] + '...'} "
            f"tx_count={len(self.transactions)}>"
        )

    def _get_coinbase_tx_id(self) -> Optional[str]:
        """
        Retrieves the `tx_id` of the Coinbase transaction, if present.
        """
        print("[Block._get_coinbase_tx_id] Searching for Coinbase TX.")
        for tx in self.transactions:
            if hasattr(tx, "tx_type") and tx.tx_type.upper() == "COINBASE":
                print(f"[Block._get_coinbase_tx_id] Found Coinbase TX with ID: {tx.tx_id}")
                return tx.tx_id  # Get `tx_id` from the Coinbase transaction
        print("[Block._get_coinbase_tx_id] No Coinbase TX found.")
        return None  # If no Coinbase TX exists
