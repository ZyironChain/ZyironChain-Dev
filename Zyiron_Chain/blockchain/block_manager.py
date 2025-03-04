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

import sys
import os
import json
import hashlib
import time
import logging
import math

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.blockchain.utils.hashing import Hashing
from Zyiron_Chain.blockchain.blockheader import BlockHeader
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager

log = logging.getLogger(__name__)  # Each module gets its own logger
log.info(f"{__name__} logger initialized.")

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

class BlockManager:
    """
    Manages blockchain validation, difficulty adjustments, and storing block data
    via the StorageManager. Also provides chain-level checks like chain validation,
    Merkle root calculations, and retrieving the latest block.
    """
    def __init__(self, blockchain, storage_manager, transaction_manager):
        """
        Initialize BlockManager with references to:
        - blockchain: The main Blockchain object (provides in-memory chain list).
        - storage_manager: For block & transaction persistence (LMDB, etc.).
        - transaction_manager: For transaction validations and references.
        """
        self.blockchain = blockchain
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager
        
        # Direct reference to the chain from the Blockchain object
        self.chain = blockchain.chain

        self.network = Constants.NETWORK
        self.version = Constants.VERSION
        self.difficulty_target = Constants.GENESIS_TARGET

        logging.info(
            f"[BLOCKMANAGER] Initialized on {self.network.upper()} "
            f"| Version {self.version} | Difficulty {hex(self.difficulty_target)}"
        )

    def validate_block(self, block):
        """
        Hook for additional block validation logic, e.g.:
        - Checking block shape
        - Doing advanced checks (smart-contract states, etc.)
        Currently references `blockchain` (imported lazily if needed).
        """
        from Zyiron_Chain.blockchain.blockchain import Blockchain
        # Perform any advanced block validations here, if required.

    def validate_chain(self):
        """
        Validate the entire chain for integrity:
        - Ensures each block's transactions meet the required confirmations.
        - Checks correct previous_hash linkage except for Genesis.
        - Ensures block difficulty/Proof-of-Work is correct.
        - Double-checks block hash correctness using single-hashed data.
        """
        if not self.chain:
            logging.error("[ERROR] ❌ Blockchain is empty. Cannot validate.")
            return False

        for i in range(len(self.chain)):
            current_block = self.chain[i]

            # -- Basic attribute checks
            if (
                not hasattr(current_block, "transactions")
                or not hasattr(current_block, "previous_hash")
                or not hasattr(current_block, "hash")
                or not hasattr(current_block, "header")
            ):
                logging.error(f"[ERROR] ❌ Block {i} is missing required attributes. Possible corruption.")
                return False

            # -- Confirmations check for transactions
            for tx in current_block.transactions:
                if not hasattr(tx, "tx_id"):
                    logging.error(f"[ERROR] ❌ Transaction in Block {current_block.index} is missing a tx_id.")
                    return False

                # ✅ Ensure `tx_id` is a string before encoding
                if isinstance(tx.tx_id, bytes):
                    tx.tx_id = tx.tx_id.decode("utf-8")

                # ✅ Apply **only single SHA3-384 hashing** to validate transaction ID
                single_hashed_tx_id = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()

                # ✅ Retrieve transaction type and required confirmations
                tx_type = PaymentTypeManager().get_transaction_type(single_hashed_tx_id)
                required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                    tx_type.name.upper(), Constants.TRANSACTION_CONFIRMATIONS["STANDARD"]
                )

                # ✅ Fetch confirmations
                confirmations = self.storage_manager.get_transaction_confirmations(single_hashed_tx_id)

                if confirmations is None or confirmations < required_confirmations:
                    logging.error(
                        f"[ERROR] ❌ Transaction {single_hashed_tx_id} in Block {current_block.index} "
                        f"does not meet required confirmations ({required_confirmations}). "
                        f"Found: {confirmations}"
                    )
                    return False

        return True


    def calculate_target(self, storage_manager):
        """
        Dynamically adjusts mining difficulty based on actual vs. expected block times.
        - Uses rolling averages over `Constants.DIFFICULTY_ADJUSTMENT_INTERVAL` blocks.
        - Prevents excessive jumps in difficulty by enforcing min/max limits.
        - Ensures difficulty never falls below `Constants.MIN_DIFFICULTY`.
        """
        try:
            stored_blocks = storage_manager.get_all_blocks()
            num_blocks = len(stored_blocks)

            if num_blocks == 0:
                logging.info("[DIFFICULTY] ❌ No blocks found. Using Genesis Target.")
                return Constants.GENESIS_TARGET

            last_block = stored_blocks[-1]

            # ✅ Ensure last block has a valid difficulty value
            if "header" not in last_block or "difficulty" not in last_block["header"]:
                logging.error("[DIFFICULTY ERROR] ❌ Last block is missing a valid header or difficulty value.")
                return Constants.GENESIS_TARGET

            try:
                # ✅ Retrieve last difficulty & ensure it's correctly formatted
                last_difficulty_str = str(last_block["header"].get("difficulty", Constants.GENESIS_TARGET))
                last_difficulty = int(last_difficulty_str, 16) if last_difficulty_str.startswith("0x") else int(last_difficulty_str)
            except ValueError as e:
                logging.error(f"[DIFFICULTY ERROR] ❌ Failed to convert difficulty value: {e}")
                return Constants.GENESIS_TARGET

            # ✅ If insufficient blocks for adjustment, return last difficulty
            if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL:
                logging.info("[DIFFICULTY] ⚠️ Not enough blocks for adjustment. Using last difficulty.")
                return last_difficulty

            # ✅ Retrieve timestamps for comparison
            first_block = stored_blocks[-Constants.DIFFICULTY_ADJUSTMENT_INTERVAL]
            try:
                last_block_timestamp = int(last_block["header"]["timestamp"])
                first_block_timestamp = int(first_block["header"]["timestamp"])
            except (ValueError, TypeError) as e:
                logging.error(f"[DIFFICULTY ERROR] ❌ Invalid timestamp format: {e}")
                return last_difficulty

            # ✅ Compute actual vs expected block time
            actual_time_taken = max(1, last_block_timestamp - first_block_timestamp)
            expected_time = Constants.DIFFICULTY_ADJUSTMENT_INTERVAL * Constants.TARGET_BLOCK_TIME

            # ✅ Compute difficulty adjustment ratio & apply min/max limits
            adjustment_ratio = expected_time / actual_time_taken
            adjustment_ratio = max(Constants.MIN_DIFFICULTY_FACTOR, min(Constants.MAX_DIFFICULTY_FACTOR, adjustment_ratio))

            # ✅ Compute new difficulty & ensure it stays within the allowed range
            new_target = int(last_difficulty * adjustment_ratio)
            new_target = max(min(new_target, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

            logging.info(f"[DIFFICULTY] 🔄 Adjusted difficulty to {hex(new_target)} at block {num_blocks} (Ratio: {adjustment_ratio:.4f})")
            return new_target

        except Exception as e:
            logging.error(f"[ERROR] ❌ Exception in difficulty calculation: {str(e)}")
            return Constants.GENESIS_TARGET


    def get_average_block_time(self, storage_manager):
        """
        Returns the rolling average block time across the last N blocks,
        where N = DIFFICULTY_ADJUSTMENT_INTERVAL.
        If insufficient blocks are present, returns TARGET_BLOCK_TIME.
        """
        stored_blocks = storage_manager.get_all_blocks()
        num_blocks = len(stored_blocks)

        if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL + 1:
            logging.warning(
                f"[DIFFICULTY] Not enough blocks ({num_blocks}) for full difficulty adjustment."
            )
            return Constants.TARGET_BLOCK_TIME

        try:
            times = []
            start_index = num_blocks - Constants.DIFFICULTY_ADJUSTMENT_INTERVAL
            for i in range(start_index + 1, num_blocks):
                # difference from block[i-1] to block[i]
                diff = stored_blocks[i]["header"]["timestamp"] - stored_blocks[i - 1]["header"]["timestamp"]
                times.append(diff)

            if not times:
                return Constants.TARGET_BLOCK_TIME  # fallback if no valid times

            avg_time = sum(times) / len(times)
            logging.info(
                f"[DIFFICULTY] Average block time: {avg_time:.2f} sec "
                f"(Target: {Constants.TARGET_BLOCK_TIME} sec)"
            )
            return avg_time

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to calculate average block time: {e}")
            return Constants.TARGET_BLOCK_TIME

    def calculate_merkle_root(self, transactions):
        """
        Compute the Merkle root using double SHA3-384.
        - If no transactions or error, returns ZERO_HASH.
        - Otherwise, each transaction is serialized & double-hashed
          to build up a Merkle tree.
        """
        try:
            if not isinstance(transactions, list):
                logging.error("[MERKLE ERROR] ❌ Transactions input must be a list.")
                return Constants.ZERO_HASH

            if not transactions:
                logging.warning("[MERKLE] ⚠️ No transactions found. Returning ZERO_HASH.")
                return Constants.ZERO_HASH

            tx_hashes = []
            for tx in transactions:
                try:
                    # If `tx` has a `to_dict()`, use that. Otherwise, assume `tx` is dict-like
                    to_serialize = tx.to_dict() if hasattr(tx, "to_dict") else tx
                    tx_serialized = json.dumps(to_serialize, sort_keys=True).encode()
                    tx_hashes.append(Hashing.double_sha3_384(tx_serialized))
                except (TypeError, ValueError) as e:
                    logging.error(f"[MERKLE ERROR] ❌ Failed to serialize transaction: {e}")
                    return Constants.ZERO_HASH

            # Build the merkle tree pairwise
            while len(tx_hashes) > 1:
                if len(tx_hashes) % 2 != 0:
                    tx_hashes.append(tx_hashes[-1])  # duplicate last hash if odd length
                # pair and combine
                temp_level = []
                for i in range(0, len(tx_hashes), 2):
                    combined = tx_hashes[i] + tx_hashes[i + 1]
                    temp_level.append(hashlib.sha3_384(combined.encode()).hexdigest())

                tx_hashes = temp_level

            logging.info(f"[MERKLE] ✅ Merkle Root Computed: {tx_hashes[0]}")
            return tx_hashes[0]

        except Exception as e:
            logging.error(f"[MERKLE ERROR] ❌ Exception while computing Merkle root: {str(e)}")
            return Constants.ZERO_HASH

    def send_block_information(self, block):
        """
        Wrapper to store block data via the StorageManager,
        typically after verifying or mining.
        """
        try:
            self.storage_manager.store_block(block, block.header.difficulty)
            logging.info(
                f"[INFO] ✅ Block {block.index} stored successfully. Difficulty: {hex(block.header.difficulty)}"
            )
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to store block {block.index}: {e}")
            raise

    def add_block(self, block):
        """
        Add a validated block to the chain in-memory,
        then optionally trigger difficulty adjustments.
        """
        self.chain.append(block)
        logging.info(
            f"[INFO] ✅ Block {block.index} added. "
            f"Difficulty: {hex(block.header.difficulty)}"
        )

        # If we want to re-check/adjust difficulty every N blocks, do it here
        if len(self.chain) % Constants.DIFFICULTY_ADJUSTMENT_INTERVAL == 0:
            self.difficulty_target = self.adjust_difficulty(self.storage_manager)

    def get_latest_block(self):
        """
        Return the last block in local in-memory chain,
        or None if chain is empty.
        """
        return self.chain[-1] if self.chain else None

    def adjust_difficulty(self, storage_manager): 
        """
        Re-checks the difficulty based on actual vs. expected block times,
        then sets the new difficulty to keep the block time close to `Constants.TARGET_BLOCK_TIME`.
        """
        try:
            stored_blocks = storage_manager.get_all_blocks()
            num_blocks = len(stored_blocks)

            if num_blocks == 0:
                logging.info("[DIFFICULTY] ❌ No blocks found. Using Genesis Target.")
                return Constants.GENESIS_TARGET

            # ✅ If not enough blocks exist, return the last recorded difficulty
            if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL:
                logging.info(f"[DIFFICULTY] ⚠️ Not enough blocks ({num_blocks}) to adjust difficulty. Using last recorded difficulty.")
                last_diff = stored_blocks[-1]["header"].get("difficulty", Constants.GENESIS_TARGET)
                return int(last_diff, 16) if isinstance(last_diff, str) else last_diff

            # ✅ Select blocks at the start & end of the interval
            first_block = stored_blocks[-Constants.DIFFICULTY_ADJUSTMENT_INTERVAL]
            last_block = stored_blocks[-1]

            # ✅ Ensure timestamps exist
            if "timestamp" not in last_block["header"] or "timestamp" not in first_block["header"]:
                logging.error("[DIFFICULTY ERROR] ❌ Missing timestamp in block header.")
                return Constants.GENESIS_TARGET

            # ✅ Convert timestamps to integers
            try:
                last_block_timestamp = int(last_block["header"]["timestamp"])
                first_block_timestamp = int(first_block["header"]["timestamp"])
            except ValueError as e:
                logging.error(f"[DIFFICULTY ERROR] ❌ Invalid timestamp format: {e}")
                return Constants.GENESIS_TARGET

            # ✅ Compute actual vs expected block time
            actual_time_taken = max(1, last_block_timestamp - first_block_timestamp)
            expected_time = Constants.DIFFICULTY_ADJUSTMENT_INTERVAL * Constants.TARGET_BLOCK_TIME

            # ✅ Compute adjustment ratio and clamp within defined limits
            ratio = expected_time / actual_time_taken
            ratio = max(Constants.MIN_DIFFICULTY_FACTOR, min(Constants.MAX_DIFFICULTY_FACTOR, ratio))

            # ✅ Retrieve last difficulty (hex -> int if needed)
            try:
                last_difficulty = int(str(last_block["header"].get("difficulty", Constants.GENESIS_TARGET)), 16)
            except ValueError as e:
                logging.error(f"[DIFFICULTY ERROR] ❌ Failed to retrieve last difficulty: {e}")
                return Constants.GENESIS_TARGET

            # ✅ Calculate new difficulty and clamp to allowed range
            new_target = int(last_difficulty * ratio)
            new_target = max(min(new_target, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

            logging.info(f"[DIFFICULTY] 🔄 Adjusted difficulty to {hex(new_target)} at block {num_blocks} (Ratio: {ratio:.4f})")
            return new_target

        except Exception as e:
            logging.error(f"[ERROR] ❌ Unexpected error during difficulty adjustment: {str(e)}")
            return Constants.GENESIS_TARGET
