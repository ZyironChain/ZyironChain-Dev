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
    ZERO_HASH = "0" * 96  # 384-bit zero hash for SHA-3 384

    def __init__(self, storage_manager, transaction_manager=None):
        """
        Initialize the BlockManager.
        :param storage_manager: Manages blockchain storage.
        :param transaction_manager: (Optional) Manages transactions.
        """
        self.chain = []
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager  # ✅ Store transaction manager
        self.difficulty = 4  # Default to 4 leading zeros
        self.difficulty_adjustment_interval = 24  # Adjust every 24 blocks (~2 hours)

       

    def create_genesis_block(self):
        """Create the Genesis block if it doesn't exist."""
        
        if self.storage_manager.poc.get_block("block:0"):
            logging.info("Genesis block already exists.")
            return

        try:
            # ✅ Lazy Import to prevent circular dependency
            from Zyiron_Chain.blockchain.miner import Miner  
            from Zyiron_Chain.blockchain.transaction_manager import TransactionManager  
            from Zyiron_Chain.blockchain.block import Block  
            from Zyiron_Chain.transactions.Blockchain_transaction import TransactionOut

            # ✅ Fix: Correctly instantiate Transaction
            Transaction = get_transaction()

            # ✅ Ensure Genesis Transaction Has No Fees
            genesis_transaction = Transaction(
                inputs=[],  # Coinbase transactions have no inputs
                outputs=[TransactionOut(script_pub_key="genesis_output", amount=50, locked=False)],
                tx_id="0"  # ✅ Explicitly set `tx_id=0` for Genesis Block
            )

            # ✅ Calculate Merkle Root
            merkle_root = self.calculate_merkle_root([genesis_transaction])

            # ✅ Fix: Correctly instantiate Block
            Block = get_block()

            genesis_block = Block(
                index=0,
                previous_hash=self.ZERO_HASH,
                transactions=[genesis_transaction],
                timestamp=int(time.time()),
            )

            # ✅ Set miner address
            key_manager = self.transaction_manager.key_manager  
            genesis_block.miner_address = key_manager.get_default_public_key("testnet", "miner")

            # ✅ Fix: Set block header correctly using `BlockHeader`
            genesis_block.header = BlockHeader(
                version=1,
                index=0,
                previous_hash=self.ZERO_HASH,
                merkle_root=merkle_root,  # ✅ Fix: Assign Merkle Root inside BlockHeader
                timestamp=genesis_block.timestamp,
                nonce=0
            )

            # ✅ Use fixed 4 leading zeros for Genesis Block
            genesis_target = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF

            # ✅ Mine the Genesis Block
            miner = Miner(self, self.transaction_manager, self.storage_manager)  # ✅ Ensure correct initialization
            if miner.mine_block():
                self.chain.append(genesis_block)
                self.storage_manager.store_block(genesis_block, self.difficulty)
                logging.info("[INFO] Genesis block created successfully")
            else:
                logging.error("[ERROR] Failed to mine Genesis block")

        except Exception as e:
            logging.error(f"[ERROR] Error creating Genesis block: {str(e)}")
            raise RuntimeError(f"Genesis Block Creation Failed: {str(e)}") from e

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
        """Compute the Merkle root from transaction IDs."""
        if not transactions:
            return self.ZERO_HASH

        tx_hashes = []
        for tx in transactions:
            if isinstance(tx, dict):
                tx_str = json.dumps(tx, sort_keys=True)
            elif isinstance(tx, get_transaction()):
                tx_str = json.dumps(tx.to_dict(), sort_keys=True)
            else:
                tx_str = str(tx)
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
        """Dynamically calculate the mining target based on hashrate & VRAM scaling."""
        last_block = self.chain[-1] if self.chain else None

        # Genesis Block Target
        if not last_block:
            return 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # 4 leading zeros

        # ✅ Adjust target dynamically every 24 blocks (~2 hours)
        if last_block.index % self.difficulty_adjustment_interval == 0:
            return self._adjust_target(last_block)

        return last_block.header.difficulty

    def _adjust_target(self, last_block):
        """Adjusts difficulty dynamically every 24 blocks based on network hashrate."""
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
        """Recalculate difficulty dynamically."""
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