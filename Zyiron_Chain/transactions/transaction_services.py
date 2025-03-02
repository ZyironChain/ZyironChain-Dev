import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from decimal import Decimal
from Zyiron_Chain.transactions.transactiontype import TransactionType

from typing import Dict, List
from Zyiron_Chain.transactions.Blockchain_transaction import  TransactionFactory
from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.transactions.txin import TransactionIn
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.coinbase import CoinbaseTx




class TransactionService:
    
    def _calculate_fees(self, tx_type: TransactionType, inputs: List[Dict], outputs: List[Dict]) -> Decimal:
        """Proper SHA3-384-based size calculation and fee computation"""
        from Zyiron_Chain.transactions.fees import FeeModel  # Lazy import
        from Zyiron_Chain.blockchain.constants import Constants
        from Zyiron_Chain.blockchain.utils.hashing import Hashing  # Import Hashing

        # Serialize transaction components
        input_data = "".join(f"{i['tx_id']}{i['amount']}" for i in inputs)
        output_data = "".join(f"{o['address']}{o['amount']}" for o in outputs)

        # Calculate actual byte size
        tx_size = len(input_data.encode()) + len(output_data.encode())

        # Create verification hash using double hash (sha3_384)
        verification_hash = Hashing.hash((input_data + output_data).encode())  # Use Hashing.hash here
        
        # Initialize FeeModel with current network parameters
        fee_model = FeeModel(max_supply=Constants.MAX_SUPPLY)
        
        # Calculate and return fee using the model
        return fee_model.calculate_fee(
            block_size=Constants.MAX_BLOCK_SIZE_BYTES,  # Or get dynamic block size
            payment_type=tx_type.name,
            amount=sum(Decimal(i["amount"]) for i in inputs),
            tx_size=tx_size
        )


    def prepare_transaction(self,
                          tx_type: TransactionType,
                          inputs: List[Dict],
                          outputs: List[Dict],
                          metadata: Dict = None) -> Dict:
        """Prepares a transaction and calculates fees."""
        
        # Validate transaction structure
        if not self._validate_io_sum(inputs, outputs):
            raise ValueError("Input/output mismatch")

        # Calculate fees
        fee = self._calculate_fees(tx_type, inputs, outputs)
        
        # Prepare final transaction using TransactionFactory
        tx = TransactionFactory.create_transaction(tx_type, inputs, outputs)
        
        # Allocate funds from the fee model
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
        """Check that the sum of inputs is greater than or equal to the sum of outputs."""
        input_sum = sum(Decimal(inp["amount"]) for inp in inputs)
        output_sum = sum(Decimal(out["amount"]) for out in outputs)
        return input_sum >= output_sum