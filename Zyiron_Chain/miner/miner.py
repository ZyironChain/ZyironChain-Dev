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

# Ensure this is at the very top of your script, before any other code


class Miner:
    def __init__(self, blockchain, transaction_manager, key_manager, mempool_storage):
        """
        Initialize the Miner.

        :param blockchain: The blockchain instance.
        :param transaction_manager: The transaction manager instance.
        :param key_manager: The key manager instance.
        :param mempool_storage: The mempool storage instance.
        """
        self.blockchain = blockchain
        self.transaction_manager = transaction_manager
        self.key_manager = key_manager
        self.mempool_storage = mempool_storage
        print("[Miner.__init__] INFO: Miner initialized successfully.")
        
        # Fetch the blockchain reference dynamically
        self.blockchain = self.block_manager.blockchain

        # Fetch the active network dynamically from Constants
        self.network = Constants.NETWORK

        self.current_block_size = 1.0  # Set initial block size dynamically
        self.chain = self.block_manager.chain  # Ensure Miner has reference to blockchain

        print(f"[Miner.__init__] INFO: Miner initialized on {self.network.upper()}.")

    def _calculate_block_size(self):
        """
        Dynamically adjust block size based on mempool transaction volume and allocation settings.
        Processes block size in MB.
        """
        try:
            pending_txs = self.transaction_manager.mempool.get_pending_transactions(
                block_size_mb=self.current_block_size
            )
            if not isinstance(pending_txs, list):
                print("[Miner._calculate_block_size] ERROR: Invalid transaction list retrieved from mempool.")
                return

            count = len(pending_txs)
            # Use Constants for block size settings (converted to MB)
            min_tx, max_tx = 1000, 50000
            min_size = Constants.MIN_BLOCK_SIZE_BYTES / (1024 * 1024)
            max_size = Constants.MAX_BLOCK_SIZE_BYTES / (1024 * 1024)

            if count <= min_tx:
                new_size = min_size
            elif count >= max_tx:
                new_size = max_size
            else:
                scale = (count - min_tx) / (max_tx - min_tx)
                new_size = min_size + (max_size - min_size) * scale

            standard_allocation = new_size * Constants.MEMPOOL_STANDARD_ALLOCATION
            smart_allocation = new_size * Constants.MEMPOOL_SMART_ALLOCATION

            standard_txs = []
            smart_txs = []
            for tx in pending_txs:
                if not hasattr(tx, "tx_id") or not hasattr(tx, "size"):
                    print(f"[Miner._calculate_block_size] WARNING: Skipping transaction with missing attributes: {tx}")
                    continue
                if any(tx.tx_id.startswith(prefix) for prefix in Constants.TRANSACTION_MEMPOOL_MAP["STANDARD"]["prefixes"]):
                    standard_txs.append(tx)
                elif any(tx.tx_id.startswith(prefix) for prefix in Constants.TRANSACTION_MEMPOOL_MAP["SMART"]["prefixes"]):
                    smart_txs.append(tx)

            total_standard_size = sum(tx.size for tx in standard_txs) / (1024 * 1024)
            total_smart_size = sum(tx.size for tx in smart_txs) / (1024 * 1024)

            if total_standard_size > standard_allocation:
                print(f"[Miner._calculate_block_size] WARNING: Standard transactions exceed allocation ({total_standard_size:.2f} MB)")
                total_standard_size = standard_allocation
            if total_smart_size > smart_allocation:
                print(f"[Miner._calculate_block_size] WARNING: Smart transactions exceed allocation ({total_smart_size:.2f} MB)")
                total_smart_size = smart_allocation

            final_block_size = total_standard_size + total_smart_size
            self.current_block_size = max(min_size, min(final_block_size, max_size))
            print(f"[Miner._calculate_block_size] INFO: Block size dynamically adjusted to {self.current_block_size:.2f} MB")
        except Exception as e:
            print(f"[Miner._calculate_block_size] ERROR: Exception during block size calculation: {e}")

    def _create_coinbase(self, miner_address, fees):
        """
        Creates a coinbase transaction for miners using single SHA3-384 hashing.
        - If max supply is reached, only transaction fees are rewarded.
        - Ensures a minimum payout using Constants.MIN_TRANSACTION_FEE.
        """
        try:
            block_reward = self._calculate_block_reward()
            total_mined = self.storage_manager.get_total_mined_supply()
            if Constants.MAX_SUPPLY is not None and total_mined >= Decimal(Constants.MAX_SUPPLY):
                print("[Miner._create_coinbase] INFO: Max supply reached; only fees will be rewarded.")
                block_reward = Decimal("0")
            total_reward = max(block_reward + fees, Decimal(Constants.MIN_TRANSACTION_FEE))
            print(f"[Miner._create_coinbase] INFO: Coinbase reward computed as {total_reward} ZYC (Fees: {fees}, Reward: {block_reward}).")
            coinbase_tx = CoinbaseTx(
                block_height=len(self.block_manager.chain),
                miner_address=miner_address,
                reward=total_reward
            )
            coinbase_tx.fee = Decimal("0")
            coinbase_tx.tx_id = Hashing.hash(coinbase_tx.calculate_hash().encode()).hex()
            print(f"[Miner._create_coinbase] SUCCESS: Coinbase transaction created: {coinbase_tx.tx_id}")
            return coinbase_tx
        except Exception as e:
            print(f"[Miner._create_coinbase] ERROR: Coinbase creation failed: {e}")
            raise

    def _calculate_block_reward(self):
        """
        Calculate the current block reward using halving logic.
        - Halves every BLOCKCHAIN_HALVING_BLOCK_HEIGHT blocks.
        - If MAX_SUPPLY is reached, reward is zero (only fees).
        """
        try:
            halving_interval = getattr(Constants, "BLOCKCHAIN_HALVING_BLOCK_HEIGHT", None)
            initial_reward = getattr(Constants, "INITIAL_COINBASE_REWARD", None)
            max_supply = getattr(Constants, "MAX_SUPPLY", None)
            min_fee = getattr(Constants, "MIN_TRANSACTION_FEE", None)
            if halving_interval is None or initial_reward is None or min_fee is None:
                print("[Miner._calculate_block_reward] ERROR: Missing required constants for reward calculation.")
                return Decimal("0")
            initial_reward = Decimal(initial_reward)
            min_fee = Decimal(min_fee)
            if not hasattr(self.block_manager, "chain") or not isinstance(self.block_manager.chain, list):
                print("[Miner._calculate_block_reward] ERROR: Invalid blockchain reference in block manager.")
                return Decimal("0")
            current_height = len(self.block_manager.chain)
            halvings = max(0, current_height // halving_interval)
            reward = initial_reward / (2 ** halvings)
            try:
                total_mined = self.storage_manager.get_total_mined_supply()
            except Exception as e:
                print(f"[Miner._calculate_block_reward] ERROR: Failed to retrieve total mined supply: {e}")
                return Decimal("0")
            if max_supply is not None and total_mined >= Decimal(max_supply):
                print("[Miner._calculate_block_reward] INFO: Max supply reached; no new coins rewarded.")
                return Decimal("0")
            final_reward = max(reward, min_fee)
            print(f"[Miner._calculate_block_reward] INFO: Block reward: {final_reward} ZYC (Mined: {total_mined}/{max_supply})")
            return final_reward
        except Exception as e:
            print(f"[Miner._calculate_block_reward] ERROR: Unexpected error during reward calculation: {e}")
            return Decimal("0")

    def _validate_coinbase(self, tx):
        """
        Ensure the coinbase transaction follows protocol rules:
        - No inputs, exactly one output, type is "COINBASE", fee is zero.
        - Uses single SHA3-384 hashing for transaction ID.
        """
        from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
        try:
            if not hasattr(tx, "tx_id") or not isinstance(tx.tx_id, str):
                print(f"[Miner._validate_coinbase] ERROR: Invalid Coinbase transaction ID format: {tx.tx_id}")
                return False
            single_hashed_tx_id = Hashing.hash(tx.tx_id.encode()).hex()
            valid = (isinstance(tx, CoinbaseTx) and len(tx.inputs) == 0 and len(tx.outputs) == 1 and
                     tx.type == "COINBASE" and tx.fee == Decimal(0) and single_hashed_tx_id == tx.tx_id)
            if not valid:
                print(f"[Miner._validate_coinbase] ERROR: Coinbase transaction {tx.tx_id} failed validation.")
            else:
                print(f"[Miner._validate_coinbase] SUCCESS: Coinbase transaction {tx.tx_id} validated.")
            return valid
        except Exception as e:
            print(f"[Miner._validate_coinbase] ERROR: Coinbase validation failed: {e}")
            return False

    def mining_loop(self, network=None):
        """
        Continuous mining loop:
        - Mines new blocks until interrupted.
        - Ensures Genesis block exists (handled externally).
        - Dynamically adjusts difficulty.
        - Uses detailed print statements for progress.
        """
        network = network or Constants.NETWORK
        print(f"\n[Miner.mining_loop] INFO: Starting mining loop on {network.upper()}. Press Ctrl+C to stop.\n")
        if not self.block_manager.chain:
            print(f"[Miner.mining_loop] WARNING: Blockchain is empty! Ensuring Genesis block exists on {network.upper()}...")
            self.block_manager.blockchain._ensure_genesis_block()
            genesis_block = self.storage_manager.get_latest_block()
            if not genesis_block or int(genesis_block.hash, 16) >= genesis_block.difficulty:
                raise RuntimeError(f"[Miner.mining_loop] ERROR: Genesis Block validation failed on {network.upper()}!")
            print(f"[Miner.mining_loop] INFO: Genesis Block ready with hash: {genesis_block.hash[:12]}...")

        block_height = len(self.block_manager.chain)
        block = None

        while True:
            try:
                block = self.mine_block(network)
                if not block or not self.validate_new_block(block):
                    print(f"[Miner.mining_loop] ERROR: Mined block at height {block.index} is invalid on {network.upper()}.")
                    raise ValueError(f"[Miner.mining_loop] ERROR: Mined block failed validation on {network.upper()}.")
                block_height += 1
                self.block_manager.chain.append(block)
                self.storage_manager.store_block(block, block.header.difficulty)
                total_supply = self.storage_manager.get_total_mined_supply()
                print(f"[Miner.mining_loop] INFO: Total mined supply: {total_supply} (Max: {Constants.MAX_SUPPLY})")
                new_difficulty = self.block_manager.calculate_target(self.storage_manager)
                print(f"[Miner.mining_loop] INFO: Adjusted difficulty on {network.upper()} to: {hex(new_difficulty)}")
            except KeyboardInterrupt:
                print(f"\n[Miner.mining_loop] INFO: Mining loop on {network.upper()} interrupted by user.")
                break
            except Exception as e:
                print(f"[Miner.mining_loop] ERROR: Mining error on {network.upper()}: {e}")
                if block is not None:
                    print(f"[Miner.mining_loop] ERROR: Failed at block height: {block.index} on {network.upper()}")
                    print(f"         Block hash: {block.hash[:12]}...")
                else:
                    print(f"[Miner.mining_loop] ERROR: Error during block initialization on {network.upper()}.")
                if self.block_manager.chain:
                    print(f"[Miner.mining_loop] ERROR: Last valid block hash: {self.block_manager.chain[-1].hash[:12]}...")
                break

    def validate_new_block(self, new_block):
        """
        Validate a newly mined block:
        - Ensure its hash meets the proof-of-work target using single SHA3-384.
        - Validate the coinbase transaction.
        - Validate subsequent transactions via the transaction manager.
        - Verify block timestamp consistency.
        - Ensure block size does not exceed max limit.
        """
        try:
            if not hasattr(new_block, "hash") or not hasattr(new_block, "header"):
                print("[Miner.validate_new_block] ERROR: Block object is missing required attributes.")
                return False

            if not isinstance(new_block.transactions, list):
                print("[Miner.validate_new_block] ERROR: Transactions must be a list.")
                return False

            try:
                block_hash_int = int(new_block.hash, 16)
            except ValueError:
                print(f"[Miner.validate_new_block] ERROR: Block {new_block.index} has an invalid hash format.")
                return False

            if block_hash_int >= new_block.header.difficulty:
                print(f"[Miner.validate_new_block] ERROR: Invalid Proof-of-Work for block {new_block.index}.")
                return False

            if not new_block.transactions or not isinstance(new_block.transactions[0], CoinbaseTx):
                print("[Miner.validate_new_block] ERROR: Block must start with a valid Coinbase transaction.")
                return False

            coinbase_tx = new_block.transactions[0]
            if not self._validate_coinbase(coinbase_tx):
                print("[Miner.validate_new_block] ERROR: Invalid coinbase transaction in new block.")
                return False

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

            try:
                total_block_size = sum(len(json.dumps(tx.to_dict())) for tx in new_block.transactions)
            except (TypeError, AttributeError) as e:
                print(f"[Miner.validate_new_block] ERROR: Failed to calculate block size: {e}")
                return False

            if total_block_size > Constants.MAX_BLOCK_SIZE_BYTES:
                print(f"[Miner.validate_new_block] ERROR: Block {new_block.index} exceeds max block size limit: {total_block_size} bytes.")
                return False

            for tx in new_block.transactions[1:]:
                try:
                    if isinstance(tx.tx_id, bytes):
                        tx.tx_id = tx.tx_id.decode("utf-8")
                    single_hashed_tx_id = Hashing.hash(tx.tx_id.encode()).hex()
                    if not self.transaction_manager.validate_transaction(tx):
                        print(f"[Miner.validate_new_block] ERROR: Invalid transaction in block {new_block.index}: {single_hashed_tx_id}")
                        return False
                except AttributeError as e:
                    print(f"[Miner.validate_new_block] ERROR: Transaction missing required attributes: {e}")
                    return False

            print(f"[Miner.validate_new_block] SUCCESS: Block {new_block.index} successfully validated.")
            return True

        except Exception as e:
            print(f"[Miner.validate_new_block] ERROR: Unexpected error during block validation: {e}")
            return False

    def mine_block(self, network=Constants.NETWORK):
        """
        Mines a new block using Proof-of-Work with dynamically adjusted difficulty.
        Delegates the PoW hashing loop to pow.py (via perform_pow).
        All data is processed as bytes.
        """
        with self.mining_lock:
            try:
                # Debug: Start mining procedure
                print("[Miner.mine_block] START: Initiating mining procedure. (Function: mine_block, Class: Miner)")
                start_time = time.time()

                # Get the latest block
                last_block = self.storage_manager.get_latest_block()
                if not last_block:
                    print("[Miner.mine_block] WARNING: No previous block found; ensuring Genesis block exists. (Function: mine_block, Class: Miner)")
                    self.block_manager.blockchain._ensure_genesis_block()
                    last_block = self.storage_manager.get_latest_block()
                if not last_block:
                    print("[Miner.mine_block] ERROR: Failed to retrieve or create Genesis block. (Function: mine_block, Class: Miner)")
                    return None

                block_height = last_block.index + 1
                print(f"[Miner.mine_block] INFO: Preparing new block at height {block_height}. (Function: mine_block, Class: Miner)")

                # Adjust difficulty
                current_target = self.block_manager.calculate_target(self.storage_manager)
                current_target = max(min(current_target, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)
                print(f"[Miner.mine_block] INFO: Adjusted difficulty target set to {hex(current_target)}. (Function: mine_block, Class: Miner)")

                # Get miner address
                miner_address = self.key_manager.get_default_public_key(network, "miner")
                if not miner_address:
                    print("[Miner.mine_block] ERROR: Failed to retrieve miner address. (Function: mine_block, Class: Miner)")
                    return None

                # Calculate block size and get pending transactions
                self._calculate_block_size()
                pending_txs = self.transaction_manager.mempool.get_pending_transactions(
                    block_size_mb=self.current_block_size
                ) or []
                total_fees = sum(tx.fee for tx in pending_txs if hasattr(tx, "fee"))

                # Create coinbase transaction
                coinbase_tx = self._create_coinbase(miner_address, total_fees)
                valid_txs = [coinbase_tx] + pending_txs

                # Create new block
                new_block = Block(
                    index=block_height,
                    previous_hash=last_block.hash,
                    transactions=valid_txs,
                    timestamp=int(time.time()),
                    nonce=0,
                    difficulty=current_target
                )

                # Perform Proof-of-Work
                from Zyiron_Chain.miner.pow import PowManager
                final_hash, final_nonce, attempts = PowManager().perform_pow(new_block)

                # Update block with final hash and nonce
                new_block.hash = final_hash
                new_block.header.nonce = final_nonce

                # Store block and update chain
                self.storage_manager.store_block(new_block, new_block.difficulty)
                self.block_manager.chain.append(new_block)

                # Print final success message
                elapsed_time = int(time.time() - start_time)
                print(f"[Miner.mine_block] SUCCESS: Block {block_height} mined! Final Hash: {new_block.hash} | Time Taken: {elapsed_time}s. (Function: mine_block, Class: Miner)")
                return new_block

            except Exception as e:
                print(f"[Miner.mine_block] ERROR: Mining failed with exception -> {e}. (Function: mine_block, Class: Miner)")
                return None
    @property
    def mining_lock(self):
        if not hasattr(self, "_mining_lock"):
            self._mining_lock = Lock()
        return self._mining_lock
