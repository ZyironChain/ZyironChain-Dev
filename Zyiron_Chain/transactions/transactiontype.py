from enum import Enum
from decimal import Decimal

from enum import Enum, auto
from decimal import Decimal
from typing import Dict, Optional

from enum import Enum, auto
from Zyiron_Chain.blockchain.constants import Constants
class TransactionType(Enum):
    """Defines all supported transaction types"""
    STANDARD = auto()  # Regular peer-to-peer transactions
    SMART = auto()     # Smart contract transactions
    INSTANT = auto()   # Instant settlement transactions
    COINBASE = auto()  # Block reward transactions

class PaymentTypeManager:
    """Manages transaction type configurations dynamically using Constants"""
    
    TYPE_CONFIG = {
        TransactionType.STANDARD: {
            "prefixes": Constants.TRANSACTION_MEMPOOL_MAP["STANDARD"]["prefixes"],  # ✅ Uses Constants
            "confirmations": Constants.TRANSACTION_CONFIRMATIONS["STANDARD"],  # ✅ Uses Constants
            "description": "Standard peer-to-peer transactions"
        },
        TransactionType.SMART: {
            "prefixes": Constants.TRANSACTION_MEMPOOL_MAP["SMART"]["prefixes"],  # ✅ Uses Constants
            "confirmations": Constants.TRANSACTION_CONFIRMATIONS["SMART"],  # ✅ Uses Constants
            "description": "Smart contract transactions"
        },
        TransactionType.INSTANT: {
            "prefixes": Constants.TRANSACTION_MEMPOOL_MAP["INSTANT"]["prefixes"],  # ✅ Uses Constants
            "confirmations": Constants.TRANSACTION_CONFIRMATIONS["INSTANT"],  # ✅ Uses Constants
            "description": "Instant settlement transactions"
        },
        TransactionType.COINBASE: {
            "prefixes": Constants.TRANSACTION_MEMPOOL_MAP["COINBASE"]["prefixes"],  # ✅ Uses Constants
            "confirmations": Constants.TRANSACTION_CONFIRMATIONS["COINBASE"],  # ✅ Uses Constants
            "description": "Block reward transactions"
        }
    }

    def get_transaction_type(self, tx_id: str) -> TransactionType:
        """Determine transaction type based on ID prefix using Constants"""
        if not tx_id:  
            return TransactionType.STANDARD  # ✅ Default to STANDARD

        # ✅ Validate against Constants-defined prefixes
        for tx_type, config in self.TYPE_CONFIG.items():
            if any(tx_id.startswith(prefix) for prefix in Constants.TRANSACTION_MEMPOOL_MAP[tx_type.name]["prefixes"]):
                return tx_type
        
        return TransactionType.STANDARD  # ✅ Default to STANDARD if no match
