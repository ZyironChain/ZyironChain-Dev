import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.transactions.transactiontype import PaymentType
import sys
import os
import hashlib
import time
import json
from typing import Optional
from Zyiron_Chain.transactions.transactiontype import TransactionType
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
from Zyiron_Chain.blockchain.utils.hashing import sha3_384
from Zyiron_Chain.transactions.fees import FeeModel

class BlockHeader:
    def __init__(self, version, index, previous_hash, merkle_root, timestamp, nonce):
        """
        Initialize a BlockHeader object.
        :param version: The version of the block header.
        :param index: The index of the block in the blockchain.
        :param previous_hash: The hash of the previous block.
        :param merkle_root: The Merkle root of the block's transactions.
        :param timestamp: The timestamp of the block.
        :param nonce: The nonce used for mining.
        """
        self.version = version
        self.index = index
        self.previous_hash = previous_hash
        self.merkle_root = merkle_root
        self.timestamp = timestamp
        self.nonce = nonce

    def to_dict(self):
        """
        Convert the BlockHeader object into a dictionary for serialization.
        """
        return {
            "version": self.version,
            "index": self.index,  # Include index in the serialized dictionary
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
        }


    @staticmethod
    def from_dict(data: dict):
        """
        Reconstruct a BlockHeader object from its dictionary representation.
        Handles missing fields with appropriate defaults or raises errors for critical fields.
        """
        required_keys = {"version", "index", "previous_hash", "merkle_root", "timestamp", "nonce"}
        missing_keys = required_keys - data.keys()
        if missing_keys:
            raise KeyError(f"Missing required keys in BlockHeader data: {missing_keys}")

        return BlockHeader(
            version=data["version"],
            index=data["index"],  # Ensure index is included
            previous_hash=data["previous_hash"],
            merkle_root=data["merkle_root"],
            timestamp=data["timestamp"],
            nonce=data["nonce"],
        )

    def calculate_hash(self):
        """
        Calculates the double SHA-3 384 hash of the block header.
        """
        header_string = (
            f"{self.version}{self.index}{self.previous_hash}{self.merkle_root}{self.timestamp}{self.nonce}"
        )
        # Apply double SHA-3 384 hashing
        first_hash = hashlib.sha3_384(header_string.encode()).digest()
        return hashlib.sha3_384(first_hash).hexdigest()

    @property
    def hash_block(self):
        """
        Returns the hash of the block header.
        """
        return self.calculate_hash()
    def validate(self):
        """
        Validate the integrity of the BlockHeader fields.
        """
        if not isinstance(self.version, int) or self.version <= 0:
            raise ValueError("Invalid version: Must be a positive integer.")
        if not isinstance(self.index, int) or self.index < 0:
            raise ValueError("Invalid index: Must be a non-negative integer.")
        if not isinstance(self.previous_hash, str) or len(self.previous_hash) != 96:
            raise ValueError("Invalid previous_hash: Must be a 96-character string.")
        if not isinstance(self.merkle_root, str) or len(self.merkle_root) != 96:
            raise ValueError("Invalid merkle_root: Must be a 96-character string.")
        if not isinstance(self.timestamp, (int, float)) or self.timestamp <= 0:
            raise ValueError("Invalid timestamp: Must be a positive number.")
        if not isinstance(self.nonce, int) or self.nonce < 0:
            raise ValueError("Invalid nonce: Must be a non-negative integer.")

    def __repr__(self):
        """
        Returns a string representation of the block header for debugging.
        """
        return (
            f"BlockHeader(version={self.version}, index={self.index}, previous_hash={self.previous_hash[:10]}..., "
            f"merkle_root={self.merkle_root[:10]}..., nonce={self.nonce}, timestamp={self.timestamp})"
        )


import time
from typing import List, Union
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction  # Ensure this import is correct

import time
from typing import List, Union
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction  # Ensure this import is correct

class Block:
    def __init__(self, index, previous_hash, transactions, timestamp=None, nonce=0, miner_address=None):
        """
        Initialize a Block object.
        :param index: The index of the block in the blockchain.
        :param previous_hash: The hash of the previous block.
        :param transactions: A list of transactions (can be Transaction objects or dictionaries).
        :param timestamp: The timestamp of the block (defaults to current time if not provided).
        :param nonce: The nonce used for mining (defaults to 0).
        :param miner_address: The public key hash of the miner who mined the block.
        """
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = self._ensure_transactions(transactions)  # Ensure transactions are Transaction objects
        self.timestamp = timestamp or time.time()
        self.nonce = nonce
        self.miner_address = miner_address  # Miner's public key hash
        self.hash = None
        self.merkle_root = None

        # Initialize the block header
        self.header = BlockHeader(
            version=1,
            index=self.index,  # Pass index to the header
            previous_hash=self.previous_hash,
            merkle_root=self.merkle_root,
            timestamp=self.timestamp,
            nonce=self.nonce,
        )


    def _ensure_transactions(self, transactions: List[Union[Transaction, dict]]) -> List[Transaction]:
        """
        Ensure that all transactions are Transaction objects.
        :param transactions: A list of transactions (can be Transaction objects or dictionaries).
        :return: A list of Transaction objects.
        """
        validated_transactions = []
        for tx in transactions:
            if isinstance(tx, dict):  # If transaction is a dictionary, convert it to a Transaction object
                tx = Transaction.from_dict(tx)
            validated_transactions.append(tx)
        return validated_transactions


    def to_dict(self):
        """
        Convert the Block object into a dictionary for serialization.
        This method is required for storing the block in a database or for JSON serialization.
        """
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "transactions": [tx.to_dict() if hasattr(tx, 'to_dict') else tx for tx in self.transactions],  # Handle both Transaction objects and dictionaries
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "miner_address": self.miner_address,  # Include miner's address
            "hash": self.hash,
            "merkle_root": self.merkle_root,
            "header": self.header.to_dict()  # Serialize block header
        }

    @classmethod
    def from_dict(cls, data):
        """
        Create a Block instance from a dictionary.
        :param data: Dictionary representation of a block.
        :return: Block instance.
        """
        try:
            # Validate required keys in the input data
            required_keys = ["index", "transactions", "previous_hash", "header", "hash", "miner_address"]
            for key in required_keys:
                if key not in data:
                    raise KeyError(f"Missing required key: '{key}' in block data.")

            # Extract block header data
            header = BlockHeader.from_dict(data["header"])

            # Create the Block instance
            block = cls(
                index=data["index"],
                transactions=data["transactions"],
                previous_hash=data["previous_hash"],
                miner_address=data["miner_address"]  # Include miner's address
            )

            # Attach the header and hash to the block
            block.header = header
            block.hash = data["hash"]

            return block

        except KeyError as e:
            print(f"[ERROR] Missing key during block deserialization: {e}")
            raise
        except ValueError as e:
            print(f"[ERROR] Validation error during block deserialization: {e}")
            raise
        except Exception as e:
            print(f"[ERROR] Unexpected error during block deserialization: {e}")
            raise




    def validate_transaction(self, tx):
        """
        Validate a transaction to ensure it has all required fields.
        :param tx: The transaction to validate.
        :return: True if the transaction is valid, False otherwise.
        """
        required_fields = ["tx_id", "tx_inputs", "tx_outputs"]
        if isinstance(tx, dict):
            for field in required_fields:
                if field not in tx:
                    print(f"[ERROR] Transaction is missing required field: {field}")
                    return False
        elif isinstance(tx, Transaction):
            if not hasattr(tx, "tx_id") or not hasattr(tx, "tx_inputs") or not hasattr(tx, "tx_outputs"):
                print(f"[ERROR] Transaction object is missing required fields.")
                return False
        else:
            print(f"[ERROR] Invalid transaction type: {type(tx)}")
            return False
        return True







    def validate_transactions(self, fee_model, mempool, block_size):
        """
        Validate all transactions in the block.
        :param fee_model: FeeModel instance for fee validation.
        :param mempool: Mempool instance to determine congestion and total size.
        :param block_size: Current block size in MB.
        :return: True if all transactions are valid, False otherwise.
        """
        payment_type_manager = PaymentType()  # Initialize PaymentType manager

        for tx in self.transactions:
            # Skip coinbase transaction (it has no inputs)
            if isinstance(tx, dict):
                continue

            # Determine the transaction type based on its ID
            tx_type = payment_type_manager.get_payment_type(tx.tx_id)
            if tx_type == "Unknown":
                print(f"[ERROR] Invalid transaction type for transaction: {tx.tx_id}")
                return False

            # Validate transaction based on its type
            if not self._validate_transaction_by_type(tx, tx_type, fee_model, mempool, block_size):
                return False

        print("[INFO] All transactions in the block are valid.")
        return True

    def _validate_transaction_by_type(self, tx, tx_type, fee_model, mempool, block_size):
        """
        Validate a transaction based on its type.
        :param tx: The transaction to validate.
        :param tx_type: The type of the transaction (e.g., "Instant", "Smart", "Standard").
        :param fee_model: FeeModel instance for fee validation.
        :param mempool: Mempool instance to determine congestion and total size.
        :param block_size: Current block size in MB.
        :return: True if the transaction is valid, False otherwise.
        """
        # Calculate transaction size
        tx_size = sum(
            len(str(inp.to_dict())) + len(str(out.to_dict()))
            for inp, out in zip(tx.tx_inputs, tx.tx_outputs)
        )

        # Validate fees
        required_fee = fee_model.calculate_fee(
            block_size=block_size,
            payment_type=tx_type,  # Use transaction type for fee calculation
            amount=mempool.get_total_size(),
            tx_size=tx_size
        )
        actual_fee = sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)
        if actual_fee < required_fee:
            print(f"[ERROR] Transaction {tx.tx_id} does not meet the required fees for type {tx_type}.")
            return False

        # Additional validation for specific transaction types
        if tx_type == "Instant":
            # Instant transactions require 1-2 block confirmations
            print(f"[INFO] Instant transaction {tx.tx_id} requires 1-2 block confirmations.")
        elif tx_type == "Smart":
            # Smart transactions require 4-6 block confirmations
            print(f"[INFO] Smart transaction {tx.tx_id} requires 4-6 block confirmations.")

        return True

    def update_utxos(self, utxos):
        """
        Update the UTXO set based on the block's transactions.
        :param utxos: The UTXO dictionary to update.
        """
        for tx in self.transactions:
            if isinstance(tx, dict):
                tx_id = tx["tx_id"]

                # Add transaction outputs to UTXOs
                for index, output in enumerate(tx.get("tx_outputs", [])):
                    utxo_key = f"{tx_id}:{index}"
                    utxos[utxo_key] = output

                # Remove transaction inputs from UTXOs
                for tx_input in tx.get("tx_inputs", []):
                    spent_utxo_key = f"{tx_input['tx_out_id']}:{tx_input['index']}"
                    if spent_utxo_key in utxos:
                        del utxos[spent_utxo_key]

    def set_header(self, version: int, merkle_root: str):
        """
        Sets the block header and calculates its hash.
        :param version: The version of the block header.
        :param merkle_root: The Merkle root of the block's transactions.
        """
        if not merkle_root or len(merkle_root) != 96:
            raise ValueError("[ERROR] Invalid Merkle root provided.")

        # Update the block header
        self.header = BlockHeader(
            version=version,
            index=self.index,  # Use the existing index from the block
            previous_hash=self.previous_hash,
            merkle_root=merkle_root,
            timestamp=self.timestamp,
            nonce=self.nonce,
        )
        self.hash = self.header.calculate_hash()
        print(f"[INFO] Block header set with Merkle root: {merkle_root}")

    def calculate_hash(self):
        """
        Calculate the hash of the block using its header.
        """
        if not self.header:
            raise ValueError("Header must be set before calculating the hash.")
        self.hash = self.header.calculate_hash()
        return self.hash

    def mine(self, target, fee_model, mempool, block_size, newBlockAvailable: bool, network_manager=None):
        """
        Perform proof-of-work to mine the block.
        :param target: The mining target based on difficulty.
        :param fee_model: FeeModel instance for validating transaction fees.
        :param mempool: Mempool instance to access pending transactions.
        :param block_size: Maximum block size in MB.
        :param newBlockAvailable: Boolean to stop mining if a new block is available.
        :param network_manager: Optional NetworkManager instance for P2P communication.
        """
        if not self.header:
            raise ValueError("Header must be set before mining.")

        # Ensure miner address is set
        if not self.miner_address:
            raise ValueError("Miner address must be set before mining.")

        # Skip fee calculation for the genesis block as it doesn't have inputs
        if self.index == 0:
            print("[INFO] Genesis block detected. Skipping fee validation.")
            total_fee = 0  # No fees for the genesis block
        else:
            # Process transactions normally for other blocks
            total_fee = 0
            for tx in self.transactions:
                # Skip coinbase transaction (it has no inputs)
                if isinstance(tx, dict) or not hasattr(tx, 'tx_inputs'):
                    continue

                # Validate transaction before processing
                if not self.validate_transaction(tx):
                    print(f"[ERROR] Skipping invalid transaction: {tx}")
                    continue

                # Calculate transaction size
                tx_size = sum(
                    len(str(inp.to_dict())) + len(str(out.to_dict()))
                    for inp, out in zip(tx.tx_inputs, tx.tx_outputs)
                )

                # Validate fees
                try:
                    # Ensure mempool has the required method
                    if hasattr(mempool, 'get_total_size'):
                        mempool_size = mempool.get_total_size()
                    else:
                        print("[WARNING] Mempool does not have 'get_total_size' method. Using default size.")
                        mempool_size = 0  # Default size if method is missing

                    required_fee = fee_model.calculate_fee(
                        block_size=block_size,
                        payment_type="Standard",  # Adjust payment type if needed
                        amount=mempool_size,
                        tx_size=tx_size
                    )
                    actual_fee = sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)
                    if actual_fee < required_fee:
                        print(f"[ERROR] Transaction {tx.tx_id} does not meet the required fees.")
                        return False

                    total_fee += actual_fee  # Fix: Use actual_fee instead of tx_fee
                except Exception as e:
                    print(f"[ERROR] Error calculating fees for transaction {tx.tx_id}: {e}")
                    return False

        # Start mining
        self.header.nonce = 0
        print(f"[INFO] Mining block {self.index}...")
        while int(self.calculate_hash(), 16) > target:
            if newBlockAvailable:
                print("[INFO] New block available. Stopping mining.")
                return False

            # Increment nonce and recalculate hash
            self.header.nonce += 1
            self.hash = self.calculate_hash()
            print(f"Mining... Nonce: {self.header.nonce}", end="\r")

        print("\n[INFO] Mining Completed!")
        print(f"[INFO] Block {self.index} mined successfully! Nonce: {self.header.nonce}")

        # Broadcast the mined block to the network if network_manager is provided
        if network_manager:
            network_manager.broadcast_block(self.to_dict())
        else:
            print("[INFO] Network manager not provided. Skipping block broadcast.")

        return True


    @staticmethod
    def validate_block(block_data, blockchain):
        """
        Validate a block received from the network.
        :param block_data: The block data (dictionary).
        :param blockchain: The local blockchain instance.
        :return: True if the block is valid, False otherwise.
        """
        try:
            # Deserialize the block
            block = Block.from_dict(block_data)

            # Verify the proof-of-work
            if int(block.calculate_hash(), 16) > blockchain.current_target:
                print("[ERROR] Block does not meet the proof-of-work target.")
                return False

            # Verify the previous hash
            if block.previous_hash != blockchain.get_latest_block().hash:
                print("[ERROR] Block does not link to the latest block in the chain.")
                return False

            # Validate all transactions in the block
            if not block.validate_transactions(blockchain.fee_model, blockchain.mempool, blockchain.block_size):
                print("[ERROR] Block contains invalid transactions.")
                return False

            return True
        except Exception as e:
            print(f"[ERROR] Block validation failed: {e}")
            return False


    def __repr__(self):
        """
        Returns a string representation of the block for debugging.
        """
        hash_preview = self.hash[:10] + "..." if self.hash else "None"
        previous_hash_preview = self.previous_hash[:10] + "..." if self.previous_hash else "None"
        return (f"Block(index={self.index}, hash={hash_preview}, previous_hash={previous_hash_preview}, "
                f"transactions={len(self.transactions)}, nonce={self.header.nonce if self.header else 0}, "
                f"timestamp={self.timestamp})")