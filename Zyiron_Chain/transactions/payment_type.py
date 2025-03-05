import sys
import os
from Zyiron_Chain.transactions.transactiontype import TransactionType
from Zyiron_Chain.blockchain.constants import Constants

class PaymentTypeManager:
    """Manages transaction type configurations dynamically using Constants.
    Uses single-hashing conventions for transaction IDs.
    """

    def __init__(self):
        # Dynamically populate type configuration with descriptions.
        self.TYPE_CONFIG = {
            TransactionType.STANDARD: {
                "description": "Standard peer-to-peer transactions"
            },
            TransactionType.SMART: {
                "description": "Smart contract transactions"
            },
            TransactionType.INSTANT: {
                "description": "Instant settlement transactions"
            },
            TransactionType.COINBASE: {
                "description": "Block reward transactions"
            }
        }
        print("[PaymentTypeManager.__init__] Initialized with TYPE_CONFIG:", self.TYPE_CONFIG)

    def get_transaction_type(self, tx_id: str) -> TransactionType:
        """
        Determine transaction type based on the transaction ID prefix using Constants.
        Assumes that transaction IDs are generated with single SHA3-384 hashing.
        
        :param tx_id: The transaction ID (expected to be a 96-character hex string).
        :return: The corresponding TransactionType.
        """
        if not tx_id:
            print("[PaymentTypeManager.get_transaction_type] No transaction ID provided; defaulting to STANDARD.")
            return TransactionType.STANDARD  # Default to STANDARD if tx_id is empty

        # Check each type's defined prefixes from Constants
        for tx_type, config in self.TYPE_CONFIG.items():
            prefixes = Constants.TRANSACTION_MEMPOOL_MAP.get(tx_type.name, {}).get("prefixes", [])
            for prefix in prefixes:
                if tx_id.startswith(prefix):
                    print(f"[PaymentTypeManager.get_transaction_type] Transaction ID '{tx_id}' matched prefix '{prefix}' for type '{tx_type.name}'.")
                    return tx_type

        print(f"[PaymentTypeManager.get_transaction_type] No matching prefix found for transaction ID '{tx_id}'; defaulting to STANDARD.")
        return TransactionType.STANDARD
