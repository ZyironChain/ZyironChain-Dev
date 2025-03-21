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
from Zyiron_Chain.utils.diff_conversion import DifficultyConverter  # ✅ Make sure this import exists
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
        """Ensures the Genesis block exists before mining a new one."""
        with self.genesis_lock:
            try:
                print("[GenesisBlockManager.ensure_genesis_block] INFO: Checking for existing Genesis block...")

                # ✅ **Check LMDB Storage for Block 0**
                existing_genesis = self.block_storage.get_block_by_height(0)

                if existing_genesis:
                    print(f"[GenesisBlockManager.ensure_genesis_block] ✅ INFO: Genesis Block found with hash {existing_genesis.hash}")

                    # ✅ **Verify Hash Consistency**
                    computed_hash = existing_genesis.calculate_hash()
                    if existing_genesis.hash == computed_hash:
                        print("[GenesisBlockManager.ensure_genesis_block] ✅ SUCCESS: Stored Genesis Block is valid.")
                        return existing_genesis
                    else:
                        print("[GenesisBlockManager.ensure_genesis_block] ❌ ERROR: Stored Genesis Block hash mismatch!")
                        print(f"Expected: {computed_hash}, Found: {existing_genesis.hash}")
                        return None  # ❌ Block integrity issue, needs re-mining

                # ✅ **Check Coinbase TX in Transaction Storage**
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

                genesis_block = self.create_and_mine_genesis_block()

                # ✅ **Ensure Genesis Block is Stored in LMDB**
                self.block_storage.store_block(genesis_block)

                # ✅ **Store the Genesis Coinbase TX ID for Future Lookups**
                if genesis_block.transactions:
                    coinbase_tx = genesis_block.transactions[0]
                    if hasattr(coinbase_tx, "tx_id"):
                        with self.block_storage.env.begin(write=True) as txn:
                            txn.put(b"GENESIS_COINBASE", coinbase_tx.tx_id.encode("utf-8"))
                        print(f"[GenesisBlockManager.ensure_genesis_block] INFO: Stored Genesis Coinbase TX ID: {coinbase_tx.tx_id}")

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

            # ✅ **Check if Genesis Block Already Exists in Storage**
            existing_genesis = self.block_storage.get_block_by_height(0)
            if existing_genesis:
                print(f"[GenesisBlockManager] ✅ INFO: Genesis block already exists with hash: {existing_genesis.mined_hash}")
                return existing_genesis

            # ✅ **Retrieve Miner Address from Default Keys**
            miner_address = self.key_manager.get_default_public_key(self.network, "miner")
            if not miner_address:
                print("[GenesisBlockManager] ⚠️ WARNING: Failed to retrieve miner address from default keys. Using fallback address.")
                miner_address = "UNKNOWN_MINER"

            print(f"[GenesisBlockManager] INFO: Using miner address: {miner_address}")

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

            # ✅ Create Coinbase Transaction
            coinbase_tx = CoinbaseTx(
                block_height=0,
                miner_address=miner_address,
                reward=Decimal(Constants.INITIAL_COINBASE_REWARD)
            )
            coinbase_tx.fee = Decimal("0")
            coinbase_tx.metadata = genesis_metadata

            if not hasattr(coinbase_tx, "tx_id") or not isinstance(coinbase_tx.tx_id, str):
                coinbase_tx.tx_id = Hashing.hash(json.dumps(coinbase_tx.to_dict(), sort_keys=True).encode()).hex()
                print(f"[GenesisBlockManager] INFO: Generated Coinbase TX ID: {coinbase_tx.tx_id}")

            # ✅ Use DifficultyConverter for standard difficulty
            difficulty_hex = DifficultyConverter.convert(Constants.GENESIS_TARGET)
            print(f"[GenesisBlockManager] INFO: Genesis difficulty target: {difficulty_hex}")

            # ✅ Initialize Genesis Block
            genesis_block = Block(
                index=0,
                previous_hash=Constants.ZERO_HASH,
                transactions=[coinbase_tx],
                difficulty=difficulty_hex,
                miner_address=miner_address,
                fees=Decimal(0),
                version=Constants.VERSION,
                timestamp=int(time.time()),
                nonce=0
            )

            print(f"[GenesisBlockManager] INFO: Genesis Block initialized with nonce {genesis_block.nonce}")

            # ✅ Mining Loop
            start_time = time.time()
            last_update_time = start_time

            while True:
                genesis_block.nonce += 1
                computed_hash = genesis_block.calculate_hash()
                if int(computed_hash, 16) < int(difficulty_hex, 16):
                    genesis_block.mined_hash = computed_hash
                    genesis_block.hash = computed_hash
                    print(f"[GenesisBlockManager] ✅ SUCCESS: Mined Genesis Block with nonce {genesis_block.nonce}")
                    break

                current_time = time.time()
                if current_time - last_update_time >= 1:
                    print(f"[GenesisBlockManager] LIVE: Nonce {genesis_block.nonce}, Elapsed Time: {int(current_time - start_time)}s")
                    last_update_time = current_time

            print("[GenesisBlockManager] INFO: Storing Genesis Block in BlockStorage...")
            self.block_storage.store_block(genesis_block)

            # ✅ Store Genesis Block Metadata to prevent missing Block 0 error
            self.block_storage.store_block_metadata(genesis_block)
            print("[GenesisBlockManager] ✅ SUCCESS: Stored Genesis block metadata.")


            print(f"[GenesisBlockManager] ✅ SUCCESS: Stored Genesis block with hash: {genesis_block.hash}")
            return genesis_block

        except Exception as e:
            print(f"[GenesisBlockManager] ❌ ERROR: Genesis block mining failed: {e}")
            fallback_genesis = Block(
                index=0,
                previous_hash=Constants.ZERO_HASH,
                transactions=[],
                difficulty=DifficultyConverter.convert(Constants.GENESIS_TARGET),
                miner_address="FALLBACK_MINER",
                fees=Decimal(0),
                version=Constants.VERSION,
                timestamp=int(time.time()),
                nonce=0
            )
            fallback_genesis.mined_hash = Constants.ZERO_HASH
            fallback_genesis.hash = Constants.ZERO_HASH
            print("[GenesisBlockManager] ⚠️ WARNING: Using fallback Genesis block due to mining failure.")
            return fallback_genesis


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
        - Block storage (LMDB)
        - Transaction index (tx_storage)
        If inconsistencies are found, resets storage.
        """
        try:
            print("[GenesisBlockManager.prevent_duplicate_genesis] INFO: Checking for existing Genesis block...")

            # ✅ **Check Block Storage (LMDB)**
            existing_block = self.block_storage.get_block_by_height(0)

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
        - Prevents duplicate entries and enforces data consistency.

        Args:
            genesis_block (Block): The Genesis block to store.

        Returns:
            Block: The stored Genesis block.
        """
        try:
            print("[GenesisBlockManager.store_genesis_block] INFO: Storing Genesis block...")

            # ✅ Validate Genesis Block Structure
            if not self.validate_genesis_block(genesis_block):
                raise ValueError("[GenesisBlockManager.store_genesis_block] ❌ ERROR: Genesis block failed validation.")

            # ✅ Check for Existing Genesis Block
            existing_block = self.block_storage.get_block_by_height(0)
            if existing_block:
                print(f"[GenesisBlockManager.store_genesis_block] ✅ INFO: Genesis block already exists with hash {existing_block.hash}")
                computed_hash = existing_block.calculate_hash()
                if existing_block.hash == computed_hash:
                    print("[GenesisBlockManager.store_genesis_block] ✅ SUCCESS: Stored Genesis Block is valid. Skipping re-storage.")
                    return existing_block
                else:
                    print("[GenesisBlockManager.store_genesis_block] ❌ ERROR: Stored Genesis Block hash mismatch!")
                    print(f"Expected: {computed_hash}, Found: {existing_block.hash}")
                    return None

            # ✅ Attempt Recovery from Metadata
            stored_metadata = self.block_storage.get_block_metadata(0)
            if stored_metadata:
                print("[GenesisBlockManager.store_genesis_block] INFO: Found stored Genesis metadata. Attempting recovery...")

                recovered_block = Block(
                    index=stored_metadata.get("index", 0),
                    previous_hash=stored_metadata.get("previous_hash", Constants.ZERO_HASH),
                    transactions=[],
                    difficulty=DifficultyConverter.convert(stored_metadata.get("difficulty", Constants.GENESIS_TARGET)),
                    miner_address=stored_metadata.get("miner_address", ""),
                    fees=stored_metadata.get("fees", Decimal(0)),
                    version=stored_metadata.get("version", Constants.VERSION),
                    timestamp=stored_metadata.get("timestamp", int(time.time())),
                    nonce=stored_metadata.get("nonce", 0)
                )
                recovered_block.hash = stored_metadata.get("hash", recovered_block.calculate_hash())

                if recovered_block.hash:
                    print(f"[GenesisBlockManager.store_genesis_block] ✅ SUCCESS: Recovered Genesis Block with hash: {recovered_block.hash}")
                    return recovered_block
                else:
                    print("[GenesisBlockManager.store_genesis_block] ❌ ERROR: Failed to recover Genesis Block from metadata.")

            # ✅ Serialize and Store Genesis Block
            genesis_block_serialized = json.dumps(genesis_block.to_dict(), sort_keys=True).encode("utf-8")
            with self.block_storage.env.begin(write=True) as txn:
                txn.put(f"block:0".encode(), genesis_block_serialized)
            print("[GenesisBlockManager.store_genesis_block] ✅ SUCCESS: Genesis block stored correctly in LMDB.")

            # ✅ Index Genesis Transactions
            print("[GenesisBlockManager.store_genesis_block] INFO: Indexing Genesis transactions in tx_storage...")
            for tx in genesis_block.transactions:
                if hasattr(tx, "tx_id") and hasattr(tx, "to_dict"):
                    tx_dict = tx.to_dict()
                    tx_inputs = tx_dict.get("inputs", [])
                    tx_outputs = tx_dict.get("outputs", [])

                    if not isinstance(tx_inputs, list) or not isinstance(tx_outputs, list):
                        print(f"[GenesisBlockManager.store_genesis_block] ⚠️ WARNING: Skipping invalid transaction format for {tx.tx_id}.")
                        continue

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

            # ✅ Verify Integrity After Storage
            stored_genesis_block = self.block_storage.get_block_by_height(0)
            if not stored_genesis_block or stored_genesis_block.hash != genesis_block.hash:
                raise ValueError("[GenesisBlockManager.store_genesis_block] ❌ ERROR: Genesis block verification failed after storage.")

            print(f"[GenesisBlockManager.store_genesis_block] ✅ SUCCESS: Genesis block stored with hash: {genesis_block.hash}")
            return genesis_block

        except Exception as e:
            print(f"[GenesisBlockManager.store_genesis_block] ❌ ERROR: Failed to store Genesis block: {e}")
            raise
