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
from Zyiron_Chain.database.poc import PoC  # Use PoC for routing transactions
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

    def __init__(self, tx_id: str, inputs: List[Dict], outputs: List[Dict], poc: PoC):
        """
        Initialize a transaction.
        :param tx_id: Unique transaction identifier.
        :param inputs: List of transaction inputs (previous UTXOs being spent).
        :param outputs: List of transaction outputs (recipients and amounts).
        :param poc: PoC instance for routing transactions.
        """
        self.tx_id = tx_id
        self.inputs = self._ensure_inputs(inputs)  # Ensures all inputs have necessary fields
        self.outputs = self._ensure_outputs(outputs)  # Ensures all outputs have necessary fields
        self.timestamp = time.time()
        self.type = PaymentTypeManager().get_transaction_type(tx_id)
        self.fee = self._calculate_fee()
        self.hash = self.calculate_hash()
        self.poc = poc  # Use PoC for transaction routing

    def _ensure_inputs(self, inputs):
        """Ensure all inputs have required fields and default values if missing."""
        validated_inputs = []
        for inp in inputs:
            if "tx_out_id" not in inp:
                raise ValueError("[ERROR] Transaction input is missing 'tx_out_id'")
            if "amount" not in inp:
                raise ValueError("[ERROR] Transaction input is missing 'amount'")

            validated_inputs.append({
                "tx_out_id": inp["tx_out_id"],
                "amount": Decimal(inp["amount"]),
                "script_sig": inp.get("script_sig", "DEFAULT_SIGNATURE")
            })
        return validated_inputs

    def _ensure_outputs(self, outputs):
        """Ensure all outputs have required fields and default values if missing."""
        validated_outputs = []
        for out in outputs:
            if "recipient" not in out:
                raise ValueError("[ERROR] Transaction output is missing 'recipient'")
            if "amount" not in out:
                raise ValueError("[ERROR] Transaction output is missing 'amount'")

            validated_outputs.append({
                "recipient": out["recipient"],
                "amount": Decimal(out["amount"]),
                "script_pub_key": self._get_script_pub_key(out["recipient"])  # Fetch from KeyManager
            })
        return validated_outputs

    def _calculate_fee(self) -> Decimal:
        """Calculate transaction fee as input_total - output_total"""
        input_total = sum(inp["amount"] for inp in self.inputs)
        output_total = sum(out["amount"] for out in self.outputs)
        return input_total - output_total

    def _get_script_pub_key(self, recipient_address):
        """Fetch the scriptPubKey (hashed public key) for a given recipient using KeyManager"""
        key_manager = KeyManager()
        try:
            return key_manager.get_default_public_key("mainnet", "miner")  # Defaulting to miner for now
        except ValueError:
            return recipient_address  # If no key found, fallback to recipient address

    def calculate_hash(self) -> str:
        """Calculate SHA3-384 hash of the transaction"""
        input_data = "".join(f"{i['tx_out_id']}{i['amount']}" for i in self.inputs)
        output_data = "".join(f"{o['recipient']}{o['amount']}" for o in self.outputs)
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
    def create_transaction(tx_type: TransactionType, inputs: List[Dict], outputs: List[Dict]) -> Transaction:
        """Create a new transaction of the specified type"""
        prefix = PaymentTypeManager().TYPE_CONFIG[tx_type]["prefixes"][0] if tx_type != TransactionType.STANDARD else ""
        base_data = f"{prefix}{','.join(str(i['amount']) for i in inputs)}"
        tx_id = sha3_384_hash(base_data + str(time.time()))[:64]
        return Transaction(tx_id, inputs, outputs)


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