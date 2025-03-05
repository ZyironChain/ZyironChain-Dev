#!/usr/bin/env python3
"""
Blockchain Class

- Loads and manages the in-memory chain.
- Interacts with the new storage modules (block_storage, blockmetadata, etc.).
- Imports genesis block creation from 'genesis_block.py' if no chain is found.
- Uses only print statements (no logging).
- Single SHA3-384 hashing is assumed throughout (Block, BlockManager, etc.).
"""

import sys
import os

# Adjust Python path for project structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

import json
import time

# -------------------------------------------------------------------------
# Imports from our new splitted storage modules and block code
# -------------------------------------------------------------------------
from Zyiron_Chain.storage.block_storage import WholeBlockData
from Zyiron_Chain.storage.blockmetadata import BlockMetadata
from Zyiron_Chain.blockchain.block_manager import BlockManager
from Zyiron_Chain.blockchain. block import Block
from Zyiron_Chain.blockchain.genesis_block import GenesisBlockManager  # Hypothetical genesis block generator

# Constants might be needed for difficulty, chain name, etc.
from Zyiron_Chain.blockchain.constants import Constants


class Blockchain:
    """
    Main Blockchain class that:
      - Loads blocks from the new storage modules.
      - Creates a genesis block if none exist.
      - Maintains an in-memory list of blocks (self.chain).
      - Provides high-level methods for adding blocks, retrieving blocks, etc.
    """

    def __init__(self):
        """
        Initialize the Blockchain:
         - Set up references to the new splitted storage modules (block_storage, blockmetadata).
         - Load existing chain from storage. If none found, create a genesis block.
         - Initialize a BlockManager to handle advanced block tasks (like difficulty).
        """
        print("[Blockchain.__init__] Initializing Blockchain...")

        # Storage modules for blocks and metadata
        self.block_storage = WholeBlockData()
        self.block_metadata = BlockMetadata()

        # In-memory chain list
        self.chain = []

        # Attempt to load chain from storage
        self.load_chain_from_storage()

        # If chain is empty, create genesis block
        if not self.chain:
            print("[Blockchain.__init__] No existing blocks found. Creating Genesis block.")
            # Use GenesisBlockManager to create a new genesis block
            genesis_block = GenesisBlockManager().create_genesis_block()
            self.add_block(genesis_block, is_genesis=True)
        else:
            print(f"[Blockchain.__init__] Loaded {len(self.chain)} blocks from storage.")

        # Initialize BlockManager with references (the block manager might need the chain)
        # transaction_manager can be None or replaced if needed
        self.block_manager = BlockManager(self, self.block_storage, None)

    def load_chain_from_storage(self):
        """
        Load all blocks from block storage & metadata into self.chain.
        """
        print("[Blockchain.load_chain_from_storage] Loading chain from block storage...")

        # We rely on block_metadata to get block heights / ordering, then fetch full blocks from block_storage
        stored_blocks = self.block_metadata.get_all_block_headers()
        if not stored_blocks:
            print("[Blockchain.load_chain_from_storage] No blocks found in metadata. Possibly empty chain.")
            return

        # Sort blocks by index to rebuild chain in correct order
        sorted_by_index = sorted(stored_blocks, key=lambda b: b["index"])
        for meta in sorted_by_index:
            block_hash = meta.get("hash")
            if not block_hash:
                print(f"[Blockchain.load_chain_from_storage] WARNING: Block metadata missing 'hash' for index {meta.get('index')}. Skipping.")
                continue

            # Fetch the full block from block_storage
            block_obj = self.block_storage.load_block_by_hash(block_hash)
            if not block_obj:
                print(f"[Blockchain.load_chain_from_storage] ERROR: Could not load block data for hash {block_hash}.")
                continue

            # Rebuild the block object from dictionary
            loaded_block = Block.from_dict(block_obj)
            self.chain.append(loaded_block)

        print(f"[Blockchain.load_chain_from_storage] Finished loading. Found {len(self.chain)} blocks in total.")

    def add_block(self, new_block: Block, is_genesis=False):
        """
        Add a block to the chain (both in-memory and storage).
        If not genesis, do minimal checks like ensuring previous hash matches last block's hash.
        """
        print(f"[Blockchain.add_block] Adding Block #{new_block.index} to chain...")

        # If it's not the genesis block, ensure previous hash matches the last chain block
        if not is_genesis:
            if not self.chain:
                print("[Blockchain.add_block] ERROR: No existing chain, but block is not genesis.")
                return
            last_block = self.chain[-1]
            if new_block.previous_hash != last_block.hash:
                print("[Blockchain.add_block] ERROR: new_block.previous_hash != last_block.hash. Cannot add block.")
                return

        # Persist the block in the new splitted storage modules
        self.block_storage.store_block(new_block)
        self.block_metadata.store_block_header(new_block)  # Update metadata as well
        self.chain.append(new_block)

        print(f"[Blockchain.add_block] SUCCESS: Block #{new_block.index} added. Chain length: {len(self.chain)}")

    def get_latest_block(self) -> Block:
        """
        Return the last block in the chain, or None if empty.
        """
        if not self.chain:
            print("[Blockchain.get_latest_block] WARNING: Chain is empty.")
            return None
        return self.chain[-1]

    def validate_chain(self) -> bool:
        """
        Validate the entire chain in memory:
         - Check each block's previous_hash matches the last block's hash.
         - Optionally check difficulty, merkle root, etc. if needed.
        """
        print("[Blockchain.validate_chain] Validating entire in-memory chain...")

        if not self.chain:
            print("[Blockchain.validate_chain] Chain is empty, considered invalid or incomplete.")
            return False

        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            prev_block = self.chain[i - 1]

            # Check previous_hash link
            if current_block.previous_hash != prev_block.hash:
                print(f"[Blockchain.validate_chain] ERROR: Block #{current_block.index} previous_hash mismatch.")
                return False

            # Recalculate block hash and compare
            recalculated_hash = current_block.calculate_hash()
            if recalculated_hash != current_block.hash:
                print(f"[Blockchain.validate_chain] ERROR: Block #{current_block.index} hash mismatch. Expected {current_block.hash}, got {recalculated_hash}.")
                return False

        print("[Blockchain.validate_chain] SUCCESS: Chain is valid.")
        return True

    def get_block_by_index(self, index: int) -> Block:
        """
        Return the block at the given index from the in-memory chain or None if out of range.
        """
        for blk in self.chain:
            if blk.index == index:
                return blk
        print(f"[Blockchain.get_block_by_index] No block found at index {index}.")
        return None

    def __repr__(self):
        return f"<Blockchain length={len(self.chain)} network={Constants.NETWORK}>"

    def _get_chain_height(self) -> int:
        """
        Example helper to retrieve chain height from block metadata.
        If your blockmetadata has a different method, adjust accordingly.
        """
        try:
            # block_metadata might have a method get_highest_block_index() or similar
            # Example: highest_block = self.block_metadata.get_latest_block_header()
            all_headers = self.block_metadata.get_all_block_headers()
            if not all_headers:
                return 0
            highest_index = max(h["index"] for h in all_headers if "index" in h)
            return highest_index + 1
        except Exception as e:
            print(f"[TransactionManager._get_chain_height] ERROR: {e}")
            return 0
