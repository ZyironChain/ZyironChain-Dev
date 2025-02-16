import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import json
import hashlib
import time
import logging
import math
# Remove all existing handlers (prevents log conflicts across modules)
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Set up clean logging for this module
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

log = logging.getLogger(__name__)  # Each module gets its own logger

log.info(f"{__name__} logger initialized.")

from Zyiron_Chain.blockchain.blockheader import BlockHeader
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager

def get_transaction():
    """Lazy import to prevent circular dependencies"""
    from Zyiron_Chain.transactions.Blockchain_transaction import Transaction
    return Transaction

def get_coinbase_tx():
    """Lazy import to prevent circular dependencies"""
    from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
    return CoinbaseTx

def get_block():
    """Lazy import to prevent circular dependencies"""
    from Zyiron_Chain.blockchain.block import Block
    return Block








import json
import hashlib
import math
import logging

import time
import math
import logging
import json
import hashlib

class BlockManager:
    # Adjusted constants
    MIN_DIFFICULTY = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    MAX_TARGET = 0x000000000000000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    INITIAL_TARGET = MAX_TARGET  # Start with easier difficulty (higher target)
    DIFFICULTY_ADJUSTMENT_INTERVAL = 2 # Adjusted to every 10 blocks
    TARGET_BLOCK_TIME = 300  # 5-minute blocks
    GENESIS_TARGET = INITIAL_TARGET  # Use INITIAL_TARGET for Genesis

    def __init__(self, storage_manager, transaction_manager=None):
        self.chain = []
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager
        self.difficulty_target = self.INITIAL_TARGET  # Start at max difficulty

        logging.info("[INIT] ⏳ 5-minute block target, retarget every 10 blocks.")
        logging.info(f"[INIT] 🚀 Starting difficulty target: {hex(self.difficulty_target)}")

    def validate_chain(self):
        """
        Validate chain integrity:
        - Ensures Block 0 and Block 1 meet the 4-zero difficulty rule.
        - Each block's previous_hash correctly links to the prior block's hash.
        - Each block's hash < block's difficulty.
        - Recomputes block hash to ensure no corruption.
        """
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            prev_block = self.chain[i - 1]

            # Ensure Blocks 0 & 1 use the required 4-zero difficulty
            if i in (0, 1) and current_block.header.difficulty != self.GENESIS_TARGET:
                logging.error(f"[VALIDATION ERROR] ❌ Block {i} does not meet required 4-zero difficulty.")
                return False

            # Validate previous hash linkage
            if current_block.previous_hash != prev_block.hash:
                logging.error(f"[VALIDATION ERROR] ❌ Block {i} has a previous hash mismatch.")
                return False

            # Validate difficulty
            if int(current_block.hash, 16) >= current_block.header.difficulty:
                logging.error(f"[VALIDATION ERROR] ❌ Block {i} does not meet the difficulty target.")
                return False

            # Verify block integrity (hash correctness)
            if current_block.hash != current_block.calculate_hash():
                logging.error(f"[VALIDATION ERROR] ❌ Block {i} hash mismatch (possible corruption).")
                return False

        return True

    def calculate_target(self):
        """
        Corrected difficulty adjustment using actual_time / expected_time.
        """
        if len(self.chain) < self.DIFFICULTY_ADJUSTMENT_INTERVAL:
            return self.INITIAL_TARGET

        last_n_blocks = self.chain[-self.DIFFICULTY_ADJUSTMENT_INTERVAL:]
        actual_times = [
            last_n_blocks[i].timestamp - last_n_blocks[i-1].timestamp
            for i in range(1, len(last_n_blocks))
        ]

        if not actual_times:
            return self.difficulty_target

        actual_time = sum(actual_times) / len(actual_times)
        expected_time = self.TARGET_BLOCK_TIME

        if actual_time <= 0:
            logging.error("Prevented division by zero, using fallback difficulty.")
            return self.difficulty_target

        # Corrected adjustment factor
        adjustment_factor = actual_time / expected_time
        last_difficulty = self.chain[-1].header.difficulty
        new_target = int(last_difficulty * adjustment_factor)

        # Ensure difficulty doesn't drop below minimum
        new_target = max(new_target, self.MIN_DIFFICULTY)
        self.difficulty_target = new_target

        logging.info(f"New difficulty: {hex(new_target)} (Factor: {adjustment_factor:.4f})")
        return new_target


    def get_average_block_time(self, num_blocks=5):
        """
        Get the rolling average of the last `num_blocks` mined.
        If not enough blocks exist, return the target block time.
        """
        if len(self.chain) < num_blocks + 1:
            return self.TARGET_BLOCK_TIME  

        # Calculate block times over last `num_blocks`
        times = [
            self.chain[i].timestamp - self.chain[i - 1].timestamp
            for i in range(len(self.chain) - num_blocks, len(self.chain))
        ]

        return sum(times) / len(times) if times else self.TARGET_BLOCK_TIME

    def calculate_merkle_root(self, transactions):
        """
        Compute the Merkle root using SHA3-384.
        """
        if not transactions:
            return self.ZERO_HASH

        tx_hashes = [hashlib.sha3_384(json.dumps(tx.to_dict() if hasattr(tx, "to_dict") else tx, sort_keys=True).encode()).hexdigest() for tx in transactions]

        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])  # Duplicate last hash if odd number

            tx_hashes = [hashlib.sha3_384((tx_hashes[i] + tx_hashes[i + 1]).encode()).hexdigest() for i in range(0, len(tx_hashes), 2)]

        return tx_hashes[0]

    def send_block_information(self, block):
        """
        Store block data via StorageManager.
        """
        try:
            self.storage_manager.store_block(block, block.header.difficulty)
            logging.info(f"[INFO] ✅ Block {block.index} stored successfully.")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to store block {block.index}: {e}")
            raise

    def add_block(self, block):
        """
        Add a new block to the blockchain and store it.
        """
        if block.index == 0 and not self.chain:
            logging.info("[INFO] ⛓️ Storing Genesis Block.")
        else:
            logging.info(f"[INFO] 📦 Adding Block {block.index} to chain.")

        self.chain.append(block)
        self.storage_manager.store_block(block)

    def get_latest_block(self):
        """
        Retrieve the latest block from storage.
        """
        return self.chain[-1] if self.chain else None




    def adjust_difficulty(self, previous_difficulty, previous_timestamp, current_timestamp):
        """
        Dynamically adjusts difficulty based on actual mining speed.

        - Uses a faster adjustment formula for better reaction
        - Implements emergency difficulty increase if blocks are way too fast
        - Caps difficulty changes for more gradual adjustments
        """

        # ✅ Ensure valid timestamps to prevent division by zero
        time_diff = current_timestamp - previous_timestamp
        if time_diff <= 0:
            logging.warning("[DIFF ADJUST] ⚠️ Invalid block time detected! Setting to 1 second to prevent errors.")
            time_diff = 3  # Prevent zero division

        # 🚨 Emergency difficulty increase (if blocks are WAY too fast)
        if time_diff < self.TARGET_BLOCK_TIME / 10:  # If blocks found in <30s
            logging.warning("[DIFF ADJUST] ⚠️ Emergency difficulty increase: Mining is WAY too fast!")
            return int(previous_difficulty * 1.5)  # Force a 1.5x increase

        # ✅ Calculate difficulty adjustment factor (faster reaction)
        expected_time = self.TARGET_BLOCK_TIME  # 300 seconds per block
        adjustment_factor = min(3.0, max(0.5, expected_time / time_diff))  # React faster

        # 🚀 Compute new difficulty
        new_difficulty = int(previous_difficulty * adjustment_factor)

        # ✅ Ensure difficulty never drops below the minimum allowed
        new_difficulty = max(new_difficulty, self.MIN_DIFFICULTY)

        # ✅ Log difficulty changes
        logging.info(f"[DIFF ADJUST] ⏳ Time Diff: {time_diff}s | Adj. Factor: {adjustment_factor:.4f}")
        logging.info(f"[DIFF ADJUST] 🔄 New Difficulty: {hex(new_difficulty)} (Prev: {hex(previous_difficulty)})")

        return new_difficulty

