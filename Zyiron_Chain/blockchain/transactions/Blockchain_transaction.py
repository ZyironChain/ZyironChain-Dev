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
import logging

def get_poc():
    """Lazy import PoC to break circular dependencies."""
    from Zyiron_Chain.database.poc import PoC
    return PoC


def get_transaction():
    """Lazy import Transaction to break circular dependencies."""
    from Zyiron_Chain.transactions.Blockchain_transaction import Transaction
    return Transaction

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

import hashlib
import time
from decimal import Decimal
from typing import Dict

class CoinbaseTx:
    """Represents a block reward transaction"""
    
    def __init__(self, block_height: int, miner_address: str, reward: Decimal):
        self.timestamp = time.time()  # ✅ Define timestamp first
        self.tx_id = self._generate_tx_id(block_height, self.timestamp)  # ✅ Generate TX ID after timestamp
        self.inputs = []  # Coinbase transactions have no inputs
        self.outputs = [{"address": miner_address, "amount": float(reward)}]
        self.type = "COINBASE"  # ✅ Ensure consistent transaction type
        self.hash = self.calculate_hash()  # ✅ Ensure hash is generated

    def _generate_tx_id(self, block_height: int, timestamp: float) -> str:
        """Generate a unique transaction ID using SHA3-384 hashing"""
        tx_data = f"COINBASE-{block_height}-{timestamp}"
        return hashlib.sha3_384(tx_data.encode()).hexdigest()[:24]  # ✅ Shorten to 24 characters

    def calculate_hash(self) -> str:
        """Calculate SHA3-384 hash of the transaction"""
        tx_data = f"{self.tx_id}{self.timestamp}{self.outputs[0]['address']}{self.outputs[0]['amount']}"
        return hashlib.sha3_384(tx_data.encode()).hexdigest()

    def to_dict(self) -> Dict:
        """Serialize CoinbaseTx to a dictionary"""
        return {
            "tx_id": self.tx_id,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "timestamp": self.timestamp,
            "type": self.type,
            "hash": self.hash
        }


class Transaction:
    """Represents a standard blockchain transaction"""

    def __init__(self, inputs: List["TransactionIn"], outputs: List["TransactionOut"], tx_id: str = None, poc: "PoC" = None, utxo_manager=None):
        """
        Initialize a transaction object.

        :param inputs: List of transaction inputs.
        :param outputs: List of transaction outputs.
        :param tx_id: (Optional) Unique transaction ID. If not provided, it is auto-generated.
        :param poc: (Optional) Point-of-Contact instance for blockchain interactions.
        :param utxo_manager: (Optional) UTXO Manager for handling UTXO state.
        """
        # ✅ Validate input and output types
        if not all(isinstance(inp, TransactionIn) for inp in inputs):
            raise TypeError("[ERROR] All inputs must be instances of TransactionIn.")
        if not all(isinstance(out, TransactionOut) for out in outputs):
            raise TypeError("[ERROR] All outputs must be instances of TransactionOut.")

        # ✅ Assign UTXO Manager, ensuring it exists
        self.utxo_manager = utxo_manager if utxo_manager else self._get_default_utxo_manager()

        # ✅ Convert inputs/outputs to correct format if needed
        self.inputs = [inp if isinstance(inp, TransactionIn) else TransactionIn.from_dict(inp) for inp in inputs]
        self.outputs = [out if isinstance(out, TransactionOut) else TransactionOut.from_dict(out) for out in outputs]

        # ✅ Assign timestamp
        self.timestamp = time.time()

        # ✅ Ensure transaction type is set properly
        self.type = PaymentTypeManager().get_transaction_type(tx_id)

        # ✅ Fix: Auto-generate a `tx_id` if it's missing
        self.tx_id = tx_id if tx_id else self._generate_tx_id()

        # ✅ Calculate hash after ensuring all required attributes exist
        self.hash = self.calculate_hash()

        # ✅ Store PoC reference for blockchain interactions
        self.poc = poc if poc else get_poc()

        # ✅ Compute transaction size
        self.size = self._calculate_size()  # ✅ Change from `size_bytes` to `size`

        # ✅ Compute transaction fee
        self.fee = self._calculate_fee()  # ✅ Ensure fee is calculated after all attributes are set




    def _generate_tx_id(self) -> str:
        """Generate a unique transaction ID using SHA3-384 hashing"""
        tx_data = f"{self.timestamp}{self.calculate_hash()}"
        return sha3_384_hash(tx_data)[:24]  # ✅ Shorten to 24 characters


    def _get_default_utxo_manager(self):
        """Retrieve the default UTXO manager instance if not provided."""
        from Zyiron_Chain.transactions.utxo_manager import UTXOManager
        from Zyiron_Chain.database.poc import PoC  # Ensure PoC is passed to UTXOManager
        return UTXOManager(PoC())  # ✅ Provide a valid default instance

    @classmethod
    def from_dict(cls, data: Dict) -> "Transaction":
        """
        Create a Transaction instance from a dictionary.
        :param data: Dictionary containing transaction data.
        :return: A Transaction instance.
        """
        if not isinstance(data, dict):
            raise TypeError("[ERROR] Input data must be a dictionary.")

        # ✅ Ensure all inputs are converted from dictionaries properly
        inputs = [
            TransactionIn.from_dict(inp) if isinstance(inp, dict) else inp
            for inp in data.get("inputs", [])
        ]

        # ✅ Ensure all outputs are converted from dictionaries properly
        outputs = [
            TransactionOut.from_dict(out) if isinstance(out, dict) else out
            for out in data.get("outputs", [])
        ]

        return cls(
            tx_id=data.get("tx_id", ""),
            inputs=inputs,
            outputs=outputs
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
        """Calculate transaction fee and ensure it is never negative."""

        # ✅ Ensure Coinbase transactions never calculate fees
        if self.type == "COINBASE":
            logging.info(f"[INFO] Coinbase Transaction Detected - Fee Set to 0")
            return Decimal("0")

        # ✅ Initialize totals to ensure safe calculations
        input_total = Decimal("0")
        output_total = Decimal("0")

        # ✅ Retrieve input UTXOs and sum their amounts
        for inp in self.inputs:
            utxo = self.utxo_manager.get_utxo(inp.tx_out_id)
            if utxo:
                input_total += Decimal(utxo.amount)
            else:
                logging.warning(f"[WARNING] Missing UTXO {inp.tx_out_id} - Defaulting to 0")

        # ✅ Sum output amounts
        for out in self.outputs:
            output_total += Decimal(out.amount) if isinstance(out, TransactionOut) else Decimal(out.get("amount", 0))

        # ✅ Calculate fee (Preventing Negative Fee Issue)
        fee = input_total - output_total

        if fee < Decimal("0"):
            logging.warning(f"[WARNING] Negative Fee Detected: Adjusting to 0. Input: {input_total}, Output: {output_total}, Fee: {fee}")
            fee = Decimal("0")  # ✅ Ensure fee never goes negative

        return fee



    def _get_script_pub_key(self, recipient_address):
        """Fetch the scriptPubKey (hashed public key) for a given recipient using KeyManager"""
        key_manager = KeyManager()
        try:
            return key_manager.get_default_public_key("mainnet", "miner")  # Defaulting to miner for now
        except ValueError:
            return recipient_address  # If no key found, fallback to recipient address

    def calculate_hash(self) -> str:
        """Calculate SHA3-384 hash of the transaction"""
        input_data = "".join(f"{i.tx_out_id}" for i in self.inputs)
        output_data = "".join(f"{o.script_pub_key}{o.amount}" for o in self.outputs)
        return sha3_384_hash(f"{input_data}{output_data}{self.timestamp}")


    
    
    def to_dict(self) -> Dict:
        """Serialize Transaction to a dictionary"""
        return {
            "tx_id": self.tx_id,
            "inputs": [inp.to_dict() if isinstance(inp, TransactionIn) else inp for inp in self.inputs],  # ✅ Convert inputs properly
            "outputs": [out.to_dict() if isinstance(out, TransactionOut) else out for out in self.outputs],  # ✅ Convert outputs properly
            "timestamp": self.timestamp,
            "type": self.type.name if self.type else "UNKNOWN",
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
                    "amount": float(output.amount),  # ✅ Convert amount properly
                    "script_pub_key": output.script_pub_key,  # ✅ Access object attribute
                    "locked": False,  # Newly created UTXOs are unlocked
                    "block_index": 0  # To be updated when included in a block
                })
            print(f"[INFO] UTXOs stored successfully via PoC for transaction {self.tx_id}")
        except Exception as e:
            print(f"[ERROR] Failed to store UTXOs for transaction {self.tx_id}: {e}")


class TransactionFactory:
    """Factory for creating transactions"""

    @staticmethod
    def create_transaction(tx_type: "TransactionType", inputs: List[Dict], outputs: List[Dict], poc=None) -> "Transaction":
        """
        Create a new transaction of the specified type.
        """
        if poc is None:
            from Zyiron_Chain.database.poc import PoC
            poc = PoC()  # ✅ Load PoC dynamically

        payment_manager = PaymentTypeManager()
        if tx_type not in payment_manager.TYPE_CONFIG:
            raise ValueError(f"[ERROR] Invalid transaction type: {tx_type}")

        prefix = payment_manager.TYPE_CONFIG[tx_type]["prefixes"][0] if tx_type != TransactionType.STANDARD else ""
        
        # ✅ Use `sha3_384_hash()` instead of custom function
        base_data = f"{prefix}{','.join(str(i['amount']) for i in inputs)}{str(time.time())}"
        tx_id = sha3_384_hash(base_data)[:64]  # ✅ Proper hashing

        return Transaction(
            inputs=[TransactionIn.from_dict(inp) for inp in inputs],
            outputs=[TransactionOut.from_dict(out) for out in outputs],
            tx_id=tx_id,
            poc=poc
        )


class TransactionIn:
    """
    Represents a transaction input, referencing a previous UTXO.
    """

    def __init__(self, tx_out_id: str, script_sig: str):
        """
        Initialize a Transaction Input.
        :param tx_out_id: The UTXO being referenced.
        :param script_sig: The unlocking script (signature).
        """
        if not isinstance(tx_out_id, str) or not tx_out_id:
            raise ValueError("[ERROR] tx_out_id must be a valid string.")
        if not isinstance(script_sig, str) or not script_sig:
            raise ValueError("[ERROR] script_sig must be a valid string.")

        self.tx_out_id = tx_out_id
        self.script_sig = script_sig

    def to_dict(self) -> Dict[str, str]:
        """
        Convert the Transaction Input to a dictionary format.
        :return: Dictionary representation of the transaction input.
        """
        return {
            "tx_out_id": self.tx_out_id,
            "script_sig": self.script_sig
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TransactionIn":
        """
        Create a TransactionIn instance from a dictionary.
        :param data: Dictionary containing transaction input data.
        :return: A TransactionIn instance.
        """
        if not isinstance(data, dict):
            raise TypeError("[ERROR] Input data must be a dictionary.")

        if "tx_out_id" not in data or "script_sig" not in data:
            raise KeyError("[ERROR] Missing required fields: 'tx_out_id' or 'script_sig'.")

        return cls(
            tx_out_id=data["tx_out_id"],
            script_sig=data["script_sig"]
        )
