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
        Calculate the transaction fee using the FeeModel.
        
        Steps:
        - Fetch fee parameters from FeeModel.
        - Compute the fee based on the current congestion level.
        - Allocate funds dynamically to the smart contract pool if needed.
        """
        if not inputs or not outputs:
            print("[TransactionService._calculate_fees] ERROR: Inputs or outputs cannot be empty.")
            raise ValueError("Inputs and outputs are required for fee calculation.")

        # ✅ Get total input and output amounts
        total_input_amount = sum(Decimal(i["amount"]) for i in inputs if "amount" in i)
        total_output_amount = sum(Decimal(o["amount"]) for o in outputs if "amount" in o)

        if total_input_amount < total_output_amount:
            print("[TransactionService._calculate_fees] ERROR: Input amount must be >= Output amount.")
            raise ValueError("Input amount must be greater than or equal to output amount.")

        from Zyiron_Chain.transactions.fees import FeeModel  # Lazy import
        fee_model = FeeModel(max_supply=Constants.MAX_SUPPLY)

        print(f"[TransactionService._calculate_fees] INFO: FeeModel initialized with max_supply {Constants.MAX_SUPPLY}.")

        # ✅ Compute transaction fee using FeeModel
        try:
            fee_details = fee_model.calculate_fee_and_tax(
                block_size=Constants.MAX_BLOCK_SIZE_MB,
                payment_type=tx_type.name,
                amount=total_input_amount,
                tx_size=0  # ✅ No longer using transaction size for fee calculation
            )

            fee = fee_details["base_fee"]
            print(f"[TransactionService._calculate_fees] INFO: Computed transaction fee is {fee}.")

        except Exception as e:
            print(f"[TransactionService._calculate_fees] ERROR: Failed to calculate fee: {e}")
            raise ValueError("Fee calculation error.")

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
