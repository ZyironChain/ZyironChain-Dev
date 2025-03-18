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
from Zyiron_Chain.storage.block_storage import BlockStorage
from Zyiron_Chain.storage.tx_storage import TxStorage
from Zyiron_Chain.storage.utxostorage import UTXOStorage
from Zyiron_Chain.storage.mempool_storage import MempoolStorage

# -------------------------------------------------------------------------
# Imports for blockchain, transactions, keys, and miner
# -------------------------------------------------------------------------
from Zyiron_Chain.blockchain.blockchain import Blockchain
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.miner.miner import Miner
from Zyiron_Chain.transactions.transaction_manager import TransactionManager
from Zyiron_Chain.accounts.key_manager import KeyManager
from Zyiron_Chain.storage.lmdatabase import LMDBManager  # For LMDB manager creation
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.blockchain.block_manager import BlockManager  # Import BlockManager
from Zyiron_Chain.blockchain.genesis_block import GenesisBlockManager  # ✅ Import GenesisBlockManager
from Zyiron_Chain.transactions.fees import FeeModel

def detailed_print(message: str):
    """Helper function for detailed print-based debugging."""
    print(f"[START] {message}")

class Start:
    def __init__(self):
        detailed_print("Initializing blockchain project...")
        detailed_print(f"Network: {Constants.NETWORK}, Version: {Constants.VERSION}")

        # ✅ 1. Initialize KeyManager
        detailed_print("Initializing KeyManager...")
        self.key_manager = KeyManager()

        # ✅ 2. Initialize FeeModel
        detailed_print("Initializing FeeModel...")
        self.fee_model = FeeModel(Constants.MAX_SUPPLY)

        # ✅ 3. Initialize TxStorage (Pass FeeModel)
        detailed_print("Initializing TxStorage...")
        self.tx_storage = TxStorage(fee_model=self.fee_model)

        # ✅ 4. Initialize Block Storage & Metadata (Pass TxStorage & KeyManager)
        detailed_print("Initializing block storage and metadata...")
        self.block_storage = WholeBlockData(tx_storage=self.tx_storage, key_manager=self.key_manager)  # ✅ FIXED

        # ✅ Ensure BlockMetadata Receives Shared LMDB Instances
        self.block_metadata = BlockMetadata(
            block_metadata_db=self.block_storage.block_metadata_db,
            txindex_db=self.block_storage.txindex_db,
            tx_storage=self.tx_storage,
            current_block_file=self.block_storage.current_block_file
        )

        # ✅ 5. Initialize UTXO Storage (Ensure LMDB paths exist)
        utxo_db_path = Constants.DATABASES.get("utxo")
        utxo_history_path = Constants.DATABASES.get("utxo_history")

        detailed_print(f"Initializing LMDB managers for UTXO at {utxo_db_path} and UTXO history at {utxo_history_path}...")
        utxo_db = LMDBManager(utxo_db_path)  # ✅ Corrected
        utxo_history_db = LMDBManager(utxo_history_path)  # ✅ Fixed, No Nested Instantiation

        # ✅ 6. Initialize UTXO Manager (Pass LMDB and Peer Constants)
        from Zyiron_Chain.network.peerconstant import PeerConstants
        peer_constants = PeerConstants()
        detailed_print(f"Initializing UTXOManager with peer id '{peer_constants.PEER_USER_ID}'...")
        utxo_manager = UTXOManager(utxo_db)

        # ✅ 7. Initialize UTXO Storage
        self.utxo_storage = UTXOStorage(
            utxo_db=utxo_db,
            utxo_history_db=utxo_history_db,
            utxo_manager=utxo_manager
        )
        detailed_print("UTXOStorage initialized successfully.")

        # ✅ 8. Initialize Transaction Manager (Ensure it gets TxStorage)
        detailed_print("Initializing TransactionManager...")
        self.transaction_manager = TransactionManager(
            block_storage=self.block_storage,
            block_metadata=self.block_metadata,
            tx_storage=self.tx_storage,  # ✅ Ensure correct storage is passed
            utxo_manager=utxo_manager,
            key_manager=self.key_manager
        )

        # ✅ 9. Initialize Mempool Storage (Pass Transaction Manager)
        detailed_print("Initializing MempoolStorage...")
        self.mempool_storage = MempoolStorage(self.transaction_manager)
        detailed_print("MempoolStorage initialized successfully.")

        # ✅ 10. Initialize Blockchain (Ensure All Components Are Passed)
        detailed_print("Initializing Blockchain...")
        try:
            self.blockchain = Blockchain(
                block_storage=self.block_storage,
                block_metadata=self.block_metadata,
                tx_storage=self.tx_storage,  # ✅ Ensure TxStorage is passed
                utxo_storage=self.utxo_storage,
                transaction_manager=self.transaction_manager,
                key_manager=self.key_manager
            )
            detailed_print("[Blockchain] ✅ SUCCESS: Blockchain initialized successfully.")
        except Exception as e:
            detailed_print(f"[Blockchain] ❌ ERROR: Blockchain initialization failed: {e}")
            raise

        # ✅ 11. Initialize BlockManager (Ensure Blockchain and Storage Are Passed)
        detailed_print("Initializing BlockManager...")
        self.block_manager = BlockManager(
            blockchain=self.blockchain,
            block_storage=self.block_storage,
            block_metadata=self.block_metadata,
            tx_storage=self.tx_storage,
            transaction_manager=self.transaction_manager
        )

        # ✅ 12. Initialize Genesis Block Manager (Pass BlockManager's Chain)
        detailed_print("Initializing GenesisBlockManager...")
        self.genesis_block_manager = GenesisBlockManager(
            block_storage=self.block_storage,
            block_metadata=self.block_metadata,
            key_manager=self.key_manager,  # ✅ Ensured key_manager is passed
            chain=self.block_manager.blockchain,  # ✅ Ensured the correct chain object is passed
            block_manager=self.block_manager
        )

        # ✅ 13. Initialize Miner (Ensure All Components Are Passed)
        detailed_print("Initializing Miner...")
        self.miner = Miner(
            blockchain=self.blockchain,
            block_manager=self.block_manager,
            block_metadata=self.block_metadata,
            block_storage=self.block_storage,
            transaction_manager=self.transaction_manager,
            key_manager=self.key_manager,
            mempool_storage=self.mempool_storage,
            genesis_block_manager=self.genesis_block_manager
        )

        detailed_print("[Start] ✅ SUCCESS: Blockchain system fully initialized.")


    def load_blockchain(self):
        """
        Load blockchain data from storage.
        """
        detailed_print("Loading blockchain data from storage...")
        try:
            chain = self.blockchain.load_chain_from_storage()  # Assumes Blockchain has this method
            if chain is None or not isinstance(chain, list):
                detailed_print("[load_blockchain] WARNING: Blockchain data is empty or invalid.")
                return []
            detailed_print(f"Loaded {len(chain)} blocks from storage.")
            return chain
        except Exception as e:
            detailed_print(f"[load_blockchain] ERROR: Failed to load blockchain from storage: {e}")
            return []

    def validate_blockchain(self):
        """
        Validate blockchain integrity.
        """
        detailed_print("Validating blockchain integrity...")
        try:
            valid = self.blockchain.validate_chain()  # Assumes Blockchain.validate_chain() exists
            if valid is None:
                detailed_print("[validate_blockchain] WARNING: Validation returned None. Possible corruption detected.")
                return False
            elif valid:
                detailed_print("Blockchain validation passed.")
            else:
                detailed_print("Blockchain validation failed.")
            return valid
        except Exception as e:
            detailed_print(f"[validate_blockchain] ERROR: Blockchain validation failed: {e}")
            return False

    def send_sample_transaction(self):
        """
        Create and send a sample transaction.
        """
        detailed_print("Preparing sample transaction...")
        try:
            sender_address = self.key_manager.get_default_public_key(Constants.NETWORK, "user")
            if not sender_address:
                detailed_print("[send_sample_transaction] ERROR: Failed to retrieve sender's public key.")
                return

            tx_data = self.transaction_manager.create_transaction(
                sender=sender_address,  # ✅ Added sender validation
                recipient_address="sample_recipient_address",  # ✅ Updated parameter
                amount=Decimal("0.9"),
                block_size=Constants.MAX_BLOCK_SIZE_MB / (1024 * 1024),  # Convert bytes to MB
                payment_type="STANDARD"
            )

            if tx_data and "transaction" in tx_data and hasattr(tx_data["transaction"], "tx_id"):
                detailed_print(f"Sample transaction prepared with TX ID: {tx_data['transaction'].tx_id}")
            else:
                detailed_print("[send_sample_transaction] ERROR: Failed to create a valid sample transaction.")

        except Exception as e:
            detailed_print(f"[send_sample_transaction] ERROR: Error preparing sample transaction: {e}")

    def start_mining(self):
        """
        Start the mining loop. Handles errors and user interruptions.
        """
        detailed_print("Starting mining loop. Press Ctrl+C to stop.")
        try:
            if not hasattr(self.miner, "mining_loop") or not callable(self.miner.mining_loop):
                detailed_print("[start_mining] ERROR: Mining loop function not found. Miner instance may be invalid.")
                return

            self.miner.mining_loop()
        except KeyboardInterrupt:
            detailed_print("Mining loop interrupted by user.")
        except Exception as e:
            detailed_print(f"[start_mining] ERROR: Miner encountered an issue: {e}")

    def run_all(self):
        """
        Run all blockchain operations in sequence.
        """
        detailed_print("----- Starting Full Blockchain Operations -----")
        try:
            chain = self.load_blockchain()
            if not chain:
                detailed_print("[run_all] ERROR: Blockchain is empty. Cannot proceed.")
                return

            valid_chain = self.validate_blockchain()
            if not valid_chain:
                detailed_print("[run_all] ERROR: Blockchain validation failed. Aborting operations.")
                return

            self.send_sample_transaction()
            self.start_mining()
            detailed_print("----- Blockchain Operations Completed -----")
        except Exception as e:
            detailed_print(f"[run_all] ERROR: Blockchain operations failed: {e}")

if __name__ == "__main__":
    starter = Start()
    starter.run_all()
