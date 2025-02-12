import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import hashlib
import logging
import json
import time 
import random
from Zyiron_Chain.database.unqlitedatabase import BlockchainUnqliteDB
from Zyiron_Chain.database.sqlitedatabase import SQLiteDB
from Zyiron_Chain.database.duckdatabase import AnalyticsNetworkDB
from Zyiron_Chain.database.lmdatabase import LMDBManager
from Zyiron_Chain.database.tinydatabase import TinyDBManager
from Zyiron_Chain.blockchain.helper  import get_block
from typing import Optional
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager

from Zyiron_Chain.blockchain.blockheader import BlockHeader
from Zyiron_Chain.transactions.transactiontype import TransactionType
import importlib
from Zyiron_Chain.blockchain.block_manager import BlockManager
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.offchain.dispute import DisputeResolutionContract

import sqlite3
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager
from datetime import datetime
from Zyiron_Chain.transactions.transactiontype import TransactionType
from decimal import Decimal
def get_transaction():
    """Lazy import Transaction to break circular dependencies."""
    module = importlib.import_module("Zyiron_Chain.transactions.Blockchain_transaction")
    return getattr(module, "Transaction")

def get_standard_mempool():
    """Lazy import StandardMempool to prevent circular imports."""
    module = importlib.import_module("Zyiron_Chain.blockchain.utils.standardmempool")
    return getattr(module, "StandardMempool")

def get_block_instance():
    """Dynamically import Block only when needed to prevent circular imports."""
    return get_block()
def get_fee_model():
    """Lazy import FeeModel to break circular dependencies."""
    module = importlib.import_module("Zyiron_Chain.transactions.fees")
    return getattr(module, "FeeModel")

def get_smart_mempool():
    """Lazy load SmartMempool to fix circular import"""
    module = importlib.import_module("Zyiron_Chain.smartpay.smartmempool")
    return getattr(module, "SmartMempool")
logging.basicConfig(level=logging.INFO)



class PoC:
    def __init__(self):
        """Initialize the Point-of-Contact (PoC) layer"""
        self.unqlite_db = BlockchainUnqliteDB()  # Stores the entire blockchain
        self.sqlite_db = SQLiteDB()  # UTXO storage
        self.duckdb_analytics = AnalyticsNetworkDB()  # Analytics database
        self.lmdb_manager = LMDBManager()  # Stores block metadata
        self.tinydb_manager = TinyDBManager()  # Handles node settings

        # ✅ Assign storage_manager to UnQLite since it handles full blockchain storage
        self.storage_manager = self.unqlite_db  

        # ✅ Initialize BlockManager (Fix for missing attribute)
        from Zyiron_Chain.blockchain.block_manager import BlockManager  # Ensure correct import
        self.block_manager = BlockManager(storage_manager=self.lmdb_manager)

        # ✅ Initialize `TransactionManager` to Fix Missing Attribute Error
        from Zyiron_Chain.blockchain.transaction_manager import TransactionManager
        from Zyiron_Chain.blockchain.utils.key_manager import KeyManager  # Ensure KeyManager is available
        self.key_manager = KeyManager()  # ✅ Ensure KeyManager is initialized
        self.transaction_manager = TransactionManager(self.storage_manager, self.key_manager, self)

        # ✅ Pass `transaction_manager` to `BlockManager`
        self.block_manager = BlockManager(storage_manager=self.storage_manager, transaction_manager=self.transaction_manager)

        # ✅ Lazy Load FeeModel to Prevent Circular Import
        FeeModel = get_fee_model()
        self.fee_model = FeeModel(max_supply=Decimal("84096000"))

        # ✅ Initialize Payment Type Manager
        self.payment_type_manager = PaymentTypeManager()

        # ✅ Initialize Dispute Resolution Contract
        self.dispute_contract = DisputeResolutionContract(self)

        # ✅ Lazy Load StandardMempool with PoC Instance
        StandardMempool = get_standard_mempool()
        self.standard_mempool = StandardMempool(self)  # ✅ Fix: Pass `self` (PoC instance)
        self.mempool = self.standard_mempool  # Default to standard mempool

        # ✅ Initialize UTXO Cache to Store Retrieved UTXOs
        self._cache = {}  # 🚀 This prevents `AttributeError`



    ### --------------------- Anti Farm Logic -------------------------------###

    # 🚀 Dynamic VRAM Scaling (8MB - 192MB)
    def get_vram_allocation(self):
        """Determine dynamic VRAM requirement based on network hashrate."""
        hashrate = self.get_network_hashrate()

        if hashrate < 10_000:
            return 8  # 8MB VRAM
        elif hashrate < 50_000:
            return 32
        elif hashrate < 100_000:
            return 64
        elif hashrate < 500_000:
            return 128
        else:
            return 192  # 192MB for high hashrate


    # 🔁 Algorithm Rotation Based on Hashrate
    def check_algorithm_rotation(self, block_index):
        """Trigger algorithm rotation if hashrate jumps 10%+ in 2 hours."""
        hashrate_change = self.get_network_hashrate_change()
        if hashrate_change > 10:
            logging.warning(f"[WARNING] Hashrate spiked {hashrate_change:.2f}%. Rotating algorithm.")
            return True
        return block_index % random.randint(24, 100) == 0  # Normal rotation every 24-100 blocks

    # 🚨 ASIC & Farm Detection
    def detect_farm_activity(self):
        """Detect large mining farms based on unusual hashrate spikes."""
        hashrate_change = self.get_network_hashrate_change()
        if hashrate_change > 10:
            logging.warning(f"[WARNING] Hashrate increased {hashrate_change:.2f}%. Activating countermeasures.")
            self.increase_vram_allocation()
            self.increase_difficulty()
            self.force_algorithm_rotation()

    # ⚙️ Real-Time Difficulty Adjustment (Every 24 Blocks)
    def adjust_difficulty(self, block_index):
        """Adjust mining difficulty dynamically every 24 blocks."""
        if block_index % 24 == 0:
            self.block_manager.recalculate_difficulty()

    # ⏳ Network Hashrate Monitoring (Every 2 Hours)
    def monitor_network_hashrate(self):
        """Check network hashrate every 2 hours & adjust accordingly."""
        while True:
            time.sleep(7200)  # 2-hour intervals
            hashrate_change = self.get_network_hashrate_change()
            if hashrate_change < 5:
                logging.info("[INFO] Minor hashrate change. No major adjustments needed.")
            elif hashrate_change < 10:
                logging.info("[INFO] Moderate hashrate increase detected. Adjusting difficulty.")
                self.adjust_difficulty(self.get_latest_block_index())
            else:
                logging.warning(f"[WARNING] Major hashrate spike ({hashrate_change:.2f}%). Triggering countermeasures.")
                self.detect_farm_activity()








    ### -------------------- BLOCKCHAIN STORAGE & VALIDATION -------------------- ###

    def store_block(self, block, difficulty):
        """
        Store a block in the PoC layer with atomic transactions to prevent inconsistencies.
        """
        try:
            from Zyiron_Chain.blockchain.block import Block  # ✅ Ensure Block is properly imported

            if isinstance(block, dict):
                block = Block.from_dict(block)  # ✅ Correct reference to Block class

            block_data = block.to_dict()
            block_header = block.header.to_dict()
            transactions = [tx.to_dict() for tx in block.transactions]
            size = sum(len(json.dumps(tx)) for tx in transactions)  # Calculate block size

            # Use atomic transactions across databases
            self.sqlite_db.begin_transaction()
            self.unqlite_db.begin_transaction()
            self.lmdb_manager.begin_transaction()

            # Store block in multiple databases
            self.unqlite_db.add_block(block_data['hash'], block_header, transactions, size, difficulty)

            self.unqlite_db.add_block(block_data['hash'], block_header, transactions, size, difficulty)
            self.lmdb_manager.add_block(block_data['hash'], block_header, transactions, size, difficulty)

            # Commit changes to all databases
            self.sqlite_db.commit()
            self.unqlite_db.commit()
            self.lmdb_manager.commit()

            logging.info(f"[INFO] Block {block.index} stored successfully in PoC.")

        except Exception as e:
            # Rollback changes in case of failure
            self.sqlite_db.rollback()
            self.unqlite_db.rollback()
            self.lmdb_manager.rollback()
            logging.error(f"[ERROR] Block storage failed: {e}")
            raise



    def store_utxo(self, utxo_id, utxo_data):
        """
        Store a UTXO in SQLite via PoC, ensuring type safety and preventing duplicates.
        """
        try:
            if not isinstance(utxo_data, dict):
                raise TypeError("[ERROR] UTXO data must be a dictionary.")

            required_keys = ["tx_out_id", "amount", "script_pub_key"]
            for key in required_keys:
                if key not in utxo_data:
                    raise KeyError(f"[ERROR] Missing required UTXO field: {key}")

            # ✅ Convert types for SQLite storage
            tx_out_id = str(utxo_data["tx_out_id"])
            amount = float(utxo_data["amount"])  # ✅ Convert Decimal to float
            script_pub_key = str(utxo_data["script_pub_key"])
            locked = int(bool(utxo_data.get("locked", False)))  # ✅ Convert boolean to int (0 or 1)
            block_index = int(utxo_data.get("block_index", 0))  # ✅ Ensure block index is an integer

            # ✅ Remove existing UTXO if it exists
            existing_utxo = self.sqlite_db.get_utxo(tx_out_id)
            if existing_utxo:
                logging.warning(f"[WARNING] UTXO {tx_out_id} already exists. Replacing with new data.")
                self.sqlite_db.delete_utxo(tx_out_id)  # ✅ Remove old UTXO before inserting a new one

            # ✅ Store UTXO in SQLite
            self.sqlite_db.insert_utxo(
                utxo_id=utxo_id,
                tx_out_id=tx_out_id,
                amount=amount,
                script_pub_key=script_pub_key,
                locked=locked,
                block_index=block_index
            )

            logging.info(f"[INFO] UTXO {utxo_id} successfully stored in SQLite.")
            return True  # ✅ Indicate success

        except (KeyError, TypeError, ValueError) as e:
            logging.error(f"[ERROR] Failed to store UTXO {utxo_id}: {e}")
            return False  # ✅ Indicate failure






    def ensure_consistency(self, block):
        """
        Ensure blockchain consistency before adding a new block.
        :param block: The block to check.
        :raises ValueError: If the block does not meet consistency requirements.
        """
        if not block:
            raise ValueError("[ERROR] Invalid block: Block data is missing.")

        if not block.hash or not block.merkle_root:
            raise ValueError("[ERROR] Block hash or Merkle root is missing.")

        if self.chain:
            last_block = self.chain[-1]

            # Check for proper block linking
            if block.previous_hash != last_block.hash:
                raise ValueError(
                    f"[ERROR] Previous hash mismatch: Expected {last_block.hash}, Got {block.previous_hash}"
                )

            # Ensure sequential block indexing
            if block.index != last_block.index + 1:
                raise ValueError(
                    f"[ERROR] Block index mismatch: Expected {last_block.index + 1}, Got {block.index}"
                )

        else:
            # Ensure genesis block has the correct index
            if block.index != 0:
                raise ValueError("[ERROR] First block must have index 0.")

        logging.info(f"[INFO] Block {block.index} passed consistency checks.")

    def get_last_block(self):
        """Fetch the latest block from the database, returning a default block if empty."""
        from Zyiron_Chain.blockchain.block import Block  # ✅ Lazy import fixes circular import issue

        logging.info("[POC] Fetching latest block...")

        blocks = self.unqlite_db.get_all_blocks()
        if not blocks:
            logging.warning("[POC] No blocks found in database. Creating Genesis Block...")
            return Block(
                index=0,
                previous_hash="0" * 96,
                transactions=[CoinbaseTx(block_height=0, miner_address="genesis", reward=Decimal("100.0"))],
                timestamp=int(time.time()),
                key_manager=KeyManager(),
                nonce=0,
                poc=self
            )

        last_block_data = blocks[-1]  # Get the most recent block

        # ✅ Ensure critical fields exist
        last_block_data.setdefault("index", len(blocks) - 1)  
        last_block_data.setdefault("previous_hash", "0" * 96)  
        last_block_data.setdefault("timestamp", time.time())  
        last_block_data.setdefault("merkle_root", "0" * 96)  
        last_block_data.setdefault("nonce", 0)  
        last_block_data.setdefault("header", {
            "version": 1,
            "index": last_block_data["index"],
            "previous_hash": last_block_data["previous_hash"],
            "merkle_root": last_block_data["merkle_root"],
            "timestamp": last_block_data["timestamp"],
            "nonce": last_block_data["nonce"]
        })

        # ✅ Handle missing hash by recalculating it
        if "hash" not in last_block_data:
            logging.warning(f"[POC] Block {last_block_data['index']} missing 'hash'. Recalculating...")
            temp_block = Block.from_dict(last_block_data)
            last_block_data["hash"] = temp_block.calculate_hash()

        return Block.from_dict(last_block_data)  # ✅ Ensures return type is Block object





    def get_block(self, block_hash):
        """
        Retrieve a block from the blockchain database by its hash.
        """
        logging.info(f"[POC] Fetching block with hash {block_hash}")
        try:
            block_data = self.unqlite_db.get_block(block_hash)
            if block_data:
                return get_block.from_dict(block_data)  # Ensure return type is Block object
            logging.warning(f"[POC] Block {block_hash} not found.")
            return None
        except Exception as e:
            logging.error(f"[POC] Failed to fetch block {block_hash}: {e}")
            return None
    
    
        
    def get_utxo(self, tx_out_id: str) -> Optional[TransactionOut]:
        """Retrieve UTXO from SQLite, ensuring correct row conversion and caching."""
        
        if tx_out_id in self._cache:
            return TransactionOut.from_dict(dict(self._cache[tx_out_id]))  # ✅ Convert cached UTXO to dict

        utxo_data = self.sqlite_db.get_utxo(tx_out_id)  # ✅ Corrected method call

        if utxo_data:
            try:
                # ✅ Convert sqlite3.Row to a dictionary if necessary
                utxo_dict = dict(utxo_data) if isinstance(utxo_data, sqlite3.Row) else utxo_data
                self._cache[tx_out_id] = utxo_dict  # ✅ Cache the converted UTXO
                return TransactionOut.from_dict(utxo_dict)  # ✅ Ensure proper format
            except Exception as e:
                logging.error(f"[ERROR] Failed to convert UTXO {tx_out_id}: {e}")
                return None

        logging.warning(f"[WARNING] UTXO {tx_out_id} not found in SQLite.")
        return None  # ✅ Explicitly return None if not found


    def validate_block(self, block):
        """
        Validate a block before adding it to the blockchain.
        :param block: The block to validate.
        """
        try:
            self.ensure_consistency(block)
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
            self.lmdb_manager.store_pending_transaction(transaction.tx_id, transaction.to_dict())
            logging.info(f"[POC] Routed transaction {transaction.tx_id} to LMDB (Mempool).")
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

            self.unqlite_db.store_transaction(transaction)
            logging.info(f"[INFO] Transaction {transaction.tx_id} handled successfully.")

        except Exception as e:
            logging.error(f"[ERROR] Failed to handle transaction: {e}")
            raise

    def get_pending_transactions(self, transaction_id=None):
        """
        Retrieve pending transactions.
        """
        return self.mempool if transaction_id is None else [tx for tx in self.mempool if tx.tx_id == transaction_id]

    def add_pending_transaction(self, transaction):
        """
        Add a transaction to the mempool.
        """
        self.mempool.append(transaction)

    ### -------------------- BLOCK PROPAGATION & NETWORK -------------------- ###

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
