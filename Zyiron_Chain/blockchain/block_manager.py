import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import json
import hashlib
import time
import logging

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

class BlockManager:
    ZERO_HASH = "0" * 96  # 384-bit zero hash for SHA3-384

    def __init__(self, storage_manager, transaction_manager=None):
        """
        Initialize the BlockManager.
        - Stores blockchain storage reference.
        - Manages block difficulty & hashrate.
        - No longer creates the Genesis block (handled by Blockchain).
        """
        self.chain = []  # ✅ Ensure chain is always initialized
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager  # ✅ Store transaction manager
        self.difficulty_adjustment_interval = 288  # ✅ Adjust difficulty every 288 blocks (5 min target)
        
        if self.storage_manager and hasattr(self.storage_manager, "block_manager"):
            self.storage_manager.block_manager = self

    def validate_chain(self):
        """Validate the entire blockchain by checking hashes and Merkle roots."""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            if current.previous_hash != previous.hash:
                return False
            if current.hash != current.calculate_hash():
                return False
            if current.header.merkle_root != self.calculate_merkle_root(current.transactions):
                return False
            if int(current.hash, 16) > self.calculate_target():
                return False

        return True

    def calculate_merkle_root(self, transactions):
        """Compute the Merkle root from transaction IDs."""
        if not transactions:
            return self.ZERO_HASH

        tx_hashes = []
        for tx in transactions:
            if isinstance(tx, dict):
                tx_str = json.dumps(tx, sort_keys=True)
            else:
                tx_str = json.dumps(tx.to_dict(), sort_keys=True)

            tx_hashes.append(hashlib.sha3_384(tx_str.encode()).hexdigest())

        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])
            tx_hashes = [
                hashlib.sha3_384((tx_hashes[i] + tx_hashes[i + 1]).encode()).hexdigest()
                for i in range(0, len(tx_hashes), 2)
            ]

        return tx_hashes[0] if tx_hashes else self.ZERO_HASH

    def calculate_target(self):
        """
        Calculate the mining target.
        - Block #1 should mine in ~10 seconds.
        - Adjusts difficulty every 288 blocks to reach a 5-minute block time.
        """
        print(f"[DEBUG] Called calculate_target() - Chain Length: {len(self.chain)}")

        if len(self.chain) == 0:
            print(f"[DEBUG] Returning Genesis Difficulty: {hex(0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF)}")
            return 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # ✅ Genesis Difficulty

        if len(self.chain) == 1:
            # ✅ Lower Block #1 Difficulty (~10 sec mining)
            block_1_difficulty = 0x000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # ✅ Lowered target
            print(f"[DEBUG] Lowering Difficulty for Block #1: {hex(block_1_difficulty)}")
            return block_1_difficulty  # ✅ Ensures a ~10s block time

        last_block = self.chain[-1]
        if last_block.index % 288 == 0:
            adjusted_target = self._adjust_target(last_block)
            print(f"[DEBUG] Adjusting Difficulty at Block {last_block.index}: {hex(adjusted_target)}")
            return adjusted_target

        print(f"[DEBUG] Returning Unchanged Difficulty: {hex(last_block.header.difficulty)}")
        return last_block.header.difficulty



    def _adjust_target(self, last_block):
        """
        Adjust mining difficulty every 288 blocks.
        - Targets an average block time of **5 minutes (300 seconds)**.
        - Limits difficulty changes within **2x increase or 0.5x decrease**.
        """
        if len(self.chain) < 288:
            return last_block.header.difficulty

        actual_time = last_block.timestamp - self.chain[-288].timestamp
        expected_time = 288 * 300  # 288 blocks * 5 minutes per block

        # ✅ Prevent division by zero
        if actual_time <= 0:
            actual_time = expected_time  

        adjustment_ratio = actual_time / expected_time
        new_difficulty = int(last_block.header.difficulty * max(0.5, min(2.0, adjustment_ratio)))  # ✅ Limit change to ±50%

        print(f"[DEBUG] Adjusting Difficulty: {hex(new_difficulty)} | Block Time: {actual_time}s (Expected: {expected_time}s)")
        return max(new_difficulty, 1)  # ✅ Never let difficulty go below 1

