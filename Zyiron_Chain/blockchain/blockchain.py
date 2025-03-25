#!/usr/bin/env python3
"""
Blockchain Class

- Loads and manages the in-memory chain.
- Interacts with the new storage modules (block_storage, blockmetadata, etc.).
- Imports genesis block creation from 'genesis_block.py' if no chain is found.
- Uses only print statements (no logging).
- Single SHA3-384 hashing is assumed throughout (Block, BlockManager, etc.).
"""

import sys
import os
from typing import List, Optional
# Adjust Python path for project structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

import json
import time
import lmdb
# -------------------------------------------------------------------------
# Imports from our new splitted storage modules and block code
# -------------------------------------------------------------------------
from Zyiron_Chain.storage.block_storage import BlockStorage
from Zyiron_Chain.blockchain.block_manager import BlockManager
from Zyiron_Chain.blockchain.block import Block

from Zyiron_Chain.blockchain.genesis_block import GenesisBlockManager  # Hypothetical genesis block generator

# Constants might be needed for difficulty, chain name, etc.
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.miner.pow import PowManager
from Zyiron_Chain.transactions.txout import TransactionOut 
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.utils.diff_conversion import DifficultyConverter
from Zyiron_Chain.transactions.coinbase import CoinbaseTx
from Zyiron_Chain.transactions.tx import Transaction



class Blockchain:
    """
    Main Blockchain class that:
      - Loads blocks from LMDB storage.
      - Creates a genesis block if none exist.
      - Maintains an in-memory list of blocks (`self.chain`).
      - Provides high-level methods for adding and retrieving blocks.
    """

    def __init__(
        self,
        tx_storage=None,      # Handles transaction indexing (TxStorage).
        utxo_storage=None,    # Manages UTXOs (UTXOStorage).
        transaction_manager=None,  # Transaction handling (TransactionManager).
        key_manager=None,  # Manages cryptographic keys (KeyManager).
        full_block_store=None  # ✅ Handles full block storage in LMDB.
    ):
        """
        Initialize the Blockchain.

        - Uses LMDB (`full_block_chain.lmdb`) for full block storage.
        - Ensures blockchain metadata is loaded correctly.
        - Creates a genesis block if no existing blocks are found.
        """
        try:
            print("[Blockchain.__init__] INFO: Initializing Blockchain...")

            # ✅ Initialize LMDB storage for full blocks (merged storage)
            self.full_block_store = full_block_store or LMDBManager(Constants.DATABASES["full_block_chain"])

            # ✅ Initialize BlockStorage
            self.block_storage = BlockStorage(
                tx_storage=tx_storage,
                key_manager=key_manager
            )

            # ✅ Initialize storage modules
            self.tx_storage = tx_storage
            self.utxo_storage = utxo_storage
            self.transaction_manager = transaction_manager
            self.key_manager = key_manager

            # ✅ In-memory blockchain representation
            self.chain = []

            # ✅ Initialize Proof-of-Work Manager with block storage
            self.pow_manager = PowManager(self.block_storage)

            # ✅ Load chain from storage
            self.load_chain_from_storage()

            # ✅ Create Genesis Block if no blocks exist
            if not self.chain:
                print("[Blockchain.__init__] INFO: No existing blocks found. Creating Genesis block...")

                # ✅ Initialize Genesis Block Manager
                self.genesis_block_manager = GenesisBlockManager(
                    block_storage=self.block_storage,  # Correct parameter name and type
                    key_manager=self.key_manager,
                    chain=self.chain,
                    block_manager=self
                )

                # ✅ Create and store the Genesis block in LMDB
                genesis_block = self.genesis_block_manager.create_and_mine_genesis_block()
                self.add_block(genesis_block, is_genesis=True)

            else:
                print(f"[Blockchain.__init__] ✅ SUCCESS: Loaded {len(self.chain)} blocks from LMDB.")

        except Exception as e:
            print(f"[Blockchain.__init__] ❌ ERROR: Blockchain initialization failed: {e}")
            raise


    def load_chain_from_storage(self) -> list:
        """
        Load the blockchain from LMDB storage into memory with validation.
        - Retrieves full blocks directly from `full_block_chain.lmdb`.
        - Ensures all transactions are valid before adding to the in-memory chain.
        - Verifies UTXO consistency before blocks are added.
        - Skips blocks with missing or invalid hashes.
        """
        try:
            print("[Blockchain.load_chain_from_storage] INFO: Loading blockchain from LMDB...")

            stored_blocks = self.full_block_store.get_all_blocks()
            if not stored_blocks:
                print("[Blockchain.load_chain_from_storage] ❌ WARNING: No blocks found in LMDB.")
                self.chain = []  # Explicitly clear the chain if empty
                return []

            loaded_blocks = []
            previous_hash = Constants.ZERO_HASH

            for block_data in stored_blocks:
                try:
                    header = block_data.get("header", {})
                    transactions_data = block_data.get("transactions", [])

                    # ✅ Handle missing critical header fields with fallbacks
                    required_fields = {"index", "previous_hash", "merkle_root", "timestamp", "nonce", "difficulty"}
                    missing_fields = required_fields - header.keys()
                    if missing_fields:
                        print(f"[Blockchain.load_chain_from_storage] INFO: Missing fields in block header: {missing_fields}. Using fallback values.")
                        for field in missing_fields:
                            if field == "index":
                                header["index"] = len(loaded_blocks)
                            elif field == "previous_hash":
                                header["previous_hash"] = previous_hash
                            elif field == "merkle_root":
                                temp_data = json.dumps(block_data, sort_keys=True).encode()
                                header["merkle_root"] = Hashing.hash(temp_data).hex()
                            elif field == "timestamp":
                                header["timestamp"] = int(time.time())
                            elif field == "nonce":
                                header["nonce"] = 0
                            elif field == "difficulty":
                                header["difficulty"] = self._parse_difficulty(Constants.GENESIS_TARGET)

                    # ✅ Normalize difficulty
                    header["difficulty"] = self._parse_difficulty(header.get("difficulty", Constants.GENESIS_TARGET))
                    block_data["header"] = header
                    block_data["transactions"] = transactions_data

                    block = Block.from_dict(block_data)
                    if block is None:
                        print(f"[Blockchain.load_chain_from_storage] ⚠️ WARNING: Skipping invalid block at index {header.get('index', 'Unknown')}.")
                        continue

                    # ✅ Deserialize transactions
                    for i, tx in enumerate(block.transactions):
                        if isinstance(tx, dict):
                            if tx.get("type") == "COINBASE":
                                block.transactions[i] = CoinbaseTx.from_dict(tx)
                            else:
                                block.transactions[i] = Transaction.from_dict(tx)

                    # ✅ Genesis block validation
                    if block.index == 0:
                        if block.previous_hash != Constants.ZERO_HASH:
                            print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Genesis block has invalid previous hash. Expected {Constants.ZERO_HASH}, Found: {block.previous_hash}")
                            continue
                        loaded_blocks.append(block)
                        previous_hash = block.hash
                        continue

                    # ✅ Chain linkage validation
                    if block.previous_hash != previous_hash:
                        print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Block {block.index} has incorrect previous hash. Expected {previous_hash}, Found: {block.previous_hash}")
                        continue

                    # ✅ Block structure validation
                    if not self.validate_block(block):
                        print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Block {block.index} failed structural validation.")
                        continue

                    # ✅ Transaction validation
                    valid_transactions = []
                    for tx in block.transactions:
                        tx_id = getattr(tx, "tx_id", None)
                        if not tx_id:
                            print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Missing tx_id in Block {block.index}. Skipping TX.")
                            continue

                        stored_tx = self.tx_storage.get_transaction(tx_id)
                        if not stored_tx:
                            print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: TX {tx_id} missing from LMDB. Skipping TX.")
                            continue

                        if not self.transaction_manager.validate_transaction(tx):
                            print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: TX {tx_id} in Block {block.index} failed validation.")
                            continue

                        valid_transactions.append(tx)

                    block.transactions = valid_transactions

                    # ✅ UTXO validation
                    if not self.utxo_storage.validate_utxos(block):
                        print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: UTXOs invalid for Block {block.index}. Skipping block.")
                        continue

                    loaded_blocks.append(block)
                    previous_hash = block.hash

                except Exception as block_error:
                    print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Failed to process block {block_data.get('index', 'Unknown')}: {block_error}")

            # ✅ Final chain validation
            if not self.validate_chain(loaded_blocks):
                print("[Blockchain.load_chain_from_storage] ❌ ERROR: Final chain structure is invalid.")
                self.chain = []
                return []

            self.chain = loaded_blocks  # ✅ FIXED: store loaded chain
            print(f"[Blockchain.load_chain_from_storage] ✅ SUCCESS: Loaded {len(self.chain)} valid blocks from LMDB.")
            return self.chain

        except Exception as e:
            print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Failed to load chain from LMDB: {e}")
            self.chain = []
            return []

    def _compute_block_hash(self, block) -> str:
        """
        Retrieves the PoW-mined hash of the block instead of recalculating.
        - Ensures only the finalized PoW hash (`mined_hash`) is used.
        """
        try:
            # ✅ **Ensure block has a valid PoW-mined hash**
            if not hasattr(block, "mined_hash") or not isinstance(block.mined_hash, str) or len(block.mined_hash) != 96:
                print(f"[Blockchain._compute_block_hash] ❌ ERROR: Block {block.index} is missing a valid PoW-mined hash.")
                return Constants.ZERO_HASH

            # ✅ **Return the PoW-mined hash without recalculating**
            return block.mined_hash

        except Exception as e:
            print(f"[Blockchain._compute_block_hash] ❌ ERROR: Failed to retrieve block hash: {e}")
            return Constants.ZERO_HASH

    def _validate_transaction(self, tx: dict, tx_id: str, block_index: int) -> bool:
        """
        Validate a transaction structure before adding it to the block.
        - Ensures all required fields exist.
        - Checks inputs and outputs for validity.
        """
        try:
            # ✅ **Ensure `tx_id` is properly formatted**
            if not isinstance(tx_id, str) or not tx_id:
                return False  # Skip invalid transaction IDs

            # ✅ **Check for required transaction fields**
            required_fields = ["tx_id", "inputs", "outputs", "timestamp", "type"]
            if not all(field in tx for field in required_fields):
                return False  # Skip transactions with missing fields

            # ✅ **Validate inputs and outputs**
            inputs = tx.get("inputs", [])
            outputs = tx.get("outputs", [])

            if not isinstance(inputs, list) or not isinstance(outputs, list) or (not inputs and not outputs):
                return False  # Invalid input/output structure

            # ✅ **Ensure `timestamp` is a valid integer**
            timestamp = tx.get("timestamp")
            if not isinstance(timestamp, int) or timestamp <= 0:
                return False  # Invalid timestamp

            return True  # ✅ Transaction is valid

        except Exception:
            return False  # Catch all validation errors


    def add_block(self, block: Block, is_genesis: bool = False) -> bool:
        """
        Add a block to the blockchain with full validation.

        - Validates the block before adding (except for genesis block).
        - Ensures correct structure of transactions and UTXOs.
        - Updates storage modules (full block store, transactions, and UTXOs).
        - Prevents adding corrupted or incompatible blocks.

        :param block: The block to add.
        :param is_genesis: Whether the block is the genesis block.
        :return: True if the block was added successfully, False otherwise.
        """
        try:
            print(f"[Blockchain.add_block] INFO: Adding Block {block.index} to the chain...")

            # ✅ Skip validation for Genesis block
            if not is_genesis:
                if not self.validate_block(block):
                    print(f"[Blockchain.add_block] ❌ ERROR: Block {block.index} failed validation.")
                    return False

            # ✅ Block version compatibility
            if block.version != Constants.VERSION:
                print(f"[Blockchain.add_block] ⚠️ WARNING: Version mismatch in Block {block.index}. Expected {Constants.VERSION}, got {block.version}.")
                return False

            # ✅ Validate transactions
            valid_transactions = []
            for tx in block.transactions:
                if isinstance(tx, dict):
                    tx_dict = tx
                elif hasattr(tx, "to_dict"):
                    tx_dict = tx.to_dict()
                else:
                    print(f"[Blockchain.add_block] ⚠️ WARNING: Unrecognized transaction format in block {block.index}. Skipping.")
                    continue

                tx_id = tx_dict.get("tx_id")
                if not tx_id:
                    print(f"[Blockchain.add_block] ⚠️ WARNING: Transaction missing 'tx_id'. Skipping.")
                    continue

                valid_transactions.append(tx_dict)

            if not valid_transactions:
                print(f"[Blockchain.add_block] ❌ ERROR: No valid transactions found in Block {block.index}.")
                return False

            block.transactions = valid_transactions

            # ✅ Validate UTXOs before accepting the block
            if not self.utxo_storage.validate_utxos(valid_transactions):
                print(f"[Blockchain.add_block] ❌ ERROR: Invalid UTXOs found in Block {block.index}.")
                return False

            # ✅ Store full block (binary file + metadata)
            try:
                self.full_block_store.store_block(block)
                print(f"[Blockchain.add_block] ✅ INFO: Block {block.index} stored successfully.")
            except Exception as e:
                print(f"[Blockchain.add_block] ❌ ERROR: Failed to store Block {block.index}: {e}")
                return False

            # ✅ Index transactions from the block
            for tx_dict in valid_transactions:
                try:
                    tx_id = tx_dict.get("tx_id")
                    if not tx_id:
                        continue

                    block_hash = block.hash if isinstance(block.hash, str) else str(block.hash)
                    outputs = tx_dict.get("outputs", [])
                    timestamp = tx_dict.get("timestamp", int(time.time()))

                    self.tx_storage.store_transaction(tx_id, block_hash, tx_dict, outputs, timestamp)
                    print(f"[Blockchain.add_block] ✅ INFO: Indexed transaction {tx_id}.")

                except Exception as e:
                    print(f"[Blockchain.add_block] ❌ ERROR: Failed to index transaction {tx_id} in Block {block.index}: {e}")

            # ✅ Update UTXO set
            try:
                self.utxo_storage.update_utxos(block)
                print(f"[Blockchain.add_block] ✅ INFO: UTXOs updated for Block {block.index}.")
            except Exception as e:
                print(f"[Blockchain.add_block] ❌ ERROR: Failed to update UTXOs for Block {block.index}: {e}")
                return False

            # ✅ Add to in-memory chain
            self.chain.append(block)
            print(f"[Blockchain.add_block] ✅ SUCCESS: Block {block.index} added to the chain.")
            return True

        except Exception as e:
            print(f"[Blockchain.add_block] ❌ EXCEPTION: Unexpected error while adding Block {block.index}: {e}")
            return False

    def _convert_tx_outputs(self, outputs) -> list:
        """
        Convert transaction outputs that are dictionaries into proper TransactionOut objects.
        
        :param outputs: List of outputs (can be dicts or TransactionOut objects).
        :return: List of standardized outputs.
        """
        converted_outputs = []
        
        for out in outputs:
            if isinstance(out, dict):
                try:
                    converted_outputs.append(TransactionOut.from_dict(out))
                except Exception:
                    continue  # Skip invalid outputs
            else:
                converted_outputs.append(out)  # Assume it's already a TransactionOut object

        return converted_outputs



    def _extract_inputs(self, tx) -> list:
        """
        Extract transaction inputs into a consistent dictionary format.
        
        :param tx: Transaction instance or dictionary containing inputs.
        :return: List of standardized input dictionaries.
        """
        extracted_inputs = []

        # ✅ **Ensure `tx` is handled correctly**
        inputs = tx.get("inputs", []) if isinstance(tx, dict) else getattr(tx, "inputs", [])

        print(f"[Blockchain._extract_inputs] INFO: Found {len(inputs)} input(s) in transaction.")

        for idx, inp in enumerate(inputs):
            try:
                # ✅ **Ensure input fields are properly extracted**
                amount = inp.get("amount", 0) if isinstance(inp, dict) else getattr(inp, "amount", 0)
                previous_tx = inp.get("previous_tx", "") if isinstance(inp, dict) else getattr(inp, "previous_tx", "")
                output_index = inp.get("output_index", None) if isinstance(inp, dict) else getattr(inp, "output_index", None)

                print(f"[Blockchain._extract_inputs] INFO: Input {idx} - amount: {amount}, previous_tx: {previous_tx}, output_index: {output_index}.")

                extracted_inputs.append({
                    "amount": amount,
                    "previous_tx": previous_tx,
                    "output_index": output_index
                })
            except Exception as e:
                print(f"[Blockchain._extract_inputs] ERROR: Failed to process input {idx}: {e}")

        print(f"[Blockchain._extract_inputs] ✅ SUCCESS: Extracted {len(extracted_inputs)} inputs.")
        return extracted_inputs


    def _extract_outputs(self, tx) -> list:
        """
        Extract transaction outputs into a consistent dictionary format.
        
        :param tx: Transaction instance or dictionary containing outputs.
        :return: List of standardized output dictionaries.
        """
        extracted_outputs = []

        # ✅ **Ensure `tx` is handled correctly**
        outputs = tx.get("outputs", []) if isinstance(tx, dict) else getattr(tx, "outputs", [])

        print(f"[Blockchain._extract_outputs] INFO: Found {len(outputs)} output(s) in transaction.")

        for idx, out in enumerate(outputs):
            try:
                # ✅ **Ensure output fields are properly extracted**
                amount = out.get("amount", 0) if isinstance(out, dict) else getattr(out, "amount", 0)
                script_pub_key = out.get("script_pub_key", "") if isinstance(out, dict) else getattr(out, "script_pub_key", "")
                locked = out.get("locked", False) if isinstance(out, dict) else getattr(out, "locked", False)

                print(f"[Blockchain._extract_outputs] INFO: Output {idx} - amount: {amount}, script_pub_key: {script_pub_key}, locked: {locked}.")

                extracted_outputs.append({
                    "amount": amount,
                    "script_pub_key": script_pub_key,
                    "locked": locked
                })
            except Exception as e:
                print(f"[Blockchain._extract_outputs] ERROR: Failed to process output {idx}: {e}")

        print(f"[Blockchain._extract_outputs] ✅ SUCCESS: Extracted {len(extracted_outputs)} outputs.")
        return extracted_outputs



    def validate_block(self, block: Block) -> bool:
        """
        Validate a block before adding it to the blockchain.
        Ensures:
        - Required metadata fields exist
        - Genesis block has `previous_hash = Constants.ZERO_HASH`
        - Block version matches current chain version
        - Proof-of-Work validation (using the mined hash)
        - Correct linkage to previous block
        - All transactions are valid
        """
        try:
            print(f"[Blockchain.validate_block] INFO: Validating Block {block.index}...")

            # ✅ Required metadata fields
            required_fields = ["index", "previous_hash", "merkle_root", "timestamp", "nonce", "difficulty", "hash"]
            missing_fields = [field for field in required_fields if not hasattr(block, field)]

            if missing_fields:
                print(f"[Blockchain.validate_block] ❌ ERROR: Block {block.index} is missing fields: {missing_fields}")
                return False

            print(f"[Blockchain.validate_block] INFO: Block {block.index} contains all required metadata fields.")

            # ✅ Genesis block special rule
            if block.index == 0:
                if block.previous_hash != Constants.ZERO_HASH:
                    print(f"[Blockchain.validate_block] ❌ ERROR: Genesis block must have `previous_hash = Constants.ZERO_HASH`")
                    return False

            # ✅ For all other blocks, validate previous linkage
            elif self.chain:
                last_block = self.chain[-1]
                if block.previous_hash != last_block.mined_hash:
                    print(f"[Blockchain.validate_block] ❌ ERROR: Block {block.index} has an invalid previous hash. "
                        f"Expected: {last_block.mined_hash}, Found: {block.previous_hash}")
                    return False

            print(f"[Blockchain.validate_block] INFO: Block {block.index} correctly links to the previous block.")

            # ✅ Block version check
            if block.version != Constants.VERSION:
                print(f"[Blockchain.validate_block] ⚠️ WARNING: Block {block.index} has mismatched version. "
                    f"Expected {Constants.VERSION}, found {block.version}.")
                return False

            print(f"[Blockchain.validate_block] INFO: Block {block.index} version validated.")

            # ✅ Standardize difficulty before PoW check
            block.difficulty = self._parse_difficulty(block.difficulty)

            # ✅ Validate PoW
            if not block.mined_hash:
                print(f"[Blockchain.validate_block] ❌ ERROR: Block {block.index} is missing a valid PoW-mined hash.")
                return False

            if not self.pow_manager.validate_proof_of_work(block):
                print(f"[Blockchain.validate_block] ❌ ERROR: Block {block.index} failed Proof-of-Work validation.")
                return False

            print(f"[Blockchain.validate_block] INFO: Proof-of-Work validation passed for Block {block.index}.")

            # ✅ Validate each transaction (convert if dict)
            for tx in block.transactions:
                if isinstance(tx, dict):
                    tx_type = tx.get("type")
                    if tx_type == "COINBASE":
                        tx = CoinbaseTx.from_dict(tx)
                    else:
                        tx = Transaction.from_dict(tx)

                if not self.transaction_manager.validate_transaction(tx):
                    print(f"[Blockchain.validate_block] ❌ ERROR: Invalid transaction {getattr(tx, 'tx_id', 'UNKNOWN')} in Block {block.index}.")
                    return False

            print(f"[Blockchain.validate_block] ✅ SUCCESS: Block {block.index} validated.")
            return True

        except Exception as e:
            print(f"[Blockchain.validate_block] ❌ ERROR: Block {block.index} validation failed: {e}")
            return False



    def purge_chain():
        """
        Placeholder function for purging the blockchain.
        This will be implemented later to handle full blockchain resets.
        """
        pass

    def validate_chain(self, chain: Optional[List[Block]] = None) -> bool:
        """
        Validate the entire blockchain with robust fallback mechanisms.
        - Ensures each block is valid and linked correctly.
        - Validates all transactions in each block using the TransactionManager.
        - Handles missing or invalid data gracefully.
        """
        try:
            if chain is None:
                chain = self.chain

            print("[Blockchain.validate_chain] INFO: Validating blockchain...")

            if not chain:
                print("[Blockchain.validate_chain] ❌ ERROR: Blockchain is empty.")
                return False

            if len(chain) > 0:
                print(f"[DEBUG] Block 0 previous_hash: {chain[0].previous_hash}")
                print(f"[DEBUG] Expected previous_hash: {Constants.ZERO_HASH}")

            for i, block in enumerate(chain):
                print(f"[Blockchain.validate_chain] INFO: Validating Block {block.index}...")

                # ✅ Ensure index is present
                if not hasattr(block, "index"):
                    print(f"[Blockchain.validate_chain] ⚠️ WARNING: Block at position {i} missing 'index'. Setting fallback index.")
                    block.index = i

                # ✅ Validate block structure & PoW
                if not self.validate_block(block):
                    print(f"[Blockchain.validate_chain] ❌ ERROR: Block {block.index} failed structural or PoW validation.")
                    return False

                # ✅ Genesis block check
                if i == 0:
                    if block.previous_hash != Constants.ZERO_HASH:
                        print(f"[Blockchain.validate_chain] ❌ ERROR: Genesis block previous hash mismatch.\nExpected: {Constants.ZERO_HASH}\nFound:    {block.previous_hash}")
                        return False
                else:
                    # Ensure previous_hash exists
                    if not hasattr(block, "previous_hash"):
                        print(f"[Blockchain.validate_chain] ⚠️ WARNING: Block {block.index} missing 'previous_hash'. Using fallback.")
                        block.previous_hash = Constants.ZERO_HASH

                    # ✅ Check block linkage
                    if block.previous_hash != chain[i - 1].hash:
                        print(f"[Blockchain.validate_chain] ❌ ERROR: Block {block.index} not linked correctly.\nExpected: {chain[i - 1].hash}\nFound:    {block.previous_hash}")
                        return False

                # ✅ Validate each transaction
                if not hasattr(block, "transactions") or not isinstance(block.transactions, list):
                    print(f"[Blockchain.validate_chain] ⚠️ WARNING: Block {block.index} has no valid transaction list. Skipping transaction checks.")
                    continue

                for j, tx in enumerate(block.transactions):
                    try:
                        # Deserialize from dict if needed
                        if isinstance(tx, dict):
                            tx_type = tx.get("type", "STANDARD")
                            tx_obj = CoinbaseTx.from_dict(tx) if tx_type == "COINBASE" else Transaction.from_dict(tx)
                            block.transactions[j] = tx_obj
                            tx = tx_obj

                        # Ensure transaction ID
                        if not hasattr(tx, "tx_id"):
                            print(f"[Blockchain.validate_chain] ⚠️ WARNING: Transaction in Block {block.index} missing 'tx_id'. Generating fallback.")
                            tx.tx_id = Hashing.hash(json.dumps(tx.to_dict(), sort_keys=True).encode("utf-8")).hex()

                        # Validate transaction
                        if not self.transaction_manager.validate_transaction(tx):
                            print(f"[Blockchain.validate_chain] ❌ ERROR: Invalid transaction {tx.tx_id} in Block {block.index}.")
                            return False

                    except Exception as tx_err:
                        print(f"[Blockchain.validate_chain] ❌ ERROR: Exception while validating transaction in Block {block.index}: {tx_err}")
                        return False

            print("[Blockchain.validate_chain] ✅ SUCCESS: Blockchain validated successfully.")
            return True

        except Exception as e:
            print(f"[Blockchain.validate_chain] ❌ ERROR: Blockchain validation failed: {e}")
            return False


    def _parse_difficulty(self, value) -> str:
        """
        Standardize difficulty to a 96-character hex string using DifficultyConverter.
        Accepts int or hex str.
        """
        try:
            return DifficultyConverter.to_standard_hex(value)
        except Exception as e:
            print(f"[Blockchain._parse_difficulty] ❌ ERROR: Failed to parse difficulty: {e}")
            return Constants.GENESIS_TARGET  # fallback

    def _parse_difficulty_int(self, value) -> int:
        """
        Convert difficulty from hex (with or without '0x') or int into a standardized int.
        """
        try:
            return DifficultyConverter.to_integer(value)
        except Exception as e:
            print(f"[Blockchain._parse_difficulty_int] ❌ ERROR: Failed to convert difficulty to int: {e}")
            return int(Constants.GENESIS_TARGET, 16)  # fallback        