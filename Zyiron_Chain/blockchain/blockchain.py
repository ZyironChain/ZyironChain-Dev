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
        """
        try:
            print("[Blockchain.load_chain_from_storage] INFO: Loading blockchain from LMDB...")

            # ✅ **Retrieve full blocks from LMDB**
            stored_blocks = self.full_block_store.get_all_blocks()
            if not stored_blocks:
                print("[Blockchain.load_chain_from_storage] ❌ WARNING: No blocks found in LMDB.")
                return []  # Explicitly return an empty list

            loaded_blocks = []
            previous_hash = Constants.ZERO_HASH  # Track previous hash for proper linkage

            for block_data in stored_blocks:
                try:
                    # ✅ **Handle both legacy and new block formats**
                    if "header" in block_data:
                        header = block_data["header"]
                    else:
                        # Legacy format where header fields are at root level
                        header = block_data
                        block_data = {"header": header, "transactions": block_data.get("transactions", [])}

                    # ✅ **Ensure block header contains required fields**
                    required_fields = {"index", "previous_hash", "hash", "timestamp", "nonce", "difficulty"}
                    if not required_fields.issubset(header.keys()):
                        print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Missing fields in block header: {header}")
                        continue  # Skip incomplete block headers

                    # ✅ **Deserialize the block safely**
                    block = Block.from_dict(block_data)

                    # ✅ **Genesis block special handling**
                    if block.index == 0:
                        loaded_blocks.append(block)
                        previous_hash = block.hash
                        continue

                    # ✅ **Ensure block links to the previous block**
                    if block.previous_hash != previous_hash:
                        print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Block {block.index} has incorrect previous hash.")
                        continue  # Skip invalid blocks

                    # ✅ **Validate block**
                    if not self.validate_block(block):
                        print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Block {block.index} failed validation.")
                        continue  # Skip invalid blocks

                    # ✅ **Ensure transactions are valid before adding to the block**
                    valid_transactions = []
                    for tx in block.transactions:
                        tx_id = tx.get("tx_id") if isinstance(tx, dict) else getattr(tx, "tx_id", None)
                        if not tx_id:
                            print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Transaction missing tx_id in Block {block.index}. Skipping...")
                            continue  # Skip transactions missing a tx_id

                        # ✅ **Ensure transaction exists in LMDB**
                        stored_tx = self.tx_storage.get_transaction(tx_id)
                        if not stored_tx:
                            print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Transaction {tx_id} not found in storage. Skipping...")
                            continue  # Skip transactions that aren't in storage

                        # ✅ **Add valid transactions**
                        valid_transactions.append(tx)

                    block.transactions = valid_transactions  # Assign only valid transactions

                    # ✅ **Ensure UTXO integrity**
                    if not self.utxo_storage.validate_utxos(block):
                        print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Block {block.index} has invalid UTXOs. Skipping...")
                        continue  # Skip blocks with invalid UTXOs

                    loaded_blocks.append(block)  # Add validated block to the in-memory chain
                    previous_hash = block.hash  # Update previous hash for linkage check

                except Exception as block_error:
                    print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Failed to process block {block_data.get('index', 'Unknown')}: {block_error}")

            print(f"[Blockchain.load_chain_from_storage] ✅ SUCCESS: Loaded {len(loaded_blocks)} valid blocks from LMDB.")
            return loaded_blocks

        except Exception as e:
            print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Failed to load chain from LMDB: {e}")
            return []  # Return an empty list on any failure


    def _compute_block_hash(self, block) -> str:
        """
        Compute block hash based on block header fields ensuring correct serialization.
        - Uses a standardized format for SHA3-384 hashing.
        - Ensures only critical header fields are included.
        """
        try:
            # ✅ **Ensure block object is valid**
            if not hasattr(block, "index") or not hasattr(block, "previous_hash") or not hasattr(block, "merkle_root"):
                print(f"[Blockchain._compute_block_hash] ❌ ERROR: Block object missing required fields.")
                return Constants.ZERO_HASH

            # ✅ **Prepare Header Data for Hashing**
            header_data = {
                "index": block.index,
                "previous_hash": block.previous_hash,
                "merkle_root": block.merkle_root,
                "timestamp": block.timestamp,
                "nonce": block.nonce,
                "difficulty": block.difficulty,
                "miner_address": block.miner_address,
                "transaction_signature": getattr(block, "signature", "0" * 96),  # Default to zeroed hash if missing
                "version": block.version,
            }

            # ✅ **Serialize Data as a JSON String**
            header_string = json.dumps(header_data, sort_keys=True)

            # ✅ **Compute SHA3-384 Hash**
            return Hashing.hash(header_string).hex()

        except Exception as e:
            print(f"[Blockchain._compute_block_hash] ❌ ERROR: Failed to compute block hash: {e}")
            return Constants.ZERO_HASH  # Return default zero hash on failure



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

            # ✅ **Skip validation for Genesis block**
            if not is_genesis and not self.validate_block(block):
                print(f"[Blockchain.add_block] ❌ ERROR: Block {block.index} failed validation.")
                return False

            # ✅ **Check block version compatibility**
            if block.version != Constants.VERSION:
                print(f"[Blockchain.add_block] ⚠️ WARNING: Block {block.index} has mismatched version. Expected {Constants.VERSION}, found {block.version}.")
                return False  # Prevent adding incompatible blocks

            # ✅ **Validate transactions before indexing**
            valid_transactions = []
            for tx in block.transactions:
                tx_id = tx.get("tx_id") if isinstance(tx, dict) else getattr(tx, "tx_id", None)
                if not tx_id:
                    continue  # Skip transactions without a valid ID

                valid_transactions.append(tx)

            block.transactions = valid_transactions  # Assign only valid transactions

            # ✅ **Validate UTXOs before storing block**
            if not self.utxo_storage.validate_utxos(block.transactions):
                print(f"[Blockchain.add_block] ❌ ERROR: Invalid UTXOs in Block {block.index}.")
                return False

            # ✅ **Store full block in LMDB**
            try:
                self.full_block_store.store_block(block)  # No 'difficulty' argument needed
                print(f"[Blockchain.add_block] ✅ INFO: Block {block.index} stored successfully.")
            except Exception as e:
                print(f"[Blockchain.add_block] ❌ ERROR: Failed to store block {block.index}: {e}")
                return False

            # ✅ **Index transactions from the block**
            for tx in block.transactions:
                try:
                    tx_id = tx.get("tx_id") if isinstance(tx, dict) else getattr(tx, "tx_id", None)
                    if not tx_id:
                        continue  # Skip invalid transaction

                    # ✅ **Retrieve block hash directly as a string**
                    block_hash = block.hash if isinstance(block.hash, str) else str(block.hash)

                    # ✅ **Extract outputs and timestamp from the transaction**
                    outputs = tx.get("outputs") if isinstance(tx, dict) else getattr(tx, "outputs", [])
                    timestamp = tx.get("timestamp") if isinstance(tx, dict) else getattr(tx, "timestamp", int(time.time()))

                    # ✅ **Store transaction in LMDB with required parameters**
                    self.tx_storage.store_transaction(tx_id, block_hash, tx, outputs, timestamp)
                    print(f"[Blockchain.add_block] ✅ INFO: Transaction {tx_id} indexed successfully.")

                except Exception as e:
                    print(f"[Blockchain.add_block] ❌ ERROR: Failed to index transaction in Block {block.index}: {e}")

            # ✅ **Validate and update UTXO storage**
            if not self.utxo_storage.validate_utxos(block.transactions):
                print(f"[Blockchain.add_block] ❌ ERROR: Block {block.index} has invalid UTXOs. Aborting addition.")
                return False  # Prevent corrupt UTXO storage

            self.utxo_storage.update_utxos(block)
            print(f"[Blockchain.add_block] ✅ INFO: UTXO database updated successfully.")

            # ✅ **Append block to in-memory chain**
            self.chain.append(block)
            print(f"[Blockchain.add_block] ✅ SUCCESS: Block {block.index} added to the chain.")
            return True

        except Exception as e:
            print(f"[Blockchain.add_block] ❌ ERROR: Failed to add Block {block.index}: {e}")
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
        - Block version matches current chain version
        - Proof-of-Work validation
        - Correct linkage to previous block
        - All transactions are valid
        """
        try:
            print(f"[Blockchain.validate_block] INFO: Validating Block {block.index}...")

            # ✅ **Check for required metadata fields**
            required_fields = ["index", "previous_hash", "merkle_root", "timestamp", "nonce", "difficulty"]
            missing_fields = [field for field in required_fields if not hasattr(block, field)]

            if missing_fields:
                print(f"[Blockchain.validate_block] ❌ ERROR: Block {block.index} is missing fields: {missing_fields}")
                return False

            print(f"[Blockchain.validate_block] INFO: Block {block.index} contains all required metadata fields.")

            # ✅ **Check block version compatibility**
            if block.version != Constants.VERSION:
                print(f"[Blockchain.validate_block] ⚠️ WARNING: Block {block.index} has mismatched version. "
                    f"Expected {Constants.VERSION}, found {block.version}.")
                return False  # Prevent adding incompatible blocks

            print(f"[Blockchain.validate_block] INFO: Block {block.index} version validated.")

            # ✅ **Validate Proof-of-Work**
            if not self.pow_manager.validate_proof_of_work(block):
                print(f"[Blockchain.validate_block] ❌ ERROR: Block {block.index} failed Proof-of-Work validation.")
                return False

            print(f"[Blockchain.validate_block] INFO: Proof-of-Work validation passed for Block {block.index}.")

            # ✅ **Ensure block links to the previous block**
            if self.chain:
                last_block = self.chain[-1]
                if block.previous_hash != last_block.hash:
                    print(f"[Blockchain.validate_block] ❌ ERROR: Block {block.index} has an invalid previous hash. "
                        f"Expected: {last_block.hash}, Found: {block.previous_hash}")
                    return False

            print(f"[Blockchain.validate_block] INFO: Block {block.index} correctly links to the previous block.")

            # ✅ **Validate all transactions in the block**
            for tx in block.transactions:
                if not self.transaction_manager.validate_transaction(tx):
                    print(f"[Blockchain.validate_block] ❌ ERROR: Invalid transaction {tx.tx_id} in Block {block.index}.")
                    return False

            print(f"[Blockchain.validate_block] ✅ SUCCESS: Block {block.index} validated.")
            return True

        except Exception as e:
            print(f"[Blockchain.validate_block] ❌ ERROR: Block {block.index} validation failed: {e}")
            return False

            


    def validate_chain(self) -> bool:
        """
        Validate the entire blockchain.
        - Ensures each block correctly links to the previous block.
        - Validates all transactions in each block.

        :return: True if the blockchain is valid, False otherwise.
        """
        try:
            print("[Blockchain.validate_chain] INFO: Validating blockchain integrity...")

            # ✅ **Retrieve All Blocks from LMDB**
            stored_blocks = self.full_block_store.get_all_blocks()
            if not stored_blocks:
                print("[Blockchain.validate_chain] ❌ ERROR: No blocks found in LMDB storage.")
                return False

            # ✅ **Sort Blocks by Height (No More `header`)**
            sorted_blocks = sorted(stored_blocks, key=lambda b: b["index"])

            # ✅ **Validate Block Linkage & Transaction Integrity**
            prev_hash = Constants.ZERO_HASH
            for block_meta in sorted_blocks:
                try:
                    # ✅ **Deserialize Block Properly**
                    block = Block.from_dict(block_meta)
                    if not block:
                        print(f"[Blockchain.validate_chain] ❌ ERROR: Failed to deserialize block at height {block_meta.get('index', 'UNKNOWN')}.")
                        return False

                    # ✅ **Check Previous Hash Consistency (Skip for Genesis Block)**
                    if block.index > 0 and block.previous_hash != prev_hash:
                        print(f"[Blockchain.validate_chain] ❌ ERROR: Block {block.index} has an invalid previous hash. "
                            f"Expected {prev_hash}, Found {block.previous_hash}")
                        return False

                    # ✅ **Validate Block Transactions**
                    for tx in block.transactions:
                        if not self.transaction_manager.validate_transaction(tx):
                            print(f"[Blockchain.validate_chain] ❌ ERROR: Transaction {tx.get('tx_id')} in Block {block.index} is invalid.")
                            return False

                    prev_hash = block.hash  # ✅ Update previous hash for the next block

                except Exception as block_error:
                    print(f"[Blockchain.validate_chain] ❌ ERROR: Block validation failed at index {block_meta.get('index', 'UNKNOWN')}: {block_error}")
                    return False

            print("[Blockchain.validate_chain] ✅ SUCCESS: Blockchain validation complete.")
            return True

        except Exception as e:
            print(f"[Blockchain.validate_chain] ❌ ERROR: Blockchain validation failed: {e}")
            return False


    def purge_chain():
        """
        Placeholder function for purging the blockchain.
        This will be implemented later to handle full blockchain resets.
        """
        pass
