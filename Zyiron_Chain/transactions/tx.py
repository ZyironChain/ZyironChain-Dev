import sys
import os





# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)





from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Zyiron_Chain.database.poc import PoC


import time
import hashlib
import logging
from decimal import Decimal
from typing import List, Dict
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.txin import TransactionIn
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
# helper.py
import importlib


from Zyiron_Chain.blockchain.utils.hashing import sha3_384_hash


def get_poc():
    """Lazy import PoC using importlib to avoid circular imports."""
    module = importlib.import_module("Zyiron_Chain.database.poc")
    return getattr(module, "PoC")
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # These imports will only be available during type-checking (e.g., for linters, IDEs, or mypy)
    from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
    from Zyiron_Chain.transactions.fees import FundsAllocator

class Transaction:
    """Represents a standard blockchain transaction"""

    def __init__(self,
                inputs: List["TransactionIn"],
                outputs: List["TransactionOut"],
                tx_id: str = None,
                poc: "PoC" = None,
                utxo_manager=None,
                tx_type: str = "STANDARD"):
        """
        Initialize a transaction object.

        :param inputs: List of transaction inputs.
        :param outputs: List of transaction outputs.
        :param tx_id: (Optional) Unique transaction ID. If not provided, it is auto-generated.
        :param poc: (Optional) PoC instance for blockchain interactions.
        :param utxo_manager: (Optional) UTXO Manager for handling UTXO state.
        :param tx_type: (Optional) Transaction type, e.g. "STANDARD" or "COINBASE".
        """
        # Validate input and output types
        if not all(isinstance(inp, TransactionIn) for inp in inputs):
            raise TypeError("[ERROR] All inputs must be instances of TransactionIn.")
        if not all(isinstance(out, TransactionOut) for out in outputs):
            raise TypeError("[ERROR] All outputs must be instances of TransactionOut.")

        # Assign UTXO Manager, ensuring it exists
        self.utxo_manager = utxo_manager if utxo_manager else self._get_default_utxo_manager()

        # Convert inputs/outputs to proper instances if needed
        self.inputs = [inp if isinstance(inp, TransactionIn) else TransactionIn.from_dict(inp) for inp in inputs]
        self.outputs = [out if isinstance(out, TransactionOut) else TransactionOut.from_dict(out) for out in outputs]

        # Assign timestamp
        self.timestamp = time.time()

        # Set transaction type (allowing caller to override)
        self.type = tx_type.upper()  # e.g. "STANDARD" or "COINBASE"

        # Auto-generate tx_id if missing
        self.tx_id = tx_id if tx_id else self._generate_tx_id()

        # Calculate transaction hash (must come after tx_id and timestamp are set)
        self.hash = self.calculate_hash()

        # Store PoC reference for blockchain interactions
        self.poc = poc if poc else get_poc()

        # Compute transaction size
        self.size = self._calculate_size()

        # Compute transaction fee and enforce minimum fee
        self.fee = max(self._calculate_fee(), Decimal(Constants.MIN_TRANSACTION_FEE))

        logging.info(f"[TRANSACTION] Created new transaction: {self.tx_id}, Type: {self.type}, Fee: {self.fee}, Size: {self.size} bytes")


    def _determine_transaction_type(self, tx_id: str) -> str:
        """Determine transaction type based on ID prefix using Constants."""
        if not tx_id:
            return "STANDARD"  # Default to STANDARD
        for tx_type, config in Constants.TRANSACTION_MEMPOOL_MAP.items():
            if any(tx_id.startswith(prefix) for prefix in config["prefixes"]):
                return tx_type
        return "STANDARD"

    def _generate_tx_id(self) -> str:
        """Generate a unique transaction ID using SHA3-384 hashing and proper prefixing."""
        prefix = Constants.TRANSACTION_MEMPOOL_MAP.get(self.type, {}).get("prefixes", [""])[0]
        # Include timestamp and a random element to ensure uniqueness.
        tx_data = f"{prefix}{self.timestamp}{hashlib.sha3_384(str(time.time()).encode()).hexdigest()}"
        return hashlib.sha3_384(tx_data.encode()).hexdigest()[:24]

    def _get_default_utxo_manager(self):
        """Retrieve the default UTXO manager instance dynamically using Constants."""
        from Zyiron_Chain.transactions.utxo_manager import UTXOManager
        from Zyiron_Chain.database.poc import PoC
        db_type = Constants.DATABASES.get("utxo", "SQLite")
        return UTXOManager(PoC(storage_type=db_type))  # PoC now accepts storage_type

    @classmethod
    def from_dict(cls, data: Dict) -> "Transaction":
        """
        Create a Transaction instance from a dictionary.
        :param data: Dictionary containing transaction data.
        :return: A Transaction instance.
        """
        if not isinstance(data, dict):
            raise TypeError("[ERROR] Input data must be a dictionary.")
        if "inputs" not in data or "outputs" not in data:
            raise ValueError("[ERROR] Transaction dictionary must contain 'inputs' and 'outputs'.")
        inputs = [TransactionIn.from_dict(inp) if isinstance(inp, dict) else inp for inp in data.get("inputs", [])]
        outputs = [TransactionOut.from_dict(out) if isinstance(out, dict) else out for out in data.get("outputs", [])]
        tx_type = data.get("type", "STANDARD")
        return cls(
            tx_id=data.get("tx_id", ""),
            inputs=inputs,
            outputs=outputs,
            tx_type=tx_type
        )


    def _ensure_inputs(self, inputs):
        """Ensure all inputs have required fields and convert to dictionaries."""
        from Zyiron_Chain.transactions.txin import TransactionIn
        if not isinstance(inputs, list):
            raise TypeError("[ERROR] Inputs must be a list.")
        validated_inputs = []
        for inp in inputs:
            try:
                if isinstance(inp, dict):
                    inp = TransactionIn.from_dict(inp)
                if not isinstance(inp, TransactionIn):
                    logging.warning(f"[WARN] Skipping invalid input: {inp}")
                    continue
                validated_inputs.append(inp.to_dict())
            except Exception as e:
                logging.error(f"[ERROR] Failed to process input {inp}: {e}")
        logging.info(f"[TRANSACTION] ✅ Validated {len(validated_inputs)} transaction inputs successfully.")
        return validated_inputs

    def _calculate_size(self) -> int:
        """
        Estimate transaction size based on inputs, outputs, metadata, and enforced limits.
        For non-coinbase transactions, require at least one input and one output.
        For coinbase transactions, only outputs are required.
        """
        if self.type != "COINBASE":
            if not self.inputs or not self.outputs:
                raise ValueError("[ERROR] Transaction must have at least one input and one output.")
        else:
            if not self.outputs:
                raise ValueError("[ERROR] Coinbase transaction must have at least one output.")

        try:
            input_size = sum(len(str(inp.to_dict())) for inp in self.inputs)
            output_size = sum(len(str(out.to_dict())) for out in self.outputs)
            metadata_size = len(self.tx_id) + len(str(self.timestamp)) + len(self.hash)
            total_size = input_size + output_size + metadata_size
            if total_size > Constants.MAX_BLOCK_SIZE_BYTES:
                logging.warning(f"[WARN] Transaction size {total_size} exceeds maximum block size {Constants.MAX_BLOCK_SIZE_BYTES}. Adjusting.")
                total_size = Constants.MAX_BLOCK_SIZE_BYTES
            logging.info(f"[TRANSACTION] ✅ Calculated transaction size: {total_size} bytes")
            return total_size
        except Exception as e:
            logging.error(f"[ERROR] Failed to calculate transaction size: {e}")
            return 0


    def _ensure_outputs(self, outputs):
        """Ensure all outputs have required fields and convert to dictionaries."""
        from Zyiron_Chain.transactions.txout import TransactionOut
        if not isinstance(outputs, list):
            raise TypeError("[ERROR] Outputs must be a list.")
        validated_outputs = []
        for out in outputs:
            try:
                if isinstance(out, dict):
                    out = TransactionOut.from_dict(out)
                if not isinstance(out, TransactionOut):
                    logging.warning(f"[WARN] Skipping invalid output: {out}")
                    continue
                if out.amount <= 0:
                    logging.warning(f"[WARN] Skipping output with non-positive amount: {out.amount}")
                    continue
                validated_outputs.append(out.to_dict())
            except Exception as e:
                logging.error(f"[ERROR] Failed to process output {out}: {e}")
        logging.info(f"[TRANSACTION] ✅ Validated {len(validated_outputs)} transaction outputs successfully.")
        return validated_outputs

    def _calculate_fee(self) -> Decimal:
        """Calculate transaction fee using FeeModel, ensuring it meets the required minimum fee."""
        try:
            # For coinbase transactions, fee is always zero.
            if self.type == "COINBASE":
                logging.info("[INFO] Coinbase Transaction Detected - Fee Set to 0")
                return Decimal("0")
            input_total = Decimal("0")
            output_total = Decimal("0")
            for inp in self.inputs:
                utxo = self.utxo_manager.get_utxo(inp.tx_out_id)
                if utxo and "amount" in utxo:
                    try:
                        input_total += Decimal(utxo["amount"])
                    except (ValueError, TypeError):
                        logging.error(f"[ERROR] Invalid UTXO amount format for {inp.tx_out_id}")
                else:
                    logging.warning(f"[WARNING] Missing UTXO {inp.tx_out_id} - Defaulting to 0")
            for out in self.outputs:
                try:
                    output_total += Decimal(out.amount) if isinstance(out, TransactionOut) else Decimal(out.get("amount", 0))
                except (ValueError, TypeError):
                    logging.error(f"[ERROR] Invalid output amount format for {out}")
                    continue
            fee = input_total - output_total
            if fee < Decimal("0"):
                logging.warning(f"[WARNING] Negative Fee Detected: Adjusting to 0. Input: {input_total}, Output: {output_total}, Fee: {fee}")
                fee = Decimal("0")
            fee_model = self.poc.fee_model
            min_fee = Decimal(Constants.MIN_TRANSACTION_FEE)
            network_fee = fee_model.calculate_fee(
                block_size=Constants.MAX_BLOCK_SIZE_BYTES,
                payment_type=self.type,
                tx_size=self.size
            )
            required_fee = max(min_fee, network_fee)
            if hasattr(self, "rebroadcast") and self.rebroadcast:
                required_fee *= Decimal(Constants.FEE_INCREMENT_FACTOR)
                logging.info(f"[FEE] Transaction is a rebroadcast - Applying fee increase: {required_fee}")
            if fee < required_fee:
                logging.info(f"[FEE] Adjusting fee to the required minimum: {required_fee} (Original Fee: {fee})")
                fee = required_fee
            logging.info(f"[TRANSACTION] ✅ Fee Calculated: {fee} (Input: {input_total}, Output: {output_total}, Required Fee: {required_fee})")
            return fee
        except Exception as e:
            logging.error(f"[ERROR] Failed to calculate transaction fee: {e}")
            return Decimal(Constants.MIN_TRANSACTION_FEE)


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
        """
        from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
        key_manager = KeyManager()
        try:
            if recipient_address.startswith(Constants.ADDRESS_PREFIX):
                script_pub_key = key_manager.get_hashed_public_key(Constants.NETWORK, recipient_address)
            else:
                script_pub_key = key_manager.get_default_public_key(Constants.NETWORK, "miner")
            if script_pub_key:
                return script_pub_key
            else:
                raise ValueError("No valid scriptPubKey found")
        except ValueError:
            logging.warning(f"[WARNING] No valid scriptPubKey found for {recipient_address}, defaulting to recipient address.")
            return recipient_address

    def to_dict(self) -> Dict:
        """Serialize Transaction to a dictionary, ensuring proper data formatting."""
        return {
            "tx_id": self.tx_id,
            "inputs": [inp.to_dict() if isinstance(inp, TransactionIn) else inp for inp in self.inputs],
            "outputs": [out.to_dict() if isinstance(out, TransactionOut) else out for out in self.outputs],
            "timestamp": round(self.timestamp, 6),
            "type": self.type,  # Already a string
            "fee": str(self.fee),
            "size": self.size,
            "hash": self.hash
        }

    def store_transaction(self):
        """
        Store the transaction using PoC, ensuring correct database routing.
        """
        try:
            storage_type = Constants.DATABASES.get("mempool", "LMDB")
            self.poc.store_transaction(self.to_dict(), storage_type)
            logging.info(f"[INFO] ✅ Transaction {self.tx_id} stored successfully in {storage_type}.")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to store transaction {self.tx_id}: {e}")

    def store_utxo(self):
        """
        Store the transaction outputs as UTXOs through PoC.
        """
        try:
            storage_type = Constants.DATABASES.get("utxo", "SQLite")
            for idx, output in enumerate(self.outputs):
                utxo_id = f"{self.tx_id}-{idx}"
                utxo_data = {
                    "tx_out_id": self.tx_id,
                    "amount": str(output.amount),
                    "script_pub_key": output.script_pub_key,
                    "locked": False,
                    "block_index": 0
                }
                self.poc.store_utxo(utxo_id, utxo_data, storage_type)
            logging.info(f"[INFO] ✅ UTXOs stored successfully in {storage_type} for transaction {self.tx_id}")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to store UTXOs for transaction {self.tx_id}: {e}")