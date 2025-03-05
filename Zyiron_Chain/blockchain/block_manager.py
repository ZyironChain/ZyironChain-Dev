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
            f"Difficulty {hex(self.difficulty_target)}."
        )

    def validate_block(self, block) -> bool:
        """
        Validate a block before adding it to the blockchain.
        Checks:
         - Consistency with previous block.
         - Block size does not exceed the maximum limit.
         - Proof-of-Work requirements are met.
         - Timestamp is within allowed drift.
         - All transactions meet confirmation requirements using single SHA3-384 hashing.
        """
        print(f"[BlockManager.validate_block] INFO: Validating Block {block.index}...")

        try:
            # Check previous hash linkage by fetching last block from block_metadata
            last_block = self.block_storage.get_latest_block()
            if last_block and block.previous_hash != last_block.hash:
                raise ValueError(
                    f"Block {block.index} previous hash mismatch: "
                    f"Expected {last_block.hash}, Got {block.previous_hash}"
                )

            # Validate block size
            block_serialized = json.dumps(block.to_dict()).encode("utf-8")
            block_size = sys.getsizeof(block_serialized)
            if block_size > Constants.MAX_BLOCK_SIZE_BYTES:
                raise ValueError(
                    f"Block {block.index} exceeds max block size: {block_size} bytes."
                )

            # Validate Proof-of-Work via the blockchain's method
            if not self.blockchain.validate_proof_of_work(block):
                raise ValueError(
                    f"Block {block.index} does not meet Proof-of-Work requirements."
                )

            # Validate timestamp to avoid future-dated blocks
            current_time = time.time()
            if not (
                current_time - Constants.MAX_TIME_DRIFT
                <= block.timestamp
                <= current_time + Constants.MAX_TIME_DRIFT
            ):
                raise ValueError(
                    f"Block {block.index} timestamp invalid (Possible future block)."
                )

            # Validate all transactions in the block
            for tx in block.transactions:
                # Ensure tx_id is a string before encoding
                if isinstance(tx.tx_id, bytes):
                    tx.tx_id = tx.tx_id.decode("utf-8")

                # Hash the transaction ID using single SHA3-384 hashing
                single_hashed_tx_id = Hashing.hash(tx.tx_id.encode()).hex()
                tx_type = PaymentTypeManager().get_transaction_type(single_hashed_tx_id)

                # Retrieve required confirmations from constants
                required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                    tx_type.name.upper(), 
                    Constants.TRANSACTION_CONFIRMATIONS["STANDARD"]
                )

                # Retrieve confirmations from tx_storage
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
            for attr in ["transactions", "previous_hash", "hash", "header"]:
                if not hasattr(current_block, attr):
                    print(
                        f"[BlockManager.validate_chain] ERROR: Block {i} missing attribute '{attr}'. "
                        f"Possible corruption."
                    )
                    return False

            for tx in current_block.transactions:
                if not hasattr(tx, "tx_id"):
                    print(
                        f"[BlockManager.validate_chain] ERROR: "
                        f"Transaction in Block {current_block.index} missing 'tx_id'."
                    )
                    return False

                if isinstance(tx.tx_id, bytes):
                    tx.tx_id = tx.tx_id.decode("utf-8")

                single_hashed_tx_id = Hashing.hash(tx.tx_id.encode()).hex()
                tx_type = PaymentTypeManager().get_transaction_type(single_hashed_tx_id)
                required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                    tx_type.name.upper(), 
                    Constants.TRANSACTION_CONFIRMATIONS["STANDARD"]
                )

                # Use tx_storage to get confirmations
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
            if not isinstance(transactions, list):
                print("[BlockManager.calculate_merkle_root] ERROR: Transactions input must be a list.")
                return Constants.ZERO_HASH

            if not transactions:
                print("[BlockManager.calculate_merkle_root] WARNING: No transactions found. Returning ZERO_HASH.")
                return Constants.ZERO_HASH

            tx_hashes = []
            for tx in transactions:
                try:
                    to_serialize = tx.to_dict() if hasattr(tx, "to_dict") else tx
                    tx_serialized = json.dumps(to_serialize, sort_keys=True).encode()
                    tx_hash = Hashing.hash(tx_serialized)  # single hashing (bytes -> bytes)
                    tx_hashes.append(tx_hash)
                except Exception as e:
                    print(
                        f"[BlockManager.calculate_merkle_root] ERROR: "
                        f"Failed to serialize transaction. Exception: {e}."
                    )
                    return Constants.ZERO_HASH

            while len(tx_hashes) > 1:
                if len(tx_hashes) % 2 != 0:
                    tx_hashes.append(tx_hashes[-1])
                new_level = []
                for i in range(0, len(tx_hashes), 2):
                    combined = tx_hashes[i] + tx_hashes[i + 1]
                    new_hash = Hashing.hash(combined)
                    new_level.append(new_hash)
                tx_hashes = new_level

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
            # store_block is presumably in block_storage
            self.block_storage.store_block(block, block.header.difficulty)
            print(
                f"[BlockManager.send_block_information] SUCCESS: "
                f"Block {block.index} stored with difficulty {hex(block.header.difficulty)}."
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
        self.chain.append(block)
        print(
            f"[BlockManager.add_block] INFO: "
            f"Block {block.index} added. Difficulty: {hex(block.header.difficulty)}."
        )
        # Potentially adjust difficulty
        if len(self.chain) % Constants.DIFFICULTY_ADJUSTMENT_INTERVAL == 0:
            self.difficulty_target = self.adjust_difficulty()
            print(
                f"[BlockManager.add_block] INFO: Difficulty adjusted to "
                f"{hex(self.difficulty_target)} after {len(self.chain)} blocks."
            )

    def get_latest_block(self):
        """
        Returns the last block in the in-memory chain, or prints a warning if the chain is empty.
        """
        if self.chain:
            print(f"[BlockManager.get_latest_block] INFO: Latest block is Block {self.chain[-1].index}.")
            return self.chain[-1]
        print("[BlockManager.get_latest_block] WARNING: In-memory chain is empty.")
        return None




    def get_latest_block(self):
        """Retrieve and deserialize the latest block from storage."""
        data = self.block_storage.get_latest_block()
        return Deserializer().deserialize(data) if data else None
