import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

import json
import hashlib
import time
from typing import List, Dict
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager
from Zyiron_Chain.blockchain.helper import get_poc

PoC = get_poc()  # ✅ Dynamically load PoC before using it


def get_poc_instance():
    """Dynamically import PoC only when needed to prevent circular imports."""
    return get_poc()

def _ensure_inputs(self, inputs):
    """Ensure all inputs have required fields and convert to dictionaries."""
    from Zyiron_Chain.transactions.Blockchain_transaction import TransactionIn  # Local import to avoid circular dependency

    validated_inputs = []
    for inp in inputs:
        if not isinstance(inp, TransactionIn):
            raise TypeError("[ERROR] Expected TransactionIn object.")
        validated_inputs.append(inp.to_dict())
    return validated_inputs

 # Use PoC for routing transactions
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager  # Ensure KeyManager is correctly imported

from decimal import Decimal

import hashlib
import time
from decimal import Decimal
from typing import List, Dict
from Zyiron_Chain.transactions.transactiontype import TransactionType, PaymentTypeManager
def sha3_384_hash(data: str) -> str:
    """Universal SHA3-384 hashing function"""
    return hashlib.sha3_384(data.encode()).hexdigest()

def sha3_384_hash(data: str) -> str:
    """Universal SHA3-384 hashing function"""
    return hashlib.sha3_384(data.encode()).hexdigest()

class CoinbaseTx:
    """Represents a block reward transaction"""
    def __init__(self, block_height: int, miner_address: str, reward: Decimal):
        self.tx_id = f"COINBASE-{block_height}-{sha3_384_hash(str(time.time()))[:24]}"
        self.inputs = []  # Coinbase transactions have no inputs
        self.outputs = [{
            "address": miner_address,
            "amount": float(reward)
        }]
        self.timestamp = time.time()
        self.type = TransactionType.COINBASE
        self.hash = self.calculate_hash()

    def calculate_hash(self) -> str:
        """Calculate SHA3-384 hash of the transaction"""
        data = f"{self.tx_id}{self.timestamp}{self.outputs[0]['address']}"
        return sha3_384_hash(data)

    def to_dict(self) -> Dict:
        """Serialize CoinbaseTx to a dictionary"""
        return {
            "tx_id": self.tx_id,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "timestamp": self.timestamp,
            "type": self.type.name,
            "hash": self.hash
        }
class Transaction:
    """Represents a standard blockchain transaction"""

    def __init__(self, inputs: List["TransactionIn"], outputs: List["TransactionOut"], tx_id: str = None, poc: "PoC" = None, utxo_manager=None):

            if not all(isinstance(inp, TransactionIn) for inp in inputs):
                raise TypeError("[ERROR] All inputs must be instances of TransactionIn.")
            if not all(isinstance(out, TransactionOut) for out in outputs):
                raise TypeError("[ERROR] All outputs must be instances of TransactionOut.")

            self.utxo_manager = utxo_manager if utxo_manager else self._get_default_utxo_manager()  # ✅ Ensure UTXO manager exists

            self.inputs = [inp if isinstance(inp, TransactionIn) else TransactionIn.from_dict(inp) for inp in inputs]
            self.outputs = [out if isinstance(out, TransactionOut) else TransactionOut.from_dict(out) for out in outputs]

            self.timestamp = time.time()
            self.type = PaymentTypeManager().get_transaction_type(tx_id)
            self.tx_id = tx_id if tx_id else self._generate_tx_id()
            self.hash = self.calculate_hash()
            self.poc = poc  # ✅ PoC is now optional
            self.size_bytes = self._calculate_size()
            self.fee = self._calculate_fee()  # ✅ Ensure fee is calculated after all attributes are set

    def _get_default_utxo_manager(self):
        """Retrieve the default UTXO manager instance if not provided."""
        from Zyiron_Chain.transactions.utxo_manager import UTXOManager
        from Zyiron_Chain.database.poc import PoC  # Ensure PoC is passed to UTXOManager
        return UTXOManager(PoC())  # ✅ Provide a valid default instance

    @classmethod
    def from_dict(cls, data: Dict, poc: PoC = None):
        """Create a Transaction instance from a dictionary."""
        return cls(
            tx_id=data.get("tx_id", ""),
            inputs=[TransactionIn.from_dict(inp) for inp in data["inputs"]],
            outputs=[TransactionOut.from_dict(out) for out in data["outputs"]],
            poc=poc
        )


    def _ensure_inputs(self, inputs):
        """Ensure all inputs have required fields and convert to dictionaries."""
        from Zyiron_Chain.transactions.Blockchain_transaction import TransactionIn  # Local import to avoid circular dependency

        validated_inputs = []
        for inp in inputs:
            if not isinstance(inp, TransactionIn):
                raise TypeError("[ERROR] Expected TransactionIn object.")
            validated_inputs.append(inp.to_dict())
        return validated_inputs
    
    def _calculate_size(self) -> int:
        """Estimate transaction size based on inputs, outputs, and metadata."""
        input_size = sum(len(str(inp.to_dict() if isinstance(inp, TransactionIn) else inp)) for inp in self.inputs)
        output_size = sum(len(str(out.to_dict() if isinstance(out, TransactionOut) else out)) for out in self.outputs)

        metadata_size = len(self.tx_id) + len(str(self.timestamp))
        return input_size + output_size + metadata_size



    def _ensure_outputs(self, outputs):
        """Ensure all outputs have required fields and convert to dictionaries."""
        validated_outputs = []
        for out in outputs:
            if not isinstance(out, TransactionOut):
                raise TypeError("[ERROR] Expected TransactionOut object.")
            validated_outputs.append(out.to_dict())
        return validated_outputs

    def _calculate_fee(self) -> Decimal:
        """Calculate transaction fee as input_total - output_total."""
        input_total = sum(
            Decimal(utxo["amount"]) if (utxo := self.utxo_manager.get_utxo(inp.tx_out_id)) else Decimal(0)
            for inp in self.inputs
        )
        
        output_total = sum(
            Decimal(out.amount) if isinstance(out, TransactionOut) else Decimal(out.get("amount", 0))
            for out in self.outputs
        )

        return input_total - output_total





    def _get_script_pub_key(self, recipient_address):
        """Fetch the scriptPubKey (hashed public key) for a given recipient using KeyManager"""
        key_manager = KeyManager()
        try:
            return key_manager.get_default_public_key("mainnet", "miner")  # Defaulting to miner for now
        except ValueError:
            return recipient_address  # If no key found, fallback to recipient address

    def calculate_hash(self) -> str:
        """Calculate SHA3-384 hash of the transaction."""
        input_data = "".join(f"{i.tx_out_id}" if isinstance(i, TransactionIn) else f"{i['tx_out_id']}" for i in self.inputs)

        output_data = "".join(
            f"{o.script_pub_key}{o.amount}" if isinstance(o, TransactionOut) else f"{o.get('script_pub_key', '')}{o.get('amount', 0)}"
            for o in self.outputs
        )


        return hashlib.sha3_384(f"{input_data}{output_data}{self.timestamp}".encode()).hexdigest()
    
    def to_dict(self) -> Dict:
        """Serialize Transaction to a dictionary"""
        return {
            "tx_id": self.tx_id,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "timestamp": self.timestamp,
            "type": self.type.name,
            "fee": float(self.fee),
            "hash": self.hash
        }

    def store_transaction(self):
        """
        Store the transaction using PoC, which will route it to the appropriate storage layer.
        """
        try:
            self.poc.store_transaction(self)
            print(f"[INFO] Transaction {self.tx_id} stored successfully via PoC.")
        except Exception as e:
            print(f"[ERROR] Failed to store transaction {self.tx_id}: {e}")

    def store_utxo(self):
        """
        Store the transaction outputs as UTXOs through PoC.
        PoC decides whether to store it in SQLite, UnQLite, or LMDB.
        """
        try:
            for idx, output in enumerate(self.outputs):
                utxo_id = f"{self.tx_id}-{idx}"
                self.poc.store_utxo(utxo_id, {
                    "tx_out_id": self.tx_id,
                    "amount": output["amount"],
                    "script_pub_key": output["script_pub_key"],
                    "locked": False,  # Newly created UTXOs are unlocked
                    "block_index": 0  # To be updated when included in a block
                })
            print(f"[INFO] UTXOs stored successfully via PoC for transaction {self.tx_id}")
        except Exception as e:
            print(f"[ERROR] Failed to store UTXOs for transaction {self.tx_id}: {e}")

class TransactionFactory:
    """Factory for creating transactions"""
    @staticmethod
    def create_transaction(tx_type: TransactionType, inputs: List[Dict], outputs: List[Dict], poc: PoC) -> Transaction:
        """Create a new transaction of the specified type"""
        prefix = PaymentTypeManager().TYPE_CONFIG[tx_type]["prefixes"][0] if tx_type != TransactionType.STANDARD else ""
        base_data = f"{prefix}{','.join(str(i['amount']) for i in inputs)}"
        tx_id = hashlib.sha3_384(f"{base_data}{str(time.time())}".encode()).hexdigest()[:64]
        return Transaction(inputs=inputs, outputs=outputs, tx_id=tx_id, poc=poc)






class TransactionIn:
    """
    Represents a transaction input, referencing a previous UTXO.
    """
    def __init__(self, tx_out_id: str, script_sig: str):
        self.tx_out_id = tx_out_id
        self.script_sig = script_sig

    def to_dict(self):
        return {
            "tx_out_id": self.tx_out_id,
            "script_sig": self.script_sig
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            tx_out_id=data["tx_out_id"],
            script_sig=data["script_sig"]
        )

