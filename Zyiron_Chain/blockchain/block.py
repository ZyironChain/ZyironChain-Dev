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
from Zyiron_Chain.storage.lmdatabase import LMDBManager
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
from Zyiron_Chain.utils.diff_conversion import DifficultyConverter # Make sure this is imported

class Block:
    def __init__(
        self,
        index: int,
        previous_hash: Optional[str],
        transactions: List,
        timestamp: Optional[int] = None,
        nonce: int = 0,
        difficulty: Union[int, str] = None,
        miner_address: str = None,
        fees: Union[int, float, Decimal] = 0,
        version: str = Constants.VERSION
    ):
        """
        Initializes a Block object with:
        - Ensures Genesis block has `previous_hash = Constants.ZERO_HASH`
        - Uses Proof-of-Work mined hash for block linkage.
        - Ensures only valid 96-character SHA3-384 hex hashes are accepted.
        - Includes fallback logic to prevent crashes due to missing or incorrect data.
        """
        try:
            print(f"[Block.__init__] INFO: Initializing Block #{index}")

            # ✅ Handle Genesis Block Special Case
            if index == 0:
                self.previous_hash = Constants.ZERO_HASH
            else:
                if not isinstance(previous_hash, str) or len(previous_hash) != 96:
                    print(f"[Block.__init__] ⚠️ WARNING: Invalid `previous_hash` for Block {index}. Using fallback: {Constants.ZERO_HASH}")
                    self.previous_hash = Constants.ZERO_HASH
                else:
                    self.previous_hash = previous_hash

            # ✅ Validate and Convert `difficulty`
            try:
                self.difficulty = DifficultyConverter.convert(
                    difficulty if difficulty is not None else Constants.GENESIS_TARGET
                )
            except Exception as e:
                print(f"[Block.__init__] ❌ ERROR: Failed to convert difficulty for Block {index}: {e}")
                self.difficulty = DifficultyConverter.convert(Constants.GENESIS_TARGET)

            # ✅ Assign Block Properties
            self.index = int(index)
            self.transactions = transactions or []
            self.nonce = int(nonce)
            self.timestamp = int(timestamp) if timestamp else int(time.time())

            # ✅ Validate `miner_address`
            if not isinstance(miner_address, str) or not miner_address:
                print(f"[Block.__init__] ⚠️ WARNING: `miner_address` missing for Block {index}. Using UNKNOWN_MINER.")
                self.miner_address = "UNKNOWN_MINER"
            else:
                self.miner_address = miner_address[:128]

            # ✅ Convert `fees` to Decimal
            try:
                self.fees = Decimal(fees)
            except (ValueError, TypeError):
                print(f"[Block.__init__] ⚠️ WARNING: Invalid `fees` for Block {index}. Defaulting to 0.")
                self.fees = Decimal(0)

            # ✅ Compute Merkle Root
            self.merkle_root = self._compute_merkle_root()

            # ✅ Initialize mining fields
            self.hash = None
            self.mined_hash = None

            # ✅ Assign Coinbase TX ID
            self.tx_id = self._get_coinbase_tx_id()

            # ✅ Assign Version
            if not isinstance(version, str) or len(version) > 8:
                print(f"[Block.__init__] ⚠️ WARNING: Invalid `version` for Block {index}. Using default version.")
                self.version = Constants.VERSION
            else:
                self.version = version

            # ✅ Add missing `transaction_signature` field
            self.transaction_signature = Constants.ZERO_HASH  # Placeholder, update after signing if needed

            print(f"[Block.__init__] ✅ SUCCESS: Block #{self.index} initialized with version {self.version}.")

        except Exception as e:
            print(f"[Block.__init__] ❌ ERROR: Block initialization failed: {e}")
            raise


    def _compute_merkle_root(self) -> str:
        """
        Compute the Merkle root for the block's transactions using single SHA3-384 hashing.
        - If no transactions, returns a hash of ZERO_HASH.
        - Ensures all transactions are serialized before hashing.
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
                    if hasattr(tx, "to_dict"):
                        tx_serialized = json.dumps(tx.to_dict(), sort_keys=True).encode("utf-8")
                    elif isinstance(tx, dict):
                        tx_serialized = json.dumps(tx, sort_keys=True).encode("utf-8")
                    else:
                        print(f"[Block._compute_merkle_root] ❌ ERROR: Invalid transaction format: {type(tx)}")
                        return Constants.ZERO_HASH

                    # Compute SHA3-384 hash of the serialized transaction
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

                new_level = [
                    Hashing.hash((tx_hashes[i] + tx_hashes[i + 1]).encode("utf-8")).hex()
                    for i in range(0, len(tx_hashes), 2)
                ]
                tx_hashes = new_level

            return tx_hashes[0]

        except Exception as e:
            print(f"[Block._compute_merkle_root] ❌ ERROR: Merkle root computation failed: {e}")
            return Constants.ZERO_HASH
        
    def calculate_hash(self) -> str:
        """
        Calculate the block's hash using single SHA3-384.
        Ensures it does not overwrite the PoW-mined hash.
        """
        try:
            previous_hash_hex = self.previous_hash if isinstance(self.previous_hash, str) else Constants.ZERO_HASH
            merkle_root_hex = self.merkle_root if isinstance(self.merkle_root, str) else Constants.ZERO_HASH
            difficulty_hex = self.difficulty if isinstance(self.difficulty, str) else "00" * 48
            miner_address_hex = self.miner_address if isinstance(self.miner_address, str) else "00" * 128

            header_str = f"{self.index}|{previous_hash_hex}|{merkle_root_hex}|{self.timestamp}|{self.nonce}|{difficulty_hex}|{miner_address_hex}"
            pow_hash = Hashing.hash(header_str.encode("utf-8")).hex()

            # ✅ Ensure mined_hash is not overwritten after PoW completion
            if hasattr(self, "mined_hash") and self.mined_hash:
                return self.mined_hash  # ✅ Prevent recalculating PoW-mined hash

            return pow_hash

        except Exception as e:
            print(f"[Block.calculate_hash] ❌ ERROR: Failed to compute block hash: {e}")
            return Constants.ZERO_HASH




    def get_header(self) -> dict:
        """
        Returns a dictionary of the block header fields, formatted for LMDB storage.
        Ensures all fields are stored as properly formatted hex strings or default values.
        Prints which fallback values are being used for missing fields.
        """
        print(f"[Block.get_header] INFO: Retrieving block header for Block #{self.index}.")

        # ✅ Handle Missing or Invalid Fields with Fallbacks
        version = str(getattr(self, "version", "1.00"))
        index = int(getattr(self, "index", 0))
        previous_hash = str(getattr(self, "previous_hash", Constants.ZERO_HASH))
        merkle_root = str(getattr(self, "merkle_root", Constants.ZERO_HASH))
        timestamp = int(getattr(self, "timestamp", int(time.time())))
        nonce = int(getattr(self, "nonce", 0))
        miner_address = str(getattr(self, "miner_address", "00" * 128))
        transaction_signature = str(getattr(self, "transaction_signature", "00" * 48))
        reward = str(getattr(self, "reward", 0))
        fees = str(getattr(self, "fees", 0))

        # ✅ Use DifficultyConverter for consistent formatting
        try:
            raw_difficulty = getattr(self, "difficulty", Constants.GENESIS_TARGET)
            difficulty = DifficultyConverter.convert(raw_difficulty)
        except Exception as e:
            print(f"[Block.get_header] ❌ ERROR: Failed to convert difficulty: {e}. Using fallback.")
            difficulty = DifficultyConverter.convert(Constants.GENESIS_TARGET)

        # ✅ Log Fallbacks
        if getattr(self, "previous_hash", None) is None:
            print(f"[Block.get_header] ⚠️ WARNING: Previous hash missing, using {Constants.ZERO_HASH}")
        if getattr(self, "miner_address", None) is None:
            print(f"[Block.get_header] ⚠️ WARNING: Miner address missing, using default {miner_address}")
        if getattr(self, "transaction_signature", None) is None:
            print(f"[Block.get_header] ⚠️ WARNING: Transaction signature missing, using default {transaction_signature}")
        if getattr(self, "reward", None) is None:
            print(f"[Block.get_header] ⚠️ WARNING: Reward missing, using default {reward}")
        if getattr(self, "fees", None) is None:
            print(f"[Block.get_header] ⚠️ WARNING: Fees missing, using default {fees}")

        # ✅ Construct Header
        header_dict = {
            "version": version,
            "index": index,
            "previous_hash": previous_hash,
            "merkle_root": merkle_root,
            "timestamp": timestamp,
            "nonce": nonce,
            "difficulty": difficulty,
            "miner_address": miner_address,
            "transaction_signature": transaction_signature,
            "reward": reward,
            "fees": fees
        }

        print(f"[Block.get_header] ✅ SUCCESS: Retrieved block header for Block #{index}.")
        return header_dict




    def to_dict(self) -> dict:
        """
        Serialize block to a dictionary with standardized field formatting.
        Ensures all fields are converted to proper formats for LMDB storage.
        """
        print("[Block.to_dict] INFO: Serializing block to dictionary for LMDB storage.")

        try:
            # ✅ Convert difficulty safely
            try:
                difficulty = DifficultyConverter.convert(getattr(self, 'difficulty', Constants.GENESIS_TARGET))
            except Exception as e:
                print(f"[Block.to_dict] ❌ ERROR: Failed to convert difficulty: {e}")
                difficulty = DifficultyConverter.convert(Constants.GENESIS_TARGET)

            # ✅ Serialize Header Fields
            header = {
                "version": str(getattr(self, "version", Constants.VERSION)),
                "index": int(self.index),
                "previous_hash": self.previous_hash if isinstance(self.previous_hash, str) else Constants.ZERO_HASH,
                "merkle_root": self.merkle_root if isinstance(self.merkle_root, str) else Constants.ZERO_HASH,
                "timestamp": int(getattr(self, "timestamp", int(time.time()))),
                "nonce": int(getattr(self, "nonce", 0)),
                "difficulty": difficulty,
                "miner_address": self.miner_address if isinstance(self.miner_address, str) else "00" * 64,
                "transaction_signature": self.transaction_signature if isinstance(self.transaction_signature, str) else "00" * 48,
                "reward": str(getattr(self, "reward", "0")),
                "fees": str(getattr(self, "fees", "0")),
            }

            # ✅ Serialize Transactions
            transactions = []
            for tx in getattr(self, "transactions", []):
                try:
                    tx_dict = tx.to_dict() if hasattr(tx, "to_dict") else tx
                    transactions.append(tx_dict)
                except Exception as e:
                    print(f"[Block.to_dict] ERROR: Failed to serialize transaction in Block {self.index}: {e}")

            # ✅ Additional Fields
            additional_fields = {
                "hash": self.mined_hash if isinstance(self.mined_hash, str) else Constants.ZERO_HASH,
                "metadata": getattr(self, "metadata", {}),
                "size": int(getattr(self, "size", 0)),
                "network": str(getattr(self, "network", Constants.NETWORK)),
                "flags": list(getattr(self, "flags", [])),
            }

            # ✅ Final Combined Dict
            block_dict = {
                "header": header,
                "transactions": transactions,
                **additional_fields,
            }

            print(f"[Block.to_dict] ✅ SUCCESS: Block #{self.index} serialized successfully.")
            return block_dict

        except Exception as e:
            print(f"[Block.to_dict] ❌ ERROR: Failed to serialize Block #{self.index}: {e}")
            raise




    @classmethod
    def from_dict(cls, data: dict) -> Optional["Block"]:
        """
        Deserialize a block from a dictionary, ensuring proper type conversions and safety checks.
        - Ensures missing fields have fallbacks.
        - Converts transaction dictionaries into proper transaction objects.
        - Parses difficulty consistently with DifficultyConverter.
        - Validates block hash format.
        """
        try:
            print("[Block.from_dict] INFO: Reconstructing block from dict...")

            header = data.get("header", data)

            required_fields = {
                "index", "previous_hash", "merkle_root",
                "timestamp", "nonce", "difficulty", "miner_address"
            }

            missing_fields = required_fields - set(header.keys())
            if missing_fields:
                print(f"[Block.from_dict] WARNING: Missing required fields: {missing_fields}. Applying fallback values.")

            block_index = int(header.get("index", data.get("block_height", 0)))
            previous_hash = str(header.get("previous_hash", Constants.ZERO_HASH))
            merkle_root = str(header.get("merkle_root", Constants.ZERO_HASH))
            timestamp = int(header.get("timestamp", int(time.time())))
            nonce = int(header.get("nonce", 0))
            miner_address = str(header.get("miner_address", "UNKNOWN_MINER"))

            # ✅ Use DifficultyConverter for consistency
            try:
                difficulty_raw = header.get("difficulty", Constants.GENESIS_TARGET)
                difficulty = DifficultyConverter.convert(difficulty_raw)
            except Exception as e:
                print(f"[Block.from_dict] ❌ ERROR: Failed to parse difficulty: {e}. Using fallback.")
                difficulty = DifficultyConverter.convert(Constants.GENESIS_TARGET)

            # ✅ Validate and normalize stored hash
            stored_hash = data.get("hash", Constants.ZERO_HASH)
            if isinstance(stored_hash, bytes):
                stored_hash = stored_hash.hex()
            elif isinstance(stored_hash, str):
                stored_hash = stored_hash.lower().strip()
            else:
                print(f"[Block.from_dict] ERROR: Invalid block hash type: {type(stored_hash)}")
                return None

            if len(stored_hash) != 96 or not all(c in "0123456789abcdef" for c in stored_hash):
                print(f"[Block.from_dict] ERROR: Invalid block hash format. Got: {stored_hash}")
                return None

            # ✅ Deserialize Transactions
            transactions = []
            for tx_data in data.get("transactions", []):
                try:
                    if isinstance(tx_data, dict):
                        if tx_data.get("type") == "COINBASE":
                            from Zyiron_Chain.transactions.coinbase import CoinbaseTx
                            tx = CoinbaseTx.from_dict(tx_data)
                        else:
                            from Zyiron_Chain.transactions.tx import Transaction
                            tx = Transaction.from_dict(tx_data)
                        if tx:
                            transactions.append(tx)
                    elif hasattr(tx_data, "to_dict"):
                        transactions.append(tx_data)
                    else:
                        print(f"[Block.from_dict] ERROR: Invalid transaction format in Block {block_index}: {type(tx_data)}")
                        return None
                except Exception as e:
                    print(f"[Block.from_dict] ERROR: Failed to parse transaction in Block {block_index}: {e}")
                    return None

            has_coinbase = any(
                (isinstance(tx, dict) and tx.get("type") == "COINBASE") or
                (hasattr(tx, "type") and getattr(tx, "type") == "COINBASE")
                for tx in transactions
            )
            if not has_coinbase:
                print(f"[Block.from_dict] ERROR: Block {block_index} is missing a valid Coinbase transaction!")
                return None

            # ✅ Construct the block
            block = cls(
                index=block_index,
                previous_hash=previous_hash,
                transactions=transactions,
                timestamp=timestamp,
                nonce=nonce,
                difficulty=difficulty,
                miner_address=miner_address
            )

            block.mined_hash = stored_hash
            block.hash = stored_hash

            print(f"[Block.from_dict] ✅ SUCCESS: Block #{block.index} reconstructed with stored hash: {block.hash}")
            return block

        except Exception as e:
            print(f"[Block.from_dict] ❌ ERROR: Failed to deserialize block: {e}. Skipping block.")
            return None




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



    @staticmethod
    def standardize_hash(hash_input: Union[str, bytes, int]) -> str:
        """
        Standardizes a hash value into a 96-character lowercase hex string.
        
        Args:
            hash_input (Union[str, bytes, int]): The hash input to format.
            
        Returns:
            str: A 96-character lowercase hex string.
        
        Raises:
            ValueError: If the input cannot be standardized.
        """
        try:
            if isinstance(hash_input, bytes):
                hex_str = hash_input.hex()
            elif isinstance(hash_input, int):
                hex_str = f"{hash_input:x}"
            elif isinstance(hash_input, str):
                hex_str = hash_input.lower().strip()
                if hex_str.startswith("0x"):
                    hex_str = hex_str[2:]
            else:
                raise ValueError("Unsupported type for hash conversion")

            # Validate and pad
            if len(hex_str) > 96:
                raise ValueError("Hash exceeds 96 characters")
            return hex_str.zfill(96)

        except Exception as e:
            print(f"[Block.standardize_hash] ❌ ERROR: Failed to standardize hash: {e}")
            raise
