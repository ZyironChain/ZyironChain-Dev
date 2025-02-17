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

class Blockchain:
    GENESIS_TARGET = Constants.GENESIS_TARGET
    ZERO_HASH = Constants.ZERO_HASH

    def __init__(self, storage_manager, transaction_manager, block_manager, key_manager):
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager
        self.block_manager = block_manager
        self.key_manager = key_manager

        self.chain = []
        self.fee_model = FeeModel(
            max_supply=Decimal('84096000'),
            base_fee_rate=Decimal('0.00015')
        )
        self.miner = Miner(self.block_manager, self.transaction_manager, 
                        self.storage_manager, self.key_manager)

        try:
            stored_blocks = self.storage_manager.get_all_blocks()
            if stored_blocks:
                self._load_chain_from_storage()
        except Exception as e:
            logging.error(f"Chain reset required: {str(e)}")
            self.storage_manager.purge_chain()
        # Ensure genesis block exists and is loaded
        self._ensure_genesis_block()







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
        Create, mine, and validate the Genesis block with proper attributes,
        using SHA3-384 and a difficulty target that requires 4 leading zeros.
        """
        try:
            miner_address = self.key_manager.get_default_public_key("mainnet", "miner")
            coinbase_tx = CoinbaseTx(
                block_height=0,
                miner_address=miner_address,
                reward=Decimal("100.00")
            )
            coinbase_tx.fee = Decimal("0")  # Ensure coinbase fee is zero

            genesis_block = Block(
                index=0,
                previous_hash=Constants.ZERO_HASH,
                transactions=[coinbase_tx],
                timestamp=int(time.time()),
                nonce=0,
                difficulty=Constants.GENESIS_TARGET,  # Target requiring 4 leading zeros
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
        """
        Mine the genesis block using SHA3-384:
        Iterate the nonce until the block's hash (computed with SHA3-384)
        is below the difficulty target (which requires a hash starting with 4 zeros).
        Shows live nonce count, attempts, and elapsed time every second.
        """
        from Zyiron_Chain.blockchain.block import Block  # Lazy import
        if block is None:
            miner_address = self.key_manager.get_default_public_key("mainnet", "miner")
            from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx  # Lazy import
            coinbase_tx = CoinbaseTx(
                block_height=0,
                miner_address=miner_address,
                reward=Decimal("100.00")
            )
            coinbase_tx.fee = Decimal("0")
            block = Block(
                index=0,
                previous_hash=Constants.ZERO_HASH,
                transactions=[coinbase_tx],
                timestamp=int(time.time()),
                nonce=0,
                difficulty=Constants.GENESIS_TARGET,  # Using our new target for 4 zeros
                miner_address=miner_address
            )
        logging.info("Mining genesis block...")
        start_time = time.time()
        last_update = start_time
        attempts = 0

        # Loop: recalculate the SHA3-384 hash until it meets the target.
        while int(block.hash, 16) >= block.header.difficulty:
            block.header.nonce += 1
            block.hash = block.calculate_hash()  # calculate_hash() uses hashlib.sha3_384
            attempts += 1
            current_time = time.time()
            if current_time - last_update >= 1:  # Print every second
                elapsed = current_time - start_time
                print(f"[LIVE] Nonce: {block.header.nonce}, Attempts: {attempts}, Elapsed Time: {elapsed:.2f}s")
                last_update = current_time

        logging.info(f"Genesis block mined: nonce={block.header.nonce}, hash={block.hash}")
        self.storage_manager.store_block(block, Constants.GENESIS_TARGET)
        if not self.storage_manager.verify_block_storage(block):
            raise RuntimeError("Genesis block storage verification failed")







    def _ensure_genesis_block(self):
        """Ensure a valid genesis block exists with proper structure and add it to the chain."""
        try:
            stored_blocks = self.storage_manager.get_all_blocks()
            if stored_blocks:
                genesis_data = stored_blocks[0]
                if genesis_data['header']['index'] != 0 or genesis_data['header']['previous_hash'] != self.ZERO_HASH:
                    raise ValueError("Corrupted genesis block in storage")
                genesis_block = Block.from_dict(genesis_data)
                # Add the genesis block to the chain if not already present.
                if not self.chain:
                    self.chain.append(genesis_block)
                    self.block_manager.chain.append(genesis_block)
                return
            # No stored genesis block; create a new one.
            genesis_block = self._create_genesis_block()
            genesis_block.previous_hash = self.ZERO_HASH
            if not self.validate_new_block(genesis_block):
                raise ValueError("Generated genesis block failed validation")
            self._store_and_validate_genesis(genesis_block)
            # Now add the newly created genesis block to the chain.
            self.chain.append(genesis_block)
            self.block_manager.chain.append(genesis_block)
            logging.info("Successfully initialized new genesis block")
        except Exception as e:
            logging.error(f"Genesis initialization failed: {str(e)}")
            logging.info("Purging corrupted chain data...")
            self.storage_manager.purge_chain()
            raise



    def add_block(self, new_block):
        """Add validated block to both chain and storage"""
        if int(new_block.hash, 16) >= new_block.header.difficulty:
            raise ValueError("Invalid Proof-of-Work")

        try:
            # Add to memory chain
            self.chain.append(new_block)
            self.block_manager.chain.append(new_block)

            # Persist to storage
            self.storage_manager.store_block(new_block, new_block.header.difficulty)

            # Validate storage
            if not self.storage_manager.get_block(new_block.hash):
                raise RuntimeError("Block storage verification failed")

            logging.info(f"Added block {new_block.index} [Hash: {new_block.hash[:12]}...]")
            
        except Exception as e:
            logging.error(f"Block addition failed: {str(e)}")
            self.chain.pop()
            self.block_manager.chain.pop()
            raise
        

    def validate_new_block(self, new_block: Block, prev_block: Block = None) -> bool:
        """
        Validate a new block before adding to the chain
        """
        # 1. Verify Proof-of-Work
        if int(new_block.hash, 16) >= new_block.header.difficulty:
            logging.error(f"Invalid Proof-of-Work for block {new_block.index}")
            return False

        # 2. Validate previous hash linkage
        if prev_block and new_block.previous_hash != prev_block.hash:
            logging.error(f"Block {new_block.index} has invalid previous hash")
            return False

        # 3. Validate coinbase transaction structure
        if len(new_block.transactions) == 0:
            logging.error("Block contains no transactions")
            return False
            
        coinbase_tx = new_block.transactions[0]
        if not isinstance(coinbase_tx, CoinbaseTx):
            logging.error("First transaction must be CoinbaseTx instance")
            return False
            
        if not (len(coinbase_tx.inputs) == 0 and 
                len(coinbase_tx.outputs) == 1 and 
                coinbase_tx.reward > 0):
            logging.error("Invalid coinbase transaction structure")
            return False

        # 4. Validate transaction signatures (skip coinbase)
        for tx in new_block.transactions[1:]:
            if not self.transaction_manager.validate_transaction(tx):
                logging.error(f"Invalid transaction in block {new_block.index}: {tx.tx_id}")
                return False

        # 5. Validate timestamp sequence
        if prev_block and new_block.header.timestamp <= prev_block.header.timestamp:
            logging.error(f"Block {new_block.index} has invalid timestamp")
            return False

        return True
            


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
        # Initialize KeyManager with existing keys
        key_manager = KeyManager()
        
        # Verify existing miner keys without generation
        if not key_manager.validate_miner_key("mainnet"):
            raise RuntimeError(
                "Miner key missing in KeyManager.\n"
                "First generate keys using:\n"
                "python -m Zyiron_Chain.accounts.key_manager\n"
                "Then choose '4. Add new batch of keys to mainnet'"
            )

        # Rest of initialization remains the same
        poc_instance = PoC()
        storage_manager = StorageManager(poc_instance)
        transaction_manager = TransactionManager(storage_manager, key_manager, poc_instance)
        block_manager = BlockManager(storage_manager, transaction_manager)
        blockchain = Blockchain(storage_manager, transaction_manager, block_manager, key_manager)

        miner = blockchain.miner
        miner.mining_loop(network="mainnet")
        logging.info("=== Blockchain Operational ===")
        
    except Exception as e:
        logging.error(f"[FATAL ERROR] Initialization Failed: {str(e)}")
        logging.info("Recovery Steps:")
        logging.info("1. Launch Key Manager: python -m Zyiron_Chain.accounts.key_manager")
        logging.info("2. Select option 4 to generate mainnet miner keys")
        logging.info("3. Restart the blockchain")