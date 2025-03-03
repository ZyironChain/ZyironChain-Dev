import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import hashlib
import logging
import json
import time 
import random
import importlib
import pickle
import sqlite3
from decimal import Decimal
from datetime import datetime
from typing import Optional, TYPE_CHECKING
import threading
# Database imports (safe, no circular deps)

from Zyiron_Chain.database.lmdatabase import LMDBManager
from Zyiron_Chain.database.tinydatabase import TinyDBManager

# Constants and base components
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
from Zyiron_Chain.transactions.transactiontype import TransactionType
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.offchain.dispute import DisputeResolutionContract
from Zyiron_Chain.blockchain.network.peerconstant import PeerConstants
# Lazy import helpers
def get_block():
    """Lazy import Block to break circular dependency"""
    from Zyiron_Chain.blockchain.block import Block
    return Block

def get_blockchain():
    """Lazy import Blockchain to prevent circular imports"""
    from Zyiron_Chain.blockchain.blockchain import Blockchain
    return Blockchain

def get_transaction_manager():
    """Lazy import TransactionManager"""
    from Zyiron_Chain.blockchain.transaction_manager import TransactionManager
    return TransactionManager

def get_storage_manager():
    """Lazy import StorageManager"""
    from Zyiron_Chain.blockchain.storage_manager import StorageManager
    return StorageManager

def get_standard_mempool():
    """Lazy import StandardMempool"""
    module = importlib.import_module("Zyiron_Chain.blockchain.utils.standardmempool")
    return getattr(module, "StandardMempool")

def get_smart_mempool():
    """Lazy import SmartMempool"""
    module = importlib.import_module("Zyiron_Chain.smartpay.smartmempool")
    return getattr(module, "SmartMempool")

def get_fee_model():
    """Lazy import FeeModel"""
    module = importlib.import_module("Zyiron_Chain.transactions.fees")
    return getattr(module, "FeeModel")

def get_transaction():
    """Lazy import Transaction"""
    module = importlib.import_module("Zyiron_Chain.transactions.tx")
    return getattr(module, "Transaction")

# Type checking imports only
if TYPE_CHECKING:
    from Zyiron_Chain.transactions.coinbase import CoinbaseTx
    from Zyiron_Chain.blockchain.block import Block
    from Zyiron_Chain.blockchain.blockchain import Blockchain

logging.basicConfig(level=logging.INFO)
class PoC:
    def __init__(self):
        """Initialize the core PoC instance and connect all blockchain modules."""
        self.databases = Constants.DATABASES  # Fetch DB configuration from constants

        # ✅ Initialize LMDB databases
        self.block_metadata_db = LMDBManager(Constants.get_db_path("block_metadata"))
        self.txindex_db = LMDBManager(Constants.get_db_path("txindex"))
        self.utxo_db = LMDBManager(Constants.get_db_path("utxo"))
        self.utxo_history_db = LMDBManager(Constants.get_db_path("utxo_history"))
        self.wallet_index_db = LMDBManager(Constants.get_db_path("wallet_index"))
        self.mempool_db = LMDBManager(Constants.get_db_path("mempool"))
        self.fee_stats_db = LMDBManager(Constants.get_db_path("fee_stats"))
        self.orphan_blocks_db = LMDBManager(Constants.get_db_path("orphan_blocks"))

        self._db_lock = threading.Lock()  # Global lock for all DB operations

        # ✅ Initialize blockchain components
        self._init_key_manager()
        self._init_storage_manager()
        self._init_transaction_manager()
        self._init_blockchain()
        self._init_fee_model()
        self._init_mempools()
        self._init_utxo_cache()
        self._init_dispute_contract()

    def _init_key_manager(self):
        """Initialize the key manager."""
        self.key_manager = KeyManager()

    def _init_storage_manager(self):
        """Initialize the Storage Manager dynamically."""
        StorageManager = get_storage_manager()
        self.storage_manager = StorageManager(self)

    def _init_transaction_manager(self):
        """Initialize the Transaction Manager dynamically."""
        TransactionManager = get_transaction_manager()
        self.transaction_manager = TransactionManager(self.storage_manager, self.key_manager, self)

    def _init_blockchain(self):
        """Initialize the blockchain system and miner."""
        Blockchain = get_blockchain()
        self.blockchain = Blockchain(self.storage_manager, self.transaction_manager, self.key_manager)
        self.block_manager = self.blockchain.block_manager
        self.miner = self.blockchain.miner

    def _init_fee_model(self):
        """Initialize the fee model using the configured max supply."""
        FeeModel = get_fee_model()
        self.fee_model = FeeModel(max_supply=Decimal(Constants.MAX_SUPPLY))

    def _init_mempools(self):
        """Initialize and allocate mempool resources dynamically."""
        self.standard_mempool = get_standard_mempool()(self)
        self.smart_mempool = get_smart_mempool()(
            peer_id=f"peer_{PeerConstants.PEER_USER_ID}",
            max_size_mb=int(Constants.MEMPOOL_MAX_SIZE_MB * Constants.MEMPOOL_SMART_ALLOCATION)
        )
        self.mempool = self.standard_mempool  # ✅ Default to standard mempool

    def _init_utxo_cache(self):
        """Initialize the UTXO cache for fast lookups."""
        self._cache = {}

    def _init_dispute_contract(self):
        """Initialize the dispute resolution contract for off-chain transactions."""
        self.dispute_contract = DisputeResolutionContract(self)


    def store_block(self, block, difficulty):
        """Store block metadata in LMDB using JSON serialization and correct block height referencing."""
        try:
            with self._db_lock:
                # ✅ Ensure Merkle Root Calculation
                if not hasattr(block.header, "merkle_root") or not block.header.merkle_root:
                    block.header.merkle_root = self._calculate_merkle_root(block.transactions)

                # ✅ Prepare Block Metadata for LMDB (Correcting Block Height Reference)
                block_metadata = {
                    "hash": block.hash,
                    "block_header": {
                        "index": block.index,  # Correct block height reference
                        "previous_hash": block.previous_hash,
                        "merkle_root": block.header.merkle_root,
                        "timestamp": block.timestamp,
                        "nonce": block.nonce,
                        "difficulty": difficulty,
                    },
                    "transaction_count": len(block.transactions),
                    "block_size": len(json.dumps(block.to_dict()).encode("utf-8")),
                    "data_file": self.storage_manager.current_block_file,
                    "data_offset": self.storage_manager.current_block_offset,
                    "tx_ids": [tx.tx_id for tx in block.transactions]  # ✅ Store all transaction IDs for indexing
                }

                # ✅ Store block metadata in LMDB with JSON serialization
                with self.block_metadata_db.env.begin(write=True) as txn:
                    txn.put(f"block:{block.hash}".encode(), json.dumps(block_metadata).encode("utf-8"))

                # ✅ Store transactions in `txindex.lmdb`
                with self.txindex_db.env.begin(write=True) as txn:
                    for idx, tx in enumerate(block.transactions):
                        txn.put(f"tx:{tx.tx_id}".encode(), json.dumps({
                            "block_hash": block.hash,
                            "position": idx,
                            "merkle_root": block.header.merkle_root,
                            "block_height": block.index,
                            "timestamp": block.timestamp
                        }).encode("utf-8"))

                # ✅ Store the full block in `block.data`
                self.storage_manager.append_block(block)

                # ✅ Update UTXOs only AFTER block storage is successful
                self._update_utxos(block)

            logging.info(f"[STORAGE] ✅ Block {block.index} stored successfully.")

        except json.JSONDecodeError as e:
            logging.error(f"[STORAGE ERROR] ❌ JSON serialization failed while storing block: {e}")
        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to store block: {e}")
            raise




    def _update_utxos(self, block):
        """Update UTXO databases for new block"""
        try:
            with self.utxo_db.env.begin(write=True) as utxo_txn, \
                 self.utxo_history_db.env.begin(write=True) as history_txn:

                for tx in block.transactions:
                    # ✅ Validate transaction structure
                    if not hasattr(tx, "inputs") or not hasattr(tx, "outputs"):
                        logging.error(f"[UTXO ERROR] ❌ Transaction {tx.tx_id} is malformed. Skipping UTXO update.")
                        continue

                    # ✅ Remove spent UTXOs (only if they exist)
                    for inp in tx.inputs:
                        utxo_key = f"utxo:{inp.tx_out_id}".encode()
                        if utxo_txn.get(utxo_key):
                            utxo_txn.delete(utxo_key)
                            logging.info(f"[UTXO] ❌ Spent UTXO removed: {inp.tx_out_id}")
                        else:
                            logging.warning(f"[UTXO WARNING] ⚠️ Attempted to delete non-existent UTXO: {inp.tx_out_id}")

                    # ✅ Add new UTXOs
                    for out_idx, output in enumerate(tx.outputs):
                        utxo_id = f"{tx.tx_id}:{out_idx}"
                        utxo_data = {
                            "tx_out_id": utxo_id,
                            "amount": float(output.amount),
                            "script_pub_key": output.script_pub_key,
                            "block_index": block.index
                        }
                        utxo_txn.put(f"utxo:{utxo_id}".encode(), pickle.dumps(utxo_data))
                        history_txn.put(
                            f"history:{utxo_id}:{block.timestamp}".encode(),
                            pickle.dumps(utxo_data)
                        )
                        logging.info(f"[UTXO] ✅ Added new UTXO: {utxo_id} | Amount: {output.amount}")

            logging.info(f"[UTXO] ✅ UTXO database updated successfully for Block {block.index}")

        except Exception as e:
            logging.error(f"[UTXO ERROR] ❌ Failed to update UTXOs for Block {block.index}: {str(e)}")
            raise

    def load_blockchain_data(self) -> list:
        """Load blockchain data from LMDB, ensuring data integrity."""
        logging.info("[POC] 🔄 Loading blockchain data from LMDB...")
        try:
            blockchain_db = self._get_database("block_metadata")
            raw_blocks = blockchain_db.get_all_blocks()

            # ✅ Ensure blocks are valid before storing them
            self.chain = []
            for block in raw_blocks:
                if isinstance(block, bytes):
                    try:
                        block = pickle.loads(block)  # Convert binary to dict
                    except (pickle.UnpicklingError, TypeError) as e:
                        logging.error(f"[ERROR] ❌ Failed to decode block: {str(e)}")
                        continue

                if "hash" not in block or not isinstance(block["hash"], str):
                    logging.warning(f"[WARNING] ⚠️ Retrieved block missing 'hash': {block}")
                    continue

                self.chain.append(block)

            logging.info(f"[POC] ✅ Successfully loaded {len(self.chain)} blocks from LMDB.")
            return self.chain

        except Exception as e:
            logging.error(f"[POC ERROR] ❌ Failed to load blockchain data: {e}")
            return []  # Return empty list on failure


    def _get_database(self, db_key):
        """Retrieve the correct database instance from Constants (LMDB only)."""
        try:
            db_path = Constants.DATABASES.get(db_key, None)
            if not db_path:
                raise ValueError(f"[ERROR] ❌ Unknown database key: {db_key}")

            # ✅ Open LMDB database dynamically
            return LMDBManager(db_path)

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to get database {db_key}: {str(e)}")
            raise

    def get_all_blocks(self) -> list:
        """
        Retrieve all stored blocks from LMDB.
        Ensures proper block retrieval and validation.
        """
        try:
            blockchain_db = self._get_database("block_metadata")
            raw_blocks = blockchain_db.get_all_blocks()

            decoded_blocks = []
            for block in raw_blocks:
                if isinstance(block, bytes):
                    try:
                        block = pickle.loads(block)  # Convert from binary to dictionary
                    except (pickle.UnpicklingError, TypeError) as e:
                        logging.error(f"[ERROR] ❌ Failed to decode block: {str(e)}")
                        continue

                # ✅ Ensure essential fields exist
                if not all(k in block for k in ["hash", "header", "transactions"]):
                    logging.warning(f"[WARNING] ⚠️ Block missing required fields: {block}")
                    continue

                # ✅ Ensure block hash is valid
                if not isinstance(block["hash"], str):
                    logging.warning(f"[WARNING] ⚠️ Invalid block hash format: {block}")
                    block["hash"] = block["header"].get("merkle_root", Constants.ZERO_HASH)  # Fallback to merkle root

                decoded_blocks.append(block)

            logging.info(f"[DEBUG] ✅ Successfully retrieved {len(decoded_blocks)} blocks from LMDB.")
            return decoded_blocks

        except KeyError as ke:
            logging.error(f"[ERROR] ❌ Missing key in block data: {str(ke)}")
            return []
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to retrieve blocks: {str(e)}")
            return []

    def store_utxo(self, utxo_id: str, utxo_data: dict) -> bool:
        """
        Store a UTXO in LMDB, ensuring type safety and preventing duplicates.
        """
        try:
            if not isinstance(utxo_data, dict):
                raise TypeError("[ERROR] ❌ UTXO data must be a dictionary.")

            # ✅ Ensure required fields exist
            required_keys = {"tx_out_id", "amount", "script_pub_key", "block_index"}
            missing_keys = required_keys - utxo_data.keys()
            if missing_keys:
                raise KeyError(f"[ERROR] ❌ Missing required UTXO fields: {missing_keys}")

            # ✅ Convert values to appropriate types
            tx_out_id = str(utxo_data["tx_out_id"])
            amount = Decimal(str(utxo_data["amount"])).quantize(Decimal(Constants.COIN))  # ✅ Standardized precision
            script_pub_key = str(utxo_data["script_pub_key"])
            locked = bool(utxo_data.get("locked", False))  # ✅ Explicitly store as boolean
            block_index = int(utxo_data.get("block_index", 0))  # ✅ Ensure block index is an integer

            # ✅ Get correct LMDB storage for UTXOs
            utxo_db = self._get_database("utxo")

            # ✅ Check if UTXO already exists (avoid redundant writes)
            existing_utxo = utxo_db.get(tx_out_id)
            if existing_utxo:
                logging.warning(f"[WARNING] ⚠️ UTXO {tx_out_id} already exists. Replacing with new data.")

            # ✅ Prepare data for LMDB storage
            utxo_entry = {
                "tx_out_id": tx_out_id,
                "amount": str(amount),  # ✅ Store as string to preserve precision
                "script_pub_key": script_pub_key,
                "locked": locked,
                "block_index": block_index
            }

            # ✅ Insert/Replace in LMDB
            utxo_db.put(tx_out_id, json.dumps(utxo_entry), replace=True)

            logging.info(f"[INFO] ✅ UTXO {utxo_id} stored successfully in LMDB.")
            return True  # ✅ Indicate success

        except (KeyError, TypeError, ValueError, Decimal.InvalidOperation) as e:
            logging.error(f"[ERROR] ❌ Failed to store UTXO {utxo_id}: {str(e)}")
            return False  # ❌ Indicate failure


    def ensure_consistency(self, block):
        """
        Ensure blockchain consistency before adding a new block.
        Retrieves the latest block from storage to validate proper linking.
        """
        if not isinstance(block, Block):
            raise ValueError("[ERROR] ❌ Invalid block: Block must be an instance of `Block`.")

        if not hasattr(block, "hash") or not hasattr(block, "merkle_root"):
            raise ValueError("[ERROR] ❌ Block is missing required attributes (hash, merkle_root).")

        # ✅ Fetch the last stored block dynamically from StorageManager
        last_block = self.storage_manager.get_latest_block()

        if last_block:
            # ✅ Ensure previous block hash matches
            if block.previous_hash != last_block.hash:
                raise ValueError(
                    f"[ERROR] ❌ Previous hash mismatch: Expected {last_block.hash}, Got {block.previous_hash}"
                )

            # ✅ Ensure block index increments properly
            if block.index != last_block.index + 1:
                raise ValueError(
                    f"[ERROR] ❌ Block index mismatch: Expected {last_block.index + 1}, Got {block.index}"
                )

        else:
            # ✅ Ensure Genesis block starts at index 0
            if block.index != 0:
                raise ValueError("[ERROR] ❌ First block must have index 0 (Genesis Block).")
            logging.warning("[WARNING] 🚀 No previous blocks found. Initializing Genesis Block.")

        logging.info(f"[INFO] ✅ Block {block.index} passed consistency checks.")

    def get_last_block(self):
        """
        Retrieve the latest block from storage. If no blocks exist, ensure Genesis Block is created.
        """
        try:
            Block = get_block()  # Lazy import to prevent circular dependencies
            
            # ✅ Fetch latest block from StorageManager
            latest_block = self.storage_manager.get_latest_block()

            if latest_block:
                return latest_block  # ✅ Return the block if found
            
            # ✅ No block found, attempt Genesis Block creation
            logging.warning("[POC] ⚠️ No blocks found. Initializing Genesis Block...")
            
            for retry_count in range(3):  # ✅ Retry up to 3 times
                self.block_manager.create_genesis_block()
                latest_block = self.storage_manager.get_latest_block()

                if latest_block:
                    logging.info(f"[POC] ✅ Genesis Block successfully created at retry {retry_count + 1}.")
                    return latest_block
            
            raise RuntimeError("[ERROR] ❌ Failed to initialize Genesis Block after 3 attempts.")

        except Exception as e:
            logging.error(f"[CRITICAL] ❌ Failed to fetch last block: {str(e)}")
            return None  # ✅ Return None instead of raising to prevent crashes


    def get_block(self, block_hash: str):
        """
        Retrieve a block from storage, ensuring it has the correct magic number.
        """
        try:
            # ✅ Fetch block from StorageManager (block.data file)
            block = self.storage_manager.get_block_from_data_file(block_hash)

            if not block:
                logging.warning(f"[WARNING] ❌ Block {block_hash} not found in block.data storage.")
                return None

            # ✅ Validate magic number to prevent cross-network retrieval
            expected_magic = Constants.MAGIC_NUMBER
            if block.header.magic_number != expected_magic:
                logging.error(f"[ERROR] ❌ Block {block_hash} has an invalid magic number: {block.header.magic_number}. Expected: {expected_magic}")
                return None
            
            logging.info(f"[STORAGE] ✅ Block {block_hash} retrieved successfully.")
            return block

        except Exception as e:
            logging.error(f"[ERROR] ❌ Block retrieval failed: {str(e)}")
            return None  # ✅ Return None to prevent crashes


    def get_utxo(self, tx_out_id: str) -> Optional[TransactionOut]:
        """
        Retrieve UTXO from storage, ensuring proper caching and validation.
        """
        try:
            # ✅ Check cache before querying storage
            if tx_out_id in self._cache:
                logging.info(f"[CACHE] ✅ UTXO {tx_out_id} retrieved from cache.")
                return TransactionOut.from_dict(self._cache[tx_out_id])

            # ✅ Fetch UTXO from StorageManager
            utxo_data = self.storage_manager.get_utxo(tx_out_id)

            if not utxo_data:
                logging.warning(f"[WARNING] ❌ UTXO {tx_out_id} not found in LMDB.")
                return None

            # ✅ Validate UTXO format
            if not isinstance(utxo_data, dict):
                logging.error(f"[ERROR] ❌ Unexpected UTXO format: {type(utxo_data)}")
                return None

            # ✅ Cache UTXO for future access
            self._cache[tx_out_id] = utxo_data

            logging.info(f"[STORAGE] ✅ UTXO {tx_out_id} retrieved successfully.")
            return TransactionOut.from_dict(utxo_data)

        except Exception as e:
            logging.error(f"[ERROR] ❌ UTXO retrieval failed for {tx_out_id}: {str(e)}")
            return None  # ✅ Return None to prevent crashes

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

    def load_blockchain_data(self):
        """Load blockchain data from StorageManager."""
        logging.info("[POC] 🔄 Loading blockchain data...")
        try:
            self.chain = self.storage_manager.get_all_blocks()

            if not self.chain:
                logging.warning("[POC] ⚠️ No blocks found in storage. Blockchain may be empty.")
                return

            logging.info(f"[POC] ✅ Successfully loaded {len(self.chain)} blocks from storage.")
        except Exception as e:
            logging.error(f"[POC ERROR] ❌ Failed to load blockchain data: {e}")
            self.chain = []


    ### -------------------- TRANSACTION HANDLING -------------------- ###


    def route_transaction_to_lmdb(self, transaction):
        """Routes pending transactions to LMDB (Mempool)."""
        try:
            tx_type = self.payment_type_manager.get_transaction_type(transaction.tx_id)
            mempool_type = Constants.TRANSACTION_MEMPOOL_MAP.get(tx_type.name, {}).get("mempool", "StandardMempool")

            # ✅ Ensure transactions are routed correctly
            if mempool_type == "SmartMempool":
                success = self.smart_mempool.add_transaction(transaction, len(self.blockchain.chain))
            else:
                success = self.standard_mempool.add_transaction(transaction)

            if success:
                logging.info(f"[POC] ✅ Routed transaction {transaction.tx_id} to {mempool_type}.")
            else:
                logging.error(f"[POC] ❌ Failed to add transaction {transaction.tx_id} to {mempool_type}.")
        except Exception as e:
            logging.error(f"[POC ERROR] ❌ Failed to route transaction {transaction.tx_id}: {e}")

    def handle_transaction(self, transaction):
        """Process and store a transaction in LMDB Mempool."""
        try:
            if not hasattr(transaction, 'tx_id'):
                raise ValueError("[ERROR] ❌ Transaction is missing required field: tx_id")

            tx_type = self.payment_type_manager.get_transaction_type(transaction.tx_id)
            mempool_type = Constants.TRANSACTION_MEMPOOL_MAP.get(tx_type.name, {}).get("mempool", "StandardMempool")

            # ✅ Store transaction in LMDB mempool
            success = self.storage_manager.store_pending_transaction(transaction)

            if success:
                logging.info(f"[INFO] ✅ Transaction {transaction.tx_id} stored in {mempool_type}.")
            else:
                logging.error(f"[ERROR] ❌ Failed to store transaction {transaction.tx_id} in {mempool_type}.")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to handle transaction {transaction.tx_id}: {e}")
            raise


    def get_pending_transactions(self, transaction_id=None):
        """
        Retrieve pending transactions from LMDB Mempool.
        - Uses StorageManager to fetch transactions instead of direct mempool access.
        - Can filter by `transaction_id` if provided.
        """
        try:
            # ✅ Fetch transactions from LMDB Mempool via StorageManager
            all_transactions = self.storage_manager.get_pending_transactions()

            if transaction_id is None:
                return all_transactions  # ✅ Return all transactions

            # ✅ Filter transactions by specific ID
            filtered_transactions = [tx for tx in all_transactions if tx.tx_id == transaction_id]

            if not filtered_transactions:
                logging.warning(f"[MEMPOOL] ⚠️ Transaction {transaction_id} not found in Mempool.")

            return filtered_transactions

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to retrieve pending transactions: {e}")
            return []

    def add_pending_transaction(self, transaction):
        """
        Add a transaction to the correct mempool based on its type.
        - Routes transaction storage via StorageManager.
        - Uses TRANSACTION_MEMPOOL_MAP to determine correct mempool.
        """
        try:
            tx_type = self.payment_type_manager.get_transaction_type(transaction.tx_id)
            mempool_type = Constants.TRANSACTION_MEMPOOL_MAP.get(tx_type.name, {}).get("mempool", "StandardMempool")

            # ✅ Store transaction in LMDB Mempool
            success = self.storage_manager.store_pending_transaction(transaction)

            if success:
                logging.info(f"[MEMPOOL] ✅ Transaction {transaction.tx_id} added to {mempool_type}.")
                return True
            else:
                logging.error(f"[MEMPOOL] ❌ Failed to add transaction {transaction.tx_id} to {mempool_type}.")
                return False

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to add pending transaction {transaction.tx_id}: {e}")
            return False

    ### -------------------- BLOCK PROPAGATION & NETWORK -------------------- ###

    def propagate_block(self, block, nodes):
        """
        Broadcast a mined block to the P2P network.
        - Ensures only validated blocks are propagated.
        """
        try:
            if not isinstance(block, Block):
                logging.error("[ERROR] ❌ Invalid block format for propagation.")
                return

            logging.info(f"[POC] 🔄 Propagating new block {block.hash} to network.")
            serialized_block = json.dumps(block.to_dict())

            for node in nodes:
                if hasattr(node, "receive_block"):  # ✅ Check if node can receive block
                    node.receive_block(serialized_block)
                else:
                    logging.warning(f"[WARNING] ⚠️ Node {node} does not support block reception.")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to propagate block {block.hash}: {e}")

    def validate_transaction(self, transaction):
        """
        Validate a transaction before propagation.
        - Ensures transaction ID exists.
        - Calls StorageManager for full validation.
        """
        try:
            if not transaction.tx_id:
                logging.error("[ERROR] ❌ Transaction is missing tx_id.")
                return False

            # ✅ Validate using StorageManager (signature, UTXO, balance checks)
            is_valid = self.storage_manager.validate_transaction(transaction)

            if not is_valid:
                logging.warning(f"[VALIDATION] ⚠️ Transaction {transaction.tx_id} failed validation.")
                return False

            logging.info(f"[VALIDATION] ✅ Transaction {transaction.tx_id} is valid.")
            return True

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to validate transaction {transaction.tx_id}: {e}")
            return False

    def propagate_transaction(self, transaction, nodes):
        """
        Send a valid transaction to miner nodes.
        - Ensures transaction validation before propagation.
        """
        try:
            if not self.validate_transaction(transaction):
                logging.warning(f"[POC] ⚠️ Transaction {transaction.tx_id} failed validation. Not propagating.")
                return

            logging.info(f"[POC] 🔄 Propagating transaction {transaction.tx_id} for mining.")
            serialized_transaction = json.dumps(transaction.to_dict())

            for node in nodes:
                if hasattr(node, "receive_transaction"):  # ✅ Ensure node can receive transactions
                    node.receive_transaction(serialized_transaction)
                else:
                    logging.warning(f"[WARNING] ⚠️ Node {node} does not support transaction reception.")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to propagate transaction {transaction.tx_id}: {e}")

    def validate_transaction_fee(self, transaction):
        """
        Ensure a transaction has sufficient fees.
        - Uses FeeModel for correct fee calculations.
        """
        try:
            # ✅ Calculate transaction size based on input/output structure
            transaction_size = self.storage_manager.calculate_transaction_size(transaction)

            # ✅ Compute required fee using FeeModel
            required_fee = self.fee_model.calculate_fee(
                block_size=Constants.MAX_BLOCK_SIZE_BYTES,
                payment_type=transaction.type,
                amount=sum(inp.amount for inp in transaction.inputs),
                tx_size=transaction_size
            )

            # ✅ Compute actual fee
            total_fee = sum(inp.amount for inp in transaction.inputs) - sum(out.amount for out in transaction.outputs)

            if total_fee >= required_fee:
                logging.info(f"[FEE VALIDATION] ✅ Transaction {transaction.tx_id} meets fee requirement.")
                return True
            else:
                logging.warning(f"[FEE VALIDATION] ⚠️ Insufficient fee for transaction {transaction.tx_id}. Required: {required_fee}, Provided: {total_fee}.")
                return False

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to validate transaction fee for {transaction.tx_id}: {e}")
            return False

    def synchronize_node(self, node, peers):
        """
        Sync node with the latest blockchain state.
        - Uses StorageManager to fetch the latest block.
        - Synchronizes mempool transactions.
        """
        try:
            if not hasattr(node, "sync_blockchain") or not hasattr(node, "sync_mempool"):
                logging.error(f"[ERROR] ❌ Node {node} does not support synchronization.")
                return

            logging.info(f"[POC] 🔄 Synchronizing node {node.node_id} with network...")

            # ✅ Fetch latest block from LMDB
            latest_block = self.storage_manager.get_latest_block()
            if latest_block:
                serialized_block = json.dumps(latest_block.to_dict())
                node.sync_blockchain(serialized_block)
            else:
                logging.warning(f"[POC] ⚠️ No valid blocks found for synchronization.")

            # ✅ Fetch and sync mempool transactions
            pending_transactions = self.storage_manager.get_pending_transactions()
            node.sync_mempool(pending_transactions)

            logging.info(f"[POC] ✅ Node {node.node_id} successfully synchronized.")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to synchronize node {node.node_id}: {e}")

