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





from Zyiron_Chain.blockchain.constants import Constants


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
    def __init__(self, blockchain, storage_manager, transaction_manager):  
        self.blockchain = blockchain  # ✅ Fix: Ensure BlockManager has blockchain reference
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager
        self.chain = []

        # ✅ Fix: Pull difficulty values from `Constants`
        self.difficulty_target = Constants.INITIAL_DIFFICULTY

        logging.info(f"[INIT] 🔧 Difficulty Target set to {hex(self.difficulty_target)}")
        logging.info(f"[INIT] ⏳ Blocks should take ~{Constants.TARGET_BLOCK_TIME} seconds")



    def validate_chain(self):
        """
        Validate chain integrity:
        - Ensures Block 0 (Genesis) meets the 4-zero difficulty rule.
        - Each block's previous_hash correctly links to the prior block's hash.
        - Each block's hash < block's difficulty.
        - Recomputes block hash to ensure no corruption.
        """
        for i in range(len(self.chain)):
            current_block = self.chain[i]

            # Ensure Block 0 (Genesis) uses the required 4-zero difficulty
            if i == 0 and current_block.header.difficulty != Constants.GENESIS_TARGET:
                logging.error(f"[VALIDATION ERROR] ❌ Block {i} (Genesis) does not meet required 4-zero difficulty.")
                return False

            # Validate previous hash linkage (skip for Genesis block)
            if i > 0:
                prev_block = self.chain[i - 1]
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















    def calculate_target(self, storage_manager):
        """
        Dynamically adjusts mining difficulty based on actual vs. expected block times.
        Ensures difficulty is updated every `DIFFICULTY_ADJUSTMENT_INTERVAL` blocks.
        """
        try:
            # ✅ Ensure `get_all_blocks()` exists
            if not hasattr(storage_manager, "get_all_blocks"):
                logging.error("[ERROR] StorageManager is missing 'get_all_blocks()' method!")
                return Constants.GENESIS_TARGET  # Fallback to Genesis Target

            stored_blocks = storage_manager.get_all_blocks()
            num_blocks = len(stored_blocks)

            if num_blocks == 0:
                logging.info("[DIFFICULTY] No blocks found. Using Genesis Target.")
                return Constants.GENESIS_TARGET  

            # ✅ Retrieve latest block for current difficulty reference
            last_block = stored_blocks[-1]
            last_difficulty_hex = last_block["header"].get("difficulty", hex(Constants.GENESIS_TARGET))  
            
            # ✅ Convert difficulty safely
            last_difficulty = int(last_difficulty_hex, 16) if isinstance(last_difficulty_hex, str) else Constants.GENESIS_TARGET

            # ✅ If not enough blocks exist for an adjustment, use last difficulty
            if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL:
                logging.info("[DIFFICULTY] Not enough blocks for adjustment. Using last difficulty.")
                return last_difficulty

            # ✅ Get the block at the difficulty adjustment interval
            first_block = stored_blocks[-Constants.DIFFICULTY_ADJUSTMENT_INTERVAL]

            # ✅ Compute actual vs expected mining time
            actual_time_taken = last_block["header"]["timestamp"] - first_block["header"]["timestamp"]
            expected_time = Constants.DIFFICULTY_ADJUSTMENT_INTERVAL * Constants.TARGET_BLOCK_TIME

            # ✅ Compute difficulty adjustment ratio
            adjustment_ratio = expected_time / max(actual_time_taken, 1)  # Prevent division by zero
            adjustment_ratio = max(Constants.MIN_DIFFICULTY_FACTOR, min(Constants.MAX_DIFFICULTY_FACTOR, adjustment_ratio))

            # ✅ Compute new target difficulty
            new_target = int(last_difficulty * adjustment_ratio)

            # ✅ Enforce difficulty limits
            new_target = max(min(new_target, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

            logging.info(f"[DIFFICULTY] Adjusted difficulty to {hex(new_target)} at block {num_blocks}")

            return new_target

        except Exception as e:
            logging.error(f"[ERROR] Exception in difficulty calculation: {str(e)}")
            return Constants.GENESIS_TARGET  # Ensure fallback in case of errors












    def get_average_block_time(storage_manager):
        """
        Get the rolling average block mining time over the last `DIFFICULTY_ADJUSTMENT_INTERVAL` blocks.
        If not enough blocks exist, return the target block time.
        """
        stored_blocks = storage_manager.get_all_blocks()
        num_blocks = len(stored_blocks)

        if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL + 1:
            logging.warning(f"[DIFFICULTY] Not enough blocks ({num_blocks}) for full difficulty adjustment.")
            return Constants.TARGET_BLOCK_TIME  

        # ✅ Compute block mining times over the last `DIFFICULTY_ADJUSTMENT_INTERVAL` blocks
        times = [
            stored_blocks[i]["header"]["timestamp"] - stored_blocks[i - 1]["header"]["timestamp"]
            for i in range(num_blocks - Constants.DIFFICULTY_ADJUSTMENT_INTERVAL, num_blocks)
        ]

        avg_time = sum(times) / len(times) if times else Constants.TARGET_BLOCK_TIME
        logging.info(f"[DIFFICULTY] Average block time: {avg_time:.2f} sec (Target: {Constants.TARGET_BLOCK_TIME} sec)")
        
        return avg_time
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






    def adjust_difficulty(self, storage_manager):
        """
        Force difficulty adjustment based on the actual mining time vs. the target block time.
        Ensures that difficulty is updated every Constants.DIFFICULTY_ADJUSTMENT_INTERVAL blocks.
        """

        stored_blocks = storage_manager.get_all_blocks()
        num_blocks = len(stored_blocks)

        if num_blocks == 0:
            logging.info("[DIFFICULTY] No blocks found. Using Genesis Target.")
            return Constants.GENESIS_TARGET  

        if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL:
            first_block = stored_blocks[0]  
        else:
            first_block = stored_blocks[-Constants.DIFFICULTY_ADJUSTMENT_INTERVAL]

        last_block = stored_blocks[-1]

        # Compute time taken
        actual_time_taken = last_block["header"]["timestamp"] - first_block["header"]["timestamp"]
        expected_time = Constants.DIFFICULTY_ADJUSTMENT_INTERVAL * Constants.TARGET_BLOCK_TIME

        # Compute adjustment ratio
        adjustment_ratio = expected_time / max(1, actual_time_taken)
        adjustment_ratio = max(Constants.MIN_DIFFICULTY_FACTOR, min(Constants.MAX_DIFFICULTY_FACTOR, adjustment_ratio))

        # Apply new difficulty
        last_difficulty = int(last_block["header"]["difficulty"], 16)
        new_target = int(last_difficulty * adjustment_ratio)

        # Enforce limits
        new_target = max(min(new_target, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

        # Store updated difficulty
        self.difficulty_target = new_target

        # Log enforced difficulty update
        logging.info(f"[DIFFICULTY] Enforced difficulty: {hex(new_target)} at block {num_blocks} (Ratio: {adjustment_ratio:.4f})")

        return new_target

