import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import json
import hashlib
import time
import logging
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction, CoinbaseTx
from Zyiron_Chain.transactions.txout import TransactionOut

class BlockManager:
    ZERO_HASH = "0" * 96  # 384-bit zero hash for SHA-3 384

    def __init__(self, storage_manager):
        self.chain = []
        self.storage_manager = storage_manager
        self.difficulty = 4  # Default to 4 leading zeros
        self.difficulty_adjustment_interval = 24  # Adjust every 24 blocks (~2 hours)

    def create_genesis_block(self, key_manager):
        if self.storage_manager.poc.get_block("block:0"):
            logging.info("Genesis block already exists.")
            return

        try:
            genesis_transaction = Transaction(
                tx_inputs=[],
                tx_outputs=[TransactionOut(script_pub_key="genesis_output", amount=50, locked=False)]
            )
            
            merkle_root = self.calculate_merkle_root([genesis_transaction])
            genesis_block = Block(
                index=0,
                previous_hash=self.ZERO_HASH,
                transactions=[genesis_transaction],
                timestamp=int(time.time()),
                merkle_root=merkle_root,
            )
            genesis_block.miner_address = key_manager.get_default_public_key("testnet", "miner")

            # ✅ Use fixed 4 leading zeros for Genesis Block
            genesis_target = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF

            if genesis_block.mine(genesis_target, None, None, None, False):
                self.chain.append(genesis_block)
                self.storage_manager.store_block(genesis_block, self.difficulty)
                logging.info("Genesis block created successfully")
            else:
                logging.error("Failed to mine genesis block")

        except Exception as e:
            logging.error(f"Error creating genesis block: {str(e)}")
            raise

    def validate_chain(self):
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i-1]
            
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
        if not transactions:
            return self.ZERO_HASH
            
        tx_hashes = []
        for tx in transactions:
            if isinstance(tx, dict):
                tx_str = json.dumps(tx, sort_keys=True)
            elif isinstance(tx, Transaction):
                tx_str = json.dumps(tx.to_dict(), sort_keys=True)
            else:
                tx_str = str(tx)
            tx_hashes.append(hashlib.sha3_384(tx_str.encode()).hexdigest())

        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])
            tx_hashes = [hashlib.sha3_384((tx_hashes[i] + tx_hashes[i+1]).encode()).hexdigest() 
                        for i in range(0, len(tx_hashes), 2)]
            
        return tx_hashes[0] if tx_hashes else self.ZERO_HASH

    def calculate_target(self):
        """Dynamically calculate the mining target based on hashrate & VRAM scaling"""
        last_block = self.chain[-1] if self.chain else None
        
        # Genesis Block Target
        if not last_block:
            return 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # 4 leading zeros
        
        # ✅ Adjust target dynamically every 24 blocks (~2 hours)
        if last_block.index % self.difficulty_adjustment_interval == 0:
            return self._adjust_target(last_block)

        return last_block.header.difficulty

    def _adjust_target(self, last_block):
        """Adjusts difficulty dynamically every 24 blocks based on network hashrate"""
        if len(self.chain) < 24:
            return last_block.header.difficulty
        
        # Calculate actual time for last 24 blocks
        actual_time = last_block.timestamp - self.chain[-24].timestamp
        expected_time = 24 * 300  # 24 blocks * 5 minutes
        
        # Difficulty Adjustment Ratio
        adjustment_ratio = actual_time / expected_time
        new_difficulty = last_block.header.difficulty * adjustment_ratio

        # Prevent difficulty from dropping too low
        return max(new_difficulty, 1)

    def calculate_block_difficulty(self, block):
        """Recalculate difficulty dynamically"""
        if block.index == 0:
            return 1  # Genesis Block difficulty fixed at 1
            
        prev_block = self.chain[-1]
        time_diff = block.timestamp - prev_block.timestamp
        expected_time = 300  # 5-minute block target
        
        if time_diff < expected_time:
            return prev_block.difficulty + 1
        elif time_diff > expected_time:
            return max(prev_block.difficulty - 1, 1)
        else:
            return prev_block.difficulty
