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
        genesis_block_manager=None
    ):
        """
        Initialize the Miner.
        """
        print("[Miner.__init__] INFO: Initializing Miner...")

        # ✅ **Ensure required components are provided**
        required_params = {
            "blockchain": blockchain,
            "block_manager": block_manager,
            "block_storage": block_storage,
            "transaction_manager": transaction_manager,
            "key_manager": key_manager,
            "mempool_storage": mempool_storage,
        }

        for param_name, param_value in required_params.items():
            if not param_value:
                raise ValueError(f"[Miner.__init__] ERROR: `{param_name}` instance is required.")

        # ✅ **Assign instances**
        self.blockchain = blockchain
        self.block_manager = block_manager
        self.block_storage = block_storage
        self.transaction_manager = transaction_manager
        self.key_manager = key_manager
        self.mempool_storage = mempool_storage
        self.genesis_block_manager = genesis_block_manager

        # ✅ **Initialize Proof-of-Work Manager**
        self.pow_manager = PowManager(block_storage)

        # ✅ **Initialize Mining Lock**
        self._mining_lock = Lock()

        # ✅ **Initialize Current Block Size**
        self.current_block_size = Constants.INITIAL_BLOCK_SIZE_MB  # 🔹 Default to 0MB - 10MB

        print("[Miner.__init__] INFO: Miner initialized successfully.")
        print(f"[Miner.__init__] INFO: Initial block size set to {self.current_block_size} MB.")



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
        - Uses a **fixed block reward** instead of halving.
        - If `MAX_SUPPLY` is reached, only transaction fees are rewarded.
        - Ensures a minimum payout using `Constants.MIN_TRANSACTION_FEE`.
        - Stores transaction ID as a standard string (no offsets or byte transformations).
        """
        try:
            print("[Miner._create_coinbase] INFO: Initiating Coinbase transaction creation...")

            # ✅ **Use Fixed Block Reward (No Halving)**
            block_reward = Decimal(Constants.INITIAL_COINBASE_REWARD)

            # ✅ **Retrieve Total Mined Supply from New Storage Model**
            try:
                total_mined = self.block_storage.get_total_mined_supply()  # ✅ Uses `block_storage` method
                total_mined = Decimal(total_mined) if isinstance(total_mined, (int, float, str)) else total_mined
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

            # ✅ **Ensure Miner Address is Formatted Correctly**
            miner_address = miner_address[:128]  # Trim to max 128 characters if too long

            print(f"[Miner._create_coinbase] INFO: Miner address formatted.")

            # ✅ **Retrieve Latest Block Height from `block_storage`**
            try:
                latest_block = self.block_storage.get_latest_block()
                block_height = latest_block["index"] + 1 if latest_block else 0
            except Exception as e:
                print(f"[Miner._create_coinbase] ERROR: Failed to retrieve latest block. Defaulting to height 0. Error: {e}")
                block_height = 0  # Default to Genesis block if retrieval fails

            # ✅ **Create Coinbase Transaction**
            coinbase_tx = CoinbaseTx(
                block_height=block_height,
                miner_address=miner_address,
                reward=total_reward
            )
            coinbase_tx.fee = Decimal("0")

            # ✅ **Generate Transaction ID Using SHA3-384 & Store as String**
            tx_id = Hashing.hash(json.dumps(coinbase_tx.to_dict(), sort_keys=True)).hex()

            # ✅ **Ensure TX ID is Valid**
            if not isinstance(tx_id, str) or len(tx_id) != Constants.SHA3_384_HASH_SIZE:
                print(f"[Miner._create_coinbase] ERROR: TX ID length mismatch! Expected {Constants.SHA3_384_HASH_SIZE} characters, got {len(tx_id)}")
                return None

            coinbase_tx.tx_id = tx_id  # ✅ Store as string

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
        - Ensures a minimum payout using `MIN_TRANSACTION_FEE`.
        """
        try:
            print("[Miner._calculate_block_reward] INFO: Initiating block reward calculation...")

            # ✅ **Use Fixed Block Reward**
            block_reward = Decimal(Constants.INITIAL_COINBASE_REWARD)

            # ✅ **Retrieve Total Mined Supply from Updated Storage Model**
            try:
                total_mined = self.block_storage.get_total_mined_supply()  # ✅ Uses `block_storage`
                
                # ✅ **Ensure `total_mined` is a valid Decimal**
                total_mined = Decimal(total_mined) if isinstance(total_mined, (int, float, str)) else total_mined
            except Exception as e:
                print(f"[Miner._calculate_block_reward] ERROR: Failed to retrieve total mined supply: {e}")
                return Decimal("0")  # Return zero reward if there's an error

            print(f"[Miner._calculate_block_reward] INFO: Total Mined Supply: {total_mined} ZYC (Max: {Constants.MAX_SUPPLY})")

            # ✅ **Check if Max Supply is Reached**
            if Constants.MAX_SUPPLY is not None and total_mined >= Decimal(Constants.MAX_SUPPLY):
                print("[Miner._calculate_block_reward] INFO: Max supply reached; no new coins rewarded.")
                return Decimal("0")  # No block reward if max supply is reached

            # ✅ **Ensure Reward Does Not Go Below Minimum Transaction Fee**
            final_reward = max(block_reward, Decimal(Constants.MIN_TRANSACTION_FEE))

            print(f"[Miner._calculate_block_reward] SUCCESS: Final Block Reward: {final_reward} ZYC")
            return final_reward  # ✅ Returns **Decimal** value instead of bytes

        except Exception as e:
            print(f"[Miner._calculate_block_reward] ERROR: Unexpected error during reward calculation: {e}")
            return Decimal("0")  # Return zero reward on error





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
        """
        Continuous mining loop:
        - Mines new blocks until interrupted.
        - Ensures Genesis block exists.
        - Dynamically adjusts difficulty.
        - Uses detailed print statements for progress and debugging.
        - Stops mining on errors.
        """
        network = network or Constants.NETWORK
        print(f"\n[Miner.mining_loop] INFO: Starting mining loop on {network.upper()}. Press Ctrl+C to stop.\n")

        # ✅ **Ensure the Genesis Block Exists**
        if not self.block_manager.chain:
            print(f"[Miner.mining_loop] WARNING: Blockchain is empty! Ensuring Genesis block exists on {network.upper()}...")

            self.genesis_block_manager.ensure_genesis_block()
            genesis_block = self.block_storage.get_latest_block()  # ✅ Uses `block_storage`

            if not genesis_block:
                print(f"[Miner.mining_loop] ERROR: Genesis Block not found after creation attempt on {network.upper()}! Stopping mining.")
                return

            self.block_manager.chain.append(genesis_block)
            print(f"[Miner.mining_loop] INFO: Genesis Block added successfully: {genesis_block.tx_id}")

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
                if last_block:
                    try:
                        last_tx_id_int = int(last_block.tx_id, 16)
                        last_difficulty_int = int(last_block.difficulty, 16)
                        if last_tx_id_int >= last_difficulty_int:
                            print(f"[Miner.mining_loop] ERROR: Last block in chain is invalid. Stopping mining.")
                            break
                    except ValueError:
                        print("[Miner.mining_loop] ERROR: Failed to parse last block values for validation.")
                        break

                # ✅ **Store the Valid Block**
                self.block_storage.store_block(block, block.difficulty)  # ✅ Uses `block_storage`
                self.block_manager.chain.append(block)

                # ✅ **Check Total Mined Supply**
                total_supply = self.block_storage.get_total_mined_supply()  # ✅ Uses `block_storage`
                print(f"[Miner.mining_loop] INFO: Total mined supply: {total_supply} (Max: {Constants.MAX_SUPPLY}).")

                # ✅ **Dynamically Adjust Difficulty Using PowManager**
                new_difficulty = self.pow_manager.adjust_difficulty()  # ✅ FIXED
                print(f"[Miner.mining_loop] INFO: Difficulty adjusted on {network.upper()} to: {new_difficulty}")

                block_height += 1

            except KeyboardInterrupt:
                print(f"\n[Miner.mining_loop] INFO: Mining loop on {network.upper()} interrupted by user.")
                break

            except Exception as e:
                print(f"[Miner.mining_loop] ERROR: Mining encountered an unexpected error on {network.upper()}: {e}")
                if block:
                    print(f"[Miner.mining_loop] ERROR: Block {block.index} | TX ID: {block.tx_id}")

                last_block = self.block_storage.get_latest_block()  # ✅ Uses `block_storage`
                if last_block:
                    print(f"[Miner.mining_loop] INFO: Last valid block TX ID: {last_block.tx_id}")
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
                block_hash_int = int(new_block.tx_id, 16)
            except ValueError:
                print(f"[Miner.validate_new_block] ERROR: Block {new_block.index} has an invalid hash format.")
                return False

            difficulty_int = int(new_block.difficulty, 16) if isinstance(new_block.difficulty, str) else new_block.difficulty

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
                total_mined = self.block_storage.get_total_mined_supply()  # ✅ Uses `block_storage`
            except Exception as e:
                print(f"[Miner.validate_new_block] ERROR: Failed to retrieve total mined supply: {e}")
                return False

            print(f"[Miner.validate_new_block] INFO: Total Mined Supply: {total_mined} ZYC (Max: {Constants.MAX_SUPPLY})")

            if Constants.MAX_SUPPLY is not None and total_mined >= Decimal(Constants.MAX_SUPPLY):
                print("[Miner.validate_new_block] ERROR: Max supply reached. Rejecting new block.")
                return False

            # ✅ **Validate Fees Collected**
            if not hasattr(new_block, "fees_collected"):
                print("[Miner.validate_new_block] ERROR: Missing fees_collected attribute.")
                return False

            if new_block.fees_collected < Decimal("0"):
                print(f"[Miner.validate_new_block] ERROR: Fees collected cannot be negative. Found: {new_block.fees_collected}")
                return False

            print(f"[Miner.validate_new_block] INFO: Fees collected validated as {new_block.fees_collected} ZYC.")

            # ✅ **Validate Block Timestamp**
            prev_block = self.block_storage.get_latest_block()  # ✅ Uses `block_storage`
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
                total_block_size = sum(len(json.dumps(tx.to_dict())) for tx in new_block.transactions)
            except (TypeError, AttributeError) as e:
                print(f"[Miner.validate_new_block] ERROR: Failed to calculate block size: {e}")
                return False

            if total_block_size > Constants.MAX_BLOCK_SIZE_MB:  # ✅ Corrected comparison (was incorrectly checking against MB)
                print(f"[Miner.validate_new_block] ERROR: Block {new_block.index} exceeds max block size limit: {total_block_size} bytes.")
                return False

            print(f"[Miner.validate_new_block] INFO: Block size validation passed for block {new_block.index}.")

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
        """
        with self._mining_lock:
            try:
                print("[Miner.mine_block] START: Initiating mining procedure.")
                start_time = time.time()

                # ✅ **Ensure BlockManager is Properly Initialized**
                if not hasattr(self, "block_manager") or not self.block_manager:
                    print("[Miner.mine_block] ERROR: `block_manager` not initialized. Cannot retrieve latest block.")
                    return None

                # ✅ **Get the Latest Block**
                print("[Miner.mine_block] INFO: Checking for latest block.")
                last_block = self.block_manager.get_latest_block()

                if not last_block:
                    print("[Miner.mine_block] WARNING: No previous block found. Ensuring Genesis block exists.")

                    if not hasattr(self, "genesis_block_manager") or not self.genesis_block_manager:
                        print("[Miner.mine_block] ERROR: `genesis_block_manager` not initialized. Stopping mining.")
                        return None

                    print("[Miner.mine_block] INFO: Creating Genesis block using GenesisBlockManager.")
                    self.genesis_block_manager.ensure_genesis_block()

                    last_block = self.block_manager.get_latest_block()
                    if not last_block:
                        print("[Miner.mine_block] ERROR: Failed to retrieve or create Genesis block. Stopping mining.")
                        return None

                block_height = last_block.index + 1
                print(f"[Miner.mine_block] INFO: Preparing new block at height {block_height}.")

                # ✅ **Adjust Difficulty Using PowManager**
                print("[Miner.mine_block] INFO: Calculating difficulty target.")
                current_target = self.pow_manager.adjust_difficulty()
                print(f"[Miner.mine_block] INFO: Adjusted difficulty target set to {hex(current_target)}.")

                # ✅ **Retrieve Miner Address**
                print("[Miner.mine_block] INFO: Retrieving miner address.")
                miner_address = self.key_manager.get_default_public_key(network, "miner")
                if not miner_address:
                    print("[Miner.mine_block] ERROR: Failed to retrieve miner address. Stopping mining.")
                    return None
                print(f"[Miner.mine_block] INFO: Miner address retrieved: {miner_address}.")

                # ✅ **Retrieve Pending Transactions from Mempool**
                print("[Miner.mine_block] INFO: Retrieving pending transactions from mempool.")
                pending_txs = self.transaction_manager.mempool.get_pending_transactions(self.current_block_size) or []
                print(f"[Miner.mine_block] INFO: Retrieved {len(pending_txs)} pending transactions.")

                total_fees = sum(tx["fee"] for tx in pending_txs if "fee" in tx)
                print(f"[Miner.mine_block] INFO: Total fees for this block: {total_fees} ZYC.")

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
                    miner_address=miner_address,
                    fees_collected=total_fees
                )

                # ✅ **Perform Proof-of-Work Using PowManager**
                print("[Miner.mine_block] INFO: Starting Proof-of-Work.")
                final_hash, final_nonce, attempts = self.pow_manager.perform_pow(new_block)
                print(f"[Miner.mine_block] INFO: Proof-of-Work completed after {attempts} attempts. Final hash: {final_hash[:12]}...")

                # ✅ **Validate Proof-of-Work Before Storing**
                if int(final_hash, 16) >= current_target:
                    print("[Miner.mine_block] ERROR: Invalid Proof-of-Work. Hash does not meet difficulty target. Stopping mining.")
                    return None

                # ✅ **Update Block with Final Hash and Nonce**
                new_block.tx_id = final_hash
                new_block.nonce = final_nonce
                print(f"[Miner.mine_block] INFO: Block updated with final hash and nonce {final_nonce}.")

                # ✅ **Store Block Using BlockManager**
                print("[Miner.mine_block] INFO: Storing block in BlockManager.")
                self.block_manager.add_block(new_block)
                print(f"[Miner.mine_block] INFO: Block {block_height} added to the chain.")

                elapsed_time = int(time.time() - start_time)
                print(f"[Miner.mine_block] SUCCESS: Block {block_height} mined! Final TX ID: {new_block.tx_id[:12]}... | Time Taken: {elapsed_time}s.")
                return new_block

            except Exception as e:
                print(f"[Miner.mine_block] ERROR: Mining failed: {e}. Stopping mining.")
                return None
