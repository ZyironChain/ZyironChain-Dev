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
from threading import Lock

import time
import sys
import hashlib
from decimal import Decimal
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
import logging

# Remove all previous handlers to stop cross-logging


# Setup logging for this specific module only
from Zyiron_Chain.blockchain.constants import Constants

# Ensure this is at the very top of your script, before any other code
class Miner:
    def __init__(self, block_manager, transaction_manager, storage_manager, key_manager):
        self.block_manager = block_manager
        self.transaction_manager = transaction_manager
        self.storage_manager = storage_manager
        self.key_manager = key_manager

        self.current_block_size = 1.0
        # Ensure Miner has a reference to the blockchain chain via block_manager
        self.chain = self.block_manager.chain



    def _validate_coinbase(self, tx):
        """
        Ensure the coinbase transaction follows protocol rules:
        - No inputs.
        - Exactly one output.
        - Transaction type is "COINBASE".
        - Fee is zero.
        """
        from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx  # Lazy import
        return (
            len(tx.inputs) == 0 and
            len(tx.outputs) == 1 and
            tx.type == "COINBASE" and
            tx.fee == Decimal(0)
        )



    def sha3_384_pow(self, block_header, target, block_height, start_time):
        nonce = 0
        last_update = start_time
        hash_attempts = 0

        # Precompute static header data
        static_header_data = (
            f"{block_header.version}{block_header.index}"
            f"{block_header.previous_hash}{block_header.merkle_root}"
            f"{block_header.timestamp}{block_header.difficulty}"
        ).encode()

        while True:
            # Combine static header data with the current nonce
            header_data = static_header_data + str(nonce).encode()
            block_hash = hashlib.sha3_384(header_data).hexdigest()
            hash_attempts += 1

            # Check if the hash meets the target
            if int(block_hash, 16) < target:
                return nonce, block_hash

            nonce += 1

            # Show live time + nonce every 5 seconds
            current_time = time.time()
            if current_time - last_update >= 5:
                elapsed = current_time - start_time
                print(f"[LIVE] Mining Block {block_height} | Nonce: {nonce}, Attempts: {hash_attempts}, Elapsed Time: {elapsed:.2f}s")
                last_update = current_time

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
        block = None

        while True:
            try:
                block = self.mine_block(network)
                if not self.validate_new_block(block):
                    raise ValueError("Invalid block mined")
                block_height += 1
                # Optionally, add the new block to the chain here.
                self.block_manager.chain.append(block)
            except KeyboardInterrupt:
                print("\n[INFO] Mining loop interrupted by user.")
                break
            except Exception as e:
                print(f"[ERROR] Mining error: {str(e)}")
                if block is not None:
                    print(f"Failed at block height: {block.index}")
                    print(f"Block hash: {block.hash[:12]}...")
                else:
                    print("Error occurred during block initialization")
                if self.block_manager.chain:
                    print(f"Last valid block hash: {self.block_manager.chain[-1].hash[:12]}...")
                break


    def validate_new_block(self, new_block):
        """
        Validate a newly mined block:
        - Ensure its hash meets the proof-of-work target.
        - Validate the coinbase transaction.
        - Validate subsequent transactions via the transaction manager.
        """
        # Check Proof-of-Work
        if int(new_block.hash, 16) >= new_block.header.difficulty:
            logging.error(f"Invalid Proof-of-Work for block {new_block.index}")
            return False

        # Validate coinbase transaction using our local _validate_coinbase
        coinbase_tx = new_block.transactions[0]
        if not self._validate_coinbase(coinbase_tx):
            logging.error("Invalid coinbase transaction in new block")
            return False

        # Validate remaining transactions using the transaction manager
        for tx in new_block.transactions[1:]:
            if not self.transaction_manager.validate_transaction(tx):
                logging.error(f"Invalid transaction in block {new_block.index}: {tx.tx_id}")
                return False

        # (Optional) You may also validate timestamp ordering if needed.
        return True





    def mine_block(self, network="mainnet"):
        """
        Mines a new block with Proof-of-Work, dynamically adjusting difficulty based on time.
        """

        mining_lock = Lock()
        valid_txs = []
        new_block = None

        with mining_lock:
            try:
                start_time = time.time()
                last_update = start_time

                # ✅ Load last stored block
                last_stored_block = self.storage_manager.get_latest_block()

                if last_stored_block:
                    prev_block = last_stored_block
                    block_height = last_stored_block.index + 1
                    print(f"\n🔄 Resuming from stored block {last_stored_block.index} (Hash: {last_stored_block.hash})")
                else:
                    print("\n⚡ No stored blocks found. Mining Genesis Block...")
                    self.block_manager.blockchain._ensure_genesis_block()  # ✅ Correctly access Blockchain

                    time.sleep(1)
                    last_stored_block = self.storage_manager.get_latest_block()
                    prev_block = last_stored_block
                    block_height = 1  # After Genesis Block

                # ✅ Fetch dynamically adjusted difficulty before mining
                current_target = self.block_manager.calculate_target(self.storage_manager)

                # ✅ Ensure difficulty is within range
                current_target = max(min(current_target, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

                # ✅ Adjust block size dynamically
                self._calculate_block_size()
                current_block_size_mb = self.current_block_size

                # ✅ Create coinbase transaction
                miner_address = self.key_manager.get_default_public_key(network, "miner")
                pending_txs = self.transaction_manager.mempool.get_pending_transactions(block_size_mb=current_block_size_mb)
                total_fees = sum(tx.fee for tx in pending_txs if hasattr(tx, "fee")) if pending_txs else Decimal("0")

                coinbase_tx = self._create_coinbase(miner_address, total_fees)

                # ✅ Collect valid transactions
                valid_txs = [coinbase_tx] + ([tx for tx in pending_txs if self.transaction_manager.validate_transaction(tx)][:500] if pending_txs else [])

                # ✅ Create new block
                new_block = Block(
                    index=block_height,
                    previous_hash=prev_block.hash,
                    transactions=valid_txs,
                    timestamp=int(time.time()),
                    nonce=0,
                    difficulty=current_target  # ✅ Apply the latest difficulty
                )
                new_block.hash = new_block.calculate_hash()

                # ✅ Start Proof-of-Work Mining Loop
                attempts = 0
                print(f"\n⛏️ Mining Block {block_height} | Target Difficulty: {hex(current_target)}\n")

                # **Precompute static header data for efficiency**
                static_header_data = (
                    f"{new_block.index}{new_block.previous_hash}"
                    f"{new_block.transactions[0].outputs[0]['address']}{new_block.timestamp}"
                ).encode()

                while True:
                    # **Combine static header data with nonce**
                    header_data = static_header_data + str(new_block.nonce).encode()
                    new_block.hash = hashlib.sha3_384(header_data).hexdigest()
                    attempts += 1

                    # ✅ Check if hash meets the target difficulty
                    if int(new_block.hash, 16) < new_block.difficulty:
                        break

                    new_block.nonce += 1
                    current_time = time.time()

                    # **Log progress every 5 seconds**
                    if current_time - last_update >= 5:
                        elapsed = int(current_time - start_time)
                        print(f"[LIVE] ⏳ Block {block_height} | Nonce: {new_block.nonce} | Attempts: {attempts} | Time: {elapsed}s")
                        last_update = current_time

                # ✅ Block Mined - Print Details
                print(f"\n✅ Block {block_height} mined successfully with Nonce {new_block.nonce}")
                print(f"🆔 Block Hash: {new_block.hash}")
                print(f"🔗 Previous Block Hash: {prev_block.hash}")
                print(f"⛏️ Miner Address: {new_block.transactions[0].outputs[0]['address']}")
                print(f"💰 Block Reward: {new_block.transactions[0].outputs[0]['amount']} ZYC")
                print(f"🔧 Difficulty at time of mining: {hex(new_block.difficulty)}")

                # ✅ Store block
                self.storage_manager.store_block(new_block, new_block.difficulty)
                self.block_manager.chain.append(new_block)

            except Exception as e:
                logging.error(f"Mining failed: {str(e)}")
                if valid_txs:
                    self.transaction_manager.mempool.restore_transactions(valid_txs)
                raise Exception(f"Block mining aborted: {str(e)}")

        return new_block
