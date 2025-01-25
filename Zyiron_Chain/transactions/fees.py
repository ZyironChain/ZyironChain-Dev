







from decimal import Decimal

class FeeModel:
    def __init__(self, db_path="fees_db"):
        """
        Initialize the Fee Model with congestion thresholds, fee percentages, and tax rates.
        """
        self.fee_percentages = {
            "Low": {"Standard": 0.0012, "Smart": 0.0036, "Instant": 0.006},
            "Moderate": {"Standard": 0.0024, "Smart": 0.006, "Instant": 0.012},
            "High": {"Standard": 0.006, "Smart": 0.012, "Instant": 0.024},
        }
        self.congestion_thresholds = {
            1: {"Standard": [12000, 60000], "Smart": [6000, 30000], "Instant": [3000, 15000]},
            5: {"Standard": [60000, 300000], "Smart": [30000, 150000], "Instant": [15000, 75000]},
            10: {"Standard": [120000, 600000], "Smart": [60000, 300000], "Instant": [30000, 150000]},
        }
        self.tax_rates = {"Low": 0.07, "Moderate": 0.05, "High": 0.03}  # Dynamic tax rates by congestion




    def map_prefix_to_type(self, tx_id):
        """
        Map transaction prefix to its payment type.
        """
        if tx_id.startswith("PID-") or tx_id.startswith("CID-"):
            return "Instant"
        elif tx_id.startswith("S-"):
            return "Smart"
        else:
            return "Standard"




    def interpolate_thresholds(self, block_size, payment_type):
        """
        Interpolate congestion thresholds for a given block size and payment type.
        """
        sizes = sorted(self.congestion_thresholds.keys())
        for i in range(len(sizes) - 1):
            if sizes[i] <= block_size <= sizes[i + 1]:
                lower_size, upper_size = sizes[i], sizes[i + 1]
                lower_thresholds = self.congestion_thresholds[lower_size][payment_type]
                upper_thresholds = self.congestion_thresholds[upper_size][payment_type]

                low_threshold = lower_thresholds[0] + (
                    (block_size - lower_size) / (upper_size - lower_size)
                ) * (upper_thresholds[0] - lower_thresholds[0])

                moderate_threshold = lower_thresholds[1] + (
                    (block_size - lower_size) / (upper_size - lower_size)
                ) * (upper_thresholds[1] - lower_thresholds[1])

                return [low_threshold, moderate_threshold]

        if block_size in self.congestion_thresholds:
            return self.congestion_thresholds[block_size][payment_type]

        raise ValueError(f"Block size {block_size} is out of supported range.")

    def get_congestion_level(self, block_size, payment_type, amount):
        """
        Determine the congestion level based on block size, payment type, and transaction amount.

        :param block_size: The size of the block in MB.
        :param payment_type: The type of payment, inferred from transaction prefix or explicitly given.
        :param amount: The total transaction amount.
        :return: Congestion level: "Low", "Moderate", or "High".
        """
        if block_size < 1 or block_size > 10:
            raise ValueError(f"Unsupported block size: {block_size}")

        # Map prefixes to payment types for automatic detection
        transaction_prefix_map = {
            "PID-": "Standard",
            "CID-": "Standard",
            "S-": "Smart",
        }

        # Infer payment type if prefix matches
        for prefix, type_name in transaction_prefix_map.items():
            if payment_type.startswith(prefix):
                payment_type = type_name
                break
        else:  # Ensure explicit validation for recognized types
            if payment_type not in ["Standard", "Smart", "Instant"]:
                raise ValueError(f"Unsupported payment type or prefix: {payment_type}")

        thresholds = self.interpolate_thresholds(block_size, payment_type)
        if amount < thresholds[0]:
            return "Low"
        elif thresholds[0] <= amount <= thresholds[1]:
            return "Moderate"
        else:
            return "High"


    def calculate_fee_and_tax(self, block_size, payment_type, amount, tx_size):
        """
        Calculate the transaction fee, tax fee, and fund allocation based on congestion level.
        """
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

    def calculate_fee(self, block_size, tx_id, amount, tx_size, payment_type=None):
        """
        Calculate the base transaction fee based on congestion level and payment type.
        :param block_size: Current block size in MB.
        :param tx_id: Transaction ID to determine the payment type.
        :param amount: Transaction amount.
        :param tx_size: Size of the transaction in bytes.
        :param payment_type: The type of payment (Instant, Smart, Standard).
        :return: Calculated fee for the transaction.
        """
        # If payment_type is not provided, determine it from the tx_id prefix
        if payment_type is None:
            payment_type = self.map_prefix_to_type(tx_id)

        # Validate that the payment type is supported
        if payment_type not in ["Standard", "Smart", "Instant"]:
            raise ValueError(f"Unsupported payment type: {payment_type}")

        # Get congestion level for the transaction
        congestion_level = self.get_congestion_level(block_size, payment_type, amount)

        # Retrieve the maximum fee percentage for the given congestion level and payment type
        max_percentage = self.fee_percentages[congestion_level][payment_type]

        # Scale the percentage based on block size
        scaled_percentage = max_percentage * (block_size / 10)

        # Calculate the total fee and per-byte fee
        total_fee = amount * scaled_percentage

        # Ensure tx_size is not zero to avoid division by zero error
        if tx_size == 0:
            raise ValueError("Transaction size cannot be zero.")

        per_byte_fee = total_fee / tx_size

        # Return the scaled total fee based on the transaction size
        return tx_size * per_byte_fee
    

class MempoolAnalyzer:
    def __init__(self, mempool):
        """
        Initialize the MempoolAnalyzer with a reference to the mempool.
        """
        self.mempool = mempool

    def get_total_transactions(self):
        """Get the total number of transactions in the mempool."""
        return len(self.mempool.transactions)

    def get_total_size(self):
        """Calculate the total size of all transactions in the mempool."""
        return sum(tx["size"] for tx in self.mempool.transactions.values())

    def get_fee_distribution(self):
        """Calculate fee distribution metrics from the mempool."""
        fees_per_byte = [tx["fee"] / tx["size"] for tx in self.mempool.transactions.values()]
        fees_per_byte.sort()
        return {
            "min_fee_per_byte": fees_per_byte[0],
            "median_fee_per_byte": fees_per_byte[len(fees_per_byte) // 2],
            "max_fee_per_byte": fees_per_byte[-1],
        }

    def determine_congestion_level(self, fee_model, block_size):
        """
        Determine the congestion level based on mempool size and block thresholds.
        """
        total_size = self.get_total_size()
        return fee_model.get_congestion_level(block_size, "Standard", total_size)


class PaymentTypes:
    """
    Defines and manages the payment types for the blockchain system.
    """

    def __init__(self, fee_model):
        self.fee_model = fee_model  # Initialize the fee_model
        self.types = {
            "Instant": {
                "prefixes": ["PID-", "CID-"],
                "block_confirmations": (1, 2),  # Minimum and Maximum block confirmations
                "description": "Instant payments requiring 1-2 block confirmations."
            },
            "Smart": {
                "prefixes": ["S-"],
                "block_confirmations": (4, 6),  # Minimum and Maximum block confirmations
                "target_confirmation": 5,  # Target block confirmation
                "description": "Smart payments with programmable logic and confirmation rules."
            },
            "Standard": {
                "prefixes": [],
                "block_confirmations": None,  # No specific block confirmation requirement
                "description": "Standard transactions with no prefixes or additional requirements."
            },
        }

    def get_payment_type(self, tx_id):
        """
        Identify the payment type based on the transaction ID prefix.
        :param tx_id: The transaction ID to analyze.
        :return: A string indicating the payment type or 'Unknown'.
        """
        for payment_type, details in self.types.items():
            if any(tx_id.startswith(prefix) for prefix in details["prefixes"]):
                return payment_type
        return "Standard" if not tx_id.startswith(tuple("PID-" + "CID-")) else "Unknown"

    def get_confirmation_rules(self, payment_type):
        """
        Retrieve the confirmation rules for a specific payment type.
        :param payment_type: The payment type (e.g., "Instant", "Smart").
        :return: A dictionary of confirmation rules.
        """
        return self.types.get(payment_type, {}).get("block_confirmations", "No specific rules")

    def is_valid_payment_type(self, tx_id):
        """
        Check if the given transaction ID corresponds to a known payment type.
        :param tx_id: The transaction ID to validate.
        :return: Boolean indicating validity.
        """
        return self.get_payment_type(tx_id) != "Unknown"


class FundsManager:
    def __init__(self):
        """
        Initialize the FundsManager with fund balances.
        """
        self.funds = {
            "Smart Contract Fund": Decimal("0.0"),
            "Governance Fund": Decimal("0.0"),
            "Network Contribution Fund": Decimal("0.0"),
        }

    def allocate_funds(self, tax_fee):
        """
        Allocate the tax fee to the respective funds.
        :param tax_fee: The total tax fee to distribute.
        """
        self.funds["Smart Contract Fund"] += tax_fee * (3 / 7)
        self.funds["Governance Fund"] += tax_fee * (3 / 7)
        self.funds["Network Contribution Fund"] += tax_fee * (1 / 7)

    def get_fund_balances(self):
        """
        Retrieve the current balances of all funds.
        :return: Dictionary of fund balances.
        """
        return {key: float(value) for key, value in self.funds.items()}

    def reset_funds(self):
        """
        Reset all fund balances to zero.
        """
        for key in self.funds:
            self.funds[key] = Decimal("0.0")



import os
import json

class FeeModelPoC:
    def __init__(self, poc):
        """
        Initialize the FeeModel with PoC for handling fee data routing.
        :param poc: The Point of Contact layer that handles data routing.
        """
        self.poc = poc  # PoC layer for routing fee-related data

    def store_fee_data(self, key, fee_data):
        """
        Store fee-related data in LevelDB.
        :param key: The unique key for the data (e.g., block size or payment type).
        :param fee_data: Dictionary containing the fee data.
        """
        try:
            self.db.Put(key.encode(), json.dumps(fee_data).encode())
            print(f"[INFO] Fee data stored for key: {key}.")
        except Exception as e:
            print(f"[ERROR] Failed to store fee data for key {key}: {e}")

    def get_fee_data(self, key):
        """
        Retrieve fee-related data from LevelDB.
        :param key: The unique key for the data.
        :return: The fee data as a dictionary, or None if not found.
        """
        try:
            data = self.db.Get(key.encode())
            return json.loads(data.decode())
        except KeyError:
            print(f"[INFO] No fee data found for key: {key}.")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to retrieve fee data for key {key}: {e}")
            return None

    def delete_fee_data(self, key):
        """
        Delete fee-related data from LevelDB.
        :param key: The unique key for the data.
        """
        try:
            self.db.Delete(key.encode())
            print(f"[INFO] Fee data deleted for key: {key}.")
        except KeyError:
            print(f"[INFO] No fee data found to delete for key: {key}.")
        except Exception as e:
            print(f"[ERROR] Failed to delete fee data for key {key}: {e}")

    def clear_all_data(self):
        """
        Clear all fee-related data from LevelDB.
        """
        try:
            for key, _ in self.db.RangeIter():
                self.db.Delete(key)
            print("[INFO] All fee data cleared from LevelDB.")
        except Exception as e:
            print(f"[ERROR] Failed to clear LevelDB data: {e}")
