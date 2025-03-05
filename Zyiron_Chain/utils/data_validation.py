import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import hashlib
import time
from decimal import Decimal
from typing import Any, Dict, List
import json 
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.txin import TransactionIn
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.utils.hashing import Hashing

class Validation:
    """
    Handles all data integrity and consistency checks across transaction data types.
    Ensures that data formats, signatures, and fee calculations meet protocol standards.
    Detailed print statements are used to trace internal state and errors.
    All conversions use single SHA3-384 hashing and the constants from Constants.
    """

    def __init__(self):
        print("[VALIDATION] Initialized the Validation class for data integrity checks.")

    def validate_transaction_in(self, tx_in: TransactionIn) -> bool:
        """
        Validate a transaction input ensuring that tx_out_id and script_sig follow protocol.
        Uses single SHA3-384 hashing for script_sig validation.
        """
        print(f"[VALIDATION] Validating TransactionIn with tx_out_id: {tx_in.tx_out_id}")
        if not isinstance(tx_in.tx_out_id, str) or not tx_in.tx_out_id.strip():
            print("[VALIDATION ERROR] tx_out_id must be a non-empty string.")
            return False

        if not isinstance(tx_in.script_sig, str) or not tx_in.script_sig.strip():
            print("[VALIDATION ERROR] script_sig must be a non-empty string.")
            return False

        # Check if script_sig is a valid SHA3-384 hash (96 hex characters)
        script_sig_lower = tx_in.script_sig.lower()
        if len(script_sig_lower) != Constants.SHA3_384_HASH_SIZE or \
           not all(c in "0123456789abcdef" for c in script_sig_lower):
            print(f"[VALIDATION ERROR] script_sig format invalid: {tx_in.script_sig}")
            return False

        print(f"[VALIDATION] TransactionIn with tx_out_id {tx_in.tx_out_id} validated successfully.")
        return True

    def validate_transaction_out(self, tx_out: TransactionOut) -> bool:
        """
        Validate a transaction output ensuring that script_pub_key is valid and amount meets minimum.
        """
        print(f"[VALIDATION] Validating TransactionOut with script_pub_key: {tx_out.script_pub_key} and amount: {tx_out.amount}")
        if not isinstance(tx_out.script_pub_key, str) or not tx_out.script_pub_key.strip():
            print("[VALIDATION ERROR] script_pub_key must be a non-empty string.")
            return False

        try:
            amount = Decimal(tx_out.amount)
        except Exception as e:
            print(f"[VALIDATION ERROR] Failed to parse amount: {e}")
            return False

        if amount < Constants.COIN:
            print(f"[VALIDATION ERROR] TransactionOut amount {amount} is below the minimum unit {Constants.COIN}.")
            return False

        print(f"[VALIDATION] TransactionOut validated successfully.")
        return True

    def validate_coinbase_transaction(self, tx: Any) -> bool:
        """
        Validate a coinbase transaction:
          - Must be an instance of the Coinbase transaction class.
          - Should have no inputs.
          - Must have exactly one output.
          - Fee must be zero.
          - tx_id must be a single SHA3-384 hash.
        """
        print(f"[VALIDATION] Validating Coinbase transaction with tx_id: {tx.tx_id}")
        from Zyiron_Chain.transactions.coinbase import CoinbaseTx  # Lazy import

        if not isinstance(tx, CoinbaseTx):
            print("[VALIDATION ERROR] Transaction is not a valid CoinbaseTx instance.")
            return False

        if len(tx.inputs) != 0:
            print("[VALIDATION ERROR] Coinbase transaction must have no inputs.")
            return False

        if len(tx.outputs) != 1:
            print("[VALIDATION ERROR] Coinbase transaction must have exactly one output.")
            return False

        if tx.fee != Decimal("0"):
            print("[VALIDATION ERROR] Coinbase transaction fee must be zero.")
            return False

        # Verify that the tx_id is generated using a single SHA3-384 hash.
        computed_tx_id = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()
        if computed_tx_id != tx.tx_id:
            print("[VALIDATION ERROR] Coinbase transaction tx_id does not match the expected single SHA3-384 hash format.")
            return False

        print("[VALIDATION] Coinbase transaction validated successfully.")
        return True

    def validate_transaction_structure(self, tx: Any) -> bool:
        """
        Validate the overall structure of a transaction:
          - Ensure it has a non-empty tx_id.
          - Ensure inputs and outputs are lists and validate each element.
          - Check that the calculated hash matches the stored hash.
        """
        print(f"[VALIDATION] Validating structure of transaction with tx_id: {tx.tx_id}")

        if not hasattr(tx, "tx_id") or not isinstance(tx.tx_id, str) or not tx.tx_id.strip():
            print("[VALIDATION ERROR] Transaction must have a valid, non-empty tx_id.")
            return False

        if not isinstance(tx.inputs, list) or not isinstance(tx.outputs, list):
            print("[VALIDATION ERROR] Transaction inputs and outputs must be lists.")
            return False

        for inp in tx.inputs:
            if not self.validate_transaction_in(inp):
                print(f"[VALIDATION ERROR] Transaction input {inp} failed validation.")
                return False

        for out in tx.outputs:
            if not self.validate_transaction_out(out):
                print(f"[VALIDATION ERROR] Transaction output {out} failed validation.")
                return False

        # Recalculate the hash and compare with stored hash using single SHA3-384
        input_data = "".join(i.tx_out_id for i in tx.inputs)
        output_data = "".join(o.script_pub_key + str(o.amount) for o in tx.outputs)
        tx_string = f"{tx.tx_id}{tx.timestamp}{input_data}{output_data}"
        recalculated_hash = Hashing.hash(tx_string.encode())
        if recalculated_hash != tx.hash:
            print(f"[VALIDATION ERROR] Transaction hash mismatch. Calculated: {recalculated_hash}, Stored: {tx.hash}")
            return False

        print(f"[VALIDATION] Transaction {tx.tx_id} structure validated successfully.")
        return True

    def validate_fee(self, tx: Any) -> bool:
        """
        Validate that the transaction fee is sufficient:
          - Recalculate fee based on inputs and outputs.
          - Compare against the minimum fee required.
        """
        print(f"[VALIDATION] Validating fee for transaction {tx.tx_id}")
        input_total = Decimal("0")
        output_total = Decimal("0")

        for inp in tx.inputs:
            utxo_amount = Decimal("0")
            try:
                utxo_amount = Decimal(getattr(inp, "amount", "0"))
            except Exception as e:
                print(f"[VALIDATION ERROR] Could not parse input amount: {e}")
            input_total += utxo_amount

        for out in tx.outputs:
            try:
                output_total += Decimal(out.amount) if hasattr(out, "amount") else Decimal(out.get("amount", "0"))
            except Exception as e:
                print(f"[VALIDATION ERROR] Could not parse output amount: {e}")

        calculated_fee = input_total - output_total
        print(f"[VALIDATION] Calculated fee: {calculated_fee} (Inputs: {input_total}, Outputs: {output_total})")
        required_fee = max(Decimal(Constants.MIN_TRANSACTION_FEE), calculated_fee)
        if calculated_fee < required_fee:
            print(f"[VALIDATION ERROR] Insufficient fee. Required: {required_fee}, Provided: {calculated_fee}")
            return False

        print(f"[VALIDATION] Fee validated successfully for transaction {tx.tx_id}.")
        return True

    def validate_transaction(self, tx: Any) -> bool:
        """
        Comprehensive validation of a transaction:
          - Validate structure.
          - If coinbase, run coinbase-specific validation.
          - Validate fee.
        """
        print(f"[VALIDATION] Starting full validation for transaction {tx.tx_id} of type {tx.type}")
        if tx.type == "COINBASE":
            return self.validate_coinbase_transaction(tx)
        
        if not self.validate_transaction_structure(tx):
            print(f"[VALIDATION ERROR] Structure validation failed for transaction {tx.tx_id}")
            return False

        if not self.validate_fee(tx):
            print(f"[VALIDATION ERROR] Fee validation failed for transaction {tx.tx_id}")
            return False

        print(f"[VALIDATION] Transaction {tx.tx_id} passed all validation checks.")
        return True

    def validate_json_data(self, data: Any) -> bool:
        """
        Validate that data can be serialized to JSON and back without loss.
        This helps ensure consistency in data conversions.
        """
        print("[VALIDATION] Validating JSON data integrity.")
        try:
            json_str = json.dumps(data, sort_keys=True)
            new_data = json.loads(json_str)
            if new_data != data:
                print("[VALIDATION ERROR] Data mismatch after JSON serialization and deserialization.")
                return False
            print("[VALIDATION] JSON data integrity validated successfully.")
            return True
        except Exception as e:
            print(f"[VALIDATION ERROR] JSON validation failed: {e}")
            return False
