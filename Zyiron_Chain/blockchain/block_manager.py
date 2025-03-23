#!/usr/bin/env python3
"""
BlockManager Class

Manages blockchain validation, difficulty adjustments, and storing block data
via the newly refactored storage modules. Provides chain-level checks such as
chain validation, Merkle root calculations, and retrieving the latest block.

- All data is processed as bytes.
- Only single SHA3-384 hashing is used.
- Detailed print statements are used for debugging and error tracking.
- References to the old 'StorageManager' have been replaced with the new split
  storage modules (block_storage, blockmetadata, tx_storage, etc.).
"""

import sys
import os
import time
import json

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

from typing import Optional

# Import splitted storage modules
from Zyiron_Chain. storage.block_storage import BlockStorage

from Zyiron_Chain. storage.tx_storage import TxStorage

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.utils.deserializer import Deserializer

from Zyiron_Chain.utils.diff_conversion import DifficultyConverter

class BlockManager:
    def __init__(
        self,
        blockchain,
        block_storage,
        block_metadata,
        tx_storage,
        transaction_manager
    ):
        """
        Initialize BlockManager with:
          - blockchain: Main Blockchain object (provides in-memory chain list).
          - block_storage: Manages the storage/retrieval of full block data.
          - block_metadata: Manages LMDB-based block metadata (headers, indexing).
          - tx_storage: Manages transaction index & confirmations.
          - transaction_manager: Handles transaction validations.

        This replaces the old 'storage_manager' usage with modularized components.
        """
        try:
            print("[BlockManager.__init__] INFO: Initializing BlockManager...")

            # ✅ Ensure essential components are initialized
            if not blockchain:
                raise ValueError("[BlockManager.__init__] ERROR: blockchain instance is required.")
            if not block_storage:
                raise ValueError("[BlockManager.__init__] ERROR: block_storage instance is required.")
            if not block_metadata:
                raise ValueError("[BlockManager.__init__] ERROR: block_metadata instance is required.")
            if not tx_storage:
                raise ValueError("[BlockManager.__init__] ERROR: tx_storage instance is required.")
            if not transaction_manager:
                raise ValueError("[BlockManager.__init__] ERROR: transaction_manager instance is required.")

            # ✅ Assign core components
            self.blockchain = blockchain
            self.block_storage = block_storage
            self.block_metadata = block_metadata
            self.tx_storage = tx_storage
            self.transaction_manager = transaction_manager

            # ✅ Initialize in-memory chain
            self.chain = blockchain.chain  # In-memory chain list

            # ✅ Network & version settings
            self.network = Constants.NETWORK
            self.version = Constants.VERSION
            self.difficulty_target = DifficultyConverter.convert(Constants.GENESIS_TARGET)

            print(
                f"[BlockManager.__init__] ✅ SUCCESS: Initialized BlockManager on {self.network.upper()} "
                f"| Version {self.version} | Difficulty {self.difficulty_target}."
            )

        except Exception as e:
            print(f"[BlockManager.__init__] ❌ ERROR: BlockManager initialization failed: {e}")
            raise


    def adjust_difficulty(self):
        """
        Adjust difficulty by deferring to the PowManager in the blockchain.
        """
        if not hasattr(self.blockchain, 'pow_manager'):
            print("[BlockManager.adjust_difficulty] ERROR: 'pow_manager' not found in blockchain. Using fallback difficulty.")
            return self.difficulty_target  # or however you want to handle it

        return self.blockchain.pow_manager.adjust_difficulty()

    def validate_proof_of_work(self, block):
        """
        Validate block's proof-of-work by deferring to the PowManager in the blockchain.
        """
        if not hasattr(self.blockchain, 'pow_manager'):
            print("[BlockManager.validate_proof_of_work] ERROR: 'pow_manager' not found in blockchain.")
            return False

        return self.blockchain.pow_manager.validate_proof_of_work(block)




    def validate_block(self, block, check_confirmations=True) -> bool:
        """
        Validate a block before adding it to the blockchain.
        Checks:
        - Consistency with previous block.
        - Block size remains within defined min/max limits.
        - Proof-of-Work requirements are met.
        - Timestamp is within the allowed drift.
        - Transactions meet confirmation requirements using SHA3-384 hashing (if enabled).
        """
        print(f"[BlockManager.validate_block] INFO: Validating Block {block.index}...")

        try:
            # ✅ Convert and normalize difficulty value first
            difficulty = DifficultyConverter.convert(block.difficulty)

            # ✅ Ensure Previous Hash Matches the Last Stored Block
            last_block = self.block_storage.get_latest_block()
            if last_block and block.previous_hash != last_block.hash:
                print(
                    f"[BlockManager.validate_block] ❌ ERROR: Block {block.index} previous hash mismatch. "
                    f"Expected {last_block.hash}, Got {block.previous_hash}"
                )
                return False

            # ✅ Validate Block Size Within Defined Limits
            block_serialized = json.dumps(block.to_dict()).encode("utf-8")
            block_size = len(block_serialized)

            if block_size < Constants.MIN_BLOCK_SIZE_MB:
                print(
                    f"[BlockManager.validate_block] ❌ ERROR: Block {block.index} below min block size: {block_size} bytes."
                )
                return False

            if block_size > Constants.MAX_BLOCK_SIZE_MB:
                print(
                    f"[BlockManager.validate_block] ❌ ERROR: Block {block.index} exceeds max block size: {block_size} bytes."
                )
                return False

            print(f"[BlockManager.validate_block] ✅ INFO: Block {block.index} size validated: {block_size} bytes.")

            # ✅ Validate Proof-of-Work
            if not self.blockchain.validate_proof_of_work(block):
                print(
                    f"[BlockManager.validate_block] ❌ ERROR: Block {block.index} does not meet Proof-of-Work requirements."
                )
                return False

            print(f"[BlockManager.validate_block] ✅ INFO: Proof-of-Work validation passed for Block {block.index}.")

            # ✅ Validate Block Timestamp
            current_time = time.time()
            if not (
                current_time - Constants.MAX_TIME_DRIFT
                <= block.timestamp
                <= current_time + Constants.MAX_TIME_DRIFT
            ):
                print(
                    f"[BlockManager.validate_block] ❌ ERROR: Block {block.index} timestamp invalid (Future-dated block detected)."
                )
                return False

            print(f"[BlockManager.validate_block] ✅ INFO: Block {block.index} timestamp validated.")

            # ✅ Optionally Validate Transaction Confirmations
            if check_confirmations:
                for tx in block.transactions:
                    if not hasattr(tx, "tx_id"):
                        print(f"[BlockManager.validate_block] ❌ ERROR: Transaction in Block {block.index} missing 'tx_id'.")
                        return False

                    # Ensure tx_id is correctly formatted
                    tx_id = tx.tx_id if isinstance(tx.tx_id, str) else tx.tx_id.decode("utf-8")

                    # Compute SHA3-384 hash for transaction validation
                    hashed_tx_id = Hashing.hash(tx_id.encode()).hex()
                    tx_type = PaymentTypeManager().get_transaction_type(hashed_tx_id)

                    # Retrieve required confirmations dynamically
                    required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                        tx_type.name.upper(), 
                        Constants.TRANSACTION_CONFIRMATIONS["STANDARD"]
                    )

                    # Retrieve actual confirmations from tx_storage
                    confirmations = self.tx_storage.get_transaction_confirmations(hashed_tx_id)

                    if confirmations is None or confirmations < required_confirmations:
                        print(
                            f"[BlockManager.validate_block] ❌ ERROR: Transaction {hashed_tx_id} "
                            f"in Block {block.index} does not meet required confirmations "
                            f"({required_confirmations}). Found: {confirmations}."
                        )
                        return False

            print(f"[BlockManager.validate_block] ✅ SUCCESS: Block {block.index} successfully validated.")
            return True

        except Exception as e:
            print(f"[BlockManager.validate_block] ❌ ERROR: Block validation failed: {e}")
            return False




    def calculate_merkle_root(self, transactions) -> str:
        """
        Compute the Merkle root using single SHA3-384 hashing.
        - Serializes each transaction to JSON and hashes them.
        - Builds a pairwise tree until one root remains.
        - Returns the Merkle root as a hex string.
        """
        print("[BlockManager.calculate_merkle_root] INFO: Starting Merkle root calculation.")

        try:
            # ✅ **Ensure transactions are a valid list**
            if not isinstance(transactions, list):
                print("[BlockManager.calculate_merkle_root] ❌ ERROR: Transactions input must be a list.")
                return Constants.ZERO_HASH

            # ✅ **Handle case where no transactions are found**
            if not transactions:
                print("[BlockManager.calculate_merkle_root] ⚠️ WARNING: No transactions found. Returning ZERO_HASH.")
                return Constants.ZERO_HASH

            # ✅ **Serialize and hash transactions**
            tx_hashes = []
            for tx in transactions:
                try:
                    # Convert transaction to a dictionary representation
                    if hasattr(tx, "to_dict"):
                        to_serialize = tx.to_dict()
                    elif isinstance(tx, dict):
                        to_serialize = tx
                    else:
                        print(f"[BlockManager.calculate_merkle_root] ❌ ERROR: Invalid transaction format: {type(tx)}")
                        continue  # Skip invalid transactions

                    # Convert to JSON and hash using SHA3-384
                    tx_serialized = json.dumps(to_serialize, sort_keys=True).encode("utf-8")
                    tx_hash = Hashing.hash(tx_serialized).hex()  # Convert hash to hex
                    tx_hashes.append(tx_hash)

                except Exception as e:
                    print(f"[BlockManager.calculate_merkle_root] ❌ ERROR: Failed to serialize transaction: {e}")
                    continue  # Skip invalid transactions

            # ✅ **Ensure transactions have been properly hashed**
            if not tx_hashes:
                print("[BlockManager.calculate_merkle_root] ❌ ERROR: No valid transactions found. Using ZERO_HASH.")
                return Constants.ZERO_HASH

            # ✅ **Build Merkle Tree**
            while len(tx_hashes) > 1:
                if len(tx_hashes) % 2 != 0:
                    tx_hashes.append(tx_hashes[-1])  # Duplicate last hash if odd number

                new_level = []
                for i in range(0, len(tx_hashes), 2):
                    combined = (tx_hashes[i] + tx_hashes[i + 1]).encode("utf-8")  # Concatenate as bytes
                    new_hash = Hashing.hash(combined).hex()  # Compute SHA3-384 hash
                    new_level.append(new_hash)

                tx_hashes = new_level  # Move to next level

            # ✅ **Final Merkle Root**
            merkle_root = tx_hashes[0] if tx_hashes else Constants.ZERO_HASH
            print(f"[BlockManager.calculate_merkle_root] ✅ SUCCESS: Merkle Root computed: {merkle_root}")
            return merkle_root

        except Exception as e:
            print(f"[BlockManager.calculate_merkle_root] ❌ ERROR: Exception while computing Merkle root: {e}")
            return Constants.ZERO_HASH


    def send_block_information(self, block):
        """
        Stores block data using the block_storage module.
        Detailed print statements indicate the source and purpose.
        """
        try:
            print(f"[BlockManager.send_block_information] INFO: Storing Block {block.index}...")

            # ✅ Validate Block Object
            if not hasattr(block, "index") or not hasattr(block, "difficulty"):
                print("[BlockManager.send_block_information] ❌ ERROR: Block object is missing required attributes.")
                return False

            # ✅ Store block in block storage without difficulty argument
            self.block_storage.store_block(block)

            print(
                f"[BlockManager.send_block_information] ✅ SUCCESS: "
                f"Block {block.index} stored successfully."
            )
            return True

        except Exception as e:
            print(
                f"[BlockManager.send_block_information] ❌ ERROR: "
                f"Failed to store Block {block.index}. Exception: {e}."
            )
            return False



    def add_block(self, block):
        """
        Adds a validated block to the in-memory chain and triggers difficulty adjustment if needed.
        Also updates the latest block index in persistent LMDB storage.

        Args:
            block (Block): The block to add to the chain.

        Returns:
            bool: True if the block was added successfully, False otherwise.
        """
        try:
            print(f"[BlockManager.add_block] INFO: Adding Block {block.index}...")

            # ✅ Ensure block object has required attributes
            required_attributes = ["index", "difficulty", "previous_hash", "hash", "timestamp", "transactions"]
            missing_attributes = [attr for attr in required_attributes if not hasattr(block, attr)]
            if missing_attributes:
                print(f"[BlockManager.add_block] ❌ ERROR: Block object missing required attributes: {missing_attributes}.")
                return False

            # ✅ Prevent duplicate or out-of-order blocks
            if self.chain:
                last_block = self.chain[-1]
                if block.index <= last_block.index:
                    print(f"[BlockManager.add_block] ⚠️ WARNING: Block {block.index} already added or out of order.")
                    return False

                # ✅ Validate block linkage
                if block.previous_hash != last_block.hash:
                    print(
                        f"[BlockManager.add_block] ❌ ERROR: Block {block.index} has incorrect previous hash. "
                        f"Expected: {last_block.hash}, Found: {block.previous_hash}."
                    )
                    return False

            # ✅ Append block to in-memory chain
            self.chain.append(block)

            # ✅ Normalize difficulty for logging
            difficulty = DifficultyConverter.convert(block.difficulty)
            print(
                f"[BlockManager.add_block] ✅ SUCCESS: "
                f"Block {block.index} added. Difficulty: {difficulty}."
            )

            # ✅ Adjust difficulty at specified intervals
            if len(self.chain) % Constants.DIFFICULTY_ADJUSTMENT_INTERVAL == 0:
                adjusted = self.adjust_difficulty()
                adjusted = max(min(adjusted, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

                self.difficulty_target = DifficultyConverter.convert(adjusted)
                print(
                    f"[BlockManager.add_block] ✅ INFO: Difficulty adjusted to "
                    f"{self.difficulty_target} after {len(self.chain)} blocks."
                )

            # ✅ Update latest block index in LMDB
            try:
                with self.block_storage.full_block_store.env.begin(write=True) as txn:
                    txn.put(b"latest_block_index", str(block.index).encode("utf-8"))
                    print(f"[BlockManager.add_block] ✅ INFO: Updated latest_block_index to {block.index}")
            except Exception as e:
                print(f"[BlockManager.add_block] ⚠️ WARNING: Failed to update latest_block_index: {e}")

            # ✅ Store block in block storage
            try:
                self.block_storage.store_block(block)
                print(f"[BlockManager.add_block] ✅ INFO: Block {block.index} stored in block storage.")
            except Exception as e:
                print(f"[BlockManager.add_block] ❌ ERROR: Failed to store Block {block.index} in block storage: {e}")
                return False

            return True

        except Exception as e:
            print(f"[BlockManager.add_block] ❌ ERROR: Failed to add Block {block.index}. Exception: {e}.")
            return False


    def get_latest_block(self):
        """
        Returns the last block in the in-memory chain, or retrieves it from block storage or metadata if empty.
        Includes fallbacks and type checks to avoid runtime errors.
        """
        try:
            # ✅ Retrieve latest block from in-memory chain
            if self.chain:
                latest_block = self.chain[-1]
                print(f"[BlockManager.get_latest_block] ✅ INFO: Latest block is Block {latest_block.index}.")
                return latest_block

            # ✅ Attempt fallback from full block storage (if available)
            if hasattr(self.block_storage, "get_latest_block"):
                block = self.block_storage.get_latest_block()
                if block:
                    print(f"[BlockManager.get_latest_block] ✅ INFO: Retrieved latest block from block storage: Block {block.index}.")
                    return block

            # ✅ Fallback: Try direct LMDB scan if block_metadata provides no method
            if hasattr(self.block_metadata, "env"):
                with self.block_metadata.env.begin() as txn:
                    cursor = txn.cursor()
                    latest_index = -1
                    latest_block = None
                    for key, value in cursor:
                        if key.startswith(b"blockmeta:"):
                            try:
                                block_meta = json.loads(value.decode("utf-8"))
                                index = block_meta.get("index", -1)
                                if index > latest_index:
                                    latest_index = index
                                    latest_block = block_meta
                            except Exception as parse_err:
                                print(f"[BlockManager.get_latest_block] ⚠️ Failed to parse metadata for key {key}: {parse_err}")
                    if latest_block:
                        print(f"[BlockManager.get_latest_block] ✅ INFO: Retrieved latest block from metadata DB: Block {latest_index}")
                        return latest_block

            print("[BlockManager.get_latest_block] ❌ WARNING: No blocks found in memory, block storage, or metadata.")
            return None

        except Exception as e:
            print(f"[BlockManager.get_latest_block] ❌ ERROR: Exception while retrieving latest block: {e}.")
            return None
