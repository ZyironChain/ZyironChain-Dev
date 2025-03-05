import sys
import os
import json
import time
import hashlib
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.coinbase import CoinbaseTx
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.utils.hashing import Hashing

class GenesisBlockManager:
    """
    Manages the creation, mining, ensuring, and validation of the Genesis block.
    
    - Processes all data as bytes.
    - Uses only single SHA3-384 hashing via Hashing.hash().
    - Utilizes constants from Constants.
    - Provides detailed print statements for debugging.
    - Optionally uses a predefined genesis hash via GENESIS_HASH.
    """
    GENESIS_HASH = None  # Set this to a valid hash (hex string) to bypass mining, if desired.

    def __init__(self, storage_manager, key_manager, chain, block_manager):
        self.storage_manager = storage_manager
        self.key_manager = key_manager
        self.chain = chain
        self.block_manager = block_manager
        self.network = Constants.NETWORK

    def create_and_mine_genesis_block(self):
        """
        Creates and mines the Genesis block using single SHA3-384 hashing.
        - Processes all data as bytes.
        - Ensures the hash meets Constants.GENESIS_TARGET.
        - Returns the mined Genesis block.
        """
        try:
            print("[GenesisBlockManager.create_and_mine_genesis_block] INFO: Starting Genesis Block mining...")
            
            miner_address = self.key_manager.get_default_public_key(self.network, "miner")
            if not miner_address:
                raise ValueError("[GenesisBlockManager.create_and_mine_genesis_block] ERROR: Failed to retrieve miner address for Genesis block.")

            # Create Coinbase Transaction
            coinbase_tx = CoinbaseTx(
                block_height=0,
                miner_address=miner_address,
                reward=Decimal(Constants.INITIAL_COINBASE_REWARD)
            )
            coinbase_tx.fee = Decimal("0")
            
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
            print(f"[GenesisBlockManager.create_and_mine_genesis_block] INFO: Genesis Block initialized. Starting nonce: {genesis_block.header.nonce}")
            
            start_time = time.time()
            last_update = start_time

            while True:
                # Increment nonce and recompute hash using single hashing (data in bytes)
                genesis_block.header.nonce += 1
                computed_hash = Hashing.hash(genesis_block.calculate_hash().encode()).hex()
                
                if int(computed_hash, 16) < Constants.GENESIS_TARGET:
                    genesis_block.hash = computed_hash
                    break

                current_time = time.time()
                if current_time - last_update >= 2:
                    elapsed = int(current_time - start_time)
                    print(f"[GenesisBlockManager.create_and_mine_genesis_block] LIVE: Nonce: {genesis_block.header.nonce}, Elapsed Time: {elapsed}s")
                    last_update = current_time

            print(f"[GenesisBlockManager.create_and_mine_genesis_block] SUCCESS: Genesis Block mined with hash: {genesis_block.hash}")
            return genesis_block

        except Exception as e:
            print(f"[GenesisBlockManager.create_and_mine_genesis_block] ERROR: Genesis block mining failed: {e}")
            raise

    def ensure_genesis_block(self):
        """
        Ensures the Genesis block exists in storage.
        - If a valid Genesis block exists, it is loaded.
        - If not, a new Genesis block is created (or a predefined GENESIS_HASH is used if set),
          mined, and stored.
        """
        try:
            stored_blocks = self.storage_manager.get_all_blocks()
            if stored_blocks:
                genesis_data = stored_blocks[0]
                header = genesis_data.get("header", {})
                if not isinstance(header, dict):
                    raise ValueError("[GenesisBlockManager.ensure_genesis_block] ERROR: Genesis block header is not a dictionary.")
                if header.get("index", -1) != 0 or header.get("previous_hash") != Constants.ZERO_HASH:
                    raise ValueError("[GenesisBlockManager.ensure_genesis_block] ERROR: Corrupted Genesis block found in storage.")
                
                genesis_block = Block.from_dict(genesis_data)
                if not isinstance(genesis_block.hash, str):
                    genesis_block.hash = Hashing.hash(genesis_block.calculate_hash().encode()).hex()
                if not genesis_block.hash.startswith("0000"):
                    raise ValueError("[GenesisBlockManager.ensure_genesis_block] ERROR: Genesis block hash does not meet difficulty requirement.")
                
                print(f"[GenesisBlockManager.ensure_genesis_block] SUCCESS: Genesis block loaded from storage with hash: {genesis_block.hash}")
                self.chain.append(genesis_block)
                self.block_manager.chain.append(genesis_block)
                return

            # If a GENESIS_HASH is predefined, you might choose to create a Genesis block using that value.
            if self.GENESIS_HASH is not None:
                print("[GenesisBlockManager.ensure_genesis_block] INFO: Using predefined GENESIS_HASH.")
                genesis_block = Block(
                    index=0,
                    previous_hash=Constants.ZERO_HASH,
                    transactions=[],  # You may choose to leave transactions empty or add a coinbase tx.
                    timestamp=int(time.time()),
                    nonce=0,
                    difficulty=Constants.GENESIS_TARGET,
                    miner_address=self.key_manager.get_default_public_key(self.network, "miner")
                )
                genesis_block.hash = self.GENESIS_HASH
            else:
                genesis_block = self.create_and_mine_genesis_block()

            self.storage_manager.store_block(genesis_block, Constants.GENESIS_TARGET)
            self.chain.append(genesis_block)
            self.block_manager.chain.append(genesis_block)
            print(f"[GenesisBlockManager.ensure_genesis_block] SUCCESS: New Genesis block created with hash: {genesis_block.hash}")

        except Exception as e:
            print(f"[GenesisBlockManager.ensure_genesis_block] ERROR: Genesis initialization failed: {e}")
            print("[GenesisBlockManager.ensure_genesis_block] INFO: Purging corrupted chain data...")
            self.storage_manager.purge_chain()
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
