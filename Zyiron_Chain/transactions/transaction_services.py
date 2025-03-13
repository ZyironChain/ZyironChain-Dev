import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from decimal import Decimal
from Zyiron_Chain.transactions.transactiontype import TransactionType
from typing import Dict, List
from Zyiron_Chain.transactions.Blockchain_transaction import TransactionFactory
from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.transactions.txin import TransactionIn
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.coinbase import CoinbaseTx
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.hashing import Hashing
import time


from decimal import Decimal
from typing import List, Dict
import json

class TransactionService:
    """
    TransactionService handles transaction preparation and fee calculation.
    - Uses single SHA3-384 hashing for all hash computations.
    - Utilizes Constants for all configurable parameters.
    - Reports detailed status via print statements.
    """

    def _calculate_fees(self, tx_type: TransactionType, inputs: List[Dict], outputs: List[Dict]) -> Decimal:
        """
        Calculate the transaction fee using single SHA3-384 hashing and current network constants.
        
        Steps:
        - Serialize input and output data to bytes.
        - Compute the total byte size.
        - Generate a verification hash with a single hash.
        - Initialize the FeeModel using Constants.
        - Return the fee computed by the FeeModel.
        """
        if not inputs or not outputs:
            print("[TransactionService._calculate_fees] ERROR: Inputs or outputs cannot be empty.")
            raise ValueError("Inputs and outputs are required for fee calculation.")

        # ✅ Convert input and output data to strings for hashing
        input_data = "".join(f"{i['tx_id']}{i['amount']}" for i in inputs if "tx_id" in i and "amount" in i)
        output_data = "".join(f"{o['address']}{o['amount']}" for o in outputs if "address" in o and "amount" in o)

        tx_size = len(input_data.encode("utf-8")) + len(output_data.encode("utf-8"))
        print(f"[TransactionService._calculate_fees] INFO: Calculated transaction size is {tx_size} bytes.")

        # ✅ Compute verification hash
        combined_data = input_data + output_data
        verification_hash = Hashing.hash(combined_data.encode("utf-8"))
        print(f"[TransactionService._calculate_fees] INFO: Verification hash computed as {verification_hash.hex()}.")

        from Zyiron_Chain.transactions.fees import FeeModel  # Lazy import
        fee_model = FeeModel(max_supply=Constants.MAX_SUPPLY)

        print(f"[TransactionService._calculate_fees] INFO: FeeModel initialized with max_supply {Constants.MAX_SUPPLY}.")

        # ✅ Compute transaction fee
        try:
            fee = fee_model.calculate_fee(
                block_size=Constants.MAX_BLOCK_SIZE_BYTES,
                payment_type=tx_type.name,
                amount=sum(Decimal(i["amount"]) for i in inputs if "amount" in i),
                tx_size=tx_size
            )
        except Exception as e:
            print(f"[TransactionService._calculate_fees] ERROR: Failed to calculate fee: {e}")
            raise ValueError("Fee calculation error.")

        print(f"[TransactionService._calculate_fees] INFO: Calculated fee is {fee}.")
        return fee

    def prepare_transaction(self,
                            tx_type: TransactionType,
                            inputs: List[Dict],
                            outputs: List[Dict],
                            metadata: Dict = None) -> Dict:
        """
        Prepare a transaction by validating inputs/outputs, calculating fees,
        creating the transaction using TransactionFactory, and allocating funds.
        """
        print("[TransactionService.prepare_transaction] INFO: Starting transaction preparation.")

        # ✅ Ensure inputs/outputs are valid
        if not self._validate_io_sum(inputs, outputs):
            print("[TransactionService.prepare_transaction] ERROR: Input/output sum validation failed.")
            raise ValueError("Input/output mismatch: Inputs must be >= Outputs.")

        # ✅ Compute fees safely
        fee = self._calculate_fees(tx_type, inputs, outputs)
        print(f"[TransactionService.prepare_transaction] INFO: Fee calculated as {fee}.")

        # ✅ Create transaction object
        try:
            tx = TransactionFactory.create_transaction(tx_type, inputs, outputs)
        except Exception as e:
            print(f"[TransactionService.prepare_transaction] ERROR: Failed to create transaction: {e}")
            raise ValueError("Transaction creation error.")

        print(f"[TransactionService.prepare_transaction] INFO: Transaction created with tx_id {tx.tx_id}.")

        # ✅ Allocate transaction fees
        try:
            allocation = self.fee_model.allocator.allocate(Decimal(tx.fee))
            print(f"[TransactionService.prepare_transaction] INFO: Fund allocation for fee: {allocation}")
        except Exception as e:
            print(f"[TransactionService.prepare_transaction] ERROR: Failed to allocate transaction fee: {e}")
            raise ValueError("Fee allocation error.")

        # ✅ Construct result dictionary
        result = {
            "transaction": tx.to_dict() if hasattr(tx, "to_dict") else tx,
            "fee_breakdown": {
                "total_fee": float(tx.fee),
                "allocations": {k: float(v) for k, v in allocation.items()}
            },
            "metadata": metadata or {}
        }

        print("[TransactionService.prepare_transaction] INFO: Transaction preparation complete.")
        return result

    def _validate_io_sum(self, inputs: List[Dict], outputs: List[Dict]) -> bool:
        """
        Validate that the sum of inputs is greater than or equal to the sum of outputs.
        Returns True if valid, else False.
        """
        if not inputs or not outputs:
            print("[TransactionService._validate_io_sum] ERROR: Inputs or outputs cannot be empty.")
            return False

        try:
            input_sum = sum(Decimal(inp["amount"]) for inp in inputs if "amount" in inp)
            output_sum = sum(Decimal(out["amount"]) for out in outputs if "amount" in out)
        except Exception as e:
            print(f"[TransactionService._validate_io_sum] ERROR: Invalid transaction data: {e}")
            return False

        print(f"[TransactionService._validate_io_sum] INFO: Total inputs = {input_sum}, Total outputs = {output_sum}.")
        return input_sum >= output_sum
