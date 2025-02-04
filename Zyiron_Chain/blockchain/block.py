import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))






import hashlib
import time
import json
from typing import Optional, List, Union




from multiprocessing import Pool
import time
import json
from typing import List, Dict, Union
from decimal import Decimal
from Zyiron_Chain.blockchain.blockheader import BlockHeader
from Zyiron_Chain. transactions.transactiontype import PaymentTypeManager
from Zyiron_Chain. transactions.fees import FeeModel
from Zyiron_Chain.blockchain.helper import get_poc, get_transaction, get_coinbase_tx, get_block_header
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
PoC = get_poc()
Transaction = get_transaction()
CoinbaseTx = get_coinbase_tx()
BlockHeader = get_block_header()


class Block:

    def __init__(self, index, previous_hash, transactions, timestamp=None, key_manager=None, nonce=0, poc=None):
        """
        Initialize a Block.
        :param index: Block index in the blockchain.
        :param previous_hash: Hash of the previous block.
        :param transactions: List of transactions in the block.
        :param timestamp: Block creation timestamp (defaults to current time).
        :param key_manager: KeyManager instance for handling miner addresses.
        :param nonce: Initial nonce (used for mining).
        :param poc: PoC instance for transaction validation.
        """
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = self._ensure_transactions(transactions, poc)  # ✅ Pass `poc`
        self.timestamp = timestamp or time.time()
        self.nonce = nonce
        self.key_manager = key_manager or KeyManager()  # ✅ Default to KeyManager
        self.miner_address = self.key_manager.get_default_public_key("mainnet", "miner")  # ✅ Default miner key
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



    def _ensure_transactions(self, transactions, poc):
        return [Transaction.from_dict(tx, poc) if isinstance(tx, dict) else tx for tx in transactions]


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
        """
        Use PoC to store the block and ensure proper routing.
        The PoC will determine where to store transactions (SQLite, LMDB, etc.).
        """
        poc = PoC()
        difficulty = poc.block_manager.calculate_difficulty(self.index)  # Dynamically determine difficulty
        poc.store_block(self, difficulty)

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
            "miner_address": self.miner_address or KeyManager().get_default_public_key("mainnet", "miner"),  # ✅ Ensure miner address is always set
            "hash": self.hash or self.calculate_hash(),  # ✅ Ensure hash is never missing

            "merkle_root": self.merkle_root,
            "header": self.header.to_dict()
        }

    @classmethod
    def from_dict(cls, data):
        """Create a Block instance from a dictionary."""
        from Zyiron_Chain.blockchain.blockheader import BlockHeader  # Ensure correct import

        header = BlockHeader.from_dict(data["header"])
        block = cls(
            index=data["index"],
            previous_hash=data["previous_hash"],
            transactions=data["transactions"],
            timestamp=data["timestamp"],
            nonce=data["nonce"]
        )
        block.header = header

        # ✅ Handle missing miner_address safely
        block.miner_address = data.get("miner_address", None)  

        # ✅ Handle missing hash safely
        block.hash = data.get("hash", None)

        return block
        
    def validate_transactions(self, fee_model, mempool, block_size):
        """Validate all transactions in the block with parallelized execution."""
        payment_type_manager = PaymentTypeManager()

        # Parallelize transaction validation using multiprocessing
        with Pool() as pool:
            validation_results = pool.starmap(
                self._validate_transaction_by_type,
                [(tx, payment_type_manager.get_payment_type(tx.tx_id), fee_model, mempool, block_size) for tx in self.transactions if not isinstance(tx, dict)]
            )

        # Ensure all transactions are valid
        if all(validation_results):
            print("[INFO] All transactions in the block are valid.")
            return True
        return False

    def _validate_transaction_by_type(self, tx, tx_type, fee_model, mempool, block_size):
        """Validate a transaction based on its type and prevent replay attacks."""
        try:
            if tx_type == "Unknown":
                print(f"[ERROR] Invalid transaction type for transaction: {tx.tx_id}")
                return False

            tx_size = sum(len(str(inp.to_dict())) + len(str(out.to_dict())) for inp, out in zip(tx.tx_inputs, tx.tx_outputs))

            required_fee = fee_model.calculate_fee(block_size, tx_type, mempool.get_total_size(), tx_size)
            actual_fee = sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)

            if actual_fee < required_fee:
                print(f"[ERROR] Transaction {tx.tx_id} does not meet the required fees.")
                return False

            # Prevent replay attacks by checking nonce and network_id
            if self.poc.check_transaction_exists(tx.tx_id, tx.nonce, tx.network_id):
                print(f"[ERROR] Replay attack detected for transaction {tx.tx_id}.")
                return False

            return True
        except Exception as e:
            print(f"[ERROR] Failed transaction validation: {str(e)}")
            return False


    def get_block_difficulty(self):
        """
        Determines the difficulty for this block dynamically based on network hashrate.
        :return: The adjusted difficulty.
        """
        poc = PoC()
        return poc.block_manager.calculate_difficulty(self.index)

    def check_farm_activity(self):
        """
        Detects potential mining farms based on network hashrate changes.
        If hashrate increases too fast, activates countermeasures.
        """
        poc = PoC()
        hashrate_change = poc.get_network_hashrate_change()

        if hashrate_change > 10:
            print(f"[WARNING] Hashrate increased by {hashrate_change:.2f}% in 2 hours. Activating countermeasures.")
            poc.trigger_countermeasures(hashrate_change)

    def __repr__(self):
        """Return a string representation of the block."""
        hash_preview = self.hash[:10] + "..." if self.hash else "None"
        return (f"Block(index={self.index}, hash={hash_preview}, "
                f"previous_hash={self.previous_hash[:10]}..., "
                f"transactions={len(self.transactions)}, nonce={self.header.nonce}, "
                f"timestamp={self.timestamp})")
