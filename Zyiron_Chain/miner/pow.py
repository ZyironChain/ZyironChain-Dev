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
        - Includes real-time block height in logs.
        """
        try:
            print(f"[PowManager.perform_pow] INFO: Starting Proof-of-Work for block {block.index}...")

            difficulty_int = int(block.difficulty, 16) if isinstance(block.difficulty, str) else block.difficulty
            max_nonce_limit = 4**64 - 1

            nonce = 0
            start_time = time.time()

            while nonce < max_nonce_limit:
                block.nonce = nonce
                block_hash_hex = block.calculate_hash()

                if int(block_hash_hex, 16) < difficulty_int:
                    elapsed_time = time.time() - start_time
                    print(f"[PowManager.perform_pow] ✅ SUCCESS: Block {block.index} mined after {nonce} attempts in {elapsed_time:.2f} seconds.")

                    if not hasattr(block, "mined_hash") or not block.mined_hash:
                        block.mined_hash = block_hash_hex

                    return block_hash_hex, nonce

                nonce += 1

                if nonce % 100000 == 0:
                    elapsed_time = time.time() - start_time
                    print(f"[PowManager.perform_pow] INFO: Block {block.index} | Nonce {nonce:,} | Time: {elapsed_time:.2f}s | Last Hash: {block_hash_hex[:12]}...")

            print(f"[PowManager.perform_pow] ❌ ERROR: Block {block.index} reached max nonce limit without valid hash.")
            return None, None

        except Exception as e:
            print(f"[PowManager.perform_pow] ❌ ERROR: PoW failed for block {block.index}: {e}")
            return None, None





    def adjust_difficulty(self):
        """
        Adjusts mining difficulty based on actual versus expected block times.
        - Ensures difficulty is correctly retrieved from the block's header.
        - Implements fallbacks for block height, index, previous block hash, and difficulty.
        - Parses difficulty as a hex string and converts it to an integer.
        - Uses a dynamic scaling ratio for difficulty adjustment.
        """
        try:
            print("[PowManager.adjust_difficulty] INFO: Initiating difficulty adjustment...")

            stored_blocks = self.block_storage.get_all_blocks()
            num_blocks = len(stored_blocks)

            if num_blocks == 0:
                print("[PowManager.adjust_difficulty] INFO: No blocks found; using Genesis Target.")
                return Constants.GENESIS_TARGET

            last_block = stored_blocks[-1]
            header = last_block.get("header", last_block)

            # ✅ **Ensure Block Height & Index Exist (Fallback)**
            block_height = last_block.get("header", {}).get("index", num_blocks - 1)
            print(f"[PowManager.adjust_difficulty] INFO: Using block height {block_height} for difficulty adjustment.")

            # ✅ **Ensure Previous Block Hash Exists (Fallback)**
            previous_block_hash = last_block.get("header", {}).get("previous_hash", Constants.ZERO_HASH)
            if previous_block_hash == Constants.ZERO_HASH:
                print("[PowManager.adjust_difficulty] WARNING: Missing previous block hash. Using ZERO_HASH fallback.")

            # ✅ **Ensure Last Block's Difficulty Exists (Fallback)**
            if "header" not in last_block or "difficulty" not in last_block["header"]:
                print("[PowManager.adjust_difficulty] ERROR: Last block missing difficulty in header. Using Genesis Target.")
                return Constants.GENESIS_TARGET

            try:
                last_diff_str = str(last_block["header"]["difficulty"]).lower().strip()

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

            # ✅ **Ensure Timestamps Exist (Fallback)**
            try:
                last_timestamp = int(last_block.get("header", {}).get("timestamp", time.time()))
                first_timestamp = int(first_block.get("header", {}).get("timestamp", last_timestamp - Constants.TARGET_BLOCK_TIME * Constants.DIFFICULTY_ADJUSTMENT_INTERVAL))
            except (ValueError, TypeError) as e:
                print(f"[PowManager.adjust_difficulty] ERROR: Invalid timestamp format: {e}. Using estimated fallback values.")
                last_timestamp = time.time()
                first_timestamp = last_timestamp - Constants.TARGET_BLOCK_TIME * Constants.DIFFICULTY_ADJUSTMENT_INTERVAL

            if last_timestamp == 0 or first_timestamp == 0:
                print("[PowManager.adjust_difficulty] ERROR: Missing timestamps in blocks. Using estimated values.")
                last_timestamp = time.time()
                first_timestamp = last_timestamp - Constants.TARGET_BLOCK_TIME * Constants.DIFFICULTY_ADJUSTMENT_INTERVAL

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
                f"at block height {block_height} (Ratio: {ratio:.4f}).")

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
