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
        Retrieve a UTXO from the local cache, LMDB, or full block storage via fallback.
        Converts raw dictionary data into a TransactionOut instance.

        :param tx_out_id: The UTXO ID to retrieve (format: "<tx_id>:<output_index>" or raw tx_id for fallback).
        :return: A TransactionOut instance if found, else None.
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print(f"[UTXOManager ERROR] ❌ get_utxo: Invalid tx_out_id input: {tx_out_id}")
            return None

        tx_out_id = tx_out_id.strip()

        # 🔁 Handle fallback if format is invalid
        if ":" not in tx_out_id:
            print(f"[UTXOManager WARN] ⚠️ Invalid tx_out_id format: {tx_out_id}. Attempting fallback using raw tx_id...")
            tx_id = tx_out_id
            if len(tx_id) != 96:
                print(f"[UTXOManager ERROR] ❌ Fallback failed: Invalid tx_id length for {tx_id}")
                return None

            try:
                all_utxos = self.utxo_storage.get_all_utxos_by_tx_id(tx_id)
                print(f"[get_all_utxos_by_tx_id] ✅ Found {len(all_utxos)} UTXOs for tx_id={tx_id}")

                for utxo_dict in all_utxos:
                    try:
                        utxo = TransactionOut.from_dict(utxo_dict)
                        recovered_id = utxo.tx_out_id
                        self._cache[recovered_id] = utxo_dict
                        if recovered_id == tx_out_id:
                            print(f"[UTXOManager INFO] ✅ Fallback matched and cached UTXO {recovered_id}.")
                            return utxo
                    except Exception as e:
                        print(f"[UTXOManager ERROR] ❌ Failed to convert fallback UTXO: {e}")
                print(f"[UTXOManager ERROR] ❌ No UTXOs matched fallback tx_id={tx_id}.")
                return None
            except Exception as e:
                print(f"[UTXOManager ERROR] ❌ Fallback retrieval error for tx_id={tx_id}: {e}")
                return None

        # ✅ Normal path with tx_id:output_index format
        try:
            tx_id, output_index_str = tx_out_id.split(":")
            output_index = int(output_index_str)
        except Exception as e:
            print(f"[UTXOManager ERROR] ❌ Failed to parse tx_out_id '{tx_out_id}': {e}")
            return None

        if tx_out_id in self._cache:
            print(f"[UTXOManager INFO] ✅ Found {tx_out_id} in cache for peer {self.peer_id}.")
            return TransactionOut.from_dict(self._cache[tx_out_id])

        utxo_data = self.utxo_storage.get_utxo(tx_id, output_index)
        if not utxo_data:
            print(f"[UTXOManager WARN] ⚠️ UTXO {tx_out_id} not found in LMDB. Attempting fallback to full block storage...")
            return self.get_utxo(tx_id)  # Retry fallback

        try:
            utxo = TransactionOut.from_dict(utxo_data)
            self._cache[tx_out_id] = utxo_data
            print(f"[UTXOManager INFO] ✅ Retrieved and cached UTXO {tx_out_id} for peer {self.peer_id}.")
            return utxo
        except Exception as e:
            print(f"[UTXOManager ERROR] ❌ Failed to convert UTXO {tx_out_id}: {e}")
            return None


    def register_utxo(self, tx_out: TransactionOut):
        """
        Register a new UTXO in both the local cache and UTXOStorage.
        Supports fallback when tx_out_id format is invalid.
        
        :param tx_out: A TransactionOut object representing the UTXO.
        """
        if not isinstance(tx_out, TransactionOut):
            print(f"[UTXOManager ERROR] ❌ Invalid UTXO type. Expected TransactionOut, got {type(tx_out)}.")
            raise TypeError("Invalid UTXO type. Expected TransactionOut.")

        tx_out_id = tx_out.tx_out_id.strip()
        if not tx_out_id:
            print("[UTXOManager ERROR] ❌ UTXO ID is empty. Cannot register an invalid UTXO.")
            raise ValueError("UTXO ID must be a non-empty string.")

        # ✅ Check if UTXO already exists in cache or LMDB
        exists_in_cache = tx_out_id in self._cache
        exists_in_db = self.utxo_storage.get(tx_out_id)

        if exists_in_cache or exists_in_db:
            print(f"[UTXOManager WARN] ⚠️ UTXO {tx_out_id} already exists for peer {self.peer_id}. Skipping registration.")
            return

        # 🔁 Fallback: if tx_out_id is invalid (no ":"), check raw tx_id set
        if ":" not in tx_out_id:
            print(f"[UTXOManager WARN] ⚠️ Invalid tx_out_id format: {tx_out_id}. Attempting fallback using tx_id...")
            try:
                fallback_utxos = self.utxo_storage.get_all_utxos_by_tx_id(tx_out_id)
                if any(utxo.get("tx_out_id") == tx_out_id for utxo in fallback_utxos):
                    print(f"[UTXOManager WARN] ⚠️ UTXO with tx_id={tx_out_id} already exists in fallback. Skipping.")
                    return
            except Exception as e:
                print(f"[UTXOManager ERROR] ❌ Fallback UTXO check failed for tx_id={tx_out_id}: {e}")
                return

        # ✅ Proceed with storing new UTXO
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
        Lock a UTXO for transaction processing. Falls back to lock all outputs for a given tx_id if format is invalid.
        :param tx_out_id: The UTXO ID to lock. Format: '<tx_id>:<output_index>' or fallback to '<tx_id>'.
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print(f"[UTXOManager ERROR] ❌ lock_utxo: Invalid UTXO ID format: {tx_out_id}")
            return

        with self.lock:
            if ":" in tx_out_id:
                # Standard format
                utxo = self.get_utxo(tx_out_id)
                if not utxo:
                    print(f"[UTXOManager WARN] ⚠️ lock_utxo: Cannot lock non-existent UTXO {tx_out_id}.")
                    return
                if utxo.locked:
                    print(f"[UTXOManager WARN] ⚠️ lock_utxo: UTXO {tx_out_id} is already locked.")
                    return
                try:
                    utxo.locked = True
                    self.utxo_storage.put(tx_out_id, utxo.to_dict())
                    print(f"[UTXOManager INFO] 🔒 lock_utxo: Successfully locked UTXO {tx_out_id}.")
                except Exception as e:
                    print(f"[UTXOManager ERROR] ❌ lock_utxo: Failed to update UTXO {tx_out_id}: {e}")
            else:
                # Fallback: Try to lock all UTXOs with this tx_id
                print(f"[UTXOManager WARN] ⚠️ Invalid tx_out_id format: {tx_out_id}. Attempting fallback using raw tx_id...")
                utxos = self.utxo_storage.get_all_utxos_by_tx_id(tx_out_id)
                if not utxos:
                    print(f"[UTXOManager ERROR] ❌ No UTXOs found for tx_id={tx_out_id}.")
                    return
                for utxo_dict in utxos:
                    try:
                        utxo_obj = TransactionOut.from_dict(utxo_dict)
                        utxo_obj.locked = True
                        self.utxo_storage.put(utxo_obj.tx_out_id, utxo_obj.to_dict())
                        print(f"[UTXOManager INFO] 🔒 Fallback locked UTXO {utxo_obj.tx_out_id}.")
                    except Exception as e:
                        print(f"[UTXOManager ERROR] ❌ Fallback lock failed for {utxo_dict.get('tx_out_id', '?')}: {e}")

    def unlock_utxo(self, tx_out_id: str):
        """
        Unlock a UTXO after processing. Supports fallback for raw tx_id.
        :param tx_out_id: The UTXO ID to unlock. Format: '<tx_id>:<output_index>' or fallback to '<tx_id>'.
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print(f"[UTXOManager ERROR] ❌ unlock_utxo: Invalid UTXO ID format: {tx_out_id}")
            return

        with self.lock:
            if ":" in tx_out_id:
                # Standard format
                utxo = self.get_utxo(tx_out_id)
                if not utxo:
                    print(f"[UTXOManager WARN] ⚠️ unlock_utxo: Cannot unlock non-existent UTXO {tx_out_id}.")
                    return
                if not utxo.locked:
                    print(f"[UTXOManager WARN] ⚠️ unlock_utxo: UTXO {tx_out_id} is already unlocked.")
                    return
                try:
                    utxo.locked = False
                    self.utxo_storage.put(tx_out_id, utxo.to_dict())
                    print(f"[UTXOManager INFO] 🔓 unlock_utxo: Successfully unlocked UTXO {tx_out_id}.")
                except Exception as e:
                    print(f"[UTXOManager ERROR] ❌ unlock_utxo: Failed to update UTXO {tx_out_id}: {e}")
            else:
                # Fallback: Unlock all UTXOs for tx_id
                print(f"[UTXOManager WARN] ⚠️ Invalid tx_out_id format: {tx_out_id}. Attempting fallback using raw tx_id...")
                utxos = self.utxo_storage.get_all_utxos_by_tx_id(tx_out_id)
                if not utxos:
                    print(f"[UTXOManager ERROR] ❌ No UTXOs found for tx_id={tx_out_id}.")
                    return
                for utxo_dict in utxos:
                    try:
                        utxo_obj = TransactionOut.from_dict(utxo_dict)
                        utxo_obj.locked = False
                        self.utxo_storage.put(utxo_obj.tx_out_id, utxo_obj.to_dict())
                        print(f"[UTXOManager INFO] 🔓 Fallback unlocked UTXO {utxo_obj.tx_out_id}.")
                    except Exception as e:
                        print(f"[UTXOManager ERROR] ❌ Fallback unlock failed for {utxo_dict.get('tx_out_id', '?')}: {e}")



    def lock_selected_utxos(self, tx_out_ids: list):
        """
        Lock multiple UTXOs given a list of tx_out_ids (supporting both full and raw tx_id formats).
        """
        if not isinstance(tx_out_ids, list) or not tx_out_ids:
            print("[UTXOManager ERROR] ❌ lock_selected_utxos: Invalid list of UTXO IDs.")
            return

        print(f"[UTXOManager INFO] 🔒 Locking selected UTXOs: {tx_out_ids}")
        for tx_out_id in tx_out_ids:
            self.lock_utxo(tx_out_id)



    def unlock_selected_utxos(self, tx_out_ids: list):
        """
        Unlock multiple UTXOs given a list of tx_out_ids (supporting both full and raw tx_id formats).
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
        Supports fallback using tx_id only.
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print(f"[UTXOManager ERROR] ❌ validate_utxo: Invalid UTXO ID format: {tx_out_id}")
            return False

        if not isinstance(amount, Decimal) or amount <= 0:
            print(f"[UTXOManager ERROR] ❌ validate_utxo: Invalid amount: {amount}")
            return False

        # ✅ Handle valid format directly
        if ":" in tx_out_id:
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

        # 🔁 Fallback: Handle raw tx_id
        print(f"[UTXOManager WARN] ⚠️ validate_utxo: Raw tx_id provided. Checking all UTXOs under tx_id={tx_out_id}")
        utxos = self.utxo_storage.get_all_utxos_by_tx_id(tx_out_id)
        if not utxos:
            print(f"[UTXOManager ERROR] ❌ validate_utxo: No UTXOs found for tx_id={tx_out_id}.")
            return False

        total_available = Decimal("0")
        for utxo_dict in utxos:
            try:
                utxo = TransactionOut.from_dict(utxo_dict)
                if not utxo.locked:
                    total_available += Decimal(str(utxo.amount))
            except Exception as e:
                print(f"[UTXOManager ERROR] ❌ validate_utxo: Failed to process UTXO fallback: {e}")
                continue

        if total_available < amount:
            print(f"[UTXOManager ERROR] ❌ validate_utxo: Insufficient combined UTXOs for tx_id={tx_out_id}. "
                f"Required: {amount}, Available: {total_available}")
            return False

        print(f"[UTXOManager INFO] ✅ validate_utxo: Combined UTXOs under tx_id={tx_out_id} are valid. Available: {total_available}")
        return True
