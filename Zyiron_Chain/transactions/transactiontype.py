from enum import Enum, auto
from typing import TYPE_CHECKING
from Zyiron_Chain.blockchain.constants import Constants

if TYPE_CHECKING:
    # These imports are only for type-checking purposes.
    from Zyiron_Chain.transactions.coinbase import CoinbaseTx
    from Zyiron_Chain.transactions.fees import FundsAllocator

class TransactionType(Enum):
    """Defines all supported transaction types."""
    STANDARD = auto()  # Regular peer-to-peer transactions
    SMART = auto()     # Smart contract transactions
    INSTANT = auto()   # Instant settlement transactions
    COINBASE = auto()  # Block reward transactions

    def get_name(self) -> str:
        """Return the transaction type name in uppercase."""
        return self.name.upper()

    @classmethod
    def from_str(cls, value: str) -> "TransactionType":
        """Convert a string to a TransactionType Enum."""
        try:
            result = cls[value.upper()]
            print(f"[TransactionType.from_str] INFO: Converted '{value}' to TransactionType '{result.get_name()}'.")
            return result
        except KeyError:
            print(f"[TransactionType.from_str] ERROR: Invalid transaction type '{value}'. Allowed types: {[t.name for t in cls]}.")
            raise ValueError(f"[ERROR] Invalid transaction type: {value}.")
