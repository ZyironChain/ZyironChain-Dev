import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))





import time
import hashlib
from decimal import Decimal
from typing import Dict
from Zyiron_Chain.blockchain.constants import Constants

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import time
import hashlib
from decimal import Decimal
from typing import Dict
from Zyiron_Chain.blockchain.constants import Constants

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import time
import hashlib
from decimal import Decimal
from typing import Dict
from Zyiron_Chain.blockchain.constants import Constants

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import time
import hashlib
from decimal import Decimal
from typing import Dict
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.blockchain.utils.hashing import Hashing


import hashlib
from decimal import Decimal
import time
from typing import Dict


import time
from decimal import Decimal
from typing import Dict
import hashlib
from Zyiron_Chain.blockchain.constants import Constants


import hashlib
import time
from decimal import Decimal
from typing import Dict
from Zyiron_Chain.blockchain.constants import Constants

class CoinbaseTx:
    """Represents a block reward (coinbase) transaction"""

    def __init__(self, block_height: int, miner_address: str, reward: Decimal = None):
        """
        Initializes a Coinbase transaction.

        :param block_height: The height of the block.
        :param miner_address: The recipient miner's address.
        :param reward: The reward amount (defaults to a dynamically calculated reward based on halving).
        """
        self.block_height = block_height
        self.miner_address = miner_address
        self.reward = reward if reward is not None else self._calculate_reward(block_height)
        self.timestamp = time.time()
        self.tx_id = self._generate_tx_id(block_height, self.timestamp)
        self.inputs = []  # Coinbase transactions have no inputs
        self.outputs = [{
            "address": miner_address,
            "amount": float(self.reward),
            "script_pub_key": miner_address
        }]
        self.type = "COINBASE"
        self.fee = Decimal("0")
        self.hash = self.calculate_hash()

        # Compute estimated transaction size
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

    def _calculate_reward(self, block_height: int) -> Decimal:
        """Dynamically calculate the block reward based on halving intervals."""
        halvings = block_height // Constants.BLOCKCHAIN_HALVING_BLOCK_HEIGHT
        reward = Decimal(Constants.INITIAL_COINBASE_REWARD) / (2 ** halvings)
        return max(reward, Decimal(str(Constants.MIN_TRANSACTION_FEE)))

    def _generate_tx_id(self, block_height: int, timestamp: float) -> str:
        """Generate a unique transaction ID using SHA3-384 single hashing."""
        prefixes = Constants.TRANSACTION_MEMPOOL_MAP.get("COINBASE", {}).get("prefixes", [])
        prefix = prefixes[0] if prefixes else "COINBASE-"
        tx_data = f"{prefix}{block_height}-{timestamp}-{self.miner_address}-{self.reward}"
        return hashlib.sha3_384(tx_data.encode()).hexdigest()  # ✅ Single hash

    def calculate_hash(self) -> str:
        """Calculate the SHA3-384 hash of the transaction (single hash)."""
        output = self.outputs[0]
        tx_data = f"{self.tx_id}{self.timestamp}{output['address']}{Decimal(output['amount'])}"
        return hashlib.sha3_384(tx_data.encode()).hexdigest()  # ✅ Single hash

    def to_dict(self) -> Dict:
        """Serialize the CoinbaseTx to a dictionary."""
        return {
            "tx_id": self.tx_id,
            "block_height": self.block_height,
            "miner_address": self.miner_address,
            "reward": str(self.reward),
            "inputs": self.inputs,
            "outputs": self.outputs,
            "timestamp": self.timestamp,
            "type": self.type,  # Original field
            "tx_type": self.type,  # New field required by the serializer
            "fee": str(self.fee),  # Ensure fee is present
            "hash": self.hash,
            "size": self.size
        }

    @classmethod
    def from_dict(cls, data: Dict):
        """Deserialize a CoinbaseTx from a dictionary."""
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
        return obj

    @property
    def is_coinbase(self) -> bool:
        """Return True to identify this as a coinbase transaction."""
        return True
