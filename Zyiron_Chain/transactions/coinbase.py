import time
import hashlib
from decimal import Decimal
from typing import Dict
from Zyiron_Chain.blockchain.constants import Constants

class CoinbaseTx:
    """
    Represents a block reward (coinbase) transaction.
    Uses single SHA3-384 hashing and all amounts are handled as bytes (via encoding when needed).
    Detailed print statements are used instead of logging.
    """

    def __init__(self, block_height: int, miner_address: str, reward: Decimal = None):
        print(f"[CoinbaseTx.__init__] Initializing CoinbaseTx for block {block_height}.")
        self.block_height = block_height
        self.miner_address = miner_address
        # Calculate reward dynamically based on halving intervals
        self.reward = reward if reward is not None else self._calculate_reward(block_height)
        self.timestamp = int(time.time())
        self.tx_id = self._generate_tx_id(block_height, self.timestamp)
        self.inputs = []  # Coinbase transactions have no inputs.
        self.outputs = [{
            "address": miner_address,
            "amount": float(self.reward),
            "script_pub_key": miner_address
        }]
        self.type = "COINBASE"
        self.fee = Decimal("0")
        self.hash = self.calculate_hash()
        # Estimate transaction size (as string length)
        temp_data = {
            "tx_id": self.tx_id,
            "block_height": self.block_height,
            "miner_address": self.miner_address,
            "reward": str(self.reward),
            "inputs": self.inputs,
            "outputs": self.outputs,
            "timestamp": self.timestamp,
            "type": self.type,
            "hash": self.hash,
        }
        self.size = len(str(temp_data))
        print(f"[CoinbaseTx.__init__] CoinbaseTx initialized with tx_id: {self.tx_id}")

    def _calculate_reward(self, block_height: int) -> Decimal:
        """
        Dynamically calculate the block reward based on halving intervals.
        Uses constants from Constants.
        """
        halvings = block_height // Constants.BLOCKCHAIN_HALVING_BLOCK_HEIGHT
        reward = Decimal(Constants.INITIAL_COINBASE_REWARD) / (2 ** halvings)
        calculated_reward = max(reward, Decimal(str(Constants.MIN_TRANSACTION_FEE)))
        print(f"[CoinbaseTx._calculate_reward] Calculated reward for block {block_height}: {calculated_reward}")
        return calculated_reward

    def _generate_tx_id(self, block_height: int, timestamp: int) -> str:
        """
        Generate a unique transaction ID using single SHA3-384 hashing.
        Uses a prefix from Constants if available.
        """
        prefixes = Constants.TRANSACTION_MEMPOOL_MAP.get("COINBASE", {}).get("prefixes", [])
        prefix = prefixes[0] if prefixes else "COINBASE-"
        tx_data = f"{prefix}{block_height}-{timestamp}-{self.miner_address}-{self.reward}"
        tx_id = hashlib.sha3_384(tx_data.encode()).hexdigest()
        print(f"[CoinbaseTx._generate_tx_id] Generated tx_id: {tx_id}")
        return tx_id

    def calculate_hash(self) -> str:
        """
        Calculate the SHA3-384 hash of the transaction using single hashing.
        """
        output = self.outputs[0]
        tx_data = f"{self.tx_id}{self.timestamp}{output['address']}{Decimal(output['amount'])}"
        calculated_hash = hashlib.sha3_384(tx_data.encode()).hexdigest()
        print(f"[CoinbaseTx.calculate_hash] Calculated hash: {calculated_hash}")
        return calculated_hash

    def to_dict(self) -> Dict:
        """
        Serialize the CoinbaseTx to a dictionary.
        """
        return {
            "tx_id": self.tx_id,
            "block_height": self.block_height,
            "miner_address": self.miner_address,
            "reward": str(self.reward),
            "inputs": self.inputs,
            "outputs": self.outputs,
            "timestamp": self.timestamp,
            "type": self.type,
            "tx_type": self.type,  # For serializer compatibility
            "fee": str(self.fee),
            "hash": self.hash,
            "size": self.size
        }

    @classmethod
    def from_dict(cls, data: Dict):
        """
        Deserialize a CoinbaseTx from a dictionary.
        """
        obj = cls(
            block_height=data["block_height"],
            miner_address=data["miner_address"],
            reward=Decimal(data["reward"])
        )
        obj.tx_id = data.get("tx_id", obj.tx_id)
        obj.timestamp = data.get("timestamp", obj.timestamp)
        obj.inputs = data.get("inputs", [])
        obj.outputs = data.get("outputs", obj.outputs)
        obj.type = data.get("type", "COINBASE")
        obj.hash = data.get("hash", obj.calculate_hash())
        obj.size = data.get("size", len(str(data)))
        print(f"[CoinbaseTx.from_dict] Deserialized CoinbaseTx with tx_id: {obj.tx_id}")
        return obj

    @property
    def is_coinbase(self) -> bool:
        """
        Identify this as a coinbase transaction.
        """
        return True
