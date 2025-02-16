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
    # Constants for difficulty (7 leading zeros)
# Constants (hex values for 7 leading zeros)
# Should be set like this:
    INITIAL_DIFFICULTY = 0x0000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # 7 zeros
    MIN_DIFFICULTY = 0x000000000000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # Hardest (smallest number)
    MAX_DIFFICULTY = 0x0000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # Easiest (largest number)
    TARGET_BLOCK_TIME = 300  # 5 minutes in seconds
    DIFFICULTY_ADJUSTMENT_INTERVAL = 2  # Adjust every 10 blocks

    def __init__(self, storage_manager, transaction_manager):  # Add transaction_manager
        self.chain = []
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager  # Store transaction_manager
        self.difficulty_target = self.INITIAL_DIFFICULTY

        logging.info(f"[INIT] 🔧 Difficulty Target set to {hex(self.difficulty_target)}")
        logging.info(f"[INIT] ⏳ Blocks should take ~5 minutes")

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
        Difficulty adjustment using total time between first and last block in interval
        """
        if len(self.chain) < self.DIFFICULTY_ADJUSTMENT_INTERVAL:
            return self.INITIAL_DIFFICULTY

        # Get first and last blocks using header timestamps
        first_block = self.chain[-self.DIFFICULTY_ADJUSTMENT_INTERVAL]
        last_block = self.chain[-1]
        
        # Access timestamps through block headers
        total_time = last_block.header.timestamp - first_block.header.timestamp
        num_blocks = self.DIFFICULTY_ADJUSTMENT_INTERVAL - 1
        
        if total_time <= 0 or num_blocks <= 0:
            logging.error("⚠️ Invalid time calculation, using fallback difficulty")
            return self.difficulty_target

        avg_block_time = total_time / num_blocks
        adjustment_factor = self.TARGET_BLOCK_TIME / avg_block_time

        # Exponential response for fast blocks
        if avg_block_time < self.TARGET_BLOCK_TIME / 4:
            adjustment_factor **= 2  # Quadratic increase

        # Controlled adjustment range
        adjustment_factor = max(0.25, min(4.0, adjustment_factor))

        new_target = int(self.difficulty_target * adjustment_factor)
        new_target = max(self.MIN_DIFFICULTY, min(new_target, self.MAX_DIFFICULTY))
        
        logging.info(
            f"⏳ Difficulty Adjusted | "
            f"Avg Time: {avg_block_time:.1f}s | "
            f"Factor: {adjustment_factor:.2f}x | "
            f"New: {hex(new_target)}"
        )
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
        self.chain.append(block)
        # Change from block['index'] to block.index
        logging.info(f"[INFO] ✅ Block {block.index} added. Difficulty: {hex(self.difficulty_target)}")
        
        if len(self.chain) % self.DIFFICULTY_ADJUSTMENT_INTERVAL == 0:
            self.adjust_difficulty()


    def get_latest_block(self):
        """
        Retrieve the latest block from storage.
        """
        return self.chain[-1] if self.chain else None




    def adjust_difficulty(self):
        if len(self.chain) < self.DIFFICULTY_ADJUSTMENT_INTERVAL:
            return

        # Use header timestamps for accurate calculation
        first = self.chain[-self.DIFFICULTY_ADJUSTMENT_INTERVAL]
        last = self.chain[-1]
        
        time_window = last.header.timestamp - first.header.timestamp
        avg_block_time = time_window / (self.DIFFICULTY_ADJUSTMENT_INTERVAL - 1)

        # Controlled adjustment with bounds
        adjustment = self.TARGET_BLOCK_TIME / avg_block_time
        adjustment = max(0.25, min(4.0, adjustment))  # 4x max adjustment

        new_target = int(self.difficulty_target * adjustment)
        self.difficulty_target = max(
            self.MIN_DIFFICULTY, 
            min(new_target, self.MAX_DIFFICULTY)
    )