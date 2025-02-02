import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))



from decimal import Decimal, getcontext
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager, TransactionType
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
# Set high precision for financial calculations
getcontext().prec = 18

from decimal import Decimal, getcontext

class FundsAllocator:
    """Funds allocation model with 7% cap on circulating supply"""
    def __init__(self, max_supply: Decimal):
        # Initialize with maximum circulating supply
        self.max_supply = max_supply
        self.cap = max_supply * Decimal('0.07')  # 7% of circulating supply
        
        # Allocation ratios (sums to 7%)
        self.ratios = {
            "smart_contract": Decimal('0.03'),  # 3%
            "governance": Decimal('0.02'),      # 2%
            "network_development": Decimal('0.02')  # 2%
        }
        
        # Track allocated funds
        self.allocated = {
            "smart_contract": Decimal('0'),
            "governance": Decimal('0'),
            "network_development": Decimal('0')
        }

    def allocate(self, tax_fee: Decimal) -> dict:
        """
        Allocate funds while respecting the 7% cap.
        Returns the actual allocated amounts.
        """
        # Check if allocation would exceed the cap
        total_allocated = sum(self.allocated.values())
        remaining_cap = self.cap - total_allocated
        
        if remaining_cap <= Decimal('0'):
            return {k: Decimal('0') for k in self.ratios.keys()}
        
        # Calculate allocations
        allocations = {}
        for fund, ratio in self.ratios.items():
            allocation = min(tax_fee * ratio, remaining_cap * ratio)
            allocations[fund] = allocation
            self.allocated[fund] += allocation
        
        return allocations

    def get_allocated_totals(self) -> dict:
        """Get current allocation totals as percentages of max supply"""
        return {
            fund: (amount / self.max_supply) * Decimal('100')
            for fund, amount in self.allocated.items()
        }
class FeeModel:
    """Fee model with 7% allocation cap and no burning"""
    def __init__(self, max_supply: Decimal):
        self.allocator = FundsAllocator(max_supply)
        self.type_manager = PaymentTypeManager()
        
        # Fee structure
        self.fee_structure = {
            TransactionType.STANDARD: Decimal('0.0012'),
            TransactionType.SMART: Decimal('0.0036'),
            TransactionType.INSTANT: Decimal('0.006')
        }
        
        # Tax rates (fixed at 7%)
        self.tax_rate = Decimal('0.07')

    def calculate_fee(self, block_size: Decimal, tx_id: str, 
                     amount: Decimal, tx_size: int) -> dict:
        """Calculate fees with allocations capped at 7% of supply"""
        # Determine transaction type
        tx_type = self.type_manager.get_transaction_type(tx_id)
        
        # Calculate base fee
        base_fee = self._calculate_base_fee(tx_type, amount, tx_size)
        
        # Calculate tax and allocations
        tax_fee = base_fee * self.tax_rate
        allocations = self.allocator.allocate(tax_fee)
        
        return {
            "total_fee": float(base_fee),
            "breakdown": {
                "miner_fee": float(base_fee - tax_fee),
                "tax_fee": float(tax_fee),
                "allocations": {k: float(v) for k, v in allocations.items()},
                "tax_rate": float(self.tax_rate)
            },
            "metadata": {
                "allocated_totals": self.allocator.get_allocated_totals(),
                "remaining_cap": float(self.allocator.cap - sum(self.allocator.allocated.values()))
            }
        }

    def _calculate_base_fee(self, tx_type: TransactionType, 
                           amount: Decimal, tx_size: int) -> Decimal:
        """Calculate base fee with size normalization"""
        base_rate = self.fee_structure[tx_type]
        size_factor = Decimal(tx_size) / Decimal(1024)  # Per KB
        return amount * base_rate * size_factor
    




