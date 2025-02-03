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
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.blockchain.blockheader import BlockHeader
from Zyiron_Chain.transactions.transactiontype import TransactionType
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager
from datetime import datetime
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction
from Zyiron_Chain.transactions.transactiontype import TransactionType
from decimal import Decimal

logging.basicConfig(level=logging.INFO)


class PoC:
    def __init__(self):
        """
        Initialize the Point-of-Contact (PoC) layer to handle node interactions, database storage,
        and blockchain operations.
        """
        self.unqlite_db = BlockchainUnqliteDB()
        self.sqlite_db = SQLiteDB()
        self.duckdb_analytics = AnalyticsNetworkDB()
        self.lmdb_manager = LMDBManager()
        self.tinydb_manager = TinyDBManager()

        # Initialize Fee Model with max supply
        self.fee_model = FeeModel(Decimal("84096000"))

        # Initialize Payment Type Manager
        self.payment_type_manager = PaymentTypeManager()

        # Mempool for pending transactions
        self.mempool = []


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
            if isinstance(block, dict):
                block = Block.from_dict(block)  # Convert dict to Block object if needed

            block_data = block.to_dict()
            block_header = block.header.to_dict()
            transactions = [tx.to_dict() for tx in block.transactions]

            size = sum(len(json.dumps(tx)) for tx in transactions)  # Calculate block size

            # Use atomic transactions across databases
            self.sqlite_db.begin_transaction()
            self.unqlite_db.begin_transaction()
            self.lmdb_manager.begin_transaction()

            # Store block in databases
            self.sqlite_db.add_block(
                block_data['hash'],
                block_header,
                transactions,
                size,
                difficulty
            )

            self.unqlite_db.add_block(
                block_data['hash'],
                block_header,
                transactions,
                size,
                difficulty
            )

            self.lmdb_manager.add_block(
                block_data['hash'],
                block_header,
                transactions,
                size,
                difficulty
            )

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
        Store a UTXO in the SQLite database.
        :param utxo_id: Unique UTXO identifier.
        :param utxo_data: Dictionary containing UTXO data.
        """
        try:
            if not isinstance(utxo_data, dict):
                raise TypeError("[ERROR] UTXO data must be a dictionary.")

            required_keys = ["tx_out_id", "amount", "script_pub_key"]
            for key in required_keys:
                if key not in utxo_data:
                    raise KeyError(f"[ERROR] Missing required UTXO field: {key}")

            self.sqlite_db.add_utxo(
                utxo_id=utxo_id,
                tx_out_id=utxo_data["tx_out_id"],
                amount=Decimal(utxo_data["amount"]),
                script_pub_key=utxo_data["script_pub_key"],
                locked=utxo_data.get("locked", False),  # Default to False if not provided
                block_index=utxo_data.get("block_index", 0)  # Default index 0 for new UTXOs
            )

            logging.info(f"[INFO] UTXO {utxo_id} stored in SQLite successfully.")
        except (KeyError, TypeError, ValueError) as e:
            logging.error(f"[ERROR] Failed to store UTXO {utxo_id}: {e}")
            raise


    def ensure_consistency(self, block):
        """
        Ensure blockchain consistency before adding a new block.
        :param block: The block to check.
        """
        if self.chain:
            last_block = self.chain[-1]
            if block.previous_hash != last_block.hash:
                raise ValueError(f"Previous hash mismatch: {block.previous_hash} != {last_block.hash}")
            if block.index != last_block.index + 1:
                raise ValueError(f"Block index mismatch: {block.index} != {last_block.index + 1}")
        else:
            if block.index != 0:
                raise ValueError("First block must have index 0.")

        if not block.hash or not block.merkle_root:
            raise ValueError("Block hash or Merkle root is missing.")


    def get_last_block(self):
        """ Fetch the latest block from the database. """
        from Zyiron_Chain.blockchain.block import Block  # ✅ Lazy import fixes circular import issue

        logging.info("[POC] Fetching latest block...")

        blocks = self.unqlite_db.get_all_blocks()
        if not blocks:
            logging.warning("[POC] No blocks found in database.")
            return None  # No blocks exist

        last_block_data = blocks[-1]  # Get the most recent block

        # Ensure all critical fields exist
        last_block_data.setdefault("index", len(blocks) - 1)  # Default index
        last_block_data.setdefault("previous_hash", "0" * 96)  # Default genesis hash
        last_block_data.setdefault("timestamp", time.time())  # Assign current timestamp
        last_block_data.setdefault("merkle_root", "0" * 96)  # Default Merkle root
        last_block_data.setdefault("nonce", 0)  # Default nonce
        last_block_data.setdefault("header", {
            "version": 1,
            "index": last_block_data["index"],
            "previous_hash": last_block_data["previous_hash"],
            "merkle_root": last_block_data["merkle_root"],
            "timestamp": last_block_data["timestamp"],
            "nonce": last_block_data["nonce"]
        })

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
                return Block.from_dict(block_data)  # Ensure return type is Block object
            logging.warning(f"[POC] Block {block_hash} not found.")
            return None
        except Exception as e:
            logging.error(f"[POC] Failed to fetch block {block_hash}: {e}")
            return None
        

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
        transaction_size = len(str(transaction.tx_inputs)) + len(str(transaction.tx_outputs))
        required_fee = self.fee_model.calculate_fee(transaction_size)
        total_fee = sum(inp.amount for inp in transaction.tx_inputs) - sum(out.amount for out in transaction.tx_outputs)
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