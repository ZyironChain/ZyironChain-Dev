import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from decimal import Decimal
from typing import Dict, Optional
import json

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.utils.hashing import Hashing

class UTXOManager:
    """
    Manages Unspent Transaction Outputs (UTXOs) using a provided StorageManager.
    The StorageManager should expose an attribute 'utxo_db' for UTXO storage.
    Detailed print statements are used for step-by-step tracing.
    """

    def __init__(self, storage_manager):
        """
        Initialize the UTXOManager with a StorageManager instance.
        
        :param storage_manager: An instance of StorageManager that provides 'utxo_db'.
        """
        self.storage_manager = storage_manager
        self._cache: Dict[str, Dict] = {}  # Local cache for fast access
        print(f"[UTXOManager INFO] Initialized UTXOManager using provided StorageManager.")

    def register_utxo(self, tx_out: TransactionOut):
        """
        Register a new UTXO in both the local cache and the storage manager's utxo_db.
        Skips registration if the UTXO already exists.
        
        :param tx_out: The TransactionOut object representing the UTXO.
        """
        if not isinstance(tx_out, TransactionOut):
            print(f"[UTXOManager ERROR] Invalid UTXO type. Expected TransactionOut instance, got {type(tx_out)}.")
            raise TypeError("Invalid UTXO type. Expected TransactionOut instance.")
        
        if tx_out.tx_out_id in self._cache or self.storage_manager.utxo_db.get(tx_out.tx_out_id):
            print(f"[UTXOManager WARN] UTXO {tx_out.tx_out_id} already exists. Skipping registration.")
            return

        utxo_data = tx_out.to_dict()
        self._cache[tx_out.tx_out_id] = utxo_data
        self.storage_manager.utxo_db.put(tx_out.tx_out_id, utxo_data)
        print(f"[UTXOManager INFO] Registered UTXO: {tx_out.tx_out_id} | Amount: {tx_out.amount} | Locked: {tx_out.locked}")

    def get_utxo(self, tx_out_id: str) -> Optional[TransactionOut]:
        """
        Retrieve a UTXO from the local cache or from the storage manager's utxo_db.
        
        :param tx_out_id: The UTXO identifier.
        :return: A TransactionOut instance if found, else None.
        """
        if tx_out_id in self._cache:
            print(f"[UTXOManager INFO] Retrieved UTXO {tx_out_id} from local cache.")
            return TransactionOut.from_dict(self._cache[tx_out_id])
        
        utxo_data = self.storage_manager.utxo_db.get(tx_out_id)
        if not utxo_data:
            print(f"[UTXOManager WARN] UTXO {tx_out_id} not found in storage.")
            return None

        self._cache[tx_out_id] = utxo_data
        print(f"[UTXOManager INFO] Retrieved UTXO {tx_out_id} from storage and cached it.")
        return TransactionOut.from_dict(utxo_data)

    def delete_utxo(self, tx_out_id: str):
        """
        Delete a UTXO from both the local cache and the storage manager's utxo_db.
        
        :param tx_out_id: The UTXO identifier to delete.
        """
        if tx_out_id in self._cache:
            del self._cache[tx_out_id]
            print(f"[UTXOManager INFO] Removed UTXO {tx_out_id} from local cache.")
        
        self.storage_manager.utxo_db.delete(tx_out_id)
        print(f"[UTXOManager INFO] Deleted UTXO {tx_out_id} from storage.")

    def convert_to_standard_transaction(self, tx_id: str, new_payment_type: Optional[str] = None) -> Optional[str]:
        """
        Convert a confirmed transaction's UTXO data to a STANDARD type.
        Optionally update to a new payment type if provided (except 'COINBASE').
        
        :param tx_id: The transaction ID whose UTXO data is to be updated.
        :param new_payment_type: Optional new payment type (e.g., "INSTANT", "SMART").
        :return: The updated transaction type or None if conversion fails.
        """
        utxo_data = self.storage_manager.utxo_db.get(tx_id)
        if not utxo_data:
            print(f"[UTXOManager WARN] UTXO for transaction {tx_id} not found in storage. Cannot convert.")
            return None
        
        valid_types = list(Constants.TRANSACTION_MEMPOOL_MAP.keys())
        original_type = utxo_data.get("transaction_type", "STANDARD")
        if original_type not in valid_types:
            print(f"[UTXOManager WARN] Unknown transaction type '{original_type}' for {tx_id}. Defaulting to STANDARD.")
            original_type = "STANDARD"
        
        # Always convert confirmed transactions to STANDARD first
        utxo_data["transaction_type"] = "STANDARD"
        
        if new_payment_type in valid_types and new_payment_type != "COINBASE":
            utxo_data["transaction_type"] = new_payment_type
            print(f"[UTXOManager INFO] Reclassified transaction {tx_id} as {new_payment_type} for re-transfer.")
        
        self.storage_manager.utxo_db.put(tx_id, utxo_data)
        print(f"[UTXOManager INFO] Converted transaction {tx_id} from {original_type} to {utxo_data['transaction_type']}.")
        return utxo_data["transaction_type"]

    def update_from_block(self, block: Dict):
        """
        Update the UTXO set from a block's transactions.
        
        :param block: Dictionary representing the block (must contain a 'transactions' key).
        """
        if not isinstance(block, dict) or "transactions" not in block:
            print("[UTXOManager ERROR] Invalid block format. 'transactions' key missing.")
            return

        # Process coinbase transaction first
        coinbase = block["transactions"][0]
        if "outputs" in coinbase:
            for output in coinbase["outputs"]:
                tx_out = TransactionOut.from_dict(output)
                self.register_utxo(tx_out)
                print(f"[UTXOManager INFO] Processed coinbase UTXO: {tx_out.tx_out_id}")
        
        # Process regular transactions
        for tx in block["transactions"][1:]:
            if "outputs" not in tx or "inputs" not in tx:
                print(f"[UTXOManager WARN] Skipping malformed transaction during UTXO update: {tx}")
                continue
            
            for output in tx["outputs"]:
                tx_out = TransactionOut.from_dict(output)
                self.register_utxo(tx_out)
                print(f"[UTXOManager INFO] Registered UTXO from transaction: {tx_out.tx_out_id}")
            
            for tx_input in tx["inputs"]:
                self.consume_utxo(tx_input["tx_out_id"])
                print(f"[UTXOManager INFO] Consumed UTXO from transaction input: {tx_input['tx_out_id']}")

    def consume_utxo(self, tx_out_id: str):
        """
        Mark a UTXO as spent by removing it from storage and cache.
        
        :param tx_out_id: The UTXO identifier to consume.
        """
        utxo = self.get_utxo(tx_out_id)
        if not utxo:
            print(f"[UTXOManager WARN] Attempted to consume non-existent UTXO {tx_out_id}.")
            return
        
        if tx_out_id in self._cache:
            del self._cache[tx_out_id]
            print(f"[UTXOManager INFO] Removed UTXO {tx_out_id} from cache during consumption.")
        
        self.storage_manager.utxo_db.delete(tx_out_id)
        print(f"[UTXOManager INFO] Consumed UTXO {tx_out_id} from storage.")

    def lock_utxo(self, tx_out_id: str):
        """
        Lock a UTXO for transaction processing.
        
        :param tx_out_id: The UTXO identifier to lock.
        """
        if not hasattr(self, "lock"):
            from threading import Lock
            self.lock = Lock()
        
        with self.lock:
            utxo = self.get_utxo(tx_out_id)
            if not utxo:
                print(f"[UTXOManager WARN] Cannot lock non-existent UTXO: {tx_out_id}")
                return
            if utxo.locked:
                print(f"[UTXOManager WARN] UTXO {tx_out_id} is already locked.")
                return
            utxo.locked = True
            self.storage_manager.utxo_db.put(tx_out_id, utxo.to_dict())
            print(f"[UTXOManager INFO] Locked UTXO: {tx_out_id}")

    def unlock_utxo(self, tx_out_id: str):
        """
        Unlock a UTXO after transaction processing.
        
        :param tx_out_id: The UTXO identifier to unlock.
        """
        if not hasattr(self, "lock"):
            from threading import Lock
            self.lock = Lock()
        
        with self.lock:
            utxo = self.get_utxo(tx_out_id)
            if not utxo:
                print(f"[UTXOManager WARN] Cannot unlock non-existent UTXO: {tx_out_id}")
                return
            if not utxo.locked:
                print(f"[UTXOManager WARN] UTXO {tx_out_id} is already unlocked.")
                return
            utxo.locked = False
            self.storage_manager.utxo_db.put(tx_out_id, utxo.to_dict())
            print(f"[UTXOManager INFO] Unlocked UTXO: {tx_out_id}")

    def validate_utxo(self, tx_out_id: str, amount: Decimal) -> bool:
        """
        Validate that a UTXO exists, is unlocked, and has sufficient balance.
        
        :param tx_out_id: The UTXO identifier.
        :param amount: The required amount.
        :return: True if valid, False otherwise.
        """
        utxo = self.get_utxo(tx_out_id)
        if not utxo:
            print(f"[UTXOManager ERROR] UTXO {tx_out_id} does not exist.")
            return False
        if utxo.locked:
            print(f"[UTXOManager ERROR] UTXO {tx_out_id} is locked and cannot be spent.")
            return False
        utxo_amount = Decimal(str(utxo.amount))
        if utxo_amount < amount:
            print(f"[UTXOManager ERROR] UTXO {tx_out_id} has insufficient balance. Required: {amount}, Available: {utxo.amount}")
            return False
        print(f"[UTXOManager INFO] UTXO {tx_out_id} validated for spending: Required {amount}, Available {utxo.amount}")
        return True
