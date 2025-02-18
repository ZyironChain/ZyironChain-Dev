import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))



from decimal import Decimal
import time
import hashlib
import math
import numpy as np  # Used for memory-hard operations
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
from Zyiron_Chain.transactions.coinbase import CoinbaseTx 
import logging

# Remove all previous handlers to stop cross-logging


# Setup logging for this specific module only
from Zyiron_Chain.blockchain.constants import Constants

# Ensure this is at the very top of your script, before any other code
class Miner:
    def __init__(self, block_manager, transaction_manager, storage_manager, key_manager):
        """
        Initializes the miner with references to:
        - BlockManager (for managing blocks)
        - TransactionManager (for selecting transactions)
        - StorageManager (for persisting blocks)
        - KeyManager (for retrieving miner addresses)
        """
        self.block_manager = block_manager
        self.transaction_manager = transaction_manager
        self.storage_manager = storage_manager
        self.key_manager = key_manager

        # ✅ Fetch the blockchain reference dynamically
        self.blockchain = self.block_manager.blockchain

        # ✅ Fetch the active network dynamically
        self.network = self.blockchain.constants.NETWORK

        self.current_block_size = 1.0  # ✅ Set initial block size dynamically
        self.chain = self.block_manager.chain  # ✅ Ensure Miner has reference to blockchain

        logging.info(f"[MINER] ✅ Miner initialized on {self.network.upper()}.")

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
            isinstance(tx, CoinbaseTx) and
            len(tx.inputs) == 0 and
            len(tx.outputs) == 1 and
            tx.type == "COINBASE" and
            tx.fee == Decimal(0)
        )

    def sha3_384_pow(self, block_header, target, block_height, start_time):
        """
        Proof-of-Work function using SHA3-384:
        - Mines the block by finding a nonce that meets the target difficulty.
        - Periodically prints live mining status.
        - Returns the valid nonce and block hash.
        """
        nonce = 0
        last_update = start_time
        hash_attempts = 0

        logging.info(f"[MINING] ⛏️ Starting Proof-of-Work for Block {block_height} on {self.network.upper()}...")

        # ✅ Precompute static header data (excludes nonce)
        static_header_data = (
            f"{block_header.version}{block_header.index}"
            f"{block_header.previous_hash}{block_header.merkle_root}"
            f"{block_header.timestamp}{block_header.difficulty}"
        ).encode()

        while True:
            # ✅ Combine static header data with the current nonce
            header_data = static_header_data + str(nonce).encode()
            block_hash = hashlib.sha3_384(header_data).hexdigest()
            hash_attempts += 1

            # ✅ Check if the hash meets the difficulty target
            if int(block_hash, 16) < target:
                logging.info(f"[MINING] ✅ Block {block_height} successfully mined after {hash_attempts} attempts.")
                return nonce, block_hash

            nonce += 1

            # ✅ Show live progress every 5 seconds
            current_time = time.time()
            if current_time - last_update >= 5:
                elapsed = current_time - start_time
                logging.info(f"[LIVE] ⏳ Block {block_height} | Nonce: {nonce} | Attempts: {hash_attempts} | Elapsed: {elapsed:.2f}s")
                last_update = current_time

    def _calculate_block_size(self):
        """
        Dynamically adjust block size based on mempool transaction volume.
        """
        pending_txs = self.transaction_manager.mempool.get_pending_transactions(
            block_size_mb=self.current_block_size
        )
        count = len(pending_txs)

        min_tx, max_tx = 1000, 50000
        min_size, max_size = 1.0, Constants.MAX_BLOCK_SIZE_BYTES / (1024 * 1024)  # Convert bytes to MB

        if count <= min_tx:
            new_size = min_size
        elif count >= max_tx:
            new_size = max_size
        else:
            scale = (count - min_tx) / (max_tx - min_tx)
            new_size = min_size + (max_size - min_size) * scale

        # ✅ Ensure block size remains within range
        new_size = max(min_size, min(new_size, max_size))

        self.current_block_size = new_size
        logging.info(f"🛠️ Block size adjusted to {self.current_block_size:.2f} MB")



    def _calculate_block_reward(self):
        """
        Calculate the current block reward using halving logic.
        - Halves every `BLOCKCHAIN_HALVING_BLOCK_HEIGHT` blocks (~4 years at 5 min block times).
        - Once `MAX_SUPPLY` is reached, the reward is reduced to only transaction fees.
        """
        halving_interval = Constants.BLOCKCHAIN_HALVING_BLOCK_HEIGHT  # ✅ Defined in constants
        initial_reward = Decimal(Constants.INITIAL_COINBASE_REWARD)  # ✅ Uses constant value

        halvings = len(self.block_manager.chain) // halving_interval
        reward = initial_reward / (2 ** halvings)

        # ✅ Ensure we do NOT create coins beyond `MAX_SUPPLY`
        total_mined = self.storage_manager.get_total_mined_supply()
        
        if total_mined >= Constants.MAX_SUPPLY:
            logging.info(f"[BLOCK REWARD] 🚨 Max supply reached! Only transaction fees will be rewarded.")
            return Decimal("0")  # ✅ No new coins, miners only get transaction fees

        return max(reward, Decimal("0"))  # ✅ Ensure it never goes negative


    def _create_coinbase(self, miner_address, fees):
        """
        Creates a coinbase transaction for miners.
        - If max supply is reached, only transaction fees are rewarded.
        """
        block_reward = self._calculate_block_reward()
        total_mined = self.storage_manager.get_total_mined_supply()

        if total_mined >= Constants.MAX_SUPPLY:
            logging.info(f"[COINBASE TX] 🚨 Max supply reached! Only transaction fees will be rewarded.")
            block_reward = Decimal("0")  # ✅ No new coins, only fees are given

        total_reward = max(block_reward + fees, Decimal(Constants.MIN_TRANSACTION_FEE))  # ✅ Ensures min payout

        return CoinbaseTx(
            block_height=len(self.block_manager.chain),
            miner_address=miner_address,
            reward=total_reward
        )


    def add_block(self, new_block):
        """
        Adds a new block to the blockchain:
        - Ensures Proof-of-Work is valid.
        - Validates block structure before storing.
        - Synchronizes across storage layers (UnQLite, SQLite, LMDB).
        - Saves blockchain state safely.
        """

        # ✅ Fetch the active network dynamically
        network = self.block_manager.blockchain.constants.NETWORK

        logging.info(f"[ADD BLOCK] ⛏️ Attempting to add Block {new_block.index} on {network.upper()}...")

        # ✅ Validate Proof-of-Work
        if int(new_block.hash, 16) >= new_block.header.difficulty:
            raise ValueError(f"[ERROR] ❌ Invalid Proof-of-Work for Block {new_block.index} on {network.upper()}.")

        # ✅ Ensure block has a valid structure
        if not self.validate_new_block(new_block):
            raise ValueError(f"[ERROR] ❌ Block {new_block.index} failed validation on {network.upper()}.")

        # ✅ Append block to in-memory chain
        self.block_manager.chain.append(new_block)

        # ✅ Store block across storage layers
        try:
            self.storage_manager.store_block(new_block, new_block.header.difficulty)
            logging.info(f"[STORAGE] ✅ Block {new_block.index} stored successfully in PoC on {network.upper()}.")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to store Block {new_block.index} on {network.upper()}: {e}")
            self.block_manager.chain.pop()  # ✅ Remove from memory if storage fails
            return False

        # ✅ Save blockchain state
        try:
            self.storage_manager.save_blockchain_state(self.block_manager.chain)
            logging.info(f"[STATE] ✅ Blockchain state updated successfully on {network.upper()}.")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to update blockchain state on {network.upper()}: {e}")
            return False

        logging.info(f"[SUCCESS] 🎉 Block {new_block.index} successfully added to {network.upper()}!")
        return True  # ✅ Indicate success





    def mining_loop(self):
        """
        Continuous mining: keep adding blocks until user stops.
        - Mines the Genesis Block if the chain is empty.
        - Dynamically adjusts difficulty.
        - Logs mining progress in real-time.
        - Recovers from mining failures.
        """

        # ✅ Fetch the active network dynamically
        network = self.block_manager.blockchain.constants.NETWORK
        print(f"\n[INFO] ⛏️ Starting mining loop on {network.upper()}. Press Ctrl+C to stop.\n")

        # ✅ Ensure blockchain is not empty; mine Genesis Block if needed
        if not self.block_manager.chain:
            logging.warning(f"[WARNING] ⚠️ Blockchain is empty! Mining Genesis Block on {network.upper()}...")
            self.block_manager.blockchain._ensure_genesis_block()  # ✅ Ensures Genesis Block is mined

            # ✅ Load the newly mined Genesis Block
            genesis_block = self.storage_manager.get_latest_block()
            if not genesis_block:
                raise RuntimeError(f"[ERROR] ❌ Failed to mine Genesis Block on {network.upper()}!")
            
            logging.info(f"[INFO] ✅ Genesis Block Mined on {network.upper()}: {genesis_block.hash}")
            print(f"[INFO] ✅ Genesis Block Created (Hash: {genesis_block.hash[:12]}...)")

        # ✅ Get the latest block height
        block_height = len(self.block_manager.chain)
        block = None

        while True:
            try:
                # ✅ Mine a new block
                block = self.mine_block(network)

                # ✅ Validate new block before adding
                if not self.validate_new_block(block):
                    logging.error(f"[ERROR] ❌ Invalid block mined at height {block.index} on {network.upper()}")
                    raise ValueError(f"[ERROR] ❌ Mined block failed validation on {network.upper()}.")

                # ✅ Append the new block to the chain
                block_height += 1
                self.block_manager.chain.append(block)

                # ✅ Store block in storage
                self.storage_manager.store_block(block, block.header.difficulty)

                # ✅ Adjust difficulty dynamically after block is mined
                new_difficulty = self.block_manager.calculate_target(self.storage_manager)
                logging.info(f"[DIFFICULTY] 🔄 Adjusted difficulty on {network.upper()} to: {hex(new_difficulty)}")

            except KeyboardInterrupt:
                print(f"\n[INFO] ⏹️ Mining loop on {network.upper()} interrupted by user.")
                break

            except Exception as e:
                logging.error(f"[ERROR] ❌ Mining error on {network.upper()}: {str(e)}")
                if block is not None:
                    print(f"[ERROR] ❌ Failed at block height: {block.index} on {network.upper()}")
                    print(f"🆔 Block hash: {block.hash[:12]}...")
                else:
                    print(f"[ERROR] ❌ Error occurred during block initialization on {network.upper()}.")
                    
                if self.block_manager.chain:
                    print(f"[ERROR] ❌ Last valid block hash: {self.block_manager.chain[-1].hash[:12]}...")
                    
                break


    def validate_new_block(self, new_block):
        """
        Validate a newly mined block:
        - Ensure its hash meets the proof-of-work target.
        - Validate the coinbase transaction.
        - Validate subsequent transactions via the transaction manager.
        - Verify block timestamp consistency.
        - Ensure transactions do not exceed the max block size.
        """

        # ✅ Check Proof-of-Work Target
        if int(new_block.hash, 16) >= new_block.header.difficulty:
            logging.error(f"[ERROR] ❌ Invalid Proof-of-Work for block {new_block.index}")
            return False

        # ✅ Validate Coinbase Transaction
        if not new_block.transactions or not isinstance(new_block.transactions[0], CoinbaseTx):
            logging.error("[ERROR] ❌ Block must start with a valid Coinbase transaction.")
            return False

        coinbase_tx = new_block.transactions[0]
        if not self._validate_coinbase(coinbase_tx):
            logging.error("[ERROR] ❌ Invalid coinbase transaction in new block.")
            return False

        # ✅ Validate Block Timestamp (Must be later than previous block but not future-dated)
        prev_block = self.block_manager.chain[-1] if self.block_manager.chain else None
        if prev_block and new_block.timestamp <= prev_block.timestamp:
            logging.error(f"[ERROR] ❌ Block {new_block.index} timestamp is invalid. Must be greater than previous block.")
            return False

        max_time_drift = 7200  # 2 hours max future time drift
        if new_block.timestamp > int(time.time()) + max_time_drift:
            logging.error(f"[ERROR] ❌ Block {new_block.index} timestamp exceeds maximum allowable drift.")
            return False

        # ✅ Ensure Block Size is within Limits
        total_block_size = sum(len(json.dumps(tx.to_dict())) for tx in new_block.transactions)
        if total_block_size > Constants.MAX_BLOCK_SIZE_BYTES:
            logging.error(f"[ERROR] ❌ Block {new_block.index} exceeds max block size limit: {total_block_size} bytes.")
            return False

        # ✅ Validate Transactions (Excluding Coinbase)
        for tx in new_block.transactions[1:]:
            if not self.transaction_manager.validate_transaction(tx):
                logging.error(f"[ERROR] ❌ Invalid transaction in block {new_block.index}: {tx.tx_id}")
                return False

        # ✅ Block Successfully Validated
        logging.info(f"[SUCCESS] ✅ Block {new_block.index} successfully validated.")
        return True





    def mine_block(self, network="mainnet"):
        """
        Mines a new block with Proof-of-Work, dynamically adjusting difficulty based on time.
        - Ensures transactions fit within block constraints.
        - Dynamically adjusts block difficulty before mining.
        - Handles potential mining failures and transaction rollbacks.
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
                    logging.info(f"\n🔄 Resuming from stored block {last_stored_block.index} (Hash: {last_stored_block.hash})")
                else:
                    logging.info("\n⚡ No stored blocks found. Mining Genesis Block...")
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

                # ✅ Collect valid transactions while ensuring block size limits
                valid_txs = [coinbase_tx]
                current_block_size_bytes = len(json.dumps(coinbase_tx.to_dict()))  # Start with coinbase transaction size

                for tx in pending_txs:
                    tx_size = len(json.dumps(tx.to_dict()))
                    if current_block_size_bytes + tx_size <= Constants.MAX_BLOCK_SIZE_BYTES and self.transaction_manager.validate_transaction(tx):
                        valid_txs.append(tx)
                        current_block_size_bytes += tx_size

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
                logging.info(f"\n⛏️ Mining Block {block_height} | Target Difficulty: {hex(current_target)}\n")

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
                        logging.info(f"[LIVE] ⏳ Block {block_height} | Nonce: {new_block.nonce} | Attempts: {attempts} | Time: {elapsed}s")
                        last_update = current_time

                # ✅ Block Mined - Print Details
                logging.info(f"\n✅ Block {block_height} mined successfully with Nonce {new_block.nonce}")
                logging.info(f"🆔 Block Hash: {new_block.hash}")
                logging.info(f"🔗 Previous Block Hash: {prev_block.hash}")
                logging.info(f"⛏️ Miner Address: {new_block.transactions[0].outputs[0]['address']}")
                logging.info(f"💰 Block Reward: {new_block.transactions[0].outputs[0]['amount']} ZYC")
                logging.info(f"🔧 Difficulty at time of mining: {hex(new_block.difficulty)}")

                # ✅ Store block in storage manager
                self.storage_manager.store_block(new_block, new_block.difficulty)
                self.block_manager.chain.append(new_block)

            except Exception as e:
                logging.error(f"Mining failed: {str(e)}")
                if valid_txs:
                    self.transaction_manager.mempool.restore_transactions(valid_txs)
                raise Exception(f"Block mining aborted: {str(e)}")

        return new_block
