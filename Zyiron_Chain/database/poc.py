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

# Database imports (safe, no circular deps)
from Zyiron_Chain.database.unqlitedatabase import BlockchainUnqliteDB
from Zyiron_Chain.database.sqlitedatabase import SQLiteDB
from Zyiron_Chain.database.duckdatabase import AnalyticsNetworkDB
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
        """Initialize PoC and databases dynamically based on Constants"""
        # Initialize databases first (no dependencies)
        self.databases = Constants.DATABASES
        self.unqlite_db = self._initialize_database("blockchain")
        self.sqlite_db = self._initialize_database("utxo")
        self.duckdb_analytics = self._initialize_database("analytics")
        self.lmdb_manager = self._initialize_database("mempool")
        self.tinydb_manager = self._initialize_database("tinydb")

        # Lazy initialize components with dependencies
        self._init_key_manager()
        self._init_storage_manager()
        self._init_transaction_manager()
        self._init_blockchain()
        self._init_fee_model()
        self._init_mempools()
        self._init_utxo_cache()
        self._init_dispute_contract()

    def _init_key_manager(self):
        """Initialize KeyManager"""
        self.key_manager = KeyManager()

    def _init_storage_manager(self):
        """Initialize StorageManager with lazy imports"""
        StorageManager = get_storage_manager()
        self.storage_manager = StorageManager(self)

    def _init_transaction_manager(self):
        """Initialize TransactionManager with lazy imports"""
        TransactionManager = get_transaction_manager()
        self.transaction_manager = TransactionManager(
            self.storage_manager,
            self.key_manager,
            self
        )

    def _init_blockchain(self):
        """Initialize Blockchain component last"""
        Blockchain = get_blockchain()
        self.blockchain = Blockchain(
            storage_manager=self.storage_manager,
            transaction_manager=self.transaction_manager,
            key_manager=self.key_manager
        )
        self.block_manager = self.blockchain.block_manager
        self.miner = self.blockchain.miner

    def _init_fee_model(self):
        """Initialize FeeModel with lazy loading"""
        FeeModel = get_fee_model()
        self.fee_model = FeeModel(max_supply=Decimal(Constants.MAX_SUPPLY))

    def _init_mempools(self):
        """Initialize mempools with lazy imports"""
        # Standard Mempool
        self.standard_mempool = get_standard_mempool()(self)
        
        # Smart Mempool - use PEER_USER_ID from PeerConstants
        self.smart_mempool = get_smart_mempool()(
            peer_id=f"peer_{PeerConstants.PEER_USER_ID}",  # Use dynamic peer_id
            max_size_mb=int(Constants.MEMPOOL_MAX_SIZE_MB * Constants.MEMPOOL_SMART_ALLOCATION)
        )
        
        self.mempool = self.standard_mempool

    def _init_utxo_cache(self):
        """Initialize UTXO cache"""
        self._cache = {}

    def _init_dispute_contract(self):
        """Initialize Dispute Resolution Contract"""
        self.dispute_contract = DisputeResolutionContract(self)

    # Keep all original database methods unchanged
    def _initialize_database(self, db_key):
        """Helper function to initialize databases dynamically based on Constants"""
        db_type = self.databases.get(db_key, "Unknown")

        if db_type == "UnQLite":
            return BlockchainUnqliteDB()
        elif db_type == "SQLite":
            return SQLiteDB()
        elif db_type == "DuckDB":
            return AnalyticsNetworkDB()
        elif db_type == "LMDB":
            return LMDBManager()
        elif db_type == "TinyDB":
            return TinyDBManager()
        else:
            raise ValueError(f"[ERROR] Unsupported database type: {db_type}")



    def store_block(self, block, difficulty):
        """
        Store a block in the PoC layer with atomic transactions to prevent inconsistencies.
        Ensures block storage routes correctly based on Constants.DATABASES.
        """
        try:
            Block = get_block()  # Use lazy import helper

            if isinstance(block, dict):
                block = Block.from_dict(block)

            block_data = block.to_dict()
            block_header = block.header.to_dict()
            transactions = [tx.to_dict() for tx in block.transactions]
            size = sum(len(json.dumps(tx)) for tx in transactions)

            blockchain_db = self._get_database("blockchain")
            mempool_db = self._get_database("mempool")

            try:
                blockchain_db.begin_transaction()
                if mempool_db:
                    mempool_db.begin_transaction()

                blockchain_db.add_block(block_data['hash'], block_header, transactions, size, difficulty)
                
                if mempool_db:
                    mempool_db.add_block(block_data['hash'], block_header, transactions, size, difficulty)

                blockchain_db.commit()
                if mempool_db:
                    mempool_db.commit()

                logging.info(f"[INFO] Block {block.index} stored successfully in PoC.")
                
                # Clear cache after successful storage
                if block_data['hash'] in self._cache:
                    del self._cache[block_data['hash']]

            except Exception as inner_e:
                blockchain_db.rollback()
                if mempool_db:
                    mempool_db.rollback()
                raise

        except Exception as e:
            logging.error(f"[ERROR] Block storage failed: {e}")
            raise


    def _get_database(self, db_key):
        """Helper function to retrieve the correct database instance from Constants."""
        db_type = Constants.DATABASES.get(db_key, "Unknown")

        if db_type == "UnQLite":
            return self.unqlite_db
        elif db_type == "SQLite":
            return self.sqlite_db
        elif db_type == "DuckDB":
            return self.duckdb_analytics
        elif db_type == "LMDB":
            return self.lmdb_manager
        elif db_type == "TinyDB":
            return self.tinydb_manager
        else:
            raise ValueError(f"[ERROR] Unsupported database type: {db_type}")







    def get_all_blocks(self):
        """
        Retrieve all stored blocks from the configured blockchain storage.
        Ensures proper block retrieval and validation based on Constants.DATABASES.
        """
        try:
            blockchain_db = self._get_database("blockchain")  # ✅ Dynamically select storage
            raw_blocks = blockchain_db.get_all_blocks()  # ✅ Retrieve blocks from correct storage

            decoded_blocks = []
            for block in raw_blocks:
                if isinstance(block, bytes):
                    try:
                        block = pickle.loads(block)  # ✅ Convert from binary to dictionary
                    except (pickle.UnpicklingError, TypeError) as e:
                        logging.error(f"[ERROR] Failed to decode block: {str(e)}")
                        continue

                # ✅ Ensure block integrity
                if "hash" not in block or not isinstance(block["hash"], str):
                    logging.warning(f"[WARNING] Retrieved block missing 'hash' key: {block}")
                    block["hash"] = block["header"].get("merkle_root", Constants.ZERO_HASH)  # Fallback to merkle root

                decoded_blocks.append(block)

            logging.info(f"[DEBUG] Successfully retrieved {len(decoded_blocks)} blocks from {blockchain_db.__class__.__name__}.")
            return decoded_blocks

        except KeyError as ke:
            logging.error(f"[ERROR] Missing key in block data: {str(ke)}")
            return []
        except Exception as e:
            logging.error(f"[ERROR] Failed to retrieve blocks: {str(e)}")
            return []


    def store_utxo(self, utxo_id, utxo_data):
        """
        Store a UTXO in the correct database as defined in Constants.
        Ensures type safety, prevents duplicates, and dynamically selects the correct storage.
        """
        try:
            if not isinstance(utxo_data, dict):
                raise TypeError("[ERROR] UTXO data must be a dictionary.")

            required_keys = ["tx_out_id", "amount", "script_pub_key"]
            for key in required_keys:
                if key not in utxo_data:
                    raise KeyError(f"[ERROR] Missing required UTXO field: {key}")

            # ✅ Convert types for storage
            tx_out_id = str(utxo_data["tx_out_id"])
            amount = float(utxo_data["amount"])  # ✅ Convert Decimal to float
            script_pub_key = str(utxo_data["script_pub_key"])
            locked = int(bool(utxo_data.get("locked", False)))  # ✅ Convert boolean to int (0 or 1)
            block_index = int(utxo_data.get("block_index", 0))  # ✅ Ensure block index is an integer

            # ✅ Get correct UTXO storage from Constants
            utxo_db = self._get_database("utxo")

            # ✅ Check if UTXO already exists
            existing_utxo = utxo_db.get_utxo(tx_out_id)
            if existing_utxo:
                logging.warning(f"[WARNING] UTXO {tx_out_id} already exists. Replacing with new data.")
                utxo_db.delete_utxo(tx_out_id)  # ✅ Remove old UTXO before inserting a new one

            # ✅ Store UTXO in the correct database
            utxo_db.insert_utxo(
                utxo_id=utxo_id,
                tx_out_id=tx_out_id,
                amount=amount,
                script_pub_key=script_pub_key,
                locked=locked,
                block_index=block_index
            )

            logging.info(f"[INFO] UTXO {utxo_id} successfully stored in {utxo_db.__class__.__name__}.")
            return True  # ✅ Indicate success

        except (KeyError, TypeError, ValueError) as e:
            logging.error(f"[ERROR] Failed to store UTXO {utxo_id}: {e}")
            return False  # ✅ Indicate failure






    def ensure_consistency(self, block):
        """
        Ensure blockchain consistency before adding a new block.
        Dynamically retrieves the latest block from the correct blockchain storage.
        :param block: The block to check.
        :raises ValueError: If the block does not meet consistency requirements.
        """
        if not block:
            raise ValueError("[ERROR] Invalid block: Block data is missing.")

        if not block.hash or not block.merkle_root:
            raise ValueError("[ERROR] Block hash or Merkle root is missing.")

        # ✅ Fetch the last block dynamically from the correct storage backend
        blockchain_db = self._get_database("blockchain")
        last_block_data = blockchain_db.get_last_block()

        if last_block_data:
            last_block = Block.from_dict(last_block_data)

            # ✅ Check for proper block linking
            if block.previous_hash != last_block.hash:
                raise ValueError(
                    f"[ERROR] Previous hash mismatch: Expected {last_block.hash}, Got {block.previous_hash}"
                )

            # ✅ Ensure sequential block indexing
            if block.index != last_block.index + 1:
                raise ValueError(
                    f"[ERROR] Block index mismatch: Expected {last_block.index + 1}, Got {block.index}"
                )

        else:
            # ✅ Ensure genesis block has the correct index
            if block.index != 0:
                raise ValueError("[ERROR] First block must have index 0.")

        logging.info(f"[INFO] Block {block.index} passed consistency checks.")


    def get_last_block(self):
        """Fetch the latest block from the correct blockchain database. Ensure Genesis Block is created if missing."""
        try:
            Block = get_block()  # Use predefined lazy import helper
            blockchain_db = self._get_database("blockchain")
            retry_count = 0
            
            while retry_count < 3:  # Allow retries for concurrent access
                last_block_data = blockchain_db.get_last_block()
                
                if not last_block_data:
                    logging.warning("[POC] No blocks found. Creating Genesis Block...")
                    self.block_manager.create_genesis_block()
                    retry_count += 1
                    continue
                    
                try:
                    return Block.from_dict(last_block_data)
                except KeyError as e:
                    logging.error(f"[ERROR] Corrupted block data: {str(e)}")
                    blockchain_db.rollback()
                    raise ValueError("Invalid block data structure") from e
                    
            raise RuntimeError("[ERROR] Failed to initialize Genesis Block after 3 attempts")

        except Exception as e:
            logging.error(f"[CRITICAL] Failed to fetch last block: {str(e)}")
            raise






    def get_block(self, block_hash: str):
        """Retrieve a block from the correct blockchain database with dynamic routing and error handling."""
        try:
            # ✅ Select the correct blockchain database dynamically
            blockchain_db = self._get_database("blockchain")

            block_data = blockchain_db.get_block(block_hash)
            if not block_data:
                logging.warning(f"[WARNING] Block {block_hash} not found in {Constants.DATABASES['blockchain']}.")
                return None

            return block_data

        except KeyError:
            logging.error(f"[ERROR] Block {block_hash} not found in database.")
            return None
        except Exception as e:
            logging.error(f"[ERROR] Block retrieval failed: {str(e)}")
            return None


                
    def get_utxo(self, tx_out_id: str) -> Optional[TransactionOut]:
        """Retrieve UTXO from the correct database dynamically, ensuring proper format and caching."""
        try:
            # ✅ Use correct UTXO database dynamically
            utxo_db = self._get_database("utxo")

            # ✅ Check cache first for faster retrieval
            if tx_out_id in self._cache:
                return TransactionOut.from_dict(dict(self._cache[tx_out_id]))

            # ✅ Retrieve UTXO from the database
            utxo_data = utxo_db.get_utxo(tx_out_id)

            if utxo_data:
                try:
                    # ✅ Handle different database return types (e.g., JSON, dictionary, sqlite3.Row)
                    if isinstance(utxo_data, sqlite3.Row):
                        utxo_dict = dict(utxo_data)  # ✅ Convert sqlite3.Row to dictionary
                    elif isinstance(utxo_data, str):  
                        utxo_dict = json.loads(utxo_data)  # ✅ Handle JSON-encoded LevelDB data
                    elif isinstance(utxo_data, dict):
                        utxo_dict = utxo_data  # ✅ Already in correct format
                    else:
                        raise TypeError(f"[ERROR] Unexpected UTXO data format: {type(utxo_data)}")

                    # ✅ Cache UTXO for faster lookups
                    self._cache[tx_out_id] = utxo_dict

                    # ✅ Return as a `TransactionOut` object
                    return TransactionOut.from_dict(utxo_dict)

                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    logging.error(f"[ERROR] Failed to process UTXO {tx_out_id}: {e}")
                    return None

            logging.warning(f"[WARNING] UTXO {tx_out_id} not found in {Constants.DATABASES['utxo']}.")
            return None  # ✅ Explicitly return None if UTXO is missing

        except Exception as e:
            logging.error(f"[ERROR] UTXO retrieval failed for {tx_out_id}: {str(e)}")
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
            self.ensure_consistency(block)

            # ✅ Ensure correct block storage database is used
            block_db = self._get_database("blockchain")

            # ✅ Validate block size against max limit
            block_size = sys.getsizeof(json.dumps(block.to_dict()).encode())
            if block_size > Constants.MAX_BLOCK_SIZE_BYTES:
                raise ValueError(f"[ERROR] Block {block.index} exceeds max block size: {block_size} bytes.")

            # ✅ Validate Proof-of-Work against stored difficulty
            if int(block.hash, 16) >= block.header.difficulty:
                raise ValueError(f"[ERROR] Block {block.index} does not meet the difficulty target.")

            # ✅ Validate timestamp to prevent future-dated blocks
            max_time_drift = 7200  # 2 hours
            current_time = time.time()
            if not (current_time - max_time_drift <= block.timestamp <= current_time + max_time_drift):
                raise ValueError(f"[ERROR] Block {block.index} timestamp invalid. (Possible future block)")

            # ✅ Validate all transactions in the block
            for tx in block.transactions:
                if not self.transaction_manager.validate_transaction(tx):
                    raise ValueError(f"[ERROR] Invalid transaction {tx.tx_id} in block {block.index}")

            logging.info(f"[INFO] Block {block.index} successfully validated.")
            return True

        except Exception as e:
            logging.error(f"[ERROR] Block validation failed: {e}")
            return False


    def load_blockchain_data(self):
        """
        Load blockchain data from the database.
        """
        logging.info("[POC] Loading blockchain data...")
        try:
            self.chain = self.unqlite_db.get_all_blocks()
            logging.info(f"[POC] Loaded {len(self.chain)} blocks.")
        except Exception as e:
            logging.error(f"[POC] Error loading blockchain data: {e}")
            self.chain = []

    ### -------------------- TRANSACTION HANDLING -------------------- ###





    def route_block_metadata_to_duckdb(self, block):
        """
        Routes block metadata and analytics to DuckDB.
        """
        try:
            self.duckdb_analytics.add_block_metadata(
                block.hash,
                block.index,
                block.miner_address,
                block.timestamp,
                len(block.transactions),
                block.header["difficulty"]
            )
            logging.info(f"[POC] Routed block metadata for {block.hash} to DuckDB.")
        except Exception as e:
            logging.error(f"[POC ERROR] Failed to route block metadata for {block.hash}: {e}")






    def route_block_to_unqlite(self, block):
        """
        Routes completed blocks to UnQLite (Immutable Blockchain Storage).
        """
        try:
            self.unqlite_db.add_block(
                block.hash, 
                block.header.to_dict(), 
                [tx.to_dict() for tx in block.transactions], 
                len(block.transactions),
                block.header["difficulty"]
            )
            logging.info(f"[POC] Routed block {block.hash} to UnQLite.")
        except Exception as e:
            logging.error(f"[POC ERROR] Failed to route block {block.hash}: {e}")


    def route_transaction_to_lmdb(self, transaction):
        """
        Routes pending transactions to LMDB (Mempool).
        - LMDB handles mempool transaction storage and prioritization.
        """
        try:
            # ✅ Route to the correct database based on transaction type
            tx_type = self.payment_type_manager.get_transaction_type(transaction.tx_id)
            database_type = Constants.TRANSACTION_MEMPOOL_MAP.get(tx_type.name, {}).get("database", "LMDB")

            if database_type == "LMDB":
                self.lmdb_manager.store_pending_transaction(transaction.tx_id, transaction.to_dict())
            else:
                self.unqlite_db.store_transaction(transaction.tx_id, transaction.to_dict())  # ✅ Fallback to UnQLite

            logging.info(f"[POC] Routed transaction {transaction.tx_id} to {database_type}.")
        except Exception as e:
            logging.error(f"[POC ERROR] Failed to route transaction {transaction.tx_id}: {e}")

    def handle_transaction(self, transaction):
        """
        Process and store a transaction.
        :param transaction: The transaction to process.
        """
        try:
            if not hasattr(transaction, 'tx_id'):
                raise ValueError("Transaction is missing required field: tx_id")

            # ✅ Determine correct storage database
            tx_type = self.payment_type_manager.get_transaction_type(transaction.tx_id)
            database_type = Constants.TRANSACTION_MEMPOOL_MAP.get(tx_type.name, {}).get("database", "UnQLite")

            if database_type == "UnQLite":
                self.unqlite_db.store_transaction(transaction.tx_id, transaction.to_dict())
            elif database_type == "LMDB":
                self.lmdb_manager.store_pending_transaction(transaction.tx_id, transaction.to_dict())
            else:
                self.sqlite_db.insert_transaction(transaction.tx_id, transaction.to_dict())  # ✅ Store in SQLite if specified

            logging.info(f"[INFO] Transaction {transaction.tx_id} handled and stored in {database_type}.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to handle transaction: {e}")
            raise
    def get_pending_transactions(self, transaction_id=None):
        """
        Retrieve pending transactions from both Standard and Smart Mempools.
        """
        all_transactions = self.standard_mempool.get_pending_transactions() + self.smart_mempool.get_pending_transactions()

        if transaction_id is None:
            return all_transactions  # ✅ Return all pending transactions
        return [tx for tx in all_transactions if tx.tx_id == transaction_id]  # ✅ Filter by transaction ID

    def add_pending_transaction(self, transaction):
        """
        Add a transaction to the correct mempool based on its type.
        """
        try:
            tx_type = self.payment_type_manager.get_transaction_type(transaction.tx_id)
            mempool_type = Constants.TRANSACTION_MEMPOOL_MAP.get(tx_type.name, {}).get("mempool", "StandardMempool")

            if mempool_type == "SmartMempool":
                success = self.smart_mempool.add_transaction(transaction, len(self.blockchain.chain))
            else:
                success = self.standard_mempool.add_transaction(transaction)

            if success:
                logging.info(f"[MEMPOOL] ✅ Transaction {transaction.tx_id} added to {mempool_type}.")
                return True
            else:
                logging.error(f"[MEMPOOL] ❌ Failed to add transaction {transaction.tx_id} to {mempool_type}.")
                return False
        except Exception as e:
            logging.error(f"[ERROR] Failed to add pending transaction {transaction.tx_id}: {e}")
            return False






    ### -------------------- BLOCK PROPAGATION & NETWORK -------------------- ### NO CONSTANT UPDATE HERE YET 2-17-25 9.43PM 

    def propagate_block(self, block, nodes):
        """
        Broadcast a mined block to the P2P network.
        """
        logging.info(f"[POC] Propagating new block {block.hash} to network.")
        serialized_block = json.dumps(block.to_dict())

        for node in nodes:
            if isinstance(node, FullNode) or isinstance(node, ValidatorNode):
                node.receive_block(serialized_block)

    def validate_transaction(self, transaction, nodes):
        """
        Validate a transaction and ensure it has a valid transaction ID.
        """
        if not transaction.tx_id:
            logging.error("[ERROR] Transaction is missing tx_id.")
            return False

        logging.info(f"[POC] Validating transaction {transaction.tx_id}...")
        return True  # Temporary, implement full validation later

    def propagate_transaction(self, transaction, nodes):
        """
        Send a valid transaction to miner nodes.
        """
        logging.info(f"[POC] Propagating transaction {transaction.tx_id} for mining.")
        for node in nodes:
            if isinstance(node, MinerNode):
                node.receive_transaction(transaction)

    def validate_transaction_fee(self, transaction):
        """
        Ensure a transaction has sufficient fees.
        """
        transaction_size = len(str(transaction.inputs)) + len(str(transaction.outputs))
        required_fee = self.fee_model.calculate_fee(transaction_size)
        total_fee = sum(inp.amount for inp in transaction.inputs) - sum(out.amount for out in transaction.outputs)
        return total_fee >= required_fee



    def synchronize_node(self, node, peers):
        """Sync node with the latest blockchain state."""
        logging.info(f"[POC] Synchronizing node {node.node_id} with network.")
        latest_block = self.get_last_block()
        serialized_block = self.serialize_data(latest_block)
        node.sync_blockchain(serialized_block)
        node.sync_mempool(self.get_pending_transactions_from_mempool())


    ### -------------------- UTILITIES -------------------- ###

    def clear_blockchain(self):
        """
        Clear blockchain data for testing or reset.
        """
        self.chain = []
        logging.info("[INFO] Blockchain data cleared.")

# -------------------- NODE CLASSES FOR TESTING -------------------- #

class FullNode:
    def __init__(self, node_id):
        self.node_id = node_id

    def receive_block(self, block):
        logging.info(f"FullNode {self.node_id} received block {block}")

class ValidatorNode(FullNode):
    def validate_block(self, block):
        logging.info(f"ValidatorNode {self.node_id} is validating block {block}")

class MinerNode:
    def __init__(self, node_id):
        self.node_id = node_id

    def receive_transaction(self, transaction):
        logging.info(f"MinerNode {self.node_id} received transaction {transaction.tx_id}")

# -------------------- TEST EXECUTION -------------------- #

if __name__ == "__main__":
    poc = PoC()
    poc.clear_blockchain()  # Reset before test
    print("[INFO] PoC initialized successfully.")
