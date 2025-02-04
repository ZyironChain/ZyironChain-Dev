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
from decimal import Decimal

class FeeModel:
    """Fee model with 7% allocation cap, congestion-based fees, and dynamic fee adjustments"""
    def __init__(self, max_supply: Decimal, base_fee_rate=Decimal('0.00015')):
        self.max_supply = max_supply  # ✅ Ensure max_supply is stored
        self.base_fee_rate = base_fee_rate  # ✅ Introduce base_fee_rate
        self.allocator = FundsAllocator(max_supply)
        self.type_manager = PaymentTypeManager()
        
        # Fee structure
        self.fee_percentages = {
            "Low": {"Standard": Decimal('0.0012'), "Smart": Decimal('0.0036'), "Instant": Decimal('0.006')},
            "Moderate": {"Standard": Decimal('0.0024'), "Smart": Decimal('0.006'), "Instant": Decimal('0.012')},
            "High": {"Standard": Decimal('0.006'), "Smart": Decimal('0.012'), "Instant": Decimal('0.024')},
        }
        
        # Congestion thresholds
        self.congestion_thresholds = {
            1: {"Standard": [12000, 60000], "Smart": [6000, 30000], "Instant": [3000, 15000]},
            5: {"Standard": [60000, 300000], "Smart": [30000, 150000], "Instant": [15000, 75000]},
            10: {"Standard": [120000, 600000], "Smart": [60000, 300000], "Instant": [30000, 150000]},
        }
        
        # Tax rates (dynamic by congestion)
        self.tax_rates = {"Low": Decimal('0.07'), "Moderate": Decimal('0.05'), "High": Decimal('0.03')}
        
    def interpolate_thresholds(self, block_size, payment_type):
        """Linearly scale congestion thresholds for a given block size and payment type."""
        sizes = sorted(self.congestion_thresholds.keys())
        for i in range(len(sizes) - 1):
            lower_size, upper_size = sizes[i], sizes[i + 1]
            if lower_size <= block_size <= upper_size:
                lower_thresholds = self.congestion_thresholds[lower_size][payment_type]
                upper_thresholds = self.congestion_thresholds[upper_size][payment_type]
                
                scale_factor = (block_size - lower_size) / (upper_size - lower_size)
                low_threshold = lower_thresholds[0] + scale_factor * (upper_thresholds[0] - lower_thresholds[0])
                moderate_threshold = lower_thresholds[1] + scale_factor * (upper_thresholds[1] - lower_thresholds[1])
                
                return [low_threshold, moderate_threshold]
        
        if block_size in self.congestion_thresholds:
            return self.congestion_thresholds[block_size][payment_type]
        
        raise ValueError(f"Block size {block_size} is out of supported range.")

    def get_congestion_level(self, block_size, payment_type, amount):
        """Determine the congestion level based on block size, payment type, and transaction amount."""
        if block_size < 1 or block_size > 10:
            raise ValueError(f"Unsupported block size: {block_size}")

        if payment_type not in ["Standard", "Smart", "Instant"]:
            raise ValueError(f"Unsupported payment type: {payment_type}")

        thresholds = self.interpolate_thresholds(block_size, payment_type)
        if amount < thresholds[0]:
            return "Low"
        elif thresholds[0] <= amount <= thresholds[1]:
            return "Moderate"
        else:
            return "High"

    def calculate_fee_and_tax(self, block_size, payment_type, amount, tx_size):
        """Calculate the transaction fee, tax fee, and fund allocation based on congestion level."""
        congestion_level = self.get_congestion_level(block_size, payment_type, amount)
        base_fee = self.calculate_fee(block_size, payment_type, amount, tx_size)
        tax_rate = self.tax_rates[congestion_level]

        tax_fee = base_fee * tax_rate
        miner_fee = base_fee - tax_fee

        smart_contract_fund = tax_fee * (3 / 7)
        governance_fund = tax_fee * (3 / 7)
        network_contribution_fund = tax_fee * (1 / 7)

        total_fee_percentage = (base_fee / amount) * 100 if amount > 0 else 0
        tax_fee_percentage = (tax_fee / base_fee) * 100 if base_fee > 0 else 0

        return {
            "base_fee": base_fee,
            "tax_fee": tax_fee,
            "miner_fee": miner_fee,
            "scaled_tax_rate": round(tax_rate * 100, 2),
            "congestion_level": congestion_level,
            "fund_allocation": {
                "Smart Contract Fund": smart_contract_fund,
                "Governance Fund": governance_fund,
                "Network Contribution Fund": network_contribution_fund,
            },
            "total_fee_percentage": round(total_fee_percentage, 2),
            "tax_fee_percentage": round(tax_fee_percentage, 2),
        }

    def calculate_fee(self, block_size, payment_type, amount, tx_size):
        """Calculate the base transaction fee based on congestion level and payment type."""
        congestion_level = self.get_congestion_level(block_size, payment_type, amount)
        max_percentage = self.fee_percentages[congestion_level][payment_type]

        scaled_percentage = max_percentage * (block_size / 10)

        total_fee = amount * scaled_percentage
        per_byte_fee = total_fee / tx_size
        return tx_size * per_byte_fee
