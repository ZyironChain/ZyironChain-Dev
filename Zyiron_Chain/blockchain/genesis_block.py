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

            # ✅ **Check if Genesis Coinbase TX already exists**
            stored_tx_id = self.block_metadata.get_transaction_id("GENESIS_COINBASE")
            if stored_tx_id:
                print(f"[GenesisBlockManager.create_and_mine_genesis_block] INFO: Genesis Coinbase TX already exists with TX ID: {stored_tx_id}")

                # ✅ **Instead of returning `None`, LOAD the existing Genesis block**
                stored_genesis_block = self.block_metadata.get_block_by_tx_id(stored_tx_id)
                if stored_genesis_block:
                    print(f"[GenesisBlockManager.create_and_mine_genesis_block] SUCCESS: Loaded existing Genesis block with hash: {stored_genesis_block.hash}")
                    return stored_genesis_block  # ✅ Return the existing Genesis block

                print("[GenesisBlockManager.create_and_mine_genesis_block] WARNING: Stored Genesis TX exists but block not found, proceeding to mine again.")

            # ✅ **Create New Coinbase Transaction**
            coinbase_tx = CoinbaseTx(
                block_height=0,
                miner_address=miner_address,
                reward=Decimal(Constants.INITIAL_COINBASE_REWARD)
            )
            coinbase_tx.fee = Decimal("0")
            print(f"[GenesisBlockManager.create_and_mine_genesis_block] INFO: New Coinbase transaction created for miner: {miner_address}")

            # ✅ **Initialize Genesis Block**
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

            # ✅ **Mine Until Difficulty Target is Met**
            while True:
                genesis_block.nonce += 1
                computed_hash = Hashing.hash(genesis_block.calculate_hash().encode()).hex()
                if int(computed_hash, 16) < Constants.GENESIS_TARGET:
                    genesis_block.hash = computed_hash
                    break

                # ✅ **Display Live Mining Status Every 2 Seconds**
                current_time = time.time()
                if current_time - last_update >= 2:
                    elapsed = int(current_time - start_time)
                    print(f"[GenesisBlockManager.create_and_mine_genesis_block] LIVE: Nonce: {genesis_block.nonce}, Elapsed Time: {elapsed}s")
                    last_update = current_time

            # ✅ **Genesis Block Mined Successfully**
            print(f"Block {genesis_block.index} mined successfully with Nonce value of {genesis_block.nonce}")
            print(f"[GenesisBlockManager.create_and_mine_genesis_block] SUCCESS: Genesis Block mined with hash: {genesis_block.hash}")

            # ✅ **Store Genesis Transaction ID**
            with self.block_metadata.block_metadata_db.env.begin(write=True) as txn:
                txn.put(b"GENESIS_COINBASE", coinbase_tx.tx_id.encode("utf-8"))
            print(f"[GenesisBlockManager.create_and_mine_genesis_block] SUCCESS: Stored Genesis Coinbase TX ID: {coinbase_tx.tx_id}")

            return genesis_block

        except Exception as e:
            print(f"[GenesisBlockManager.create_and_mine_genesis_block] ERROR: Genesis block mining failed: {e}")
            raise



    def ensure_genesis_block(self):
        """
        Ensures the Genesis block exists in storage.
        - First tries to retrieve by block hash.
        - If missing, attempts retrieval by the Genesis Coinbase transaction ID (`tx_id`).
        - Only mines a new Genesis block if both lookups fail.
        """
        try:
            print("[GenesisBlockManager.ensure_genesis_block] INFO: Checking for existing Genesis block...")

            # 🔹 First, try retrieving by Block Hash (Correct Approach)
            stored_blocks = self.block_metadata.get_all_blocks()
            if stored_blocks:
                genesis_data = stored_blocks[0]
                if "hash" in genesis_data:
                    print(f"[GenesisBlockManager.ensure_genesis_block] INFO: Using stored Genesis Block with hash: {genesis_data['hash']}")
                    return Block.from_dict(genesis_data)

            # 🔹 If no block found, try retrieving by Coinbase Transaction ID (Genesis Only)
            stored_tx_id = self.block_metadata.get_transaction_id("GENESIS_COINBASE")
            if stored_tx_id:
                print(f"[GenesisBlockManager.ensure_genesis_block] INFO: Using stored Coinbase TX ID: {stored_tx_id}")
                stored_genesis_block = self.block_metadata.get_block_by_tx_id(stored_tx_id)  # ✅ Fallback
                if stored_genesis_block:
                    print(f"[GenesisBlockManager.ensure_genesis_block] SUCCESS: Loaded Genesis block with hash: {stored_genesis_block.hash}")
                    return stored_genesis_block

            print("[GenesisBlockManager.ensure_genesis_block] WARNING: No valid Genesis block found, proceeding to mine a new one...")
            genesis_block = self.create_and_mine_genesis_block()

            # ✅ Store Genesis Block
            print("[GenesisBlockManager.ensure_genesis_block] INFO: Storing Genesis block in BlockMetadata...")
            self.block_metadata.store_block(genesis_block, genesis_block.difficulty)

            print("[GenesisBlockManager.ensure_genesis_block] INFO: Storing Genesis block in BlockStorage...")
            self.block_storage.store_block(genesis_block, genesis_block.difficulty)

            print(f"[GenesisBlockManager.ensure_genesis_block] SUCCESS: New Genesis block created with hash: {genesis_block.hash}")
            return genesis_block

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
        - Ensures that the Coinbase transaction exists and is valid.
        - Validates that the Merkle root is correctly derived.
        """
        try:
            print("[GenesisBlockManager.validate_genesis_block] INFO: Validating Genesis block integrity...")

            # ✅ **Check Index**
            if genesis_block.index != 0:
                raise ValueError(f"[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block index must be 0, found {genesis_block.index}.")

            # ✅ **Check Previous Hash**
            if genesis_block.previous_hash != Constants.ZERO_HASH:
                raise ValueError("[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block has an invalid previous hash.")

            # ✅ **Ensure Block Hash is a Valid Hex String**
            if not isinstance(genesis_block.hash, str) or not all(c in "0123456789abcdefABCDEF" for c in genesis_block.hash):
                raise ValueError("[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block hash is not a valid hex string.")

            # ✅ **Check Difficulty Target Compliance**
            if int(genesis_block.hash, 16) >= genesis_block.difficulty:
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block hash does not meet difficulty target.\n"
                    f"Expected Target: {hex(genesis_block.difficulty)}\n"
                    f"Found: {genesis_block.hash}"
                )

            # ✅ **Ensure Coinbase Transaction Exists**
            if not genesis_block.transactions or len(genesis_block.transactions) == 0:
                raise ValueError("[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block must contain a Coinbase transaction.")

            coinbase_tx = genesis_block.transactions[0]
            if not hasattr(coinbase_tx, "tx_id") or not isinstance(coinbase_tx.tx_id, str):
                raise ValueError("[GenesisBlockManager.validate_genesis_block] ERROR: Coinbase transaction must have a valid `tx_id`.")

            # ✅ **Ensure Coinbase TX ID is Correct**
            expected_tx_id = Hashing.hash(json.dumps(coinbase_tx.to_dict(), sort_keys=True).encode()).hex()
            if coinbase_tx.tx_id != expected_tx_id:
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Coinbase transaction TX ID mismatch.\n"
                    f"Expected: {expected_tx_id}\n"
                    f"Found: {coinbase_tx.tx_id}"
                )

            # ✅ **Verify Merkle Root Integrity**
            expected_merkle_root = genesis_block._compute_merkle_root()
            if genesis_block.merkle_root != expected_merkle_root:
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Merkle root does not match transaction hashes.\n"
                    f"Expected: {expected_merkle_root}\n"
                    f"Found: {genesis_block.merkle_root}"
                )

            print("[GenesisBlockManager.validate_genesis_block] SUCCESS: Genesis block validated successfully.")
            return True

        except Exception as e:
            print(f"[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block validation failed: {e}")
            return False
