#!/usr/bin/env python3
"""
Main Entry Point (Start)

- Initializes all core modules: KeyManager, splitted storage modules, TransactionManager,
  Blockchain, Miner, etc.
- Uses detailed print statements for step-by-step tracing.
- Assumes single SHA3-384 hashing is used throughout.
"""

import sys
import os
import time
from decimal import Decimal

# Adjust Python path for project structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

# -------------------------------------------------------------------------
# Imports for the new splitted storage modules
# -------------------------------------------------------------------------
from Zyiron_Chain.storage.block_storage import WholeBlockData
from Zyiron_Chain.storage.blockmetadata import BlockMetadata
from Zyiron_Chain.storage.tx_storage import TxStorage
from Zyiron_Chain.storage.utxostorage import UTXOStorage
from Zyiron_Chain.storage.wallet_index import WalletStorage
from Zyiron_Chain.storage.mempool_storage import MempoolStorage

# -------------------------------------------------------------------------
# Imports for blockchain, transactions, keys, and miner
# -------------------------------------------------------------------------
from Zyiron_Chain.blockchain.blockchain import Blockchain
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.miner.miner import Miner
from Zyiron_Chain.transactions.transaction_manager import TransactionManager
from Zyiron_Chain.keys.key_manager import KeyManager
from Zyiron_Chain.storage.lmdatabase import LMDBManager  # For LMDB manager creation
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
def detailed_print(message: str):
    """Helper function for detailed print-based debugging."""
    print(f"[START] {message}")

class Start:
    """
    Main entry point for the blockchain project.

    - Initializes all splitted storage modules individually.
    - Creates the KeyManager, TransactionManager, Blockchain, and Miner.
    - Provides methods to run basic blockchain operations.
    """

    def __init__(self):
        detailed_print("Initializing blockchain project...")
        detailed_print(f"Network: {Constants.NETWORK}, Version: {Constants.VERSION}")

        # 1. Initialize KeyManager
        detailed_print("Initializing KeyManager...")
        self.key_manager = KeyManager()

        # 2. Initialize each splitted storage module
        detailed_print("Initializing splitted storage modules...")

        # Block storage & metadata
        self.block_storage = WholeBlockData()
        self.block_metadata = BlockMetadata()
        self.tx_storage = TxStorage()
        self.wallet_index = WalletStorage()
        self.mempool_storage = MempoolStorage()

        # For UTXOStorage, create LMDB managers for UTXO and UTXO history:
        utxo_db_path = Constants.DATABASES.get("utxo")
        utxo_history_path = Constants.DATABASES.get("utxo_history")
        detailed_print(f"Initializing LMDB managers for UTXO at {utxo_db_path} and UTXO history at {utxo_history_path}...")
        utxo_db = LMDBManager(utxo_db_path)
        utxo_history_db = LMDBManager(utxo_history_path)

        # Create a UTXOManager using the storage manager (peer id now comes from PeerConstants)
        from Zyiron_Chain.network.peerconstant import PeerConstants
        peer_constants = PeerConstants()  # This will validate the network and provide PEER_USER_ID
        detailed_print(f"Initializing UTXOManager with peer id '{peer_constants.PEER_USER_ID}'...")
        # UTXOManager now takes only the storage_manager as its parameter.
        from Zyiron_Chain.storage.utxostorage import UTXOStorage  # ensure correct import
        # Create UTXOManager
        utxo_manager = UTXOManager(utxo_db)

        # Now initialize UTXOStorage with the required parameters.
        self.utxo_storage = UTXOStorage(
            utxo_db=utxo_db,
            utxo_history_db=utxo_history_db,
            utxo_manager=utxo_manager
        )
        detailed_print("UTXOStorage initialized successfully.")

        # 3. Initialize TransactionManager with utxo_manager
        detailed_print("Initializing TransactionManager...")
        self.transaction_manager = TransactionManager(
            block_storage=self.block_storage,
            block_metadata=self.block_metadata,
            tx_storage=self.tx_storage,
            utxo_manager=utxo_manager,  # Pass the utxo_manager instance
            key_manager=self.key_manager
        )
        # 4. Initialize the Blockchain
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
        # 5. Initialize Miner
        detailed_print("Initializing Miner...")
        self.miner = Miner(
            blockchain=self.blockchain,
            transaction_manager=self.transaction_manager,
            key_manager=self.key_manager,
            mempool_storage=self.mempool_storage
        )

    def load_blockchain(self):
        detailed_print("Loading blockchain data from storage...")
        chain = self.blockchain.load_chain_from_storage()  # Assumes Blockchain has this method
        detailed_print(f"Loaded {len(chain)} blocks from storage.")
        return chain

    def validate_blockchain(self):
        detailed_print("Validating blockchain integrity...")
        valid = self.blockchain.validate_chain()  # Assumes Blockchain.validate_chain() exists
        if valid:
            detailed_print("Blockchain validation passed.")
        else:
            detailed_print("Blockchain validation failed.")
        return valid

    def send_sample_transaction(self):
        detailed_print("Preparing sample transaction...")
        # Replace these dummy values with real inputs/outputs from your application if needed
        sample_inputs = [{"tx_id": "dummy_tx_id1", "amount": "1.0"}]
        sample_outputs = [{"address": "sample_recipient_address", "amount": "0.9"}]
        try:
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
        detailed_print("Starting mining loop. Press Ctrl+C to stop.")
        try:
            self.miner.mining_loop()
        except KeyboardInterrupt:
            detailed_print("Mining loop interrupted by user.")

    def run_all(self):
        detailed_print("----- Starting Full Blockchain Operations -----")
        self.load_blockchain()
        self.validate_blockchain()
        self.send_sample_transaction()
        self.start_mining()
        detailed_print("----- Blockchain Operations Completed -----")


if __name__ == "__main__":
    starter = Start()
    starter.run_all()
