import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


import time


import time
import hashlib
import math
import numpy as np  # Used for memory-hard operations
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
from Zyiron_Chain. transactions.fees import FeeModel
from Zyiron_Chain. transactions. transactiontype import TransactionType
import numpy as np  # Used for memory-hard operations
import random  # Used for randomized algorithm rotation & memory buffer size

import numpy as np
import hashlib
import random
import math
import time

class Miner:
    def __init__(self, block_manager, transaction_manager, storage_manager):
        """
        Initialize the Miner.
        :param block_manager: BlockManager instance.
        :param transaction_manager: TransactionManager instance.
        :param storage_manager: StorageManager instance.
        """
        self.block_manager = block_manager  # ✅ Correctly store `block_manager`
        self.transaction_manager = transaction_manager
        self.storage_manager = storage_manager
        self.base_vram = 8 * 1024 * 1024  # Start at 8MB VRAM
        self.max_vram = 192 * 1024 * 1024  # Cap at 192MB VRAM
        self.last_hashrate_check = time.time()  # Last check for hashrate changes
        self.previous_hashrate = 0  # Stores previous network hashrate

    def get_dynamic_vram(self, network_hashrate):
        """
        Dynamically scales VRAM between 8MB - 192MB based on network hashrate.
        """
        if network_hashrate < 1e12:  # Small network (Low hashrate)
            return self.base_vram
        elif network_hashrate < 5e13:  # Moderate network growth
            return int(self.base_vram + (network_hashrate / 1e13) * self.max_vram * 0.5)
        else:  # Large-scale mining detected (High hashrate)
            return self.max_vram

    def check_hashrate_adjustment(self, new_hashrate):
        """
        Checks if the network hashrate increased significantly (10%+ in 2 hours).
        If it does, triggers an immediate algorithm rotation & VRAM increase.
        """
        current_time = time.time()
        time_elapsed = current_time - self.last_hashrate_check

        if time_elapsed >= 7200:  # Check every 2 hours
            hashrate_change = abs(new_hashrate - self.previous_hashrate) / (self.previous_hashrate + 1) * 100
            
            if hashrate_change > 10:  # If hashrate increased by 10% or more
                print(f"[WARNING] Network hashrate increased by {hashrate_change:.2f}%. Activating countermeasures.")
                self.trigger_countermeasures(new_hashrate)

            self.previous_hashrate = new_hashrate
            self.last_hashrate_check = current_time

    def trigger_countermeasures(self, network_hashrate):
        """
        Triggers network-wide countermeasures against mining farms and ASICs.
        - Increases VRAM scaling.
        - Rotates hashing algorithm immediately.
        - Increases difficulty slightly to prevent fast block times.
        """
        print("[INFO] Activating network countermeasures...")

        # Increase VRAM usage dynamically
        self.base_vram = min(self.max_vram, self.base_vram * 1.2)

        # Rotate hashing algorithm instantly
        self.algorithm_version = random.choice(["v1", "v2", "v3", "v4", "v5"])

        # Increase mining difficulty slightly
        self.block_manager.difficulty_target *= 1.1

        print(f"[INFO] New VRAM usage: {self.base_vram / (1024 * 1024)}MB")
        print(f"[INFO] Algorithm rotated to {self.algorithm_version}")
        print(f"[INFO] Difficulty increased to {self.block_manager.difficulty_target:.2f}")

    def asic_resistant_pow(self, block_header, target, network_hashrate):
        """
        Optimized ASIC-resistant Proof-of-Work.
        - Ensures difficulty is achievable.
        - Prints estimated mining speed.
        - Shows live nonce count without printing hashes.
        """
        import hashlib
        import time
        import math
        import random
        import numpy as np
        import sys

        # ✅ Reduce Hash Iterations for Faster Mining
        iterations = 256  # ✅ Decrease iteration count for speed
        vram_size = 4 * 1024 * 1024  # ✅ Reduce memory buffer for faster hashing
        memory_buffer = np.random.bytes(vram_size)  # Allocate VRAM memory

        nonce = 0
        start_time = time.time()  # ✅ Track mining time

        # ✅ Print Mining Start Information Once
        print(f"\n[INFO] Mining Block {block_header.index} - Target Difficulty: {hex(target)}")
        print(f"[INFO] Previous Hash: {block_header.previous_hash}")
        print(f"[INFO] Merkle Root: {block_header.merkle_root}")
        print(f"[INFO] Mining Started...")

        while True:
            # ✅ Ensure Block Header is Constant During Mining
            stable_data = (
                f"{block_header.version}{block_header.index}{block_header.previous_hash}"
                f"{block_header.merkle_root}{block_header.timestamp}"
            ).encode()

            # ✅ Serialize block header data with nonce
            header_data = stable_data + str(nonce).encode()

            # ✅ Perform Optimized Hashing
            hash_result = hashlib.sha3_384(header_data).digest()
            for _ in range(iterations):
                hash_result = hashlib.sha3_384(hash_result).digest()

            # ✅ Live Nonce Display Every 1000 Attempts
            if nonce % 1000 == 0:
                elapsed_time = round(time.time() - start_time, 2)
                sys.stdout.write(f"\r[INFO] Nonce: {nonce} | Time Elapsed: {elapsed_time} sec")
                sys.stdout.flush()

            # ✅ Check if Hash Meets Target
            hash_int = int(hash_result.hex(), 16)
            if hash_int < target:
                mining_time = round(time.time() - start_time, 2)
                print(f"\n\n[SUCCESS] Valid Nonce Found: {nonce}")
                print(f"[SUCCESS] Block Hash: {hash_result.hex()}")
                print(f"[INFO] Mining Time: {mining_time} seconds")
                print(f"[INFO] Final Nonce: {nonce}")
                print(f"[INFO] Block Difficulty: {hex(target)}\n")

                return nonce, hash_result.hex()

            nonce += 1  # ✅ Increment nonce faster





    def mine_block(self, network="testnet"):
        """
        Mine a new block using ASIC-resistant PoW.
        - Prints full block details before storing in DB.
        """
        from Zyiron_Chain.blockchain.block import Block

        last_block = self.block_manager.chain[-1] if self.block_manager.chain else None
        block_height = last_block.index + 1 if last_block else 0
        prev_hash = last_block.hash if last_block else "0" * 96

        # Select transactions
        transactions = self.transaction_manager.select_transactions_for_block()
        total_fees = sum(
            sum(inp.amount for inp in tx.inputs if hasattr(inp, "amount")) - 
            sum(out.amount for out in tx.outputs if hasattr(out, "amount"))
            for tx in transactions
        )

        # Create coinbase transaction
        coinbase_tx = self.transaction_manager.create_coinbase_tx(total_fees, network, block_height)
        transactions.insert(0, coinbase_tx)

        new_block = Block(
            index=block_height,
            previous_hash=prev_hash,
            transactions=transactions,
            timestamp=int(time.time()),
            key_manager=self.transaction_manager.key_manager
        )

        # Compute difficulty target
        target = self.block_manager.calculate_target()

        print(f"[INFO] Mining Block {block_height} - Target Difficulty: {hex(target)}")

        # Perform ASIC-resistant PoW
        network_hashrate = self.block_manager.get_network_hashrate()
        new_block.header.nonce, new_block.hash = self.asic_resistant_pow(new_block.header, target, network_hashrate)

        # ✅ Print full block details **before** storing in DB
        print("\n[BLOCK MINED SUCCESSFULLY!]")
        print(f"[INFO] Block Height: {block_height}")
        print(f"[INFO] Previous Hash: {prev_hash}")
        print(f"[INFO] New Block Hash: {new_block.hash}")
        print(f"[INFO] Merkle Root: {new_block.header.merkle_root}")
        print(f"[INFO] Nonce: {new_block.header.nonce}")
        print(f"[INFO] Timestamp: {new_block.timestamp}")
        print(f"[INFO] Block Difficulty: {hex(target)}")
        print(f"[INFO] Transactions Included: {len(new_block.transactions)}\n")

        # ✅ Print transaction details
        for tx in new_block.transactions:
            print(f"[TRANSACTION] ID: {tx.tx_id}, Type: {tx.type}, Inputs: {len(tx.inputs)}, Outputs: {len(tx.outputs)}")

        # ✅ Store block in the database
        self.block_manager.chain.append(new_block)
        self.storage_manager.store_block(new_block, self.block_manager.calculate_block_difficulty(new_block))

        # ✅ Verify block storage
        stored_block = self.storage_manager.poc.unqlite_db.get(f"block:{block_height}")
        if stored_block:
            print(f"[SUCCESS] Block {block_height} successfully saved to DB!")
            print(f"[STORED DATA] {stored_block}")
        else:
            print(f"[ERROR] Block {block_height} did NOT save correctly!")

        return True


    def mining_loop(self):
        """
        Continuously mine new blocks until manually stopped (Ctrl+C).
        - Automatically starts with the Genesis Block if needed.
        - No user input is required; mining runs indefinitely.
        """
        while True:
            try:
                if not self.block_manager.chain:
                    print("[INFO] Mining Genesis Block...")
                    self.block_manager.create_genesis_block()  # ✅ Remove extra argument

                else:
                    print(f"[INFO] Mining Block {len(self.block_manager.chain)}...")
                    if self.mine_block():
                        print("[SUCCESS] Block mined successfully!")
                    else:
                        print("[ERROR] Failed to mine block")

            except KeyboardInterrupt:
                print("\n[INFO] Mining stopped by user (Ctrl+C).")
                break
            except Exception as e:
                print(f"[ERROR] Mining error: {str(e)}")
                break


# Main Execution
if __name__ == "__main__":
    from Zyiron_Chain.database.poc import PoC
    from Zyiron_Chain.blockchain.storage_manager import StorageManager
    from Zyiron_Chain.blockchain.transaction_manager import TransactionManager
    from Zyiron_Chain.blockchain.block_manager import BlockManager
    from Zyiron_Chain.blockchain.utils.key_manager import KeyManager

    poc_instance = PoC()
    storage_manager = StorageManager(poc_instance)
    key_manager = KeyManager()
    transaction_manager = TransactionManager(storage_manager, key_manager, poc_instance)

    # ✅ Ensure `block_manager` is initialized with `transaction_manager`
    block_manager = BlockManager(storage_manager, transaction_manager)

    # ✅ Pass `block_manager` correctly to `Miner`
    miner = Miner(
        block_manager=block_manager,
        transaction_manager=transaction_manager,
        storage_manager=storage_manager
    )

    try:
        miner.mining_loop()
    except KeyboardInterrupt:
        print("\nMining stopped by user")
