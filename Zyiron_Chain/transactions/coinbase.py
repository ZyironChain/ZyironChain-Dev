import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))





import time
import hashlib
from decimal import Decimal
from typing import Dict
from Zyiron_Chain.blockchain.constants import Constants

class CoinbaseTx:
    """Represents a block reward transaction"""

    def __init__(self, block_height: int, miner_address: str, reward: Decimal = None):
        """
        Initializes a Coinbase transaction.

        :param block_height: The height of the block.
        :param miner_address: The recipient miner's address.
        :param reward: The reward amount (defaults to Constants.INITIAL_COINBASE_REWARD).
        """
        self.block_height = block_height
        self.miner_address = miner_address
        self.reward = reward if reward else Decimal(Constants.INITIAL_COINBASE_REWARD)
        self.timestamp = time.time()
        self.tx_id = self._generate_tx_id(block_height, self.timestamp)
        self.inputs = []  # Coinbase transactions have no inputs
        self.outputs = [{"address": miner_address, "amount": float(self.reward)}]
        self.type = "COINBASE"
        self.fee = Decimal("0")
        self.hash = self.calculate_hash()

    def _generate_tx_id(self, block_height: int, timestamp: float) -> str:
        """Generate a unique transaction ID using SHA3-384 hashing"""
        tx_data = f"COINBASE-{block_height}-{timestamp}-{self.miner_address}-{self.reward}"
        return hashlib.sha3_384(tx_data.encode()).hexdigest()[:24]

    def calculate_hash(self) -> str:
        """Calculate SHA3-384 hash of the transaction"""
        tx_data = f"{self.tx_id}{self.timestamp}{self.outputs[0]['address']}{self.outputs[0]['amount']}"
        return hashlib.sha3_384(tx_data.encode()).hexdigest()

    def to_dict(self) -> Dict:
        """Serialize CoinbaseTx to a dictionary"""
        return {
            "tx_id": self.tx_id,
            "block_height": self.block_height,
            "miner_address": self.miner_address,
            "reward": str(self.reward),  # Convert Decimal to string for serialization
            "inputs": self.inputs,
            "outputs": self.outputs,
            "timestamp": self.timestamp,
            "type": self.type,
            "hash": self.hash
        }

    @classmethod
    def from_dict(cls, data: Dict):
        """Deserialize CoinbaseTx from a dictionary"""
        return cls(
            block_height=data["block_height"],
            miner_address=data["miner_address"],
            reward=Decimal(data["reward"])
        )

    @property
    def is_coinbase(self) -> bool:
        """Identify as a coinbase transaction"""
        return True
