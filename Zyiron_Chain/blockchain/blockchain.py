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
        """
        try:
            print("[Blockchain.load_chain_from_storage] INFO: Loading chain from storage...")

            # Retrieve all stored blocks
            stored_blocks = self.block_metadata.get_all_blocks()
            if not stored_blocks:
                print("[Blockchain.load_chain_from_storage] WARNING: No blocks found in storage.")
                return []  # Explicitly return an empty list

            loaded_blocks = []
            for block_data in stored_blocks:
                try:
                    # Ensure block data is valid before processing
                    if not isinstance(block_data, dict) or "index" not in block_data or "hash" not in block_data:
                        print(f"[Blockchain.load_chain_from_storage] ❌ WARNING: Skipping corrupted block: {block_data}")
                        continue

                    # Deserialize the block safely
                    block = Block.from_dict(block_data)
                    if not self.validate_block(block):
                        print(f"[Blockchain.load_chain_from_storage] ❌ WARNING: Skipping invalid block at height {block.index}")
                        continue

                    # Add valid block to the list
                    loaded_blocks.append(block)

                except Exception as block_error:
                    print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Failed to process block: {block_error}")

            print(f"[Blockchain.load_chain_from_storage] ✅ SUCCESS: Loaded {len(loaded_blocks)} valid blocks from storage.")
            return loaded_blocks

        except Exception as e:
            print(f"[Blockchain.load_chain_from_storage] ❌ ERROR: Failed to load chain from storage: {e}")
            return []  # Return an empty list on any failure


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

            # ✅ **Validate block structure before adding (skip validation for Genesis)**
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

            # ✅ **Store block metadata and full block data**
            self.block_metadata.store_block(block, block.difficulty)
            print(f"[Blockchain.add_block] ✅ INFO: Block {block.index} metadata stored successfully.")

            # ✅ **Index transactions from the block**
            for tx in block.transactions:
                try:
                    tx_id = tx.tx_id if hasattr(tx, "tx_id") else tx.get("tx_id")
                    if not tx_id:
                        print(f"[Blockchain.add_block] ❌ ERROR: Transaction in Block {block.index} is missing `tx_id`. Skipping.")
                        continue  # Skip invalid transaction

                    block_hash = block.hash
                    inputs = self._extract_inputs(tx)
                    outputs = self._extract_outputs(tx)
                    timestamp = tx.timestamp if hasattr(tx, "timestamp") else int(time.time())

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
