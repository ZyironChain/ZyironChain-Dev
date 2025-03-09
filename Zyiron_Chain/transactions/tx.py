import sys
import os
import time
import hashlib
import json
from decimal import Decimal
from typing import List, Dict, Optional
import importlib

# Adjust Python path for project structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.txin import TransactionIn
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.utils.deserializer import Deserializer


class Transaction:
    """
    Represents a standard blockchain transaction in the new split-storage environment.

    - Uses lazy imports for TxStorage and UTXOStorage to avoid circular imports.
    - Uses single SHA3-384 hashing via Hashing.hash().
    - Detailed print statements are provided for debugging.
    """

    def __init__(
        self,
        inputs: List[TransactionIn],
        outputs: List[TransactionOut],
        tx_id: Optional[str] = None,
        utxo_manager: Optional[UTXOManager] = None,
        tx_type: str = "STANDARD",
        fee_model: Optional[FeeModel] = None
    ):
        """
        Initialize a transaction object.

        :param inputs: List of TransactionIn objects.
        :param outputs: List of TransactionOut objects.
        :param tx_id: Optional transaction ID (auto-generated if not provided).
        :param utxo_manager: Optional UTXOManager for retrieving UTXO data.
        :param tx_type: Transaction type, e.g. "STANDARD" or "COINBASE".
        :param fee_model: Optional FeeModel instance for dynamic fee calculation.
        """
        # Validate input and output types
        if not all(isinstance(inp, TransactionIn) for inp in inputs):
            print("[TRANSACTION __init__ ERROR] All inputs must be instances of TransactionIn.")
            raise TypeError("All inputs must be instances of TransactionIn.")
        if not all(isinstance(out, TransactionOut) for out in outputs):
            print("[TRANSACTION __init__ ERROR] All outputs must be instances of TransactionOut.")
            raise TypeError("All outputs must be instances of TransactionOut.")

        # Assign UTXO Manager, creating a default if not provided
        self.utxo_manager = utxo_manager if utxo_manager else self._get_default_utxo_manager()

        # Ensure inputs and outputs are proper instances
        self.inputs = [inp if isinstance(inp, TransactionIn) else TransactionIn.from_dict(inp) for inp in inputs]
        self.outputs = [out if isinstance(out, TransactionOut) else TransactionOut.from_dict(out) for out in outputs]

        # Set timestamp and transaction type
        self.timestamp = time.time()
        self.type = tx_type.upper().strip()

        # Generate transaction ID if not provided
        self.tx_id = tx_id if tx_id else self._generate_tx_id()

        # Calculate transaction hash (after tx_id and timestamp are set)
        self.hash = self.calculate_hash()

        # Lazy storage: TxStorage and UTXOStorage will be imported on-demand in their methods
        self.fee_model = fee_model if fee_model else FeeModel(max_supply=Decimal(Constants.MAX_SUPPLY))

        # Compute transaction size and fee
        self.size = self._calculate_size()
        self.fee = max(self._calculate_fee(), Decimal(Constants.MIN_TRANSACTION_FEE))

        print(f"[TRANSACTION __init__ INFO] Created transaction {self.tx_id} | Type: {self.type} | Fee: {self.fee} | Size: {self.size} bytes")

    def _generate_tx_id(self) -> str:
        """
        Generate a unique transaction ID using single SHA3-384 hashing with a time-based salt.
        """
        prefix = Constants.TRANSACTION_MEMPOOL_MAP.get(self.type, {}).get("prefixes", [""])[0]
        tx_data = f"{prefix}{self.timestamp}{hashlib.sha3_384(str(time.time()).encode()).hexdigest()}"
        tx_id = Hashing.hash(tx_data.encode())
        print(f"[TRANSACTION _generate_tx_id INFO] Generated tx_id: {tx_id}")
        return tx_id

    def calculate_hash(self) -> str:
        """
        Calculate the transaction's unique hash using single SHA3-384 hashing.
        Incorporates tx_id, timestamp, inputs, and outputs.
        """
        try:
            input_data = "".join(inp.tx_out_id for inp in self.inputs)
            output_data = "".join(f"{out.script_pub_key}{out.amount}" for out in self.outputs)
            combined = f"{self.tx_id}{self.timestamp}{input_data}{output_data}"
            tx_hash = Hashing.hash(combined.encode())
            print(f"[TRANSACTION calculate_hash INFO] Computed hash for {self.tx_id}: {tx_hash[:24]}...")
            return tx_hash
        except Exception as e:
            print(f"[TRANSACTION calculate_hash ERROR] {e}")
            return Constants.ZERO_HASH

    def _calculate_size(self) -> int:
        """
        Estimate transaction size based on inputs, outputs, and standardized metadata.
        For non-coinbase transactions, require at least one input and one output.
        For coinbase, require at least one output.
        """
        if self.type != "COINBASE":
            if not self.inputs or not self.outputs:
                print("[TRANSACTION _calculate_size ERROR] Non-coinbase transaction must have at least one input and one output.")
                raise ValueError("Transaction must have at least one input and one output.")
        else:
            if not self.outputs:
                print("[TRANSACTION _calculate_size ERROR] Coinbase transaction must have at least one output.")
                raise ValueError("Coinbase transaction must have at least one output.")

        try:
            # Calculate the size of the input fields
            input_size = sum(len(inp.to_dict()) for inp in self.inputs)
            
            # Calculate the size of the output fields
            output_size = sum(len(out.to_dict()) for out in self.outputs)
            
            # Calculate metadata size based on standardized data structure
            # Metadata includes fixed-length fields like tx_id, hash, and timestamp
            meta_size = len(self.tx_id) + len(self.hash) + 8  # 8 bytes for timestamp
            
            # Total transaction size is the sum of all components
            total_size = input_size + output_size + meta_size
            
            # If size exceeds maximum block size, clamp it to the max allowed size
            if total_size > Constants.MAX_BLOCK_SIZE_BYTES:
                print(f"[TRANSACTION _calculate_size WARN] Transaction size {total_size} exceeds max block size {Constants.MAX_BLOCK_SIZE_BYTES}. Clamping.")
                total_size = Constants.MAX_BLOCK_SIZE_BYTES
            
            # Print and return the computed size
            print(f"[TRANSACTION _calculate_size INFO] Computed size: {total_size} bytes for {self.tx_id}")
            return total_size
        except Exception as e:
            print(f"[TRANSACTION _calculate_size ERROR] {e}")
            return 0


    def _calculate_fee(self) -> Decimal:
        """
        Calculate the transaction fee:
         - Sum input amounts from the UTXO manager (if available).
         - Sum output amounts.
         - The difference is the raw fee.
         - Adjust fee based on the fee model's dynamic requirement.
        """
        if self.type == "COINBASE":
            print("[TRANSACTION _calculate_fee INFO] Coinbase transaction detected; fee set to 0.")
            return Decimal("0")

        input_total = Decimal("0")
        output_total = Decimal("0")

        if self.utxo_manager:
            for inp in self.inputs:
                utxo_info = self.utxo_manager.get_utxo(inp.tx_out_id)
                if not utxo_info or "amount" not in utxo_info:
                    print(f"[TRANSACTION _calculate_fee WARN] Missing or invalid UTXO for {inp.tx_out_id}; defaulting to 0.")
                    continue
                try:
                    input_total += Decimal(utxo_info["amount"])
                except Exception as e:
                    print(f"[TRANSACTION _calculate_fee ERROR] Invalid UTXO amount for {inp.tx_out_id}: {e}")
        else:
            print("[TRANSACTION _calculate_fee WARN] No UTXO manager provided; input_total = 0.")

        for out in self.outputs:
            try:
                output_total += Decimal(out.amount)
            except Exception as e:
                print(f"[TRANSACTION _calculate_fee ERROR] Invalid output amount for {out}: {e}")

        fee = input_total - output_total
        if fee < 0:
            print(f"[TRANSACTION _calculate_fee WARN] Negative fee detected ({fee}); clamping to 0.")
            fee = Decimal("0")

        required_fee = Decimal("0")
        if self.fee_model:
            required_fee = self.fee_model.calculate_fee(
                block_size=Constants.MAX_BLOCK_SIZE_BYTES,
                payment_type=self.type,
                amount=input_total,
                tx_size=self.size
            )
        if fee < required_fee:
            print(f"[TRANSACTION _calculate_fee INFO] Adjusting fee for {self.tx_id} to required minimum: {required_fee} (raw fee: {fee})")
            fee = required_fee

        print(f"[TRANSACTION _calculate_fee INFO] Computed fee for {self.tx_id}: {fee} (Inputs: {input_total}, Outputs: {output_total}, Required: {required_fee})")
        return fee

    def to_dict(self) -> Dict:
        """
        Serialize the transaction to a dictionary.
        Includes all fields necessary for storage and debugging.
        """
        return {
            "tx_id": self.tx_id,
            "inputs": [inp.to_dict() for inp in self.inputs],
            "outputs": [out.to_dict() for out in self.outputs],
            "timestamp": int(self.timestamp),  # Convert timestamp to integer
            "type": self.type,
            "tx_type": self.type,  # For standardized serialization
            "fee": str(self.fee),  # Fee as a string for consistency
            "size": self.size,
            "hash": self.hash,  # Transaction hash
        }

    def store_transaction(self):
        """
        Store the transaction using TxStorage.
        Uses a lazy import to break circular dependencies.
        """
        try:
            print(f"[TRANSACTION store_transaction INFO] Storing transaction {self.tx_id} in TxStorage...")
            tx_storage_module = importlib.import_module("Zyiron_Chain.storage.tx_storage")
            TxStorage = getattr(tx_storage_module, "TxStorage")
            TxStorage().store_transaction(self.to_dict())
            print(f"[TRANSACTION store_transaction SUCCESS] Transaction {self.tx_id} stored in TxStorage.")
        except Exception as e:
            print(f"[TRANSACTION store_transaction ERROR] Could not store transaction {self.tx_id}: {e}")

    def store_utxo(self):
        """
        Store each output of this transaction as a UTXO using UTXOStorage.
        Uses lazy import to break circular dependencies.
        """
        try:
            print(f"[TRANSACTION store_utxo INFO] Storing UTXOs for transaction {self.tx_id}...")
            utxo_storage_module = importlib.import_module("Zyiron_Chain.storage.utxostorage")
            UTXOStorage = getattr(utxo_storage_module, "UTXOStorage")
            utxo_storage = UTXOStorage()
            for idx, output in enumerate(self.outputs):
                utxo_id = f"{self.tx_id}-{idx}"
                utxo_data = {
                    "tx_out_id": self.tx_id,
                    "amount": str(output.amount),
                    "script_pub_key": output.script_pub_key,
                    "locked": False,
                    "block_index": 0  # This should be updated when the block is mined
                }
                utxo_storage.store_utxo(utxo_id, utxo_data)
            print(f"[TRANSACTION store_utxo SUCCESS] UTXOs for transaction {self.tx_id} stored in UTXOStorage.")
        except Exception as e:
            print(f"[TRANSACTION store_utxo ERROR] Could not store UTXOs for transaction {self.tx_id}: {e}")

    @classmethod
    def from_bytes(cls, tx_data):
        """Deserialize a transaction from bytes."""
        data = Deserializer().deserialize(tx_data)
        return cls.from_dict(data)
