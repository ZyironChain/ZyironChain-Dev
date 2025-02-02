import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

import json
import hashlib
import time
from typing import List, Dict
from Zyiron_Chain.transactions.txout import TransactionOut, UTXOManager
from Zyiron_Chain.transactions.transactiontype import TransactionType
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
    def __init__(self, tx_id: str, inputs: List[Dict], outputs: List[Dict]):
        self.tx_id = tx_id
        self.inputs = inputs
        self.outputs = outputs
        self.timestamp = time.time()
        self.type = PaymentTypeManager().get_transaction_type(tx_id)
        self.fee = self._calculate_fee()
        self.hash = self.calculate_hash()

    def _calculate_fee(self) -> Decimal:
        """Calculate transaction fee as input_total - output_total"""
        input_total = sum(Decimal(inp["amount"]) for inp in self.inputs)
        output_total = sum(Decimal(out["amount"]) for out in self.outputs)
        return input_total - output_total

    def calculate_hash(self) -> str:
        """Calculate SHA3-384 hash of the transaction"""
        input_data = "".join(f"{i['tx_id']}{i['amount']}" for i in self.inputs)
        output_data = "".join(f"{o['address']}{o['amount']}" for o in self.outputs)
        return sha3_384_hash(f"{input_data}{output_data}{self.timestamp}")

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

class TransactionFactory:
    """Factory for creating transactions"""
    @staticmethod
    def create_transaction(tx_type: TransactionType, inputs: List[Dict], outputs: List[Dict]) -> Transaction:
        """Create a new transaction of the specified type"""
        prefix = PaymentTypeManager().TYPE_CONFIG[tx_type]["prefixes"][0] if tx_type != TransactionType.STANDARD else ""
        base_data = f"{prefix}{','.join(str(i['amount']) for i in inputs)}"
        tx_id = sha3_384_hash(base_data + str(time.time()))[:64]
        return Transaction(tx_id, inputs, outputs)
