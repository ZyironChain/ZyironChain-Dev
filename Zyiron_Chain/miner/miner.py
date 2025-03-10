import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from decimal import Decimal
import time
import hashlib
import math
import random
import json
from threading import Lock

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.transactions.coinbase import CoinbaseTx
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.blockchain.block_manager import BlockManager
# Ensure this is at the very top of your script, before any other code
from Zyiron_Chain.miner.pow import PowManager
from Zyiron_Chain.storage.blockmetadata import BlockMetadata
import time
from threading import Lock
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.miner.pow import PowManager
from Zyiron_Chain.storage.blockmetadata import BlockMetadata
from Zyiron_Chain.blockchain.genesis_block import GenesisBlockManager
from Zyiron_Chain.storage.block_storage import WholeBlockData


import sys
import os
import time
import json
from threading import Lock
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.transactions.coinbase import CoinbaseTx
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.blockchain.block_manager import BlockManager
from Zyiron_Chain.miner.pow import PowManager
from Zyiron_Chain.storage.blockmetadata import BlockMetadata
from Zyiron_Chain.storage.block_storage import WholeBlockData  # ✅ Corrected Import
from Zyiron_Chain.blockchain.genesis_block import GenesisBlockManager

class Miner:
    def __init__(
        self,
        blockchain,
        block_manager,
        block_metadata,  
        block_storage,   # ✅ Uses WholeBlockData correctly
        transaction_manager,
        key_manager,
        mempool_storage,
        genesis_block_manager=None  
    ):
        """
        Initialize the Miner.

        :param blockchain: The blockchain instance.
        :param block_manager: The BlockManager instance.
        :param block_metadata: The BlockMetadata instance for LMDB interaction.
        :param block_storage: The WholeBlockData instance for full block data. ✅ Fixed
        :param transaction_manager: The transaction manager instance.
        :param key_manager: The key manager instance.
        :param mempool_storage: The mempool storage instance.
        :param genesis_block_manager: The GenesisBlockManager instance (optional).
        """
        print("[Miner.__init__] INFO: Initializing Miner...")

        # Validate required components
        if not blockchain:
            raise ValueError("[Miner.__init__] ERROR: `blockchain` instance is required.")
        if not block_manager:
            raise ValueError("[Miner.__init__] ERROR: `block_manager` instance is required.")
        if not block_metadata:
            raise ValueError("[Miner.__init__] ERROR: `block_metadata` instance is required.")
        if not block_storage:
            raise ValueError("[Miner.__init__] ERROR: `block_storage` (WholeBlockData) instance is required.")  
        if not transaction_manager:
            raise ValueError("[Miner.__init__] ERROR: `transaction_manager` instance is required.")
        if not key_manager:
            raise ValueError("[Miner.__init__] ERROR: `key_manager` instance is required.")
        if not mempool_storage:
            raise ValueError("[Miner.__init__] ERROR: `mempool_storage` instance is required.")

        # Assign instances
        self.blockchain = blockchain
        self.block_manager = block_manager
        self.block_metadata = block_metadata
        self.block_storage = block_storage  # ✅ Uses WholeBlockData
        self.transaction_manager = transaction_manager
        self.key_manager = key_manager
        self.mempool_storage = mempool_storage
        self.genesis_block_manager = genesis_block_manager  

        # Dynamically set current block size from Constants
        self.current_block_size = Constants.MIN_BLOCK_SIZE_BYTES / (1024 * 1024)
        self.network = Constants.NETWORK
        self.chain = self.block_manager.chain  

        # Initialize mining lock
        self._mining_lock = Lock()
        print("[Miner.__init__] INFO: Mining lock initialized.")

        print("[Miner.__init__] INFO: Miner initialized successfully.")
        print(f"[Miner.__init__] INFO: Current block size set to {self.current_block_size:.2f} MB from Constants.")
        print(f"[Miner.__init__] INFO: Miner initialized on {self.network.upper()}.")

    def _calculate_block_size(self):
        """
        Dynamically adjust block size based on mempool transaction volume and allocations from Constants.
        Ensures transactions are properly sorted into Standard and Smart allocations.
        """
        try:
            print("[Miner._calculate_block_size] INFO: Retrieving pending transactions from mempool...")

            pending_txs = self.transaction_manager.mempool.get_pending_transactions(
                block_size_mb=self.current_block_size
            )

            if not isinstance(pending_txs, list):
                print("[Miner._calculate_block_size] ERROR: Invalid transaction list retrieved from mempool.")
                return

            tx_count = len(pending_txs)
            print(f"[Miner._calculate_block_size] INFO: Retrieved {tx_count} transactions from mempool.")

            # ✅ **Fetch Constants for Block Sizing**
            min_size_bytes = Constants.MIN_BLOCK_SIZE_BYTES
            max_size_bytes = Constants.MAX_BLOCK_SIZE_BYTES

            min_tx_count = 1000
            max_tx_count = 50000

            # ✅ **Dynamically Adjust Block Size in Bytes**
            if tx_count <= min_tx_count:
                new_size_bytes = min_size_bytes
            elif tx_count >= max_tx_count:
                new_size_bytes = max_size_bytes
            else:
                scale = (tx_count - min_tx_count) / (max_tx_count - min_tx_count)
                new_size_bytes = min_size_bytes + (max_size_bytes - min_size_bytes) * scale

            # ✅ **Allocate Block Space Based on Constants**
            standard_allocation_bytes = new_size_bytes * Constants.BLOCK_ALLOCATION_STANDARD
            smart_allocation_bytes = new_size_bytes * Constants.BLOCK_ALLOCATION_SMART

            # ✅ **Separate Transactions by Type**
            standard_txs, smart_txs = [], []
            
            for tx in pending_txs:
                if not hasattr(tx, "tx_id") or not hasattr(tx, "size"):
                    print(f"[Miner._calculate_block_size] WARNING: Skipping invalid transaction: {tx}")
                    continue

                tx_id_bytes = tx.tx_id if isinstance(tx.tx_id, bytes) else tx.tx_id.encode()

                if any(tx_id_bytes.startswith(prefix.encode()) for prefix in Constants.TRANSACTION_MEMPOOL_MAP["STANDARD"]["prefixes"]):
                    standard_txs.append(tx)
                elif any(tx_id_bytes.startswith(prefix.encode()) for prefix in Constants.TRANSACTION_MEMPOOL_MAP["SMART"]["prefixes"]):
                    smart_txs.append(tx)

            # ✅ **Calculate Total Transaction Sizes (Bytes)**
            total_standard_size_bytes = sum(tx.size for tx in standard_txs if hasattr(tx, "size"))
            total_smart_size_bytes = sum(tx.size for tx in smart_txs if hasattr(tx, "size"))

            print(f"[Miner._calculate_block_size] INFO: Standard TXs: {len(standard_txs)}, Smart TXs: {len(smart_txs)}")
            print(f"[Miner._calculate_block_size] INFO: Total Standard TX Size: {total_standard_size_bytes} bytes")
            print(f"[Miner._calculate_block_size] INFO: Total Smart TX Size: {total_smart_size_bytes} bytes")

            # ✅ **Ensure Allocations Do Not Exceed Limits**
            if total_standard_size_bytes > standard_allocation_bytes:
                print(f"[Miner._calculate_block_size] WARNING: Standard transactions exceed allocation ({total_standard_size_bytes} bytes). Limiting to {standard_allocation_bytes} bytes.")
                total_standard_size_bytes = standard_allocation_bytes

            if total_smart_size_bytes > smart_allocation_bytes:
                print(f"[Miner._calculate_block_size] WARNING: Smart transactions exceed allocation ({total_smart_size_bytes} bytes). Limiting to {smart_allocation_bytes} bytes.")
                total_smart_size_bytes = smart_allocation_bytes

            final_block_size_bytes = total_standard_size_bytes + total_smart_size_bytes

            # ✅ **Set Final Block Size Within Allowed Bounds**
            self.current_block_size = max(min_size_bytes, min(final_block_size_bytes, max_size_bytes))

            print(f"[Miner._calculate_block_size] SUCCESS: Block size set to {self.current_block_size} bytes based on mempool transactions.")

        except Exception as e:
            print(f"[Miner._calculate_block_size] ERROR: Exception during block size calculation: {e}")
            raise


    def _create_coinbase(self, miner_address, fees):
        """
        Creates a coinbase transaction for miners using single SHA3-384 hashing.
        - Uses a **fixed block reward** instead of halving.
        - If `MAX_SUPPLY` is reached, only transaction fees are rewarded.
        - Ensures a minimum payout using `Constants.MIN_TRANSACTION_FEE`.
        - Stores transaction ID as **bytes** instead of hex string.
        """
        try:
            print("[Miner._create_coinbase] INFO: Initiating Coinbase transaction creation...")

            # ✅ **Use Fixed Block Reward (No Halving)**
            block_reward = Decimal(Constants.INITIAL_COINBASE_REWARD)

            # ✅ **Get Total Mined Supply from BlockMetadata**
            try:
                total_mined = self.block_metadata.get_total_mined_supply()
            except Exception as e:
                print(f"[Miner._create_coinbase] ERROR: Failed to retrieve total mined supply: {e}")
                return None

            print(f"[Miner._create_coinbase] INFO: Total mined supply: {total_mined} ZYC")

            # ✅ **Check if Max Supply is Reached**
            if Constants.MAX_SUPPLY is not None and total_mined >= Decimal(Constants.MAX_SUPPLY):
                print("[Miner._create_coinbase] INFO: Max supply reached; only transaction fees will be rewarded.")
                block_reward = Decimal("0")

            # ✅ **Calculate Final Reward (Including Fees)**
            total_reward = max(block_reward + fees, Decimal(Constants.MIN_TRANSACTION_FEE))

            print(f"[Miner._create_coinbase] INFO: Final Coinbase Reward: {total_reward} ZYC (Fees: {fees}, Reward: {block_reward})")

            # ✅ **Create Coinbase Transaction**
            coinbase_tx = CoinbaseTx(
                block_height=len(self.block_manager.chain),
                miner_address=miner_address,
                reward=total_reward
            )
            coinbase_tx.fee = Decimal("0")

            # ✅ **Generate Transaction ID Using SHA3-384 & Store as Bytes**
            tx_id_bytes = Hashing.hash(coinbase_tx.calculate_hash().encode())
            coinbase_tx.tx_id = tx_id_bytes  # ✅ Store as bytes instead of hex string

            print(f"[Miner._create_coinbase] SUCCESS: Coinbase transaction created with TX ID (bytes): {tx_id_bytes[:12]}")
            return coinbase_tx

        except Exception as e:
            print(f"[Miner._create_coinbase] ERROR: Coinbase creation failed: {e}")
            raise


    def _calculate_block_reward(self):
        """
        Calculate the current block reward using a **fixed supply model**.
        - Uses a **constant block reward** (`INITIAL_COINBASE_REWARD`).
        - If `MAX_SUPPLY` is reached, only transaction fees are rewarded.
        - Ensures a minimum payout using `MIN_TRANSACTION_FEE`.
        """
        try:
            print("[Miner._calculate_block_reward] INFO: Initiating block reward calculation...")

            # ✅ **Use Fixed Block Reward**
            block_reward = Decimal(Constants.INITIAL_COINBASE_REWARD)

            # ✅ **Retrieve Total Mined Supply from BlockMetadata**
            try:
                total_mined = self.block_metadata.get_total_mined_supply()
            except Exception as e:
                print(f"[Miner._calculate_block_reward] ERROR: Failed to retrieve total mined supply: {e}")
                return Decimal("0")

            print(f"[Miner._calculate_block_reward] INFO: Total Mined Supply: {total_mined} ZYC (Max: {Constants.MAX_SUPPLY})")

            # ✅ **Check if Max Supply is Reached**
            if Constants.MAX_SUPPLY is not None and total_mined >= Decimal(Constants.MAX_SUPPLY):
                print("[Miner._calculate_block_reward] INFO: Max supply reached; no new coins rewarded.")
                return Decimal("0")

            # ✅ **Ensure Reward Does Not Go Below Minimum Transaction Fee**
            final_reward = max(block_reward, Decimal(Constants.MIN_TRANSACTION_FEE))

            print(f"[Miner._calculate_block_reward] SUCCESS: Final Block Reward: {final_reward} ZYC")
            return final_reward

        except Exception as e:
            print(f"[Miner._calculate_block_reward] ERROR: Unexpected error during reward calculation: {e}")
            return Decimal("0")



    def _validate_coinbase(self, tx):
        """
        Ensure the coinbase transaction follows protocol rules:
        - No inputs, exactly one output, type is "COINBASE", fee is zero.
        - Uses single SHA3-384 hashing for transaction ID.
        - Ensures TX ID is stored as bytes, not a hex string.
        """
        from Zyiron_Chain.transactions.coinbase import CoinbaseTx  # ✅ Fixed import

        try:
            tx_id_display = tx.tx_id.hex()[:12] if isinstance(tx.tx_id, bytes) else getattr(tx, "tx_id", "UNKNOWN")
            print(f"[Miner._validate_coinbase] INFO: Validating Coinbase transaction with TX ID: {tx_id_display}")

            # ✅ **Check if Transaction is a Valid CoinbaseTx**
            if not isinstance(tx, CoinbaseTx):
                print(f"[Miner._validate_coinbase] ERROR: Transaction is not a valid CoinbaseTx instance.")
                return False

            # ✅ **Ensure TX ID is Properly Stored as Bytes**
            if not hasattr(tx, "tx_id") or not isinstance(tx.tx_id, bytes):
                print(f"[Miner._validate_coinbase] ERROR: Invalid Coinbase transaction ID format. TX ID must be bytes.")
                return False

            # ✅ **Validate Coinbase Transaction Hashing & Ensure Bytes Storage**
            expected_tx_id = Hashing.hash(tx.calculate_hash().encode())
            if tx.tx_id != expected_tx_id:
                print(f"[Miner._validate_coinbase] ERROR: Coinbase TX ID mismatch.\nExpected: {expected_tx_id.hex()}\nFound: {tx.tx_id.hex()}")
                return False

            # ✅ **Check for No Inputs and Exactly One Output**
            if len(tx.inputs) != 0:
                print(f"[Miner._validate_coinbase] ERROR: Coinbase transaction must have no inputs.")
                return False

            if len(tx.outputs) != 1:
                print(f"[Miner._validate_coinbase] ERROR: Coinbase transaction must have exactly one output. Found: {len(tx.outputs)}")
                return False

            # ✅ **Validate Output Structure**
            output = tx.outputs[0]
            if not isinstance(output, dict) or "amount" not in output or "script_pub_key" not in output:
                print(f"[Miner._validate_coinbase] ERROR: Invalid output structure in Coinbase transaction.")
                return False

            # ✅ **Ensure Fee is Zero**
            if tx.fee != Decimal(0):
                print(f"[Miner._validate_coinbase] ERROR: Coinbase transaction must have a fee of 0. Found: {tx.fee}")
                return False

            print(f"[Miner._validate_coinbase] SUCCESS: Coinbase transaction {tx.tx_id.hex()[:12]} validated successfully.")
            return True

        except Exception as e:
            print(f"[Miner._validate_coinbase] ERROR: Coinbase validation failed: {e}")
            return False

        
    def mining_loop(self, network=None):
        """
        Continuous mining loop:
        - Mines new blocks until interrupted.
        - Ensures Genesis block exists.
        - Dynamically adjusts difficulty.
        - Uses detailed print statements for progress and debugging.
        - Stops mining on errors.
        - Stores tx_id as bytes instead of string hex format.
        """
        network = network or Constants.NETWORK
        print(f"\n[Miner.mining_loop] INFO: Starting mining loop on {network.upper()}. Press Ctrl+C to stop.\n")

        # ✅ **Ensure the Genesis Block Exists**
        if not self.block_manager.chain:
            print(f"[Miner.mining_loop] WARNING: Blockchain is empty! Ensuring Genesis block exists on {network.upper()}...")

            self.genesis_block_manager.ensure_genesis_block()
            genesis_block = self.block_metadata.get_latest_block()

            if not genesis_block:
                print(f"[Miner.mining_loop] ERROR: Genesis Block not found after creation attempt on {network.upper()}! Stopping mining.")
                return

            # ✅ **Ensure Genesis Block Meets Difficulty Target**
            if int.from_bytes(genesis_block.tx_id, "big") >= genesis_block.difficulty:
                print(f"[Miner.mining_loop] ERROR: Genesis Block validation failed (invalid difficulty) on {network.upper()}! Stopping mining.")
                return

            self.block_manager.chain.append(genesis_block)
            print(f"[Miner.mining_loop] INFO: Genesis Block added successfully: {genesis_block.tx_id.hex()[:12]}...")

        block_height = self.block_manager.chain[-1].index + 1

        while True:
            try:
                print(f"\n[Miner.mining_loop] INFO: Starting to mine block at height {block_height} on {network.upper()}.")

                # ✅ **Mine a New Block**
                block = self.mine_block(network)

                if not block:
                    print(f"[Miner.mining_loop] ERROR: Failed to mine a new block at height {block_height} on {network.upper()}. Stopping mining.")
                    break

                # ✅ **Validate Mined Block Before Storing**
                if not self.blockchain.validate_block(block):
                    print(f"[Miner.mining_loop] ERROR: Mined block at height {block.index} is invalid on {network.upper()}. Stopping mining.")
                    break

                # ✅ **Ensure the Previous Block is Valid Before Adding**
                last_block = self.block_manager.chain[-1] if self.block_manager.chain else None
                if last_block and int.from_bytes(last_block.tx_id, "big") >= last_block.difficulty:
                    print(f"[Miner.mining_loop] ERROR: Last block in chain is invalid. Stopping mining.")
                    break

                # ✅ **Store the Valid Block**
                self.block_metadata.store_block(block, block.difficulty)
                self.block_manager.chain.append(block)

                # ✅ **Check Total Mined Supply**
                total_supply = self.block_metadata.get_total_mined_supply()
                print(f"[Miner.mining_loop] INFO: Total mined supply: {total_supply} (Max: {Constants.MAX_SUPPLY}).")

                # ✅ **Dynamically Adjust Difficulty**
                new_difficulty = self.block_manager.calculate_target()
                print(f"[Miner.mining_loop] INFO: Difficulty adjusted on {network.upper()} to: {hex(new_difficulty)}")

                block_height += 1

            except KeyboardInterrupt:
                print(f"\n[Miner.mining_loop] INFO: Mining loop on {network.upper()} interrupted by user.")
                break

            except Exception as e:
                print(f"[Miner.mining_loop] ERROR: Mining encountered an unexpected error on {network.upper()}: {e}")
                if block:
                    print(f"[Miner.mining_loop] ERROR: Block {block.index} | Hash: {block.tx_id.hex()[:12]}...")

                last_block = self.block_manager.get_latest_block()
                if last_block:
                    print(f"[Miner.mining_loop] INFO: Last valid block hash: {last_block.tx_id.hex()[:12]}...")
                else:
                    print("[Miner.mining_loop] ERROR: No valid blocks found in the chain. Stopping mining.")
                break






    def validate_new_block(self, new_block):
        """
        Validate a newly mined block:
        - Ensure its hash meets the proof-of-work target using single SHA3-384.
        - Validate the coinbase transaction.
        - Validate subsequent transactions via the transaction manager.
        - Verify block timestamp consistency.
        - Ensure block size does not exceed max limit.
        - Enforce max supply limit if reached.
        - Validate Genesis Block after retrieval instead of before.
        - Ensure difficulty is stored in bytes.
        """
        try:
            print(f"[Miner.validate_new_block] INFO: Validating new block at height {new_block.index}...")

            # ✅ **Check Required Attributes**
            if not hasattr(new_block, "tx_id") or not hasattr(new_block, "difficulty"):
                print("[Miner.validate_new_block] ERROR: Block object is missing required attributes.")
                return False

            if not isinstance(new_block.transactions, list):
                print("[Miner.validate_new_block] ERROR: Transactions must be a list.")
                return False

            # ✅ **Ensure Block Hash Meets Proof-of-Work Target**
            try:
                block_hash_int = int.from_bytes(new_block.tx_id, "big")
            except ValueError:
                print(f"[Miner.validate_new_block] ERROR: Block {new_block.index} has an invalid hash format.")
                return False

            difficulty_int = int.from_bytes(new_block.difficulty, "big") if isinstance(new_block.difficulty, bytes) else new_block.difficulty

            if block_hash_int >= difficulty_int:
                print(f"[Miner.validate_new_block] ERROR: Invalid Proof-of-Work for block {new_block.index}.")
                return False

            print(f"[Miner.validate_new_block] INFO: Proof-of-Work passed for block {new_block.index}.")

            # ✅ **Ensure Block Starts with a Valid Coinbase Transaction**
            if not new_block.transactions or not isinstance(new_block.transactions[0], CoinbaseTx):
                print("[Miner.validate_new_block] ERROR: Block must start with a valid Coinbase transaction.")
                return False

            coinbase_tx = new_block.transactions[0]
            if not self._validate_coinbase(coinbase_tx):
                print("[Miner.validate_new_block] ERROR: Invalid coinbase transaction in new block.")
                return False

            print("[Miner.validate_new_block] INFO: Coinbase transaction validated.")

            # ✅ **Check Total Mined Supply Before Accepting the Block**
            try:
                total_mined = self.block_metadata.get_total_mined_supply()
            except Exception as e:
                print(f"[Miner.validate_new_block] ERROR: Failed to retrieve total mined supply: {e}")
                return False

            print(f"[Miner.validate_new_block] INFO: Total Mined Supply: {total_mined} ZYC (Max: {Constants.MAX_SUPPLY})")

            if Constants.MAX_SUPPLY is not None and total_mined >= Decimal(Constants.MAX_SUPPLY):
                print("[Miner.validate_new_block] ERROR: Max supply reached. Rejecting new block.")
                return False

            # ✅ **Validate Block Timestamp**
            prev_block = self.block_manager.chain[-1] if self.block_manager.chain else None
            if prev_block:
                try:
                    if int(new_block.timestamp) <= int(prev_block.timestamp):
                        print(f"[Miner.validate_new_block] ERROR: Block {new_block.index} timestamp is invalid; must be greater than previous block.")
                        return False
                except ValueError:
                    print(f"[Miner.validate_new_block] ERROR: Block {new_block.index} has an invalid timestamp format.")
                    return False

            max_time_drift = 7200
            if new_block.timestamp > int(time.time()) + max_time_drift:
                print(f"[Miner.validate_new_block] ERROR: Block {new_block.index} timestamp exceeds maximum allowable drift.")
                return False

            print(f"[Miner.validate_new_block] INFO: Timestamp validation passed for block {new_block.index}.")

            # ✅ **Validate Block Size**
            try:
                total_block_size = sum(len(json.dumps(tx.to_dict()).encode()) for tx in new_block.transactions)
            except (TypeError, AttributeError) as e:
                print(f"[Miner.validate_new_block] ERROR: Failed to calculate block size: {e}")
                return False

            if total_block_size > Constants.MAX_BLOCK_SIZE_BYTES:
                print(f"[Miner.validate_new_block] ERROR: Block {new_block.index} exceeds max block size limit: {total_block_size} bytes.")
                return False

            print(f"[Miner.validate_new_block] INFO: Block size validation passed for block {new_block.index}.")

            # ✅ **Validate Transactions in the Block**
            for tx in new_block.transactions[1:]:
                try:
                    if isinstance(tx.tx_id, bytes):
                        tx.tx_id = tx.tx_id.decode("utf-8")

                    single_hashed_tx_id = Hashing.hash(tx.tx_id.encode()).digest()

                    if not self.transaction_manager.validate_transaction(tx):
                        print(f"[Miner.validate_new_block] ERROR: Invalid transaction in block {new_block.index}: {single_hashed_tx_id.hex()}")
                        return False
                except AttributeError as e:
                    print(f"[Miner.validate_new_block] ERROR: Transaction missing required attributes: {e}")
                    return False

            print(f"[Miner.validate_new_block] SUCCESS: Block {new_block.index} successfully validated.")
            return True

        except Exception as e:
            print(f"[Miner.validate_new_block] ERROR: Unexpected error during block validation: {e}")
            return False



    @property
    def mining_lock(self):
        """
        Property to ensure thread-safe mining operations.
        """
        if not hasattr(self, "_mining_lock"):
            print("[Miner.mining_lock] INFO: Initializing mining lock.")
            self._mining_lock = Lock()
        return self._mining_lock




    def mine_block(self, network=Constants.NETWORK):
        """
        Mines a new block using Proof-of-Work with dynamically adjusted difficulty.
        - Calls `GenesisBlockManager.ensure_genesis_block()` if no previous block is found.
        - Uses single SHA3-384 hashing for mining.
        - Retrieves transactions from mempool and includes coinbase transaction.
        - Enforces max supply constraints.
        - Checks SHA3-384 hash length.
        - Ensures block timestamp validation does not exceed 7200s.
        """
        with self.mining_lock:
            try:
                print("[Miner.mine_block] START: Initiating mining procedure.")
                start_time = time.time()

                # ✅ **Ensure `BlockMetadata` is Properly Initialized**
                if not hasattr(self, "block_metadata") or not self.block_metadata:
                    print("[Miner.mine_block] ERROR: `block_metadata` not initialized. Cannot retrieve latest block.")
                    return None

                # ✅ **Get the Latest Block**
                print("[Miner.mine_block] INFO: Checking for latest block in BlockMetadata.")
                last_block = self.block_metadata.get_latest_block()

                if last_block:
                    last_block = Block.from_dict(last_block)
                else:
                    print("[Miner.mine_block] WARNING: No previous block found. Ensuring Genesis block exists.")

                    # ✅ **Ensure `genesis_block_manager` is Initialized**
                    if not hasattr(self, "genesis_block_manager") or not self.genesis_block_manager:
                        print("[Miner.mine_block] ERROR: `genesis_block_manager` not initialized. Stopping mining.")
                        return None

                    print("[Miner.mine_block] INFO: Creating Genesis block using GenesisBlockManager.")
                    self.genesis_block_manager.ensure_genesis_block()

                    # ✅ **Retrieve the Newly Created Genesis Block**
                    last_block = self.block_metadata.get_latest_block()
                    if not last_block:
                        print("[Miner.mine_block] ERROR: Failed to retrieve or create Genesis block. Stopping mining.")
                        return None
                    last_block = Block.from_dict(last_block)

                block_height = last_block.index + 1
                print(f"[Miner.mine_block] INFO: Preparing new block at height {block_height}.")

                # ✅ **Adjust Difficulty Based on the Latest Block**
                print("[Miner.mine_block] INFO: Calculating difficulty target.")
                current_target = self.block_manager.calculate_target()
                current_target = max(min(current_target, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)
                print(f"[Miner.mine_block] INFO: Adjusted difficulty target set to {hex(current_target)}.")

                # ✅ **Retrieve Miner Address**
                print("[Miner.mine_block] INFO: Retrieving miner address.")
                miner_address = self.key_manager.get_default_public_key(network, "miner")
                if not miner_address:
                    print("[Miner.mine_block] ERROR: Failed to retrieve miner address. Stopping mining.")
                    return None
                print(f"[Miner.mine_block] INFO: Miner address retrieved: {miner_address}.")

                # ✅ **Calculate Block Size Based on Mempool Load**
                print("[Miner.mine_block] INFO: Calculating block size based on mempool load.")
                self._calculate_block_size()
                print(f"[Miner.mine_block] INFO: Current block size set to {self.current_block_size:.2f} MB.")

                # ✅ **Retrieve Pending Transactions from Mempool**
                print("[Miner.mine_block] INFO: Retrieving pending transactions from mempool.")
                pending_txs = self.transaction_manager.mempool.get_pending_transactions(
                    block_size_mb=self.current_block_size
                ) or []
                print(f"[Miner.mine_block] INFO: Retrieved {len(pending_txs)} pending transactions.")

                total_fees = sum(tx["fee"] for tx in pending_txs if "fee" in tx)
                print(f"[Miner.mine_block] INFO: Total fees for this block: {total_fees} ZYC.")

                # ✅ **Check if Max Supply is Reached**
                try:
                    total_mined = self.block_metadata.get_total_mined_supply()
                except Exception as e:
                    print(f"[Miner.mine_block] ERROR: Failed to retrieve total mined supply: {e}")
                    return None

                print(f"[Miner.mine_block] INFO: Total Mined Supply: {total_mined} ZYC (Max: {Constants.MAX_SUPPLY})")

                if Constants.MAX_SUPPLY is not None and total_mined >= Decimal(Constants.MAX_SUPPLY):
                    print("[Miner.mine_block] INFO: Max supply reached; only transaction fees will be rewarded.")

                # ✅ **Create Coinbase Transaction**
                print("[Miner.mine_block] INFO: Creating coinbase transaction.")
                coinbase_tx = self._create_coinbase(miner_address, total_fees)
                valid_txs = [coinbase_tx] + pending_txs
                print(f"[Miner.mine_block] INFO: Coinbase transaction created with TX ID: {coinbase_tx.tx_id}.")

                # ✅ **Create New Block**
                print("[Miner.mine_block] INFO: Creating new block.")
                new_block = Block(
                    index=block_height,
                    previous_hash=last_block.tx_id,
                    transactions=valid_txs,
                    timestamp=int(time.time()),
                    nonce=0,
                    difficulty=current_target,
                    miner_address=miner_address
                )

                # ✅ **Ensure SHA3-384 Hash Length is Correct**
                if len(new_block.tx_id) != 48:
                    print(f"[Miner.mine_block] ERROR: Invalid SHA3-384 hash length for block {block_height}. Stopping mining.")
                    return None

                print(f"[Miner.mine_block] INFO: New block created with index {block_height}.")

                # ✅ **Perform Proof-of-Work**
                print("[Miner.mine_block] INFO: Starting Proof-of-Work.")
                final_hash, final_nonce, attempts = self.pow_manager.perform_pow(new_block)
                print(f"[Miner.mine_block] INFO: Proof-of-Work completed after {attempts} attempts. Final hash: {final_hash[:12]}...")

                # ✅ **Validate Proof-of-Work Before Storing**
                if int(final_hash, 16) >= new_block.difficulty:
                    print("[Miner.mine_block] ERROR: Invalid Proof-of-Work. Hash does not meet difficulty target. Stopping mining.")
                    return None

                # ✅ **Update Block with Final Hash and Nonce**
                new_block.tx_id = final_hash
                new_block.nonce = final_nonce
                print(f"[Miner.mine_block] INFO: Block updated with final hash and nonce {final_nonce}.")

                # ✅ **Validate Block Timestamp (Ensure It Does Not Exceed 7200s)**
                max_time_drift = 7200
                if new_block.timestamp > int(time.time()) + max_time_drift:
                    print(f"[Miner.mine_block] ERROR: Block {new_block.index} timestamp exceeds maximum allowable drift of {max_time_drift}s. Stopping mining.")
                    return None

                print("[Miner.mine_block] INFO: Timestamp validation passed.")

                # ✅ **Store Block Using BlockMetadata**
                print("[Miner.mine_block] INFO: Storing block in BlockMetadata.")
                self.block_metadata.store_block(new_block, new_block.difficulty)
                self.chain.append(new_block)
                print(f"[Miner.mine_block] INFO: Block {block_height} added to the chain.")

                elapsed_time = int(time.time() - start_time)
                print(f"[Miner.mine_block] SUCCESS: Block {block_height} mined! Final TX ID: {new_block.tx_id[:12]}... | Time Taken: {elapsed_time}s.")
                return new_block

            except Exception as e:
                print(f"[Miner.mine_block] ERROR: Mining failed: {e}. Stopping mining.")
                return None
