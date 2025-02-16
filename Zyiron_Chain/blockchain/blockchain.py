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
        
        # Initialize chain state
        self._load_chain_from_storage()
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
        """Create and mine genesis block with proper validation"""
        try:
            miner_address = self.key_manager.get_default_public_key("mainnet", "miner")
            coinbase_tx = CoinbaseTx(
                block_height=0,
                miner_address=miner_address,
                reward=Decimal("100.00")
            )

            genesis_block = Block(
                index=0,
                previous_hash=self.ZERO_HASH,
                transactions=[coinbase_tx],
                difficulty=self.GENESIS_TARGET,
                miner_address=miner_address
            )

            # Mine the genesis block
            while int(genesis_block.hash, 16) >= genesis_block.header.difficulty:
                genesis_block.header.nonce += 1
                genesis_block.hash = genesis_block.calculate_hash()

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


    def _mine_genesis_block(self, block: Block):
        """Mine genesis block with proper validation"""
        while int(block.hash, 16) >= block.header.difficulty:
            block.header.nonce += 1
            block.hash = block.calculate_hash()

        # Store and verify
        self.storage_manager.store_block(block, Constants.GENESIS_TARGET)
        if not self.storage_manager.verify_block_storage(block):
            raise RuntimeError("Genesis block storage verification failed")





    def _ensure_genesis_block(self):
        """Ensure valid genesis block exists in both storage and memory"""
        try:
            # Check if genesis exists in loaded chain
            if any(block.index == 0 for block in self.chain):
                return

            # Create and store new genesis block
            genesis_block = self._create_genesis_block()
            self._store_and_validate_genesis(genesis_block)
            
            # Add to both chains
            self.chain.append(genesis_block)
            self.block_manager.chain.append(genesis_block)

        except Exception as e:
            logging.error(f"Genesis initialization failed: {str(e)}")
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

        # 3. Validate coinbase transaction
        coinbase_tx = new_block.transactions[0]
        if not isinstance(coinbase_tx, CoinbaseTx):
            logging.error("First transaction must be coinbase")
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

    def _validate_coinbase(self, tx: CoinbaseTx) -> bool:
        """Ensure coinbase transaction follows protocol rules"""
        return (
            len(tx.inputs) == 0
            and len(tx.outputs) == 1
            and tx.type == "COINBASE"
            and tx.fee == Decimal(0)
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