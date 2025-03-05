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


class UTXOManager:
    """
    Manages Unspent Transaction Outputs (UTXOs) using a provided UTXOStorage instance.
    Includes a local cache for performance and uses peer_id from PeerConstants.
    """

    def __init__(self, utxo_storage):
        """
        Initialize the UTXOManager with a UTXOStorage instance, and retrieve peer_id from PeerConstants.
        
        :param utxo_storage: An instance of your splitted UTXOStorage class.
        """
        super().__init__()  # Illustrative super-call if no actual parent class is used

        # Retrieve the peer ID from PeerConstants
        self.peer_id = PeerConstants.PEER_USER_ID

        # Store the provided UTXOStorage
        self.utxo_storage = utxo_storage

        # Local cache for quick lookups
        self._cache: Dict[str, Dict] = {}

        print(f"[UTXOManager INIT] UTXOManager created for peer_id={self.peer_id} with provided UTXOStorage.")

    def get_utxo(self, tx_out_id):
        """Retrieve UTXO data and deserialize it if necessary."""
        data = self.utxo_storage.get(tx_out_id)
        return Deserializer().deserialize(data) if data else None        

    def register_utxo(self, tx_out: TransactionOut):
        """
        Register a new UTXO in both the local cache and UTXOStorage.
        Skips registration if the UTXO already exists.

        :param tx_out: A TransactionOut object representing the UTXO.
        """
        if not isinstance(tx_out, TransactionOut):
            print(f"[UTXOManager ERROR] register_utxo: Invalid UTXO type. Expected TransactionOut, got {type(tx_out)}.")
            raise TypeError("Invalid UTXO type. Expected TransactionOut.")

        # Check local cache and utxo_storage
        if tx_out.tx_out_id in self._cache or self.utxo_storage.get(tx_out.tx_out_id):
            print(f"[UTXOManager WARN] UTXO {tx_out.tx_out_id} already exists for peer {self.peer_id}. Skipping.")
            return

        utxo_data = tx_out.to_dict()
        self._cache[tx_out.tx_out_id] = utxo_data
        self.utxo_storage.put(tx_out.tx_out_id, utxo_data)
        print(f"[UTXOManager INFO] register_utxo: UTXO {tx_out.tx_out_id} registered for peer {self.peer_id}.")

    def get_utxo(self, tx_out_id: str) -> Optional[TransactionOut]:
        """
        Retrieve a UTXO from the local cache or UTXOStorage.

        :param tx_out_id: The UTXO ID to retrieve.
        :return: A TransactionOut instance if found, else None.
        """
        if tx_out_id in self._cache:
            print(f"[UTXOManager INFO] get_utxo: Found {tx_out_id} in local cache for peer {self.peer_id}.")
            return TransactionOut.from_dict(self._cache[tx_out_id])

        utxo_data = self.utxo_storage.get(tx_out_id)
        if not utxo_data:
            print(f"[UTXOManager WARN] get_utxo: UTXO {tx_out_id} not found in storage for peer {self.peer_id}.")
            return None

        self._cache[tx_out_id] = utxo_data
        print(f"[UTXOManager INFO] get_utxo: UTXO {tx_out_id} retrieved from storage and cached for peer {self.peer_id}.")
        return TransactionOut.from_dict(utxo_data)

    def delete_utxo(self, tx_out_id: str):
        """
        Delete a UTXO from both the local cache and UTXOStorage.

        :param tx_out_id: The UTXO ID to delete.
        """
        if tx_out_id in self._cache:
            del self._cache[tx_out_id]
            print(f"[UTXOManager INFO] delete_utxo: Removed {tx_out_id} from local cache for peer {self.peer_id}.")

        self.utxo_storage.delete(tx_out_id)
        print(f"[UTXOManager INFO] delete_utxo: Deleted UTXO {tx_out_id} from storage for peer {self.peer_id}.")

    def update_from_block(self, block: dict):
        """
        Update UTXOs based on transactions in a block.
        Expects block["transactions"] to be a list of transaction dictionaries,
        with the first transaction as coinbase.

        :param block: Dictionary representing the block.
        """
        if not isinstance(block, dict) or "transactions" not in block:
            print("[UTXOManager ERROR] update_from_block: Invalid block or missing 'transactions'.")
            return

        # Process coinbase transaction first (index 0)
        coinbase_tx = block["transactions"][0]
        if "outputs" in coinbase_tx:
            for output in coinbase_tx["outputs"]:
                tx_out = TransactionOut.from_dict(output)
                self.register_utxo(tx_out)
                print(f"[UTXOManager INFO] update_from_block: Processed coinbase UTXO {tx_out.tx_out_id} for peer {self.peer_id}.")

        # Process subsequent transactions
        for tx_data in block["transactions"][1:]:
            if "outputs" not in tx_data or "inputs" not in tx_data:
                print(f"[UTXOManager WARN] update_from_block: Skipping malformed transaction for peer {self.peer_id}: {tx_data}")
                continue

            # Register new outputs
            for output in tx_data["outputs"]:
                tx_out = TransactionOut.from_dict(output)
                self.register_utxo(tx_out)
                print(f"[UTXOManager INFO] update_from_block: Registered UTXO {tx_out.tx_out_id} for peer {self.peer_id}.")

            # Consume spent inputs
            for tx_in in tx_data["inputs"]:
                self.consume_utxo(tx_in["tx_out_id"])
                print(f"[UTXOManager INFO] update_from_block: Consumed UTXO {tx_in['tx_out_id']} for peer {self.peer_id}.")

    def consume_utxo(self, tx_out_id: str):
        """
        Mark a UTXO as spent by removing it from local cache and UTXOStorage.

        :param tx_out_id: The UTXO ID to consume.
        """
        utxo = self.get_utxo(tx_out_id)
        if not utxo:
            print(f"[UTXOManager WARN] consume_utxo: Non-existent UTXO {tx_out_id} for peer {self.peer_id}.")
            return

        if tx_out_id in self._cache:
            del self._cache[tx_out_id]
            print(f"[UTXOManager INFO] consume_utxo: Removed {tx_out_id} from cache for peer {self.peer_id}.")

        self.utxo_storage.delete(tx_out_id)
        print(f"[UTXOManager INFO] consume_utxo: Consumed (removed) UTXO {tx_out_id} from storage for peer {self.peer_id}.")

    def lock_utxo(self, tx_out_id: str):
        """
        Lock a UTXO for transaction processing. This is a local concept unless you store 'locked' in UTXO data.

        :param tx_out_id: The UTXO ID to lock.
        """
        if not hasattr(self, "lock"):
            from threading import Lock
            self.lock = Lock()

        with self.lock:
            utxo = self.get_utxo(tx_out_id)
            if not utxo:
                print(f"[UTXOManager WARN] lock_utxo: Cannot lock non-existent UTXO {tx_out_id} for peer {self.peer_id}.")
                return
            if utxo.locked:
                print(f"[UTXOManager WARN] lock_utxo: UTXO {tx_out_id} is already locked for peer {self.peer_id}.")
                return

            utxo.locked = True
            self.utxo_storage.put(tx_out_id, utxo.to_dict())
            print(f"[UTXOManager INFO] lock_utxo: Locked UTXO {tx_out_id} for peer {self.peer_id}.")

    def unlock_utxo(self, tx_out_id: str):
        """
        Unlock a UTXO after processing.

        :param tx_out_id: The UTXO ID to unlock.
        """
        if not hasattr(self, "lock"):
            from threading import Lock
            self.lock = Lock()

        with self.lock:
            utxo = self.get_utxo(tx_out_id)
            if not utxo:
                print(f"[UTXOManager WARN] unlock_utxo: Cannot unlock non-existent UTXO {tx_out_id} for peer {self.peer_id}.")
                return
            if not utxo.locked:
                print(f"[UTXOManager WARN] unlock_utxo: UTXO {tx_out_id} is already unlocked for peer {self.peer_id}.")
                return

            utxo.locked = False
            self.utxo_storage.put(tx_out_id, utxo.to_dict())
            print(f"[UTXOManager INFO] unlock_utxo: Unlocked UTXO {tx_out_id} for peer {self.peer_id}.")

    def validate_utxo(self, tx_out_id: str, amount: Decimal) -> bool:
        """
        Validate that a UTXO exists, is unlocked, and has sufficient balance.

        :param tx_out_id: The UTXO ID to validate.
        :param amount: Required amount to spend.
        :return: True if valid, otherwise False.
        """
        utxo = self.get_utxo(tx_out_id)
        if not utxo:
            print(f"[UTXOManager ERROR] validate_utxo: UTXO {tx_out_id} does not exist for peer {self.peer_id}.")
            return False
        if utxo.locked:
            print(f"[UTXOManager ERROR] validate_utxo: UTXO {tx_out_id} is locked for peer {self.peer_id}.")
            return False

        utxo_balance = Decimal(str(utxo.amount))
        if utxo_balance < amount:
            print(f"[UTXOManager ERROR] validate_utxo: UTXO {tx_out_id} insufficient balance. Required: {amount}, Available: {utxo.amount} for peer {self.peer_id}.")
            return False

        print(f"[UTXOManager INFO] validate_utxo: UTXO {tx_out_id} is valid for spending. Required: {amount}, Available: {utxo.amount} (Peer {self.peer_id}).")
        return True
