#!/usr/bin/env python3
"""
Main Entry Point (Start)

- Initializes all core modules: KeyManager, block storage modules, transaction manager, blockchain, miner, etc.
- Demonstrates how to replace a single StorageManager with multiple splitted storage modules.
- Uses detailed print statements (instead of logging).
- Assumes single SHA3-384 hashing is used throughout the code base.
"""

import sys
import os
import time
from decimal import Decimal

# Adjust Python path for project structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

# -------------------------------------------------------------------------
# Imports for your new splitted storage modules
# -------------------------------------------------------------------------
from Zyiron_Chain.storage.block_storage import WholeBlockData
from Zyiron_Chain.storage.blockmetadata import BlockMetadata
from Zyiron_Chain.storage.tx_storage import TxStorage
from Zyiron_Chain.storage.utxostorage import UTXOStorage
from Zyiron_Chain.storage.wallet_index import WalletStorage
from Zyiron_Chain.storage.mempool_storage import MempoolStorage
# If you have orphan_blocks.py, import that if needed:
# from Zyiron_Chain.storage.orphan_blocks import OrphanBlocks

# -------------------------------------------------------------------------
# Imports for your blockchain, transactions, keys, and miner
# -------------------------------------------------------------------------
from Zyiron_Chain.blockchain.blockchain import Blockchain
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.miner.miner import Miner
from Zyiron_Chain.transactions.transaction_manager import TransactionManager
from Zyiron_Chain.keys.key_manager import KeyManager


def detailed_print(message: str):
    """Helper function for detailed print-based debugging."""
    print(f"[START] {message}")


class Start:
    """
    Main entry point for the blockchain project.

    - Initializes all new splitted storage modules individually.
    - Creates the KeyManager, TransactionManager, Blockchain, and Miner.
    - Provides methods to run basic blockchain operations:
      * Loading chain from storage
      * Validating chain
      * Sending a sample transaction
      * Starting the mining loop
    """

    def __init__(self):
        detailed_print("Initializing blockchain project...")
        detailed_print(f"Network: {Constants.NETWORK}, Version: {Constants.VERSION}")

        # ---------------------------------------------------------------------
        # 1. Initialize KeyManager
        # ---------------------------------------------------------------------
        detailed_print("Initializing KeyManager...")
        self.key_manager = KeyManager()

        # ---------------------------------------------------------------------
        # 2. Initialize each splitted storage module
        # ---------------------------------------------------------------------
        detailed_print("Initializing splitted storage modules...")
        self.block_storage = WholeBlockData()     # For storing full blocks
        self.block_metadata = BlockMetadata()     # For block header metadata
        self.tx_storage = TxStorage()            # For transaction indexing
        self.utxo_storage = UTXOStorage()        # For UTXOs
        self.wallet_index = WalletStorage()        # For wallet data
        self.mempool_storage = MempoolStorage()  # For mempool data

        # If you use orphan blocks:
        # self.orphan_blocks = OrphanBlocks()

        # ---------------------------------------------------------------------
        # 3. Initialize TransactionManager
        # ---------------------------------------------------------------------
        detailed_print("Initializing TransactionManager...")
        self.transaction_manager = TransactionManager(
            block_storage=self.block_storage,
            tx_storage=self.tx_storage,
            utxo_storage=self.utxo_storage,
            mempool_storage=self.mempool_storage,
            wallet_index=self.wallet_index,
            key_manager=self.key_manager
        )
        # Adjust arguments based on your actual TransactionManager constructor

        # ---------------------------------------------------------------------
        # 4. Initialize the Blockchain
        # ---------------------------------------------------------------------
        detailed_print("Initializing Blockchain...")
        self.blockchain = Blockchain(
            block_storage=self.block_storage,
            block_metadata=self.block_metadata,
            tx_storage=self.tx_storage,
            utxo_storage=self.utxo_storage,
            wallet_index=self.wallet_index,
            transaction_manager=self.transaction_manager,
            key_manager=self.key_manager
        )
        # Adjust arguments based on your actual Blockchain constructor

        # ---------------------------------------------------------------------
        # 5. Initialize Miner
        # ---------------------------------------------------------------------
        detailed_print("Initializing Miner...")
        self.miner = Miner(
            blockchain=self.blockchain,
            transaction_manager=self.transaction_manager,
            key_manager=self.key_manager,
            mempool_storage=self.mempool_storage
        )
        # Adjust arguments based on your actual Miner constructor

    def load_blockchain(self):
        """
        Demonstrates loading the chain from storage or in-memory references.
        If your Blockchain class handles its own loading, you can call that method.
        """
        detailed_print("Loading blockchain data from storage...")

        # If your `Blockchain` class has a method to load from the splitted storages, call it:
        chain = self.blockchain.load_chain_from_storage()  # Example method
        detailed_print(f"Loaded {len(chain)} blocks from storage.")
        return chain

    def validate_blockchain(self):
        """
        Validate the entire chain in memory, ensuring references match,
        block hashes are correct, etc.
        """
        detailed_print("Validating blockchain integrity...")
        valid = self.blockchain.validate_chain()
        if valid:
            detailed_print("Blockchain validation passed.")
        else:
            detailed_print("Blockchain validation failed.")
        return valid

    def send_sample_transaction(self):
        """
        Demonstrates sending a sample transaction with dummy data.
        Replace the dummy values with real inputs/outputs from your chain.
        """
        detailed_print("Preparing sample transaction...")

        # Replace these with actual inputs/outputs from your chain
        sample_inputs = [{"tx_id": "dummy_tx_id1", "amount": "1.0"}]
        sample_outputs = [{"address": "sample_recipient_address", "amount": "0.9"}]

        try:
            # This example usage depends on how your TransactionManager is designed
            tx_data = self.transaction_manager.create_transaction(
                recipient_script_pub_key="sample_recipient_address",
                amount=Decimal("0.9"),
                block_size=Constants.MAX_BLOCK_SIZE_BYTES / (1024 * 1024),  # Convert bytes to MB
                payment_type="STANDARD"
            )
            detailed_print(f"Sample transaction prepared with TX ID: {tx_data['transaction'].tx_id}")
        except Exception as e:
            detailed_print(f"Error preparing sample transaction: {e}")

    def start_mining(self):
        """
        Demonstrates starting the mining loop.
        Press Ctrl+C to stop.
        """
        detailed_print("Starting mining loop. Press Ctrl+C to stop.")
        try:
            self.miner.mining_loop()
        except KeyboardInterrupt:
            detailed_print("Mining loop interrupted by user.")

    def run_all(self):
        """
        Runs all major blockchain operations in sequence.
        """
        detailed_print("----- Starting Full Blockchain Operations -----")
        self.load_blockchain()
        self.validate_blockchain()
        self.send_sample_transaction()
        self.start_mining()
        detailed_print("----- Blockchain Operations Completed -----")


if __name__ == "__main__":
    starter = Start()
    starter.run_all()
