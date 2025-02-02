import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager
from decimal import Decimal
from Zyiron_Chain.transactions.transactiontype import TransactionType, PaymentTypeManager
from typing import Dict, List
from Zyiron_Chain.transactions. fees import FeeModel, FundsAllocator
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx, TransactionFactory, sha3_384_hash

class TransactionService:
    def _calculate_fees(self, tx_type: TransactionType, inputs: List[Dict], outputs: List[Dict]) -> Decimal:
        """Proper SHA3-384-based size calculation"""
        # Serialize transaction components
        input_data = "".join(f"{i['tx_id']}{i['amount']}" for i in inputs)
        output_data = "".join(f"{o['address']}{o['amount']}" for o in outputs)
        
        # Calculate actual byte size
        tx_size = len(input_data.encode()) + len(output_data.encode())
        
        # Hash verification data
        verification_hash = sha3_384_hash(input_data + output_data)
        
        return self.fee_model.calculate_fee(
            tx_id=verification_hash[:16],  # Use partial hash as ID
            amount=sum(Decimal(i["amount"]) for i in inputs),
            tx_size=tx_size
        )
    def prepare_transaction(self,
                          tx_type: TransactionType,
                          inputs: List[Dict],
                          outputs: List[Dict],
                          metadata: Dict = None) -> Dict:
        # Validate transaction structure
        if not self._validate_io_sum(inputs, outputs):
            raise ValueError("Input/output mismatch")

        # Calculate fees
        fee = self._calculate_fees(tx_type, inputs, outputs)
        
        # Prepare final transaction
        tx = TransactionFactory.create_transaction(tx_type, inputs, outputs)
        allocation = self.allocator.allocate(Decimal(tx.fee))

        return {
            "transaction": tx,
            "fee_breakdown": {
                "total_fee": float(tx.fee),
                "allocations": {k: float(v) for k, v in allocation.items()}
            },
            "metadata": metadata or {}
        }

    def _validate_io_sum(self, inputs: List[Dict], outputs: List[Dict]) -> bool:
        input_sum = sum(Decimal(inp["amount"]) for inp in inputs)
        output_sum = sum(Decimal(out["amount"]) for out in outputs)
        return input_sum >= output_sum

    def _calculate_fees(self, tx_type: TransactionType, inputs: List[Dict], outputs: List[Dict]) -> Decimal:
        tx_size = len(str(inputs)) + len(str(outputs))  # Simplified size calculation
        amount = sum(Decimal(inp["amount"]) for inp in inputs)
        return self.fee_model.calculate_fee(
            tx_id=TransactionType(tx_type).name,
            amount=amount,
            tx_size=tx_size
        )