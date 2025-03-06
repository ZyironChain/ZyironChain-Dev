#!/usr/bin/env python3
"""
GenesisBlockManager Class

- Manages the creation, mining, and validation of the Genesis block.
- Processes all data as bytes using single SHA3-384 hashing.
- Uses constants from Constants.
- Sends the mined Genesis block to the correct storage databases.
- Provides detailed print statements for debugging.
"""

import sys
import os
import json
import time
import hashlib
from decimal import Decimal

# Adjust Python path for project structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.coinbase import CoinbaseTx
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.utils.deserializer import Deserializer
from Zyiron_Chain.storage.block_storage import WholeBlockData
from Zyiron_Chain.storage.blockmetadata import BlockMetadata
from Zyiron_Chain.keys.key_manager import KeyManager

class GenesisBlockManager:
    """
    Manages the creation, mining, and validation of the Genesis block.
    
    - Processes all data as bytes.
    - Uses only single SHA3-384 hashing via Hashing.hash().
    - Utilizes Constants for defaults.
    - Provides detailed print statements for debugging.
    - Sends the Genesis block to the correct storage modules.
    """
    GENESIS_HASH = None  # Optionally set a predefined genesis hash (hex string) to bypass mining

    def __init__(self, block_storage: WholeBlockData, block_metadata: BlockMetadata, key_manager: KeyManager, chain, block_manager):
        self.block_storage = block_storage
        self.block_metadata = block_metadata
        self.key_manager = key_manager
        self.chain = chain
        self.block_manager = block_manager
        self.network = Constants.NETWORK
        print(f"[GenesisBlockManager.__init__] Initialized for network: {self.network}")

    def create_and_mine_genesis_block(self) -> Block:
        """
        Creates and mines the Genesis block using single SHA3-384 hashing.
        - Uses a Coinbase transaction.
        - Mines until the computed hash is lower than Constants.GENESIS_TARGET.
        - Returns the mined Genesis block.
        """
        try:
            print("[GenesisBlockManager.create_and_mine_genesis_block] INFO: Starting Genesis block mining...")

            miner_address = self.key_manager.get_default_public_key(self.network, "miner")
            if not miner_address:
                raise ValueError("[GenesisBlockManager.create_and_mine_genesis_block] ERROR: Failed to retrieve miner address for Genesis block.")

            # Create Coinbase Transaction for block reward
            coinbase_tx = CoinbaseTx(
                block_height=0,
                miner_address=miner_address,
                reward=Decimal(Constants.INITIAL_COINBASE_REWARD)
            )
            coinbase_tx.fee = Decimal("0")
            print(f"[GenesisBlockManager.create_and_mine_genesis_block] INFO: Coinbase transaction created for miner: {miner_address}")

            # Initialize Genesis Block
            genesis_block = Block(
                index=0,
                previous_hash=Constants.ZERO_HASH,
                transactions=[coinbase_tx],
                timestamp=int(time.time()),
                nonce=0,
                difficulty=Constants.GENESIS_TARGET,
                miner_address=miner_address
            )
            print(f"[GenesisBlockManager.create_and_mine_genesis_block] INFO: Genesis Block initialized with nonce: {genesis_block.nonce}")

            start_time = time.time()
            last_update = start_time

            # Mine the genesis block by incrementing the nonce until hash meets target
            while True:
                genesis_block.nonce += 1
                computed_hash = Hashing.hash(genesis_block.calculate_hash().encode()).hex()
                # Check if the computed hash is less than the target (as integer)
                if int(computed_hash, 16) < Constants.GENESIS_TARGET:
                    genesis_block.hash = computed_hash
                    break

                current_time = time.time()
                if current_time - last_update >= 2:
                    elapsed = int(current_time - start_time)
                    print(f"[GenesisBlockManager.create_and_mine_genesis_block] LIVE: Nonce: {genesis_block.nonce}, Elapsed Time: {elapsed}s")
                    last_update = current_time

            # Add the new print statement here
            print(f"Block {genesis_block.index} mined successfully with Nonce value of {genesis_block.nonce}")

            print(f"[GenesisBlockManager.create_and_mine_genesis_block] SUCCESS: Genesis Block mined with hash: {genesis_block.hash}")
            return genesis_block

        except Exception as e:
            print(f"[GenesisBlockManager.create_and_mine_genesis_block] ERROR: Genesis block mining failed: {e}")
            raise


    def ensure_genesis_block(self):
        try:
            stored_blocks = self.block_metadata.get_all_blocks()
            if stored_blocks:
                genesis_data = Deserializer().deserialize(stored_blocks[0])  # 🔹 Auto-deserialize data

                header = genesis_data.get("header", {})
                if not isinstance(header, dict):
                    raise ValueError("[GenesisBlockManager.ensure_genesis_block] ERROR: Genesis block header is not a dictionary.")
                if header.get("index", -1) != 0 or header.get("previous_hash") != Constants.ZERO_HASH:
                    raise ValueError("[GenesisBlockManager.ensure_genesis_block] ERROR: Corrupted Genesis block found in storage.")

                genesis_block = Block.from_dict(genesis_data)

                # Ensure the genesis block hash is correctly formatted
                if not isinstance(genesis_block.hash, str):
                    genesis_block.hash = Hashing.hash(genesis_block.calculate_hash().encode()).hex()

                # Validate difficulty target by checking hash pattern (e.g., must start with "0000")
                if not genesis_block.hash.startswith("0000"):
                    raise ValueError("[GenesisBlockManager.ensure_genesis_block] ERROR: Genesis block hash does not meet difficulty requirement.")

                print(f"[GenesisBlockManager.ensure_genesis_block] SUCCESS: Genesis block loaded from storage with hash: {genesis_block.hash}")
                self.chain.append(genesis_block)
                self.block_manager.chain.append(genesis_block)
                return

            # If GENESIS_HASH is predefined, use it instead of mining
            if self.GENESIS_HASH is not None:
                print("[GenesisBlockManager.ensure_genesis_block] INFO: Using predefined GENESIS_HASH.")
                genesis_block = Block(
                    index=0,
                    previous_hash=Constants.ZERO_HASH,
                    transactions=[],  # Optionally, add a coinbase transaction if desired
                    timestamp=int(time.time()),
                    nonce=0,
                    difficulty=Constants.GENESIS_TARGET,
                    miner_address=self.key_manager.get_default_public_key(self.network, "miner")
                )
                genesis_block.hash = self.GENESIS_HASH
            else:
                genesis_block = self.create_and_mine_genesis_block()

            # Store the genesis block using the new storage modules
            self.block_metadata.store_block(genesis_block, Constants.GENESIS_TARGET)
            self.block_storage.store_block(genesis_block, Constants.GENESIS_TARGET)
            self.chain.append(genesis_block)
            self.block_manager.chain.append(genesis_block)
            print(f"[GenesisBlockManager.ensure_genesis_block] SUCCESS: New Genesis block created with hash: {genesis_block.hash}")

        except Exception as e:
            print(f"[GenesisBlockManager.ensure_genesis_block] ERROR: Genesis initialization failed: {e}")
            print("[GenesisBlockManager.ensure_genesis_block] INFO: Purging corrupted chain data...")
            self.block_metadata.purge_chain()
            raise

    def validate_genesis_block(self, genesis_block) -> bool:
        """
        Validate the Genesis block:
        - Index must be 0 and previous_hash must equal Constants.ZERO_HASH.
        - The block hash must be a valid hex string and meet the difficulty target.
        """
        try:
            if genesis_block.index != 0:
                raise ValueError(f"[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block index must be 0, found {genesis_block.index}.")
            if genesis_block.previous_hash != Constants.ZERO_HASH:
                raise ValueError("[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block has an invalid previous hash.")
            if not isinstance(genesis_block.hash, str) or not all(c in "0123456789abcdefABCDEF" for c in genesis_block.hash):
                raise ValueError("[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block hash is not a valid hex string.")
            if int(genesis_block.hash, 16) >= genesis_block.difficulty:
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block hash does not meet difficulty target.\n"
                    f"Expected Target: {hex(genesis_block.difficulty)}\n"
                    f"Found: {genesis_block.hash}"
                )
            print("[GenesisBlockManager.validate_genesis_block] SUCCESS: Genesis block validated successfully.")
            return True
        except Exception as e:
            print(f"[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block validation failed: {e}")
            return False