import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import json
import hashlib
import time
import logging
import math

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

from Zyiron_Chain.blockchain.constants import Constants

from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.blockchain.utils.hashing import Hashing

class BlockManager:
    def __init__(self, blockchain, storage_manager, transaction_manager):
        """Initialize BlockManager with blockchain dependencies and difficulty settings."""
        self.blockchain = blockchain
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager
        self.chain = blockchain.chain  # ✅ Direct reference to the blockchain chain

        self.network = Constants.NETWORK
        self.version = Constants.VERSION
        self.difficulty_target = Constants.GENESIS_TARGET

        logging.info(f"[BLOCKMANAGER] Initialized on {self.network.upper()} | Version {self.version} | Difficulty {hex(self.difficulty_target)}")

    def validate_block(self, block):
        from Zyiron_Chain.blockchain.blockchain import Blockchain
        # Use Blockchain here without circular import issues.
        # Perform your block validation logic that depends on Blockchain.

    def validate_chain(self):
        """
        Validate chain integrity:
        - Ensures transactions in each block meet the confirmation requirements.
        - Ensures each block's previous_hash correctly links to the prior block's hash.
        - Ensures Proof-of-Work validity.
        """
        if not self.chain:
            logging.error("[ERROR] ❌ Blockchain is empty. Cannot validate.")
            return False

        for i in range(len(self.chain)):
            current_block = self.chain[i]

            # ✅ Ensure block attributes exist before validation
            if not hasattr(current_block, "transactions") or not hasattr(current_block, "previous_hash") or not hasattr(current_block, "hash") or not hasattr(current_block, "header"):
                logging.error(f"[ERROR] ❌ Block {i} is missing required attributes. Possible corruption.")
                return False

            # ✅ Validate confirmations for transactions
            for tx in current_block.transactions:
                if not hasattr(tx, "tx_id"):
                    logging.error(f"[ERROR] ❌ Transaction in Block {current_block.index} is missing a tx_id.")
                    return False

                tx_type = PaymentTypeManager().get_transaction_type(tx.tx_id)
                required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(tx_type.name, 8)
                
                # ✅ Ensure transaction IDs are double-hashed
                double_hashed_tx_id = Hashing.double_sha3_384(tx.tx_id.encode())

                confirmations = self.storage_manager.get_transaction_confirmations(double_hashed_tx_id)
                if confirmations is None or confirmations < required_confirmations:
                    logging.error(f"[ERROR] ❌ Transaction {tx.tx_id} in Block {current_block.index} does not meet required confirmations ({required_confirmations}). Found: {confirmations}")
                    return False

            # ✅ Validate previous hash linkage (skip for Genesis block)
            if i > 0:
                prev_block = self.chain[i - 1]
                if not hasattr(prev_block, "hash"):
                    logging.error(f"[ERROR] ❌ Previous block {i-1} is missing a valid hash.")
                    return False

                if current_block.previous_hash != prev_block.hash:
                    logging.error(f"[ERROR] ❌ Block {i} has a previous hash mismatch. Expected: {prev_block.hash}, Found: {current_block.previous_hash}")
                    return False

            # ✅ Validate difficulty dynamically
            try:
                block_difficulty = int(current_block.header.difficulty)
                if int(current_block.hash, 16) >= block_difficulty:
                    logging.error(f"[ERROR] ❌ Block {i} does not meet the difficulty target. Expected < {hex(block_difficulty)}, Found: {current_block.hash}")
                    return False
            except (ValueError, TypeError) as e:
                logging.error(f"[ERROR] ❌ Invalid difficulty value in Block {i}: {e}")
                return False

            # ✅ Verify block integrity (hash correctness) using double SHA3-384
            expected_hash = Hashing.double_sha3_384(current_block.calculate_hash().encode())
            if current_block.hash != expected_hash:
                logging.error(f"[ERROR] ❌ Block {i} hash mismatch (possible corruption). Expected: {expected_hash}, Found: {current_block.hash}")
                return False

        logging.info("[INFO] ✅ Blockchain validation passed.")
        return True


















    def calculate_target(self, storage_manager):
        """
        Dynamically adjusts mining difficulty based on actual vs. expected block times.
        Uses `Constants.DIFFICULTY_ADJUSTMENT_INTERVAL` to determine difficulty adjustments.
        """
        try:
            stored_blocks = storage_manager.get_all_blocks()
            num_blocks = len(stored_blocks)

            if num_blocks == 0:
                logging.info("[DIFFICULTY] ❌ No blocks found. Using Genesis Target.")
                return Constants.GENESIS_TARGET

            last_block = stored_blocks[-1]

            # ✅ Ensure block header exists before accessing difficulty
            if "header" not in last_block or "difficulty" not in last_block["header"]:
                logging.error("[DIFFICULTY ERROR] ❌ Last block is missing a valid header or difficulty value.")
                return Constants.GENESIS_TARGET

            try:
                last_difficulty = int(str(last_block["header"].get("difficulty", Constants.GENESIS_TARGET)), 16)
            except ValueError as e:
                logging.error(f"[DIFFICULTY ERROR] ❌ Failed to convert difficulty value: {e}")
                return Constants.GENESIS_TARGET

            # ✅ Ensure at least `DIFFICULTY_ADJUSTMENT_INTERVAL` blocks exist before adjusting difficulty
            if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL:
                logging.info("[DIFFICULTY] ⚠️ Not enough blocks for adjustment. Using last difficulty.")
                return last_difficulty

            # ✅ Get the block at the difficulty adjustment interval
            first_block = stored_blocks[-Constants.DIFFICULTY_ADJUSTMENT_INTERVAL]

            # ✅ Validate timestamps before computing time difference
            if "timestamp" not in last_block["header"] or "timestamp" not in first_block["header"]:
                logging.error("[DIFFICULTY ERROR] ❌ One of the blocks is missing a timestamp.")
                return last_difficulty

            try:
                last_block_timestamp = int(last_block["header"]["timestamp"])
                first_block_timestamp = int(first_block["header"]["timestamp"])
            except ValueError as e:
                logging.error(f"[DIFFICULTY ERROR] ❌ Invalid timestamp format: {e}")
                return last_difficulty

            # ✅ Calculate actual vs expected block mining time
            actual_time_taken = max(1, last_block_timestamp - first_block_timestamp)  # Prevent division by zero
            expected_time = Constants.DIFFICULTY_ADJUSTMENT_INTERVAL * Constants.TARGET_BLOCK_TIME

            # ✅ Compute adjustment ratio
            adjustment_ratio = expected_time / actual_time_taken
            adjustment_ratio = max(Constants.MIN_DIFFICULTY_FACTOR, min(Constants.MAX_DIFFICULTY_FACTOR, adjustment_ratio))

            # ✅ Compute new difficulty target
            new_target = int(last_difficulty * adjustment_ratio)

            # ✅ Ensure difficulty target remains within limits
            new_target = max(min(new_target, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

            logging.info(f"[DIFFICULTY] 🔄 Adjusted difficulty to {hex(new_target)} at block {num_blocks}. (Ratio: {adjustment_ratio:.4f})")
            return new_target

        except Exception as e:
            logging.error(f"[ERROR] ❌ Exception in difficulty calculation: {str(e)}")
            return Constants.GENESIS_TARGET











    def get_average_block_time(self, storage_manager):
        """
        Get the rolling average block mining time over the last `DIFFICULTY_ADJUSTMENT_INTERVAL` blocks.
        """
        stored_blocks = storage_manager.get_all_blocks()
        num_blocks = len(stored_blocks)

        if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL + 1:
            logging.warning(f"[DIFFICULTY] Not enough blocks ({num_blocks}) for full difficulty adjustment.")
            return Constants.TARGET_BLOCK_TIME

        times = [
            stored_blocks[i]["header"]["timestamp"] - stored_blocks[i - 1]["header"]["timestamp"]
            for i in range(num_blocks - Constants.DIFFICULTY_ADJUSTMENT_INTERVAL, num_blocks)
        ]

        avg_time = sum(times) / len(times) if times else Constants.TARGET_BLOCK_TIME
        logging.info(f"[DIFFICULTY] Average block time: {avg_time:.2f} sec (Target: {Constants.TARGET_BLOCK_TIME} sec)")
        return avg_time
    


    def calculate_merkle_root(self, transactions):
        """
        Compute the Merkle root using double SHA3-384.
        """
        try:
            # ✅ Ensure transactions is a valid list
            if not isinstance(transactions, list):
                logging.error("[MERKLE ERROR] ❌ Transactions input must be a list.")
                return Constants.ZERO_HASH

            if not transactions:
                logging.warning("[MERKLE] ⚠️ No transactions found. Returning ZERO_HASH.")
                return Constants.ZERO_HASH

            # ✅ Compute initial transaction hashes
            tx_hashes = []
            for tx in transactions:
                try:
                    tx_serialized = json.dumps(tx.to_dict() if hasattr(tx, "to_dict") else tx, sort_keys=True).encode()
                    tx_hashes.append(Hashing.double_sha3_384(tx_serialized))
                except (TypeError, ValueError) as e:
                    logging.error(f"[MERKLE ERROR] ❌ Failed to serialize transaction: {e}")
                    return Constants.ZERO_HASH  # Return ZERO_HASH if serialization fails

            # ✅ Compute Merkle root
            while len(tx_hashes) > 1:
                if len(tx_hashes) % 2 != 0:
                    tx_hashes.append(tx_hashes[-1])  # Duplicate last hash if odd number

                # ✅ Optimize list processing by using list comprehension
                tx_hashes = [
                    Hashing.double_sha3_384((tx_hashes[i] + tx_hashes[i + 1]).encode())
                    for i in range(0, len(tx_hashes), 2)
                ]

            logging.info(f"[MERKLE] ✅ Merkle Root Computed: {tx_hashes[0]}")
            return tx_hashes[0]

        except Exception as e:
            logging.error(f"[MERKLE ERROR] ❌ Exception while computing Merkle root: {str(e)}")
            return Constants.ZERO_HASH





    def send_block_information(self, block):
        """
        Store block data via StorageManager.
        """
        try:
            self.storage_manager.store_block(block, block.header.difficulty)
            logging.info(f"[INFO] ✅ Block {block.index} stored successfully. Difficulty: {hex(block.header.difficulty)}")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to store block {block.index}: {e}")
            raise

    
    def add_block(self, block):
        """
        Add a validated block to the chain and adjust difficulty if needed.
        """
        self.chain.append(block)
        logging.info(f"[INFO] ✅ Block {block.index} added. Difficulty: {hex(block.header.difficulty)}")

        # Ensure difficulty is updated every adjustment interval
        if len(self.chain) % Constants.DIFFICULTY_ADJUSTMENT_INTERVAL == 0:
            self.difficulty_target = self.adjust_difficulty(self.storage_manager)

    def get_latest_block(self):
        """
        Retrieve the latest block from storage.
        """
        return self.chain[-1] if self.chain else None






        
    def adjust_difficulty(self, storage_manager):
        """
        Adjust mining difficulty based on actual vs. expected block times.
        Ensures difficulty is updated every `DIFFICULTY_ADJUSTMENT_INTERVAL` blocks.
        """
        try:
            stored_blocks = storage_manager.get_all_blocks()
            num_blocks = len(stored_blocks)

            if num_blocks == 0:
                logging.info("[DIFFICULTY] ❌ No blocks found. Using Genesis Target.")
                return Constants.GENESIS_TARGET

            # ✅ Ensure at least `DIFFICULTY_ADJUSTMENT_INTERVAL` blocks exist before adjusting difficulty
            if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL:
                logging.info(f"[DIFFICULTY] ⚠️ Not enough blocks ({num_blocks}) for difficulty adjustment. Using last recorded difficulty.")
                last_diff = stored_blocks[-1]["header"].get("difficulty", Constants.GENESIS_TARGET)
                try:
                    return int(last_diff, 16) if isinstance(last_diff, str) else last_diff
                except ValueError as e:
                    logging.error(f"[DIFFICULTY ERROR] ❌ Failed to convert last difficulty: {e}")
                    return Constants.GENESIS_TARGET

            # ✅ Retrieve first and last block within the adjustment interval
            first_block = stored_blocks[-Constants.DIFFICULTY_ADJUSTMENT_INTERVAL]
            last_block = stored_blocks[-1]

            # ✅ Validate timestamps before computing time difference
            if "timestamp" not in last_block["header"] or "timestamp" not in first_block["header"]:
                logging.error("[DIFFICULTY ERROR] ❌ One of the blocks is missing a timestamp.")
                return Constants.GENESIS_TARGET

            try:
                last_block_timestamp = int(last_block["header"]["timestamp"])
                first_block_timestamp = int(first_block["header"]["timestamp"])
            except ValueError as e:
                logging.error(f"[DIFFICULTY ERROR] ❌ Invalid timestamp format: {e}")
                return Constants.GENESIS_TARGET

            # ✅ Calculate actual vs. expected block mining time
            actual_time_taken = max(1, last_block_timestamp - first_block_timestamp)  # Prevent division by zero
            expected_time = Constants.DIFFICULTY_ADJUSTMENT_INTERVAL * Constants.TARGET_BLOCK_TIME

            # ✅ Compute adjustment ratio
            adjustment_ratio = expected_time / actual_time_taken
            adjustment_ratio = max(Constants.MIN_DIFFICULTY_FACTOR, min(Constants.MAX_DIFFICULTY_FACTOR, adjustment_ratio))

            # ✅ Retrieve last difficulty and ensure it's a valid integer
            try:
                last_difficulty = int(str(last_block["header"].get("difficulty", Constants.GENESIS_TARGET)), 16)
            except ValueError as e:
                logging.error(f"[DIFFICULTY ERROR] ❌ Failed to retrieve last difficulty: {e}")
                return Constants.GENESIS_TARGET

            # ✅ Compute new difficulty target
            new_target = int(last_difficulty * adjustment_ratio)

            # ✅ Ensure difficulty target remains within limits
            new_target = max(min(new_target, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

            logging.info(f"[DIFFICULTY] 🔄 Adjusted difficulty to {hex(new_target)} at block {num_blocks}. (Ratio: {adjustment_ratio:.4f})")
            return new_target

        except Exception as e:
            logging.error(f"[ERROR] ❌ Unexpected error during difficulty adjustment: {str(e)}")
            return Constants.GENESIS_TARGET
