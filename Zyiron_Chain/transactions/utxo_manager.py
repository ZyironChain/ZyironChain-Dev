import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from decimal import Decimal
from typing import Dict, Optional

# Import your PeerConstants from the network folder
from Zyiron_Chain. network.peerconstant import PeerConstants

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.utils.deserializer import Deserializer
from threading import Lock

class UTXOManager:
    """
    Manages Unspent Transaction Outputs (UTXOs) using a provided UTXOStorage instance.
    Includes a local cache for performance and uses peer_id from PeerConstants.
    """

    def __init__(self, utxo_storage):
        """
        Initialize the UTXOManager with a UTXOStorage instance, and retrieve peer_id from PeerConstants.
        
        :param utxo_storage: An instance of your UTXOStorage class.
        """
        super().__init__()  # Illustrative super-call if no actual parent class is used

        # Retrieve the peer ID from PeerConstants
        self.peer_id = PeerConstants.PEER_USER_ID

        # Store the provided UTXOStorage instance
        self.utxo_storage = utxo_storage

        # Local cache for quick lookups (key: tx_out_id, value: UTXO data as dict)
        self._cache: Dict[str, Dict] = {}

        # A lock to protect critical sections in this manager
        self.lock = Lock()

        print(f"[UTXOManager INIT] UTXOManager created for peer_id={self.peer_id} with provided UTXOStorage.")

    def get_utxo(self, tx_out_id: str) -> Optional[TransactionOut]:
        """
        Retrieve a UTXO from the local cache or UTXOStorage.
        Converts raw dictionary data into a TransactionOut instance.
        
        :param tx_out_id: The UTXO ID to retrieve.
        :return: A TransactionOut instance if found, else None.
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print("[UTXOManager ERROR] ❌ Invalid tx_out_id. Must be a non-empty string.")
            return None

        # ✅ Check local cache first for quick lookup
        if tx_out_id in self._cache:
            print(f"[UTXOManager INFO] ✅ Found {tx_out_id} in cache for peer {self.peer_id}.")
            return TransactionOut.from_dict(self._cache[tx_out_id])

        # ✅ Retrieve from UTXOStorage if not found in cache
        utxo_data = self.utxo_storage.get(tx_out_id)
        if not utxo_data:
            print(f"[UTXOManager WARN] ⚠️ UTXO {tx_out_id} not found in storage for peer {self.peer_id}.")
            return None

        # ✅ Validate UTXO structure before caching
        try:
            utxo = TransactionOut.from_dict(utxo_data)
            self._cache[tx_out_id] = utxo_data  # Cache validated UTXO
            print(f"[UTXOManager INFO] ✅ Retrieved and cached UTXO {tx_out_id} for peer {self.peer_id}.")
            return utxo
        except Exception as e:
            print(f"[UTXOManager ERROR] ❌ Failed to parse UTXO {tx_out_id}: {e}")
            return None


    def register_utxo(self, tx_out: TransactionOut):
        """
        Register a new UTXO in both the local cache and UTXOStorage.
        Skips registration if the UTXO already exists.
        
        :param tx_out: A TransactionOut object representing the UTXO.
        """
        if not isinstance(tx_out, TransactionOut):
            print(f"[UTXOManager ERROR] ❌ Invalid UTXO type. Expected TransactionOut, got {type(tx_out)}.")
            raise TypeError("Invalid UTXO type. Expected TransactionOut.")

        # ✅ Ensure UTXO ID is valid
        tx_out_id = tx_out.tx_out_id.strip()
        if not tx_out_id:
            print("[UTXOManager ERROR] ❌ UTXO ID is empty. Cannot register an invalid UTXO.")
            raise ValueError("UTXO ID must be a non-empty string.")

        # ✅ Check if UTXO already exists
        if tx_out_id in self._cache or self.utxo_storage.get(tx_out_id):
            print(f"[UTXOManager WARN] ⚠️ UTXO {tx_out_id} already exists for peer {self.peer_id}. Skipping registration.")
            return

        # ✅ Convert UTXO to dictionary & store
        try:
            utxo_data = tx_out.to_dict()
            self._cache[tx_out_id] = utxo_data
            self.utxo_storage.put(tx_out_id, utxo_data)
            print(f"[UTXOManager INFO] ✅ Registered UTXO {tx_out_id} for peer {self.peer_id}.")
        except Exception as e:
            print(f"[UTXOManager ERROR] ❌ Failed to register UTXO {tx_out_id}: {e}")
    def delete_utxo(self, tx_out_id: str):
        """
        Delete a UTXO from both the local cache and UTXOStorage.
        
        :param tx_out_id: The UTXO ID to delete.
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print("[UTXOManager ERROR] ❌ Invalid UTXO ID. Must be a non-empty string.")
            return

        tx_out_id = tx_out_id.strip()

        # ✅ Remove from cache if exists
        if tx_out_id in self._cache:
            del self._cache[tx_out_id]
            print(f"[UTXOManager INFO] ✅ Removed {tx_out_id} from local cache for peer {self.peer_id}.")

        # ✅ Delete from storage with error handling
        try:
            if not self.utxo_storage.get(tx_out_id):
                print(f"[UTXOManager WARN] ⚠️ UTXO {tx_out_id} not found in storage. Skipping deletion.")
                return

            self.utxo_storage.delete(tx_out_id)
            print(f"[UTXOManager INFO] ✅ Deleted UTXO {tx_out_id} from storage for peer {self.peer_id}.")
        except Exception as e:
            print(f"[UTXOManager ERROR] ❌ Failed to delete UTXO {tx_out_id}: {e}")


    def update_from_block(self, block: dict):
        """
        Update UTXOs based on transactions in a block.
        Expects block["transactions"] to be a list of transaction dictionaries,
        with the first transaction as the coinbase transaction.

        This method is thread-safe and ensures atomic updates using a lock.

        :param block: Dictionary representing the block.
        """
        if not isinstance(block, dict) or "transactions" not in block:
            print("[UTXOManager ERROR] ❌ update_from_block: Invalid block or missing 'transactions'.")
            return

        print(f"[UTXOManager INFO] 🔄 update_from_block: Processing block UTXO updates for peer {self.peer_id}.")

        with self.lock:
            # ✅ Process coinbase transaction first (index 0)
            coinbase_tx = block["transactions"][0]
            if isinstance(coinbase_tx, dict) and "outputs" in coinbase_tx:
                for output in coinbase_tx["outputs"]:
                    try:
                        tx_out = TransactionOut.from_dict(output)
                        self.register_utxo(tx_out)
                        print(f"[UTXOManager INFO] ✅ Processed Coinbase UTXO {tx_out.tx_out_id}.")
                    except Exception as e:
                        print(f"[UTXOManager ERROR] ❌ Failed to process Coinbase UTXO: {e}")

            # ✅ Process subsequent transactions
            for tx_data in block["transactions"][1:]:
                if not isinstance(tx_data, dict) or "outputs" not in tx_data or "inputs" not in tx_data:
                    print(f"[UTXOManager WARN] ⚠️ Skipping malformed transaction: {tx_data}")
                    continue

                # ✅ Register new outputs
                for output in tx_data["outputs"]:
                    try:
                        tx_out = TransactionOut.from_dict(output)
                        self.register_utxo(tx_out)
                        print(f"[UTXOManager INFO] ✅ Registered UTXO {tx_out.tx_out_id}.")
                    except Exception as e:
                        print(f"[UTXOManager ERROR] ❌ Failed to register UTXO: {e}")

                # ✅ Consume spent inputs
                for tx_in in tx_data["inputs"]:
                    tx_out_id = tx_in.get("tx_out_id")
                    if not tx_out_id or not isinstance(tx_out_id, str):
                        print(f"[UTXOManager WARN] ⚠️ Skipping transaction input with missing 'tx_out_id': {tx_in}")
                        continue

                    try:
                        self.consume_utxo(tx_out_id)
                        print(f"[UTXOManager INFO] ✅ Consumed UTXO {tx_out_id}.")
                    except Exception as e:
                        print(f"[UTXOManager ERROR] ❌ Failed to consume UTXO {tx_out_id}: {e}")

    def consume_utxo(self, tx_out_id: str):
        """
        Mark a UTXO as spent by removing it from local cache and UTXOStorage.
        
        :param tx_out_id: The UTXO ID to consume.
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print(f"[UTXOManager ERROR] ❌ consume_utxo: Invalid UTXO ID format: {tx_out_id}")
            return

        utxo = self.get_utxo(tx_out_id)
        if not utxo:
            print(f"[UTXOManager WARN] ⚠️ consume_utxo: Non-existent UTXO {tx_out_id}. Skipping.")
            return

        # ✅ Remove from cache if present
        if tx_out_id in self._cache:
            del self._cache[tx_out_id]
            print(f"[UTXOManager INFO] 🗑️ consume_utxo: Removed {tx_out_id} from local cache.")

        # ✅ Delete from UTXO storage
        try:
            self.utxo_storage.delete(tx_out_id)
            print(f"[UTXOManager INFO] ✅ consume_utxo: Consumed (removed) UTXO {tx_out_id} from storage.")
        except Exception as e:
            print(f"[UTXOManager ERROR] ❌ consume_utxo: Failed to delete UTXO {tx_out_id}: {e}")


    def lock_utxo(self, tx_out_id: str):
        """
        Lock a UTXO for transaction processing. This updates the stored UTXO to mark it as locked.
        
        :param tx_out_id: The UTXO ID to lock.
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print(f"[UTXOManager ERROR] ❌ lock_utxo: Invalid UTXO ID format: {tx_out_id}")
            return

        with self.lock:
            utxo = self.get_utxo(tx_out_id)
            if not utxo:
                print(f"[UTXOManager WARN] ⚠️ lock_utxo: Cannot lock non-existent UTXO {tx_out_id}.")
                return
            if utxo.locked:
                print(f"[UTXOManager WARN] ⚠️ lock_utxo: UTXO {tx_out_id} is already locked.")
                return

            # ✅ Mark as locked and update storage
            try:
                utxo.locked = True
                self.utxo_storage.put(tx_out_id, utxo.to_dict())
                print(f"[UTXOManager INFO] 🔒 lock_utxo: Successfully locked UTXO {tx_out_id}.")
            except Exception as e:
                print(f"[UTXOManager ERROR] ❌ lock_utxo: Failed to update UTXO {tx_out_id}: {e}")


    def unlock_utxo(self, tx_out_id: str):
        """
        Unlock a UTXO after processing.
        
        :param tx_out_id: The UTXO ID to unlock.
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print(f"[UTXOManager ERROR] ❌ unlock_utxo: Invalid UTXO ID format: {tx_out_id}")
            return

        with self.lock:
            utxo = self.get_utxo(tx_out_id)
            if not utxo:
                print(f"[UTXOManager WARN] ⚠️ unlock_utxo: Cannot unlock non-existent UTXO {tx_out_id}.")
                return
            if not utxo.locked:
                print(f"[UTXOManager WARN] ⚠️ unlock_utxo: UTXO {tx_out_id} is already unlocked.")
                return

            # ✅ Unlock and update storage
            try:
                utxo.locked = False
                self.utxo_storage.put(tx_out_id, utxo.to_dict())
                print(f"[UTXOManager INFO] 🔓 unlock_utxo: Successfully unlocked UTXO {tx_out_id}.")
            except Exception as e:
                print(f"[UTXOManager ERROR] ❌ unlock_utxo: Failed to update UTXO {tx_out_id}: {e}")


    def lock_selected_utxos(self, tx_out_ids: list):
        """
        Lock multiple UTXOs given a list of tx_out_ids.
        
        :param tx_out_ids: List of UTXO IDs to lock.
        """
        if not isinstance(tx_out_ids, list) or not tx_out_ids:
            print("[UTXOManager ERROR] ❌ lock_selected_utxos: Invalid list of UTXO IDs.")
            return

        print(f"[UTXOManager INFO] 🔒 Locking selected UTXOs: {tx_out_ids}")
        for tx_out_id in tx_out_ids:
            self.lock_utxo(tx_out_id)


    def unlock_selected_utxos(self, tx_out_ids: list):
        """
        Unlock multiple UTXOs given a list of tx_out_ids.
        
        :param tx_out_ids: List of UTXO IDs to unlock.
        """
        if not isinstance(tx_out_ids, list) or not tx_out_ids:
            print("[UTXOManager ERROR] ❌ unlock_selected_utxos: Invalid list of UTXO IDs.")
            return

        print(f"[UTXOManager INFO] 🔓 Unlocking selected UTXOs: {tx_out_ids}")
        for tx_out_id in tx_out_ids:
            self.unlock_utxo(tx_out_id)


    def validate_utxo(self, tx_out_id: str, amount: Decimal) -> bool:
        """
        Validate that a UTXO exists, is unlocked, and has sufficient balance.
        
        :param tx_out_id: The UTXO ID to validate.
        :param amount: Required amount to spend.
        :return: True if valid, otherwise False.
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print(f"[UTXOManager ERROR] ❌ validate_utxo: Invalid UTXO ID format: {tx_out_id}")
            return False

        if not isinstance(amount, Decimal) or amount <= 0:
            print(f"[UTXOManager ERROR] ❌ validate_utxo: Invalid amount: {amount}")
            return False

        utxo = self.get_utxo(tx_out_id)
        if not utxo:
            print(f"[UTXOManager ERROR] ❌ validate_utxo: UTXO {tx_out_id} does not exist.")
            return False
        if utxo.locked:
            print(f"[UTXOManager ERROR] ❌ validate_utxo: UTXO {tx_out_id} is locked.")
            return False

        try:
            utxo_balance = Decimal(str(utxo.amount))
        except Exception as e:
            print(f"[UTXOManager ERROR] ❌ validate_utxo: Failed to parse UTXO balance: {e}")
            return False

        if utxo_balance < amount:
            print(f"[UTXOManager ERROR] ❌ validate_utxo: UTXO {tx_out_id} insufficient balance. "
                f"Required: {amount}, Available: {utxo.amount}.")
            return False

        print(f"[UTXOManager INFO] ✅ validate_utxo: UTXO {tx_out_id} is valid. Required: {amount}, Available: {utxo.amount}.")
        return True
