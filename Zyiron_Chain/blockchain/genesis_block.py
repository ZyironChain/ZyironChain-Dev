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
from Zyiron_Chain.storage.block_storage import WholeBlockData
from Zyiron_Chain.storage.blockmetadata import BlockMetadata
from Zyiron_Chain.accounts.key_manager import KeyManager

from threading import Lock

class GenesisBlockManager:
    """
    Manages the creation, mining, and validation of the Genesis block.
    
    - Processes all data as bytes.
    - Uses only single SHA3-384 hashing via Hashing.hash().
    - Utilizes Constants for defaults.
    - Provides detailed print statements for debugging.
    - Sends the Genesis block to the correct storage modules.
    """
    genesis_block_offset = Constants.BLOCK_STORAGE_OFFSETS["block_height"]["start"]

    GENESIS_HASH = None  # Optionally set a predefined genesis hash (hex string) to bypass mining


    def __init__(self, block_storage: WholeBlockData, block_metadata: BlockMetadata, key_manager: KeyManager, chain, block_manager):
        """
        Manages the creation, validation, and storage of the Genesis block.

        Args:
            block_storage (WholeBlockData): The block storage handler.
            block_metadata (BlockMetadata): The block metadata database.
            key_manager (KeyManager): Key manager for cryptographic signing and verification.
            chain: Blockchain instance.
            block_manager: Block manager instance.
        """
        if not key_manager:
            raise ValueError("[GenesisBlockManager.__init__] ❌ ERROR: `key_manager` cannot be None.")

        self.block_storage = block_storage
        self.block_metadata = block_metadata
        self.key_manager = key_manager
        self.chain = chain
        self.block_manager = block_manager
        self.network = Constants.NETWORK
        self.genesis_lock = Lock()  # Thread lock to prevent multiple Genesis blocks
        print(f"[GenesisBlockManager.__init__] ✅ INFO: Initialized for network: {self.network}")

    def ensure_genesis_block(self):
        """
        Ensures the Genesis block exists in storage.
        - First checks if it's already stored.
        - If missing, attempts retrieval by the Genesis Coinbase transaction ID (`tx_id`).
        - Validates existence in both LMDB and `block.data` with proper offset handling.
        - Only mines a new Genesis block if all lookups fail.
        """
        with self.genesis_lock:  # Ensure thread safety
            try:
                print("[GenesisBlockManager.ensure_genesis_block] INFO: Checking for existing Genesis block...")

                # ✅ **Check if Genesis Block Exists in LMDB Metadata**
                if hasattr(self.block_metadata, "get_block_by_height"):
                    existing_genesis = self.block_metadata.get_block_by_height(0)
                    if existing_genesis and hasattr(existing_genesis, "hash"):
                        print(f"[GenesisBlockManager.ensure_genesis_block] ✅ INFO: Genesis Block found in metadata with hash {existing_genesis.hash}")
                        return existing_genesis
                else:
                    print("[GenesisBlockManager.ensure_genesis_block] WARNING: `get_block_by_height` method missing. Skipping metadata lookup.")

                # ✅ **Check if Genesis Coinbase TX Exists in `txindex_db`**
                stored_tx_id = self.block_metadata.get_transaction_id("GENESIS_COINBASE")
                if stored_tx_id:
                    print(f"[GenesisBlockManager.ensure_genesis_block] INFO: Found stored Coinbase TX ID: {stored_tx_id}")

                    stored_genesis_block = self.block_metadata.get_block_by_tx_id(stored_tx_id)
                    if stored_genesis_block and hasattr(stored_genesis_block, "hash"):
                        print(f"[GenesisBlockManager.ensure_genesis_block] ✅ SUCCESS: Loaded Genesis block from transaction index with hash: {stored_genesis_block.hash}")
                        return stored_genesis_block

                    print("[GenesisBlockManager.ensure_genesis_block] WARNING: Retrieved Genesis block is invalid or missing.")

                # ✅ **Check if Genesis Block Exists in Block Storage (`block.data`)**
                print("[GenesisBlockManager.ensure_genesis_block] INFO: Checking block.data for Genesis block at correct offset...")

                # ✅ **Use Network Standard Offset for Genesis Block**
                genesis_block_offset = Constants.BLOCK_STORAGE_OFFSETS["block_height"]["start"]

                # ✅ **Ensure `block.data` exists and is large enough before reading**
                if os.path.exists(self.block_storage.current_block_file):
                    with open(self.block_storage.current_block_file, "rb") as f:
                        f.seek(0, os.SEEK_END)  # Move to end
                        file_size = f.tell()

                    if file_size < genesis_block_offset:
                        print(f"[GenesisBlockManager.ensure_genesis_block] WARNING: `block.data` is too small ({file_size} bytes), expected at least {genesis_block_offset}.")
                    else:
                        block_from_storage = self.block_storage.get_block_from_data_file(genesis_block_offset)

                        if block_from_storage and hasattr(block_from_storage, "index") and block_from_storage.index == 0:
                            print(f"[GenesisBlockManager.ensure_genesis_block] ✅ SUCCESS: Genesis Block retrieved from block.data with hash: {block_from_storage.hash}")

                            # ✅ **Ensure the block matches the expected Genesis hash**
                            expected_genesis_hash = Hashing.hash(json.dumps(block_from_storage.to_dict(), sort_keys=True).encode()).hex()
                            if block_from_storage.hash == expected_genesis_hash:
                                print("[GenesisBlockManager.ensure_genesis_block] ✅ SUCCESS: Genesis Block matches expected hash.")
                                return block_from_storage
                            else:
                                print("[GenesisBlockManager.ensure_genesis_block] ❌ ERROR: Genesis Block hash mismatch. Expected:", expected_genesis_hash)

                else:
                    print("[GenesisBlockManager.ensure_genesis_block] WARNING: `block.data` file not found.")

                # 🚨 **No Valid Genesis Block Found – Proceed to Mining a New One**
                print("[GenesisBlockManager.ensure_genesis_block] ⚠️ WARNING: No valid Genesis block found, proceeding to mine a new one...")

                # ✅ **Ensure Key Manager is Available**
                if not self.key_manager:
                    raise RuntimeError("[GenesisBlockManager.ensure_genesis_block] ❌ ERROR: Key Manager is not initialized. Cannot create Genesis block.")

                # ✅ **Create and Mine the Genesis Block**
                genesis_block = self.create_and_mine_genesis_block()

                # ✅ **Ensure Genesis Block is Stored at Correct Offset in `block.data`**
                self.block_metadata.store_block(genesis_block, genesis_block.difficulty)
                self.block_storage.store_block_at_offset(genesis_block, genesis_block_offset)

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

            # ✅ **Check for Existing Genesis Block in Metadata**
            stored_tx_id = self.block_metadata.get_transaction_id("GENESIS_COINBASE")
            if stored_tx_id:
                print(f"[GenesisBlockManager] INFO: Genesis block already exists with TX ID: {stored_tx_id}")
                stored_genesis_block = self.block_metadata.get_block_by_tx_id(stored_tx_id)
                if stored_genesis_block:
                    return stored_genesis_block

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
                "etymology": {
                    "Zion": "Divine city of righteousness and justice (Isaiah 2:3)",
                    "Zur": "Hebrew word for strength and foundation (Psalm 18:2)",
                    "Iron": "Symbolizes power and endurance (Daniel 2:40)"
                },
                "created_by": "Anthony Henriquez",
                "creation_date": "Thursday, March 6, 2025 | 2:26 PM",
                "signature_hashes": {
                    "Signature Hash 1": "a44972faa4624f6334bbe9ec3091283811b2d908f4639d35b1862d7bdf127c1191f5bf6b5948a979e358fd1dc4caf5fe",
                    "Signature Hash 2": "c76c3ac18080527165d8a2cad1b0bf2764508b2f16ef9640e02ddfbaad721e1e15717a83ec85839453bbe553ea30273b"
                },
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
            genesis_target_int = int.from_bytes(Constants.GENESIS_TARGET, byteorder='big')
            genesis_block = Block(
                index=0,
                previous_hash=Constants.ZERO_HASH.encode() if isinstance(Constants.ZERO_HASH, str) else Constants.ZERO_HASH,  # ✅ Ensure bytes
                transactions=[coinbase_tx],
                difficulty=genesis_target_int,  # Use integer difficulty
                miner_address=miner_address,
                fees=Decimal(0),  # Set fees to 0 for the Genesis block
                magic_number=Constants.MAGIC_NUMBER  # Use Constants.MAGIC_NUMBER for consistency
            )

            print(f"[GenesisBlockManager] INFO: Genesis Block initialized with nonce {genesis_block.nonce}")

            # ✅ **Mine Until Difficulty Target is Met**
            start_time = time.time()
            last_update_time = start_time  # For live display

            while True:
                genesis_block.nonce += 1
                computed_hash = genesis_block.calculate_hash()  # Returns bytes
                computed_hash_int = int.from_bytes(computed_hash, byteorder='big')  # Convert bytes to integer

                # ✅ **Ensure Hash Meets Target**
                if computed_hash_int < genesis_target_int:
                    genesis_block.hash = computed_hash.hex() if isinstance(computed_hash, bytes) else computed_hash  # ✅ Ensure hex string
                    print(f"[GenesisBlockManager] ✅ SUCCESS: Mined Genesis Block with nonce {genesis_block.nonce}")
                    break

                # ✅ **Live Progress Tracker: Show nonce & elapsed time every second**
                current_time = time.time()
                if current_time - last_update_time >= 1:
                    elapsed = int(current_time - start_time)
                    print(f"[GenesisBlockManager] LIVE: Nonce {genesis_block.nonce}, Elapsed Time: {elapsed}s")
                    last_update_time = current_time

            # ✅ **Store Genesis Block in Metadata and Block Storage**
            print("[GenesisBlockManager] INFO: Storing Genesis Block in BlockMetadata and BlockStorage...")

            # ✅ **Ensure `previous_hash`, `hash`, and `merkle_root` are stored correctly**
            genesis_block.previous_hash = genesis_block.previous_hash.hex() if isinstance(genesis_block.previous_hash, bytes) else genesis_block.previous_hash
            genesis_block.merkle_root = genesis_block._compute_merkle_root().hex() if isinstance(genesis_block._compute_merkle_root(), bytes) else genesis_block._compute_merkle_root()
            genesis_block.hash = genesis_block.hash.hex() if isinstance(genesis_block.hash, bytes) else genesis_block.hash

            # ✅ **Securely Store the Genesis Block**
            self.store_genesis_block(genesis_block)

            print(f"[GenesisBlockManager] ✅ SUCCESS: Stored Genesis block with hash: {genesis_block.hash}")
            return genesis_block

        except Exception as e:
            print(f"[GenesisBlockManager] ❌ ERROR: Genesis block mining failed: {e}")
            raise






    def print_genesis_metadata(self):
        """
        Retrieves and prints the Genesis Block metadata from the Coinbase transaction.
        """
        try:
            print("[GenesisBlockManager] INFO: Retrieving Genesis Block Metadata...")

            # ✅ Fetch the Genesis Block
            stored_tx_id = self.block_metadata.get_transaction_id("GENESIS_COINBASE")
            if not stored_tx_id:
                print("[GenesisBlockManager] ERROR: Genesis Coinbase transaction not found.")
                return

            genesis_block = self.block_metadata.get_block_by_tx_id(stored_tx_id)
            if not genesis_block:
                print("[GenesisBlockManager] ERROR: Genesis block not found.")
                return

            # ✅ Retrieve the Coinbase Transaction
            coinbase_tx = genesis_block.transactions[0] if genesis_block.transactions else None
            if not coinbase_tx:
                print("[GenesisBlockManager] ERROR: Coinbase transaction missing from Genesis block.")
                return

            # ✅ **Debug Transaction Data**
            print("[DEBUG] Full Transaction Data:")
            print(coinbase_tx.to_dict())  # Ensure metadata is present

            # ✅ **Ensure Metadata Exists**
            if not hasattr(coinbase_tx, "metadata") or not coinbase_tx.metadata:
                print("[GenesisBlockManager] ERROR: Metadata is missing from Coinbase transaction!")
                return

            # ✅ **Print the Metadata**
            print("\n*************************** Genesis Block Metadata ***************************")
            for key, value in coinbase_tx.metadata.items():
                if isinstance(value, dict):
                    print(f"{key}:")
                    for subkey, subvalue in value.items():
                        print(f"  - {subkey}: {subvalue}")
                elif isinstance(value, list):
                    print(f"{key}:")
                    for item in value:
                        print(f"  - {item}")
                else:
                    print(f"{key}: {value}")
            print("********************************************************************************\n")

        except Exception as e:
            print(f"[GenesisBlockManager] ERROR: Failed to retrieve Genesis Block metadata: {e}")



    def validate_genesis_block(self, genesis_block) -> bool:
        """
        Validate the Genesis block:
        - Index must be 0 and previous_hash must equal Constants.ZERO_HASH.
        - The block hash must be a valid SHA3-384 hex string and meet the difficulty target.
        - Ensures that the Coinbase transaction exists and is valid.
        - Validates that the Merkle root is correctly derived.
        - Checks version compatibility and embedded metadata.
        """
        try:
            print("[GenesisBlockManager.validate_genesis_block] INFO: Validating Genesis block integrity...")

            # ✅ **Check Index**
            if not isinstance(genesis_block.index, int) or genesis_block.index != 0:
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block index must be 0, found {genesis_block.index}."
                )

            # ✅ **Check Previous Hash**
            if not isinstance(genesis_block.previous_hash, str) or genesis_block.previous_hash != Constants.ZERO_HASH:
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block has an invalid previous hash.\n"
                    f"  - Expected: {Constants.ZERO_HASH}\n"
                    f"  - Found: {genesis_block.previous_hash}"
                )

            # ✅ **Ensure Block Hash is a Valid SHA3-384 Hex String**
            if (
                not isinstance(genesis_block.hash, str) or 
                len(genesis_block.hash) != Constants.SHA3_384_HASH_SIZE * 2 or 
                not all(c in "0123456789abcdef" for c in genesis_block.hash.lower())
            ):
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block hash is not a valid SHA3-384 hash.\n"
                    f"  - Expected Length: {Constants.SHA3_384_HASH_SIZE * 2}\n"
                    f"  - Found: {len(genesis_block.hash)}\n"
                    f"  - Hash: {genesis_block.hash}"
                )

            # ✅ **Check Difficulty Target Compliance**
            block_hash_int = int(genesis_block.hash, 16)
            genesis_target_int = int.from_bytes(Constants.GENESIS_TARGET, byteorder='big')

            if block_hash_int >= genesis_target_int:
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block hash does not meet difficulty target.\n"
                    f"  - Expected Target: {hex(genesis_target_int)}\n"
                    f"  - Found: {genesis_block.hash}"
                )

            # ✅ **Ensure Coinbase Transaction Exists**
            if not genesis_block.transactions or len(genesis_block.transactions) == 0:
                raise ValueError(
                    "[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block must contain a Coinbase transaction."
                )

            coinbase_tx = genesis_block.transactions[0]

            # ✅ **Ensure Coinbase Transaction Has a Valid `tx_id`**
            if not hasattr(coinbase_tx, "tx_id") or not isinstance(coinbase_tx.tx_id, str):
                raise ValueError(
                    "[GenesisBlockManager.validate_genesis_block] ERROR: Coinbase transaction must have a valid `tx_id`."
                )

            # ✅ **Ensure Coinbase TX ID is Correct**
            expected_tx_id = Hashing.hash(json.dumps(coinbase_tx.to_dict(), sort_keys=True).encode()).hex()
            if coinbase_tx.tx_id != expected_tx_id:
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Coinbase transaction TX ID mismatch.\n"
                    f"  - Expected: {expected_tx_id}\n"
                    f"  - Found: {coinbase_tx.tx_id}"
                )

            # ✅ **Verify Merkle Root Integrity**
            expected_merkle_root = genesis_block._compute_merkle_root()
            if genesis_block.merkle_root != expected_merkle_root:
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Merkle root does not match transaction hashes.\n"
                    f"  - Expected: {expected_merkle_root}\n"
                    f"  - Found: {genesis_block.merkle_root}"
                )

            # ✅ **Check Version Compatibility**
            if not hasattr(genesis_block, "version") or genesis_block.version != Constants.VERSION:
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Version mismatch in Genesis block.\n"
                    f"  - Expected: {Constants.VERSION}\n"
                    f"  - Found: {genesis_block.version}"
                )

            # ✅ **Validate Embedded Metadata**
            if not hasattr(coinbase_tx, "metadata") or not isinstance(coinbase_tx.metadata, dict):
                raise ValueError("[GenesisBlockManager.validate_genesis_block] ERROR: Missing or invalid Genesis metadata.")

            required_metadata_keys = [
                "Genesis Block", "name", "description", "created_by", "creation_date", "signature_hashes"
            ]
            for key in required_metadata_keys:
                if key not in coinbase_tx.metadata:
                    raise ValueError(f"[GenesisBlockManager.validate_genesis_block] ERROR: Missing metadata key: {key}")

            # ✅ **Ensure Metadata is in the Correct Format**
            if not isinstance(coinbase_tx.metadata.get("description"), list):
                raise ValueError("[GenesisBlockManager.validate_genesis_block] ERROR: 'description' field must be a list.")

            if not isinstance(coinbase_tx.metadata.get("signature_hashes"), dict):
                raise ValueError("[GenesisBlockManager.validate_genesis_block] ERROR: 'signature_hashes' field must be a dictionary.")

            # ✅ **Check `created_by` Format**
            if not isinstance(coinbase_tx.metadata.get("created_by"), str):
                raise ValueError("[GenesisBlockManager.validate_genesis_block] ERROR: 'created_by' field must be a string.")

            # ✅ **Check `creation_date` Format**
            if not isinstance(coinbase_tx.metadata.get("creation_date"), str):
                raise ValueError("[GenesisBlockManager.validate_genesis_block] ERROR: 'creation_date' field must be a string.")

            print("[GenesisBlockManager.validate_genesis_block] ✅ SUCCESS: Genesis block validated successfully.")
            return True

        except Exception as e:
            print(f"[GenesisBlockManager.validate_genesis_block] ❌ ERROR: Genesis block validation failed: {e}")
            return False



    def prevent_duplicate_genesis(self):
        """
        Ensures only one Genesis block is stored by checking:
        - Block metadata (LMDB)
        - Transaction index (txindex_db)
        - Block storage (block.data)
        If inconsistencies are found, resets storage.
        """
        try:
            print("[GenesisBlockManager.prevent_duplicate_genesis] INFO: Checking for existing Genesis block...")

            # ✅ **Check Block Metadata (LMDB)**
            existing_metadata = self.block_metadata.get_block_by_height(0)
            if existing_metadata and hasattr(existing_metadata, "hash"):
                print(f"[GenesisBlockManager.prevent_duplicate_genesis] ✅ Found Genesis block in metadata with hash {existing_metadata.hash}")

                # ✅ **Check if Genesis Block Exists in Transaction Index**
                stored_tx_id = self.block_metadata.get_transaction_id("GENESIS_COINBASE")
                if stored_tx_id:
                    stored_genesis_tx = self.block_metadata.get_block_by_tx_id(stored_tx_id)
                    if stored_genesis_tx and hasattr(stored_genesis_tx, "index") and stored_genesis_tx.index == 0:
                        print(f"[GenesisBlockManager.prevent_duplicate_genesis] ✅ Found Genesis block in transaction index with hash {stored_genesis_tx.hash}")
                        return stored_genesis_tx
                    else:
                        print("[GenesisBlockManager.prevent_duplicate_genesis] ⚠️ WARNING: Genesis block missing in transaction index but exists in metadata.")

                # ✅ **Check if Genesis Block Exists in Block Storage**
                existing_storage = self.block_storage.get_latest_block()
                if existing_storage and hasattr(existing_storage, "index") and existing_storage.index == 0:
                    print(f"[GenesisBlockManager.prevent_duplicate_genesis] ✅ Genesis block exists in block storage with hash {existing_storage.hash}")
                    return existing_storage
                else:
                    print("[GenesisBlockManager.prevent_duplicate_genesis] ⚠️ WARNING: Genesis block missing in block storage but exists in metadata.")

                # ✅ **Fix Inconsistencies: Rebuild from Metadata**
                print("[GenesisBlockManager.prevent_duplicate_genesis] 🔄 INFO: Restoring Genesis block from metadata...")
                self.block_storage.store_block(existing_metadata, existing_metadata.difficulty)
                return existing_metadata

            # 🚨 **Check if Genesis Block Exists in `block.data` and is Valid**
            print("[GenesisBlockManager.prevent_duplicate_genesis] INFO: Checking block.data storage for Genesis block...")
            block_from_storage = self.block_storage.get_block_from_data_file(4)  # Genesis block should be at offset 4

            if block_from_storage and hasattr(block_from_storage, "index") and block_from_storage.index == 0:
                print(f"[GenesisBlockManager.prevent_duplicate_genesis] ✅ SUCCESS: Retrieved Genesis Block from block.data with hash: {block_from_storage.hash}")

                # ✅ **Ensure the block matches the expected Genesis hash**
                expected_genesis_hash = Constants.GENESIS_BLOCK_HASH
                if block_from_storage.hash == expected_genesis_hash:
                    print("[GenesisBlockManager.prevent_duplicate_genesis] ✅ SUCCESS: Genesis Block matches expected hash.")
                    return block_from_storage
                else:
                    print("[GenesisBlockManager.prevent_duplicate_genesis] ❌ ERROR: Genesis Block hash mismatch. Expected:", expected_genesis_hash)

            else:
                print("[GenesisBlockManager.prevent_duplicate_genesis] WARNING: Genesis Block not found in block.data.")

            # 🚨 **No Valid Genesis Block Found – Proceed with Mining**
            print("[GenesisBlockManager.prevent_duplicate_genesis] ⚠️ WARNING: No valid Genesis block found, proceeding to mine a new one...")
            return None

        except Exception as e:
            print(f"[GenesisBlockManager.prevent_duplicate_genesis] ❌ ERROR: Failed to check Genesis block existence: {e}")
            return None


    def store_genesis_block(self, genesis_block: Block) -> Block:
        """
        Stores the Genesis block in both LMDB metadata and block storage.

        - Ensures only one Genesis block exists.
        - Validates block structure before storing.
        - Updates `block_metadata`, `txindex_db`, and `block_storage`.
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

            # ✅ **Store Genesis Block in Metadata**
            print("[GenesisBlockManager.store_genesis_block] INFO: Storing block in LMDB metadata...")
            self.block_metadata.store_block(genesis_block, genesis_block.difficulty)

            # ✅ **Use Standardized Network Offset for Genesis Block Storage (`block.data`)**
            genesis_block_offset = Constants.BLOCK_STORAGE_OFFSETS["block_height"]["start"]
            print(f"[GenesisBlockManager.store_genesis_block] INFO: Storing Genesis block at offset {genesis_block_offset} in block.data...")

            # ✅ **Serialize Genesis Block into Binary Format**
            genesis_block_binary = self.block_storage._serialize_block_to_binary(genesis_block)

            # ✅ **Ensure `block.data` is at least large enough before writing Genesis block**
            with open(self.block_storage.current_block_file, "r+b") as f:
                f.seek(0, os.SEEK_END)  # Move to the end of the file
                file_size = f.tell()  # Get current file size

                if file_size < genesis_block_offset:  # If file is too small, extend it
                    print(f"[GenesisBlockManager.store_genesis_block] INFO: Expanding `block.data` to fit Genesis block.")
                    f.seek(genesis_block_offset - 1)
                    f.write(b"\x00")  # Write a single null byte to extend file

                f.seek(genesis_block_offset)  # Now, safely move to offset
                f.write(genesis_block_binary)

            print("[GenesisBlockManager.store_genesis_block] ✅ SUCCESS: Genesis block stored correctly in block.data.")

            # ✅ **Index Genesis Transactions in `txindex_db`**
            print("[GenesisBlockManager.store_genesis_block] INFO: Indexing Genesis transactions in txindex_db...")
            for tx in genesis_block.transactions:
                if hasattr(tx, "tx_id") and hasattr(tx, "to_dict"):
                    tx_dict = tx.to_dict()

                    # ✅ **Verify Inputs & Outputs Structure Before Storing**
                    tx_inputs = tx_dict.get("inputs", [])
                    tx_outputs = tx_dict.get("outputs", [])

                    if not isinstance(tx_inputs, list) or not isinstance(tx_outputs, list):
                        print(f"[GenesisBlockManager.store_genesis_block] ⚠️ WARNING: Skipping invalid transaction format for {tx.tx_id}.")
                        continue

                    # ✅ **Ensure TX ID is Properly Encoded for Storage**
                    stored_tx_id = tx.tx_id.encode("utf-8") if isinstance(tx.tx_id, str) else tx.tx_id

                    # ✅ **Store Transaction in `txindex_db`**
                    self.block_metadata.tx_storage.store_transaction(
                        stored_tx_id, genesis_block.hash, tx_inputs, tx_outputs, tx_dict.get("timestamp", int(time.time()))
                    )
                    print(f"[GenesisBlockManager.store_genesis_block] ✅ INFO: Indexed transaction {tx.tx_id} in txindex_db.")

                else:
                    print(f"[GenesisBlockManager.store_genesis_block] ⚠️ WARNING: Skipping invalid transaction format.")

            # ✅ **Verify Stored Genesis Block for Integrity**
            stored_genesis_block = self.block_metadata.get_block_by_height(0)
            if not stored_genesis_block or stored_genesis_block.hash != genesis_block.hash:
                raise ValueError("[GenesisBlockManager.store_genesis_block] ❌ ERROR: Genesis block verification failed after storage.")

            print(f"[GenesisBlockManager.store_genesis_block] ✅ SUCCESS: Genesis block stored with hash: {genesis_block.hash}")
            return genesis_block

        except Exception as e:
            print(f"[GenesisBlockManager.store_genesis_block] ❌ ERROR: Failed to store Genesis block: {e}")
            raise