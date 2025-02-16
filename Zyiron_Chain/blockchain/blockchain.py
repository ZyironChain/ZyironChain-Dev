import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
from Zyiron_Chain.blockchain.block_manager import BlockManager
from Zyiron_Chain.blockchain.transaction_manager import TransactionManager
from Zyiron_Chain.blockchain.storage_manager import StorageManager
from Zyiron_Chain.blockchain.miner import Miner
from Zyiron_Chain.database.poc import PoC
import hashlib
from decimal import Decimal
import time
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx, TransactionFactory, sha3_384_hash
from Zyiron_Chain.transactions.transaction_services import TransactionService
from Zyiron_Chain.transactions.fees import FeeModel, FundsAllocator
from Zyiron_Chain.blockchain.block import Block
from decimal import Decimal
import time
import logging


import logging
import time
from decimal import Decimal
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.transactions.fees import FeeModel

class Blockchain:
    # ✅ Correct Genesis Block Target (4 Leading Zeros)
    GENESIS_TARGET = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF

    def __init__(self, storage_manager, transaction_manager, block_manager, key_manager):
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager
        self.block_manager = block_manager
        self.key_manager = key_manager

        self.chain = []
        self.ZERO_HASH = '0' * 96

        # ✅ Initialize Fee Model
        self.fee_model = FeeModel(max_supply=Decimal('84096000'), base_fee_rate=Decimal('0.00015'))
        self.initial_reward = Decimal('100.00')
        self.halving_interval = 420480
        self.max_supply = Decimal('84096000')
        self.total_issued = Decimal('0')
        self.block_time_target = 300  # 5 minutes

        # ✅ Setup Miner
        self.miner = Miner(self.block_manager, self.transaction_manager, self.storage_manager, self.key_manager)

        self._ensure_genesis_block()

    def _ensure_genesis_block(self):
        """
        Ensures the Genesis Block is stored and accessible. If missing, mines it automatically.
        """
        logging.info("[INFO] Checking for stored Genesis Block...")

        try:
            stored_genesis = self.storage_manager.get_block("block:0")
            if stored_genesis:
                logging.info("[SUCCESS] Loaded existing Genesis Block from database.")
                last_block = Block.from_dict(stored_genesis)

                # ✅ Explicitly check if the block is correctly added to the list
                if last_block.hash is None or last_block.index != 0:
                    raise RuntimeError("[ERROR] Corrupted Genesis Block retrieved!")

                self.chain.append(last_block)
                self.block_manager.chain.append(last_block)
                return
        except Exception as e:
            logging.error(f"[ERROR] Failed to retrieve Genesis Block: {str(e)}")

        # ✅ If Genesis Block not found, mine a new one
        logging.info("[INFO] No stored Genesis Block found. Auto-mining Genesis Block...")
        genesis_block = self._create_genesis_block()

        # ✅ Store it and verify storage success
        self.chain.append(genesis_block)
        self.block_manager.chain.append(genesis_block)
        self.storage_manager.store_block(genesis_block, genesis_block.header.difficulty)

        stored_genesis = self.storage_manager.get_block(genesis_block.hash)
        if not stored_genesis:
            raise RuntimeError("[ERROR] Failed to store and verify Genesis Block!")

        logging.info("[SUCCESS] Genesis Block stored and verified!")

    def _create_genesis_block(self):
        """
        Mines and creates the Genesis Block with the updated dynamic difficulty mechanism.
        """
        logging.info("[INFO] Mining Genesis Block...")

        coinbase_tx = CoinbaseTx(
            block_height=0,
            miner_address="genesis",
            reward=Decimal("100.00")
        )

        genesis_block = Block(
            index=0,
            previous_hash=self.ZERO_HASH,  # ✅ Ensures Genesis has no parent
            transactions=[coinbase_tx],
            timestamp=int(time.time()),
            nonce=0,
            difficulty=self.block_manager.GENESIS_TARGET  # ✅ New Genesis Difficulty
        )

        # ✅ Ensure Genesis Block has a valid Proof-of-Work
        while True:
            genesis_block.header.nonce += 1
            genesis_block.hash = genesis_block.calculate_hash()

            if int(genesis_block.hash, 16) < genesis_block.header.difficulty:
                break  # ✅ Found a valid Genesis Block

        logging.info(f"[SUCCESS] Genesis Block mined with Nonce {genesis_block.header.nonce}")
        return genesis_block

    def add_block(self, new_block):
        """
        Adds a new block to the blockchain while ensuring difficulty adjustments and storage.
        """
        if int(new_block.hash, 16) >= new_block.header.difficulty:
            raise ValueError("[ERROR] Invalid Proof-of-Work for block addition.")

        logging.info(f"[INFO] Adding Block {new_block.index} to chain.")

        self.chain.append(new_block)
        self.block_manager.chain.append(new_block)  # ✅ Ensure it's stored in block_manager too

        self.storage_manager.store_block(new_block, new_block.header.difficulty)

        stored_block = self.storage_manager.get_block(new_block.hash)
        if not stored_block:
            raise RuntimeError(f"[ERROR] Failed to retrieve stored block #{new_block.index} from database!")

        logging.info(f"[SUCCESS] Block #{new_block.index} added and verified.")

        # 🔍 Debugging Output:
        print(f"DEBUG: Blockchain Length = {len(self.block_manager.chain)}")
        print(f"DEBUG: Latest Block Hash = {self.block_manager.chain[-1].hash if self.block_manager.chain else 'None'}")



if __name__ == "__main__":
    logging.info("=== Starting Blockchain ===")
    
    try:
        # ✅ Initialize PoC and ensure it correctly loads UnQLite
        poc_instance = PoC()
        
        if not hasattr(poc_instance, "unqlite_db"):
            raise RuntimeError("[ERROR] PoC instance does not have `unqlite_db`. Check database initialization.")

        key_manager = KeyManager()
        storage_manager = StorageManager(poc_instance)  # ✅ Ensure PoC is passed properly
        transaction_manager = TransactionManager(storage_manager, key_manager, poc_instance)
        block_manager = BlockManager(storage_manager, transaction_manager)
        blockchain = Blockchain(storage_manager, transaction_manager, block_manager, key_manager)

        miner = blockchain.miner
        miner.mining_loop(network="mainnet")  # Start mining

        logging.info("=== Done ===")
    except Exception as e:
        logging.error(f"[FATAL ERROR] Blockchain Initialization Failed: {str(e)}")
