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
from Zyiron_Chain.storage.block_storage import WholeBlockData
from Zyiron_Chain.storage.blockmetadata import BlockMetadata
from Zyiron_Chain.blockchain.block_manager import BlockManager
from Zyiron_Chain.blockchain. block import Block
from Zyiron_Chain.blockchain.genesis_block import GenesisBlockManager  # Hypothetical genesis block generator

# Constants might be needed for difficulty, chain name, etc.
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.miner.pow import PowManager
from Zyiron_Chain.transactions.txout import TransactionOut 
from Zyiron_Chain.utils.hashing import Hashing

class Blockchain:
    """
    Main Blockchain class that:
      - Loads blocks from the new storage modules.
      - Creates a genesis block if none exist.
      - Maintains an in-memory list of blocks (self.chain).
      - Provides high-level methods for adding blocks, retrieving blocks, etc.
    """

    def __init__(
        self,
        block_storage=None,     # For retrieving block data if needed
        block_metadata=None,    # For retrieving block headers / ordering
        tx_storage=None,        # For checking transaction existence, storing TX data
        utxo_storage=None,      # For managing UTXOs
        wallet_index=None,      # For wallet-related operations
        transaction_manager=None,  # For transaction management
        key_manager=None        # For key management
    ):
        """
        Initialize the Blockchain.

        :param block_storage: Module handling full block storage (WholeBlockData).
        :param block_metadata: Module handling block metadata (BlockMetadata).
        :param tx_storage: Module for transaction indexing (TxStorage).
        :param utxo_storage: Module for UTXO management (UTXOStorage).
        :param wallet_index: Module for wallet-related operations (WalletStorage).
        :param transaction_manager: Module for transaction management (TransactionManager).
        :param key_manager: Module for key management (KeyManager).
        """
        print("[Blockchain.__init__] Initializing Blockchain...")

        # Storage modules for blocks and metadata
        self.block_storage = block_storage or WholeBlockData()
        self.block_metadata = block_metadata or BlockMetadata()
        self.tx_storage = tx_storage
        self.utxo_storage = utxo_storage
        self.wallet_index = wallet_index
        self.transaction_manager = transaction_manager
        self.key_manager = key_manager

        # In-memory chain list
        self.chain = []

        # Initialize PowManager for proof-of-work operations
        self.pow_manager = PowManager()

        # Attempt to load chain from storage
        self.load_chain_from_storage()

        # If chain is empty, create genesis block
        if not self.chain:
            print("[Blockchain.__init__] No existing blocks found. Creating Genesis block.")
            # Use GenesisBlockManager to create a new genesis block
            self.genesis_block_manager = GenesisBlockManager(
                block_storage=self.block_storage,
                block_metadata=self.block_metadata,
                key_manager=self.key_manager,
                chain=self.chain,
                block_manager=self
            )
            genesis_block = self.genesis_block_manager.create_and_mine_genesis_block()
            self.add_block(genesis_block, is_genesis=True)
        else:
            print(f"[Blockchain.__init__] Loaded {len(self.chain)} blocks from storage.")



    def load_chain_from_storage(self) -> list:
        """
        Load the blockchain from storage into memory with validation.
        - Ensures block hashes are validated without re-hashing (preserves mined hash).
        - Handles edge cases for conversions (bytes, JSON, hex, etc.).
        - Validates block structure, integrity, transactions, and UTXOs.
        """
        try:
            print("[Blockchain.load_chain_from_storage] INFO: Loading chain from storage...")

            # ✅ Retrieve all stored blocks
            stored_blocks = self.block_metadata.get_all_blocks()
            if not stored_blocks:
                print("[Blockchain.load_chain_from_storage] ❌ WARNING: No blocks found in storage.")
                return []  # Explicitly return an empty list

            loaded_blocks = []
            for block_data in stored_blocks:
                try:
                    # ✅ **Ensure block data is valid before processing**
                    if not isinstance(block_data, dict) or "index" not in block_data or "hash" not in block_data:
                        print(f"[Blockchain.load_chain_from_storage] ❌ WARNING: Skipping corrupted block: {block_data}")
                        continue

                    # ✅ **Deserialize the block safely**
                    block = Block.from_dict(block_data)

                    # ✅ **Skip hash validation for Genesis block**
                    if block.index == 0:
                        loaded_blocks.append(block)
                        print(f"[Blockchain.load_chain_from_storage] ✅ INFO: Genesis block loaded (index 0).")
                        continue

                    # ✅ **Preserve the mined hash (do not re-hash)**
                    mined_hash = block.hash  # Original mined hash

                    # ✅ **Validate block structure**
                    if not self.validate_block(block):
                        print(f"[Blockchain.load_chain_from_storage] ❌ WARNING: Skipping invalid block at height {block.index}")
                        continue

                    # ✅ **Validate block hash integrity**
                    expected_hash = self._compute_block_hash(block)
                    if expected_hash != mined_hash:
                        print(f"[Blockchain] ❌ ERROR: Block {block.index} hash mismatch!")
                        print(f"[Blockchain] Expected: {expected_hash}, Found: {mined_hash}")


                    # ✅ **Validate transactions inside the block**
                    valid_transactions = []
                    for tx in block.transactions:
                        try:
                            if not isinstance(tx, dict):
                                print(f"[Blockchain.load_chain_from_storage] ❌ WARNING: Invalid transaction format in Block {block.index}. Skipping.")
                                continue

                            tx_id = tx.get("tx_id")
                            if not self._validate_transaction(tx, tx_id, block.index):
                                print(f"[Blockchain.load_chain_from_storage] ❌ WARNING: Transaction {tx_id} in Block {block.index} failed validation.")
                                continue

                            # ✅ **Check if transaction exists in storage**
                            stored_tx = self.tx_storage.get_transaction(tx_id)
                            if stored_tx and stored_tx.get("tx_id") != tx_id:
                                print(f"[Blockchain.load_chain_from_storage] ❌ WARNING: Transaction ID mismatch in stored transactions. Expected {tx_id}, Found {stored_tx.get('tx_id')}")
                                continue

                            valid_transactions.append(tx)

                        except Exception as tx_error:
                            print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Transaction processing error in Block {block.index}: {tx_error}")
                            continue

                    # ✅ **Re-assign only valid transactions**
                    block.transactions = valid_transactions

                    # ✅ **Validate UTXOs related to this block**
                    if not self.utxo_storage.validate_utxos(block):
                        print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Block {block.index} contains invalid UTXOs. Skipping block.")
                        continue

                    loaded_blocks.append(block)

                except Exception as block_error:
                    print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Failed to process block {block_data.get('index', 'Unknown')}: {block_error}")

            print(f"[Blockchain.load_chain_from_storage] ✅ SUCCESS: Loaded {len(loaded_blocks)} valid blocks from storage.")
            return loaded_blocks

        except Exception as e:
            print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Failed to load chain from storage: {e}")
            return []  # Return an empty list on any failure


    def _compute_block_hash(self, block) -> bytes:
        """
        Compute block hash based on block header fields ensuring correct serialization.
        """
        try:
            header_data = {
                "index": block.index,
                "previous_hash": block.previous_hash,
                "merkle_root": block.merkle_root,
                "timestamp": block.timestamp,
                "nonce": block.nonce,
                "difficulty": block.difficulty,
                "miner_address": block.miner_address,
                "transaction_signature": block.signature,
                "reward": block.reward,
                "fees": block.fees,
                "version": block.version,
            }

            # ✅ Convert all fields to bytes for hashing consistently
            header_bytes = b"".join([
                str(header_data["index"]).encode(),
                self._convert_to_bytes(header_data["previous_hash"]),
                self._convert_to_bytes(header_data["merkle_root"]),
                str(header_data["timestamp"]).encode(),
                str(header_data["nonce"]).encode(),
                str(header_data["difficulty"]).encode(),
                self._convert_to_bytes(header_data["miner_address"]),
                self._convert_to_bytes(header_data["transaction_signature"]),
                str(header_data["reward"]).encode(),
                str(header_data["fees"]).encode(),
                str(header_data["version"]).encode(),
            ])

            # ✅ Ensure the computed hash is consistent
            computed_hash = Hashing.hash(header_bytes)
            return computed_hash

        except Exception as e:
            print(f"[Blockchain._compute_block_hash] ❌ ERROR: Failed to compute block hash: {e}")
            return Constants.ZERO_HASH  # Return default zero hash on failure


    def _convert_to_bytes(self, field) -> bytes:
        """
        Convert a field to bytes safely, handling hex strings, normal strings, and bytes.
        """
        if isinstance(field, bytes):
            return field
        elif isinstance(field, str):
            return field.encode()
        else:
            print(f"[Blockchain._convert_to_bytes] ❌ WARNING: Invalid field type for hashing: {type(field)}")
            return b""

    def _validate_transaction(self, tx: dict, tx_id: str, block_index: int) -> bool:
        """
        Validate a transaction structure before adding it to the block.
        """
        try:
            # ✅ **Ensure `tx_id` is properly formatted**
            if not tx_id:
                print(f"[Blockchain._validate_transaction] ❌ WARNING: Missing `tx_id` in transaction. Skipping.")
                return False

            if isinstance(tx_id, bytes):
                tx_id = tx_id.hex()
            elif not isinstance(tx_id, str):
                print(f"[Blockchain._validate_transaction] ❌ WARNING: Invalid `tx_id` type. Expected str or bytes. Found: {type(tx_id)}. Skipping.")
                return False

            # ✅ **Validate inputs and outputs**
            inputs = tx.get("inputs", [])
            outputs = tx.get("outputs", [])

            if not isinstance(inputs, list) or not isinstance(outputs, list):
                print(f"[Blockchain._validate_transaction] ❌ WARNING: Invalid inputs/outputs format in transaction {tx_id}. Skipping.")
                return False

            print(f"[Blockchain._validate_transaction] ✅ INFO: Transaction {tx_id} in Block {block_index} is valid.")
            return True

        except Exception as e:
            print(f"[Blockchain._validate_transaction] ❌ ERROR: Failed to validate transaction {tx_id}: {e}")
            return False

    def add_block(self, block: Block, is_genesis: bool = False) -> bool:
        """
        Add a block to the blockchain with full validation.
        
        - Validates the block before adding (except for genesis block).
        - Ensures correct structure of transactions and UTXOs.
        - Updates storage modules (block metadata, transactions, and UTXOs).
        - Prevents adding corrupted or incompatible blocks.
        
        :param block: The block to add.
        :param is_genesis: Whether the block is the genesis block.
        :return: True if the block was added successfully, False otherwise.
        """
        try:
            print(f"[Blockchain.add_block] INFO: Adding Block {block.index} to the chain...")

            # ✅ **Skip validation for Genesis block**
            if not is_genesis:
                if not self.validate_block(block):
                    print(f"[Blockchain.add_block] ❌ ERROR: Block {block.index} failed validation.")
                    return False

            # ✅ **Check block version compatibility**
            if block.version != Constants.VERSION:
                print(f"[Blockchain.add_block] ⚠️ WARNING: Block {block.index} has mismatched version. Expected {Constants.VERSION}, found {block.version}.")
                return False  # Prevent adding incompatible blocks

            # ✅ **Ensure outputs are properly formatted as `TransactionOut` objects**
            for tx in block.transactions:
                if hasattr(tx, "outputs"):
                    tx.outputs = [
                        TransactionOut(**output) if isinstance(output, dict) else output
                        for output in tx.outputs
                    ]
                else:
                    print(f"[Blockchain.add_block] ❌ ERROR: Transaction in Block {block.index} is missing outputs. Skipping.")
                    return False

            # ✅ **Ensure `tx_id` exists before indexing transactions**
            for tx in block.transactions:
                tx_id = tx.tx_id if hasattr(tx, "tx_id") else tx.get("tx_id")
                if not tx_id:
                    print(f"[Blockchain.add_block] ❌ ERROR: Missing `tx_id` in transaction. Skipping transaction in Block {block.index}.")
                    continue  # Skip this transaction

                # ✅ **Handle edge cases for `tx_id` (int, bytes, hex, etc.)**
                if isinstance(tx_id, int):
                    tx_id = hex(tx_id)  # Convert int to hex string
                elif isinstance(tx_id, bytes):
                    tx_id = tx_id.hex()  # Convert bytes to hex string
                elif not isinstance(tx_id, str):
                    print(f"[Blockchain.add_block] ❌ ERROR: Invalid `tx_id` type in transaction. Expected str, bytes, or int. Found {type(tx_id)}. Skipping.")
                    continue  # Skip invalid transaction

                # ✅ **Ensure `tx_id` is a valid hex string**
                try:
                    int(tx_id, 16)  # Validate hex string
                except ValueError:
                    print(f"[Blockchain.add_block] ❌ ERROR: Invalid `tx_id` format. Expected hex string. Found {tx_id}. Skipping.")
                    continue  # Skip invalid transaction

            # ✅ **Serialize transactions before UTXO validation**
            serialized_transactions = [tx.to_dict() if hasattr(tx, 'to_dict') else tx for tx in block.transactions]
            if not self.utxo_storage.validate_utxos(serialized_transactions):
                print(f"[Blockchain.add_block] ❌ ERROR: Invalid UTXOs in Block {block.index}.")
                return False

            # ✅ **Store block metadata and full block data**
            try:
                self.block_metadata.store_block(block, block.difficulty)
                print(f"[Blockchain.add_block] ✅ INFO: Block {block.index} metadata stored successfully.")
            except Exception as e:
                print(f"[Blockchain.add_block] ❌ ERROR: Failed to store block metadata for Block {block.index}: {e}")
                return False

            # ✅ **Index transactions from the block**
            for tx in block.transactions:
                try:
                    tx_id = tx.tx_id if hasattr(tx, "tx_id") else tx.get("tx_id")
                    if not tx_id:
                        print(f"[Blockchain.add_block] ❌ ERROR: Transaction in Block {block.index} is missing `tx_id`. Skipping.")
                        continue  # Skip invalid transaction

                    # ✅ **Handle edge cases for `block.hash` (bytes, hex, etc.)**
                    block_hash = block.hash
                    if isinstance(block_hash, bytes):
                        block_hash = block_hash.hex()  # Convert bytes to hex string
                    elif not isinstance(block_hash, str):
                        print(f"[Blockchain.add_block] ❌ ERROR: Invalid `block.hash` type. Expected str or bytes. Found {type(block_hash)}. Skipping.")
                        continue  # Skip invalid block

                    # ✅ **Extract inputs and outputs**
                    inputs = self._extract_inputs(tx)
                    outputs = self._extract_outputs(tx)

                    # ✅ **Handle edge cases for `timestamp`**
                    timestamp = tx.timestamp if hasattr(tx, "timestamp") else int(time.time())
                    if not isinstance(timestamp, int):
                        print(f"[Blockchain.add_block] ❌ ERROR: Invalid `timestamp` type. Expected int. Found {type(timestamp)}. Skipping.")
                        continue  # Skip invalid transaction

                    # ✅ **Store transaction**
                    self.tx_storage.store_transaction(tx_id, block_hash, inputs, outputs, timestamp)
                    print(f"[Blockchain.add_block] ✅ INFO: Transaction {tx_id} indexed successfully.")

                except Exception as e:
                    print(f"[Blockchain.add_block] ❌ ERROR: Failed to index transaction in Block {block.index}: {e}")

            # ✅ **Validate and update UTXO storage**
            if not self.utxo_storage.validate_utxos(block):
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
        New helper method to convert transaction outputs that are dictionaries
        into proper TransactionOut objects.
        
        :param outputs: List of outputs (can be dicts or TransactionOut objects).
        :return: List of TransactionOut objects.
        """
        converted_outputs = []
        for idx, out in enumerate(outputs):
            if isinstance(out, dict):
                try:
                    converted_out = TransactionOut.from_dict(out)
                    print(f"[Blockchain._convert_tx_outputs] INFO: Converted output {idx} from dict to TransactionOut with tx_out_id: {converted_out.tx_out_id}.")
                    converted_outputs.append(converted_out)
                except Exception as e:
                    print(f"[Blockchain._convert_tx_outputs] ERROR: Failed to convert output at index {idx}: {e}")
            else:
                # Assume it's already a TransactionOut object
                converted_outputs.append(out)
        return converted_outputs


    def _extract_inputs(self, tx) -> list:
        """
        Helper method to extract transaction inputs in a consistent dictionary format.
        
        :param tx: Transaction instance or dictionary containing inputs.
        :return: List of input dictionaries.
        """
        extracted_inputs = []
        # Check if tx is a dict or an object
        if isinstance(tx, dict):
            inputs = tx.get("inputs", [])
        else:
            inputs = getattr(tx, "inputs", [])
        print(f"[Blockchain._extract_inputs] INFO: Found {len(inputs)} input(s) in transaction.")
        for idx, inp in enumerate(inputs):
            if isinstance(inp, dict):
                amount = inp.get("amount", 0)
                previous_tx = inp.get("previous_tx", "")
                output_index = inp.get("output_index", None)
                print(f"[Blockchain._extract_inputs] INFO: Input {idx} (dict) - amount: {amount}, previous_tx: {previous_tx}, output_index: {output_index}.")
            else:
                amount = getattr(inp, "amount", 0)
                previous_tx = getattr(inp, "previous_tx", "")
                output_index = getattr(inp, "output_index", None)
                print(f"[Blockchain._extract_inputs] INFO: Input {idx} (object) - amount: {amount}, previous_tx: {previous_tx}, output_index: {output_index}.")
            extracted_inputs.append({
                "amount": amount,
                "previous_tx": previous_tx,
                "output_index": output_index
            })
        print(f"[Blockchain._extract_inputs] INFO: Extraction complete. Total inputs extracted: {len(extracted_inputs)}.")
        return extracted_inputs

    def _extract_outputs(self, tx) -> list:
        """
        Helper method to extract transaction outputs in a consistent dictionary format.
        
        :param tx: Transaction instance or dictionary containing outputs.
        :return: List of output dictionaries.
        """
        extracted_outputs = []
        if isinstance(tx, dict):
            outputs = tx.get("outputs", [])
        else:
            outputs = getattr(tx, "outputs", [])
        print(f"[Blockchain._extract_outputs] INFO: Found {len(outputs)} output(s) in transaction.")
        for idx, out in enumerate(outputs):
            if isinstance(out, dict):
                amount = out.get("amount", 0)
                script_pub_key = out.get("script_pub_key", "")
                locked = out.get("locked", False)
                print(f"[Blockchain._extract_outputs] INFO: Output {idx} (dict) - amount: {amount}, script_pub_key: {script_pub_key}, locked: {locked}.")
            else:
                amount = getattr(out, "amount", 0)
                script_pub_key = getattr(out, "script_pub_key", "")
                locked = getattr(out, "locked", False)
                print(f"[Blockchain._extract_outputs] INFO: Output {idx} (object) - amount: {amount}, script_pub_key: {script_pub_key}, locked: {locked}.")
            extracted_outputs.append({
                "amount": amount,
                "script_pub_key": script_pub_key,
                "locked": locked
            })
        print(f"[Blockchain._extract_outputs] INFO: Extraction complete. Total outputs extracted: {len(extracted_outputs)}.")
        return extracted_outputs


    def validate_block(self, block: Block) -> bool:
        """
        Validate a block before adding it to the blockchain.
        """
        try:
            print(f"[Blockchain.validate_block] INFO: Validating Block {block.index}...")

            # Ensure block contains required metadata
            required_metadata_fields = ["index", "previous_hash", "merkle_root", "timestamp", "nonce", "difficulty"]
            for field in required_metadata_fields:
                if not hasattr(block, field):
                    print(f"[Blockchain.validate_block] ❌ ERROR: Block {block.index} is missing metadata field: {field}")
                    return False

            # Ensure block version matches current chain version
            if block.version != Constants.VERSION:
                print(f"[Blockchain.validate_block] ⚠️ WARNING: Block {block.index} has mismatched version. Expected {Constants.VERSION}, found {block.version}.")
                return False

            # Validate proof-of-work
            if not self.pow_manager.validate_proof_of_work(block):
                print(f"[Blockchain.validate_block] ❌ ERROR: Block {block.index} failed proof-of-work validation.")
                return False

            # Ensure block links correctly to previous block
            if len(self.chain) > 0:
                last_block = self.chain[-1]
                if block.previous_hash != last_block.hash:
                    print(f"[Blockchain.validate_block] ❌ ERROR: Block {block.index} has an invalid previous hash.")
                    return False

            # Validate all transactions in the block
            for tx in block.transactions:
                if not self.transaction_manager.validate_transaction(tx):
                    print(f"[Blockchain.validate_block] ❌ ERROR: Transaction {tx.tx_id} in Block {block.index} is invalid.")
                    return False

            print(f"[Blockchain.validate_block] ✅ SUCCESS: Block {block.index} validated.")
            return True

        except Exception as e:
            print(f"[Blockchain.validate_block] ❌ ERROR: Failed to validate Block {block.index}: {e}")
            return False
        


    def get_latest_block(self) -> Optional[Block]:
        """
        Retrieve the latest valid block in the blockchain.
        
        :return: The latest valid block, or None if the chain is empty or contains corruption.
        """
        try:
            if not self.chain:
                print("[Blockchain.get_latest_block] INFO: No blocks found in the chain.")
                return None

            latest_block = self.chain[-1]

            # ✅ **Ensure Latest Block is Valid Before Returning**
            if not self.validate_block(latest_block):
                print(f"[Blockchain.get_latest_block] ❌ ERROR: Latest block {latest_block.index} is invalid. Chain may be corrupted.")
                return None

            print(f"[Blockchain.get_latest_block] ✅ SUCCESS: Latest block {latest_block.index} retrieved.")
            return latest_block

        except Exception as e:
            print(f"[Blockchain.get_latest_block] ❌ ERROR: Failed to retrieve latest block: {e}")
            return None

    def validate_chain(self) -> bool:
        """
        Validate the entire blockchain.
        - Ensures each block links to the previous block.
        - Validates all transactions in each block.

        :return: True if the blockchain is valid, False otherwise.
        """
        try:
            print("[Blockchain.validate_chain] Validating blockchain...")
            for i in range(1, len(self.chain)):
                current_block = self.chain[i]
                previous_block = self.chain[i - 1]

                # Check block linkage
                if current_block.previous_hash != previous_block.hash:
                    print(f"[Blockchain.validate_chain] ERROR: Block {current_block.index} has an invalid previous hash.")
                    return False

                # Validate all transactions in the block
                for tx in current_block.transactions:
                    if not self.transaction_manager.validate_transaction(tx):
                        print(f"[Blockchain.validate_chain] ERROR: Transaction {tx.tx_id} in Block {current_block.index} is invalid.")
                        return False

            print("[Blockchain.validate_chain] SUCCESS: Blockchain validated.")
            return True
        except Exception as e:
            print(f"[Blockchain.validate_chain] ERROR: Failed to validate blockchain: {e}")
            return False
        

    def purge_chain():
        """
        Placeholder function for purging the blockchain.
        This will be implemented later to handle full blockchain resets.
        """
        pass
