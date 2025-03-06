import time
import hashlib
import math
from decimal import Decimal
import json

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.hashing import Hashing

class PowManager:
    """
    Manages Proof-of-Work (PoW) operations for a block.
    
    - Processes all data as bytes.
    - Uses only single SHA3-384 hashing via Hashing.hash().
    - Retrieves necessary constants from Constants.
    - Provides detailed print statements for progress and errors.
    """
    def perform_pow(self, block):
        """
        Executes the PoW hashing loop for the given block.
        Continuously increments the block's nonce until the computed hash (converted
        to an integer) is lower than the block's difficulty target.
        """
        start_time = time.time()
        nonce = 0
        attempts = 0

        # Debug: Start PoW loop
        print(f"[PowManager.perform_pow] START: Entering PoW loop for Block {block.index}. Target: {block.difficulty}")

        while True:
            block.header.nonce = nonce
            block_data_bytes = block.calculate_hash().encode()
            hash_bytes = Hashing.hash(block_data_bytes)
            hash_int = int.from_bytes(hash_bytes, byteorder='big')

            # Debug: Print progress every 2 seconds
            if attempts % 1000 == 0:  # Print every 1000 attempts to reduce noise
                elapsed = int(time.time() - start_time)
                print(f"[PowManager.perform_pow] Progress: Block {block.index} | Nonce: {nonce} | Attempts: {attempts} | Elapsed: {elapsed}s")

            if hash_int < block.difficulty:
                # Success: Block mined
                elapsed = int(time.time() - start_time)
                print(f"[PowManager.perform_pow] SUCCESS: Block {block.index} mined with nonce {nonce}. Final hash: {hash_bytes.hex()} | Time: {elapsed}s")
                return hash_bytes.hex(), nonce, attempts

            nonce += 1
        attempts += 1

    def adjust_difficulty(self, storage_manager):
        """
        Adjusts mining difficulty based on actual versus expected block times.
        
        Retrieves stored block metadata from the storage_manager, calculates the ratio
        of expected time (Constants.DIFFICULTY_ADJUSTMENT_INTERVAL * TARGET_BLOCK_TIME) to
        the actual time taken, and clamps the adjustment ratio within allowed min/max factors.
        
        Returns:
            int: The new difficulty target.
        """
        try:
            stored_blocks = storage_manager.get_all_blocks()
            num_blocks = len(stored_blocks)
            if num_blocks == 0:
                print("[PowManager.adjust_difficulty] INFO: No blocks found; using Genesis Target.")
                return Constants.GENESIS_TARGET

            # Use the last block's difficulty
            last_block = stored_blocks[-1]
            if "header" not in last_block or "difficulty" not in last_block["header"]:
                print("[PowManager.adjust_difficulty] ERROR: Last block is missing header or difficulty.")
                return Constants.GENESIS_TARGET

            try:
                last_diff_str = str(last_block["header"].get("difficulty", Constants.GENESIS_TARGET))
                last_difficulty = int(last_diff_str, 16) if last_diff_str.startswith("0x") else int(last_diff_str)
            except ValueError as e:
                print(f"[PowManager.adjust_difficulty] ERROR: Failed to convert last difficulty: {e}")
                return Constants.GENESIS_TARGET

            if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL:
                print(f"[PowManager.adjust_difficulty] INFO: Insufficient blocks ({num_blocks}) for adjustment. Using last difficulty.")
                return last_difficulty

            first_block = stored_blocks[-Constants.DIFFICULTY_ADJUSTMENT_INTERVAL]
            try:
                last_timestamp = int(last_block["header"]["timestamp"])
                first_timestamp = int(first_block["header"]["timestamp"])
            except (ValueError, TypeError) as e:
                print(f"[PowManager.adjust_difficulty] ERROR: Invalid timestamp format: {e}")
                return last_difficulty

            actual_time = max(1, last_timestamp - first_timestamp)
            expected_time = Constants.DIFFICULTY_ADJUSTMENT_INTERVAL * Constants.TARGET_BLOCK_TIME
            ratio = expected_time / actual_time
            ratio = max(Constants.MIN_DIFFICULTY_FACTOR, min(Constants.MAX_DIFFICULTY_FACTOR, ratio))

            new_target = int(last_difficulty * ratio)
            new_target = max(min(new_target, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)
            print(f"[PowManager.adjust_difficulty] SUCCESS: Adjusted difficulty to {hex(new_target)} "
                  f"at block count {num_blocks} (Ratio: {ratio:.4f}).")
            return new_target

        except Exception as e:
            print(f"[PowManager.adjust_difficulty] ERROR: Unexpected error during difficulty adjustment: {e}")
            return Constants.GENESIS_TARGET

    def get_average_block_time(self, storage_manager):
        """
        Computes the rolling average block time over the last N blocks,
        where N is Constants.DIFFICULTY_ADJUSTMENT_INTERVAL.
        Returns Constants.TARGET_BLOCK_TIME if insufficient blocks are present.
        """
        try:
            stored_blocks = storage_manager.get_all_blocks()
            num_blocks = len(stored_blocks)
            if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL + 1:
                print(f"[PowManager.get_average_block_time] WARNING: Only {num_blocks} blocks available. Using target block time.")
                return Constants.TARGET_BLOCK_TIME

            times = []
            start_index = num_blocks - Constants.DIFFICULTY_ADJUSTMENT_INTERVAL
            for i in range(start_index + 1, num_blocks):
                diff = stored_blocks[i]["header"]["timestamp"] - stored_blocks[i - 1]["header"]["timestamp"]
                times.append(diff)
            if not times:
                return Constants.TARGET_BLOCK_TIME
            avg_time = sum(times) / len(times)
            print(f"[PowManager.get_average_block_time] INFO: Average block time: {avg_time:.2f} sec (Target: {Constants.TARGET_BLOCK_TIME} sec).")
            return avg_time

        except Exception as e:
            print(f"[PowManager.get_average_block_time] ERROR: Failed to calculate average block time: {e}")
            return Constants.TARGET_BLOCK_TIME