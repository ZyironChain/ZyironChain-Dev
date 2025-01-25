class PaymentType:
    """
    Defines and manages the payment types for the blockchain system.
    """

    def __init__(self):
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


class TransactionType:
    """
    Enum-like class to represent transaction types with their properties.
    """
    STANDARD = "Standard"
    SMART = "Smart"
    INSTANT = "Instant"

    @staticmethod
    def get_type_prefix(transaction_id: str):
        """
        Determine the transaction type based on its prefix or format.
        :param transaction_id: The transaction ID to analyze.
        :return: The transaction type as a string.
        """
        # Ensure the transaction_id is a string to prevent errors
        if isinstance(transaction_id, str):
            if transaction_id.startswith("PID-") or transaction_id.startswith("CID-"):
                return TransactionType.INSTANT
            elif transaction_id.startswith("S-"):
                return TransactionType.SMART
            else:
                return TransactionType.STANDARD
        else:
            raise ValueError(f"Invalid transaction ID: {transaction_id}")

    @staticmethod
    def get_confirmation_details(transaction_type: str):
        """
        Get block confirmation requirements for the given transaction type.
        :param transaction_type: The transaction type to analyze.
        :return: Dictionary with confirmation details.
        """
        if transaction_type == TransactionType.INSTANT:
            return {"min": 1, "target": 2}
        elif transaction_type == TransactionType.SMART:
            return {"min": 4, "target": 5, "max": 6}
        elif transaction_type == TransactionType.STANDARD:
            return {"min": 0, "target": None}  # Standard transactions are confirmed in normal blocks
        else:
            raise ValueError(f"Unknown transaction type: {transaction_type}")

    @staticmethod
    def requires_priority_handling(transaction_type: str):
        """
        Determine if a transaction type requires priority handling in the mempool or blockchain.
        :param transaction_type: The transaction type to analyze.
        :return: True if priority handling is required, False otherwise.
        """
        return transaction_type in [TransactionType.INSTANT, TransactionType.SMART]
