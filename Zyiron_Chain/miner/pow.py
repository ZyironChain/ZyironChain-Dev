import time
import hashlib
import math
from decimal import Decimal
import json

import sys
import os
from typing import List, Optional
# Adjust Python path for project structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.hashing import Hashing

class PowManager:
    """
    Manages Proof-of-Work (PoW) operations for a block.

    - Uses only single SHA3-384 hashing via Hashing.hash().
    - Retrieves necessary constants from Constants.
    - Provides detailed print statements for progress and errors.
    """

    def __init__(self, block_storage):
        """
        Initializes PowManager with access to block storage.

        :param block_storage: The storage handler for full blocks.
        """
        self.block_storage = block_storage  # ✅ Ensure `block_storage` is properly assigned

    def adjust_difficulty(self):
        """
        Adjust the difficulty based on actual vs. expected block times.
        Implement your logic using data from self.block_storage if needed.
        """
        print("[PowManager.adjust_difficulty] INFO: Adjusting difficulty...")
        # TODO: Retrieve blocks from block_storage, compute average times, adjust difficulty
        # Return new difficulty (as int or hex)
        return int(Constants.GENESIS_TARGET, 16)  # example fallback

    def validate_proof_of_work(self, block):
        """
        Validate a block's Proof-of-Work by checking if block.hash < block.difficulty.
        
        :param block: The block to validate.
        :return: True if PoW is correct, False otherwise.
        """
        print(f"[PowManager.validate_proof_of_work] INFO: Validating PoW for block {block.index}...")
        try:
            # ✅ **Ensure difficulty is stored as an integer**
            if isinstance(block.difficulty, str):
                try:
                    difficulty_int = int(block.difficulty, 16)  # Convert from hex if needed
                except ValueError:
                    print(f"[PowManager.validate_proof_of_work] ❌ ERROR: Invalid difficulty format: {block.difficulty}")
                    return False
            elif isinstance(block.difficulty, int):
                difficulty_int = block.difficulty  # Already an integer
            else:
                print(f"[PowManager.validate_proof_of_work] ❌ ERROR: Unexpected difficulty type: {type(block.difficulty)}")
                return False

            # ✅ **Ensure block.hash is properly formatted**
            if not isinstance(block.hash, str) or len(block.hash) != 96:
                print(f"[PowManager.validate_proof_of_work] ❌ ERROR: Invalid block hash format: {block.hash}")
                return False

            block_hash_int = int(block.hash, 16)  # Convert hash from hex to integer

            # ✅ **Validate Proof-of-Work condition**
            if block_hash_int < difficulty_int:
                print(f"[PowManager.validate_proof_of_work] ✅ SUCCESS: Block {block.index} PoW is valid.")
                return True
            else:
                print(f"[PowManager.validate_proof_of_work] ❌ ERROR: Block {block.index} PoW is invalid (hash > difficulty).")
                return False

        except Exception as e:
            print(f"[PowManager.validate_proof_of_work] ❌ ERROR: {e}")
            return False


    def perform_pow(self, block):
        """
        Performs Proof-of-Work by incrementing the nonce until a valid hash is found.
        - Uses `block.calculate_hash()` to compute hash.
        - Ensures the correct mined hash is assigned to `block.mined_hash`.
        """
        try:
            print(f"[PowManager.perform_pow] INFO: Starting Proof-of-Work for block {block.index}...")

            # ✅ Ensure difficulty is an integer
            difficulty_int = int(block.difficulty, 16) if isinstance(block.difficulty, str) else block.difficulty

            # ✅ Prevent infinite loops with a reasonable nonce limit
            max_nonce_limit = 2**64 - 1  # ✅ Avoid integer overflow

            # ✅ Initialize mining variables
            nonce = 0
            start_time = time.time()

            while nonce < max_nonce_limit:
                block.nonce = nonce  # ✅ Update nonce for each iteration

                # ✅ Compute the block's hash using `calculate_hash()`
                block_hash_hex = block.calculate_hash()  # **Ensures PoW-mined hash is used**

                if int(block_hash_hex, 16) < difficulty_int:
                    elapsed_time = time.time() - start_time
                    print(f"[PowManager.perform_pow] ✅ SUCCESS: Block {block.index} mined after {nonce} attempts in {elapsed_time:.2f} seconds.")

                    # ✅ **Ensure `mined_hash` is assigned only once**
                    if not hasattr(block, "mined_hash") or not block.mined_hash:
                        block.mined_hash = block_hash_hex  # **Fix: Ensure `mined_hash` is stored correctly**

                    return block_hash_hex, nonce  # ✅ Return correct hash and nonce

                nonce += 1

                # ✅ Log mining progress every 100,000 attempts
                if nonce % 100000 == 0:
                    elapsed_time = time.time() - start_time
                    print(f"[PowManager.perform_pow] INFO: Nonce {nonce}, Elapsed Time: {elapsed_time:.2f}s, Last Hash: {block_hash_hex[:12]}...")

            print("[PowManager.perform_pow] ❌ ERROR: Max nonce limit reached! Mining aborted.")
            return None, None  # **Abort if mining fails due to nonce overflow**

        except Exception as e:
            print(f"[PowManager.perform_pow] ❌ ERROR: Proof-of-Work failed: {e}")
            return None, None





    def adjust_difficulty(self):
        """
        Adjusts mining difficulty based on actual versus expected block times.
        """
        try:
            print("[PowManager.adjust_difficulty] INFO: Initiating difficulty adjustment...")

            # ✅ **Retrieve all stored blocks**
            stored_blocks = self.block_storage.get_all_blocks()  # ✅ Uses `block_storage`
            num_blocks = len(stored_blocks)

            if num_blocks == 0:
                print("[PowManager.adjust_difficulty] INFO: No blocks found; using Genesis Target.")
                return Constants.GENESIS_TARGET

            # ✅ **Use Last Block's Difficulty**
            last_block = stored_blocks[-1]
            if "difficulty" not in last_block:
                print("[PowManager.adjust_difficulty] ERROR: Last block is missing difficulty field.")
                return Constants.GENESIS_TARGET

            try:
                last_diff_str = str(last_block.get("difficulty", Constants.GENESIS_TARGET)).lower().strip()
                
                # Ensure it starts with `0x`, otherwise convert manually
                if last_diff_str.startswith("0x"):
                    last_difficulty = int(last_diff_str, 16)  # ✅ Proper conversion from hex
                else:
                    last_difficulty = int("0x" + last_diff_str, 16)  # ✅ Force hex conversion if `0x` is missing

            except ValueError as e:
                print(f"[PowManager.adjust_difficulty] ERROR: Failed to convert last difficulty: {e} | Value: {last_diff_str}")
                return Constants.GENESIS_TARGET

            # ✅ **Ensure Enough Blocks for Difficulty Adjustment**
            if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL:
                print(f"[PowManager.adjust_difficulty] INFO: Insufficient blocks ({num_blocks}) for adjustment. Using last difficulty.")
                return last_difficulty

            first_block = stored_blocks[-Constants.DIFFICULTY_ADJUSTMENT_INTERVAL]

            # ✅ **Ensure Timestamps Exist**
            try:
                last_timestamp = int(last_block.get("timestamp", 0))
                first_timestamp = int(first_block.get("timestamp", 0))
            except (ValueError, TypeError) as e:
                print(f"[PowManager.adjust_difficulty] ERROR: Invalid timestamp format: {e}")
                return last_difficulty

            if last_timestamp == 0 or first_timestamp == 0:
                print("[PowManager.adjust_difficulty] ERROR: Missing timestamps in blocks. Cannot adjust difficulty.")
                return last_difficulty

            # ✅ **Calculate Actual vs. Expected Block Time**
            actual_time = max(1, last_timestamp - first_timestamp)  # Prevent division errors
            expected_time = Constants.DIFFICULTY_ADJUSTMENT_INTERVAL * Constants.TARGET_BLOCK_TIME

            # ✅ **Calculate Difficulty Adjustment Ratio**
            ratio = expected_time / actual_time
            ratio = max(Constants.MIN_DIFFICULTY_FACTOR, min(Constants.MAX_DIFFICULTY_FACTOR, ratio))  # Clamp ratio

            # ✅ **Apply Difficulty Adjustment**
            new_target = int(last_difficulty * ratio)
            new_target = max(min(new_target, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

            print(f"[PowManager.adjust_difficulty] SUCCESS: Adjusted difficulty to {hex(new_target)} "
                f"at block count {num_blocks} (Ratio: {ratio:.4f}).")

            return new_target  # ✅ Now returns difficulty as an **integer**

        except Exception as e:
            print(f"[PowManager.adjust_difficulty] ERROR: Unexpected error during difficulty adjustment: {e}")
            return Constants.GENESIS_TARGET

    def get_average_block_time(self):
        """
        Computes the rolling average block time over the last N blocks,
        where N is Constants.DIFFICULTY_ADJUSTMENT_INTERVAL.
        Ensures **block timestamps do not exceed MAX_TIME_DRIFT** before calculation.

        Returns:
            int: The calculated average block time or Constants.TARGET_BLOCK_TIME.
        """
        try:
            print("[PowManager.get_average_block_time] INFO: Calculating average block time...")

            stored_blocks = self.block_storage.get_all_blocks()  # ✅ Uses `block_storage`
            num_blocks = len(stored_blocks)

            # ✅ **Ensure Enough Blocks for Calculation**
            if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL + 1:
                print(f"[PowManager.get_average_block_time] WARNING: Only {num_blocks} blocks available. Using target block time.")
                return Constants.TARGET_BLOCK_TIME

            times = []
            start_index = num_blocks - Constants.DIFFICULTY_ADJUSTMENT_INTERVAL

            # ✅ **Calculate Time Differences Between Blocks**
            for i in range(start_index + 1, num_blocks):
                try:
                    prev_timestamp = int(stored_blocks[i - 1]["header"].get("timestamp", 0))
                    curr_timestamp = int(stored_blocks[i]["header"].get("timestamp", 0))

                    # ✅ **Validate Timestamps Before Processing**
                    if prev_timestamp == 0 or curr_timestamp == 0:
                        print(f"[PowManager.get_average_block_time] ERROR: Block {i} has invalid timestamps. Skipping.")
                        continue

                    diff = max(1, curr_timestamp - prev_timestamp)  # ✅ Prevents division errors

                    # ✅ **Ensure Timestamp Validation Within Allowed Drift**
                    if diff > Constants.MAX_TIME_DRIFT:
                        print(f"[PowManager.get_average_block_time] ERROR: Block {i} timestamp drift exceeds {Constants.MAX_TIME_DRIFT}s. Skipping.")
                        continue

                    times.append(diff)

                except (ValueError, TypeError) as e:
                    print(f"[PowManager.get_average_block_time] ERROR: Invalid timestamp format in block {i}: {e}")

            avg_time = sum(times) / len(times) if times else Constants.TARGET_BLOCK_TIME
            print(f"[PowManager.get_average_block_time] SUCCESS: Computed average block time: {avg_time:.2f} sec.")
            return avg_time

        except Exception as e:
            print(f"[PowManager.get_average_block_time] ERROR: Failed to calculate average block time: {e}")
            return Constants.TARGET_BLOCK_TIME
