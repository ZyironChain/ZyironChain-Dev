import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.utils.key_manager import KeyManager

from Zyiron_Chain.blockchain.transaction_manager import TransactionManager
from Zyiron_Chain.blockchain.storage_manager import StorageManager
from Zyiron_Chain.blockchain.miner import Miner
from Zyiron_Chain.database.poc import PoC
import hashlib
from decimal import Decimal
import time
from Zyiron_Chain.transactions.Blockchain_transaction import  TransactionFactory
from Zyiron_Chain.transactions.transaction_services import TransactionService
from Zyiron_Chain.transactions.fees import FeeModel, FundsAllocator
from Zyiron_Chain.blockchain.block import Block
from decimal import Decimal
import time
import logging
from Zyiron_Chain.blockchain.constants import Constants


from Zyiron_Chain.transactions.coinbase import CoinbaseTx 
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager

def _ensure_genesis_block(self):
    from Zyiron_Chain.blockchain.block_manager import BlockManager
    # rest of the code


import threading




class Blockchain:
    GENESIS_TARGET = Constants.GENESIS_TARGET
    ZERO_HASH = Constants.ZERO_HASH

    def __init__(self, storage_manager, transaction_manager, key_manager):
        logging.info("[DEBUG] Initializing Blockchain...")

        # Network configuration with validation
        self.network = Constants.NETWORK.lower()
        if self.network not in ('mainnet', 'testnet'):
            raise ValueError(f"Invalid network configured: {self.network}. Must be 'mainnet' or 'testnet'")

        logging.info(f"🔹 Initializing on {self.network.upper()} network")

        # Validate network-specific miner keys
        if not key_manager.validate_miner_key(self.network):
            help_option = 4 if self.network == 'mainnet' else 3
            raise RuntimeError(
                f"Miner key missing for {self.network.upper()}\n"
                "Generate keys using:\n"
                "python -m Zyiron_Chain.accounts.key_manager\n"
                f"Then choose '{help_option}. Add new batch of keys to {self.network}'"
            )

        # Rest of initialization remains the same
        self.address_prefix = Constants.ADDRESS_PREFIX
        self.version = Constants.VERSION
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager
        self.key_manager = key_manager
        self.chain = []
        self.constants = Constants  # Add this line
        # Validate miner keys before proceeding
        if not self.key_manager.validate_miner_key(self.network):  # Now passing network parameter
            raise RuntimeError("Invalid miner keys for network")

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
        # Verify Proof-of-Work
        if not new_block.hash or int(new_block.hash, 16) >= new_block.header.difficulty:
            logging.error(f"Invalid Proof-of-Work for block {new_block.index}. Block hash: {new_block.hash}")
            return False

        # Validate previous hash linkage if a previous block is provided
        if prev_block and new_block.previous_hash != prev_block.hash:
            logging.error(f"Block {new_block.index} has invalid previous hash. Expected: {prev_block.hash}, Found: {new_block.previous_hash}")
            return False

        # For blocks beyond the genesis block, check transaction confirmations
        if new_block.index > 0:
            for tx in new_block.transactions:
                try:
                    # Determine transaction type and required confirmations
                    tx_type = PaymentTypeManager().get_transaction_type(tx.tx_id)
                    required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                        tx_type.name, Constants.CONFIRMATION_RULES["minimum_required"]
                    )
                    confirmations = self.storage_manager.get_transaction_confirmations(tx.tx_id)
                    if confirmations is None:
                        logging.error(f"Transaction {tx.tx_id} confirmations could not be retrieved.")
                        return False
                    if confirmations < required_confirmations:
                        logging.error(
                            f"Transaction {tx.tx_id} does not meet required confirmations "
                            f"({required_confirmations}, Confirmations: {confirmations})"
                        )
                        return False
                except Exception as e:
                    logging.error(f"Error validating transaction {tx.tx_id} in block {new_block.index}: {str(e)}")
                    return False
        else:
            # For the genesis block, you can log a message and skip the confirmations check
            logging.info("Skipping transaction confirmations check for the genesis block.")

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
        """
        Create, mine, and validate the Genesis block using network-specific settings,
        without using an explicit thread lock.
        """
        try:
            # Ensure miner address retrieval succeeds.
            miner_address = self.key_manager.get_default_public_key(self.network, "miner")
            if not miner_address:
                raise ValueError("[ERROR] Failed to retrieve miner address for Genesis block.")

            # Ensure reward is a valid Decimal.
            try:
                reward = Decimal(Constants.INITIAL_COINBASE_REWARD)
            except Exception as e:
                raise ValueError(f"[ERROR] Invalid coinbase reward: {str(e)}")

            # Construct the Coinbase transaction.
            coinbase_tx = CoinbaseTx(
                block_height=0,
                miner_address=miner_address,
                reward=reward
            )
            coinbase_tx.fee = Decimal("0")

            # Use the actual system time for the genesis block's timestamp.
            genesis_timestamp = int(time.time())

            # Create the Genesis block.
            genesis_block = Block(
                index=0,
                previous_hash=Constants.ZERO_HASH,
                transactions=[coinbase_tx],
                timestamp=genesis_timestamp,
                nonce=0,
                difficulty=Constants.GENESIS_TARGET,
                miner_address=miner_address
            )

            # Mine the Genesis block (this updates nonce and block hash).
            self._mine_genesis_block(genesis_block)

            # Validate the Genesis block.
            if not self.validate_new_block(genesis_block):
                raise ValueError("[ERROR] Generated Genesis block failed validation.")

            # Store the genesis block via the storage manager.
            self.storage_manager.store_block(genesis_block, Constants.GENESIS_TARGET)
            logging.info(f"[INFO] Genesis block created successfully. Block Hash: {genesis_block.hash}")

            return genesis_block

        except Exception as e:
            logging.error(f"[ERROR] Genesis creation failed: {str(e)}")
            raise




    def _store_and_validate_genesis(self, genesis_block):
        """Store and verify genesis block integrity."""
        try:
            # ✅ Store with proper parameters
            self.storage_manager.store_block(
                block=genesis_block,
                difficulty=Constants.GENESIS_TARGET
            )

            # ✅ Verify storage
            if not self.storage_manager.verify_block_storage(genesis_block):
                raise RuntimeError("[ERROR] Genesis block storage verification failed")

            # ✅ Validate chain properties
            if genesis_block.index != 0:
                raise ValueError("[ERROR] Genesis block must have index 0")

            if genesis_block.previous_hash != Constants.ZERO_HASH:
                raise ValueError("[ERROR] Genesis block has invalid previous hash")

            logging.info("[INFO] Genesis block stored and verified successfully.")

        except Exception as e:
            logging.error(f"[ERROR] Genesis validation failed: {str(e)}")
            raise



    def _mine_genesis_block(self, block=None):
        """Mines the Genesis block with the correct SHA3-384 target difficulty."""
        try:
            if block is None:
                miner_address = self.key_manager.get_default_public_key(self.network, "miner")
                if not miner_address:
                    raise ValueError("[ERROR] Failed to retrieve miner address for Genesis block.")

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

            logging.info("[INFO] Starting mining of Genesis block...")
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

            logging.info(f"[INFO] Genesis block mined successfully with hash: {block.hash}")

            try:
                self.storage_manager.store_block(block, Constants.GENESIS_TARGET)
                logging.info("[INFO] Genesis block stored successfully.")
            except Exception as e:
                logging.error(f"[ERROR] Failed to store Genesis block: {e}")
                raise

        except Exception as e:
            logging.error(f"[ERROR] Mining Genesis block failed: {e}")
            raise







    def _ensure_genesis_block(self):
        """Ensure a valid genesis block exists with proper structure and add it to the chain."""
        try:
            stored_blocks = self.storage_manager.get_all_blocks()
            if stored_blocks:
                genesis_data = stored_blocks[0]
                if genesis_data['header']['index'] != 0 or genesis_data['header']['previous_hash'] != Constants.ZERO_HASH:
                    raise ValueError("Corrupted genesis block in storage")
                genesis_block = Block.from_dict(genesis_data)
                if not self.chain:
                    self.chain.append(genesis_block)
                    self.block_manager.chain.append(genesis_block)
                return

            # **No stored genesis block; create a new one.**
            genesis_block = self._create_genesis_block()
            genesis_block.previous_hash = Constants.ZERO_HASH

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
        try:
            # ✅ Verify proof-of-work
            if not new_block.hash or int(new_block.hash, 16) >= new_block.header.difficulty:
                raise ValueError("[ERROR] Invalid Proof-of-Work")

            # ✅ Append the block to in-memory chain
            self.chain.append(new_block)
            self.block_manager.chain.append(new_block)

            # ✅ Store the block in the storage
            self.storage_manager.store_block(new_block, new_block.header.difficulty)

            # ✅ Confirm all transactions according to confirmation rules
            for tx in new_block.transactions:
                tx_type = PaymentTypeManager().get_transaction_type(tx.tx_id)
                required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                    tx_type.name, Constants.CONFIRMATION_RULES["minimum_required"]
                )
                self.storage_manager.confirm_transaction(tx.tx_id, required_confirmations)

            # ✅ Verify that the block was properly stored
            if not self.storage_manager.get_block(new_block.hash):
                raise RuntimeError("[ERROR] Block storage verification failed")

            logging.info(f"[INFO] Successfully added block {new_block.index} [Hash: {new_block.hash[:12]}...]")

        except Exception as e:
            logging.error(f"[ERROR] Block addition failed: {str(e)}")
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
        """Create a properly formatted coinbase transaction."""
        try:
            # ✅ Validate block height
            if block_height < 0:
                raise ValueError("[ERROR] Block height must be a non-negative integer.")

            # ✅ Get miner address from KeyManager
            miner_address = self.key_manager.get_default_public_key(Constants.NETWORK, "miner")
            if not miner_address:
                raise ValueError("[ERROR] Failed to retrieve miner address.")

            # ✅ Use reward value from constants
            reward = Decimal(Constants.INITIAL_COINBASE_REWARD)
            if reward <= 0:
                raise ValueError("[ERROR] Coinbase reward must be greater than zero.")

            # ✅ Construct the coinbase transaction
            return CoinbaseTx(
                block_height=block_height,
                miner_address=miner_address,
                reward=reward
            )

        except Exception as e:
            logging.error(f"[ERROR] Coinbase creation failed: {str(e)}")
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

