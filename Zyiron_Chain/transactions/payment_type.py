import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.transactions.transactiontype import TransactionType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # These imports will only be available during type-checking (e.g., for linters, IDEs, or mypy)
    from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
    from Zyiron_Chain.transactions.fees import FundsAllocator

class PaymentTypeManager:
    """Manages transaction type configurations dynamically using Constants"""

    def __init__(self):
        # Lazy-load Constants when the class is instantiated
        from Zyiron_Chain.blockchain.constants import Constants
        self.Constants = Constants

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

        # Use the lazily-loaded Constants
        for tx_type, config in self.TYPE_CONFIG.items():
            prefixes = self.Constants.TRANSACTION_MEMPOOL_MAP[tx_type.name]["prefixes"]
            if any(tx_id.startswith(prefix) for prefix in prefixes):
                return tx_type

        return TransactionType.STANDARD  # Default to STANDARD if no match
