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
        try:
            # ✅ Validate inputs and outputs
            if not isinstance(inputs, list) or not all(isinstance(inp, TransactionIn) for inp in inputs):
                print("[TRANSACTION ERROR] All inputs must be instances of TransactionIn.")
                raise TypeError("All inputs must be instances of TransactionIn.")
            if not isinstance(outputs, list) or not all(isinstance(out, TransactionOut) for out in outputs):
                print("[TRANSACTION ERROR] All outputs must be instances of TransactionOut.")
                raise TypeError("All outputs must be instances of TransactionOut.")

            # ✅ Assign UTXO Manager (create default if not provided)
            self.utxo_manager = utxo_manager if utxo_manager else self._get_default_utxo_manager()

            # ✅ Ensure inputs and outputs are instances of correct classes
            self.inputs = [inp if isinstance(inp, TransactionIn) else TransactionIn.from_dict(inp) for inp in inputs]
            self.outputs = [out if isinstance(out, TransactionOut) else TransactionOut.from_dict(out) for out in outputs]

            # ✅ Set timestamp and ensure transaction type is formatted correctly
            self.timestamp = int(time.time())
            self.type = tx_type.upper().strip()
            if self.type not in ["STANDARD", "COINBASE"]:
                print(f"[TRANSACTION WARNING] Unknown transaction type '{self.type}'. Defaulting to STANDARD.")
                self.type = "STANDARD"

            # ✅ Generate transaction ID if not provided
            self.tx_id = tx_id if tx_id else self._generate_tx_id()
            if not isinstance(self.tx_id, str):
                print("[TRANSACTION ERROR] Transaction ID must be a string.")
                raise TypeError("Transaction ID must be a valid string.")

            # ✅ Compute transaction hash
            self.hash = self.calculate_hash()

            # ✅ Initialize FeeModel (if not provided, use a default one)
            self.fee_model = fee_model if fee_model else FeeModel(max_supply=Decimal(Constants.MAX_SUPPLY))

            # ✅ Compute transaction size and minimum fee
            self.size = self._calculate_size()
            self.fee = max(self._calculate_fee(), Decimal(Constants.MIN_TRANSACTION_FEE))

            print(f"[TRANSACTION INFO] Created transaction {self.tx_id} | Type: {self.type} | Fee: {self.fee} | Size: {self.size} bytes")

        except Exception as e:
            print(f"[TRANSACTION ERROR] Failed to initialize transaction: {e}")
            raise ValueError("Transaction initialization failed due to an unexpected error.")

    def _generate_tx_id(self) -> str:
        """
        Generate a unique transaction ID using single SHA3-384 hashing with a time-based salt.
        Ensures a hex-encoded string output for consistency.
        """
        try:
            # ✅ Ensure prefix is properly retrieved (fallback to empty string)
            prefix = Constants.TRANSACTION_MEMPOOL_MAP.get(self.type, {}).get("prefixes", [""])[0]

            # ✅ Create time-based salt using SHA3-384
            salt = hashlib.sha3_384(str(time.time()).encode()).hexdigest()

            # ✅ Construct transaction data to hash
            tx_data = f"{prefix}{self.timestamp}{salt}"
            tx_id_bytes = Hashing.hash(tx_data.encode())

            # ✅ Ensure tx_id is returned as a hex string
            tx_id = tx_id_bytes.hex()

            print(f"[TRANSACTION _generate_tx_id INFO] Generated tx_id: {tx_id}")
            return tx_id
        except Exception as e:
            print(f"[TRANSACTION _generate_tx_id ERROR] Failed to generate tx_id: {e}")
            return Constants.ZERO_HASH  # Return default zero hash in case of failure

    def calculate_hash(self) -> str:
        """
        Calculate the transaction's unique hash using single SHA3-384 hashing.
        Incorporates tx_id, timestamp, inputs, and outputs.
        Ensures the result is a hex-encoded string.
        """
        try:
            # ✅ Safely extract input and output data
            input_data = "".join(getattr(inp, "tx_out_id", "") for inp in self.inputs)
            output_data = "".join(f"{getattr(out, 'script_pub_key', '')}{getattr(out, 'amount', '')}" for out in self.outputs)

            # ✅ Construct hashable transaction string
            combined_data = f"{self.tx_id}{self.timestamp}{input_data}{output_data}"

            # ✅ Compute SHA3-384 hash
            tx_hash_bytes = Hashing.hash(combined_data.encode())

            # ✅ Ensure hash is returned as a hex string
            tx_hash = tx_hash_bytes.hex()

            print(f"[TRANSACTION calculate_hash INFO] Computed hash for {self.tx_id}: {tx_hash[:24]}...")
            return tx_hash
        except Exception as e:
            print(f"[TRANSACTION calculate_hash ERROR] {e}")
            return Constants.ZERO_HASH  # Return default zero hash if hashing fails

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
        try:
            if self.type == "COINBASE":
                print(f"[TRANSACTION _calculate_fee INFO] Coinbase transaction detected (tx_id: {self.tx_id}); fee set to 0.")
                return Decimal("0")

            input_total = Decimal("0")
            output_total = Decimal("0")

            # ✅ Calculate total input value from UTXOs
            if self.utxo_manager:
                for inp in self.inputs:
                    try:
                        utxo_info = self.utxo_manager.get_utxo(inp.tx_out_id)
                        if not utxo_info or "amount" not in utxo_info:
                            print(f"[TRANSACTION _calculate_fee WARN] Missing or invalid UTXO for {inp.tx_out_id}; defaulting to 0.")
                            continue
                        input_total += Decimal(utxo_info["amount"])
                    except Exception as e:
                        print(f"[TRANSACTION _calculate_fee ERROR] Failed to retrieve UTXO amount for {inp.tx_out_id}: {e}")

            else:
                print("[TRANSACTION _calculate_fee WARN] No UTXO manager provided; input_total = 0.")

            # ✅ Calculate total output value
            for out in self.outputs:
                try:
                    output_total += Decimal(out.amount)
                except Exception as e:
                    print(f"[TRANSACTION _calculate_fee ERROR] Invalid output amount for {out}: {e}")

            # ✅ Compute raw transaction fee
            fee = input_total - output_total
            if fee < 0:
                print(f"[TRANSACTION _calculate_fee WARN] Negative fee detected ({fee}); clamping to 0.")
                fee = Decimal("0")

            # ✅ Ensure fee meets the minimum required
            required_fee = Decimal("0")
            if self.fee_model:
                try:
                    required_fee = self.fee_model.calculate_fee(
                        block_size=Constants.MAX_BLOCK_SIZE_BYTES,
                        payment_type=self.type,
                        amount=input_total,
                        tx_size=self.size
                    )
                except Exception as e:
                    print(f"[TRANSACTION _calculate_fee ERROR] Fee model calculation failed: {e}")
                    required_fee = Decimal("0")

            if fee < required_fee:
                print(f"[TRANSACTION _calculate_fee INFO] Adjusting fee for {self.tx_id} to required minimum: {required_fee} (raw fee: {fee})")
                fee = required_fee

            print(f"[TRANSACTION _calculate_fee INFO] Computed fee for {self.tx_id}: {fee} (Inputs: {input_total}, Outputs: {output_total}, Required: {required_fee})")
            return fee

        except Exception as e:
            print(f"[TRANSACTION _calculate_fee ERROR] Unexpected error calculating fee: {e}")
            return Decimal("0")


    def to_dict(self) -> Dict:
        """
        Serialize the transaction to a dictionary.
        Includes all fields necessary for storage and debugging.
        Ensures all values are properly formatted.
        """
        try:
            return {
                "tx_id": self.tx_id,
                "inputs": [inp.to_dict() if hasattr(inp, "to_dict") else {} for inp in self.inputs],
                "outputs": [out.to_dict() if hasattr(out, "to_dict") else {} for out in self.outputs],
                "timestamp": int(self.timestamp),  # Convert timestamp to integer for consistency
                "type": self.type,
                "tx_type": self.type,  # For standardized serialization
                "fee": str(self.fee),  # Convert Decimal fee to string to avoid float issues
                "size": self.size,
                "hash": self.hash.hex() if isinstance(self.hash, bytes) else self.hash,  # Ensure hash is hex string
            }
        except Exception as e:
            print(f"[TRANSACTION to_dict ERROR] Failed to serialize transaction {self.tx_id}: {e}")
            return {}

    def store_transaction(self):
        """
        Store the transaction using TxStorage.
        Uses a lazy import to break circular dependencies.
        Ensures transaction storage is handled safely.
        """
        try:
            print(f"[TRANSACTION store_transaction INFO] Attempting to store transaction {self.tx_id}...")

            # ✅ Lazy import of TxStorage to prevent circular imports
            import importlib
            try:
                tx_storage_module = importlib.import_module("Zyiron_Chain.storage.tx_storage")
                TxStorage = getattr(tx_storage_module, "TxStorage")
            except ImportError as e:
                print(f"[TRANSACTION store_transaction ERROR] Failed to import TxStorage module: {e}")
                return

            # ✅ Ensure TxStorage has a store_transaction method
            if not hasattr(TxStorage, "store_transaction"):
                print(f"[TRANSACTION store_transaction ERROR] TxStorage does not have a store_transaction method.")
                return

            # ✅ Store the transaction safely
            TxStorage().store_transaction(self.to_dict())
            print(f"[TRANSACTION store_transaction SUCCESS] Transaction {self.tx_id} stored successfully.")

        except Exception as e:
            print(f"[TRANSACTION store_transaction ERROR] Could not store transaction {self.tx_id}: {e}")


    def store_utxo(self):
        """
        Store each output of this transaction as a UTXO using UTXOStorage.
        Uses lazy import to break circular dependencies.
        Ensures all UTXOs are properly formatted and stored safely.
        """
        try:
            print(f"[TRANSACTION store_utxo INFO] Attempting to store UTXOs for transaction {self.tx_id}...")

            # ✅ Lazy import of UTXOStorage to prevent circular import issues
            import importlib
            try:
                utxo_storage_module = importlib.import_module("Zyiron_Chain.storage.utxostorage")
                UTXOStorage = getattr(utxo_storage_module, "UTXOStorage")
            except ImportError as e:
                print(f"[TRANSACTION store_utxo ERROR] Failed to import UTXOStorage module: {e}")
                return

            # ✅ Ensure UTXOStorage has the necessary method
            if not hasattr(UTXOStorage, "store_utxo"):
                print(f"[TRANSACTION store_utxo ERROR] UTXOStorage does not have a store_utxo method.")
                return

            # ✅ Initialize UTXOStorage instance
            utxo_storage = UTXOStorage()

            # ✅ Process and store each output
            for idx, output in enumerate(self.outputs):
                try:
                    utxo_id = f"{self.tx_id}-{idx}"

                    # ✅ Ensure output has the necessary fields
                    if not hasattr(output, "amount") or not hasattr(output, "script_pub_key"):
                        print(f"[TRANSACTION store_utxo WARN] Skipping malformed output at index {idx} in transaction {self.tx_id}.")
                        continue

                    utxo_data = {
                        "tx_out_id": self.tx_id,
                        "amount": str(output.amount),
                        "script_pub_key": output.script_pub_key,
                        "locked": False,
                        "block_index": 0  # This should be updated when the block is mined
                    }

                    utxo_storage.store_utxo(utxo_id, utxo_data)
                    print(f"[TRANSACTION store_utxo INFO] Stored UTXO {utxo_id} successfully.")

                except Exception as e:
                    print(f"[TRANSACTION store_utxo ERROR] Failed to store UTXO {self.tx_id}-{idx}: {e}")

            print(f"[TRANSACTION store_utxo SUCCESS] All valid UTXOs for transaction {self.tx_id} stored successfully.")

        except Exception as e:
            print(f"[TRANSACTION store_utxo ERROR] Unexpected failure while storing UTXOs for transaction {self.tx_id}: {e}")


