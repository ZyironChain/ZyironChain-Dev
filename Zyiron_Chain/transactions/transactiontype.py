from enum import Enum
from decimal import Decimal

from enum import Enum, auto
from decimal import Decimal
from typing import Dict, Optional

from enum import Enum, auto
from Zyiron_Chain.blockchain.constants import Constants
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # These imports will only be available during type-checking (e.g., for linters, IDEs, or mypy)
    from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
    from Zyiron_Chain.transactions.fees import FundsAllocator



class TransactionType(Enum):
    """Defines all supported transaction types"""
    STANDARD = auto()  # Regular peer-to-peer transactions
    SMART = auto()     # Smart contract transactions
    INSTANT = auto()   # Instant settlement transactions
    COINBASE = auto()  # Block reward transactions

