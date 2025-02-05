import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


from decimal import Decimal
from decimal import Decimal, getcontext
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager, TransactionType
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
# Set high precision for financial calculations
getcontext().prec = 18

from decimal import Decimal, getcontext
import logging
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

from decimal import Decimal

class FeeModel:
    """Fee model with 7% allocation cap, congestion-based fees, and dynamic fee adjustments."""
    
class FeeModel:
    """Fee model with 7% allocation cap, congestion-based fees, and dynamic fee adjustments."""
    
    def __init__(self, max_supply: Decimal, base_fee_rate=Decimal('0.00015')):
        self.max_supply = max_supply  # ✅ Ensure max_supply is stored
        self.base_fee_rate = base_fee_rate  # ✅ Introduce base_fee_rate
        self.allocator = FundsAllocator(max_supply)
        self.type_manager = PaymentTypeManager()
        
        # ✅ Fee structure (Standardized congestion levels)
        self.fee_percentages = {
            "LOW": {"STANDARD": Decimal('0.0012'), "SMART": Decimal('0.0036'), "INSTANT": Decimal('0.006')},
            "MODERATE": {"STANDARD": Decimal('0.0024'), "SMART": Decimal('0.006'), "INSTANT": Decimal('0.012')},
            "HIGH": {"STANDARD": Decimal('0.006'), "SMART": Decimal('0.012'), "INSTANT": Decimal('0.024')},
        }
        
        # ✅ Generate congestion thresholds dynamically with interpolation for 2-4, 6-9
        self.congestion_thresholds = self._generate_interpolated_thresholds()

        # ✅ Tax rates (Standardized congestion level names)
        self.tax_rates = {"LOW": Decimal('0.07'), "MODERATE": Decimal('0.05'), "HIGH": Decimal('0.03')}

    def _interpolate(self, x, x1, y1, x2, y2):
        """Perform linear interpolation to estimate congestion thresholds."""
        return y1 + (y2 - y1) * ((x - x1) / (x2 - x1))

    def _generate_interpolated_thresholds(self):
        """Generate congestion thresholds for block sizes 1-10 using linear interpolation."""
        base_thresholds = {
            1: {"STANDARD": [12000, 60000], "SMART": [6000, 30000], "INSTANT": [3000, 15000]},
            5: {"STANDARD": [60000, 300000], "SMART": [30000, 150000], "INSTANT": [15000, 75000]},
            10: {"STANDARD": [120000, 600000], "SMART": [60000, 300000], "INSTANT": [30000, 150000]},
        }
        
        # ✅ Generate interpolated congestion thresholds for block sizes 2-4 and 6-9
        interpolated_thresholds = {}
        for block_size in range(1, 11):
            if block_size in base_thresholds:
                interpolated_thresholds[block_size] = base_thresholds[block_size]
            else:
                # ✅ Determine the closest base sizes (1-5 or 5-10)
                x1, x2 = (1, 5) if block_size < 5 else (5, 10)
                
                # ✅ Interpolate values for each transaction type
                interpolated_thresholds[block_size] = {
                    tx_type: [
                        round(self._interpolate(block_size, x1, base_thresholds[x1][tx_type][0], x2, base_thresholds[x2][tx_type][0])),
                        round(self._interpolate(block_size, x1, base_thresholds[x1][tx_type][1], x2, base_thresholds[x2][tx_type][1]))
                    ]
                    for tx_type in ["STANDARD", "SMART", "INSTANT"]
                }
        
        return interpolated_thresholds
    def interpolate_thresholds(self, block_size, payment_type):
        """Linearly scale congestion thresholds for a given block size and payment type."""
        sizes = sorted(self.congestion_thresholds.keys())

        # ✅ Ensure "STANDARD" exists at all block sizes
        if payment_type not in self.congestion_thresholds[1]:  # Default to smallest block size
            raise KeyError(f"[ERROR] No congestion thresholds found for payment type: {payment_type}")

        for i in range(len(sizes) - 1):
            lower_size, upper_size = sizes[i], sizes[i + 1]
            if lower_size <= block_size <= upper_size:
                lower_thresholds = self.congestion_thresholds[lower_size].get(payment_type)
                upper_thresholds = self.congestion_thresholds[upper_size].get(payment_type)

                # ✅ Handle missing payment type by using closest available
                if lower_thresholds is None or upper_thresholds is None:
                    raise KeyError(f"[ERROR] No congestion thresholds for {payment_type} at block size {block_size}")

                scale_factor = (block_size - lower_size) / (upper_size - lower_size)
                low_threshold = lower_thresholds[0] + scale_factor * (upper_thresholds[0] - lower_thresholds[0])
                moderate_threshold = lower_thresholds[1] + scale_factor * (upper_thresholds[1] - lower_thresholds[1])

                return [low_threshold, moderate_threshold]

        # ✅ If exact match exists, return it
        if block_size in self.congestion_thresholds:
            return self.congestion_thresholds[block_size].get(payment_type, [])

        raise ValueError(f"[ERROR] Block size {block_size} is out of supported range.")


    def get_congestion_level(self, block_size, payment_type, amount):
        """Determine congestion level based on block size, payment type, and transaction amount."""

        # ✅ Convert TransactionType Enum to uppercase string if necessary
        if isinstance(payment_type, TransactionType):
            payment_type = payment_type.name.upper()

        # ✅ Ensure block size is within valid range
        if not (1 <= block_size <= 10):
            raise ValueError(f"[ERROR] Unsupported block size: {block_size}. Must be between 1MB and 10MB.")

        # ✅ Ensure payment type is valid
        valid_payment_types = ["STANDARD", "SMART", "INSTANT", "COINBASE"]
        if payment_type not in valid_payment_types:
            raise ValueError(f"[ERROR] Unsupported payment type: {payment_type}")

        # ✅ Ensure congestion thresholds exist before accessing
        if block_size not in self.congestion_thresholds:
            raise KeyError(f"[ERROR] No congestion thresholds defined for block size: {block_size}")

        # ✅ Interpolate congestion thresholds if missing
        if payment_type not in self.congestion_thresholds[block_size]:
            if 1 <= block_size <= 10:
                self.congestion_thresholds[block_size][payment_type] = self.interpolate_thresholds(block_size, payment_type)
            else:
                raise KeyError(f"[ERROR] No congestion thresholds for payment type: {payment_type} at block size {block_size}")

        # ✅ Retrieve congestion thresholds dynamically
        thresholds = self.congestion_thresholds[block_size][payment_type]

        # ✅ Determine congestion level based on transaction amount
        if amount < thresholds[0]:
            return "LOW"
        elif thresholds[0] <= amount <= thresholds[1]:
            return "MODERATE"
        else:
            return "HIGH"




    def calculate_fee_and_tax(self, block_size, payment_type, amount, tx_size):
        """Calculate the transaction fee, tax fee, and fund allocation based on congestion level."""
        
        # ✅ Ensure `payment_type` is a string, not an Enum
        if isinstance(payment_type, TransactionType):
            payment_type = payment_type.name  

        congestion_level = self.get_congestion_level(block_size, payment_type, amount)
        base_fee = self.calculate_fee(block_size, payment_type, amount, tx_size)
        
        tax_rate = self.tax_rates.get(congestion_level, 0)  # ✅ Ensure valid tax rate
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
            
    def _calculate_fee(self):
        """Calculate transaction fee and ensure it is never negative."""
        try:
            input_total = Decimal(0)

            # ✅ Fetch input UTXOs and sum their amounts
            for inp in self.inputs:
                utxo = self.utxo_manager.get_utxo(inp.tx_out_id)
                if utxo:
                    input_total += Decimal(utxo["amount"])  # ✅ Ensure amount exists
                else:
                    logging.error(f"[ERROR] UTXO {inp.tx_out_id} not found. Setting input_total = 0")
                    return Decimal("0.000001")  # ✅ Prevent negative fee errors

            # ✅ Sum up all output amounts
            output_total = sum(
                Decimal(out.amount) for out in self.outputs if hasattr(out, "amount") and out.amount is not None
            )

            # ✅ Calculate fee as the difference between inputs and outputs
            calculated_fee = input_total - output_total

            # ✅ Ensure fee is never negative; apply a minimum transaction fee
            min_transaction_fee = Decimal("0.000001")  # Minimum fee per transaction

            if calculated_fee < min_transaction_fee:
                logging.warning(f"[WARNING] Transaction {self.tx_id} has a low or negative fee. Adjusting to minimum fee.")
                calculated_fee = min_transaction_fee  # ✅ Apply minimum fee if too low

            return calculated_fee

        except Exception as e:
            logging.error(f"[ERROR] Failed to calculate fee for transaction {self.tx_id}: {e}")
            return Decimal("0.000001")  # ✅ Default to minimum fee in case of an error


        
    def calculate_fee(self, block_size, payment_type, amount, tx_size):
        """Calculate the base transaction fee based on congestion level and payment type."""

        # ✅ Convert Enum type to uppercase string if necessary
        if isinstance(payment_type, TransactionType):
            payment_type = payment_type.name.upper()

        valid_payment_types = ["STANDARD", "SMART", "INSTANT", "COINBASE"]
        if payment_type not in valid_payment_types:
            raise ValueError(f"[ERROR] Unsupported payment type: {payment_type}")

        congestion_level = self.get_congestion_level(block_size, payment_type, amount)

        # ✅ Ensure congestion level exists in fee_percentages
        if congestion_level not in self.fee_percentages:
            raise KeyError(f"[ERROR] Congestion level '{congestion_level}' is missing from fee percentages.")

        if payment_type not in self.fee_percentages[congestion_level]:
            raise KeyError(f"[ERROR] Missing fee percentage for payment type: {payment_type} under congestion level {congestion_level}")

        max_percentage = self.fee_percentages[congestion_level][payment_type]

        # ✅ Ensure minimum base fee is respected
        base_fee = Decimal(self.base_fee_rate) * Decimal(tx_size)

        # ✅ Scale based on block size and congestion level
        scaled_percentage = Decimal(max_percentage) * (Decimal(block_size) / Decimal(10))
        calculated_fee = Decimal(amount) * scaled_percentage

        # ✅ Ensure calculated fee is at least the base fee
        final_fee = max(calculated_fee, base_fee)

        # ✅ Ensure minimum transaction fee is applied
        min_transaction_fee = Decimal("0.000001")  # Minimum fee per transaction
        final_fee = max(final_fee, min_transaction_fee)

        if final_fee < 0:
            logging.error("[ERROR] Transaction fee calculation resulted in a negative fee!")
            final_fee = Decimal("0.000001")  # ✅ Ensure it is not negative

        return final_fee
