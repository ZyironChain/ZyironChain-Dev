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
from Zyiron_Chain.keys.key_manager import KeyManager

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

    GENESIS_HASH = None  # Optionally set a predefined genesis hash (hex string) to bypass mining

    def __init__(self, block_storage: WholeBlockData, block_metadata: BlockMetadata, key_manager: KeyManager, chain, block_manager):
        self.block_storage = block_storage
        self.block_metadata = block_metadata
        self.key_manager = key_manager
        self.chain = chain
        self.block_manager = block_manager
        self.network = Constants.NETWORK
        self.genesis_lock = Lock()  # Thread lock to prevent multiple Genesis blocks
        print(f"[GenesisBlockManager.__init__] Initialized for network: {self.network}")

    def ensure_genesis_block(self):
        """
        Ensures the Genesis block exists in storage.
        - First checks if it's already stored.
        - If missing, attempts retrieval by the Genesis Coinbase transaction ID (`tx_id`).
        - Only mines a new Genesis block if both lookups fail.
        """
        with self.genesis_lock:  # Ensure thread safety
            try:
                print("[GenesisBlockManager.ensure_genesis_block] INFO: Checking for existing Genesis block...")

                # ✅ **Check if Genesis Block Already Exists in Block Metadata**
                if hasattr(self.block_metadata, "get_block_by_height"):
                    existing_genesis = self.block_metadata.get_block_by_height(0)
                    if existing_genesis and hasattr(existing_genesis, "hash"):
                        print(f"[GenesisBlockManager.ensure_genesis_block] ✅ INFO: Genesis Block already exists with hash {existing_genesis.hash}")
                        return existing_genesis
                else:
                    print("[GenesisBlockManager.ensure_genesis_block] WARNING: `get_block_by_height` method missing. Skipping direct lookup.")

                # ✅ **Check if Genesis Coinbase TX Exists in `txindex_db`**
                stored_tx_id = self.block_metadata.get_transaction_id("GENESIS_COINBASE")
                if stored_tx_id:
                    print(f"[GenesisBlockManager.ensure_genesis_block] INFO: Found stored Coinbase TX ID: {stored_tx_id}")

                    stored_genesis_block = self.block_metadata.get_block_by_tx_id(stored_tx_id)
                    if stored_genesis_block and hasattr(stored_genesis_block, "hash"):
                        print(f"[GenesisBlockManager.ensure_genesis_block] ✅ SUCCESS: Loaded Genesis block with hash: {stored_genesis_block.hash}")
                        return stored_genesis_block

                    print("[GenesisBlockManager.ensure_genesis_block] WARNING: Retrieved Genesis block is invalid or missing.")

                # ✅ **Check if Genesis Block Exists in Block Storage**
                latest_block = self.block_storage.get_latest_block()
                if latest_block and hasattr(latest_block, "index") and latest_block.index == 0:
                    print(f"[GenesisBlockManager.ensure_genesis_block] ✅ INFO: Loaded Genesis Block from storage with hash: {latest_block.hash}")
                    return latest_block

                # 🚨 **No Valid Genesis Block Found – Proceed to Mining a New One**
                print("[GenesisBlockManager.ensure_genesis_block] ⚠️ WARNING: No valid Genesis block found, proceeding to mine a new one...")

                # ✅ **Create and Mine the Genesis Block**
                genesis_block = self.create_and_mine_genesis_block()

                # ✅ **Store Genesis Block in BlockMetadata & BlockStorage**
                self.block_metadata.store_block(genesis_block, genesis_block.difficulty)
                self.block_storage.store_block(genesis_block, genesis_block.difficulty)

                print(f"[GenesisBlockManager.ensure_genesis_block] ✅ SUCCESS: New Genesis block created with hash: {genesis_block.hash}")
                return genesis_block

            except Exception as e:
                print(f"[GenesisBlockManager.ensure_genesis_block] ❌ ERROR: Genesis initialization failed: {e}")
                raise




    def create_and_mine_genesis_block(self) -> Block:
        """
        Creates and mines the Genesis block with full Zyiron metadata.
        - Uses a Coinbase transaction.
        - Stores metadata in the Coinbase transaction.
        - Keeps block format unchanged while ensuring metadata is retrievable.
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

            # ✅ **Retrieve Miner Address**
            miner_address = self.key_manager.get_default_public_key(self.network, "miner")
            if not miner_address:
                raise ValueError("[GenesisBlockManager] ERROR: Failed to retrieve miner address.")

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
                "biblical_references": {
                    "Proverbs 13:22": "A good person leaves an inheritance for their children's children, but a sinner's wealth is stored up for the righteous.",
                    "1 Peter 4:10": "Each of you should use whatever gift you have received to serve others, as faithful stewards of God's grace in its various forms.",
                    "John 14:27": "Peace I leave with you; my peace I give you. I do not give to you as the world gives. Do not let your hearts be troubled and do not be afraid.",
                    "Proverbs 27:17": "As iron sharpens iron, so one person sharpens another."
                },
                "created_by": "Anthony Henriquez",
                "creation_date": "Thursday, March 6, 2025 | 2:26 PM",
                "market_data": {
                    "Bitcoin (BTC)": "$89,864.99",
                    "Litecoin (LTC)": "$104.73",
                    "US Inflation Rate": "3%",
                    "Crypto Market Capitalization": "$2.94 Trillion",
                    "Special Event": "President Trump signs executive order officially creating a Bitcoin Strategic Reserve."
                },
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

            print(f"[GenesisBlockManager] INFO: Genesis Block initialized with nonce {genesis_block.nonce}")

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
                    print(f"[GenesisBlockManager] LIVE: Nonce {genesis_block.nonce}, Elapsed Time: {elapsed}s")
                    last_update = current_time

            # ✅ **Genesis Block Mined Successfully**
            print(f"[GenesisBlockManager] ✅ SUCCESS: Mined Genesis Block {genesis_block.index} with hash: {genesis_block.hash}")

            # ✅ **Store Genesis Transaction in LMDB**
            with self.block_metadata.block_metadata_db.env.begin(write=True) as txn:
                txn.put(b"GENESIS_COINBASE", coinbase_tx.tx_id.encode("utf-8"))

            # ✅ **Ensure Block Storage and Metadata Exist Before Storing**
            if not hasattr(self, "block_metadata") or not self.block_metadata:
                raise ValueError("[GenesisBlockManager] ERROR: BlockMetadata instance is missing.")

            if not hasattr(self, "block_storage") or not self.block_storage:
                raise ValueError("[GenesisBlockManager] ERROR: BlockStorage instance is missing.")

            # ✅ **Store Genesis Block in Metadata and Block Storage**
            print("[GenesisBlockManager] INFO: Storing Genesis Block in BlockMetadata and BlockStorage...")
            self.block_metadata.store_block(genesis_block, genesis_block.difficulty)
            self.block_storage.store_block(genesis_block, genesis_block.difficulty)

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
            if genesis_block.index != 0:
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block index must be 0, found {genesis_block.index}."
                )

            # ✅ **Check Previous Hash**
            if genesis_block.previous_hash != Constants.ZERO_HASH:
                raise ValueError(
                    "[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block has an invalid previous hash."
                )

            # ✅ **Ensure Block Hash is a Valid SHA3-384 Hex String**
            if not isinstance(genesis_block.hash, str) or len(genesis_block.hash) != Constants.SHA3_384_HASH_SIZE:
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block hash is not a valid SHA3-384 hash.\n"
                    f"Expected Length: {Constants.SHA3_384_HASH_SIZE}, Found: {len(genesis_block.hash)}"
                )

            # ✅ **Check Difficulty Target Compliance (Uses `Constants.GENESIS_TARGET`)**
            genesis_target = Constants.GENESIS_TARGET
            block_hash_int = int(genesis_block.hash, 16)

            if block_hash_int >= genesis_target:
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block hash does not meet difficulty target.\n"
                    f"Expected Target: {hex(genesis_target)}\n"
                    f"Found: {genesis_block.hash}"
                )

            # ✅ **Ensure Coinbase Transaction Exists**
            if not genesis_block.transactions or len(genesis_block.transactions) == 0:
                raise ValueError(
                    "[GenesisBlockManager.validate_genesis_block] ERROR: Genesis block must contain a Coinbase transaction."
                )

            coinbase_tx = genesis_block.transactions[0]
            if not hasattr(coinbase_tx, "tx_id") or not isinstance(coinbase_tx.tx_id, str):
                raise ValueError(
                    "[GenesisBlockManager.validate_genesis_block] ERROR: Coinbase transaction must have a valid `tx_id`."
                )

            # ✅ **Ensure Coinbase TX ID is Correct (Fix: Ensure TX ID is Bytes-Compatible)**
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

            # ✅ **Check Version Compatibility**
            if not hasattr(genesis_block, "version") or genesis_block.version != Constants.VERSION:
                raise ValueError(
                    f"[GenesisBlockManager.validate_genesis_block] ERROR: Version mismatch in Genesis block.\n"
                    f"Expected: {Constants.VERSION}\n"
                    f"Found: {genesis_block.version}"
                )

            # ✅ **Validate Embedded Metadata**
            if not hasattr(coinbase_tx, "metadata") or not isinstance(coinbase_tx.metadata, dict):
                raise ValueError("[GenesisBlockManager.validate_genesis_block] ERROR: Missing or invalid Genesis metadata.")

            required_metadata_keys = [
                "Genesis Block", "name", "description", "created_by", "creation_date", "market_data"
            ]
            for key in required_metadata_keys:
                if key not in coinbase_tx.metadata:
                    raise ValueError(f"[GenesisBlockManager.validate_genesis_block] ERROR: Missing metadata key: {key}")

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
            if existing_metadata:
                print(f"[GenesisBlockManager.prevent_duplicate_genesis] ✅ Found Genesis block in metadata with hash {existing_metadata.hash}")

                # ✅ **Check if Genesis Block Exists in Transaction Index**
                stored_tx_id = self.block_metadata.get_transaction_id("GENESIS_COINBASE")
                if stored_tx_id:
                    stored_genesis_tx = self.block_metadata.get_block_by_tx_id(stored_tx_id)
                    if stored_genesis_tx and stored_genesis_tx.index == 0:
                        print(f"[GenesisBlockManager.prevent_duplicate_genesis] ✅ Found Genesis block in transaction index with hash {stored_genesis_tx.hash}")
                        return stored_genesis_tx
                    else:
                        print("[GenesisBlockManager.prevent_duplicate_genesis] ⚠️ WARNING: Genesis block missing in transaction index but exists in metadata.")

                # ✅ **Check if Genesis Block Exists in Block Storage**
                existing_storage = self.block_storage.get_latest_block()
                if existing_storage and existing_storage.index == 0:
                    print(f"[GenesisBlockManager.prevent_duplicate_genesis] ✅ Genesis block exists in block storage with hash {existing_storage.hash}")
                    return existing_storage
                else:
                    print("[GenesisBlockManager.prevent_duplicate_genesis] ⚠️ WARNING: Genesis block missing in block storage but exists in metadata.")

                # ✅ **Fix Inconsistencies: Rebuild from Metadata**
                print("[GenesisBlockManager.prevent_duplicate_genesis] 🔄 INFO: Restoring Genesis block from metadata...")
                self.block_storage.store_block(existing_metadata, existing_metadata.difficulty)
                return existing_metadata

            # ✅ **No Valid Genesis Block Found – Proceed with Mining**
            print("[GenesisBlockManager.prevent_duplicate_genesis] ⚠️ No valid Genesis block found, proceeding with new mining...")
            return None

        except Exception as e:
            print(f"[GenesisBlockManager.prevent_duplicate_genesis] ❌ ERROR: Failed to check Genesis block existence: {e}")
            return None
