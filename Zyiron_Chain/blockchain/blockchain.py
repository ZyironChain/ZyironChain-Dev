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
from Zyiron_Chain.transactions.tx import Transaction

from Zyiron_Chain.transactions.coinbase import CoinbaseTx 
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.blockchain.utils.hashing import Hashing 

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
            logging.error(f"❌ Invalid Proof-of-Work for block {new_block.index}. Block hash: {new_block.hash}")
            return False

        # Validate previous hash linkage if a previous block is provided
        if prev_block and new_block.previous_hash != prev_block.hash:
            logging.error(f"❌ Block {new_block.index} has invalid previous hash. Expected: {prev_block.hash}, Found: {new_block.previous_hash}")
            return False

        # Skip transaction validation for the genesis block
        if new_block.index == 0:
            logging.info("✅ Skipping transaction confirmations check for the genesis block.")
            return True

        # Validate transactions in the block
        for tx in new_block.transactions:
            try:
                # Ensure `tx_id` is a string before encoding
                if isinstance(tx.tx_id, bytes):
                    tx.tx_id = tx.tx_id.decode("utf-8")

                # Apply **only single hashing** to transaction ID
                single_hashed_tx_id = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()

                # Determine transaction type and required confirmations
                tx_type = PaymentTypeManager().get_transaction_type(single_hashed_tx_id)
                required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                    tx_type.name, Constants.TRANSACTION_CONFIRMATIONS["STANDARD"]
                )

                # Fetch confirmations from storage
                confirmations = self.storage_manager.get_transaction_confirmations(single_hashed_tx_id)

                if confirmations is None:
                    logging.error(f"❌ Transaction {single_hashed_tx_id} confirmations could not be retrieved.")
                    return False

                if confirmations < required_confirmations:
                    logging.error(
                        f"❌ Transaction {single_hashed_tx_id} does not meet required confirmations "
                        f"({required_confirmations}, Confirmations: {confirmations})"
                    )
                    return False

            except Exception as e:
                logging.error(f"❌ Error validating transaction {tx.tx_id} in block {new_block.index}: {str(e)}")
                return False

        return True







    def _load_chain_from_storage(self):
        """Load blockchain from storage, using block.data offsets for full deserialization"""
        try:
            # ✅ Step 1: Get all block metadata from LMDB
            stored_blocks_metadata = self.storage_manager.get_all_blocks()

            if not stored_blocks_metadata:
                logging.info("[INFO] No existing blocks found in storage")
                return

            # ✅ Step 2: Sort blocks by index to maintain chain order
            sorted_blocks = sorted(stored_blocks_metadata, key=lambda b: b["header"]["index"])
            
            # ✅ Step 3: Load blocks sequentially using their stored offsets
            for block_metadata in sorted_blocks:
                try:
                    # Ensure metadata contains data_offset
                    data_offset = block_metadata.get("data_offset")
                    if data_offset is None:
                        logging.warning(f"[STORAGE WARNING] Skipping block {block_metadata.get('hash')} due to missing data_offset.")
                        continue  # ✅ Skip this block, do NOT raise an exception

                    # Load the full block from `block.data`
                    block = self.storage_manager.get_block_from_data_file(data_offset)
                    if block is None:
                        logging.warning(f"[STORAGE WARNING] Skipping block {block_metadata.get('hash')} due to load failure.")
                        continue  # ✅ Skip this block, do NOT raise an exception

                    # Ensure block transactions are valid
                    if not all(isinstance(tx, (dict, Transaction)) for tx in block.transactions):
                        logging.warning(f"[STORAGE WARNING] Block {block.index} contains invalid transaction format. Skipping block.")
                        continue  # ✅ Skip this block, do NOT raise an exception

                    # ✅ Step 4: Convert transactions to `Transaction` objects
                    processed_transactions = []
                    for tx_data in block.transactions:
                        try:
                            if isinstance(tx_data, Transaction):
                                processed_transactions.append(tx_data)  # ✅ Already a Transaction object
                            elif isinstance(tx_data, dict):
                                if tx_data.get("type") == "COINBASE":
                                    processed_transactions.append(CoinbaseTx.from_dict(tx_data))
                                else:
                                    processed_transactions.append(Transaction.from_dict(tx_data))
                            else:
                                logging.warning(f"[TRANSACTION WARNING] Skipping invalid transaction in Block {block.index}.")
                        except Exception as e:
                            logging.error(f"[TRANSACTION ERROR] ❌ Failed to parse transaction in Block {block.index}: {str(e)}")

                    # ✅ Step 5: Attach processed transactions to the block
                    block.transactions = processed_transactions

                    # ✅ Step 6: Ensure no duplicate blocks are added
                    if block.hash not in [b.hash for b in self.chain]:
                        self.chain.append(block)
                        logging.info(f"[INFO] ✅ Loaded block {block.index} from storage")
                    else:
                        logging.warning(f"[STORAGE WARNING] Block {block.index} is already in memory. Skipping duplicate.")

                except Exception as e:
                    logging.error(f"[ERROR] Failed to load block {block_metadata.get('hash')}: {str(e)}")
                    continue  # ✅ Instead of raising, just skip the failed block

            logging.info(f"[INFO] ✅ Successfully loaded {len(self.chain)} blocks from storage")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Chain loading failed: {str(e)}")
            # ✅ Fix: Instead of purging chain, just log an error



            # In your Blockchain class
    def _create_and_mine_genesis_block(self):
        """
        Creates and mines the Genesis block.
        - Uses SHA3-384 hashing to find a valid block hash.
        - Ensures the hash meets `Constants.GENESIS_TARGET`.
        - Only stores the block if the mined hash is valid.
        """
        try:
            logging.info("[INFO] ⛏️ Mining Genesis Block... (Optimized)")

            miner_address = self.key_manager.get_default_public_key(self.network, "miner")
            if not miner_address:
                raise ValueError("[ERROR] ❌ Failed to retrieve miner address for Genesis block.")

            # ✅ Create Coinbase Transaction
            coinbase_tx = CoinbaseTx(
                block_height=0,
                miner_address=miner_address,
                reward=Decimal(Constants.INITIAL_COINBASE_REWARD)
            )
            coinbase_tx.fee = Decimal("0")

            # ✅ Initialize Genesis Block
            genesis_block = Block(
                index=0,
                previous_hash=Constants.ZERO_HASH,
                transactions=[coinbase_tx],
                timestamp=int(time.time()),
                nonce=0,
                difficulty=Constants.GENESIS_TARGET,
                miner_address=miner_address
            )

            start_time = time.time()
            last_update = start_time

            # ✅ Start Mining Process (Ensure it keeps going until difficulty is met)
            while True:
                # Increment nonce and recompute hash
                genesis_block.header.nonce += 1
                computed_hash = hashlib.sha3_384(genesis_block.calculate_hash().encode()).hexdigest()

                # ✅ Ensure hash meets Genesis difficulty target
                if int(computed_hash, 16) < Constants.GENESIS_TARGET:
                    genesis_block.hash = computed_hash  # ✅ Store valid hash
                    break  # ✅ Exit loop when a valid hash is found

                # ✅ Log progress every 2 seconds
                current_time = time.time()
                if current_time - last_update >= 2:
                    elapsed = int(current_time - start_time)
                    logging.info(f"[LIVE] ⏳ Genesis Block Mining | Nonce: {genesis_block.header.nonce}, Time: {elapsed}s")
                    last_update = current_time

            logging.info(f"[INFO] ✅ Genesis Block Mined Successfully! Hash: {genesis_block.hash}")
            return genesis_block

        except Exception as e:
            logging.error(f"[ERROR] ❌ Genesis block mining failed: {str(e)}")
            raise



    def _ensure_genesis_block(self):
        """
        Ensures the Genesis block exists, validating it against storage.
        If missing or corrupted, a new Genesis block is created, mined, validated,
        and stored exactly once.
        """
        try:
            # ✅ Check if the Genesis block already exists in storage
            stored_blocks = self.storage_manager.get_all_blocks()

            if stored_blocks:
                # ✅ Confirm the first block is indeed the Genesis block
                genesis_data = stored_blocks[0]
                header = genesis_data.get("header", {})

                if not isinstance(header, dict):
                    raise ValueError("[ERROR] ❌ Genesis block header is not a dictionary.")

                if header.get("index", -1) != 0 or header.get("previous_hash") != Constants.ZERO_HASH:
                    raise ValueError("[ERROR] ❌ Corrupted Genesis block found in storage (index != 0 or wrong prev_hash).")

                # ✅ Rebuild the block object from stored data
                genesis_block = Block.from_dict(genesis_data)

                # ✅ Fix: Ensure hash is stored as a string, not a hashlib object
                if not isinstance(genesis_block.hash, str):
                    genesis_block.hash = hashlib.sha3_384(genesis_block.calculate_hash().encode()).hexdigest()

                # ✅ Ensure leading zeros check instead of expected hash mismatch
                if not genesis_block.hash.startswith("0000"):
                    raise ValueError("[ERROR] ❌ Genesis block hash does not meet difficulty requirement.")

                logging.info(f"✅ Genesis block successfully loaded from storage with hash: {genesis_block.hash}")
                self.chain.append(genesis_block)
                self.block_manager.chain.append(genesis_block)
                return  # ✅ Exit early to prevent unnecessary mining

            # ✅ Step 4: If missing, mine and store a new Genesis block
            genesis_block = self._create_and_mine_genesis_block()

            # ✅ Store the Genesis block exactly as mined
            self.storage_manager.store_block(genesis_block, Constants.GENESIS_TARGET)
            self.chain.append(genesis_block)
            self.block_manager.chain.append(genesis_block)

            logging.info(f"✅ Successfully initialized new Genesis Block with hash: {genesis_block.hash}")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Genesis initialization failed: {str(e)}")
            logging.info("⚡ Purging corrupted chain data...")
            self.storage_manager.purge_chain()
        raise





    def add_block(self, new_block):
        """Add validated block to both chain and storage."""
        try:
            # ✅ Ensure block hash is correctly computed using SHA3-384 (NO double hashing)
            computed_hash = hashlib.sha3_384(new_block.calculate_hash().encode()).hexdigest()

            if not new_block.hash or computed_hash != new_block.hash:
                raise ValueError(
                    f"❌ [ERROR] Block {new_block.index} has an invalid hash. Expected: {computed_hash}, Found: {new_block.hash}"
                )

            if int(new_block.hash, 16) >= new_block.header.difficulty:
                raise ValueError(f"❌ [ERROR] Block {new_block.index} does not meet Proof-of-Work difficulty target.")

            # ✅ Append the block to in-memory chain
            self.chain.append(new_block)
            self.block_manager.chain.append(new_block)

            # ✅ Store the block in the storage
            self.storage_manager.store_block(new_block, new_block.header.difficulty)

            # ✅ Confirm all transactions according to updated confirmation rules
            for tx in new_block.transactions:
                try:
                    # ✅ Ensure transaction ID is a string before encoding
                    if isinstance(tx.tx_id, bytes):
                        tx.tx_id = tx.tx_id.decode("utf-8")

                    # ✅ Apply **only single hashing** to transaction ID
                    single_hashed_tx_id = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()

                    # ✅ Retrieve transaction type safely
                    tx_type = PaymentTypeManager().get_transaction_type(single_hashed_tx_id)
                    if not tx_type:
                        logging.warning(f"⚠️ [WARN] Skipping confirmation for transaction {single_hashed_tx_id} (Unknown Type).")
                        continue

                    # ✅ Fetch required confirmations dynamically from Constants
                    required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                        tx_type.name.upper(), Constants.TRANSACTION_CONFIRMATIONS["STANDARD"]
                    )

                    # ✅ Ensure transaction exists before confirming
                    if not self.storage_manager.get_transaction(single_hashed_tx_id):
                        logging.warning(f"⚠️ [WARN] Transaction {single_hashed_tx_id} not found in storage. Skipping confirmation.")
                        continue

                    self.storage_manager.confirm_transaction(single_hashed_tx_id, required_confirmations)

                except Exception as tx_error:
                    logging.error(f"❌ [ERROR] Failed to confirm transaction {single_hashed_tx_id}: {str(tx_error)}")
                    continue  # Proceed to the next transaction even if one fails

            # ✅ Verify that the block was properly stored
            stored_block = self.storage_manager.get_block(new_block.hash)
            if not stored_block or stored_block.hash != new_block.hash:
                raise RuntimeError(f"❌ [ERROR] Block storage verification failed for Block {new_block.index}")

            logging.info(f"✅ [INFO] Successfully added Block {new_block.index} [Hash: {new_block.hash[:12]}...]")

        except Exception as e:
            logging.error(f"❌ [ERROR] Block addition failed: {str(e)}")

            # ✅ Remove invalid block from the chain to prevent corruption
            if self.chain and self.chain[-1] == new_block:
                self.chain.pop()

            if self.block_manager.chain and self.block_manager.chain[-1] == new_block:
                self.block_manager.chain.pop()

            raise



    def _validate_genesis_block(self, genesis_block):
        """
        Validate the Genesis block:
        - Ensures the hash meets the difficulty target.
        - Ensures index is 0 and previous hash is Constants.ZERO_HASH.
        - Ensures stored hash is properly formatted before comparison.
        """
        try:
            # ✅ Check Index and Previous Hash
            if genesis_block.index != 0:
                raise ValueError(f"[ERROR] ❌ Genesis block index must be 0, found {genesis_block.index}.")
            if genesis_block.previous_hash != Constants.ZERO_HASH:
                raise ValueError("[ERROR] ❌ Genesis block has an invalid previous hash.")

            # ✅ Ensure Genesis block hash is a valid hexadecimal string
            if not isinstance(genesis_block.hash, str) or not all(c in "0123456789abcdefABCDEF" for c in genesis_block.hash):
                raise ValueError("[ERROR] ❌ Genesis block hash is not a valid hex string.")

            # ✅ Ensure hash meets difficulty target
            if int(genesis_block.hash, 16) >= genesis_block.difficulty:
                raise ValueError(
                    f"[ERROR] ❌ Genesis block hash does not meet difficulty target.\n"
                    f"Expected Target: {hex(genesis_block.difficulty)}\n"
                    f"Found: {genesis_block.hash}"
                )

            logging.info("[INFO] ✅ Genesis block validated successfully.")
            return True

        except Exception as e:
            logging.error(f"[ERROR] ❌ Genesis block validation failed: {e}")
            return False




    def _validate_block_structure(self, block: Block) -> bool:
        """Validate critical block fields ensuring integrity and SHA3-384 hashing compliance."""
        try:
            # ✅ Ensure block hash is correctly computed using double SHA3-384
            computed_hash = hashlib.sha3_384(block.calculate_hash().encode()).hexdigest()


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

            # ✅ Apply double SHA3-384 hashing to transaction ID and convert to hex string
            coinbase_tx.tx_id = hashlib.sha3_384(coinbase_tx.calculate_hash().encode()).hexdigest()

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
            expected_tx_id = hashlib.sha3_384(tx.calculate_hash().encode()).hexdigest()

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


