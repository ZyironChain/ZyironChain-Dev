import sys
import os


# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)





import time
import hashlib
import logging
from decimal import Decimal
from typing import List, Dict
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.txin import TransactionIn
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.database.poc import PoC  # Ensure PoC is passed to UTXOManager
from Zyiron_Chain.blockchain.transaction_manager import PaymentTypeManager
from Zyiron_Chain.blockchain.utils.hashing import sha3_384_hash

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

        # ✅ Auto-generate `tx_id` if missing
        self.tx_id = tx_id if tx_id else self._generate_tx_id()

        # ✅ Calculate hash after ensuring all required attributes exist
        self.hash = self.calculate_hash()

        # ✅ Store PoC reference for blockchain interactions
        self.poc = poc if poc else PoC()

        # ✅ Compute transaction size
        self.size = self._calculate_size()

        # ✅ Compute transaction fee
        self.fee = self._calculate_fee()

        logging.info(f"[TRANSACTION] Created new transaction: {self.tx_id}, Type: {self.type}, Fee: {self.fee}, Size: {self.size} bytes")


    def _generate_tx_id(self) -> str:
        """Generate a unique transaction ID using SHA3-384 hashing"""
        tx_data = f"{self.timestamp}{self.hash}"
        return hashlib.sha3_384(tx_data.encode()).hexdigest()[:24]  # ✅ Shortened for efficiency

    def _get_default_utxo_manager(self):
        """Retrieve the default UTXO manager instance if not provided."""
        from Zyiron_Chain.transactions.utxo_manager import UTXOManager
        from Zyiron_Chain.database.poc import PoC

        return UTXOManager(PoC(storage_type=Constants.DATABASES["utxo"]))  # ✅ Uses correct database type

    @classmethod
    def from_dict(cls, data: Dict) -> "Transaction":
        """
        Create a Transaction instance from a dictionary.
        
        :param data: Dictionary containing transaction data.
        :return: A Transaction instance.
        """
        if not isinstance(data, dict):
            raise TypeError("[ERROR] Input data must be a dictionary.")

        # ✅ Convert inputs from dict format
        inputs = [
            TransactionIn.from_dict(inp) if isinstance(inp, dict) else inp
            for inp in data.get("inputs", [])
        ]

        # ✅ Convert outputs from dict format
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
        from Zyiron_Chain.transactions.txin import TransactionIn  # Updated import for modular structure

        if not isinstance(inputs, list):
            raise TypeError("[ERROR] Inputs must be a list.")

        validated_inputs = []
        for inp in inputs:
            if not isinstance(inp, TransactionIn):
                if isinstance(inp, dict):
                    inp = TransactionIn.from_dict(inp)  # Convert from dict if necessary
                else:
                    raise TypeError(f"[ERROR] Expected TransactionIn object or dictionary, got {type(inp)}")
            
            validated_inputs.append(inp.to_dict())

        logging.info(f"[TRANSACTION] Validated {len(validated_inputs)} transaction inputs successfully.")
        return validated_inputs





    def _calculate_size(self) -> int:
        """Estimate transaction size based on inputs, outputs, and metadata."""
        if not self.inputs or not self.outputs:
            raise ValueError("[ERROR] Transaction must have at least one input and one output.")

        input_size = sum(len(str(inp.to_dict())) for inp in self.inputs)
        output_size = sum(len(str(out.to_dict())) for out in self.outputs)

        metadata_size = len(self.tx_id) + len(str(self.timestamp)) + len(self.hash)

        total_size = input_size + output_size + metadata_size

        logging.info(f"[TRANSACTION] Calculated transaction size: {total_size} bytes")
        return total_size


    def _ensure_outputs(self, outputs):
        """Ensure all outputs have required fields and convert to dictionaries."""
        from Zyiron_Chain.transactions.txout import TransactionOut  # Updated import

        if not isinstance(outputs, list):
            raise TypeError("[ERROR] Outputs must be a list.")

        validated_outputs = []
        for out in outputs:
            if not isinstance(out, TransactionOut):
                if isinstance(out, dict):
                    out = TransactionOut.from_dict(out)  # Convert from dict if necessary
                else:
                    raise TypeError(f"[ERROR] Expected TransactionOut object or dictionary, got {type(out)}")
            
            validated_outputs.append(out.to_dict())

        logging.info(f"[TRANSACTION] Validated {len(validated_outputs)} transaction outputs successfully.")
        return validated_outputs



    def _calculate_fee(self) -> Decimal:
        """Calculate transaction fee and ensure it meets the minimum required fee."""
        try:
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
                if utxo and "amount" in utxo:
                    try:
                        input_total += Decimal(utxo["amount"])
                    except (ValueError, TypeError):
                        logging.error(f"[ERROR] Invalid UTXO amount format for {inp.tx_out_id}")
                else:
                    logging.warning(f"[WARNING] Missing UTXO {inp.tx_out_id} - Defaulting to 0")

            # ✅ Sum output amounts
            for out in self.outputs:
                try:
                    output_total += Decimal(out.amount) if isinstance(out, TransactionOut) else Decimal(out.get("amount", 0))
                except (ValueError, TypeError):
                    logging.error(f"[ERROR] Invalid output amount format for {out}")
                    continue  # Skip invalid outputs

            # ✅ Calculate the raw transaction fee (Input - Output)
            fee = input_total - output_total

            # ✅ Prevent negative fees
            if fee < Decimal("0"):
                logging.warning(f"[WARNING] Negative Fee Detected: Adjusting to 0. Input: {input_total}, Output: {output_total}, Fee: {fee}")
                fee = Decimal("0")

            # ✅ Fetch the minimum fee from constants
            min_fee = Decimal(Constants.MIN_TRANSACTION_FEE)

            # ✅ Compute dynamic fee based on network congestion & transaction type
            dynamic_fee = self.poc.fee_model.calculate_fee(
                tx_size=self.size,
                tx_type=self.type,
                network_congestion=self.poc.mempool.size
            )

            # ✅ Ensure the fee is at least the greater of min_fee or dynamic_fee
            required_fee = max(min_fee, dynamic_fee)

            if fee < required_fee:
                logging.info(f"[FEE] Adjusting fee to the required minimum: {required_fee} (Original Fee: {fee})")
                fee = required_fee

            logging.info(f"[TRANSACTION] Fee Calculated: {fee} (Input: {input_total}, Output: {output_total}, Required Fee: {required_fee})")
            return fee

        except Exception as e:
            logging.error(f"[ERROR] Failed to calculate transaction fee: {e}")
            return Decimal(Constants.MIN_TRANSACTION_FEE)  # ✅ Default to minimum fee in case of an error





    def calculate_hash(self) -> str:
        """Calculate SHA3-384 hash of the transaction."""
        try:
            input_data = "".join(f"{i.tx_out_id}" for i in self.inputs)
            output_data = "".join(f"{o.script_pub_key}{o.amount}" for o in self.outputs)

            tx_string = f"{self.tx_id}{self.timestamp}{input_data}{output_data}"
            tx_hash = hashlib.sha3_384(tx_string.encode()).hexdigest()

            logging.info(f"[TRANSACTION] Computed transaction hash: {tx_hash[:24]}...")

            return tx_hash
        except Exception as e:
            logging.error(f"[ERROR] Transaction hash calculation failed: {e}")
            return Constants.ZERO_HASH
        

    def _get_script_pub_key(self, recipient_address):
        """
        Fetch the scriptPubKey (hashed public key) for a given recipient using KeyManager.
        - Uses KeyManager to retrieve the recipient's hashed public key if available.
        - Defaults to the recipient address if no key is found.
        """
        from Zyiron_Chain.blockchain.utils.key_manager import KeyManager  # Lazy import to avoid circular dependency

        key_manager = KeyManager()
        try:
            # ✅ Determine if the recipient is a miner or a standard user
            if recipient_address.startswith(Constants.ADDRESS_PREFIX):
                script_pub_key = key_manager.get_hashed_public_key(Constants.NETWORK, recipient_address)
            else:
                script_pub_key = key_manager.get_default_public_key(Constants.NETWORK, "miner")  # Fallback to miner key

            if script_pub_key:
                return script_pub_key
            else:
                raise ValueError("No valid scriptPubKey found")

        except ValueError:
            logging.warning(f"[WARNING] No valid scriptPubKey found for {recipient_address}, defaulting to recipient address.")
            return recipient_address  # ✅ Fallback to recipient address if key not found



    def to_dict(self) -> Dict:
        """Serialize Transaction to a dictionary, ensuring proper data formatting."""
        return {
            "tx_id": self.tx_id,
            "inputs": [inp.to_dict() if isinstance(inp, TransactionIn) else inp for inp in self.inputs],  # ✅ Convert inputs properly
            "outputs": [out.to_dict() if isinstance(out, TransactionOut) else out for out in self.outputs],  # ✅ Convert outputs properly
            "timestamp": round(self.timestamp, 6),  # ✅ Ensure precision for storage
            "type": self.type.name if self.type else "UNKNOWN",
            "fee": str(self.fee),  # ✅ Convert Decimal to string for safe serialization
            "size": self.size,  # ✅ Include transaction size for analytics
            "hash": self.hash
        }

    def store_transaction(self):
        """
        Store the transaction using PoC, ensuring correct database routing.
        - Uses the correct storage database from Constants.DATABASES.
        """
        try:
            storage_type = Constants.DATABASES.get("mempool", "LMDB")  # ✅ Fetch correct database
            self.poc.store_transaction(self.to_dict(), storage_type)  # ✅ Ensure transaction is stored properly
            logging.info(f"[INFO] ✅ Transaction {self.tx_id} stored successfully in {storage_type}.")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to store transaction {self.tx_id}: {e}")

    def store_utxo(self):
        """
        Store the transaction outputs as UTXOs through PoC.
        - PoC decides whether to store it in SQLite, UnQLite, or LMDB.
        - Ensures proper UTXO tracking for spending and validation.
        """
        try:
            storage_type = Constants.DATABASES.get("utxo", "SQLite")  # ✅ Determine correct UTXO storage
            for idx, output in enumerate(self.outputs):
                utxo_id = f"{self.tx_id}-{idx}"
                utxo_data = {
                    "tx_out_id": self.tx_id,
                    "amount": str(output.amount),  # ✅ Convert Decimal to string for safe storage
                    "script_pub_key": output.script_pub_key,  # ✅ Ensure correct scriptPubKey storage
                    "locked": False,  # ✅ Newly created UTXOs are unlocked
                    "block_index": 0  # ✅ To be updated when included in a block
                }
                self.poc.store_utxo(utxo_id, utxo_data, storage_type)  # ✅ Store in correct database

            logging.info(f"[INFO] ✅ UTXOs stored successfully in {storage_type} for transaction {self.tx_id}")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to store UTXOs for transaction {self.tx_id}: {e}")


            
