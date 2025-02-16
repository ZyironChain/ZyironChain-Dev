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
        block = None  # Initialize variable

        while True:
            try:
                block = self.mine_block(network)
                if not self.validate_new_block(block):
                    raise ValueError("Invalid block mined")
                block_height += 1
            except KeyboardInterrupt:
                print("\n[INFO] Mining loop interrupted by user.")
                break
            except Exception as e:
                print(f"[ERROR] Mining error: {str(e)}")
                # Safely check if block exists
                if block is not None:  # First check if block was created
                    print(f"Failed at block height: {block.index}")
                    print(f"Block hash: {block.hash[:12]}...")
                else:
                    print("Error occurred during block initialization")
                if self.block_manager.chain:
                    print(f"Last valid block hash: {self.block_manager.chain[-1].hash[:12]}...")
                break

    def validate_new_block(self, new_block: Block) -> bool:
        """Comprehensive block validation"""
        # 1. Verify Proof-of-Work
        if int(new_block.hash, 16) >= new_block.header.difficulty:
            logging.error("Invalid Proof-of-Work")
            return False

        # 2. Check previous block linkage
        if self.chain:
            last_block = self.chain[-1]
            if new_block.previous_hash != last_block.hash:
                logging.error("Previous hash mismatch")
                return False

        # 3. Validate coinbase transaction
        if not self._validate_coinbase(new_block.transactions[0]):
            logging.error("Invalid coinbase transaction")
            return False

        # 4. Verify transaction signatures
        for tx in new_block.transactions[1:]:
            if not self.transaction_manager.validate_transaction(tx):
                logging.error(f"Invalid transaction {tx.tx_id}")
                return False

        return True
    



    def mine_block(self, network="mainnet"):
        """
        Mines a block with comprehensive validation and real-time difficulty monitoring
        """
        from threading import Lock
        mining_lock = Lock()
        
        # Initialize variables outside try block
        valid_txs = []
        valid_block = None

        with mining_lock:
            try:
                # Initialize mining session
                start_time = time.time()
                last_update = start_time
                mining_attempts = 0

                # Get current chain state
                current_chain = self.block_manager.chain
                if not current_chain:
                    self._mine_genesis_block()
                    time.sleep(1)  # Allow for chain state propagation
                    current_chain = self.block_manager.chain

                prev_block = current_chain[-1]
                block_height = len(current_chain)

                # Dynamic difficulty handling
                current_target = self.block_manager.difficulty_target
                current_target = max(current_target, self.block_manager.MIN_DIFFICULTY)

                # Calculate current block size
                self._calculate_block_size()
                current_block_size_mb = self.current_block_size

                # Prepare block components
                coinbase_tx = self._create_coinbase(
                    self.key_manager.get_default_public_key(network, "miner"),
                    sum(tx.fee for tx in self.transaction_manager.mempool.get_pending_transactions(
                        block_size_mb=current_block_size_mb  # Fixed here
                    ))
                )

                # Validate transactions before mining
                valid_txs = [coinbase_tx] + [
                    tx for tx in self.transaction_manager.mempool.get_pending_transactions(
                        block_size_mb=current_block_size_mb  # Fixed here
                    )
                    if self.transaction_manager.validate_transaction(tx)
                ][:500]

                # Create preliminary block
                new_block = Block(
                    index=block_height,
                    previous_hash=prev_block.hash,
                    transactions=valid_txs,
                    timestamp=int(time.time()),
                    nonce=0,
                    difficulty=current_target
                )

                # Rest of the method remains the same...
                
            except Exception as e:
                logging.error(f"Mining failed: {str(e)}")
                if valid_txs:
                    self.transaction_manager.mempool.restore_transactions(valid_txs)
                raise MiningError(f"Block mining aborted: {str(e)}")