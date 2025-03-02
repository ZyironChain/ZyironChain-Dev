import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


from decimal import Decimal
from decimal import Decimal, getcontext
from Zyiron_Chain.transactions.transactiontype import TransactionType

# Set high precision for financial calculations
getcontext().prec = 18
from Zyiron_Chain.blockchain.constants import Constants
from decimal import Decimal, getcontext
import logging
from typing import TYPE_CHECKING



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
    """Fee model with 7% allocation cap, congestion-based fees, and dynamic fee adjustments."""

    def __init__(self, max_supply: Decimal, base_fee_rate=Decimal("0.00015")):
        self.max_supply = max_supply
        self.base_fee_rate = base_fee_rate

        # Allocate funds and set up transaction type manager
        from Zyiron_Chain.transactions.fees import FundsAllocator  # Lazy import
        from Zyiron_Chain.transactions.payment_type import PaymentTypeManager  # Lazy import

        self.allocator = FundsAllocator(max_supply)
        self.type_manager = PaymentTypeManager()

        # Fee structure (Standardized congestion levels)
        self.fee_percentages = {
            "LOW": {"STANDARD": Decimal("0.0012"), "SMART": Decimal("0.0036"), "INSTANT": Decimal("0.006")},
            "MODERATE": {"STANDARD": Decimal("0.0024"), "SMART": Decimal("0.006"), "INSTANT": Decimal("0.012")},
            "HIGH": {"STANDARD": Decimal("0.006"), "SMART": Decimal("0.012"), "INSTANT": Decimal("0.024")},
        }

        # Generate congestion thresholds dynamically
        self.congestion_thresholds = self._generate_interpolated_thresholds()

        # Tax rates
        self.tax_rates = {"LOW": Decimal("0.07"), "MODERATE": Decimal("0.05"), "HIGH": Decimal("0.03")}

    def _generate_interpolated_thresholds(self):
        """Generate congestion thresholds dynamically for block sizes 1-10 using linear interpolation."""
        base_thresholds = {
            1: {"STANDARD": [12000, 60000], "SMART": [6000, 30000], "INSTANT": [3000, 15000]},
            5: {"STANDARD": [60000, 300000], "SMART": [30000, 150000], "INSTANT": [15000, 75000]},
            10: {"STANDARD": [120000, 600000], "SMART": [60000, 300000], "INSTANT": [30000, 150000]},
        }

        interpolated_thresholds = {}
        for block_size in range(1, 11):
            if block_size in base_thresholds:
                interpolated_thresholds[block_size] = base_thresholds[block_size]
            else:
                x1, x2 = (1, 5) if block_size < 5 else (5, 10)
                interpolated_thresholds[block_size] = {
                    tx_type: [
                        round(self._interpolate(block_size, x1, base_thresholds[x1][tx_type][0], x2, base_thresholds[x2][tx_type][0])),
                        round(self._interpolate(block_size, x1, base_thresholds[x1][tx_type][1], x2, base_thresholds[x2][tx_type][1])),
                    ]
                    for tx_type in ["STANDARD", "SMART", "INSTANT"]
                }

        return interpolated_thresholds

    def _interpolate(self, x, x1, y1, x2, y2):
        """Perform linear interpolation to estimate congestion thresholds."""
        return y1 + (y2 - y1) * ((x - x1) / (x2 - x1))

    def get_congestion_level(self, block_size, payment_type, amount):
        """Determine congestion level based on block size, payment type, and transaction amount."""
        if isinstance(payment_type, TransactionType):
            payment_type = payment_type.name.upper()

        if not (1 <= block_size <= 10):
            raise ValueError(f"[ERROR] Unsupported block size: {block_size}. Must be between 1MB and 10MB.")

        valid_payment_types = ["STANDARD", "SMART", "INSTANT", "COINBASE"]
        if payment_type not in valid_payment_types:
            raise ValueError(f"[ERROR] Unsupported payment type: {payment_type}")

        thresholds = self.congestion_thresholds.get(block_size, {}).get(payment_type, [])

        if not thresholds:
            raise KeyError(f"[ERROR] No congestion thresholds for {payment_type} at block size {block_size}")

        if amount < thresholds[0]:
            return "LOW"
        elif thresholds[0] <= amount <= thresholds[1]:
            return "MODERATE"
        return "HIGH"

    def calculate_fee_and_tax(self, block_size, payment_type, amount, tx_size):
        """Calculate transaction fee, tax fee, and fund allocation based on congestion level."""
        if isinstance(payment_type, TransactionType):
            payment_type = payment_type.name

        congestion_level = self.get_congestion_level(block_size, payment_type, amount)
        base_fee = self.calculate_fee(block_size, payment_type, amount, tx_size)

        tax_rate = self.tax_rates.get(congestion_level, Decimal("0"))
        tax_fee = base_fee * tax_rate
        miner_fee = base_fee - tax_fee

        allocation = self.allocator.allocate(tax_fee)

        return {
            "base_fee": base_fee,
            "tax_fee": tax_fee,
            "miner_fee": miner_fee,
            "scaled_tax_rate": round(tax_rate * 100, 2),
            "congestion_level": congestion_level,
            "fund_allocation": allocation,
            "total_fee_percentage": round((base_fee / amount) * 100 if amount > 0 else 0, 2),
            "tax_fee_percentage": round((tax_fee / base_fee) * 100 if base_fee > 0 else 0, 2),
        }

    def calculate_fee(self, block_size, payment_type, amount, tx_size):
        """Calculate transaction fees based on congestion and minimum limits."""
        congestion_level = self.get_congestion_level(block_size, payment_type, amount)
        base_fee_percentage = self.fee_percentages[congestion_level].get(payment_type, Decimal("0"))

        base_fee = max(Decimal(Constants.MIN_TRANSACTION_FEE), base_fee_percentage * Decimal(tx_size))

        return base_fee

    def _calculate_fee(self, transaction):
        """Ensure transaction fees are never negative."""
        input_total = sum(Decimal(inp.amount) for inp in transaction.inputs if hasattr(inp, "amount"))
        output_total = sum(Decimal(out.amount) for out in transaction.outputs if hasattr(out, "amount"))

        fee = input_total - output_total

        return max(Decimal(Constants.MIN_TRANSACTION_FEE), fee)
