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
        Performs Proof-of-Work (PoW) by incrementing the nonce until a valid hash is found.
        - Uses single SHA3-384 hashing.
        - Ensures nonce increments correctly to prevent infinite loops.
        - Prevents double mining of the Genesis block.
        """
        try:
            print(f"[PowManager.perform_pow] INFO: Starting Proof-of-Work for block {block.index}...")

            # ✅ **Ensure Genesis Block is Not Mined Twice**
            if block.index == 0:
                existing_genesis = self.block_metadata.get_latest_block()
                if existing_genesis and existing_genesis.index == 0:
                    print(f"[PowManager.perform_pow] WARNING: Genesis block already exists with hash: {existing_genesis.hash}. Skipping mining.")
                    return existing_genesis.hash, block.nonce, 0  # ✅ Return existing hash & prevent duplicate mining

            # ✅ **Initialize Variables**
            nonce = 0
            start_time = time.time()

            while True:
                # ✅ **Update Block Nonce**
                block.nonce = nonce

                # ✅ **Compute Hash (Stored as Bytes)**
                block_hash = Hashing.hash(block.calculate_hash().encode())  # ✅ Store as bytes

                # ✅ **Check if Hash Meets Difficulty Target**
                if int.from_bytes(block_hash, "big") < block.difficulty:
                    elapsed_time = time.time() - start_time
                    print(f"[PowManager.perform_pow] SUCCESS: Block {block.index} mined after {nonce} attempts in {elapsed_time:.2f} seconds.")
                    return block_hash, nonce, nonce  # ✅ Return valid hash, nonce, and attempts

                # ✅ **Increment Nonce**
                nonce += 1

                # ✅ **Log Progress Every 100,000 Nonce Increments**
                if nonce % 100000 == 0:
                    elapsed_time = time.time() - start_time
                    print(f"[PowManager.perform_pow] INFO: Nonce {nonce}, Elapsed Time: {elapsed_time:.2f}s")

        except Exception as e:
            print(f"[PowManager.perform_pow] ERROR: Proof-of-Work failed: {e}")
            return None, None, None



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
            print("[PowManager.adjust_difficulty] INFO: Initiating difficulty adjustment...")

            stored_blocks = storage_manager.get_all_blocks()
            num_blocks = len(stored_blocks)

            if num_blocks == 0:
                print("[PowManager.adjust_difficulty] INFO: No blocks found; using Genesis Target.")
                return Constants.GENESIS_TARGET

            # ✅ **Use Last Block's Difficulty**
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

            # ✅ **Ensure Enough Blocks for Difficulty Adjustment**
            if num_blocks < Constants.DIFFICULTY_ADJUSTMENT_INTERVAL:
                print(f"[PowManager.adjust_difficulty] INFO: Insufficient blocks ({num_blocks}) for adjustment. Using last difficulty.")
                return last_difficulty

            first_block = stored_blocks[-Constants.DIFFICULTY_ADJUSTMENT_INTERVAL]

            # ✅ **Ensure Timestamps Exist and Are Valid**
            try:
                last_timestamp = int(last_block["header"].get("timestamp", 0))
                first_timestamp = int(first_block["header"].get("timestamp", 0))
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
            ratio = max(Constants.MIN_DIFFICULTY_FACTOR, min(Constants.MAX_DIFFICULTY_FACTOR, ratio))

            # ✅ **Apply Difficulty Adjustment**
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
            print("[PowManager.get_average_block_time] INFO: Calculating average block time...")

            stored_blocks = storage_manager.get_all_blocks()
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

                    if prev_timestamp == 0 or curr_timestamp == 0:
                        print(f"[PowManager.get_average_block_time] ERROR: Block {i} has invalid timestamps. Skipping.")
                        continue

                    diff = max(1, curr_timestamp - prev_timestamp)  # ✅ Prevents division errors
                    if diff > 7200:  # ✅ Ensure timestamp validation within 7200s drift
                        print(f"[PowManager.get_average_block_time] ERROR: Block {i} timestamp drift exceeds 7200s. Skipping.")
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

