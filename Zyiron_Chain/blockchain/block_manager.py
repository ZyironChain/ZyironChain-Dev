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
        self.difficulty = 4

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
            
            if genesis_block.mine(self.calculate_target(), None, None, None, False):
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
        return 2 ** (384 - self.difficulty * 4)

    def calculate_block_difficulty(self, block):
        if block.index == 0:
            return 1
            
        prev_block = self.chain[-1]
        time_diff = block.timestamp - prev_block.timestamp
        target_time = 15  # 15 seconds target
        
        if time_diff < target_time:
            return prev_block.difficulty + 1
        elif time_diff > target_time:
            return max(prev_block.difficulty - 1, 1)
        else:
            return prev_block.difficulty