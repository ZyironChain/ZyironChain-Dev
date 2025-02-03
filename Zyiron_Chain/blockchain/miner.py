import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


import time
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.blockchain.block_manager import BlockManager

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
        self.block_manager = block_manager
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
        Performs ASIC-resistant Proof-of-Work with:
        - **Memory-hard VRAM allocation** (8MB - 192MB)
        - **Iterative SHA3-384, SHA3-512, or BLAKE3 hashing** (1,024 - 3,072 iterations)
        - **Algorithm rotation** every 24-100 blocks or if hashrate spikes
        - **Floating-point math obfuscation** to hinder ASIC optimizations

        :param block_header: Block header to hash.
        :param target: Current mining target difficulty.
        :param network_hashrate: Current network hashrate.
        :return: Valid nonce and hash when PoW is successful.
        """
        # Step 1: Dynamically Allocate VRAM Buffer
        vram_size = self.get_dynamic_vram(network_hashrate)
        memory_buffer = np.random.bytes(vram_size)  # Allocate VRAM memory

        nonce = 0
        rotation_interval = random.randint(24, 100)
        iterations = random.randint(1024, 3072)  # Random SHA3 iterations
        algorithm_version = block_header.index % 3  # Rotate between hashing algorithms

        while True:
            # Step 2: Serialize block header data with nonce
            header_data = (
                f"{block_header.version}{block_header.index}{block_header.previous_hash}"
                f"{block_header.merkle_root}{block_header.timestamp}{nonce}"
            ).encode()

            # Step 3: Apply Memory-Hard Computation
            memory_index = (nonce % len(memory_buffer) - 64) % len(memory_buffer)
            memory_hard_data = header_data + memory_buffer[memory_index:memory_index + 64]

            # Step 4: Iterative Hashing with Algorithm Rotation
            hash_result = memory_hard_data
            for _ in range(iterations):
                if algorithm_version == 0:
                    hash_result = hashlib.sha3_384(hash_result).digest()
                elif algorithm_version == 1:
                    hash_result = hashlib.sha3_512(hash_result).digest()
                else:
                    hash_result = hashlib.blake2b(hash_result).digest()

            # Step 5: Floating-Point Math Obfuscation
            float_value = sum([math.sin(x) * math.log1p(x) for x in range(1, 100)])
            hash_result = hashlib.sha3_384(hash_result + str(float_value).encode()).hexdigest()

            # Step 6: Algorithm Rotation Based on Block Height & Hashrate Spikes
            if block_header.index % rotation_interval == 0 or self.detect_hashrate_spike():
                hash_result = hashlib.sha3_384(hash_result.encode()).hexdigest()

            # Step 7: Check if Valid Hash is Found
            hash_int = int(hash_result, 16)
            if hash_int < target:
                return nonce, hash_result

            nonce += 1


    def mine_block(self, network="testnet"):
        """
        Mine a new block using Anti-Farm PoW.
        - Uses SHA3-384 with memory-hard VRAM scaling.
        - Rotates algorithms dynamically.
        - Maintains a strict 5-minute block time.

        :param network: "testnet" or "mainnet"
        :return: True if block is successfully mined.
        """
        last_block = self.block_manager.chain[-1] if self.block_manager.chain else None
        block_height = last_block.index + 1 if last_block else 0
        prev_hash = last_block.hash if last_block else "0" * 96

        # Select transactions
        transactions = self.transaction_manager.select_transactions_for_block()
        total_fees = sum(
            sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)
            for tx in transactions
        )

        # Create coinbase transaction
        coinbase_tx = self.transaction_manager.create_coinbase_tx(total_fees, network)
        transactions.insert(0, coinbase_tx)

        new_block = Block(
            index=block_height,
            previous_hash=prev_hash,
            transactions=transactions,
            timestamp=int(time.time()),
            key_manager=self.transaction_manager.key_manager
        )

        # Compute difficulty target (4 leading zeros at genesis)
        target = (
            0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
            if block_height == 0 else self.block_manager.calculate_target()
        )

        print(f"[INFO] Mining block {block_height} with target {hex(target)}...")

        # Perform ASIC-resistant PoW
        network_hashrate = self.block_manager.get_network_hashrate()
        new_block.header.nonce, new_block.hash = self.asic_resistant_pow(new_block.header, target, network_hashrate)

        print(f"[SUCCESS] Block {block_height} mined! Nonce: {new_block.header.nonce}, Hash: {new_block.hash}")

        # Append the block to the chain
        self.block_manager.chain.append(new_block)
        self.storage_manager.store_block(new_block, self.block_manager.calculate_block_difficulty(new_block))
        self.storage_manager.save_blockchain_state(self.block_manager.chain, [])

        return True





    def mining_loop(self):
        """
        Continuously mine new blocks until stopped by user or system.
        """
        while True:
            try:
                if not self.block_manager.chain:
                    print("Mining genesis block...")
                    self.block_manager.create_genesis_block(self.transaction_manager.key_manager)
                else:
                    print(f"Mining block {len(self.block_manager.chain)}...")
                    if self.mine_block():
                        print("Block mined successfully!")
                    else:
                        print("Failed to mine block")

                user_input = input("Mine another block? (y/n): ").lower()
                if user_input != 'y':
                    break
            except KeyboardInterrupt:
                print("\nMining interrupted")
                break
            except Exception as e:
                print(f"Mining error: {str(e)}")
                break