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
from Zyiron_Chain. storage.block_storage import WholeBlockData
from Zyiron_Chain. storage.blockmetadata import BlockMetadata
from Zyiron_Chain. storage.tx_storage import TxStorage

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.utils.deserializer import Deserializer

class BlockManager:
    def __init__(
        self,
        blockchain,
        block_storage: WholeBlockData,
        block_metadata: BlockMetadata,
        tx_storage: TxStorage,
        transaction_manager
    ):
        """
        Initialize BlockManager with:
          - blockchain: Main Blockchain object (provides in-memory chain list).
          - block_storage: Manages the storage/retrieval of full block data (block.data).
          - block_metadata: Manages LMDB-based block metadata (headers, offsets, etc.).
          - tx_storage: Manages transaction index & confirmations from txindex.lmdb.
          - transaction_manager: Provides transaction validations.

        This replaces the old 'storage_manager' usage with the new splitted modules.
        """
        self.blockchain = blockchain
        self.block_storage = block_storage
        self.block_metadata = block_metadata
        self.tx_storage = tx_storage
        self.transaction_manager = transaction_manager

        self.chain = blockchain.chain  # In-memory chain list

        self.network = Constants.NETWORK
        self.version = Constants.VERSION
        self.difficulty_target = Constants.GENESIS_TARGET

        print(
            f"[BlockManager.__init__] INIT: "
            f"Initialized on {self.network.upper()} | "
            f"Version {self.version} | "
            f"Difficulty {self.difficulty_target.hex()}."
        )

    def validate_block(self, block) -> bool:
        """
        Validate a block before adding it to the blockchain.
        Checks:
        - Consistency with previous block.
        - Block size remains within defined min/max limits.
        - Proof-of-Work requirements are met.
        - Timestamp is within the allowed drift.
        - Transactions meet confirmation requirements using SHA3-384 hashing.
        """
        print(f"[BlockManager.validate_block] INFO: Validating Block {block.index}...")

        try:
            # ✅ **Ensure Previous Hash Matches the Last Stored Block**
            last_block = self.block_storage.get_latest_block()
            if last_block and block.previous_hash != last_block.hash:
                raise ValueError(
                    f"[BlockManager.validate_block] ERROR: Block {block.index} previous hash mismatch. "
                    f"Expected {last_block.hash}, Got {block.previous_hash}"
                )

            # ✅ **Validate Block Size Within Defined Limits**
            block_serialized = json.dumps(block.to_dict()).encode("utf-8")
            block_size = sys.getsizeof(block_serialized)

            if block_size < Constants.MIN_BLOCK_SIZE_BYTES:
                raise ValueError(
                    f"[BlockManager.validate_block] ERROR: Block {block.index} is below min block size: {block_size} bytes."
                )

            if block_size > Constants.MAX_BLOCK_SIZE_BYTES:
                raise ValueError(
                    f"[BlockManager.validate_block] ERROR: Block {block.index} exceeds max block size: {block_size} bytes."
                )

            print(f"[BlockManager.validate_block] INFO: Block {block.index} size validated: {block_size} bytes.")

            # ✅ **Validate Proof-of-Work**
            if not self.blockchain.validate_proof_of_work(block):
                raise ValueError(
                    f"[BlockManager.validate_block] ERROR: Block {block.index} does not meet Proof-of-Work requirements."
                )

            print(f"[BlockManager.validate_block] INFO: Proof-of-Work validation passed for Block {block.index}.")

            # ✅ **Validate Block Timestamp**
            current_time = time.time()
            if not (
                current_time - Constants.MAX_TIME_DRIFT
                <= block.timestamp
                <= current_time + Constants.MAX_TIME_DRIFT
            ):
                raise ValueError(
                    f"[BlockManager.validate_block] ERROR: Block {block.index} timestamp invalid (Future-dated block detected)."
                )

            print(f"[BlockManager.validate_block] INFO: Block {block.index} timestamp validated.")

            # ✅ **Validate All Transactions in the Block**
            for tx in block.transactions:
                if not hasattr(tx, "tx_id"):
                    print(f"[BlockManager.validate_block] ERROR: Transaction in Block {block.index} missing 'tx_id'.")
                    return False

                # Ensure tx_id is correctly formatted
                if isinstance(tx.tx_id, bytes):
                    tx.tx_id = tx.tx_id.decode("utf-8")

                # Compute SHA3-384 hash for transaction validation
                single_hashed_tx_id = Hashing.hash(tx.tx_id.encode()).hex()
                tx_type = PaymentTypeManager().get_transaction_type(single_hashed_tx_id)

                # Retrieve required confirmations dynamically
                required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                    tx_type.name.upper(), 
                    Constants.TRANSACTION_CONFIRMATIONS["STANDARD"]
                )

                # Retrieve actual confirmations from tx_storage
                confirmations = self.tx_storage.get_transaction_confirmations(single_hashed_tx_id)

                if confirmations is None or confirmations < required_confirmations:
                    print(
                        f"[BlockManager.validate_block] ERROR: Transaction {single_hashed_tx_id} "
                        f"in Block {block.index} does not meet required confirmations "
                        f"({required_confirmations}). Found: {confirmations}."
                    )
                    return False

            print(f"[BlockManager.validate_block] SUCCESS: Block {block.index} successfully validated.")
            return True

        except Exception as e:
            print(f"[BlockManager.validate_block] ERROR: Block validation failed: {e}")
            return False


    def validate_chain(self) -> bool:
        """
        Validate the entire blockchain for data integrity:
        - Each block's transactions meet required confirmations.
        - Correct previous_hash linkage (except for the Genesis block).
        - Block difficulty and Proof-of-Work are correct.
        - Transaction IDs validated using single SHA3-384 hashing.
        """
        print("[BlockManager.validate_chain] INFO: Starting full blockchain validation.")
        if not self.chain:
            print("[BlockManager.validate_chain] ERROR: Blockchain is empty. Cannot validate.")
            return False

        for i, current_block in enumerate(self.chain):
            print(f"[BlockManager.validate_chain] INFO: Validating Block {current_block.index}...")

            # ✅ **Ensure Block Has Required Attributes**
            for field, data in Constants.BLOCK_STORAGE_OFFSETS.items():
                if not hasattr(current_block, field):
                    print(
                        f"[BlockManager.validate_chain] ERROR: Block {i} missing required attribute '{field}'. "
                        f"Possible corruption."
                    )
                    return False

            # ✅ **Validate Previous Hash (Except for Genesis Block)**
            if i > 0:
                previous_block = self.chain[i - 1]
                if current_block.previous_hash != previous_block.hash:
                    print(
                        f"[BlockManager.validate_chain] ERROR: Block {current_block.index} previous hash mismatch. "
                        f"Expected {previous_block.hash}, Got {current_block.previous_hash}"
                    )
                    return False

            # ✅ **Validate Block Size**
            block_serialized = json.dumps(current_block.to_dict()).encode("utf-8")
            block_size = sys.getsizeof(block_serialized)

            if block_size < Constants.MIN_BLOCK_SIZE_BYTES:
                print(f"[BlockManager.validate_chain] ERROR: Block {current_block.index} below min size: {block_size} bytes.")
                return False

            if block_size > Constants.MAX_BLOCK_SIZE_BYTES:
                print(f"[BlockManager.validate_chain] ERROR: Block {current_block.index} exceeds max size: {block_size} bytes.")
                return False

            print(f"[BlockManager.validate_chain] INFO: Block {current_block.index} size validated: {block_size} bytes.")

            # ✅ **Validate Proof-of-Work**
            if not self.blockchain.validate_proof_of_work(current_block):
                print(
                    f"[BlockManager.validate_chain] ERROR: Block {current_block.index} does not meet Proof-of-Work requirements."
                )
                return False

            print(f"[BlockManager.validate_chain] INFO: Proof-of-Work validation passed for Block {current_block.index}.")

            # ✅ **Validate All Transactions in the Block**
            for tx in current_block.transactions:
                if not hasattr(tx, "tx_id"):
                    print(
                        f"[BlockManager.validate_chain] ERROR: "
                        f"Transaction in Block {current_block.index} missing 'tx_id'."
                    )
                    return False

                # Ensure tx_id is properly formatted
                if isinstance(tx.tx_id, bytes):
                    tx.tx_id = tx.tx_id.decode("utf-8")

                # Compute SHA3-384 hash for transaction validation
                single_hashed_tx_id = Hashing.hash(tx.tx_id.encode()).hex()
                tx_type = PaymentTypeManager().get_transaction_type(single_hashed_tx_id)

                # Retrieve required confirmations dynamically
                required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                    tx_type.name.upper(), 
                    Constants.TRANSACTION_CONFIRMATIONS["STANDARD"]
                )

                # Retrieve actual confirmations from tx_storage
                confirmations = self.tx_storage.get_transaction_confirmations(single_hashed_tx_id)
                if confirmations is None or confirmations < required_confirmations:
                    print(
                        f"[BlockManager.validate_chain] ERROR: Transaction {single_hashed_tx_id} "
                        f"in Block {current_block.index} does not meet required confirmations "
                        f"({required_confirmations}). Found: {confirmations}."
                    )
                    return False

        print("[BlockManager.validate_chain] SUCCESS: Blockchain validated successfully.")
        return True


    def calculate_merkle_root(self, transactions) -> str:
        """
        Compute the Merkle root using single SHA3-384 hashing.
        - Serializes each transaction to JSON bytes and hashes them.
        - Builds a pairwise tree until one root remains.
        - Returns the Merkle root as a hex string.
        """
        print("[BlockManager.calculate_merkle_root] INFO: Starting Merkle root calculation.")

        try:
            # ✅ **Ensure transactions are a valid list**
            if not isinstance(transactions, list):
                print("[BlockManager.calculate_merkle_root] ERROR: Transactions input must be a list.")
                return Constants.ZERO_HASH

            # ✅ **Handle case where no transactions are found**
            if not transactions:
                print("[BlockManager.calculate_merkle_root] WARNING: No transactions found. Returning ZERO_HASH.")
                return Constants.ZERO_HASH

            # ✅ **Serialize and hash transactions**
            tx_hashes = []
            for tx in transactions:
                try:
                    # Ensure transaction has a proper dictionary representation
                    if hasattr(tx, "to_dict"):
                        to_serialize = tx.to_dict()
                    elif isinstance(tx, dict):
                        to_serialize = tx
                    else:
                        print(f"[BlockManager.calculate_merkle_root] ERROR: Invalid transaction format: {tx}")
                        return Constants.ZERO_HASH

                    # Convert to JSON and encode to bytes
                    tx_serialized = json.dumps(to_serialize, sort_keys=True).encode()
                    tx_hash = Hashing.hash(tx_serialized)  # single hashing (bytes -> bytes)
                    tx_hashes.append(tx_hash)
                except Exception as e:
                    print(f"[BlockManager.calculate_merkle_root] ERROR: Failed to serialize transaction: {e}")
                    return Constants.ZERO_HASH

            # ✅ **Ensure all hashes are correct length (48 bytes for SHA3-384)**
            for h in tx_hashes:
                if len(h) != Constants.SHA3_384_HASH_SIZE:
                    print(f"[BlockManager.calculate_merkle_root] ERROR: Invalid transaction hash length: {len(h)}")
                    return Constants.ZERO_HASH

            # ✅ **Build Merkle Tree**
            while len(tx_hashes) > 1:
                if len(tx_hashes) % 2 != 0:
                    tx_hashes.append(tx_hashes[-1])  # Duplicate last hash if odd number

                new_level = []
                for i in range(0, len(tx_hashes), 2):
                    combined = tx_hashes[i] + tx_hashes[i + 1]
                    new_hash = Hashing.hash(combined)
                    new_level.append(new_hash)
                tx_hashes = new_level

            # ✅ **Convert final Merkle Root to hex string**
            merkle_root = tx_hashes[0].hex()
            print(f"[BlockManager.calculate_merkle_root] SUCCESS: Merkle Root computed: {merkle_root}.")
            return merkle_root

        except Exception as e:
            print(f"[BlockManager.calculate_merkle_root] ERROR: Exception while computing Merkle root: {e}.")
            return Constants.ZERO_HASH


    def send_block_information(self, block):
        """
        Stores block data using the block_storage module.
        Detailed print statements indicate the source and purpose.
        """
        try:
            print(f"[BlockManager.send_block_information] INFO: Storing Block {block.index}...")

            # ✅ Ensure difficulty remains within valid bounds
            difficulty = max(min(block.header.difficulty, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

            # ✅ Store block in block storage
            self.block_storage.store_block(block, difficulty)

            print(
                f"[BlockManager.send_block_information] SUCCESS: "
                f"Block {block.index} stored with difficulty {hex(difficulty)}."
            )

        except Exception as e:
            print(
                f"[BlockManager.send_block_information] ERROR: "
                f"Failed to store Block {block.index}. Exception: {e}."
            )
            raise

    def add_block(self, block):
        """
        Adds a validated block to the in-memory chain and triggers difficulty adjustment if needed.
        """
        try:
            print(f"[BlockManager.add_block] INFO: Adding Block {block.index}...")

            self.chain.append(block)
            print(
                f"[BlockManager.add_block] INFO: "
                f"Block {block.index} added. Difficulty: {hex(block.header.difficulty)}."
            )

            # ✅ Ensure difficulty is adjusted properly
            if len(self.chain) % Constants.DIFFICULTY_ADJUSTMENT_INTERVAL == 0:
                self.difficulty_target = max(
                    min(self.adjust_difficulty(), Constants.MAX_DIFFICULTY), 
                    Constants.MIN_DIFFICULTY
                )

                print(
                    f"[BlockManager.add_block] INFO: Difficulty adjusted to "
                    f"{hex(self.difficulty_target)} after {len(self.chain)} blocks."
                )

        except Exception as e:
            print(f"[BlockManager.add_block] ERROR: Failed to add Block {block.index}. Exception: {e}.")
            raise


    def get_latest_block(self):
        """
        Returns the last block in the in-memory chain, or retrieves it from block_metadata if empty.
        """
        try:
            if self.chain:
                print(f"[BlockManager.get_latest_block] INFO: Latest block is Block {self.chain[-1].index}.")
                return self.chain[-1]

            # ✅ Retrieve latest block from storage if in-memory chain is empty
            latest_block = self.block_metadata.get_latest_block()
            if latest_block:
                print(f"[BlockManager.get_latest_block] INFO: Retrieved latest block from storage: {latest_block['index']}.")
                return latest_block

            print("[BlockManager.get_latest_block] WARNING: No blocks found in-memory or storage.")
            return None

        except Exception as e:
            print(f"[BlockManager.get_latest_block] ERROR: Exception while retrieving latest block: {e}.")
            return None

