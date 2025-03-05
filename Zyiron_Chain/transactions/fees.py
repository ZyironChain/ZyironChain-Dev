import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from decimal import Decimal, getcontext
getcontext().prec = 18
from Zyiron_Chain.transactions.transactiontype import TransactionType
from Zyiron_Chain.blockchain.constants import Constants

# Use minimal print statements for progress/errors (instead of logging)
# Here we assume that "print" statements are our final output mechanism.
# (If you prefer logging, simply replace print() with logging.info()/logging.error())

class FundsAllocator:
    """Funds allocation model with a 4% cap allocated exclusively for smart contract funds."""
    def __init__(self, max_supply: Decimal):
        # Initialize with maximum circulating supply
        self.max_supply = max_supply
        # Cap is now 4% of circulating supply
        self.cap = max_supply * Decimal('0.04')
        # Allocate funds only for smart_contract (100% of cap allocation)
        self.ratios = {
            "smart_contract": Decimal('1.00')
        }
        # Track allocated funds
        self.allocated = {
            "smart_contract": Decimal('0')
        }
        print("[FundsAllocator.__init__] Initialized with cap =", self.cap)

    def allocate(self, tax_fee: Decimal) -> dict:
        """
        Allocate funds while respecting the 4% cap.
        Returns a dictionary with the allocated amount for smart_contract.
        """
        total_allocated = self.allocated["smart_contract"]
        remaining_cap = self.cap - total_allocated
        if remaining_cap <= Decimal('0'):
            print("[FundsAllocator.allocate] Allocation cap reached. Returning 0.")
            return {"smart_contract": Decimal('0')}
        allocation = min(tax_fee, remaining_cap)
        self.allocated["smart_contract"] += allocation
        print(f"[FundsAllocator.allocate] Allocated {allocation} to smart_contract fund.")
        return {"smart_contract": allocation}

    def get_allocated_totals(self) -> dict:
        """Return the current allocation total for smart_contract as a percentage of max supply."""
        total_percent = (self.allocated["smart_contract"] / self.max_supply) * Decimal('100')
        print(f"[FundsAllocator.get_allocated_totals] Smart contract allocation is {total_percent}% of max supply.")
        return {"smart_contract": total_percent}


class FeeModel:
    """Fee model with a 4% allocation cap for smart contract funds, congestion-based fees, and dynamic fee adjustments."""
    def __init__(self, max_supply: Decimal, base_fee_rate=Decimal("0.00015")):
        self.max_supply = max_supply
        self.base_fee_rate = base_fee_rate

        # Lazy import FundsAllocator and PaymentTypeManager
        from Zyiron_Chain.transactions.fees import FundsAllocator
        from Zyiron_Chain.transactions.payment_type import PaymentTypeManager

        # Initialize the FundsAllocator (now with 4% cap)
        self.allocator = FundsAllocator(max_supply)
        self.type_manager = PaymentTypeManager()

        # Fee structure based on congestion levels (use single hashing throughout)
        self.fee_percentages = {
            "LOW": {"STANDARD": Decimal("0.0012"), "SMART": Decimal("0.0036"), "INSTANT": Decimal("0.006")},
            "MODERATE": {"STANDARD": Decimal("0.0024"), "SMART": Decimal("0.006"), "INSTANT": Decimal("0.012")},
            "HIGH": {"STANDARD": Decimal("0.006"), "SMART": Decimal("0.012"), "INSTANT": Decimal("0.024")},
        }

        # Generate congestion thresholds dynamically
        self.congestion_thresholds = self._generate_interpolated_thresholds()

        # Tax rates remain as set; these determine what fraction of the fee is taken as tax
        self.tax_rates = {"LOW": Decimal("0.07"), "MODERATE": Decimal("0.05"), "HIGH": Decimal("0.03")}
        print("[FeeModel.__init__] FeeModel initialized with base fee rate =", self.base_fee_rate)

    def _generate_interpolated_thresholds(self):
        """
        Generate congestion thresholds dynamically for block sizes 1-10 using linear interpolation.
        Returns a dictionary mapping block sizes to threshold ranges per payment type.
        """
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
                # Use linear interpolation between known points
                x1, x2 = (1, 5) if block_size < 5 else (5, 10)
                interpolated_thresholds[block_size] = {
                    tx_type: [
                        round(self._interpolate(block_size, x1, base_thresholds[x1][tx_type][0], x2, base_thresholds[x2][tx_type][0])),
                        round(self._interpolate(block_size, x1, base_thresholds[x1][tx_type][1], x2, base_thresholds[x2][tx_type][1])),
                    ]
                    for tx_type in ["STANDARD", "SMART", "INSTANT"]
                }
        print("[FeeModel._generate_interpolated_thresholds] Generated thresholds:", interpolated_thresholds)
        return interpolated_thresholds

    def _interpolate(self, x, x1, y1, x2, y2):
        """Perform linear interpolation to estimate congestion thresholds."""
        return y1 + (y2 - y1) * ((x - x1) / (x2 - x1))

    def get_congestion_level(self, block_size, payment_type, amount):
        """
        Determine the congestion level ('LOW', 'MODERATE', 'HIGH') based on block size, payment type, and transaction amount.
        """
        if isinstance(payment_type, TransactionType):
            payment_type = payment_type.name.upper()
        if not (1 <= block_size <= 10):
            raise ValueError(f"[FeeModel.get_congestion_level] ERROR: Unsupported block size: {block_size}. Must be between 1 and 10.")
        valid_payment_types = ["STANDARD", "SMART", "INSTANT", "COINBASE"]
        if payment_type not in valid_payment_types:
            raise ValueError(f"[FeeModel.get_congestion_level] ERROR: Unsupported payment type: {payment_type}")
        thresholds = self.congestion_thresholds.get(block_size, {}).get(payment_type, [])
        if not thresholds:
            raise KeyError(f"[FeeModel.get_congestion_level] ERROR: No congestion thresholds for {payment_type} at block size {block_size}")
        if amount < thresholds[0]:
            return "LOW"
        elif thresholds[0] <= amount <= thresholds[1]:
            return "MODERATE"
        return "HIGH"

    def calculate_fee_and_tax(self, block_size, payment_type, amount, tx_size):
        """
        Calculate the transaction fee, tax fee, miner fee, and fund allocation based on congestion level.
        Returns a dictionary with all computed values.
        """
        if isinstance(payment_type, TransactionType):
            payment_type = payment_type.name
        congestion_level = self.get_congestion_level(block_size, payment_type, amount)
        base_fee = self.calculate_fee(block_size, payment_type, amount, tx_size)
        tax_rate = self.tax_rates.get(congestion_level, Decimal("0"))
        tax_fee = base_fee * tax_rate
        miner_fee = base_fee - tax_fee
        allocation = self.allocator.allocate(tax_fee)
        result = {
            "base_fee": base_fee,
            "tax_fee": tax_fee,
            "miner_fee": miner_fee,
            "scaled_tax_rate": round(tax_rate * 100, 2),
            "congestion_level": congestion_level,
            "fund_allocation": allocation,
            "total_fee_percentage": round((base_fee / amount) * 100 if amount > 0 else 0, 2),
            "tax_fee_percentage": round((tax_fee / base_fee) * 100 if base_fee > 0 else 0, 2),
        }
        print("[FeeModel.calculate_fee_and_tax] Computed fee and tax:", result)
        return result

    def calculate_fee(self, block_size, payment_type, amount, tx_size):
        """
        Calculate the transaction fee based on block size, payment type, transaction amount, and transaction size.
        Ensures that fees do not fall below the minimum fee defined in Constants.
        """
        congestion_level = self.get_congestion_level(block_size, payment_type, amount)
        base_fee_percentage = self.fee_percentages[congestion_level].get(payment_type, Decimal("0"))
        fee = max(Decimal(Constants.MIN_TRANSACTION_FEE), base_fee_percentage * Decimal(tx_size))
        print(f"[FeeModel.calculate_fee] For block_size {block_size}, payment_type {payment_type}, tx_size {tx_size}, fee = {fee}")
        return fee

    def _calculate_fee(self, transaction):
        """
        Calculate the fee for a given transaction ensuring it is not negative.
        """
        input_total = sum(Decimal(inp.amount) for inp in transaction.inputs if hasattr(inp, "amount"))
        output_total = sum(Decimal(out.amount) for out in transaction.outputs if hasattr(out, "amount"))
        fee = input_total - output_total
        calculated_fee = max(Decimal(Constants.MIN_TRANSACTION_FEE), fee)
        print(f"[FeeModel._calculate_fee] Calculated fee: {calculated_fee}")
        return calculated_fee
