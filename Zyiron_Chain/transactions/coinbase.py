import time
import hashlib
from decimal import Decimal
from typing import Dict
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.deserializer import Deserializer
import time
import hashlib
from decimal import Decimal
from typing import Dict
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.deserializer import Deserializer

class CoinbaseTx:
    """
    Represents a block reward (coinbase) transaction.
    Uses single SHA3-384 hashing and all amounts are handled as bytes (via encoding when needed).
    Detailed print statements are used instead of logging.
    """

    def __init__(self, block_height: int, miner_address: str, reward: Decimal = None):
        print(f"[CoinbaseTx.__init__]  Initializing Coinbase Transaction for Block {block_height}...")

        # Assign core attributes
        self.block_height = block_height
        self.miner_address = miner_address

        # Dynamically calculate block reward based on halving intervals
        self.reward = reward if reward is not None else self._calculate_reward(block_height)
        self.timestamp = int(time.time())

        # Generate unique transaction ID (SHA3-384 hash)
        self.tx_id = self._generate_tx_id()
        print(f"[CoinbaseTx.__init__]  Transaction ID (tx_id) generated: {self.tx_id}")

        # Coinbase transactions have **no inputs**
        self.inputs = []
        
        # Define outputs (miner reward)
        self.outputs = [{
            "address": miner_address,
            "amount": float(self.reward),
            "script_pub_key": miner_address
        }]
        
        # Define transaction type and fee
        self.type = "COINBASE"
        self.fee = Decimal("0")

        # Estimate transaction size
        self.size = self._estimate_size()
        print(f"[CoinbaseTx.__init__]  Transaction size estimated: {self.size} bytes")

        print(f"[CoinbaseTx.__init__]  CoinbaseTx successfully initialized for miner: {miner_address}")

    def _calculate_reward(self, block_height: int) -> Decimal:
        """
        Dynamically calculate the block reward based on halving intervals.
        Uses constants from Constants.
        """
        halvings = block_height // Constants.BLOCKCHAIN_HALVING_BLOCK_HEIGHT
        reward = Decimal(Constants.INITIAL_COINBASE_REWARD) / (2 ** halvings)
        calculated_reward = max(reward, Decimal(str(Constants.MIN_TRANSACTION_FEE)))
        print(f"[CoinbaseTx._calculate_reward]  Reward for Block {block_height}: {calculated_reward} ZYC")
        return calculated_reward

    def _generate_tx_id(self) -> str:
        """
        Generate a unique transaction ID using single SHA3-384 hashing.
        Uses a prefix from Constants if available.
        """
        prefixes = Constants.TRANSACTION_MEMPOOL_MAP.get("COINBASE", {}).get("prefixes", [])
        prefix = prefixes[0] if prefixes else "COINBASE-"

        # Construct the data string
        tx_data = f"{prefix}{self.block_height}-{self.timestamp}-{self.miner_address}-{self.reward}"
        tx_id = hashlib.sha3_384(tx_data.encode()).hexdigest()

        print(f"[CoinbaseTx._generate_tx_id]  Generated tx_id: {tx_id}")
        return tx_id

    def _estimate_size(self) -> int:
        """
        Estimate the transaction size in bytes.
        """
        temp_data = {
            "tx_id": self.tx_id,
            "block_height": self.block_height,
            "miner_address": self.miner_address,
            "reward": str(self.reward),
            "inputs": self.inputs,
            "outputs": self.outputs,
            "timestamp": self.timestamp,
            "type": self.type,
        }
        return len(str(temp_data))

    def to_dict(self) -> Dict:
        """
        Serialize the CoinbaseTx to a dictionary.
        """
        print(f"[CoinbaseTx.to_dict]  Serializing CoinbaseTx (tx_id: {self.tx_id})")
        return {
            "tx_id": self.tx_id,
            "block_height": self.block_height,
            "miner_address": self.miner_address,
            "reward": str(self.reward),
            "inputs": self.inputs,
            "outputs": self.outputs,
            "timestamp": self.timestamp,
            "type": self.type,
            "fee": str(self.fee),
            "size": self.size,
            "metadata": self.metadata  # ✅ Include metadata
        }

    @classmethod
    def from_dict(cls, data: Dict):
        """
        Deserialize a CoinbaseTx from a dictionary.
        - Ignores unexpected fields.
        - Restores metadata if available.
        - Ensures required fields are present.
        """
        try:
            print(f"[CoinbaseTx.from_dict]  INFO: Deserializing CoinbaseTx from dictionary...")

            # ✅ **Required Fields Validation**
            required_fields = {"tx_id", "block_height", "miner_address", "reward"}
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                raise ValueError(f"[CoinbaseTx.from_dict] ❌ ERROR: Missing required fields: {missing_fields}")

            # ✅ **Initialize CoinbaseTx Object**
            obj = cls(
                block_height=data["block_height"],
                miner_address=data["miner_address"],
                reward=Decimal(data["reward"]),
                metadata=data.get("metadata", {})  # ✅ Restore metadata if present
            )

            # ✅ **Ensure TX ID is Generated if Missing**
            obj.tx_id = data.get("tx_id", obj._generate_tx_id())

            # ✅ **Restore Optional Fields**
            obj.timestamp = data.get("timestamp", int(time.time()))  # Use current timestamp if missing
            obj.inputs = data.get("inputs", [])  # Default empty list if missing
            obj.outputs = data.get("outputs", obj.outputs)  # Use class default if missing
            obj.type = data.get("type", "COINBASE")  # Default transaction type
            obj.size = data.get("size", obj._estimate_size())  # Auto-calculate size if missing

            # ✅ **Log Success**
            print(f"[CoinbaseTx.from_dict] ✅ SUCCESS: Deserialized CoinbaseTx with tx_id: {obj.tx_id}")
            return obj

        except Exception as e:
            print(f"[CoinbaseTx.from_dict] ❌ ERROR: Failed to deserialize CoinbaseTx: {e}")
            return None


    @property
    def is_coinbase(self) -> bool:
        """
        Identify this as a coinbase transaction.
        """
        return True