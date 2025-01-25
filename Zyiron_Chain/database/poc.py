import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import hashlib
import logging
import json
import time 
from Zyiron_Chain.database.blockchainpoc import BlockchainPoC
from Zyiron_Chain.database.unqlitedatabase import BlockchainUnqliteDB
from Zyiron_Chain.database.sqlitedatabase import SQLiteDB
from Zyiron_Chain.database.duckdatabase import AnalyticsNetworkDB
from Zyiron_Chain.database.lmdatabase import LMDBManager
from Zyiron_Chain.database.tinydatabase import TinyDBManager
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.transactions.transactiontype import TransactionType
from Zyiron_Chain.transactions.fees import FeeModel, PaymentTypes
from datetime import datetime
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction
from Zyiron_Chain.transactions.transactiontype import TransactionType

logging.basicConfig(level=logging.INFO)

class PoC:
    def __init__(self):
        # Initialize the databases and transaction manager
        self.unqlite_db = BlockchainUnqliteDB()
        self.sqlite_db = SQLiteDB()
        self.duckdb_analytics = AnalyticsNetworkDB()
        self.lmdb_manager = LMDBManager()
        self.tinydb_manager = TinyDBManager()

        # Fee Model and Mempool
        self.fee_model = FeeModel()

        # Initialize PaymentType (or PaymentTypes) with the fee_model
        self.payment_type_manager = PaymentTypes(self.fee_model)  # Pass fee_model to PaymentType

        # Initialize BlockchainPoC (the blockchain-specific logic handler)
        self.blockchain_poc = BlockchainPoC(self)  # PoC now interacts with BlockchainPoC for blockchain-related operations

        # Initialize mempool for pending transactions
        self.mempool = []

    def store_block_metadata(self, block):
        """
        Store metadata about the block in DuckDB for analytics.
        :param block: The block whose metadata needs to be stored.
        """
        try:
            # Calculate block size
            block_size = 0
            for tx in block.transactions:
                if hasattr(tx, 'to_dict'):  # If tx is a Transaction object
                    block_size += len(str(tx.to_dict()))
                else:  # If tx is a dictionary
                    block_size += len(str(tx))

            # Extract metadata from the block
            block_metadata = {
                "index": block.index,
                "miner": "miner_address_placeholder",  # Replace with actual miner address
                "timestamp": block.timestamp,
                "size": block_size,  # Block size based on transactions
                "difficulty": block.header.nonce,  # Replace with actual difficulty if available
                "transaction_count": len(block.transactions)
            }

            # Store metadata in DuckDB
            self.duckdb_analytics.insert_block_metadata(**block_metadata)
            logging.info(f"[INFO] Stored metadata for block {block.index} in DuckDB.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to store block metadata: {e}")
            raise


    def get_total_size(self):
        """
        Calculate the total size of the mempool or blockchain.
        """
        return len(self.mempool)  # Example: Return the number of transactions in the mempool

    def serialize_data(self, data):
        """
        Serialize data before sending it to UnQLite, SQLite, or over the network.
        Convert the data into a JSON string for transmission or storage.
        """
        try:
            serialized_data = json.dumps(data)
            logging.info(f"[POC] Serialized data: {serialized_data}")
            return serialized_data
        except Exception as e:
            logging.error(f"[ERROR] Failed to serialize data: {e}")
            return None

    def load_blockchain_data(self):
        """
        Load blockchain data (blocks, transactions, UTXOs) from the appropriate storage.
        This could be from a database, file system, or other sources.
        """
        logging.info("[POC] Loading blockchain data...")

        # Delegate to BlockchainPoC to load blockchain data
        try:
            self.blockchain_poc.load_blockchain_data()  # Let BlockchainPoC handle the loading of blockchain data
            logging.info(f"[POC] Loaded blockchain data successfully.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to load blockchain data: {e}")

    def store_block(self, block, difficulty):
        """
        Store a block in the PoC layer.
        This will handle storing the block data into UnQLite (or another DB you are using).
        :param block: The block to be stored.
        :param difficulty: The difficulty for mining the block.
        """
        try:
            # Serialize the block into a dictionary form
            block_data = block.to_dict()

            # Get the necessary details to pass to add_block
            block_header = block.header
            transactions = block.transactions
            size = sum(len(str(tx.to_dict())) for tx in transactions)  # Example block size based on transactions

            # Now store the block data in UnQLite
            self.unqlite_db.add_block(
                block_data['hash'],
                block_header,
                transactions,
                size,
                difficulty
            )

            print(f"[INFO] Block {block.index} stored in PoC successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to store block: {e}")
            raise

    def get_blockchain_data(self):
        """
        Return the blockchain data that has been loaded by BlockchainPoC.
        """
        # Delegate to BlockchainPoC to get the blockchain data
        return self.blockchain_poc.get_blockchain_data()  # Get blockchain data from BlockchainPoC

    def deserialize_data(self, serialized_data):
        """
        Deserialize data received from UnQLite, SQLite, or the network.
        Convert the JSON string back into a Python object.
        """
        try:
            deserialized_data = json.loads(serialized_data)
            logging.info(f"[POC] Deserialized data: {deserialized_data}")
            return deserialized_data
        except Exception as e:
            logging.error(f"[ERROR] Failed to deserialize data: {e}")
            return None

    def route_request(self, node, request_type, data=None):
        """
        Route requests between nodes in the P2P network based on node type and request type.
        """
        if request_type == "block":
            return self.handle_block_request(node, data)
        elif request_type == "utxo":
            return self.handle_utxo_request(node, data)
        elif request_type == "transaction":
            return self.handle_transaction_request(node, data)
        elif request_type == "metadata":
            return self.handle_metadata_request(node)
        else:
            logging.error(f"[ERROR] Unsupported request type: {request_type}")
            return None

    def handle_block_request(self, node, block_hash):
        """
        Handle requests for blocks, routing to the appropriate node based on role.
        """
        logging.info(f"[POC] Handling block request for {block_hash}")
        if isinstance(node, FullNode) or isinstance(node, ValidatorNode):
            # Route block request to BlockchainPoC for handling block retrieval
            block_data = self.blockchain_poc.get_block(block_hash)  # BlockchainPoC handles getting the block
            return self.deserialize_data(block_data)  # Deserialize block data for the node
        logging.error("[ERROR] Invalid node type for block request.")
        return None

    def handle_utxo_request(self, node, utxo_id):
        """
        Handle UTXO request, routing it to the correct database.
        """
        logging.info(f"[POC] Handling UTXO request for {utxo_id}")
        if isinstance(node, FullNode) or isinstance(node, ValidatorNode):
            # Route UTXO request to BlockchainPoC for handling UTXO retrieval
            utxo_data = self.blockchain_poc.get_utxo_data(utxo_id)  # BlockchainPoC handles getting UTXOs
            return self.deserialize_data(utxo_data)  # Deserialize UTXO data for the node
        logging.error("[ERROR] Invalid node type for UTXO request.")
        return None

    def handle_transaction_request(self, node, transaction_id):
        """
        Handle requests for pending transactions, routing to LMDB or other sources.
        """
        logging.info(f"[POC] Handling transaction request for {transaction_id}")
        if isinstance(node, FullNode) or isinstance(node, MinerNode):
            # Route transaction request to BlockchainPoC for handling transaction retrieval
            pending_transactions = self.blockchain_poc.get_pending_transactions(transaction_id)  # BlockchainPoC handles transactions
            return self.deserialize_data(pending_transactions)  # Deserialize transaction data for the node
        logging.error("[ERROR] Invalid node type for transaction request.")
        return None

    def handle_metadata_request(self, node):
        """
        Handle metadata requests for light nodes or analytics purposes.
        """
        logging.info("[POC] Handling metadata request.")
        if isinstance(node, LightNode):
            metadata = self.duckdb_analytics.fetch_network_analytics("avg_fee")
            return self.deserialize_data(metadata)  # Deserialize metadata for Light Node
        logging.error("[ERROR] Invalid node type for metadata request.")
        return None

    def handle_transaction_type(self, transaction):
        """
        Handle transaction type after it is processed.
        If the transaction was Instant or Smart, update it to Standard after usage.
        """
        current_type = transaction.current_type
        print(f"Current transaction type: {current_type}")

        # Update transaction type if it was Instant or Smart and has been processed
        if current_type == TransactionType.INSTANT:
            print(f"Changing transaction type to {TransactionType.STANDARD} after processing.")
            transaction.update_payment_type(TransactionType.STANDARD)

        elif current_type == TransactionType.SMART:
            print(f"Changing transaction type to {TransactionType.STANDARD} after processing.")
            transaction.update_payment_type(TransactionType.STANDARD)

    def propagate_block(self, block, nodes):
        """
        Propagate a newly mined block to the P2P network.
        """
        logging.info(f"[POC] Propagating new block {block.hash} to the network.")
        # Use BlockchainPoC to serialize the block
        serialized_block = self.blockchain_poc.serialize_data(block)  # BlockchainPoC handles block serialization
        for node in nodes:
            if isinstance(node, FullNode) or isinstance(node, ValidatorNode):
                node.receive_block(serialized_block)  # Send the serialized block to nodes

    def validate_transaction(self, transaction, nodes):
        """
        Validate a transaction and propagate it through the network.
        """
        logging.info(f"[POC] Validating transaction {transaction.tx_id}.")
        if self.validate_transaction_fee(transaction):
            logging.info(f"[POC] Transaction {transaction.tx_id} is valid.")
            # Propagate to LMDB for mining via PoC
            serialized_tx = self.blockchain_poc.serialize_data(transaction)  # BlockchainPoC handles transaction serialization
            self.add_pending_transaction(serialized_tx)  # PoC handles adding transaction to the mempool
            self.propagate_transaction(serialized_tx, nodes)
        else:
            logging.error(f"[ERROR] Transaction {transaction.tx_id} failed fee validation.")

    def propagate_transaction(self, transaction, nodes):
        """
        Propagate a valid transaction to Miner Nodes for inclusion in blocks.
        """
        logging.info(f"[POC] Propagating transaction {transaction.tx_id} for mining.")
        for node in nodes:
            if isinstance(node, MinerNode):
                node.receive_transaction(transaction)

    def validate_transaction_fee(self, transaction):
        """
        Validate if the transaction fee is adequate.
        """
        transaction_size = len(str(transaction.tx_inputs)) + len(str(transaction.tx_outputs))
        required_fee = self.fee_model.calculate_fee(transaction_size)
        total_fee = sum(inp.amount for inp in transaction.tx_inputs) - sum(out.amount for out in transaction.tx_outputs)
        if total_fee >= required_fee:
            return True
        return False

    def synchronize_node(self, node, peers):
        """
        Synchronize a node with the latest blockchain state from peers.
        """
        logging.info(f"[POC] Synchronizing node {node.node_id} with the P2P network.")
        latest_block = self.blockchain_poc.get_last_block()  # Use BlockchainPoC to get the latest block
        serialized_block = self.serialize_data(latest_block)  # Use PoC for serialization
        node.sync_blockchain(serialized_block)
        node.sync_mempool(self.get_pending_transactions_from_mempool())  # Use PoC to sync mempool with node

    def handle_error(self, error):
        """
        Handle errors during PoC operations and implement retry logic.
        """
        logging.error(f"[POC] Error encountered: {error}. Retrying...")
        # Implement retry logic here, for example:
        self.retry_failed_operation(error)  # PoC can manage retries for failed operations

    def get_block(self, block_hash):
        """
        Route block retrieval request to BlockchainPoC.
        """
        return self.blockchain_poc.get_block(block_hash)  # PoC now delegates to BlockchainPoC for blocks

    def get_utxo_data(self, utxo_id):
        """
        Route UTXO retrieval request to BlockchainPoC.
        """
        return self.blockchain_poc.get_utxo_data(utxo_id)

    def get_pending_transactions(self, transaction_id=None):
        """
        Route transaction retrieval request to BlockchainPoC.
        """
        return self.blockchain_poc.get_pending_transactions(transaction_id)

    def get_pending_transactions_from_mempool(self):
        """
        Get pending transactions from the mempool.
        """
        return self.mempool

    def add_pending_transaction(self, transaction):
        """
        Add a pending transaction to the mempool.
        """
        self.mempool.append(transaction)

    def retry_failed_operation(self, error):
        """
        Retry a failed operation.
        """
        logging.info(f"[POC] Retrying failed operation: {error}")
        # Implement retry logic here

# Example Node Classes for routing requests (FullNode, ValidatorNode, MinerNode, etc.)
class FullNode:
    def __init__(self, node_id):
        self.node_id = node_id

    def receive_block(self, block):
        logging.info(f"FullNode {self.node_id} received block {block.hash}")

    def sync_blockchain(self, block):
        logging.info(f"FullNode {self.node_id} is syncing blockchain with block {block.hash}")

class ValidatorNode(FullNode):
    def validate_block(self, block):
        logging.info(f"ValidatorNode {self.node_id} is validating block {block.hash}")

class MinerNode:
    def __init__(self, node_id):
        self.node_id = node_id

    def receive_transaction(self, transaction):
        logging.info(f"MinerNode {self.node_id} received transaction {transaction.tx_id}")

class LightNode:
    def __init__(self, node_id):
        self.node_id = node_id

# Main execution for testing PoC functionalities
if __name__ == "__main__":
    poc = PoC()

    # Example setup for nodes
    node_a = FullNode(node_id="Node_A")
    node_b = ValidatorNode(node_id="Node_B")
    nodes = [node_a, node_b]

    # Example transaction validation and propagation
    transaction = Transaction(tx_inputs=["input1"], tx_outputs=["output1"], fee=0.01)
    poc.validate_transaction(transaction, nodes)

    # Example block propagation
    block = Block(index=1, previous_hash="0", transactions=["tx1", "tx2"])
    poc.propagate_block(block, nodes)

    # Example synchronization
    poc.synchronize_node(node_a, nodes)