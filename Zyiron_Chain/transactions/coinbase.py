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
        print(f"[CoinbaseTx.__init__] Initializing Coinbase Transaction for Block {block_height}...")

        # Assign core attributes
        self.block_height = block_height
        self.miner_address = miner_address

        # Dynamically calculate block reward based on halving intervals
        self.reward = reward if reward is not None else self._calculate_reward(block_height)
        self.timestamp = int(time.time())

        # Generate unique transaction ID (SHA3-384 hash)
        self.tx_id = self._generate_tx_id()
        print(f"[CoinbaseTx.__init__] Transaction ID (tx_id) generated: {self.tx_id}")

        # Coinbase transactions have **no inputs**
        self.inputs = []

        # Define outputs (miner reward)
        # Notice that each output is just a dict, so this is JSON-serializable.
        self.outputs = [{
            "address": miner_address,
            "amount": float(self.reward),
            "script_pub_key": miner_address
        }]

        # Define transaction type and fee
        self.type = "COINBASE"
        self.fee = Decimal("0")

        # Initialize an optional metadata field (to avoid KeyErrors if not set externally).
        self.metadata = {}

        # Estimate transaction size
        self.size = self._estimate_size()
        print(f"[CoinbaseTx.__init__] Transaction size estimated: {self.size} bytes")

        print(f"[CoinbaseTx.__init__] CoinbaseTx successfully initialized for miner: {miner_address}")

    def _calculate_reward(self, block_height: int) -> Decimal:
        """
        Dynamically calculate the block reward based on halving intervals.
        Uses constants from Constants.
        """
        halvings = block_height // Constants.BLOCKCHAIN_HALVING_BLOCK_HEIGHT
        reward = Decimal(Constants.INITIAL_COINBASE_REWARD) / (2 ** halvings)
        calculated_reward = max(reward, Decimal(str(Constants.MIN_TRANSACTION_FEE)))
        print(f"[CoinbaseTx._calculate_reward] Reward for Block {block_height}: {calculated_reward} ZYC")
        return calculated_reward

    def _generate_tx_id(self) -> str:
        """
        Generate a unique transaction ID using single SHA3-384 hashing.
        Uses a prefix from Constants if available.
        """
        # Attempt to get a prefix from TRANSACTION_MEMPOOL_MAP for COINBASE
        prefixes = Constants.TRANSACTION_MEMPOOL_MAP.get("COINBASE", {}).get("prefixes", [])
        prefix = prefixes[0] if prefixes else "COINBASE-"

        # Construct the data string
        tx_data = f"{prefix}{self.block_height}-{self.timestamp}-{self.miner_address}-{self.reward}"
        tx_id = hashlib.sha3_384(tx_data.encode()).hexdigest()

        print(f"[CoinbaseTx._generate_tx_id] Generated tx_id: {tx_id}")
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
        Includes all fields, including metadata, so everything is JSON-serializable.
        """
        print(f"[CoinbaseTx.to_dict] Serializing CoinbaseTx (tx_id: {self.tx_id})")
        return {
            "tx_id": self.tx_id,
            "block_height": self.block_height,
            "miner_address": self.miner_address,
            "reward": str(self.reward),      # Convert Decimal to string for serialization
            "inputs": self.inputs,           # Already a list of dicts
            "outputs": self.outputs,         # List of dicts, so it's JSON-serializable
            "timestamp": self.timestamp,
            "type": self.type,
            "fee": str(self.fee),            # Convert Decimal to string
            "size": self.size,
            "metadata": self.metadata        # Ensure it's a dict to be JSON-serializable
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
            print(f"[CoinbaseTx.from_dict] INFO: Deserializing CoinbaseTx from dictionary...")

            # Expected keys in the dictionary
            expected_keys = {
                "block_height", "miner_address", "reward", "tx_id",
                "timestamp", "inputs", "outputs", "type", "size", "fee"
            }

            # Filter out only the expected keys
            filtered_data = {k: data[k] for k in expected_keys if k in data}

            # Required fields for a valid CoinbaseTx
            required_fields = {"block_height", "miner_address", "reward"}
            missing_fields = [field for field in required_fields if field not in filtered_data]
            if missing_fields:
                raise ValueError(f"[CoinbaseTx.from_dict] ❌ ERROR: Missing required fields: {missing_fields}")

            # Create the CoinbaseTx object
            obj = cls(
                block_height=filtered_data["block_height"],
                miner_address=filtered_data["miner_address"],
                reward=Decimal(filtered_data["reward"])  # Convert string to Decimal
            )

            # Restore optional fields
            obj.tx_id = filtered_data.get("tx_id", obj._generate_tx_id())  # Generate TX ID if missing
            obj.timestamp = filtered_data.get("timestamp", int(time.time()))  # Use current time if missing
            obj.inputs = filtered_data.get("inputs", [])    # Default to empty list
            obj.outputs = filtered_data.get("outputs", obj.outputs)
            obj.type = filtered_data.get("type", "COINBASE")
            obj.size = filtered_data.get("size", obj._estimate_size())
            obj.fee = Decimal(filtered_data.get("fee", "0"))

            # Restore metadata safely
            # If the 'metadata' field is present in the original data, use it if it's a dict, else default to {}
            potential_metadata = data.get("metadata", {})
            obj.metadata = potential_metadata if isinstance(potential_metadata, dict) else {}

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