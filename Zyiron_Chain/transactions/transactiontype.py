from enum import Enum
from decimal import Decimal

from enum import Enum, auto
from decimal import Decimal
from typing import Dict, Optional

from enum import Enum, auto

class TransactionType(Enum):
    """Defines all supported transaction types"""
    STANDARD = auto()  # Regular peer-to-peer transactions
    SMART = auto()     # Smart contract transactions
    INSTANT = auto()   # Instant settlement transactions
    COINBASE = auto()  # Block reward transactions

class PaymentTypeManager:
    """Manages transaction type configurations"""
    TYPE_CONFIG = {
        TransactionType.STANDARD: {
            "prefixes": [],
            "confirmations": 8,
            "description": "Standard peer-to-peer transactions"
        },
        TransactionType.SMART: {
            "prefixes": ["S-"],
            "confirmations": 5,
            "description": "Smart contract transactions"
        },
        TransactionType.INSTANT: {
            "prefixes": ["PID-", "CID-"],
            "confirmations": 2,
            "description": "Instant settlement transactions"
        },
        TransactionType.COINBASE: {
            "prefixes": ["COINBASE-"],
            "confirmations": 12,  # Coinbase transactions require 12 confirmations
            "description": "Block reward transactions"
        }
    }

    def get_transaction_type(self, tx_id: str) -> TransactionType:
        """Determine transaction type based on ID prefix"""
        for tx_type, config in self.TYPE_CONFIG.items():
            if any(tx_id.startswith(prefix) for prefix in config["prefixes"]):
                return tx_type
        return TransactionType.STANDARD