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
from Zyiron_Chain.blockchain.constants import Constants

import logging
import time
from decimal import Decimal
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager
class Blockchain:
    GENESIS_TARGET = Constants.GENESIS_TARGET
    ZERO_HASH = Constants.ZERO_HASH

    def __init__(self, storage_manager, transaction_manager, key_manager):
        logging.info("[DEBUG] Initializing Blockchain...")

        # ✅ Determine the active network dynamically
        self.network = Constants.NETWORK  
        self.address_prefix = Constants.ADDRESS_PREFIX  # ✅ Fetches from constants dynamically
        self.version = Constants.VERSION  # ✅ Fetches blockchain version

        logging.info(f"🔹 Blockchain v{self.version} initialized on {self.network.upper()} ({self.address_prefix})")

        # ✅ Initialize core components
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager
        self.key_manager = key_manager
        self.chain = []

        if not all([self.storage_manager, self.transaction_manager, self.key_manager]):
            raise ValueError("Missing required dependencies for Blockchain")

        try:
            from Zyiron_Chain.blockchain.block_manager import BlockManager  
            self.block_manager = BlockManager(
                blockchain=self,
                storage_manager=self.storage_manager,
                transaction_manager=self.transaction_manager
            )
        except Exception as e:
            logging.error(f"BlockManager init failed: {str(e)}")
            raise

        # ✅ Initialize Fee Model using Constants
        self.fee_model = FeeModel(
            max_supply=Decimal(Constants.MAX_SUPPLY),
            base_fee_rate=Decimal(Constants.MIN_TRANSACTION_FEE)  
        )

        # ✅ Initialize Miner with Network Awareness
        self.miner = Miner(
            self.block_manager,
            self.transaction_manager,
            self.storage_manager,
            self.key_manager
        )

        # ✅ Load Blockchain Data or Create a New Chain
        try:
            if stored_blocks := self.storage_manager.get_all_blocks():
                self._load_chain_from_storage()
        except Exception as e:
            logging.error(f"Chain reset: {str(e)}")
            self.storage_manager.purge_chain()

        # ✅ Ensure Genesis Block Exists
        self._ensure_genesis_block()

        logging.info(f"✅ Blockchain v{self.version} successfully initialized on {self.network.upper()}")


    def validate_new_block(self, new_block: Block, prev_block: Block = None) -> bool:
        """
        Validate a new block before adding it to the chain.
        """
        # ✅ Verify Proof-of-Work
        if int(new_block.hash, 16) >= new_block.header.difficulty:
            logging.error(f"Invalid Proof-of-Work for block {new_block.index}")
            return False

        # ✅ Validate previous hash linkage
        if prev_block and new_block.previous_hash != prev_block.hash:
            logging.error(f"Block {new_block.index} has invalid previous hash")
            return False

        # ✅ Validate transactions inside the block
        for tx in new_block.transactions:
            tx_type = PaymentTypeManager().get_transaction_type(tx.tx_id)
            required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(tx_type.name, Constants.CONFIRMATION_RULES["minimum_required"])
            
            if self.storage_manager.get_transaction_confirmations(tx.tx_id) < required_confirmations:
                logging.error(f"Transaction {tx.tx_id} does not meet required confirmations ({required_confirmations})")
                return False

        return True



    def _load_chain_from_storage(self):
        """Load and validate stored blocks"""
        try:
            stored_blocks = self.storage_manager.get_all_blocks()
            for block_data in stored_blocks:
                block = Block.from_dict(block_data)
                
                # Validate each block against chain rules
                if not self.validate_new_block(block):
                    raise ValueError(f"Invalid block in storage: {block.hash[:12]}...")

                self.chain.append(block)
                self.block_manager.chain.append(block)

            logging.info(f"Loaded {len(self.chain)} blocks from storage")

        except Exception as e:
            logging.error(f"Chain loading failed: {str(e)}")
            self.chain.clear()
            self.block_manager.chain.clear()
            raise

    # In your Blockchain class
    def _create_genesis_block(self):
        """Create, mine, and validate the Genesis block using network-specific settings."""
        try:
            miner_address = self.key_manager.get_default_public_key(self.network, "miner")
            coinbase_tx = CoinbaseTx(
                block_height=0,
                miner_address=miner_address,
                reward=Decimal(Constants.INITIAL_COINBASE_REWARD)
            )
            coinbase_tx.fee = Decimal("0")

            genesis_block = Block(
                index=0,
                previous_hash=Constants.ZERO_HASH,
                transactions=[coinbase_tx],
                timestamp=int(time.time()),
                nonce=0,
                difficulty=Constants.GENESIS_TARGET,  
                miner_address=miner_address
            )
            self._mine_genesis_block(genesis_block)
            if not self.validate_new_block(genesis_block):
                raise ValueError("Generated Genesis block failed validation")
            return genesis_block
        except Exception as e:
            logging.error(f"Genesis creation failed: {str(e)}")
            raise




    def _store_and_validate_genesis(self, genesis_block):
        """Store and verify genesis block integrity"""
        try:
            # Store with proper parameters
            self.storage_manager.store_block(
                block=genesis_block,
                difficulty=Constants.GENESIS_TARGET
            )
            
            # Verify storage
            if not self.storage_manager.verify_block_storage(genesis_block):
                raise RuntimeError("Genesis block storage verification failed")

            # Validate chain properties
            if genesis_block.index != 0:
                raise ValueError("Genesis block must have index 0")
            
            if genesis_block.previous_hash != self.ZERO_HASH:
                raise ValueError("Genesis block has invalid previous hash")

        except Exception as e:
            logging.error(f"Genesis validation failed: {str(e)}")
            raise


    def _mine_genesis_block(self, block=None):
        """Mines the Genesis block with the correct SHA3-384 target difficulty."""
        if block is None:
            miner_address = self.key_manager.get_default_public_key(self.network, "miner")
            coinbase_tx = CoinbaseTx(
                block_height=0,
                miner_address=miner_address,
                reward=Decimal(Constants.INITIAL_COINBASE_REWARD)
            )
            coinbase_tx.fee = Decimal("0")
            block = Block(
                index=0,
                previous_hash=Constants.ZERO_HASH,
                transactions=[coinbase_tx],
                timestamp=int(time.time()),
                nonce=0,
                difficulty=Constants.GENESIS_TARGET  
            )

        logging.info("Mining Genesis Block...")
        start_time = time.time()
        last_update = start_time

        while int(block.hash, 16) >= block.difficulty:
            block.header.nonce += 1
            block.hash = block.calculate_hash()
            current_time = time.time()

            if current_time - last_update >= 1:
                elapsed = int(current_time - start_time)
                print(f"[LIVE] Mining Genesis Block | Nonce: {block.header.nonce}, Time: {elapsed}s")
                last_update = current_time

        logging.info(f"✅ Genesis block mined with hash: {block.hash}")
        self.storage_manager.store_block(block, Constants.GENESIS_TARGET)







    def _ensure_genesis_block(self):
        """Ensure a valid genesis block exists with proper structure and add it to the chain."""
        try:
            stored_blocks = self.storage_manager.get_all_blocks()
            if stored_blocks:
                genesis_data = stored_blocks[0]
                if genesis_data['header']['index'] != 0 or genesis_data['header']['previous_hash'] != self.ZERO_HASH:
                    raise ValueError("Corrupted genesis block in storage")
                genesis_block = Block.from_dict(genesis_data)
                if not self.chain:
                    self.chain.append(genesis_block)
                    self.block_manager.chain.append(genesis_block)
                return

            # **No stored genesis block; create a new one.**
            genesis_block = self._create_genesis_block()
            genesis_block.previous_hash = self.ZERO_HASH

            if not self.validate_new_block(genesis_block):
                raise ValueError("Generated Genesis block failed validation")

            self._store_and_validate_genesis(genesis_block)

            # Add the Genesis Block to the chain.
            self.chain.append(genesis_block)
            self.block_manager.chain.append(genesis_block)

            logging.info("✅ Successfully initialized new Genesis Block")

        except Exception as e:
            logging.error(f"Genesis initialization failed: {str(e)}")
            logging.info("⚡ Purging corrupted chain data...")
            self.storage_manager.purge_chain()
            raise



    def add_block(self, new_block):
        """Add validated block to both chain and storage."""
        if int(new_block.hash, 16) >= new_block.header.difficulty:
            raise ValueError("Invalid Proof-of-Work")

        try:
            self.chain.append(new_block)
            self.block_manager.chain.append(new_block)

            # ✅ Store the block in storage
            self.storage_manager.store_block(new_block, new_block.header.difficulty)

            # ✅ Ensure transactions are confirmed according to constants
            for tx in new_block.transactions:
                tx_type = PaymentTypeManager().get_transaction_type(tx.tx_id)
                required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(tx_type.name, Constants.CONFIRMATION_RULES["minimum_required"])
                
                self.storage_manager.confirm_transaction(tx.tx_id, required_confirmations)

            if not self.storage_manager.get_block(new_block.hash):
                raise RuntimeError("Block storage verification failed")

            logging.info(f"Added block {new_block.index} [Hash: {new_block.hash[:12]}...]")

        except Exception as e:
            logging.error(f"Block addition failed: {str(e)}")
            self.chain.pop()
            self.block_manager.chain.pop()
            raise



    def _validate_block_structure(self, block: Block) -> bool:
        """Validate critical block fields"""
        return all([
            hasattr(block, 'index'),
            hasattr(block.header, 'previous_hash'),
            hasattr(block.header, 'merkle_root'),
            hasattr(block.header, 'timestamp'),
            block.hash == block.calculate_hash()
        ])


    def _create_coinbase(self, block_height: int) -> CoinbaseTx:
        """Create a properly formatted coinbase transaction"""
        try:
            # Get miner address from KeyManager
            miner_address = self.key_manager.get_default_public_key("mainnet", "miner")
            reward = Decimal("100.00")
            
            return CoinbaseTx(
                block_height=block_height,
                miner_address=miner_address,
                reward=reward
            )
        except Exception as e:
            logging.error(f"Coinbase creation failed: {str(e)}")
            raise

    def _validate_coinbase(self, tx):
        """
        Ensure the coinbase transaction follows protocol rules:
        - No inputs.
        - Exactly one output.
        - Transaction type is "COINBASE".
        - Fee is zero.
        """
        from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx  # Lazy import
        return (
            len(tx.inputs) == 0 and
            len(tx.outputs) == 1 and
            tx.type == "COINBASE" and
            tx.fee == Decimal(0)
        )





if __name__ == "__main__":
    logging.info("=== Starting Blockchain ===")
    
    try:
        key_manager = KeyManager()
        
        if not key_manager.validate_miner_key("mainnet"):
            raise RuntimeError(
                "Miner key missing in KeyManager.\n"
                "First generate keys using:\n"
                "python -m Zyiron_Chain.accounts.key_manager\n"
                "Then choose '4. Add new batch of keys to mainnet'"
            )

        # ✅ Debug: Print Storage & Transaction Manager Before Blockchain Initialization
        poc_instance = PoC()
        storage_manager = StorageManager(poc_instance)
        transaction_manager = TransactionManager(storage_manager, key_manager, poc_instance)

        logging.info(f"[DEBUG] Creating Blockchain instance with {storage_manager}, {transaction_manager}")

        # ✅ FIX: Ensure `blockchain` instance is created properly
        blockchain = Blockchain(
            storage_manager=storage_manager,
            transaction_manager=transaction_manager,
            key_manager=key_manager
        )

        logging.info("[DEBUG] Blockchain instance created successfully.")

        # ✅ Start Mining
        miner = blockchain.miner
        miner.mining_loop(network="mainnet")

        logging.info("=== Blockchain Operational ===")
        
    except Exception as e:
        logging.error(f"[FATAL ERROR] Initialization Failed: {str(e)}")

