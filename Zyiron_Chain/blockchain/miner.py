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

import time
import sys
import hashlib
from decimal import Decimal
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
import logging

# Remove all previous handlers to stop cross-logging
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Setup logging for this specific module only
def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    if logger.hasHandlers():
        logger.handlers.clear()  # Prevent duplicate logs
    logger.addHandler(handler)
    logger.propagate = False  # Prevent log propagation across modules
    return logger

log = setup_logger(__name__)  # Assign this logger to your module
log.info(f"{__name__} logger initialized.")


# Ensure this is at the very top of your script, before any other code
class Miner:
    def __init__(self, block_manager, transaction_manager, storage_manager, key_manager):
        self.block_manager = block_manager
        self.transaction_manager = transaction_manager
        self.storage_manager = storage_manager
        self.key_manager = key_manager

        self.current_block_size = 1.0

    def sha3_384_pow(self, block_header, target, block_height, start_time):
        nonce = 0
        last_update = time.time()
        hash_attempts = 0

        while True:
            header_data = (
                f"{block_header.version}{block_header.index}"
                f"{block_header.previous_hash}{block_header.merkle_root}"
                f"{block_header.timestamp}{block_header.difficulty}{nonce}"
            ).encode()

            block_hash = hashlib.sha3_384(header_data).hexdigest()
            hash_attempts += 1

            # If the block hash meets the target, we're done
            if int(block_hash, 16) < target:
                return nonce, block_hash

            nonce += 1

            # Show live time + nonce every 5 seconds
            if time.time() - last_update > 5:
                elapsed = time.time() - start_time
                print(f"[LIVE] Mining Block {block_height} | Elapsed: {elapsed:.1f}s | Nonce: {nonce}")
                last_update = time.time()

    def _calculate_block_size(self):
        pending_txs = self.transaction_manager.mempool.get_pending_transactions(
            block_size_mb=self.current_block_size
        )
        count = len(pending_txs)

        min_tx, max_tx = 1000, 50000
        min_size, max_size = 1.0, 10.0

        if count <= min_tx:
            new_size = min_size
        elif count >= max_tx:
            new_size = max_size
        else:
            scale = (count - min_tx) / (max_tx - min_tx)
            new_size = min_size + (max_size - min_size) * scale

        # Ensure values remain within range
        new_size = max(min_size, min(new_size, max_size))

        self.current_block_size = new_size
        logging.info(f"Block size adjusted to {self.current_block_size:.2f} MB")


    def _calculate_block_reward(self):
        block_count = len(self.block_manager.chain)
        halvings = block_count // 420480
        reward = Decimal('100.00') / (2 ** halvings)
        return reward

    def _create_coinbase(self, miner_address, fees):
        block_reward = self._calculate_block_reward()
        if block_reward <= Decimal('0'):
            raise ValueError("[ERROR] Block reward exhausted")

        return CoinbaseTx(
            block_height=len(self.block_manager.chain),
            miner_address=miner_address,
            reward=(block_reward + fees)
        )

    def add_block(self, new_block):
        if int(new_block.hash, 16) >= new_block.header.difficulty:
            raise ValueError("[ERROR] Invalid Proof-of-Work")

        self.block_manager.chain.append(new_block)
        self.storage_manager.store_block(new_block, new_block.header.difficulty)
        self.storage_manager.save_blockchain_state(self.block_manager.chain)






    def mining_loop(self, network="mainnet"):
        """
        Continuous mining: keep adding blocks until user stops.
        """
        if not self.block_manager.chain:
            raise RuntimeError("[ERROR] The chain is empty - mine Genesis block first.")

        print("[INFO] Starting indefinite mining loop. Press Ctrl+C to stop.\n")
        block_height = len(self.block_manager.chain)

        while True:
            try:
                block = self.mine_block(network)
                block_height += 1
            except KeyboardInterrupt:
                print("\n[INFO] Mining loop interrupted by user.")
                break
            except Exception as e:
                print(f"[ERROR] Mining error: {str(e)}")
                break


    def mine_block(self, network="mainnet"):
        """
        Mines a single block while ensuring difficulty adjusts dynamically 
        and prioritizes a 5-minute block time.
        """

        # ✅ Ensure Genesis Block Exists
        if not self.block_manager.chain:
            logging.info("[INFO] No Genesis Block found. Creating Genesis Block...")
            self._mine_genesis_block()
            time.sleep(1)

        # ✅ Validate Blockchain State Before Mining
        if not self.block_manager.chain:
            raise RuntimeError("[FATAL ERROR] Blockchain is empty after mining Genesis Block!")

        block_height = len(self.block_manager.chain)

        # ✅ Get Last Block in the Chain Safely
        prev_block = self.block_manager.chain[-1]
        if not prev_block or not prev_block.hash:
            raise RuntimeError("[ERROR] Last block retrieved is invalid or missing a hash!")

        # ✅ Adjust Difficulty Every `DIFFICULTY_ADJUSTMENT_INTERVAL` Blocks
        if block_height % self.block_manager.DIFFICULTY_ADJUSTMENT_INTERVAL == 0:
            target = self.block_manager.calculate_target()
            logging.info(f"[DIFF ADJUST] New difficulty: {hex(target)} after {self.block_manager.DIFFICULTY_ADJUSTMENT_INTERVAL} blocks")
        else:
            target = prev_block.header.difficulty

        # Ensure difficulty never drops below minimum allowed
        min_difficulty = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        target = max(target, min_difficulty)

        self._calculate_block_size()

        # ✅ Fetch Pending Transactions Safely
        pending_txs = self.transaction_manager.mempool.get_pending_transactions(block_size_mb=self.current_block_size)
        if not pending_txs:
            pending_txs = []

        total_fees = sum(tx.fee for tx in pending_txs) if pending_txs else Decimal('0')

        miner_address = self.key_manager.get_default_public_key(network, "miner")
        coinbase_tx = self._create_coinbase(miner_address, total_fees)

        # ✅ Create New Block
        new_block = Block(
            index=block_height,
            previous_hash=prev_block.hash,
            transactions=[coinbase_tx] + pending_txs[:500],
            timestamp=int(time.time()),
            nonce=0,
            difficulty=target
        )

        # ✅ Start Proof-of-Work Mining
        start_time = time.time()
        last_update = start_time
        nonce_limit = 2**64 - 1  # Prevent nonce overflow

        while new_block.header.nonce < nonce_limit:
            new_block.header.nonce += 1
            new_block.hash = new_block.calculate_hash()

            # Check if block meets the difficulty target
            if new_block.hash.startswith("0000") and int(new_block.hash, 16) < target:
                break

            if time.time() - last_update >= 5:
                elapsed = time.time() - start_time
                logging.info(f"[MINING] Block {new_block.index} | Elapsed: {elapsed:.1f}s | Nonce: {new_block.header.nonce}")
                last_update = time.time()

        mining_time = time.time() - start_time
        self.add_block(new_block)

        logging.info(f"[SUCCESS] Block {new_block.index} mined successfully with nonce {new_block.header.nonce} in {mining_time:.2f}s")
        logging.info(f"Previous Block Hash: {new_block.previous_hash}")

        # ✅ Debugging Output
        logging.debug(f"DEBUG: Blockchain Length After Mining = {len(self.block_manager.chain)}")
        logging.debug(f"DEBUG: Latest Block Hash = {self.block_manager.chain[-1].hash if self.block_manager.chain else 'None'}")

        # ✅ Ensure block is stored before moving to next iteration
        stored_block = self.storage_manager.get_block(new_block.hash)
        if not stored_block:
            raise RuntimeError(f"[ERROR] Newly mined block {new_block.index} is missing from storage!")

        return new_block
