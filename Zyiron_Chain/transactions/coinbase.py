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
import time
import json
import hashlib
from decimal import Decimal
from typing import Dict, Optional

from Zyiron_Chain.blockchain.constants import Constants


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

        # ✅ Initialize .size before using it in to_dict()
        self.size = 0
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
        print(f"[CoinbaseTx.to_dict] INFO: Serializing CoinbaseTx (tx_id: {self.tx_id})")
        return {
            "tx_id": self.tx_id,
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

            reward_decimal = Decimal(data["reward"])

            tx_id = data.get("tx_id")
            if isinstance(tx_id, str) and len(tx_id) == 96:
                try:
                    bytes.fromhex(tx_id)  # validate hex string
                except Exception:
                    print("[CoinbaseTx.from_dict] WARN: tx_id is not a valid hex. Using as string.")

            obj = cls(
                block_height=data["block_height"],
                miner_address=data["miner_address"],
                reward=reward_decimal,
                tx_id=tx_id
            )

            obj.timestamp = data.get("timestamp", int(time.time()))
            obj.inputs = data.get("inputs", [])

            obj.outputs = []
            for output in data.get("outputs", []):
                obj.outputs.append({
                    "amount": str(output.get("amount", "0")),
                    "script_pub_key": output.get("script_pub_key", ""),
                    "locked": output.get("locked", False)
                })

            obj.type = data.get("type", "COINBASE")
            obj.fee = Decimal(data.get("fee", "0"))
            obj.metadata = data.get("metadata", {})

            # ✅ FIXED: Always estimate size AFTER outputs and metadata are set
            obj.size = obj._estimate_size()

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
