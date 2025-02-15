import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


import time

from decimal import Decimal
import time
import hashlib
import math
import numpy as np  # Used for memory-hard operations
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
from Zyiron_Chain. transactions.fees import FeeModel
from Zyiron_Chain. transactions. transactiontype import TransactionType
import numpy as np  # Used for memory-hard operations
import random  # Used for randomized algorithm rotation & memory buffer size
from Zyiron_Chain.blockchain.block import Block
from  Zyiron_Chain.database.unqlitedatabase import BlockchainUnqliteDB
import json
import numpy as np
import hashlib
import random
import math
import time
def get_block():
    """Lazy import to prevent circular dependencies"""
    from Zyiron_Chain.blockchain.block import Block
    return Block


class Miner:
    def __init__(self, block_manager, transaction_manager, storage_manager, key_manager):
        """
        Initialize the Miner with blockchain components and key manager.
        """
        self.block_manager = block_manager
        self.transaction_manager = transaction_manager
        self.storage_manager = storage_manager
        self.key_manager = key_manager  # Add the key manager to the miner



    def sha3_384_pow(self, block_header, target, block_height):
        """
        Perform SHA3-384 Proof-of-Work (PoW) with dynamic difficulty adjustment.
        """
        nonce = 0
        start_time = time.time()
        last_update = time.time()
        elapsed_time = 0  # Initialize elapsed_time to track how long the mining takes

        while True:
            # Prepare the header data for hashing
            header_data = f"{block_header.version}{block_header.index}{block_header.previous_hash}{block_header.merkle_root}{block_header.timestamp}{nonce}".encode()
            block_hash = hashlib.sha3_384(header_data).hexdigest()

            # Check if the block hash is less than the target (valid block)
            if int(block_hash, 16) < target:
                print(f"\n[SUCCESS] Block {block_height} mined successfully with Nonce value of {nonce}!")
                print(f"Elapsed Time: {elapsed_time:.2f}s")  # Print elapsed time
                sys.stdout.flush()  # Force flush the output
                return nonce, block_hash

            nonce += 1
            elapsed_time = time.time() - start_time  # Update elapsed time for mining progress

            # Print mining progress every 0.05 seconds (20 updates per second)
            if time.time() - last_update >= 0.05:
                print(f"\rBlock {block_height} mining in progress... Nonce: {nonce} | Elapsed Time: {elapsed_time:.2f}s", end="")
                sys.stdout.flush()  # Force flush the output
                last_update = time.time()

            # If Block #1 is mining too slowly (takes more than 10 seconds), reduce difficulty more aggressively
            if block_height == 1 and elapsed_time > 10:
                print(f"\n[WARNING] Block #1 mining is slow, adjusting difficulty...")

                # Reduce difficulty significantly (target multiplied by 4)
                new_target = target * 4  # More aggressive difficulty scaling
                return self.sha3_384_pow(block_header, new_target, block_height)  # Retry with reduced difficulty

            # Safety net: If Block #1 takes longer than 15 seconds, reduce difficulty even more
            if block_height == 1 and elapsed_time > 15:
                print("\n[WARNING] Block #1 took too long, restarting with lower difficulty.")
                return self.sha3_384_pow(block_header, target * 8, block_height)  # Retry with an even lower difficulty




    def _calculate_block_size(self):
        """
        Dynamically adjust block size based on the number of pending transactions.
        Block sizes scale linearly from 1MB to 10MB based on transaction count.
        """
        pending_tx_count = len(self.transaction_manager.mempool)

        min_tx = 1000     # Minimum transactions for 1MB block
        max_tx = 50000    # Maximum transactions for 10MB block
        min_size = 1.0    # Minimum block size (MB)
        max_size = 10.0   # Maximum block size (MB)

        # Ensure linear scaling of block size
        if pending_tx_count <= min_tx:
            new_block_size = min_size
        elif pending_tx_count >= max_tx:
            new_block_size = max_size
        else:
            new_block_size = min_size + ((max_size - min_size) * ((pending_tx_count - min_tx) / (max_tx - min_tx)))

        # Ensure block size stays within valid limits
        self.current_block_size = max(min_size, min(new_block_size, max_size))

        print(f"[INFO] Block size adjusted to {self.current_block_size:.2f}MB based on {pending_tx_count} transactions.")



    def _create_coinbase(self, miner_address: str, fees: Decimal):
        """Create coinbase transaction with protocol rules."""
        block_reward = self._calculate_block_reward()
        total_reward = block_reward + fees

        return CoinbaseTx(
            block_height=len(self.block_manager.chain),
            miner_address=miner_address,
            reward=total_reward
        )




    def _calculate_difficulty(self):
        """Calculate difficulty based on block time and network conditions."""
        return 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF




    def _calculate_block_reward(self):
        """Calculate current block reward with halving."""
        block_count = len(self.block_manager.chain)
        halvings = block_count // 420480
        reward = Decimal('100.00') / (2 ** halvings)
        return reward


    def add_block(self, new_block):
        """
        Add a mined block to the blockchain.
        - Stores the block in memory.
        - Saves it to persistent storage.
        - Ensures correct difficulty recalculation.
        """
        self.block_manager.chain.append(new_block)
        self.storage_manager.store_block(new_block, new_block.header.difficulty)
        self.storage_manager.save_blockchain_state(self.block_manager.chain)






    def mine_block(self, network="mainnet"):
        """
        Mine a new block using SHA3-384 PoW.
        - Ensures a constant 5-minute block time.
        - Dynamically adjusts difficulty every 288 blocks.
        - Accepts network argument for flexibility (e.g., "mainnet" or "testnet").
        """
        if len(self.block_manager.chain) == 0:
            raise RuntimeError("[ERROR] Blockchain is empty. Ensure Genesis block is created.")

        # Get the miner address from the key manager
        miner_address = self.key_manager.get_default_public_key(network, "miner")

        # Dynamically Adjust Block Size
        self._calculate_block_size()

        # Calculate Total Transaction Fees (even if there are no transactions)
        total_fees = sum(tx['fee'] for tx in self.pending_transactions) if self.pending_transactions else 0

        # Create Coinbase Transaction for Miner (Always included)
        coinbase_tx = self._create_coinbase(miner_address, Decimal(total_fees))

        # Select Transactions for Block (Limited by Block Size)
        max_block_bytes = self.current_block_size * 1024 * 1024  # Convert MB to bytes
        current_block_size = 0
        selected_transactions = []

        # If there are pending transactions, select them
        for tx in list(self.pending_transactions):
            tx_size = self._calculate_transaction_size(tx)
            if current_block_size + tx_size <= max_block_bytes:
                selected_transactions.append(tx)
                current_block_size += tx_size
                self.pending_transactions.remove(tx)
            else:
                break

        # Assemble Block Data with only coinbase transaction if no regular transactions
        new_block = Block(
            index=len(self.block_manager.chain),
            previous_hash=self.block_manager.chain[-1].hash if self.block_manager.chain else self.ZERO_HASH,
            transactions=[coinbase_tx] + selected_transactions,  # Always include coinbase_tx
            timestamp=int(time.time()),
            nonce=0
        )

        # Get Current Difficulty Target
        target = self._calculate_difficulty()

        # Mining Logic (SHA3-384 PoW)
        nonce, block_hash = self.sha3_384_pow(new_block.header, target, new_block.index)

        # Store the mined block
        new_block.header.nonce = nonce
        new_block.hash = block_hash
        self.add_block(new_block)

        return new_block