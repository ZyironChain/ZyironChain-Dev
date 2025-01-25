import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)





import hashlib
import time
import json
from typing import Optional

from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
from Zyiron_Chain.blockchain.utils.hashing import sha3_384
import hashlib
import time

class BlockHeader:
    def __init__(self, version, previous_hash, merkle_root, timestamp, nonce):
        """
        Initialize a BlockHeader object.
        :param version: Version of the block.
        :param previous_hash: Hash of the previous block header.
        :param merkle_root: Merkle root of the transactions in the block.
        :param timestamp: Timestamp of block creation.
        :param nonce: Nonce used for mining.
        """
        self.version = version
        self.previous_hash = previous_hash
        self.merkle_root = merkle_root
        self.timestamp = timestamp
        self.nonce = nonce

    def to_dict(self):
        """
        Convert the BlockHeader object into a dictionary for JSON serialization.
        """
        return {
            "version": self.version,
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
        required_keys = {"version", "previous_hash", "merkle_root", "timestamp", "nonce"}
        missing_keys = required_keys - data.keys()
        if missing_keys:
            raise KeyError(f"Missing required keys in BlockHeader data: {missing_keys}")

        # Ensure timestamp is properly formatted or provide a default if missing (for legacy support)
        timestamp = data.get("timestamp", time.time())

        return BlockHeader(
            version=data["version"],
            previous_hash=data["previous_hash"],
            merkle_root=data["merkle_root"],
            timestamp=timestamp,
            nonce=data["nonce"],
        )



    def calculate_hash(self):
        """
        Calculates the double SHA-3 384 hash of the block header.
        """
        header_string = (
            f"{self.version}{self.previous_hash}{self.merkle_root}{self.timestamp}{self.nonce}"
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
            f"BlockHeader(version={self.version}, previous_hash={self.previous_hash[:10]}..., "
            f"merkle_root={self.merkle_root[:10]}..., nonce={self.nonce}, "
            f"timestamp={self.timestamp})"
        )



class Block:
    def __init__(self, index, previous_hash, transactions, timestamp=None, nonce=0):
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.timestamp = timestamp or time.time()
        self.nonce = nonce
        self.hash = None
        self.merkle_root = None

        # Initialize the block header if needed
        self.header = BlockHeader(
            version=1,
            previous_hash=self.previous_hash,
            merkle_root=self.merkle_root,
            timestamp=self.timestamp,
            nonce=self.nonce,
        )



    def validate_transactions(self, fee_model, mempool, block_size):
        """
        Validate all transactions in the block.
        :param fee_model: FeeModel instance for fee validation.
        :param mempool: Mempool instance to determine congestion and total size.
        :param block_size: Current block size in MB.
        :return: True if all transactions are valid, False otherwise.
        """
        for tx in self.transactions:
            if isinstance(tx, dict):  # Skip coinbase transaction
                continue

            # Calculate transaction size
            tx_size = sum(
                len(str(inp.to_dict())) + len(str(out.to_dict()))
                for inp, out in zip(tx.tx_inputs, tx.tx_outputs)
            )

            # Validate fees
            required_fee = fee_model.calculate_fee(
                block_size=block_size,
                payment_type="Standard",  # Adjust if using multiple payment types
                amount=mempool.get_total_size(),
                tx_size=tx_size
            )
            actual_fee = sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)
            if actual_fee < required_fee:
                print(f"[ERROR] Transaction {tx.tx_id} does not meet the required fees.")
                return False

        print("[INFO] All transactions in the block are valid.")
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
        """
        if not merkle_root or len(merkle_root) != 96:
            raise ValueError("[ERROR] Invalid Merkle root provided.")
        self.header = BlockHeader(
            version=version,
            previous_hash=self.previous_hash,
            merkle_root=merkle_root,
            timestamp=self.timestamp,
            nonce=0,
        )
        self.hash = self.header.calculate_hash()
        print(f"[INFO] Block header set with Merkle root: {merkle_root}")


    @classmethod
    def from_dict(cls, data):
        """
        Create a Block instance from a dictionary.
        :param data: Dictionary representation of a block.
        :return: Block instance.
        """
        try:
            # Validate required keys in the input data
            required_keys = ["index", "transactions", "previous_hash", "header", "hash"]
            for key in required_keys:
                if key not in data:
                    raise KeyError(f"Missing required key: '{key}' in block data.")

            header_keys = ["version", "previous_hash", "merkle_root", "nonce"]
            for key in header_keys:
                if key not in data["header"]:
                    raise KeyError(f"Missing required key: '{key}' in block header.")

            # Extract block header data
            header = BlockHeader(
                version=data["header"]["version"],
                previous_hash=data["header"]["previous_hash"],
                merkle_root=data["header"]["merkle_root"],
                nonce=data["header"]["nonce"]
            )

            # Validate `previous_hash` in both block and header
            if data["previous_hash"] != header.previous_hash:
                raise ValueError(
                    f"Inconsistent 'previous_hash': Block has {data['previous_hash']} but header has {header.previous_hash}"
                )

            # Create the Block instance
            block = cls(
                index=data["index"],
                transactions=data["transactions"],
                previous_hash=data["previous_hash"]  # Ensure `previous_hash` is extracted correctly
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

    def calculate_hash(self):
        """
        Calculate the hash of the block using its header.
        """
        if not self.header:
            raise ValueError("Header must be set before calculating the hash.")
        self.hash = self.header.calculate_hash()
        return self.hash

    def mine(self, target: int, fee_model, mempool, block_size, newBlockAvailable: bool):
        """
        Perform proof-of-work to mine the block.
        :param target: The mining target based on difficulty.
        :param fee_model: FeeModel instance for validating transaction fees.
        :param mempool: Mempool instance to access pending transactions.
        :param block_size: Maximum block size in MB.
        :param newBlockAvailable: Boolean to stop mining if a new block is available.
        """
        if not self.header:
            raise ValueError("Header must be set before mining.")

        self.header.nonce = 0
        while int(self.calculate_hash(), 16) > target:
            # Ensure transactions in the block meet fee requirements
            for tx in self.transactions:
                if isinstance(tx, dict):  # Skip validation for coinbase transactions
                    continue

                tx_size = sum(
                    len(str(inp.to_dict())) + len(str(out.to_dict()))
                    for inp, out in zip(tx.tx_inputs, tx.tx_outputs)
                )
                required_fee = fee_model.calculate_fee(
                    block_size=block_size,
                    payment_type="Standard",  # Adjust as needed
                    amount=mempool.get_total_size(),
                    tx_size=tx_size
                )
                actual_fee = sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)
                if actual_fee < required_fee:
                    print(f"[ERROR] Transaction {tx.tx_id} does not meet the required fees. Aborting mining.")
                    return False

            if newBlockAvailable:
                return False

            self.header.nonce += 1
            self.hash = self.calculate_hash()
            print(f"Mining... Nonce: {self.header.nonce}", end="\r")

        print("\nMining Completed!")
        return True
    def __repr__(self):
        """
        Returns a string representation of the block for debugging.
        """
        hash_preview = self.hash[:10] + "..." if self.hash else "None"
        previous_hash_preview = self.previous_hash[:10] + "..." if self.previous_hash else "None"
        return (f"Block(index={self.index}, hash={hash_preview}, previous_hash={previous_hash_preview}, "
                f"transactions={len(self.transactions)}, nonce={self.header.nonce if self.header else 0}, "
                f"timestamp={self.timestamp})")
