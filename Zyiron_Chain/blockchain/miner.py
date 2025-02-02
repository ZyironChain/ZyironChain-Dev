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


class Miner:
    def __init__(self, block_manager, transaction_manager, storage_manager):
        self.block_manager = block_manager
        self.transaction_manager = transaction_manager
        self.storage_manager = storage_manager
        self.difficulty_adjustment_interval = 2016  # Similar to Bitcoin's 2016 block interval

    def asic_resistant_pow(self, block_header, target):
        """
        Perform ASIC-resistant Proof-of-Work by incorporating:
        - Memory-Hard Computation (Random 32MB - 64MB RAM lookups)
        - Iterative SHA3-384 Hashing (Random 1,024 - 3,072 Iterations)
        - Floating-Point Math Operations
        - Algorithm Rotation (Every 24-100 Blocks, Randomized)

        :param block_header: The BlockHeader object.
        :param target: The mining target difficulty.
        :return: The valid nonce and hash when PoW is successful.
        """
        # Randomly select memory buffer size between 32MB and 64MB
        memory_size_mb = random.randint(32, 64)
        memory_buffer = np.random.bytes(memory_size_mb * 1024 * 1024)  # Randomized memory buffer

        # Randomized algorithm rotation interval between 24 and 100 blocks
        rotation_interval = random.randint(24, 100)

        # Randomize the number of SHA3-384 iterations (1,024 - 3,072)
        iterations = random.randint(1024, 3072)

        nonce = 0
        while True:
            # Step 1: Serialize header data with nonce
            header_data = (
                f"{block_header.version}{block_header.index}{block_header.previous_hash}"
                f"{block_header.merkle_root}{block_header.timestamp}{nonce}"
            ).encode()

            # Step 2: Apply memory-hard transformation using a random segment of the buffer
            memory_index = (nonce % len(memory_buffer) - 64) % len(memory_buffer)
            memory_hard_data = header_data + memory_buffer[memory_index:memory_index + 64]

            # Step 3: Iterative SHA3-384 hashing (Random 1,024 - 3,072 iterations)
            hash_result = memory_hard_data
            for _ in range(iterations):
                hash_result = hashlib.sha3_384(hash_result).digest()

            # Step 4: Floating-Point Math Obfuscation (ASIC-resistant computation)
            float_value = sum([math.sin(x) * math.log1p(x) for x in range(1, 100)])
            hash_result = hashlib.sha3_384(hash_result + str(float_value).encode()).hexdigest()

            # Step 5: Randomized Algorithm Rotation (Every 24-100 Blocks)
            if block_header.index % rotation_interval == 0:
                hash_result = hashlib.sha3_384(hash_result.encode()).hexdigest()

            # Convert to integer for difficulty comparison
            hash_int = int(hash_result, 16)

            # Check if valid hash is found
            if hash_int < target:
                return nonce, hash_result

            nonce += 1
    def mine_block(self, network="testnet"):
        """
        Mine a new block using ASIC-resistant Proof-of-Work.
        :param network: "testnet" or "mainnet"
        :return: True if block is successfully mined, False otherwise.
        """
        last_block = self.block_manager.chain[-1] if self.block_manager.chain else None
        block_height = last_block.index + 1 if last_block else 0
        prev_hash = last_block.hash if last_block else "0" * 96

        transactions = self.transaction_manager.select_transactions_for_block()
        total_fees = sum(
            sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)
            for tx in transactions
        )

        coinbase_tx = self.transaction_manager.create_coinbase_tx(total_fees, network)
        transactions.insert(0, coinbase_tx)

        new_block = Block(
            index=block_height,
            previous_hash=prev_hash,
            transactions=transactions,
            timestamp=int(time.time()),
            key_manager=self.transaction_manager.key_manager
        )

        # Compute difficulty target
        if block_height == 0:
            target = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # 4 Leading Zeros
        else:
            target = self.block_manager.calculate_target()

        print(f"[INFO] Mining block {block_height} with target {hex(target)}...")

        # Perform ASIC-resistant PoW
        new_block.header.nonce, new_block.hash = self.asic_resistant_pow(new_block.header, target)

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
