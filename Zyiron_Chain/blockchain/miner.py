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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # These imports will only be available during type-checking (e.g., for linters, IDEs, or mypy)
    from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
    from Zyiron_Chain.transactions.fees import FundsAllocator


# Remove all previous handlers to stop cross-logging


# Setup logging for this specific module only
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.blockchain.utils.hashing import Hashing
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
        self.network = Constants.NETWORK  # ✅ Use Constants for network assignment

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
        
        # ✅ Ensure transaction ID is properly double hashed
        if not hasattr(tx, "tx_id") or not isinstance(tx.tx_id, str):
            logging.error(f"[ERROR] ❌ Invalid Coinbase transaction ID format: {tx.tx_id}")
            return False
        
        tx_id_hashed = Hashing.double_sha3_384(tx.tx_id.encode())  # ✅ Apply double SHA3-384 hashing

        return (
            isinstance(tx, CoinbaseTx) and
            len(tx.inputs) == 0 and
            len(tx.outputs) == 1 and
            tx.type == "COINBASE" and
            tx.fee == Decimal(0) and
            tx_id_hashed == tx.tx_id  # ✅ Ensure transaction ID matches double-hashed format
        )


    def _calculate_block_size(self):
        """
        Dynamically adjust block size based on mempool transaction volume and block allocation settings.
        """
        try:
            # ✅ Fetch pending transactions safely
            pending_txs = self.transaction_manager.mempool.get_pending_transactions(
                block_size_mb=self.current_block_size
            )

            if not isinstance(pending_txs, list):
                logging.error("[BLOCK SIZE] ❌ Invalid transaction list retrieved from mempool.")
                return

            count = len(pending_txs)

            # ✅ Use Constants for min/max block size settings
            min_tx, max_tx = 1000, 50000
            min_size, max_size = (
                Constants.MIN_BLOCK_SIZE_BYTES / (1024 * 1024),
                Constants.MAX_BLOCK_SIZE_BYTES / (1024 * 1024)
            )  # Convert bytes to MB

            # ✅ Dynamically adjust block size based on transaction volume
            if count <= min_tx:
                new_size = min_size
            elif count >= max_tx:
                new_size = max_size
            else:
                scale = (count - min_tx) / (max_tx - min_tx)
                new_size = min_size + (max_size - min_size) * scale

            # ✅ Ensure block size respects mempool allocation limits
            standard_allocation = new_size * Constants.MEMPOOL_STANDARD_ALLOCATION
            smart_allocation = new_size * Constants.MEMPOOL_SMART_ALLOCATION

            # ✅ Dynamically allocate space based on transaction type
            standard_txs = []
            smart_txs = []

            for tx in pending_txs:
                if not hasattr(tx, "tx_id") or not hasattr(tx, "size"):
                    logging.warning(f"[BLOCK SIZE] ⚠️ Skipping transaction with missing attributes: {tx}")
                    continue

                if any(tx.tx_id.startswith(prefix) for prefix in Constants.TRANSACTION_MEMPOOL_MAP["STANDARD"]["prefixes"]):
                    standard_txs.append(tx)
                elif any(tx.tx_id.startswith(prefix) for prefix in Constants.TRANSACTION_MEMPOOL_MAP["SMART"]["prefixes"]):
                    smart_txs.append(tx)

            # ✅ Calculate allocated space usage
            total_standard_size = sum(tx.size for tx in standard_txs) / (1024 * 1024)  # Convert to MB
            total_smart_size = sum(tx.size for tx in smart_txs) / (1024 * 1024)  # Convert to MB

            # ✅ Ensure block allocation respects priority limits
            if total_standard_size > standard_allocation:
                logging.warning(f"[BLOCK SIZE] 🚨 Standard transactions exceed allocation ({total_standard_size:.2f} MB)")
                total_standard_size = standard_allocation
            if total_smart_size > smart_allocation:
                logging.warning(f"[BLOCK SIZE] 🚨 Smart transactions exceed allocation ({total_smart_size:.2f} MB)")
                total_smart_size = smart_allocation

            # ✅ Adjust final block size based on real allocation
            final_block_size = total_standard_size + total_smart_size
            self.current_block_size = max(min_size, min(final_block_size, max_size))

            logging.info(f"🛠️ Block size dynamically adjusted to {self.current_block_size:.2f} MB")

        except Exception as e:
            logging.error(f"[BLOCK SIZE ERROR] ❌ Exception occurred during block size calculation: {e}")




    def _calculate_block_reward(self):
        """
        Calculate the current block reward using halving logic.
        - Halves every `BLOCKCHAIN_HALVING_BLOCK_HEIGHT` blocks (~4 years at 5 min block times).
        - Once `MAX_SUPPLY` is reached, the reward is reduced to only transaction fees.
        """
        try:
            # ✅ Fetch dynamic blockchain constants safely
            halving_interval = getattr(Constants, "BLOCKCHAIN_HALVING_BLOCK_HEIGHT", None)
            initial_reward = getattr(Constants, "INITIAL_COINBASE_REWARD", None)
            max_supply = getattr(Constants, "MAX_SUPPLY", None)
            min_fee = getattr(Constants, "MIN_TRANSACTION_FEE", None)

            if halving_interval is None or initial_reward is None or min_fee is None:
                logging.error("[BLOCK REWARD ERROR] ❌ Missing required constants for block reward calculation.")
                return Decimal("0")

            if not isinstance(initial_reward, (int, float, Decimal)):
                logging.error(f"[BLOCK REWARD ERROR] ❌ Invalid INITIAL_COINBASE_REWARD value: {initial_reward}")
                return Decimal("0")

            initial_reward = Decimal(initial_reward)
            min_fee = Decimal(min_fee)

            # ✅ Ensure blockchain chain is valid before accessing its length
            if not hasattr(self.block_manager, "chain") or not isinstance(self.block_manager.chain, list):
                logging.error("[BLOCK REWARD ERROR] ❌ Invalid blockchain reference in block manager.")
                return Decimal("0")

            current_height = len(self.block_manager.chain)

            # ✅ Prevent division by zero and negative halving calculations
            halvings = max(0, current_height // halving_interval)
            reward = initial_reward / (2 ** halvings)

            # ✅ Fetch total mined supply safely
            try:
                total_mined = self.storage_manager.get_total_mined_supply()
            except Exception as e:
                logging.error(f"[BLOCK REWARD ERROR] ❌ Failed to retrieve total mined supply: {e}")
                return Decimal("0")

            # ✅ Prevent over-minting beyond `MAX_SUPPLY`
            if max_supply is not None and isinstance(max_supply, (int, float, Decimal)) and total_mined >= Decimal(max_supply):
                logging.info("[BLOCK REWARD] 🚨 Max supply reached! Miners will only receive transaction fees.")
                return Decimal("0")  # ✅ No new coins, miners only get transaction fees

            # ✅ Ensure reward does not go below the minimum fee
            final_reward = max(reward, min_fee)

            logging.info(f"[BLOCK REWARD] 🎁 Block reward: {final_reward} ZYC | Total Mined: {total_mined}/{max_supply}")
            return final_reward

        except Exception as e:
            logging.error(f"[BLOCK REWARD ERROR] ❌ Unexpected error during reward calculation: {e}")
            return Decimal("0")




    def _create_coinbase(self, miner_address, fees):
        """
        Creates a coinbase transaction for miners.
        - If max supply is reached, only transaction fees are rewarded.
        - Ensures a minimum payout using `Constants.MIN_TRANSACTION_FEE`.
        """
        # ✅ Fetch calculated block reward
        block_reward = self._calculate_block_reward()
        
        # ✅ Fetch total mined supply from storage
        total_mined = self.storage_manager.get_total_mined_supply()

        # ✅ If max supply is reached, only reward transaction fees
        if Constants.MAX_SUPPLY is not None and total_mined >= Constants.MAX_SUPPLY:
            logging.info(f"[COINBASE TX] 🚨 Max supply reached! Only transaction fees will be rewarded.")
            block_reward = Decimal("0")  # ✅ Ensure no new coin generation

        # ✅ Ensure a minimum payout (block reward + fees)
        total_reward = max(block_reward + fees, Decimal(Constants.MIN_TRANSACTION_FEE))

        logging.info(f"[COINBASE TX] 🎁 Coinbase reward: {total_reward} ZYC (Fees: {fees}, Block Reward: {block_reward})")

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
        - Synchronizes across storage layers (LMDB).
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

        # ✅ Confirm all transactions before adding the block
        for tx in new_block.transactions:
            tx_id_hashed = Hashing.double_sha3_384(tx.tx_id.encode())

            tx_type = PaymentTypeManager().get_transaction_type(tx_id_hashed)
            required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(tx_type.name, Constants.TRANSACTION_CONFIRMATIONS["STANDARD"])

            confirmations = self.storage_manager.get_transaction_confirmations(tx_id_hashed)

            if confirmations is None:
                logging.error(f"[ERROR] ❌ Could not retrieve confirmations for transaction {tx_id_hashed}.")
                return False

            if confirmations < required_confirmations:
                logging.error(f"[ERROR] ❌ Transaction {tx_id_hashed} does not meet required confirmations ({required_confirmations}, Found: {confirmations}).")
                return False

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







    def mining_loop(self, network=None):
        """
        Continuous mining: keep adding blocks until user stops.
        - Mines the Genesis Block if the chain is empty.
        - Dynamically adjusts difficulty.
        - Logs mining progress in real-time.
        - Recovers from mining failures.

        :param network: (Optional) Network name (e.g., "mainnet" or "testnet").
                        If not provided, uses the active network from the blockchain.
        """
        from Zyiron_Chain.blockchain.constants import Constants
        network = network or self.block_manager.blockchain.constants.NETWORK
        print(f"\n[INFO] ⛏️ Starting mining loop on {network.upper()}. Press Ctrl+C to stop.\n")

        # ✅ Ensure blockchain is initialized and Genesis Block is valid
        if not self.block_manager.chain:
            logging.warning(f"[WARNING] ⚠️ Blockchain is empty! Mining Genesis Block on {network.upper()}...")
            self.block_manager.blockchain._ensure_genesis_block()

            # ✅ Validate and retrieve the Genesis Block
            genesis_block = self.storage_manager.get_latest_block()
            if not genesis_block or int(genesis_block.hash, 16) >= genesis_block.difficulty:
                raise RuntimeError(f"[ERROR] ❌ Genesis Block validation failed on {network.upper()}!")

            logging.info(f"[INFO] ✅ Genesis Block Mined on {network.upper()}: {genesis_block.hash}")
            print(f"[INFO] ✅ Genesis Block Created (Hash: {genesis_block.hash[:12]}...)")

        block_height = len(self.block_manager.chain)
        block = None

        while True:
            try:
                block = self.mine_block(network)

                # ✅ Ensure mined block is valid before adding it
                if not block or not self.validate_new_block(block):
                    logging.error(f"[ERROR] ❌ Invalid block mined at height {block.index} on {network.upper()}")
                    raise ValueError(f"[ERROR] ❌ Mined block failed validation on {network.upper()}.")

                block_height += 1
                self.block_manager.chain.append(block)

                # ✅ Store mined block
                self.storage_manager.store_block(block, block.header.difficulty)

                # ✅ Retrieve and log total mined supply
                total_supply = self.storage_manager.get_total_mined_supply()
                logging.info(f"[SUPPLY] Total mined supply so far: {total_supply} out of maximum {Constants.MAX_SUPPLY}")

                # ✅ Dynamically adjust difficulty
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
        try:
            # ✅ Ensure `new_block` is valid
            if not hasattr(new_block, "hash") or not hasattr(new_block, "header"):
                logging.error("[BLOCK VALIDATION ERROR] ❌ Block object is missing required attributes.")
                return False

            if not isinstance(new_block.transactions, list):
                logging.error("[BLOCK VALIDATION ERROR] ❌ Transactions must be a list.")
                return False

            # ✅ Check Proof-of-Work Target using double SHA3-384
            try:
                block_hash_int = int(new_block.hash, 16)
            except ValueError:
                logging.error(f"[ERROR] ❌ Block {new_block.index} has an invalid hash format.")
                return False

            if block_hash_int >= new_block.header.difficulty:
                logging.error(f"[ERROR] ❌ Invalid Proof-of-Work for block {new_block.index}.")
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
            if prev_block:
                try:
                    if int(new_block.timestamp) <= int(prev_block.timestamp):
                        logging.error(f"[ERROR] ❌ Block {new_block.index} timestamp is invalid. Must be greater than previous block.")
                        return False
                except ValueError:
                    logging.error(f"[ERROR] ❌ Block {new_block.index} has an invalid timestamp format.")
                    return False

            max_time_drift = 7200  # 2 hours max future time drift
            if new_block.timestamp > int(time.time()) + max_time_drift:
                logging.error(f"[ERROR] ❌ Block {new_block.index} timestamp exceeds maximum allowable drift.")
                return False

            # ✅ Ensure Block Size is within Limits
            try:
                total_block_size = sum(len(json.dumps(tx.to_dict())) for tx in new_block.transactions)
            except (TypeError, AttributeError) as e:
                logging.error(f"[ERROR] ❌ Failed to calculate block size: {e}")
                return False

            if total_block_size > Constants.MAX_BLOCK_SIZE_BYTES:
                logging.error(f"[ERROR] ❌ Block {new_block.index} exceeds max block size limit: {total_block_size} bytes.")
                return False

            # ✅ Validate Transactions (Excluding Coinbase)
            for tx in new_block.transactions[1:]:
                try:
                    tx_hash = Hashing.double_sha3_384(tx.tx_id.encode())  # ✅ Use a separate variable to avoid modifying tx_id

                    if not self.transaction_manager.validate_transaction(tx):
                        logging.error(f"[ERROR] ❌ Invalid transaction in block {new_block.index}: {tx.tx_id}")
                        return False

                except AttributeError as e:
                    logging.error(f"[ERROR] ❌ Transaction missing required attributes: {e}")
                    return False

            # ✅ Block Successfully Validated
            logging.info(f"[SUCCESS] ✅ Block {new_block.index} successfully validated.")
            return True

        except Exception as e:
            logging.error(f"[BLOCK VALIDATION ERROR] ❌ Unexpected error during block validation: {e}")
            return False




    def mine_block(self, network=Constants.NETWORK):
        """
        Mines a new block using Proof-of-Work with dynamically adjusted difficulty.
        - Uses single SHA3-384 hashing.
        - Dynamically adjusts difficulty based on `Constants.DIFFICULTY_ADJUSTMENT_INTERVAL`.
        """
        mining_lock = Lock()
        with mining_lock:
            try:
                start_time = time.time()
                last_update = start_time

                # ✅ Retrieve last stored block safely
                last_block = self.storage_manager.get_latest_block()
                if not last_block:
                    logging.warning("[MINING] ⚠️ No previous block found; mining Genesis block.")
                    self.block_manager.blockchain._ensure_genesis_block()
                    last_block = self.storage_manager.get_latest_block()

                if not last_block:
                    logging.error("[MINING ERROR] ❌ Failed to retrieve or create Genesis block.")
                    return None

                block_height = last_block.index + 1
                logging.info(f"\n🔄 Resuming from Block {last_block.index} (Hash: {last_block.hash})")

                # ✅ Dynamically adjust difficulty
                current_target = self.block_manager.calculate_target(self.storage_manager)
                current_target = max(min(current_target, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

                # ✅ Retrieve miner address safely
                miner_address = self.key_manager.get_default_public_key(network, "miner")
                if not miner_address:
                    logging.error("[MINING ERROR] ❌ Failed to retrieve miner address.")
                    return None

                self._calculate_block_size()
                pending_txs = self.transaction_manager.mempool.get_pending_transactions(
                    block_size_mb=self.current_block_size
                ) or []

                total_fees = sum(tx.fee for tx in pending_txs if hasattr(tx, "fee"))

                # ✅ Create coinbase transaction
                coinbase_tx = self._create_coinbase(miner_address, total_fees)
                valid_txs = [coinbase_tx] + pending_txs

                # ✅ Construct new block
                new_block = Block(
                    index=block_height,
                    previous_hash=last_block.hash,
                    transactions=valid_txs,
                    timestamp=int(time.time()),
                    nonce=0,
                    difficulty=current_target
                )

                # ✅ Proof-of-Work Mining
                nonce = 0
                hash_attempts = 0  # ✅ Keep track of attempts
                last_update = start_time

                logging.info(f"[MINING] ⛏️ Starting mining loop for Block {block_height}...")

                while True:
                    new_block.header.nonce = nonce
                    block_hash = hashlib.sha3_384(new_block.calculate_hash().encode()).hexdigest()

                    # ✅ Ensure hash meets difficulty target
                    if int(block_hash, 16) < new_block.difficulty:
                        new_block.hash = block_hash
                        break

                    nonce += 1
                    hash_attempts += 1

                    # ✅ Log live progress every 2 seconds
                    current_time = time.time()
                    if current_time - last_update >= 2:
                        elapsed = int(current_time - start_time)
                        logging.info(f"[LIVE] ⏳ Block {block_height} | Nonce: {nonce} | Attempts: {hash_attempts} | Time: {elapsed}s")
                        last_update = current_time

                self.storage_manager.store_block(new_block, new_block.difficulty)
                self.block_manager.chain.append(new_block)

                logging.info(f"✅ Block {block_height} mined successfully! Hash: {new_block.hash}")
                return new_block

            except Exception as e:
                logging.error(f"[MINING ERROR] ❌ Mining failed: {e}")
                return None
