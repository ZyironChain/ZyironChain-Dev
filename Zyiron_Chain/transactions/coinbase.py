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

import hashlib
import struct
import time
from decimal import Decimal
from typing import Dict
from Zyiron_Chain.transactions.txout import TransactionOut

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

        # ✅ FIX: Ensure correct output format
        self.outputs = [{
            "script_pub_key": miner_address,  # ✅ FIXED: Changed from 'address' to 'script_pub_key'
            "amount": float(self.reward),
            "locked": False  # Added default locked state
        }]

        # Define transaction type and fee
        self.type = "COINBASE"
        self.fee = Decimal("0")

        # ✅ FIX: Ensure metadata is always initialized
        self.metadata = {}

        # ✅ FIX: Improved transaction size estimation
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
        prefixes = Constants.TRANSACTION_MEMPOOL_MAP.get("COINBASE", {}).get("prefixes", [])
        prefix = prefixes[0] if prefixes else "COINBASE-"

        tx_data = f"{prefix}{self.block_height}-{self.timestamp}-{self.miner_address}-{self.reward}"
        tx_id = hashlib.sha3_384(tx_data.encode()).hexdigest()

        print(f"[CoinbaseTx._generate_tx_id] Generated tx_id: {tx_id}")
        return tx_id

    def _estimate_size(self) -> int:
        """
        Improved size estimation using struct.pack().
        """
        try:
            header_size = struct.calcsize(">I 48s Q")  # block_height, tx_id, timestamp
            outputs_size = sum(struct.calcsize(">d 128s") for _ in self.outputs)  # Each output: amount (double), script_pub_key (128 bytes)
            estimated_size = header_size + outputs_size
            return estimated_size
        except Exception as e:
            print(f"[CoinbaseTx._estimate_size] ERROR: Failed to estimate size: {e}")
            return 0

    def to_dict(self) -> Dict:
        """
        Serialize the CoinbaseTx to a dictionary.
        """
        print(f"[CoinbaseTx.to_dict] Serializing CoinbaseTx (tx_id: {self.tx_id})")

        return {
            "tx_id": self.tx_id,
            "block_height": self.block_height,
            "miner_address": self.miner_address,
            "reward": str(self.reward),
            "inputs": self.inputs,
            "outputs": [
                out.to_dict() if isinstance(out, TransactionOut) else {
                    "script_pub_key": out["script_pub_key"],  # ✅ FIXED: Ensure valid output structure
                    "amount": str(out["amount"]),  # ✅ Ensure `amount` remains a string for JSON compatibility
                    "locked": out.get("locked", False)
                } for out in self.outputs
            ],
            "timestamp": self.timestamp,
            "type": self.type,
            "fee": str(self.fee),  # ✅ Ensure `fee` is stored as a string
            "size": self.size,
            "metadata": self.metadata if isinstance(self.metadata, dict) else {}  # ✅ Ensure metadata is always a valid dictionary
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CoinbaseTx":
        """
        Deserialize a CoinbaseTx from a dictionary.
        """
        try:
            print(f"[CoinbaseTx.from_dict] INFO: Deserializing CoinbaseTx from dictionary...")

            # ✅ **Ensure Required Fields Exist**
            required_fields = {"block_height", "miner_address", "reward"}
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                raise ValueError(f"[CoinbaseTx.from_dict] ❌ ERROR: Missing required fields: {missing_fields}")

            # ✅ **Parse Basic Fields**
            obj = cls(
                block_height=data["block_height"],
                miner_address=data["miner_address"],
                reward=Decimal(str(data["reward"]))  # ✅ Ensure reward is stored as Decimal
            )

            obj.tx_id = data.get("tx_id", obj._generate_tx_id())  # ✅ Ensure tx_id is generated if missing
            obj.timestamp = data.get("timestamp", int(time.time()))  # ✅ Default to current time if missing
            obj.inputs = data.get("inputs", [])

            # ✅ **Ensure Outputs Are Properly Deserialized**
            obj.outputs = [
                TransactionOut.from_dict(out) if isinstance(out, dict) else out
                for out in data.get("outputs", [])
            ]

            obj.type = data.get("type", "COINBASE")
            obj.size = data.get("size", obj._estimate_size())
            obj.fee = Decimal(str(data.get("fee", "0")))  # ✅ Ensure fee is stored as Decimal
            obj.metadata = data.get("metadata", {}) if isinstance(data.get("metadata", {}), dict) else {}

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