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
        for i in range(len(self.chain)):
            current_block = self.chain[i]

            # ✅ Validate confirmations for transactions
            for tx in current_block.transactions:
                tx_type = PaymentTypeManager().get_transaction_type(tx.tx_id)
                required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(tx_type.name, Constants.CONFIRMATION_RULES["minimum_required"])
                
                if self.storage_manager.get_transaction_confirmations(tx.tx_id) < required_confirmations:
                    logging.error(f"Transaction {tx.tx_id} in Block {current_block.index} does not meet required confirmations ({required_confirmations})")
                    return False

            # ✅ Validate previous hash linkage (skip for Genesis block)
            if i > 0:
                prev_block = self.chain[i - 1]
                if current_block.previous_hash != prev_block.hash:
                    logging.error(f"Block {i} has a previous hash mismatch.")
                    return False

            # ✅ Validate difficulty dynamically
            if int(current_block.hash, 16) >= current_block.header.difficulty:
                logging.error(f"Block {i} does not meet the difficulty target.")
                return False

            # ✅ Verify block integrity (hash correctness)
            if current_block.hash != current_block.calculate_hash():
                logging.error(f"Block {i} hash mismatch (possible corruption).")
                return False

        return True

















    def calculate_target(self, storage_manager):
        """
        Dynamically adjusts mining difficulty based on actual vs. expected block times.
        Uses CONFIRMATION_RULES["finalization_threshold"] to determine difficulty adjustments.
        """
        try:
            if not hasattr(storage_manager, "get_all_blocks"):
                logging.error("[ERROR] StorageManager is missing 'get_all_blocks()' method!")
                return Constants.GENESIS_TARGET

            stored_blocks = storage_manager.get_all_blocks()
            num_blocks = len(stored_blocks)

            if num_blocks == 0:
                logging.info("[DIFFICULTY] No blocks found. Using Genesis Target.")
                return Constants.GENESIS_TARGET

            last_block = stored_blocks[-1]
            last_difficulty = int(last_block["header"].get("difficulty", Constants.GENESIS_TARGET), 16)

            # Ensure at least finalization_threshold blocks exist before adjusting difficulty
            if num_blocks < Constants.CONFIRMATION_RULES["finalization_threshold"]:
                logging.info("[DIFFICULTY] Not enough blocks for adjustment. Using last difficulty.")
                return last_difficulty

            # Get the block at the finalization_threshold interval
            first_block = stored_blocks[-Constants.CONFIRMATION_RULES["finalization_threshold"]]
            
            # Calculate actual vs expected block mining time
            actual_time_taken = last_block["header"]["timestamp"] - first_block["header"]["timestamp"]
            expected_time = Constants.CONFIRMATION_RULES["finalization_threshold"] * Constants.TARGET_BLOCK_TIME

            # Compute adjustment ratio
            adjustment_ratio = expected_time / max(actual_time_taken, 1)  # Prevent division by zero
            adjustment_ratio = max(Constants.MIN_DIFFICULTY_FACTOR, min(Constants.MAX_DIFFICULTY_FACTOR, adjustment_ratio))

            # Compute new difficulty target
            new_target = int(last_difficulty * adjustment_ratio)

            # Enforce difficulty limits
            new_target = max(min(new_target, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

            logging.info(f"[DIFFICULTY] Adjusted difficulty to {hex(new_target)} at block {num_blocks} based on finalization_threshold of {Constants.CONFIRMATION_RULES['finalization_threshold']}")

            return new_target

        except Exception as e:
            logging.error(f"[ERROR] Exception in difficulty calculation: {str(e)}")
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
        Compute the Merkle root using SHA3-384.
        """
        if not transactions:
            return Constants.ZERO_HASH

        tx_hashes = [
            hashlib.sha3_384(json.dumps(tx.to_dict() if hasattr(tx, "to_dict") else tx, sort_keys=True).encode()).hexdigest()
            for tx in transactions
        ]

        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])

            tx_hashes = [
                hashlib.sha3_384((tx_hashes[i] + tx_hashes[i + 1]).encode()).hexdigest()
                for i in range(0, len(tx_hashes), 2)
            ]

        return tx_hashes[0]




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
        Ensures difficulty is updated every DIFFICULTY_ADJUSTMENT_INTERVAL blocks.
        """
        try:
            stored_blocks = storage_manager.get_all_blocks()
            num_blocks = len(stored_blocks)
            if num_blocks == 0:
                logging.info("[DIFFICULTY] No blocks found. Using Genesis Target.")
                return Constants.GENESIS_TARGET

            if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL:
                logging.info(f"[DIFFICULTY] Not enough blocks ({num_blocks}) for difficulty adjustment. Using last recorded difficulty.")
                last_diff = stored_blocks[-1]["header"].get("difficulty", Constants.GENESIS_TARGET)
                if isinstance(last_diff, int):
                    return last_diff
                else:
                    return int(last_diff, 16)

            # Retrieve first and last block within the adjustment interval
            first_block = stored_blocks[-Constants.DIFFICULTY_ADJUSTMENT_INTERVAL]
            last_block = stored_blocks[-1]

            # Calculate actual vs. expected time
            actual_time_taken = last_block["header"]["timestamp"] - first_block["header"]["timestamp"]
            expected_time = Constants.DIFFICULTY_ADJUSTMENT_INTERVAL * Constants.TARGET_BLOCK_TIME

            adjustment_ratio = expected_time / max(actual_time_taken, 1)
            adjustment_ratio = max(Constants.MIN_DIFFICULTY_FACTOR, min(Constants.MAX_DIFFICULTY_FACTOR, adjustment_ratio))

            last_diff = last_block["header"].get("difficulty", Constants.GENESIS_TARGET)
            if isinstance(last_diff, int):
                last_difficulty = last_diff
            else:
                last_difficulty = int(last_diff, 16)

            new_target = int(last_difficulty * adjustment_ratio)
            new_target = max(min(new_target, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

            logging.info(f"[DIFFICULTY] Adjusted difficulty: {hex(new_target)} at block {num_blocks} (Ratio: {adjustment_ratio:.4f})")
            return new_target

        except Exception as e:
            logging.error(f"[ERROR] Unexpected error during difficulty adjustment: {e}")
            return Constants.GENESIS_TARGET
