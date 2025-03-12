import sys
import os
from Zyiron_Chain.transactions.transactiontype import TransactionType
from Zyiron_Chain.blockchain.constants import Constants

class PaymentTypeManager:
    """
    Manages transaction type configurations dynamically using Constants.
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

        # ✅ Automatically extract transaction type prefixes from Constants
        self.TYPE_PREFIXES = {
            tx_type: Constants.TRANSACTION_MEMPOOL_MAP.get(tx_type.name, {}).get("prefixes", [])
            for tx_type in self.TYPE_CONFIG
        }

        print("[PaymentTypeManager.__init__] Initialized TYPE_CONFIG with transaction type details.")
        print("[PaymentTypeManager.__init__] Loaded transaction type prefixes:", self.TYPE_PREFIXES)

    def get_transaction_type(self, tx_id: str) -> TransactionType:
        """
        Determine transaction type based on the transaction ID prefix using Constants.
        Assumes that transaction IDs are generated with single SHA3-384 hashing.
        
        :param tx_id: The transaction ID (expected to be a 96-character hex string).
        :return: The corresponding TransactionType.
        """
        if not isinstance(tx_id, str) or len(tx_id) < 4:
            print("[PaymentTypeManager.get_transaction_type] ❌ Invalid or empty transaction ID provided. Defaulting to STANDARD.")
            return TransactionType.STANDARD  # Default to STANDARD if tx_id is empty or too short

        # ✅ Iterate through transaction types and check for prefix matches
        for tx_type, prefixes in self.TYPE_PREFIXES.items():
            for prefix in prefixes:
                if tx_id.startswith(prefix):
                    print(f"[PaymentTypeManager.get_transaction_type] ✅ Transaction ID '{tx_id}' matched prefix '{prefix}' for type '{tx_type.name}'.")
                    return tx_type

        print(f"[PaymentTypeManager.get_transaction_type] ⚠️ No matching prefix found for transaction ID '{tx_id}'; defaulting to STANDARD.")
        return TransactionType.STANDARD

