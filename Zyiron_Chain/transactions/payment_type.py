from Zyiron_Chain.transactions.transactiontype import TransactionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # These imports will only be available during type-checking (e.g., for linters, IDEs, or mypy)
    from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
    from Zyiron_Chain.transactions.fees import FundsAllocator

from Zyiron_Chain.blockchain.constants import Constants  # ✅ Import Constants directly

class PaymentTypeManager:
    """Manages transaction type configurations dynamically using Constants"""

    def __init__(self):
        # The TYPE_CONFIG is dynamically populated using Constants
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

    def get_transaction_type(self, tx_id: str) -> TransactionType:
        """Determine transaction type based on ID prefix using Constants"""
        if not tx_id:
            return TransactionType.STANDARD  # Default to STANDARD

        # Dynamically check the prefixes using Constants
        for tx_type, config in self.TYPE_CONFIG.items():
            prefixes = Constants.TRANSACTION_MEMPOOL_MAP.get(tx_type.name, {}).get("prefixes", [])
            if any(tx_id.startswith(prefix) for prefix in prefixes):
                return tx_type

        return TransactionType.STANDARD  # Default to STANDARD if no match
