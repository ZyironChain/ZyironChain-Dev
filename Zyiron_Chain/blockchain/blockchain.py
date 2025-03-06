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
from typing import List, Optional
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
from Zyiron_Chain.miner.pow import PowManager


class Blockchain:
    """
    Main Blockchain class that:
      - Loads blocks from the new storage modules.
      - Creates a genesis block if none exist.
      - Maintains an in-memory list of blocks (self.chain).
      - Provides high-level methods for adding blocks, retrieving blocks, etc.
    """

    def __init__(
        self,
        block_storage=None,     # For retrieving block data if needed
        block_metadata=None,    # For retrieving block headers / ordering
        tx_storage=None,        # For checking transaction existence, storing TX data
        utxo_storage=None,      # For managing UTXOs
        wallet_index=None,      # For wallet-related operations
        transaction_manager=None,  # For transaction management
        key_manager=None        # For key management
    ):
        """
        Initialize the Blockchain.

        :param block_storage: Module handling full block storage (WholeBlockData).
        :param block_metadata: Module handling block metadata (BlockMetadata).
        :param tx_storage: Module for transaction indexing (TxStorage).
        :param utxo_storage: Module for UTXO management (UTXOStorage).
        :param wallet_index: Module for wallet-related operations (WalletStorage).
        :param transaction_manager: Module for transaction management (TransactionManager).
        :param key_manager: Module for key management (KeyManager).
        """
        print("[Blockchain.__init__] Initializing Blockchain...")

        # Storage modules for blocks and metadata
        self.block_storage = block_storage or WholeBlockData()
        self.block_metadata = block_metadata or BlockMetadata()
        self.tx_storage = tx_storage
        self.utxo_storage = utxo_storage
        self.wallet_index = wallet_index
        self.transaction_manager = transaction_manager
        self.key_manager = key_manager

        # In-memory chain list
        self.chain = []

        # Initialize PowManager for proof-of-work operations
        self.pow_manager = PowManager()

        # Attempt to load chain from storage
        self.load_chain_from_storage()

        # If chain is empty, create genesis block
        if not self.chain:
            print("[Blockchain.__init__] No existing blocks found. Creating Genesis block.")
            # Use GenesisBlockManager to create a new genesis block
            genesis_block_manager = GenesisBlockManager(
                block_storage=self.block_storage,
                block_metadata=self.block_metadata,
                key_manager=self.key_manager,
                chain=self.chain,
                block_manager=self
            )
            genesis_block = genesis_block_manager.create_and_mine_genesis_block()
            self.add_block(genesis_block, is_genesis=True)
        else:
            print(f"[Blockchain.__init__] Loaded {len(self.chain)} blocks from storage.")

    def load_chain_from_storage(self) -> None:
        """
        Load the blockchain from storage into memory.
        """
        try:
            print("[Blockchain.load_chain_from_storage] Loading chain from storage...")
            stored_blocks = self.block_metadata.get_all_blocks()
            if stored_blocks:
                for block_data in stored_blocks:
                    block = Block.from_dict(block_data)
                    self.chain.append(block)
                print(f"[Blockchain.load_chain_from_storage] Loaded {len(self.chain)} blocks from storage.")
            else:
                print("[Blockchain.load_chain_from_storage] No blocks found in storage.")
        except Exception as e:
            print(f"[Blockchain.load_chain_from_storage] ERROR: Failed to load chain from storage: {e}")

    def add_block(self, block: Block, is_genesis: bool = False) -> bool:
        """
        Add a block to the blockchain.
        - Validates the block before adding.
        - Updates storage modules.
        - Updates the in-memory chain.

        :param block: The block to add.
        :param is_genesis: Whether the block is the genesis block.
        :return: True if the block was added successfully, False otherwise.
        """
        try:
            print(f"[Blockchain.add_block] Adding Block {block.index} to the chain...")

            # Validate the block (skip validation for genesis block)
            if not is_genesis and not self.validate_block(block):
                print(f"[Blockchain.add_block] ERROR: Block {block.index} failed validation.")
                return False

            # Add block to storage via BlockMetadata (handles both metadata and block data)
            self.block_metadata.store_block(block, block.difficulty)

            # Add block to in-memory chain
            self.chain.append(block)
            print(f"[Blockchain.add_block] SUCCESS: Block {block.index} added to the chain.")
            return True
        except Exception as e:
            print(f"[Blockchain.add_block] ERROR: Failed to add Block {block.index}: {e}")
            return False

    def validate_block(self, block: Block) -> bool:
        """
        Validate a block before adding it to the blockchain.
        - Checks proof-of-work.
        - Ensures the block links to the previous block.
        - Validates all transactions in the block.

        :param block: The block to validate.
        :return: True if the block is valid, False otherwise.
        """
        try:
            print(f"[Blockchain.validate_block] Validating Block {block.index}...")

            # Check proof-of-work
            if not self.pow_manager.validate_proof_of_work(block):
                print(f"[Blockchain.validate_block] ERROR: Block {block.index} failed proof-of-work validation.")
                return False

            # Ensure the block links to the previous block
            if len(self.chain) > 0:
                last_block = self.chain[-1]
                if block.previous_hash != last_block.hash:
                    print(f"[Blockchain.validate_block] ERROR: Block {block.index} has an invalid previous hash.")
                    return False

            # Validate all transactions in the block
            for tx in block.transactions:
                if not self.transaction_manager.validate_transaction(tx):
                    print(f"[Blockchain.validate_block] ERROR: Transaction {tx.tx_id} in Block {block.index} is invalid.")
                    return False

            print(f"[Blockchain.validate_block] SUCCESS: Block {block.index} validated.")
            return True
        except Exception as e:
            print(f"[Blockchain.validate_block] ERROR: Failed to validate Block {block.index}: {e}")
            return False

    def get_latest_block(self) -> Optional[Block]:
        """
        Retrieve the latest block in the blockchain.

        :return: The latest block, or None if the chain is empty.
        """
        if self.chain:
            return self.chain[-1]
        return None

    def validate_chain(self) -> bool:
        """
        Validate the entire blockchain.
        - Ensures each block links to the previous block.
        - Validates all transactions in each block.

        :return: True if the blockchain is valid, False otherwise.
        """
        try:
            print("[Blockchain.validate_chain] Validating blockchain...")
            for i in range(1, len(self.chain)):
                current_block = self.chain[i]
                previous_block = self.chain[i - 1]

                # Check block linkage
                if current_block.previous_hash != previous_block.hash:
                    print(f"[Blockchain.validate_chain] ERROR: Block {current_block.index} has an invalid previous hash.")
                    return False

                # Validate all transactions in the block
                for tx in current_block.transactions:
                    if not self.transaction_manager.validate_transaction(tx):
                        print(f"[Blockchain.validate_chain] ERROR: Transaction {tx.tx_id} in Block {current_block.index} is invalid.")
                        return False

            print("[Blockchain.validate_chain] SUCCESS: Blockchain validated.")
            return True
        except Exception as e:
            print(f"[Blockchain.validate_chain] ERROR: Failed to validate blockchain: {e}")
            return False