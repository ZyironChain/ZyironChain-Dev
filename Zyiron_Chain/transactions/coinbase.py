import json
import time
import hashlib
from decimal import Decimal
from typing import Dict, Optional
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

import hashlib
import struct
import time
from decimal import Decimal
from typing import Dict

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.txout import TransactionOut




import time
import hashlib
import json
from decimal import Decimal
from typing import Dict, Optional

class CoinbaseTx:
    """
    Represents a block reward (coinbase) transaction.
    Uses single SHA3-384 hashing, handles amounts in smallest units (ZYC * Constants.COIN),
    and ensures transactions are correctly serialized in JSON format.
    """

    def __init__(self, block_height: int, miner_address: str, reward: Decimal, tx_id: Optional[str] = None):
        print(f"[CoinbaseTx.__init__] Initializing Coinbase Transaction for Block {block_height}...")

        self.block_height = block_height
        self.miner_address = miner_address
        self.reward = reward * Constants.COIN  # Store in smallest unit
        self.timestamp = int(time.time())

        self.tx_id = tx_id if tx_id else self._generate_tx_id()
        print(f"[CoinbaseTx.__init__] Transaction ID set: {self.tx_id}")

        self.inputs = []
        self.outputs = [{
            "script_pub_key": miner_address,
            "amount": str(self.reward / Constants.COIN),
            "locked": False
        }]

        self.type = "COINBASE"
        self.fee = Decimal("0")
        self.metadata = {}

        self.size = None
        self.size = self._estimate_size()

        print(f"[CoinbaseTx.__init__] Transaction size estimated: {self.size} bytes")
        print(f"[CoinbaseTx.__init__] ✅ SUCCESS: CoinbaseTx initialized for miner: {miner_address}")

    def _generate_tx_id(self) -> str:
        """
        Generate a unique transaction ID using single SHA3-384 hashing.
        """
        prefixes = Constants.TRANSACTION_MEMPOOL_MAP.get("COINBASE", {}).get("prefixes", [])
        prefix = prefixes[0] if prefixes else "COINBASE-"

        tx_data = f"{prefix}{self.block_height}-{self.timestamp}-{self.miner_address}-{self.reward}"
        tx_id = hashlib.sha3_384(tx_data.encode()).hexdigest()

        print(f"[CoinbaseTx._generate_tx_id] INFO: Generated tx_id: {tx_id}")
        return tx_id

    def _estimate_size(self) -> int:
        """
        Estimate transaction size based on JSON serialization.
        """
        try:
            estimated_size = len(json.dumps(self.to_dict()).encode("utf-8"))
            return estimated_size
        except Exception as e:
            print(f"[CoinbaseTx._estimate_size] ❌ ERROR: Failed to estimate size: {e}")
            return 0

    def to_dict(self) -> Dict:
        """
        Serialize the CoinbaseTx to a dictionary.
        """
        print(f"[CoinbaseTx.to_dict] INFO: Serializing CoinbaseTx (tx_id: {self.tx_id.hex() if isinstance(self.tx_id, bytes) else self.tx_id})")
        return {
            "tx_id": self.tx_id.hex() if isinstance(self.tx_id, bytes) else self.tx_id,
            "block_height": self.block_height,
            "miner_address": self.miner_address,
            "reward": str(self.reward / Constants.COIN),  # human-readable
            "inputs": self.inputs,
            "outputs": self.outputs,
            "timestamp": self.timestamp,
            "type": self.type,
            "fee": str(self.fee),
            "size": self.size,
            "metadata": self.metadata
        }


    @classmethod
    def from_dict(cls, data: Dict) -> Optional["CoinbaseTx"]:
        """
        Deserialize a CoinbaseTx from a dictionary.
        """
        try:
            print(f"[CoinbaseTx.from_dict] INFO: Deserializing CoinbaseTx from dictionary...")

            required_fields = {"block_height", "miner_address", "reward"}
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                raise ValueError(f"[CoinbaseTx.from_dict] ❌ ERROR: Missing required fields: {missing_fields}")

            reward_decimal = Decimal(data["reward"])  # reward is already human-readable

            # Convert tx_id back to bytes if it's a hex string
            tx_id = data.get("tx_id")
            if tx_id and isinstance(tx_id, str):
                try:
                    tx_id = bytes.fromhex(tx_id)
                except Exception:
                    print("[CoinbaseTx.from_dict] WARN: Failed to convert tx_id from hex, keeping as str.")
                    pass

            # Initialize the CoinbaseTx object
            obj = cls(
                block_height=data["block_height"],
                miner_address=data["miner_address"],
                reward=reward_decimal,
                tx_id=tx_id
            )

            # Optional fields
            obj.timestamp = data.get("timestamp", int(time.time()))
            obj.inputs = data.get("inputs", [])
            
            # Normalize outputs
            raw_outputs = data.get("outputs", [])
            obj.outputs = []
            for output in raw_outputs:
                amount = str(output.get("amount", "0"))
                script_pub_key = output.get("script_pub_key", "")
                obj.outputs.append({
                    "amount": amount,
                    "script_pub_key": script_pub_key
                })

            obj.type = data.get("type", "COINBASE")
            obj.size = data.get("size", obj._estimate_size())
            obj.fee = Decimal(data.get("fee", "0"))
            obj.metadata = data.get("metadata", {})

            print(f"[CoinbaseTx.from_dict] ✅ SUCCESS: Deserialized CoinbaseTx with tx_id: {obj.tx_id.hex() if isinstance(obj.tx_id, bytes) else obj.tx_id}")
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
