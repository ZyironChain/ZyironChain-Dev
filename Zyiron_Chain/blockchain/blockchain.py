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
from Zyiron_Chain.blockchain.utils.hashing import Hashing 

def _ensure_genesis_block(self):
    from Zyiron_Chain.blockchain.block_manager import BlockManager
    # rest of the code


import threading




class Blockchain:
    GENESIS_TARGET = Constants.GENESIS_TARGET
    ZERO_HASH = Constants.ZERO_HASH

    def __init__(self, storage_manager, transaction_manager, key_manager):
        logging.info("[DEBUG] Initializing Blockchain...")

        # ✅ Network Configuration with Validation
        self.network = Constants.NETWORK.lower()
        if self.network not in ('mainnet', 'testnet'):
            raise ValueError(f"Invalid network configured: {self.network}. Must be 'mainnet' or 'testnet'")

        logging.info(f"🔹 Initializing on {self.network.upper()} network")

        # ✅ Validate Network-Specific Miner Keys
        if not key_manager.validate_miner_key(self.network):
            help_option = 4 if self.network == 'mainnet' else 3
            raise RuntimeError(
                f"Miner key missing for {self.network.upper()}\n"
                "Generate keys using:\n"
                "python -m Zyiron_Chain.accounts.key_manager\n"
                f"Then choose '{help_option}. Add new batch of keys to {self.network}'"
            )

        # ✅ Core Blockchain Components
        self.address_prefix = Constants.ADDRESS_PREFIX
        self.version = Constants.VERSION
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager
        self.key_manager = key_manager
        self.chain = []
        self.constants = Constants  # ✅ Ensures access to updated constants

        # ✅ Validate Miner Keys Before Proceeding
        if not self.key_manager.validate_miner_key(self.network):  # ✅ Now passing network parameter
            raise RuntimeError("[ERROR] Invalid miner keys for network")

        # ✅ Block Manager Initialization
        try:
            from Zyiron_Chain.blockchain.block_manager import BlockManager
            self.block_manager = BlockManager(
                blockchain=self,
                storage_manager=self.storage_manager,
                transaction_manager=self.transaction_manager
            )
        except Exception as e:
            logging.error(f"[ERROR] BlockManager init failed: {str(e)}")
            raise

        # ✅ Initialize Fee Model with Updated Constants
        self.fee_model = FeeModel(
            max_supply=Decimal(Constants.MAX_SUPPLY),
            base_fee_rate=Decimal(Constants.MIN_TRANSACTION_FEE)
        )

        # ✅ Miner Initialization with Hashing Integration
        self.miner = Miner(
            self.block_manager,
            self.transaction_manager,
            self.storage_manager,
            self.key_manager
        )

        # ✅ Load Blockchain Data or Create a New Chain
        try:
            stored_blocks = self.storage_manager.get_all_blocks()
            if stored_blocks:
                self._load_chain_from_storage()
        except Exception as e:
            logging.error(f"[ERROR] Chain reset: {str(e)}")
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
                    # Double hash the transaction ID
                    tx.tx_id = Hashing.double_sha3_384(tx.tx_id.encode())

                    # Determine transaction type and required confirmations
                    tx_type = PaymentTypeManager().get_transaction_type(tx.tx_id)
                    required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                        tx_type.name, Constants.TRANSACTION_CONFIRMATIONS["STANDARD"]
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
        try:
            stored_blocks = self.storage_manager.get_all_blocks()
            for block_data in stored_blocks:
                if not isinstance(block_data, dict):
                    logging.error(f"[ERROR] ❌ Invalid block data type: {type(block_data)}")
                    continue
                block = Block.from_dict(block_data)
                self.chain.append(block)
            logging.info(f"✅ Successfully loaded {len(self.chain)} blocks from storage.")
        except Exception as e:
            logging.error(f"[ERROR] Chain loading failed: {str(e)}")
            self.chain.clear()
            raise

            # In your Blockchain class
    def _create_genesis_block(self):
        """
        Create, mine, and validate the Genesis block using network-specific settings,
        ensuring double SHA3-384 hashing for integrity.
        """
        try:
            # ✅ Ensure miner address retrieval succeeds
            miner_address = self.key_manager.get_default_public_key(self.network, "miner")
            if not miner_address:
                raise ValueError("[ERROR] Failed to retrieve miner address for Genesis block.")

            # ✅ Ensure reward is a valid Decimal
            try:
                reward = Decimal(Constants.INITIAL_COINBASE_REWARD)
            except Exception as e:
                raise ValueError(f"[ERROR] Invalid coinbase reward: {str(e)}")

            # ✅ Construct the Coinbase transaction
            coinbase_tx = CoinbaseTx(
                block_height=0,
                miner_address=miner_address,
                reward=reward
            )
            coinbase_tx.fee = Decimal("0")

            # ✅ Use the actual system time for the Genesis block's timestamp
            genesis_timestamp = int(time.time())

            # ✅ Create the Genesis block
            genesis_block = Block(
                index=0,
                previous_hash=Constants.ZERO_HASH,
                transactions=[coinbase_tx],
                timestamp=genesis_timestamp,
                nonce=0,
                difficulty=Constants.GENESIS_TARGET,
                miner_address=miner_address
            )

            # ✅ Compute double SHA3-384 hash for block integrity
            genesis_block.hash = Hashing.double_sha3_384(genesis_block.calculate_hash().encode())

            # ✅ Mine the Genesis block (this updates nonce and block hash)
            self._mine_genesis_block(genesis_block)

            # ✅ Validate the Genesis block
            if not self.validate_new_block(genesis_block):
                raise ValueError("[ERROR] Generated Genesis block failed validation.")

            # ✅ Store the genesis block via the storage manager
            self.storage_manager.store_block(genesis_block, Constants.GENESIS_TARGET)
            logging.info(f"[INFO] ✅ Genesis block created successfully. Block Hash: {genesis_block.hash}")

            return genesis_block

        except Exception as e:
            logging.error(f"[ERROR] ❌ Genesis creation failed: {str(e)}")
            raise



    def _store_and_validate_genesis(self, genesis_block):
        """
        Stores the Genesis block and verifies its integrity.
        """
        try:
            computed_hash = Hashing.double_sha3_384(genesis_block.calculate_hash().encode())

            if genesis_block.hash != computed_hash:
                raise ValueError(f"[ERROR] ❌ Genesis block hash mismatch.\nExpected: {computed_hash}\nFound: {genesis_block.hash}")

            # ✅ Store block and verify consistency
            self.storage_manager.store_block(genesis_block, Constants.GENESIS_TARGET)

            if not self.storage_manager.verify_block_storage(genesis_block):
                raise RuntimeError("[ERROR] ❌ Genesis block storage verification failed.")

            # ✅ Validate chain properties
            if genesis_block.index != 0:
                raise ValueError("[ERROR] ❌ Genesis block must have index 0.")

            if genesis_block.previous_hash != Constants.ZERO_HASH:
                raise ValueError("[ERROR] ❌ Genesis block has invalid previous hash.")

            logging.info("[INFO] ✅ Genesis block stored, hashed, and verified successfully.")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Genesis validation failed: {str(e)}")
            raise



    def _mine_genesis_block(self, block=None):
        """Mines the Genesis block with the correct SHA3-384 target difficulty using double hashing."""
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
                    difficulty=Constants.GENESIS_TARGET,
                    miner_address=miner_address  # Ensure miner address is included
                )

            logging.info("[INFO] ⛏️ Starting mining of Genesis block...")
            start_time = time.time()
            last_update = start_time

            while int(block.hash, 16) >= block.difficulty:
                block.header.nonce += 1

                # ✅ Compute double SHA3-384 hash for Genesis block
                block.hash = Hashing.double_sha3_384(block.calculate_hash().encode())

                current_time = time.time()
                if current_time - last_update >= 1:
                    elapsed = int(current_time - start_time)
                    print(f"[LIVE] ⛏️ Mining Genesis Block | Nonce: {block.header.nonce}, Time: {elapsed}s")
                    last_update = current_time

            logging.info(f"[INFO] ✅ Genesis block mined successfully with hash: {block.hash}")

            try:
                # ✅ Ensure double SHA3-384 hash is stored correctly
                self.storage_manager.store_block(block, Constants.GENESIS_TARGET)
                logging.info("[INFO] ✅ Genesis block stored successfully.")
            except Exception as e:
                logging.error(f"[ERROR] ❌ Failed to store Genesis block: {e}")
                raise

        except Exception as e:
            logging.error(f"[ERROR] ❌ Mining Genesis block failed: {e}")
            raise









    def _ensure_genesis_block(self):
        """
        Ensures the Genesis block exists, validating it against storage.
        If missing or corrupted, a new Genesis block is created, mined, and stored.
        """
        try:
            stored_blocks = self.storage_manager.get_all_blocks()
            
            if stored_blocks:
                genesis_data = stored_blocks[0]

                # ✅ Ensure header exists and is a dictionary
                header = genesis_data.get("header", {})
                if not isinstance(header, dict):
                    raise ValueError("[ERROR] ❌ Genesis block header is not a dictionary.")

                # ✅ Validate the Genesis block structure
                if header.get("index", -1) != 0 or header.get("previous_hash") != Constants.ZERO_HASH:
                    raise ValueError("[ERROR] ❌ Corrupted Genesis block found in storage.")

                # ✅ Reconstruct the Genesis block
                genesis_block = Block.from_dict(genesis_data)

                # ✅ Validate stored hash with recalculated hash
                expected_hash = Hashing.double_sha3_384(genesis_block.calculate_hash().encode())
                stored_hash = genesis_data.get("hash", "")
                
                if expected_hash != stored_hash:
                    raise ValueError(f"[ERROR] ❌ Genesis block hash mismatch.\nExpected: {expected_hash}\nFound: {stored_hash}")

                # ✅ Add to chain if missing
                if not self.chain:
                    self.chain.append(genesis_block)
                    self.block_manager.chain.append(genesis_block)

                logging.info("✅ Genesis block successfully loaded from storage.")
                return  # Genesis block is valid; exit function.

            # ✅ No Genesis block found in storage; create a new one.
            genesis_block = self._create_genesis_block()
            genesis_block.previous_hash = Constants.ZERO_HASH
            genesis_block.hash = Hashing.double_sha3_384(genesis_block.calculate_hash().encode())

            # ✅ Validate newly created Genesis block before storing
            if not self.validate_new_block(genesis_block):
                raise ValueError("[ERROR] ❌ Generated Genesis block failed validation.")

            self._store_and_validate_genesis(genesis_block)

            # ✅ Append to chain after storage verification
            self.chain.append(genesis_block)
            self.block_manager.chain.append(genesis_block)
            
            logging.info("✅ Successfully initialized new Genesis Block.")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Genesis initialization failed: {str(e)}")
            logging.info("⚡ Purging corrupted chain data...")
            self.storage_manager.purge_chain()
            raise





    def add_block(self, new_block):
        """Add validated block to both chain and storage."""
        try:
            # ✅ Ensure block hash is correctly computed using double SHA3-384
            computed_hash = Hashing.double_sha3_384(new_block.calculate_hash().encode())

            if not new_block.hash or computed_hash != new_block.hash:
                raise ValueError(f"[ERROR] ❌ Block {new_block.index} has an invalid hash. Expected: {computed_hash}, Found: {new_block.hash}")

            if int(new_block.hash, 16) >= new_block.header.difficulty:
                raise ValueError(f"[ERROR] ❌ Block {new_block.index} does not meet Proof-of-Work difficulty target.")

            # ✅ Append the block to in-memory chain
            self.chain.append(new_block)
            self.block_manager.chain.append(new_block)

            # ✅ Store the block in the storage
            self.storage_manager.store_block(new_block, new_block.header.difficulty)

            # ✅ Confirm all transactions according to updated confirmation rules
            for tx in new_block.transactions:
                try:
                    # ✅ Ensure transaction ID is hashed with double SHA3-384
                    tx.tx_id = Hashing.double_sha3_384(tx.tx_id.encode())

                    # ✅ Retrieve transaction type safely
                    tx_type = PaymentTypeManager().get_transaction_type(tx.tx_id)
                    if not tx_type:
                        logging.warning(f"[WARN] ⚠️ Skipping confirmation for transaction {tx.tx_id} (Unknown Type).")
                        continue

                    # ✅ Fetch required confirmations dynamically from Constants
                    required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                        tx_type.name.upper(), Constants.TRANSACTION_CONFIRMATIONS["STANDARD"]
                    )

                    # ✅ Ensure transaction exists before confirming
                    if not self.storage_manager.get_transaction(tx.tx_id):
                        logging.warning(f"[WARN] ⚠️ Transaction {tx.tx_id} not found in storage. Skipping confirmation.")
                        continue

                    self.storage_manager.confirm_transaction(tx.tx_id, required_confirmations)

                except Exception as tx_error:
                    logging.error(f"[ERROR] ❌ Failed to confirm transaction {tx.tx_id}: {str(tx_error)}")
                    continue  # Proceed to the next transaction even if one fails

            # ✅ Verify that the block was properly stored
            stored_block = self.storage_manager.get_block(new_block.hash)
            if not stored_block or stored_block.hash != new_block.hash:
                raise RuntimeError(f"[ERROR] ❌ Block storage verification failed for Block {new_block.index}")

            logging.info(f"[INFO] ✅ Successfully added Block {new_block.index} [Hash: {new_block.hash[:12]}...]")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Block addition failed: {str(e)}")

            # ✅ Remove invalid block from the chain to prevent corruption
            if self.chain and self.chain[-1] == new_block:
                self.chain.pop()

            if self.block_manager.chain and self.block_manager.chain[-1] == new_block:
                self.block_manager.chain.pop()

            raise




    def _validate_block_structure(self, block: Block) -> bool:
        """Validate critical block fields ensuring integrity and SHA3-384 hashing compliance."""
        try:
            # ✅ Ensure block hash is correctly computed using double SHA3-384
            computed_hash = Hashing.double_sha3_384(block.calculate_hash().encode())

            # ✅ Validate essential block fields
            valid_structure = all([
                hasattr(block, 'index'),
                hasattr(block.header, 'previous_hash'),
                hasattr(block.header, 'merkle_root'),
                hasattr(block.header, 'timestamp'),
                block.hash == computed_hash  # Ensure stored hash matches computed hash
            ])

            if not valid_structure:
                logging.error(f"[ERROR] ❌ Block {block.index} structure validation failed.")
                return False

            logging.info(f"[INFO] ✅ Block {block.index} passed structure validation.")
            return True

        except Exception as e:
            logging.error(f"[ERROR] ❌ Block structure validation encountered an exception: {str(e)}")
            return False



    def _create_coinbase(self, block_height: int) -> CoinbaseTx:
        """Create a properly formatted coinbase transaction with double SHA3-384 hashed transaction ID."""
        try:
            # ✅ Validate block height
            if block_height < 0:
                raise ValueError("[ERROR] Block height must be a non-negative integer.")

            # ✅ Get miner address from KeyManager
            miner_address = self.key_manager.get_default_public_key(Constants.NETWORK, "miner")
            if not miner_address:
                raise ValueError("[ERROR] Failed to retrieve miner address.")

            # ✅ Use reward value from Constants
            reward = Decimal(Constants.INITIAL_COINBASE_REWARD)
            if reward <= 0:
                raise ValueError("[ERROR] Coinbase reward must be greater than zero.")

            # ✅ Construct the coinbase transaction
            coinbase_tx = CoinbaseTx(
                block_height=block_height,
                miner_address=miner_address,
                reward=reward
            )

            # ✅ Ensure coinbase transaction fee is set to zero
            coinbase_tx.fee = Decimal("0")

            # ✅ Apply double SHA3-384 hashing to transaction ID
            coinbase_tx.tx_id = Hashing.double_sha3_384(coinbase_tx.calculate_hash().encode())

            logging.info(f"[INFO] ✅ Successfully created Coinbase transaction for block {block_height}: {coinbase_tx.tx_id}")

            return coinbase_tx

        except Exception as e:
            logging.error(f"[ERROR] ❌ Coinbase creation failed: {str(e)}")
            raise



    def _validate_coinbase(self, tx):
        """
        Ensure the coinbase transaction follows protocol rules:
        - No inputs.
        - Exactly one output.
        - Transaction type is "COINBASE".
        - Fee is zero.
        - Transaction ID uses double SHA3-384 hashing.
        """
        from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx  # Lazy import

        try:
            # ✅ Verify basic Coinbase structure
            if not (len(tx.inputs) == 0 and len(tx.outputs) == 1 and tx.type == "COINBASE" and tx.fee == Decimal(0)):
                logging.error(f"[ERROR] ❌ Invalid Coinbase transaction format: {tx.tx_id}")
                return False

            # ✅ Ensure transaction ID is double SHA3-384 hashed
            expected_tx_id = Hashing.double_sha3_384(tx.calculate_hash().encode())
            if tx.tx_id != expected_tx_id:
                logging.error(f"[ERROR] ❌ Coinbase transaction ID mismatch! Expected: {expected_tx_id}, Found: {tx.tx_id}")
                return False

            logging.info(f"[INFO] ✅ Coinbase transaction {tx.tx_id} validated successfully.")
            return True

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to validate Coinbase transaction: {str(e)}")
            return False





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


