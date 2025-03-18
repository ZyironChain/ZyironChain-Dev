#!/usr/bin/env python3
"""
GenesisBlockManager Class

- Manages the creation, mining, and validation of the Genesis block.
- Processes all data as bytes using single SHA3-384 hashing.
- Uses constants from Constants.
- Sends the mined Genesis block to the correct storage databases.
- Provides detailed print statements for debugging.
"""
# run genesis_manager.print_genesis_metadata()
# run genesis_manager.print_genesis_metadata()
# run genesis_manager.print_genesis_metadata()
# run genesis_manager.print_genesis_metadata()


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
from Zyiron_Chain.storage.block_storage import BlockStorage
from Zyiron_Chain.accounts.key_manager import KeyManager

from threading import Lock

from threading import Lock

class GenesisBlockManager:
    """
    Manages the creation, mining, and validation of the Genesis block.
    
    - Uses single SHA3-384 hashing via Hashing.hash().
    - Utilizes Constants for network-specific defaults.
    - Provides detailed print statements for debugging.
    - Sends the Genesis block to the correct storage modules.
    """

    GENESIS_HASH = None  # Optionally set a predefined genesis hash to bypass mining

    def __init__(self, block_storage: BlockStorage, key_manager: KeyManager, chain, block_manager):
        """
        Initializes GenesisBlockManager, ensuring required dependencies are set.

        Args:
            block_storage (BlockStorage): The block storage handler (replacing metadata storage).
            key_manager (KeyManager): Key manager for cryptographic signing and verification.
            chain: Blockchain instance.
            block_manager: Block manager instance.
        """
        if not key_manager:
            raise ValueError("[GenesisBlockManager.__init__] ❌ ERROR: `key_manager` cannot be None.")

        # ✅ Use the new storage system (No more `block_metadata`)
        self.block_storage = block_storage
        self.key_manager = key_manager
        self.chain = chain
        self.block_manager = block_manager
        self.network = Constants.NETWORK
        self.genesis_lock = Lock()  # ✅ Thread lock to prevent multiple Genesis blocks

        print(f"[GenesisBlockManager.__init__] ✅ INFO: Initialized for network: {self.network}")


    def ensure_genesis_block(self):
        """
        Ensures the Genesis block exists in storage.
        - First checks if it's already stored.
        - If missing, attempts retrieval by the Genesis Coinbase transaction ID (`tx_id`).
        - Validates existence in LMDB.
        - Only mines a new Genesis block if all lookups fail.
        """
        with self.genesis_lock:  # ✅ Ensure thread safety
            try:
                print("[GenesisBlockManager.ensure_genesis_block] INFO: Checking for existing Genesis block...")

                # ✅ **Check if Genesis Block Exists in LMDB Storage**
                existing_genesis = self.block_storage.get_block_by_index(0)
                if existing_genesis:
                    print(f"[GenesisBlockManager.ensure_genesis_block] ✅ INFO: Genesis Block found with hash {existing_genesis.hash}")
                    return existing_genesis

                # ✅ **Check if Genesis Coinbase TX Exists in `full_block_store`**
                stored_tx_id = self.block_storage.get_transaction_id("GENESIS_COINBASE")
                if stored_tx_id:
                    print(f"[GenesisBlockManager.ensure_genesis_block] INFO: Found stored Coinbase TX ID: {stored_tx_id}")

                    stored_genesis_block = self.block_storage.get_block_by_tx_id(stored_tx_id)
                    if stored_genesis_block:
                        print(f"[GenesisBlockManager.ensure_genesis_block] ✅ SUCCESS: Loaded Genesis block from transaction index with hash: {stored_genesis_block.hash}")
                        return stored_genesis_block

                    print("[GenesisBlockManager.ensure_genesis_block] WARNING: Retrieved Genesis block is invalid or missing.")

                # 🚨 **No Valid Genesis Block Found – Proceed to Mining a New One**
                print("[GenesisBlockManager.ensure_genesis_block] ⚠️ WARNING: No valid Genesis block found, proceeding to mine a new one...")

                # ✅ **Ensure Key Manager is Available**
                if not self.key_manager:
                    raise RuntimeError("[GenesisBlockManager.ensure_genesis_block] ❌ ERROR: Key Manager is not initialized. Cannot create Genesis block.")

                # ✅ **Create and Mine the Genesis Block**
                genesis_block = self.create_and_mine_genesis_block()

                # ✅ **Ensure Genesis Block is Stored in LMDB**
                self.block_storage.store_block(genesis_block)

                print(f"[GenesisBlockManager.ensure_genesis_block] ✅ SUCCESS: New Genesis block created with hash: {genesis_block.hash}")
                return genesis_block

            except Exception as e:
                print(f"[GenesisBlockManager.ensure_genesis_block] ❌ ERROR: Genesis initialization failed: {e}")
                raise




    def create_and_mine_genesis_block(self) -> Block:
        """
        Creates and mines the Genesis block with full Zyiron metadata.
        Ensures the mined hash is used directly without re-hashing.
        """
        try:
            print("[GenesisBlockManager] INFO: Checking for existing Genesis block...")

            # ✅ **Check for Existing Genesis Block in Storage**
            existing_genesis = self.block_storage.get_block_by_index(0)
            if existing_genesis:
                print(f"[GenesisBlockManager] INFO: Genesis block already exists with hash: {existing_genesis.hash}")
                return existing_genesis

            # ✅ **Retrieve Miner Address from Default Keys**
            miner_address = self.key_manager.get_default_public_key(self.network, "miner")
            if not miner_address:
                raise ValueError("[GenesisBlockManager] ERROR: Failed to retrieve miner address from default keys.")

            print(f"[GenesisBlockManager] INFO: Using default miner address: {miner_address}")

            # ✅ **Define Zyiron Chain Metadata for Genesis Block**
            genesis_metadata = {
                "Genesis Block": "***************************Genesis Block***************************",
                "name": "Zyiron Chain",
                "pronunciation": "ˈzaɪ-ɪ-rɒn",
                "description": [
                    "A strong, incorruptible foundation for a decentralized financial system, "
                    "built on trust, security, and resilience.",
                    "A digital economic structure designed to be immutable, transparent, and resistant to manipulation.",
                    "Symbolic of strength and endurance, derived from biblical and metallurgical themes, representing an unshakable financial kingdom."
                ],
                "created_by": "Anthony Henriquez",
                "creation_date": "Thursday, March 6, 2025 | 2:26 PM",
                "Genesis Block End": "***************************Genesis Block***************************"
            }

            # ✅ **Create the Coinbase Transaction**
            coinbase_tx = CoinbaseTx(
                block_height=0,
                miner_address=miner_address,
                reward=Decimal(Constants.INITIAL_COINBASE_REWARD)
            )
            coinbase_tx.fee = Decimal("0")
            coinbase_tx.metadata = genesis_metadata  # Embed metadata in Coinbase transaction

            # ✅ **Ensure Coinbase TX ID is correctly set**
            if not hasattr(coinbase_tx, "tx_id") or not isinstance(coinbase_tx.tx_id, str):
                coinbase_tx.tx_id = Hashing.hash(json.dumps(coinbase_tx.to_dict(), sort_keys=True).encode()).hex()
                print(f"[GenesisBlockManager] INFO: Generated Coinbase TX ID: {coinbase_tx.tx_id}")

            # ✅ **Initialize Genesis Block**
            genesis_target_int = int(Constants.GENESIS_TARGET, 16)  # Convert target to integer
            genesis_block = Block(
                index=0,
                previous_hash=Constants.ZERO_HASH,
                transactions=[coinbase_tx],
                difficulty=genesis_target_int,  # Use integer difficulty
                miner_address=miner_address,
                fees=Decimal(0)  # Set fees to 0 for the Genesis block
            )

            print(f"[GenesisBlockManager] INFO: Genesis Block initialized with nonce {genesis_block.nonce}")

            # ✅ **Mine Until Difficulty Target is Met**
            start_time = time.time()
            last_update_time = start_time  # For live display

            while True:
                genesis_block.nonce += 1
                computed_hash = genesis_block.calculate_hash()
                computed_hash_int = int(computed_hash, 16)  # Convert hex string to integer

                # ✅ **Ensure Hash Meets Target**
                if computed_hash_int < genesis_target_int:
                    genesis_block.hash = computed_hash  # ✅ Store hash as hex string
                    print(f"[GenesisBlockManager] ✅ SUCCESS: Mined Genesis Block with nonce {genesis_block.nonce}")
                    break

                # ✅ **Live Progress Tracker: Show nonce & elapsed time every second**
                current_time = time.time()
                if current_time - last_update_time >= 1:
                    elapsed = int(current_time - start_time)
                    print(f"[GenesisBlockManager] LIVE: Nonce {genesis_block.nonce}, Elapsed Time: {elapsed}s")
                    last_update_time = current_time

            # ✅ **Store Genesis Block in Storage**
            print("[GenesisBlockManager] INFO: Storing Genesis Block in BlockStorage...")
            self.block_storage.store_block(genesis_block)

            print(f"[GenesisBlockManager] ✅ SUCCESS: Stored Genesis block with hash: {genesis_block.hash}")
            return genesis_block

        except Exception as e:
            print(f"[GenesisBlockManager] ❌ ERROR: Genesis block mining failed: {e}")
            raise



    def prevent_duplicate_genesis(self):
        """
        Ensures only one Genesis block is stored by checking:
        - Block storage (LMDB)
        - Transaction index (tx_storage)
        If inconsistencies are found, resets storage.
        """
        try:
            print("[GenesisBlockManager.prevent_duplicate_genesis] INFO: Checking for existing Genesis block...")

            # ✅ **Check Block Storage (LMDB)**
            existing_block = self.block_storage.get_block_by_index(0)
            if existing_block:
                print(f"[GenesisBlockManager.prevent_duplicate_genesis] ✅ Found Genesis block in block storage with hash {existing_block.hash}")

                # ✅ **Check if Genesis Block Exists in Transaction Index**
                stored_tx_id = self.tx_storage.get_transaction_id("GENESIS_COINBASE")
                if stored_tx_id:
                    stored_genesis_tx = self.tx_storage.get_block_by_tx_id(stored_tx_id)
                    if stored_genesis_tx and stored_genesis_tx.index == 0:
                        print(f"[GenesisBlockManager.prevent_duplicate_genesis] ✅ Found Genesis block in transaction index with hash {stored_genesis_tx.hash}")
                        return stored_genesis_tx
                    else:
                        print("[GenesisBlockManager.prevent_duplicate_genesis] ⚠️ WARNING: Genesis block missing in transaction index but exists in block storage.")

                # ✅ **Validate Stored Block Integrity**
                computed_hash = Hashing.hash(json.dumps(existing_block.to_dict(), sort_keys=True).encode()).hex()
                if existing_block.hash == computed_hash:
                    print("[GenesisBlockManager.prevent_duplicate_genesis] ✅ SUCCESS: Genesis Block matches computed hash.")
                    return existing_block
                else:
                    print("[GenesisBlockManager.prevent_duplicate_genesis] ❌ ERROR: Genesis Block hash mismatch. Expected:", computed_hash)

            else:
                print("[GenesisBlockManager.prevent_duplicate_genesis] WARNING: Genesis Block not found in LMDB storage.")

            # 🚨 **No Valid Genesis Block Found – Proceed with Mining**
            print("[GenesisBlockManager.prevent_duplicate_genesis] ⚠️ WARNING: No valid Genesis block found, proceeding to mine a new one...")
            return None

        except Exception as e:
            print(f"[GenesisBlockManager.prevent_duplicate_genesis] ❌ ERROR: Failed to check Genesis block existence: {e}")
            return None

    def store_genesis_block(self, genesis_block: Block) -> Block:
        """
        Stores the Genesis block in LMDB storage.

        - Ensures only one Genesis block exists.
        - Validates block structure before storing.
        - Updates `tx_storage` and `block_storage`.
        - Prevents duplicate entries.

        Args:
            genesis_block (Block): The Genesis block to store.

        Returns:
            Block: The stored Genesis block.
        """
        try:
            print("[GenesisBlockManager.store_genesis_block] INFO: Storing Genesis block...")

            # ✅ **Ensure Genesis block follows standardized structure**
            if not self.validate_genesis_block(genesis_block):
                raise ValueError("[GenesisBlockManager.store_genesis_block] ❌ ERROR: Genesis block failed validation.")

            # ✅ **Prevent Duplicate Genesis Blocks**
            existing_block = self.prevent_duplicate_genesis()
            if existing_block:
                print(f"[GenesisBlockManager.store_genesis_block] ✅ INFO: Genesis block already exists with hash {existing_block.hash}")
                return existing_block

            # ✅ **Serialize Genesis Block and Store in LMDB**
            genesis_block_serialized = json.dumps(genesis_block.to_dict(), sort_keys=True).encode("utf-8")

            with self.block_storage.env.begin(write=True) as txn:
                txn.put(f"block:0".encode(), genesis_block_serialized)

            print("[GenesisBlockManager.store_genesis_block] ✅ SUCCESS: Genesis block stored correctly in LMDB.")

            # ✅ **Index Genesis Transactions in `tx_storage`**
            print("[GenesisBlockManager.store_genesis_block] INFO: Indexing Genesis transactions in tx_storage...")

            for tx in genesis_block.transactions:
                if hasattr(tx, "tx_id") and hasattr(tx, "to_dict"):
                    tx_dict = tx.to_dict()

                    # ✅ **Ensure Inputs & Outputs Are Properly Structured**
                    tx_inputs = tx_dict.get("inputs", [])
                    tx_outputs = tx_dict.get("outputs", [])

                    if not isinstance(tx_inputs, list) or not isinstance(tx_outputs, list):
                        print(f"[GenesisBlockManager.store_genesis_block] ⚠️ WARNING: Skipping invalid transaction format for {tx.tx_id}.")
                        continue

                    # ✅ **Store Transaction in `tx_storage`**
                    with self.tx_storage.env.begin(write=True) as txn:
                        txn.put(tx.tx_id.encode("utf-8"), json.dumps({
                            "block_hash": genesis_block.hash,
                            "inputs": tx_inputs,
                            "outputs": tx_outputs,
                            "timestamp": tx_dict.get("timestamp", int(time.time()))
                        }).encode("utf-8"))
                    
                    print(f"[GenesisBlockManager.store_genesis_block] ✅ INFO: Indexed transaction {tx.tx_id} in tx_storage.")

                else:
                    print(f"[GenesisBlockManager.store_genesis_block] ⚠️ WARNING: Skipping invalid transaction format.")

            # ✅ **Verify Stored Genesis Block for Integrity**
            stored_genesis_block = self.block_storage.get_block_by_index(0)
            if not stored_genesis_block or stored_genesis_block.hash != genesis_block.hash:
                raise ValueError("[GenesisBlockManager.store_genesis_block] ❌ ERROR: Genesis block verification failed after storage.")

            print(f"[GenesisBlockManager.store_genesis_block] ✅ SUCCESS: Genesis block stored with hash: {genesis_block.hash}")
            return genesis_block

        except Exception as e:
            print(f"[GenesisBlockManager.store_genesis_block] ❌ ERROR: Failed to store Genesis block: {e}")
            raise
