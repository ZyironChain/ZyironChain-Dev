import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import json
import hashlib
import time
import math
from decimal import Decimal
import threading

from Zyiron_Chain.utils.key_manager import KeyManager
from Zyiron_Chain.blockchain.transaction_manager import TransactionManager
from Zyiron_Chain.blockchain.storage_manager import StorageManager
from Zyiron_Chain.blockchain.miner import Miner
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.transactions.Blockchain_transaction import TransactionFactory
from Zyiron_Chain.transactions.transaction_services import TransactionService
from Zyiron_Chain.transactions.fees import FeeModel, FundsAllocator
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.transactions.coinbase import CoinbaseTx 
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.utils.hashing import Hashing

# =============================================================================
# Blockchain Class
# =============================================================================
class Blockchain:


    def __init__(self, storage_manager, transaction_manager, key_manager):
        print("[Blockchain.__init__] START: Initializing Blockchain...")

        # Network Configuration with Validation
        self.network = Constants.NETWORK.lower()
        if self.network not in ('mainnet', 'testnet'):
            raise ValueError(f"[Blockchain.__init__] ERROR: Invalid network configured: {self.network}. Must be 'mainnet' or 'testnet'")
        print(f"[Blockchain.__init__] INFO: Initializing on {self.network.upper()} network")

        # Validate Miner Keys
        if not key_manager.validate_miner_key(self.network):
            help_option = 4 if self.network == 'mainnet' else 3
            raise RuntimeError(
                f"[Blockchain.__init__] ERROR: Miner key missing for {self.network.upper()}\n"
                "Generate keys using:\n"
                "python -m Zyiron_Chain.accounts.key_manager\n"
                f"Then choose '{help_option}. Add new batch of keys to {self.network}'"
            )

        # Core Components
        self.address_prefix = Constants.ADDRESS_PREFIX
        self.version = Constants.VERSION
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager
        self.key_manager = key_manager
        self.chain = []
        self.constants = Constants  # Access to updated constants

        print(f"[Blockchain.__init__] INFO: Miner keys validated for {self.network.upper()}.")

        # Block Manager Initialization
        try:
            from Zyiron_Chain.blockchain.block_manager import BlockManager
            self.block_manager = BlockManager(
                blockchain=self,
                storage_manager=self.storage_manager,
                transaction_manager=self.transaction_manager
            )
            print("[Blockchain.__init__] INFO: BlockManager initialized successfully.")
        except Exception as e:
            print(f"[Blockchain.__init__] ERROR: BlockManager init failed: {e}")
            raise

        # Initialize Fee Model with Updated Constants
        self.fee_model = FeeModel(
            max_supply=Decimal(Constants.MAX_SUPPLY),
            base_fee_rate=Decimal(Constants.MIN_TRANSACTION_FEE)
        )

        # Miner Initialization with Hashing Integration
        self.miner = Miner(
            self.block_manager,
            self.transaction_manager,
            self.storage_manager,
            self.key_manager
        )

        # Load Blockchain Data (if any)
        try:
            stored_blocks = self.storage_manager.get_all_blocks()
            if stored_blocks:
                self._load_chain_from_storage()
        except Exception as e:
            print(f"[Blockchain.__init__] ERROR: Chain loading error: {e}")
            self.storage_manager.purge_chain()

        # NOTE: Genesis block creation has been moved to its own module.
        # (Thus, we no longer call _ensure_genesis_block() here.)
        print(f"[Blockchain.__init__] SUCCESS: Blockchain v{self.version} successfully initialized on {self.network.upper()}.")

    def validate_new_block(self, new_block: Block, prev_block: Block = None) -> bool:
        """
        Validate a new block before adding it to the chain.
        Checks:
         - Proof-of-Work (hash and difficulty).
         - Previous hash linkage.
         - Transaction confirmations (using single SHA3-384 hashing).
        """
        # Verify Proof-of-Work
        if not new_block.hash or int(new_block.hash, 16) >= new_block.header.difficulty:
            print(f"[Blockchain.validate_new_block] ERROR: Invalid Proof-of-Work for block {new_block.index}. Block hash: {new_block.hash}")
            return False

        # Validate previous hash linkage if a previous block is provided
        if prev_block and new_block.previous_hash != prev_block.hash:
            print(f"[Blockchain.validate_new_block] ERROR: Block {new_block.index} has invalid previous hash. Expected: {prev_block.hash}, Found: {new_block.previous_hash}")
            return False

        # Skip transaction confirmation check for genesis block (index 0)
        if new_block.index == 0:
            print("[Blockchain.validate_new_block] INFO: Skipping transaction confirmation check for Genesis block.")
            return True

        # Validate transactions in the block
        for tx in new_block.transactions:
            try:
                if isinstance(tx.tx_id, bytes):
                    tx.tx_id = tx.tx_id.decode("utf-8")
                # Apply only single SHA3-384 hashing
                single_hashed_tx_id = Hashing.hash(tx.tx_id.encode()).hex()
                tx_type = PaymentTypeManager().get_transaction_type(single_hashed_tx_id)
                required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                    tx_type.name, Constants.TRANSACTION_CONFIRMATIONS["STANDARD"]
                )
                confirmations = self.storage_manager.get_transaction_confirmations(single_hashed_tx_id)
                if confirmations is None:
                    print(f"[Blockchain.validate_new_block] ERROR: Confirmations for transaction {single_hashed_tx_id} could not be retrieved.")
                    return False
                if confirmations < required_confirmations:
                    print(f"[Blockchain.validate_new_block] ERROR: Transaction {single_hashed_tx_id} does not meet required confirmations ({required_confirmations}, Confirmations: {confirmations}).")
                    return False
            except Exception as e:
                print(f"[Blockchain.validate_new_block] ERROR: Error validating transaction {tx.tx_id} in block {new_block.index}: {e}")
                return False

        return True

    def _load_chain_from_storage(self):
        """
        Load blockchain from storage using block.data offsets for full deserialization.
        Blocks are sorted by index and loaded sequentially.
        """
        try:
            stored_blocks_metadata = self.storage_manager.get_all_blocks()
            if not stored_blocks_metadata:
                print("[Blockchain._load_chain_from_storage] INFO: No existing blocks found in storage.")
                return

            sorted_blocks = sorted(stored_blocks_metadata, key=lambda b: b["header"]["index"])
            for block_metadata in sorted_blocks:
                try:
                    data_offset = block_metadata.get("data_offset")
                    if data_offset is None:
                        print(f"[Blockchain._load_chain_from_storage] WARNING: Skipping block {block_metadata.get('hash')} due to missing data_offset.")
                        continue

                    block = self.storage_manager.get_block_from_data_file(data_offset)
                    if block is None:
                        print(f"[Blockchain._load_chain_from_storage] WARNING: Skipping block {block_metadata.get('hash')} due to load failure.")
                        continue

                    # Convert transactions if necessary
                    processed_transactions = []
                    for tx_data in block.transactions:
                        try:
                            from Zyiron_Chain.transactions.tx import Transaction
                            from Zyiron_Chain.transactions.coinbase import CoinbaseTx
                            if isinstance(tx_data, Transaction):
                                processed_transactions.append(tx_data)
                            elif isinstance(tx_data, dict):
                                if tx_data.get("type") == "COINBASE":
                                    processed_transactions.append(CoinbaseTx.from_dict(tx_data))
                                else:
                                    processed_transactions.append(Transaction.from_dict(tx_data))
                            else:
                                print(f"[Blockchain._load_chain_from_storage] WARNING: Skipping invalid transaction in Block {block.index}.")
                        except Exception as e:
                            print(f"[Blockchain._load_chain_from_storage] ERROR: Failed to parse transaction in Block {block.index}: {e}")
                    block.transactions = processed_transactions

                    if block.hash not in [b.hash for b in self.chain]:
                        self.chain.append(block)
                        self.block_manager.chain.append(block)
                        print(f"[Blockchain._load_chain_from_storage] INFO: Loaded block {block.index} from storage.")
                    else:
                        print(f"[Blockchain._load_chain_from_storage] WARNING: Block {block.index} is already in memory. Skipping duplicate.")

                except Exception as e:
                    print(f"[Blockchain._load_chain_from_storage] ERROR: Failed to load block {block_metadata.get('hash')}: {e}")
                    continue

            print(f"[Blockchain._load_chain_from_storage] SUCCESS: Loaded {len(self.chain)} blocks from storage.")

        except Exception as e:
            print(f"[Blockchain._load_chain_from_storage] ERROR: Chain loading failed: {e}")

    def add_block(self, new_block):
        """
        Adds a validated block to the blockchain:
        - Verifies the block hash using single SHA3-384 hashing.
        - Validates transactions and block structure.
        - Stores the block across storage layers and updates the blockchain state.
        """
        try:
            # Compute expected hash using single SHA3-384
            computed_hash = Hashing.hash(new_block.calculate_hash().encode()).hex()
            if not new_block.hash or computed_hash != new_block.hash:
                raise ValueError(f"[Blockchain.add_block] ERROR: Block {new_block.index} has an invalid hash. Expected: {computed_hash}, Found: {new_block.hash}")
            if int(new_block.hash, 16) >= new_block.header.difficulty:
                raise ValueError(f"[Blockchain.add_block] ERROR: Block {new_block.index} does not meet the Proof-of-Work difficulty target.")

            # Append block to the in-memory chain (both Blockchain and BlockManager references)
            self.chain.append(new_block)
            self.block_manager.chain.append(new_block)
            # Store block using the storage manager
            self.storage_manager.store_block(new_block, new_block.header.difficulty)
            print(f"[Blockchain.add_block] SUCCESS: Block {new_block.index} added. [Hash: {new_block.hash[:12]}...]")

            # Confirm each transaction in the block
            for tx in new_block.transactions:
                try:
                    if isinstance(tx.tx_id, bytes):
                        tx.tx_id = tx.tx_id.decode("utf-8")
                    # Hash the transaction ID using single SHA3-384
                    single_hashed_tx_id = Hashing.hash(tx.tx_id.encode()).hex()
                    tx_type = PaymentTypeManager().get_transaction_type(single_hashed_tx_id)
                    if not tx_type:
                        print(f"[Blockchain.add_block] WARNING: Skipping confirmation for transaction {single_hashed_tx_id} (Unknown Type).")
                        continue
                    required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(
                        tx_type.name.upper(), Constants.TRANSACTION_CONFIRMATIONS["STANDARD"]
                    )
                    confirmations = self.storage_manager.get_transaction_confirmations(single_hashed_tx_id)
                    if confirmations is None:
                        print(f"[Blockchain.add_block] ERROR: Could not retrieve confirmations for transaction {single_hashed_tx_id}.")
                        return False
                    if confirmations < required_confirmations:
                        print(f"[Blockchain.add_block] ERROR: Transaction {single_hashed_tx_id} does not meet required confirmations ({required_confirmations}, Found: {confirmations}).")
                        return False
                    self.storage_manager.confirm_transaction(single_hashed_tx_id, required_confirmations)
                except Exception as tx_error:
                    print(f"[Blockchain.add_block] ERROR: Failed to confirm transaction {tx.tx_id}: {tx_error}")
                    continue

            # Verify that the block was properly stored
            stored_block = self.storage_manager.get_block(new_block.hash)
            if not stored_block or stored_block.hash != new_block.hash:
                raise RuntimeError(f"[Blockchain.add_block] ERROR: Block storage verification failed for Block {new_block.index}")

        except Exception as e:
            print(f"[Blockchain.add_block] ERROR: Block addition failed: {e}")
            if self.chain and self.chain[-1] == new_block:
                self.chain.pop()
            if self.block_manager.chain and self.block_manager.chain[-1] == new_block:
                self.block_manager.chain.pop()
            raise


    def _validate_block_structure(self, block: Block) -> bool:
        """
        Validate critical block fields ensuring integrity and SHA3-384 hashing compliance.
        """
        try:
            computed_hash = Hashing.hash(block.calculate_hash().encode()).hex()
            valid_structure = all([
                hasattr(block, 'index'),
                hasattr(block.header, 'previous_hash'),
                hasattr(block.header, 'merkle_root'),
                hasattr(block.header, 'timestamp'),
                block.hash == computed_hash
            ])
            if not valid_structure:
                print(f"[Blockchain._validate_block_structure] ERROR: Block {block.index} structure validation failed.")
                return False
            print(f"[Blockchain._validate_block_structure] INFO: Block {block.index} passed structure validation.")
            return True
        except Exception as e:
            print(f"[Blockchain._validate_block_structure] ERROR: Exception during block structure validation: {e}")
            return False

    def _create_coinbase(self, block_height: int) -> CoinbaseTx:
        """
        Create a properly formatted coinbase transaction using single SHA3-384 hashing.
        """
        try:
            if block_height < 0:
                raise ValueError("[Blockchain._create_coinbase] ERROR: Block height must be non-negative.")
            miner_address = self.key_manager.get_default_public_key(Constants.NETWORK, "miner")
            if not miner_address:
                raise ValueError("[Blockchain._create_coinbase] ERROR: Failed to retrieve miner address.")
            reward = Decimal(Constants.INITIAL_COINBASE_REWARD)
            if reward <= 0:
                raise ValueError("[Blockchain._create_coinbase] ERROR: Coinbase reward must be greater than zero.")
            coinbase_tx = CoinbaseTx(
                block_height=block_height,
                miner_address=miner_address,
                reward=reward
            )
            coinbase_tx.fee = Decimal("0")
            # Use single hashing for transaction ID
            coinbase_tx.tx_id = Hashing.hash(coinbase_tx.calculate_hash().encode()).hex()
            print(f"[Blockchain._create_coinbase] SUCCESS: Created Coinbase transaction for block {block_height}: {coinbase_tx.tx_id}")
            return coinbase_tx
        except Exception as e:
            print(f"[Blockchain._create_coinbase] ERROR: Coinbase creation failed: {e}")
            raise

    def _validate_coinbase(self, tx):
        """
        Validate that the coinbase transaction adheres to protocol:
         - No inputs, one output, type is "COINBASE", fee is zero.
         - Transaction ID is correctly hashed using single SHA3-384.
        """
        from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
        try:
            if not (len(tx.inputs) == 0 and len(tx.outputs) == 1 and tx.type == "COINBASE" and tx.fee == Decimal(0)):
                print(f"[Blockchain._validate_coinbase] ERROR: Invalid Coinbase format for transaction {tx.tx_id}")
                return False
            expected_tx_id = Hashing.hash(tx.calculate_hash().encode()).hex()
            if tx.tx_id != expected_tx_id:
                print(f"[Blockchain._validate_coinbase] ERROR: Coinbase transaction ID mismatch! Expected: {expected_tx_id}, Found: {tx.tx_id}")
                return False
            print(f"[Blockchain._validate_coinbase] SUCCESS: Coinbase transaction {tx.tx_id} validated.")
            return True
        except Exception as e:
            print(f"[Blockchain._validate_coinbase] ERROR: Coinbase validation failed: {e}")
            return False

    def ensure_consistency(self, block):
        """
        Ensure blockchain consistency before adding a new block.
        Retrieves the latest block from storage to validate proper linking.
        """
        if not isinstance(block, Block):
            raise ValueError("[ERROR] ❌ Invalid block: Block must be an instance of `Block`.")

        if not hasattr(block, "hash") or not hasattr(block, "merkle_root"):
            raise ValueError("[ERROR] ❌ Block is missing required attributes (hash, merkle_root).")

        # ✅ Fetch the last stored block dynamically from StorageManager
        last_block = self.storage_manager.get_latest_block()

        if last_block:
            # ✅ Ensure previous block hash matches
            if block.previous_hash != last_block.hash:
                raise ValueError(
                    f"[ERROR] ❌ Previous hash mismatch: Expected {last_block.hash}, Got {block.previous_hash}"
                )

            # ✅ Ensure block index increments properly
            if block.index != last_block.index + 1:
                raise ValueError(
                    f"[ERROR] ❌ Block index mismatch: Expected {last_block.index + 1}, Got {block.index}"
                )

        else:
            # ✅ Ensure Genesis block starts at index 0
            if block.index != 0:
                raise ValueError("[ERROR] ❌ First block must have index 0 (Genesis Block).")
            logging.warning("[WARNING] 🚀 No previous blocks found. Initializing Genesis Block.")

        logging.info(f"[INFO] ✅ Block {block.index} passed consistency checks.")