import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))






import hashlib
import time
import json
from typing import Optional, List, Union





import time
import json
from typing import List, Dict, Union
from decimal import Decimal
from Zyiron_Chain.blockchain.blockheader import BlockHeader
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction, CoinbaseTx
from Zyiron_Chain. transactions.transactiontype import PaymentTypeManager
from Zyiron_Chain. transactions.fees import FeeModel
from Zyiron_Chain.database.poc import PoC


class Block:
    def __init__(self, index, previous_hash, transactions, timestamp=None, key_manager=None, nonce=0):
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = self._ensure_transactions(transactions)
        self.timestamp = timestamp or time.time()
        self.nonce = nonce
        self.key_manager = key_manager
        self.miner_address = None  # Set during mining
        self.merkle_root = self.calculate_merkle_root()

        self.header = BlockHeader(
            version=1,
            index=self.index,
            previous_hash=self.previous_hash,
            merkle_root=self.merkle_root,
            timestamp=self.timestamp,
            nonce=self.nonce
        )
        self.hash = None  # Will be calculated during PoW
    def _ensure_transactions(self, transactions: List[Union[Transaction, dict]]) -> List[Transaction]:
        """Ensure all transactions are valid `Transaction` objects."""
        return [Transaction.from_dict(tx) if isinstance(tx, dict) else tx for tx in transactions]

    def calculate_merkle_root(self):
        """Compute the Merkle root from transaction IDs."""
        tx_hashes = [tx.tx_id for tx in self.transactions]

        if not tx_hashes:
            return hashlib.sha3_384(b'').hexdigest()

        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])

            tx_hashes = [
                hashlib.sha3_384((tx_hashes[i] + tx_hashes[i + 1]).encode()).hexdigest()
                for i in range(0, len(tx_hashes), 2)
            ]

 
 
        return tx_hashes[0]



    def store_block(self):
        """Use PoC to store the block in the appropriate database."""
        from Zyiron_Chain.database.poc import PoC  # ✅ Import inside method to break circular dependency
        poc = PoC()
        poc.store_block(self, difficulty=1)  # ✅ Route block storage through PoC







    def set_header(self, version: int, merkle_root: str):
        """
        Sets the block header and calculates its hash.
        :param version: The version of the block header.
        :param merkle_root: The Merkle root of the block's transactions.
        """
        if not merkle_root or len(merkle_root) != 96:
            raise ValueError("[ERROR] Invalid Merkle root provided.")

        self.header = BlockHeader(
            version=version,
            index=self.index,
            previous_hash=self.previous_hash,
            merkle_root=merkle_root,
            timestamp=self.timestamp,
            nonce=self.nonce,
        )

        # Update the block hash after setting the header
        self.hash = self.header.calculate_hash()
        print(f"[INFO] Block header set with Merkle root: {merkle_root}")



    def calculate_hash(self):
        """
        Calculate the block hash using the block header.
        :return: The computed block hash.
        """
        if not self.header:
            raise ValueError("Header must be set before calculating the hash.")

        self.hash = self.header.calculate_hash()
        return self.hash




    def to_dict(self):
        """Convert Block into a serializable dictionary."""
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "miner_address": self.miner_address,
            "hash": self.hash,
            "merkle_root": self.merkle_root,
            "header": self.header.to_dict()
        }

    @classmethod
    def from_dict(cls, data):
        """Create a Block instance from a dictionary."""
        header = BlockHeader.from_dict(data["header"])
        block = cls(
            index=data["index"],
            previous_hash=data["previous_hash"],
            transactions=data["transactions"],
            timestamp=data["timestamp"],
            nonce=data["nonce"]
        )
        block.header = header
        block.miner_address = data["miner_address"]
        block.hash = data["hash"]
        return block

    def validate_transactions(self, fee_model, mempool, block_size):
        """Validate all transactions in the block."""
        payment_type_manager = PaymentTypeManager()

        for tx in self.transactions:
            if isinstance(tx, dict):
                continue  # Skip coinbase transactions

            tx_type = payment_type_manager.get_payment_type(tx.tx_id)
            if tx_type == "Unknown":
                print(f"[ERROR] Invalid transaction type for transaction: {tx.tx_id}")
                return False

            if not self._validate_transaction_by_type(tx, tx_type, fee_model, mempool, block_size):
                return False

        print("[INFO] All transactions in the block are valid.")
        return True

    def _validate_transaction_by_type(self, tx, tx_type, fee_model, mempool, block_size):
        """Validate a transaction based on its type."""
        tx_size = sum(len(str(inp.to_dict())) + len(str(out.to_dict())) for inp, out in zip(tx.tx_inputs, tx.tx_outputs))

        required_fee = fee_model.calculate_fee(block_size, tx_type, mempool.get_total_size(), tx_size)
        actual_fee = sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)

        if actual_fee < required_fee:
            print(f"[ERROR] Transaction {tx.tx_id} does not meet the required fees.")
            return False

        return True

    def __repr__(self):
        """Return a string representation of the block."""
        hash_preview = self.hash[:10] + "..." if self.hash else "None"
        return (f"Block(index={self.index}, hash={hash_preview}, "
                f"previous_hash={self.previous_hash[:10]}..., "
                f"transactions={len(self.transactions)}, nonce={self.header.nonce}, "
                f"timestamp={self.timestamp})")
