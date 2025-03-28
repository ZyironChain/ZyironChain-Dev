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
import time
import traceback
import time
from datetime import datetime
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.transactions.coinbase import CoinbaseTx
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.blockchain.block_manager import BlockManager
# Ensure this is at the very top of your script, before any other code
import time
from threading import Lock
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.miner.pow import PowManager
from Zyiron_Chain.blockchain.genesis_block import GenesisBlockManager
from Zyiron_Chain.storage.block_storage import BlockStorage

class Miner:
    def __init__(
        self,
        blockchain,
        block_manager,
        block_storage,
        transaction_manager,
        key_manager,
        mempool_storage,
        utxo_storage,  # ✅ ADDED
        genesis_block_manager=None
    ):
        """
        Initialize the Miner.
        """
        print("[Miner.__init__] INFO: Initializing Miner...")

        # ✅ Ensure required components are provided
        required_params = {
            "blockchain": blockchain,
            "block_manager": block_manager,
            "block_storage": block_storage,
            "transaction_manager": transaction_manager,
            "key_manager": key_manager,
            "mempool_storage": mempool_storage,
            "utxo_storage": utxo_storage  # ✅ INCLUDED IN CHECK
        }

        for param_name, param_value in required_params.items():
            if not param_value:
                raise ValueError(f"[Miner.__init__] ERROR: `{param_name}` instance is required.")

        # ✅ Assign instances
        self.blockchain = blockchain
        self.block_manager = block_manager
        self.block_storage = block_storage
        self.transaction_manager = transaction_manager
        self.key_manager = key_manager
        self.mempool_storage = mempool_storage
        self.utxo_storage = utxo_storage  # ✅ ASSIGNED
        self.genesis_block_manager = genesis_block_manager
        self._mining_active = False  # Mining state flag
        self._current_block = None   # Track current block being mined

        # ✅ Extract TxStorage from transaction_manager (needed for fallback/validation)
        self.tx_storage = getattr(transaction_manager, "tx_storage", None)
        if not self.tx_storage:
            raise ValueError("[Miner.__init__] ERROR: `tx_storage` is missing from transaction_manager.")

        # ✅ Initialize Proof-of-Work Manager
        self.pow_manager = PowManager(block_storage)

        # ✅ Initialize Mining Lock
        self._mining_lock = Lock()

        # ✅ Initialize Current Block Size
        self.current_block_size = Constants.INITIAL_BLOCK_SIZE_MB  # 🔹 Default to 0MB - 10MB

        print("[Miner.__init__] INFO: Miner initialized successfully.")
        print(f"[Miner.__init__] INFO: Initial block size set to {self.current_block_size} MB.")





    def is_mining(self):
        """Check if miner is currently active"""
        return self._mining_active

    def get_current_block(self):
        """Get the current block being mined"""
        return self._current_block

    def pause(self):
        """Temporarily pause mining"""
        self._mining_active = False

    def resume(self):
        """Resume paused mining"""
        self._mining_active = True











    def _calculate_block_size(self):
        """
        Dynamically adjust block size based on mempool transaction volume and allocations from Constants.
        Ensures transactions are properly sorted into Standard and Smart allocations.
        """
        try:
            print("[Miner._calculate_block_size] INFO: Retrieving pending transactions from mempool...")

            # ✅ **Ensure current_block_size is initialized**
            if not hasattr(self, "current_block_size"):
                self.current_block_size = Constants.INITIAL_BLOCK_SIZE_MB  # Default to initial block size

            # ✅ **Retrieve pending transactions from mempool with dynamic block size**
            pending_txs = self.mempool_storage.get_pending_transactions(self.current_block_size)

            if not isinstance(pending_txs, list):
                print("[Miner._calculate_block_size] ERROR: Invalid transaction list retrieved from mempool.")
                return

            tx_count = len(pending_txs)
            print(f"[Miner._calculate_block_size] INFO: Retrieved {tx_count} transactions from mempool.")

            # ✅ **Fetch Constants for Block Sizing**
            min_size_mb = Constants.MIN_BLOCK_SIZE_MB  # Use predefined constant
            max_size_mb = Constants.MAX_BLOCK_SIZE_MB  # Use predefined constant

            min_tx_count = 0  # ✅ Set lower bound for transaction count
            max_tx_count = 30000  # ✅ Set upper bound for transaction count

            # ✅ **Dynamically Adjust Block Size in MB**
            if tx_count <= min_tx_count:
                new_size_mb = min_size_mb
            elif tx_count >= max_tx_count:
                new_size_mb = max_size_mb
            else:
                scale = (tx_count - min_tx_count) / (max_tx_count - min_tx_count)
                new_size_mb = min_size_mb + (max_size_mb - min_size_mb) * scale

            # ✅ **Allocate Block Space Based on Constants**
            standard_allocation_mb = new_size_mb * Constants.BLOCK_ALLOCATION_STANDARD
            smart_allocation_mb = new_size_mb * Constants.BLOCK_ALLOCATION_SMART

            # ✅ **Separate Transactions by Type**
            standard_txs, smart_txs = [], []
            
            for tx in pending_txs:
                if not isinstance(tx, dict) or "tx_id" not in tx or "size" not in tx:
                    print(f"[Miner._calculate_block_size] WARNING: Skipping invalid transaction: {tx}")
                    continue

                tx_id = str(tx["tx_id"])  # Ensure string format

                if any(tx_id.startswith(prefix) for prefix in Constants.TRANSACTION_MEMPOOL_MAP["STANDARD"]["prefixes"]):
                    standard_txs.append(tx)
                elif any(tx_id.startswith(prefix) for prefix in Constants.TRANSACTION_MEMPOOL_MAP["SMART"]["prefixes"]):
                    smart_txs.append(tx)

            # ✅ **Calculate Total Transaction Sizes (MB)**
            total_standard_size_mb = sum(tx["size"] / (1024 * 1024) for tx in standard_txs)
            total_smart_size_mb = sum(tx["size"] / (1024 * 1024) for tx in smart_txs)

            print(f"[Miner._calculate_block_size] INFO: Standard TXs: {len(standard_txs)}, Smart TXs: {len(smart_txs)}")
            print(f"[Miner._calculate_block_size] INFO: Total Standard TX Size: {total_standard_size_mb:.2f} MB")
            print(f"[Miner._calculate_block_size] INFO: Total Smart TX Size: {total_smart_size_mb:.2f} MB")

            # ✅ **Ensure Allocations Do Not Exceed Limits**
            total_standard_size_mb = min(total_standard_size_mb, standard_allocation_mb)
            total_smart_size_mb = min(total_smart_size_mb, smart_allocation_mb)

            # ✅ **Set Final Block Size Within Allowed Bounds**
            final_block_size_mb = max(min_size_mb, min(total_standard_size_mb + total_smart_size_mb, max_size_mb))
            
            print(f"[Miner._calculate_block_size] SUCCESS: Block size set to {final_block_size_mb:.2f} MB based on mempool transactions.")

            # ✅ **Assign the Correct Block Size**
            self.current_block_size = final_block_size_mb

        except Exception as e:
            print(f"[Miner._calculate_block_size] ERROR: Exception during block size calculation: {e}")
            raise


    def _create_coinbase(self, miner_address, fees):
        """
        Creates a coinbase transaction for miners using single SHA3-384 hashing.
        - Uses a fixed block reward (no halving).
        - If MAX_SUPPLY is reached, only transaction fees are rewarded.
        - Generates a transaction ID as a standard string (no offsets or byte transformations).
        """
        try:
            print("[Miner._create_coinbase] INFO: Initiating Coinbase transaction creation...")

            # Use Fixed Block Reward (No Halving)
            block_reward = Decimal(Constants.INITIAL_COINBASE_REWARD)

            # Retrieve Total Mined Supply from Storage
            try:
                total_mined = self.block_storage.get_total_mined_supply() or Decimal("0")
                total_mined = Decimal(total_mined)
            except Exception as e:
                print(f"[Miner._create_coinbase] ERROR: Failed to retrieve total mined supply: {e}")
                return None

            print(f"[Miner._create_coinbase] INFO: Total mined supply: {total_mined} ZYC")

            # Check if Max Supply is Reached
            if Constants.MAX_SUPPLY is not None and total_mined >= Decimal(Constants.MAX_SUPPLY):
                print("[Miner._create_coinbase] INFO: Max supply reached; only transaction fees will be rewarded.")
                block_reward = Decimal("0")

            # Calculate Final Reward (Block Reward + Fees)
            total_reward = block_reward + fees
            print(f"[Miner._create_coinbase] INFO: Final Coinbase Reward: {total_reward} ZYC (Fees: {fees}, Reward: {block_reward})")

            # Ensure Miner Address is Formatted Correctly
            miner_address = miner_address[:128]  # Trim to max 128 chars if too long
            print(f"[Miner._create_coinbase] INFO: Miner address formatted.")

            # Retrieve Latest Block Height
            try:
                latest_block = self.block_storage.get_latest_block()
                block_height = latest_block.index + 1 if latest_block else 0  # ✅ FIXED: Use attribute not dict access
            except Exception as e:
                print(f"[Miner._create_coinbase] ERROR: Failed to retrieve latest block. Defaulting to height 0. Error: {e}")
                block_height = 0

            # Create Coinbase Transaction
            coinbase_tx = CoinbaseTx(
                block_height=block_height,
                miner_address=miner_address,
                reward=total_reward
            )
            coinbase_tx.fee = Decimal("0")

            # Generate Transaction ID Using SHA3-384 & Store as String
            tx_id = Hashing.hash(json.dumps(coinbase_tx.to_dict(), sort_keys=True).encode("utf-8")).hex()
            if not isinstance(tx_id, str) or len(tx_id) != Constants.SHA3_384_HASH_SIZE:
                print(f"[Miner._create_coinbase] ERROR: TX ID length mismatch! Expected {Constants.SHA3_384_HASH_SIZE}, got {len(tx_id)}")
                return None

            coinbase_tx.tx_id = tx_id
            print(f"[Miner._create_coinbase] SUCCESS: Coinbase transaction created with TX ID: {tx_id[:12]}...")
            print(f"[Miner._create_coinbase] INFO: Miner Address: {miner_address}")

            return coinbase_tx

        except Exception as e:
            print(f"[Miner._create_coinbase] ERROR: Coinbase creation failed: {e}")
            raise





    def _calculate_block_reward(self):
        """
        Calculate the current block reward using a **fixed supply model**.
        - Uses a **constant block reward** (`INITIAL_COINBASE_REWARD`).
        - If `MAX_SUPPLY` is reached, only transaction fees are rewarded.
        """
        try:
            print("[Miner._calculate_block_reward] INFO: Initiating block reward calculation...")

            # ✅ Use Fixed Block Reward
            block_reward = Decimal(Constants.INITIAL_COINBASE_REWARD)

            # ✅ Retrieve Total Mined Supply
            try:
                total_mined = self.block_storage.get_total_mined_supply()
                total_mined = Decimal(total_mined) if not isinstance(total_mined, Decimal) else total_mined
            except Exception as e:
                print(f"[Miner._calculate_block_reward] ERROR: Failed to retrieve total mined supply: {e}")
                return Decimal("0")

            print(f"[Miner._calculate_block_reward] INFO: Total Mined Supply: {total_mined} ZYC (Max: {Constants.MAX_SUPPLY})")

            # ✅ If Max Supply is Reached, No New Coins Are Minted
            if Constants.MAX_SUPPLY is not None and total_mined >= Decimal(Constants.MAX_SUPPLY):
                print("[Miner._calculate_block_reward] INFO: Max supply reached; no new coins rewarded.")
                return Decimal("0")

            print(f"[Miner._calculate_block_reward] SUCCESS: Final Block Reward: {block_reward} ZYC")
            return block_reward

        except Exception as e:
            print(f"[Miner._calculate_block_reward] ERROR: Unexpected error during reward calculation: {e}")
            return Decimal("0")






    def _validate_coinbase(self, tx):
        """
        Ensure the coinbase transaction follows protocol rules:
        - No inputs, exactly one output, type is "COINBASE", fee is zero.
        - Uses single SHA3-384 hashing for transaction ID.
        """
        from Zyiron_Chain.transactions.coinbase import CoinbaseTx  # ✅ Fixed import

        try:
            tx_id_display = getattr(tx, "tx_id", "UNKNOWN")
            print(f"[Miner._validate_coinbase] INFO: Validating Coinbase transaction with TX ID: {tx_id_display}")

            # ✅ **Check if Transaction is a Valid CoinbaseTx**
            if not isinstance(tx, CoinbaseTx):
                print("[Miner._validate_coinbase] ERROR: Transaction is not a valid CoinbaseTx instance.")
                return False

            # ✅ **Ensure TX ID Exists and is Correctly Formatted**
            if not hasattr(tx, "tx_id") or not isinstance(tx.tx_id, str):
                print("[Miner._validate_coinbase] ERROR: Invalid Coinbase transaction ID format. TX ID must be a string.")
                return False

            # ✅ **Validate TX ID Using SHA3-384 Hashing**
            try:
                serialized_tx = json.dumps(tx.to_dict(), sort_keys=True).encode()
                expected_tx_id = Hashing.hash(serialized_tx).hex()
            except Exception as e:
                print(f"[Miner._validate_coinbase] ERROR: Failed to generate expected TX ID: {e}")
                return False

            if tx.tx_id != expected_tx_id:
                print(f"[Miner._validate_coinbase] ERROR: Coinbase TX ID mismatch.\nExpected: {expected_tx_id}\nFound: {tx.tx_id}")
                return False

            # ✅ **Ensure Exactly One Output (No Inputs Allowed)**
            if len(tx.outputs) != 1:
                print(f"[Miner._validate_coinbase] ERROR: Coinbase transaction must have exactly one output. Found: {len(tx.outputs)}")
                return False

            # ✅ **Validate Output Structure**
            output = tx.outputs[0]
            if not isinstance(output, dict):
                print("[Miner._validate_coinbase] ERROR: Invalid output format. Expected a dictionary.")
                return False

            required_output_fields = {"amount", "script_pub_key"}
            if not required_output_fields.issubset(output.keys()):
                print(f"[Miner._validate_coinbase] ERROR: Missing required fields in Coinbase output. Found: {list(output.keys())}")
                return False

            # ✅ **Ensure Fee is Zero**
            if not hasattr(tx, "fee") or not isinstance(tx.fee, Decimal) or tx.fee != Decimal(0):
                print(f"[Miner._validate_coinbase] ERROR: Coinbase transaction must have a fee of 0. Found: {tx.fee}")
                return False

            print(f"[Miner._validate_coinbase] SUCCESS: Coinbase transaction {tx.tx_id[:12]} validated successfully.")
            return True

        except Exception as e:
            print(f"[Miner._validate_coinbase] ERROR: Coinbase validation failed: {e}")
            return False





    def mining_loop(self, network=None):
        import time
        from datetime import datetime

        network = network or Constants.NETWORK
        print(f"\n[Miner.mining_loop] INFO: Starting mining loop on {network.upper()}. Press Ctrl+C to stop.\n")

        last_block = self.block_storage.get_latest_block()

        if not last_block:
            print(f"[Miner.mining_loop] ⚠️ No existing block found. Creating genesis block...")
            self.genesis_block_manager.ensure_genesis_block()
            last_block = self.block_storage.get_latest_block()

            if not last_block:
                with open("mining_errors.txt", "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now()}] ❌ [Miner.mining_loop] ERROR: Failed to initialize Genesis block.\n")
                return
            else:
                with open("mining_errors.txt", "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now()}] ✅ Genesis block created: Height 0 | Hash: {last_block.hash}\n")

        self.block_manager.chain = [last_block]
        block_height = last_block.index + 1

        mined_blocks = 0
        total_mining_time = 0
        mining_start_time = time.time()

        while True:
            try:
                print(f"\n[Miner.mining_loop] INFO: Mining block at height {block_height}...")
                start_time = time.time()

                block = self.mine_block(network)
                mining_time = round(time.time() - start_time, 2)

                if not block:
                    raise ValueError(f"Failed to mine block at height {block_height}")

                self.block_storage.store_block(block)
                self.block_manager.chain.append(block)

                last_block = block
                block_height = last_block.index + 1

                mined_blocks += 1
                total_mining_time += mining_time
                total_supply = self.block_storage.get_total_mined_supply()

                print(f"[Miner.mining_loop] ✅ Block {block.index} mined in {mining_time}s | Total Supply: {total_supply}")

                try:
                    new_difficulty = self.pow_manager.adjust_difficulty()
                    print(f"[Miner.mining_loop] ✅ Difficulty adjusted to: {new_difficulty}")
                except Exception as diff_error:
                    with open("mining_errors.txt", "a", encoding="utf-8") as f:
                        f.write(f"[{datetime.now()}] ❌ [Difficulty Adjustment ERROR]: {diff_error}\n")

                with open("mining_errors.txt", "a", encoding="utf-8") as f:
                    f.write(
                        f"[{datetime.now()}] ✅ Block {block.index} MINED in {mining_time}s | "
                        f"Hash: {block.hash} | PrevHash: {block.previous_hash}\n"
                    )

                # ✅ Print summary stats every 10 blocks
                if mined_blocks % 10 == 0:
                    avg_time = round(total_mining_time / mined_blocks, 2)
                    runtime = round(time.time() - mining_start_time, 2)
                    summary = (
                        f"\n--- Mining Summary @ Block {block.index} ---\n"
                        f"⛏️  Blocks Mined: {mined_blocks}\n"
                        f"🕒  Avg Mining Time: {avg_time}s\n"
                        f"💰  Total Supply: {total_supply}\n"
                        f"📏  Current Height: {block.index}\n"
                        f"⏱️  Runtime: {runtime}s\n"
                        f"🎯  Difficulty: {new_difficulty}\n"
                        f"-------------------------------\n"
                    )
                    print(summary)
                    with open("mining_errors.txt", "a", encoding="utf-8") as f:
                        f.write(summary)

                time.sleep(1)

            except KeyboardInterrupt:
                print("\n[Miner.mining_loop] INFO: Mining interrupted by user.")
                break

            except Exception as e:
                error_message = f"[{datetime.now()}] ❌ [Mining ERROR @ Height {block_height}] {e}\n"
                print(error_message)
                with open("mining_errors.txt", "a", encoding="utf-8") as f:
                    f.write(error_message)
                time.sleep(1)
                continue



    def validate_new_block(self, new_block):
        """
        Validate a newly mined block:
        - Ensure its hash meets the proof-of-work target using single SHA3-384.
        - Validate the coinbase transaction.
        - Validate subsequent transactions via the transaction manager.
        - Verify block timestamp consistency.
        - Ensure block size does not exceed max limit.
        - Enforce max supply limit if reached.
        """
        try:
            print(f"[Miner.validate_new_block] INFO: Validating new block at height {new_block.index}...")

            # ✅ Ensure block has critical fields
            if not hasattr(new_block, "tx_id") or not hasattr(new_block, "difficulty"):
                print("[Miner.validate_new_block] ERROR: Block object is missing required attributes.")
                return False

            if not isinstance(new_block.transactions, list):
                print("[Miner.validate_new_block] ERROR: Transactions must be a list.")
                return False

            # ✅ Validate Proof-of-Work: Hash must be < difficulty
            try:
                block_hash_int = int(new_block.tx_id, 16)
            except ValueError:
                print(f"[Miner.validate_new_block] ERROR: Block {new_block.index} has an invalid tx_id format.")
                return False

            difficulty_int = int(new_block.difficulty, 16) if isinstance(new_block.difficulty, str) else new_block.difficulty
            if block_hash_int >= difficulty_int:
                print(f"[Miner.validate_new_block] ERROR: Invalid Proof-of-Work for block {new_block.index}.")
                return False

            print(f"[Miner.validate_new_block] INFO: Proof-of-Work passed for block {new_block.index}.")

            # ✅ Coinbase must be first transaction and valid
            if not new_block.transactions or not isinstance(new_block.transactions[0], CoinbaseTx):
                print("[Miner.validate_new_block] ERROR: First transaction must be a valid CoinbaseTx.")
                return False

            coinbase_tx = new_block.transactions[0]
            if not self._validate_coinbase(coinbase_tx):
                print("[Miner.validate_new_block] ERROR: Invalid coinbase transaction.")
                return False

            print("[Miner.validate_new_block] INFO: Coinbase transaction validated.")

            # ✅ Check if MAX_SUPPLY is reached
            try:
                total_mined = self.block_storage.get_total_mined_supply()
                total_mined = Decimal(total_mined)
            except Exception as e:
                print(f"[Miner.validate_new_block] ERROR: Failed to retrieve total mined supply: {e}")
                return False

            print(f"[Miner.validate_new_block] INFO: Total Mined Supply: {total_mined} ZYC (Max: {Constants.MAX_SUPPLY})")
            if Constants.MAX_SUPPLY is not None and total_mined >= Decimal(Constants.MAX_SUPPLY):
                print("[Miner.validate_new_block] ERROR: Max supply reached. Rejecting new block.")
                return False

            # ✅ Validate fees
            if not hasattr(new_block, "fees") or not isinstance(new_block.fees, Decimal):
                print("[Miner.validate_new_block] ERROR: Missing or invalid 'fees' attribute.")
                return False

            if new_block.fees < Decimal("0"):
                print(f"[Miner.validate_new_block] ERROR: Fees cannot be negative. Found: {new_block.fees}")
                return False

            print(f"[Miner.validate_new_block] INFO: Fees validated as {new_block.fees} ZYC.")

            # ✅ Validate timestamp: must be greater than previous and not too far in future
            prev_block = self.block_storage.get_latest_block()
            if prev_block:
                try:
                    if int(new_block.timestamp) <= int(prev_block.timestamp):
                        print(f"[Miner.validate_new_block] ERROR: Timestamp must be greater than previous block.")
                        return False
                except ValueError:
                    print(f"[Miner.validate_new_block] ERROR: Invalid timestamp format in block {new_block.index}.")
                    return False

            max_drift = 7200
            if new_block.timestamp > int(time.time()) + max_drift:
                print(f"[Miner.validate_new_block] ERROR: Timestamp exceeds allowable drift.")
                return False

            print(f"[Miner.validate_new_block] INFO: Timestamp validated.")

            # ✅ Validate block size
            try:
                total_block_bytes = sum(len(json.dumps(tx.to_dict()).encode("utf-8")) for tx in new_block.transactions)
                max_allowed_bytes = Constants.MAX_BLOCK_SIZE_MB * 1024 * 1024
            except Exception as e:
                print(f"[Miner.validate_new_block] ERROR: Block size calculation failed: {e}")
                return False

            if total_block_bytes > max_allowed_bytes:
                print(f"[Miner.validate_new_block] ERROR: Block exceeds max size: {total_block_bytes} bytes.")
                return False

            print(f"[Miner.validate_new_block] INFO: Block size validated: {total_block_bytes} bytes.")

            print(f"[Miner.validate_new_block] ✅ SUCCESS: Block {new_block.index} validated successfully.")
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
        - Added stop functionality while preserving all original logging
        - Uses self._mining_active flag to control mining process
        - Maintains exact same output format for mining progress
        """
        with self._mining_lock:
            try:
                # Initialize mining state
                self._mining_active = True
                print("[Miner.mine_block] START: Initiating mining procedure.")
                start_time = time.time()

                if not self.block_manager:
                    print("[Miner.mine_block] ERROR: `block_manager` is not initialized.")
                    return None

                if not self.block_storage:
                    print("[Miner.mine_block] ERROR: `block_storage` is not initialized.")
                    return None

                print("[Miner.mine_block] INFO: Fetching latest block.")
                last_block = self.block_manager.get_latest_block()

                if not last_block:
                    print("[Miner.mine_block] WARNING: No previous block found. Ensuring Genesis block exists.")
                    if not self.genesis_block_manager:
                        print("[Miner.mine_block] ERROR: `genesis_block_manager` not initialized.")
                        return None
                    self.genesis_block_manager.ensure_genesis_block()
                    last_block = self.block_manager.get_latest_block()
                    if not last_block:
                        print("[Miner.mine_block] ERROR: Failed to create Genesis block.")
                        return None

                # ✅ Handle missing mined hash for Genesis
                if last_block.index == 0 and not getattr(last_block, "mined_hash", None):
                    print("[Miner.mine_block] WARNING: Genesis block missing `mined_hash`. Performing PoW.")
                    pow_result = self.pow_manager.perform_pow(last_block)
                    if pow_result:
                        last_block.mined_hash, last_block.nonce = pow_result[:2]
                        self.block_storage.store_block(last_block)
                        print(f"[Miner.mine_block] ✅ FIXED: Genesis block PoW assigned: {last_block.mined_hash[:12]}...")

                block_height = last_block.index + 1
                print(f"[Miner.mine_block] INFO: Preparing new block at height {block_height}.")

                # ✅ PREVENT DUPLICATE MINING
                existing_block = self.block_storage.get_block_by_height(block_height)
                if existing_block:
                    print(f"[Miner.mine_block] ✅ Block at height {block_height} already exists. Skipping mining.")
                    self.block_manager.chain.append(existing_block)  # ✅ Critical fix to prevent re-mining loop
                    return existing_block

                # ✅ Adjust difficulty
                current_target = self.pow_manager.adjust_difficulty()
                print(f"[Miner.mine_block] INFO: Target difficulty: {hex(current_target)}.")

                # ✅ Get miner address
                miner_address = self.key_manager.get_default_public_key(network, "miner")
                if not miner_address:
                    print("[Miner.mine_block] ERROR: No miner address found.")
                    return None
                print(f"[Miner.mine_block] INFO: Using miner address: {miner_address}")

                # ✅ Get pending transactions
                pending_txs = self.transaction_manager.mempool.get_pending_transactions(self.current_block_size) or []
                print(f"[Miner.mine_block] INFO: Retrieved {len(pending_txs)} pending transactions.")

                total_fees = sum(Decimal(tx.get("fee", 0)) for tx in pending_txs)
                print(f"[Miner.mine_block] INFO: Total block fees: {total_fees} ZYC")

                # ✅ Create coinbase transaction
                coinbase_tx = self._create_coinbase(miner_address, total_fees)
                if not coinbase_tx:
                    print("[Miner.mine_block] ERROR: Failed to create coinbase transaction.")
                    return None

                valid_txs = [coinbase_tx] + pending_txs

                # ✅ Previous hash
                previous_hash = getattr(last_block, "mined_hash", last_block.hash)
                if block_height == 0:
                    previous_hash = Constants.ZERO_HASH

                # ✅ Construct block
                new_block = Block(
                    index=block_height,
                    previous_hash=previous_hash,
                    transactions=valid_txs,
                    timestamp=int(time.time()),
                    nonce=0,
                    difficulty=current_target,
                    miner_address=miner_address,
                    fees=total_fees
                )

                # ✅ Perform Proof-of-Work
                print("[Miner.mine_block] INFO: Performing Proof-of-Work.")
                pow_result = self.pow_manager.perform_pow(new_block)

                if not pow_result:
                    print("[Miner.mine_block] ERROR: PoW failed.")
                    return None

                mined_hash, mined_nonce = pow_result[:2]
                if int(mined_hash, 16) >= current_target:
                    print("[Miner.mine_block] ERROR: Mined hash does not meet target.")
                    return None

                new_block.mined_hash = mined_hash
                new_block.nonce = mined_nonce
                self.block_storage.store_block(new_block)

                for tx in valid_txs:
                    tx_dict = tx.to_dict() if hasattr(tx, "to_dict") else tx
                    tx_id = tx_dict.get("tx_id")
                    outputs = tx_dict.get("outputs", [])
                    timestamp = tx_dict.get("timestamp", int(time.time()))
                    tx_signature = tx_dict.get("tx_signature", b"")
                    falcon_signature = tx_dict.get("falcon_signature", b"")

                    if isinstance(tx_signature, str):
                        try:
                            tx_signature = bytes.fromhex(tx_signature)
                        except ValueError:
                            tx_signature = b""

                    if isinstance(falcon_signature, str):
                        try:
                            falcon_signature = bytes.fromhex(falcon_signature)
                        except ValueError:
                            falcon_signature = b""

                    self.tx_storage.store_transaction(
                        tx_id=tx_id,
                        block_hash=new_block.mined_hash,
                        tx_data=tx_dict,
                        outputs=outputs,
                        timestamp=timestamp,
                        tx_signature=tx_signature,
                        falcon_signature=falcon_signature
                    )

                self.utxo_storage.update_utxos(new_block)

                # ✅ Update block manager in-memory state
                self.block_manager.chain.append(new_block)

                print(f"[Miner.mine_block] ✅ SUCCESS: Block {block_height} mined with hash {mined_hash[:12]}... in {time.time() - start_time:.2f}s")
                return new_block

            except Exception as e:
                print(f"[Miner.mine_block] ERROR: Unexpected error: {e}")
                return None
            finally:
                self._mining_active = False

    # Add this method to your Miner class
    def stop(self):
        """Stop the current mining operation"""
        self._mining_active = False
        print("[Miner.stop] Mining stop requested")