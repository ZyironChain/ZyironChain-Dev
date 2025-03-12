import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import struct

from decimal import Decimal, getcontext
getcontext().prec = 18
from Zyiron_Chain.transactions.transactiontype import TransactionType
from Zyiron_Chain.blockchain.constants import Constants

# Use minimal print statements for progress/errors (instead of logging)
# Here we assume that "print" statements are our final output mechanism.
# (If you prefer logging, simply replace print() with logging.info()/logging.error())

from decimal import Decimal
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager

class FundsAllocator:
    """
    Funds allocation model with a strict 4% cap for smart contract funds.
    """

    def __init__(self, max_supply: Decimal):
        """
        Initialize the fund allocator with a 4% cap of the maximum supply.
        """
        self.max_supply = max_supply
        self.cap = max_supply * Decimal('0.04')  # 4% cap
        self.allocated = {"smart_contract": Decimal('0')}
        print(f"[FundsAllocator.__init__] ✅ Initialized with max supply: {max_supply}, cap: {self.cap}")

    def allocate(self, tax_fee: Decimal) -> dict:
        """
        Allocate funds while respecting the 4% cap.
        
        :param tax_fee: The amount to be allocated from the tax fee.
        :return: Dictionary containing the allocated smart contract funds.
        """
        total_allocated = self.allocated["smart_contract"]
        remaining_cap = self.cap - total_allocated

        if remaining_cap <= Decimal('0'):
            print("[FundsAllocator.allocate] ❌ Allocation cap reached. Returning 0.")
            return {"smart_contract": Decimal('0')}

        allocation = min(tax_fee, remaining_cap)
        self.allocated["smart_contract"] += allocation

        print(f"[FundsAllocator.allocate] ✅ Allocated {allocation} to smart_contract fund. "
              f"Remaining cap: {self.cap - self.allocated['smart_contract']}")

        return {"smart_contract": allocation}

    def get_allocated_totals(self) -> dict:
        """
        Return the current allocation total for smart_contract as a percentage of max supply.
        """
        total_percent = (self.allocated["smart_contract"] / self.max_supply) * Decimal('100')
        print(f"[FundsAllocator.get_allocated_totals] 📊 Smart contract allocation is {total_percent}% of max supply.")

        return {"smart_contract": total_percent}



class FeeModel:
    """
    Fee model with a 4% allocation cap for smart contract funds, congestion-based fees, and dynamic fee adjustments.
    Reduced fees by 50% for sustainability.
    """

    def __init__(self, max_supply: Decimal):
        """
        Initializes the Fee Model with congestion-based fees and fund allocation.
        Fetches values from Constants class.
        """
        self.max_supply = max_supply
        self.allocator = FundsAllocator(max_supply)
        self.type_manager = PaymentTypeManager()

        # Fetch payment types dynamically from Constants
        self.payment_types = [payment_type for payment_type in Constants.TRANSACTION_MEMPOOL_MAP.keys() if payment_type != "COINBASE"]
        
        # Fetch minimum transaction fee dynamically from Constants
        self.min_transaction_fee = Decimal(Constants.MIN_TRANSACTION_FEE)  # Dynamically get the min transaction fee

        # Reduced fee percentages by 50%
        self.fee_percentages = {
            "LOW_MODERATE_LOW": {"STANDARD": Decimal("0.0003"), "SMART": Decimal("0.0009"), "INSTANT": Decimal("0.0015")},
            "MODERATE_HIGH_HIGH": {"STANDARD": Decimal("0.0012"), "SMART": Decimal("0.003"), "INSTANT": Decimal("0.006")},
            "LOW_HIGH_MODERATE": {"STANDARD": Decimal("0.0006"), "SMART": Decimal("0.0018"), "INSTANT": Decimal("0.003")},
            "HIGH_MODERATE": {"STANDARD": Decimal("0.0015"), "SMART": Decimal("0.0045"), "INSTANT": Decimal("0.0075")},
            "HIGH": {"STANDARD": Decimal("0.003"), "SMART": Decimal("0.006"), "INSTANT": Decimal("0.012")},
        }

        # Generate congestion thresholds dynamically
        self.congestion_thresholds = self._generate_interpolated_thresholds()

        # Define tax rates for each congestion level
        self.tax_rates = {"LOW": Decimal("0.07"), "MODERATE": Decimal("0.05"), "HIGH": Decimal("0.03")}
        print(f"[FeeModel.__init__] ✅ Initialized with base fee rate from Constants: {self.min_transaction_fee}")

    def _generate_interpolated_thresholds(self):
        """
        Generate congestion thresholds dynamically for block sizes 1-10 using linear interpolation.
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
                x1, x2 = (1, 5) if block_size < 5 else (5, 10)
                interpolated_thresholds[block_size] = {
                    tx_type: [
                        round(self._interpolate(block_size, x1, base_thresholds[x1][tx_type][0], x2, base_thresholds[x2][tx_type][0])),
                        round(self._interpolate(block_size, x1, base_thresholds[x1][tx_type][1], x2, base_thresholds[x2][tx_type][1])),
                    ]
                    for tx_type in self.payment_types  # Excluding COINBASE here
                }
        print(f"[FeeModel._generate_interpolated_thresholds] ✅ Generated thresholds: {interpolated_thresholds}")
        return interpolated_thresholds

    def _interpolate(self, x, x1, y1, x2, y2):
        """Perform linear interpolation to estimate congestion thresholds."""
        return y1 + (y2 - y1) * ((x - x1) / (x2 - x1))

    def get_congestion_level(self, block_size, payment_type, amount):
        """
        Determine the congestion level ('LOW', 'MODERATE', 'HIGH') based on block size, payment type, and transaction amount.
        """
        payment_type = payment_type.upper()
        thresholds = self.congestion_thresholds.get(block_size, {}).get(payment_type, [])

        if not thresholds:
            raise KeyError(f"[FeeModel.get_congestion_level] ❌ No congestion thresholds for {payment_type} at block size {block_size}")

        if amount < thresholds[0]:
            return "LOW"
        elif thresholds[0] <= amount <= thresholds[1]:
            return "MODERATE"
        return "HIGH"

    def calculate_fee_and_tax(self, block_size, payment_type, amount, tx_size):
        """
        Calculate the transaction fee, tax fee, miner fee, and fund allocation based on congestion level.
        """
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
        print(f"[FeeModel.calculate_fee_and_tax] ✅ Computed fee and tax: {result}")
        return result

    def calculate_fee(self, block_size, payment_type, amount, tx_size):
        """
        Calculate the transaction fee based on block size, payment type, transaction amount, and transaction size.
        """
        congestion_level = self.get_congestion_level(block_size, payment_type, amount)
        base_fee_percentage = self.fee_percentages[congestion_level].get(payment_type, Decimal("0"))
        fee = max(Decimal(self.min_transaction_fee), base_fee_percentage * Decimal(tx_size))
        print(f"[FeeModel.calculate_fee] ✅ Block Size: {block_size}, Payment Type: {payment_type}, Fee: {fee}")
        return fee

    def store_fee(self, transaction_id: str, block_hash: str, base_fee: Decimal, tax_fee: Decimal, miner_fee: Decimal, congestion_level: str) -> bool:
        """
        Stores the computed fee data in `fee_stats.lmdb` with full validation and binary serialization.
        """
        try:
            # Validate inputs
            if not isinstance(transaction_id, str) or len(transaction_id) == 0:
                raise ValueError("[FeeModel.store_fee] ❌ Invalid transaction_id format.")
            if not isinstance(block_hash, str) or len(block_hash) != 96:  # SHA3-384 hash length in hex
                raise ValueError("[FeeModel.store_fee] ❌ Invalid block_hash format.")

            # Convert fees to smallest unit using `Constants.COIN`
            base_fee = int(Decimal(base_fee) * Constants.COIN)
            tax_fee = int(Decimal(tax_fee) * Constants.COIN)
            miner_fee = int(Decimal(miner_fee) * Constants.COIN)

            # Generate Binary Key for Storage
            fee_key = f"fee:{transaction_id}".encode("utf-8")

            # Serialize Fee Data in Binary Format
            fee_data = struct.pack(
                ">96s 32s Q Q Q 8s",
                block_hash.encode("utf-8"),
                transaction_id.encode("utf-8"),
                base_fee,
                tax_fee,
                miner_fee,
                congestion_level.encode("utf-8")
            )

            # Store Fee Data in LMDB
            with self.fee_stats_db.env.begin(write=True) as txn:
                txn.put(fee_key, fee_data)

            print(f"[FeeModel.store_fee] ✅ SUCCESS: Stored fee data for transaction {transaction_id} in fee_stats.lmdb.")
            return True

        except Exception as e:
            print(f"[FeeModel.store_fee] ❌ ERROR: Failed to store fee data for transaction {transaction_id}: {e}")
            return False
