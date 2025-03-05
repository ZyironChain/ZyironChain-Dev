import sys
import os
import json
import hashlib
import time
import math
from threading import Lock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.blockchain.blockheader import BlockHeader
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.utils.key_manager import KeyManager
from Zyiron_Chain.utils.hashing import Hashing

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

# =============================================================================
# BlockManager: Manages blockchain validation, difficulty adjustments, and block storage.
# =============================================================================
class BlockManager:
    """
    Manages blockchain validation, difficulty adjustments, and storing block data
    via the StorageManager. Also provides chain-level checks like chain validation,
    Merkle root calculations, and retrieving the latest block.
    
    - All data is processed as bytes.
    - Only single SHA3-384 hashing is used.
    """
    def __init__(self, blockchain, storage_manager, transaction_manager):
        """
        Initialize BlockManager with references to:
        - blockchain: Main Blockchain object (provides in-memory chain list).
        - storage_manager: Handles block & transaction persistence.
        - transaction_manager: Provides transaction validations.
        """
        self.blockchain = blockchain
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager
        self.chain = blockchain.chain  # In-memory chain list

        self.network = Constants.NETWORK
        self.version = Constants.VERSION
        self.difficulty_target = Constants.GENESIS_TARGET

        print(f"[BlockManager.__init__] INIT: Initialized on {self.network.upper()} | Version {self.version} | Difficulty {hex(self.difficulty_target)}.")

    def validate_block(self, block):
        """
        Hook for additional block validation logic (e.g., checking block shape,
        advanced checks such as smart-contract states, etc.).
        (Currently a stub; advanced validations can be added as needed.)
        """
        print(f"[BlockManager.validate_block] INFO: Validating Block {block.index}.")

    def validate_chain(self):
        """
        Validate the entire chain for integrity:
        - Each block's transactions meet required confirmations.
        - Correct previous_hash linkage (except for Genesis).
        - Block difficulty/Proof-of-Work is correct.
        - Transaction IDs are validated using single SHA3-384 hashing.
        """
        if not self.chain:
            print("[BlockManager.validate_chain] ERROR: Blockchain is empty. Cannot validate.")
            return False

        for i, current_block in enumerate(self.chain):
            # Basic attribute checks
            for attr in ["transactions", "previous_hash", "hash", "header"]:
                if not hasattr(current_block, attr):
                    print(f"[BlockManager.validate_chain] ERROR: Block {i} missing attribute '{attr}'. Possible corruption.")
                    return False

            # Confirmations check for transactions
            for tx in current_block.transactions:
                if not hasattr(tx, "tx_id"):
                    print(f"[BlockManager.validate_chain] ERROR: Transaction in Block {current_block.index} missing 'tx_id'.")
                    return False

                # Ensure tx_id is a string before encoding
                if isinstance(tx.tx_id, bytes):
                    tx.tx_id = tx.tx_id.decode("utf-8")

                # Use single SHA3-384 hashing via our Hashing utility (input as bytes, output as bytes)
                single_hashed_tx_id = Hashing.hash(tx.tx_id.encode()).hex()

                tx_type = PaymentTypeManager().get_transaction_type(single_hashed_tx_id)
                required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                    tx_type.name.upper(), Constants.TRANSACTION_CONFIRMATIONS["STANDARD"]
                )
                confirmations = self.storage_manager.get_transaction_confirmations(single_hashed_tx_id)
                if confirmations is None or confirmations < required_confirmations:
                    print(f"[BlockManager.validate_chain] ERROR: Transaction {single_hashed_tx_id} in Block {current_block.index} does not meet required confirmations ({required_confirmations}). Found: {confirmations}.")
                    return False

        print("[BlockManager.validate_chain] SUCCESS: Blockchain validated successfully.")
        return True

    def calculate_merkle_root(self, transactions):
        """
        Compute the Merkle root using single SHA3-384 hashing.
        - Each transaction is serialized to JSON (as bytes) and hashed.
        - The tree is built pairwise until one root remains.
        - Returns the Merkle root as a hex string.
        """
        try:
            if not isinstance(transactions, list):
                print("[BlockManager.calculate_merkle_root] ERROR: Transactions input must be a list.")
                return Constants.ZERO_HASH

            if not transactions:
                print("[BlockManager.calculate_merkle_root] WARNING: No transactions found. Returning ZERO_HASH.")
                return Constants.ZERO_HASH

            tx_hashes = []
            for tx in transactions:
                try:
                    # Use to_dict() if available, else assume tx is dict-like
                    to_serialize = tx.to_dict() if hasattr(tx, "to_dict") else tx
                    tx_serialized = json.dumps(to_serialize, sort_keys=True).encode()
                    # Use single hashing (bytes in, bytes out)
                    tx_hash = Hashing.hash(tx_serialized)
                    tx_hashes.append(tx_hash)
                except Exception as e:
                    print(f"[BlockManager.calculate_merkle_root] ERROR: Failed to serialize transaction. Exception: {e}.")
                    return Constants.ZERO_HASH

            # Build the Merkle tree pairwise
            while len(tx_hashes) > 1:
                if len(tx_hashes) % 2 != 0:
                    tx_hashes.append(tx_hashes[-1])  # Duplicate last hash if odd count
                temp_level = []
                for i in range(0, len(tx_hashes), 2):
                    combined = tx_hashes[i] + tx_hashes[i + 1]
                    new_hash = Hashing.hash(combined)
                    temp_level.append(new_hash)
                tx_hashes = temp_level

            merkle_root = tx_hashes[0].hex()  # Convert final hash to hex for output
            print(f"[BlockManager.calculate_merkle_root] SUCCESS: Merkle Root computed: {merkle_root}.")
            return merkle_root

        except Exception as e:
            print(f"[BlockManager.calculate_merkle_root] ERROR: Exception while computing Merkle root: {e}.")
            return Constants.ZERO_HASH

    def send_block_information(self, block):
        """
        Stores block data via the StorageManager.
        """
        try:
            self.storage_manager.store_block(block, block.header.difficulty)
            print(f"[BlockManager.send_block_information] SUCCESS: Block {block.index} stored (Difficulty: {hex(block.header.difficulty)}).")
        except Exception as e:
            print(f"[BlockManager.send_block_information] ERROR: Failed to store Block {block.index}. Exception: {e}.")
            raise

    def add_block(self, block):
        """
        Adds a validated block to the in-memory chain and triggers difficulty adjustment if needed.
        """
        self.chain.append(block)
        print(f"[BlockManager.add_block] INFO: Block {block.index} added. Difficulty: {hex(block.header.difficulty)}.")
        if len(self.chain) % Constants.DIFFICULTY_ADJUSTMENT_INTERVAL == 0:
            self.difficulty_target = self.adjust_difficulty(self.storage_manager)

    def get_latest_block(self):
        """
        Returns the last block in the in-memory chain, or None if the chain is empty.
        """
        if self.chain:
            return self.chain[-1]
        print("[BlockManager.get_latest_block] WARNING: In-memory chain is empty.")
        return None

    def validate_block(self, block):
        """
        Validate a block before adding it to the blockchain.
        - Ensures consistency with previous blocks.
        - Checks Proof-of-Work meets difficulty target.
        - Validates all transactions within the block.
        - Ensures block size does not exceed the maximum limit.
        - Prevents future-dated blocks.
        """
        try:
            # ✅ Ensure the block follows correct blockchain structure
            last_block = self.storage_manager.get_last_block()
            if last_block and block.previous_hash != last_block.hash:
                raise ValueError(f"[ERROR] ❌ Block {block.index} previous hash mismatch: Expected {last_block.hash}, Got {block.previous_hash}")

            # ✅ Validate block size against max limit
            block_size = sys.getsizeof(json.dumps(block.to_dict()).encode())
            if block_size > Constants.MAX_BLOCK_SIZE_BYTES:
                raise ValueError(f"[ERROR] ❌ Block {block.index} exceeds max block size: {block_size} bytes.")

            # ✅ Validate Proof-of-Work
            if not self.blockchain.validate_proof_of_work(block):
                raise ValueError(f"[ERROR] ❌ Block {block.index} does not meet Proof-of-Work requirements.")

            # ✅ Validate timestamp to prevent future-dated blocks
            current_time = time.time()
            if not (current_time - Constants.MAX_TIME_DRIFT <= block.timestamp <= current_time + Constants.MAX_TIME_DRIFT):
                raise ValueError(f"[ERROR] ❌ Block {block.index} timestamp invalid. (Possible future block)")

            # ✅ Validate all transactions in the block
            for tx in block.transactions:
                if not self.transaction_manager.validate_transaction(tx):
                    logging.warning(f"[WARNING] ❌ Skipping invalid transaction {tx.tx_id} in block {block.index}")
                    continue  # ✅ Skip invalid transactions instead of rejecting the entire block

            logging.info(f"[STORAGE] ✅ Block {block.index} successfully validated.")
            return True

        except Exception as e:
            logging.error(f"[ERROR] ❌ Block validation failed: {e}")
            return False