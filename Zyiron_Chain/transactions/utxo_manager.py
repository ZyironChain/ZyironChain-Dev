import json
import sys
import os

from Zyiron_Chain.blockchain.block import Block
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from decimal import Decimal
from typing import Dict, List, Optional, Union

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

    def get_utxos_by_address(self, address: str) -> List[dict]:
        """
        Lazy-imports UTXOStorage and delegates the UTXO lookup to it.
        Avoids early import conflicts and ensures dynamic fallback access.
        """
        try:
            if not hasattr(self, "utxo_storage") or self.utxo_storage is None:
                from Zyiron_Chain.storage.utxostorage import UTXOStorage
                self.utxo_storage = UTXOStorage(block_storage=self.block_storage)

            return self.utxo_storage.get_utxos_by_address(address)

        except Exception as e:
            print(f"[UTXOManager] ❌ ERROR: Failed to retrieve UTXOs for {address}: {e}")
            return []


    def get_utxo(self, tx_out_id: str) -> Optional[TransactionOut]:
        """
        Retrieve a UTXO from the local cache, LMDB, or full block storage via fallback.
        Converts raw dictionary data into a TransactionOut instance.

        Args:
            tx_out_id: The UTXO ID to retrieve (format: "<tx_id>:<output_index>" or raw tx_id)
            
        Returns:
            TransactionOut: If UTXO is found and valid
            None: If UTXO cannot be found or is invalid
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print(f"[UTXOManager.get_utxo] ❌ Invalid tx_out_id: {tx_out_id}")
            return None

        tx_out_id = tx_out_id.strip()

        # ✅ Check local cache first
        if tx_out_id in self._cache:
            cached = self._cache[tx_out_id]
            if isinstance(cached, TransactionOut):
                return cached
            try:
                utxo = TransactionOut.from_dict(cached)
                self._cache[tx_out_id] = utxo
                return utxo
            except Exception as e:
                print(f"[UTXOManager.get_utxo] ❌ Corrupted cache entry for {tx_out_id}: {e}")
                del self._cache[tx_out_id]

        # 🔄 Parse tx_out_id
        if ':' in tx_out_id:
            try:
                tx_id, output_index_str = tx_out_id.split(':')
                output_index = int(output_index_str)
            except Exception as e:
                print(f"[UTXOManager.get_utxo] ❌ Malformed tx_out_id '{tx_out_id}': {e}")
                return None
        else:
            tx_id = tx_out_id
            output_index = 0  # Fallback default
            print(f"[UTXOManager.get_utxo] ⚠️ Using fallback mode for raw tx_id: {tx_id}")

        # ✅ Try LMDB lookup
        utxo_key = f"utxo:{tx_id}:{output_index}"
        try:
            with self.utxo_db.env.begin() as txn:
                value_bytes = txn.get(utxo_key.encode('utf-8'))
                if value_bytes:
                    try:
                        utxo_data = json.loads(value_bytes.decode('utf-8'))
                        utxo = TransactionOut.from_dict(utxo_data)
                        self._cache[tx_out_id] = utxo
                        return utxo
                    except Exception as parse_err:
                        print(f"[UTXOManager.get_utxo] ❌ Failed to parse LMDB UTXO for {utxo_key}: {parse_err}")
        except Exception as e:
            print(f"[UTXOManager.get_utxo] ⚠️ LMDB lookup failed for {utxo_key}: {e}")

        # 🔁 Fallback: Scan block storage
        print(f"[UTXOManager.get_utxo] ⚠️ Falling back to block storage for {tx_out_id}")
        try:
            all_utxos = self.utxo_storage.get_all_utxos_by_tx_id(tx_out_id)    



            for utxo_dict in all_utxos:
                try:
                    if isinstance(utxo_dict, TransactionOut):
                        if utxo_dict.tx_out_id == tx_out_id:
                            self._cache[tx_out_id] = utxo_dict
                            return utxo_dict
                    elif isinstance(utxo_dict, dict):
                        if utxo_dict.get("output_index") == output_index:
                            utxo = TransactionOut.from_dict(utxo_dict)
                            self._cache[tx_out_id] = utxo
                            return utxo
                except Exception as match_err:
                    print(f"[UTXOManager.get_utxo] ⚠️ UTXO match parse error: {match_err}")
                    continue

            print(f"[UTXOManager.get_utxo] ❌ No UTXO found for {tx_out_id} in block storage")
            return None
        except Exception as e:
            print(f"[UTXOManager.get_utxo] ❌ Fallback failed for {tx_out_id}: {e}")
            return None

    def register_utxo(self, tx_out: TransactionOut):
        """
        Register a new UTXO in both the local cache and UTXOStorage.
        Supports fallback when tx_out_id format is invalid.

        :param tx_out: A TransactionOut object representing the UTXO.
        """
        if not isinstance(tx_out, TransactionOut):
            print(f"[UTXOManager.register_utxo] ❌ Invalid UTXO type. Expected TransactionOut, got {type(tx_out)}.")
            raise TypeError("Invalid UTXO type. Expected TransactionOut.")

        tx_out_id = tx_out.tx_out_id.strip()
        if not tx_out_id:
            print("[UTXOManager.register_utxo] ❌ UTXO ID is empty. Cannot register an invalid UTXO.")
            raise ValueError("UTXO ID must be a non-empty string.")

        # ✅ Check if already exists
        exists_in_cache = tx_out_id in self._cache
        exists_in_db = self.utxo_storage.get(tx_out_id)

        if exists_in_cache or exists_in_db:
            print(f"[UTXOManager.register_utxo] ⚠️ UTXO {tx_out_id} already exists for peer {self.peer_id}. Skipping.")
            return

        # 🔁 Fallback: If no ':' in tx_out_id, check raw tx_id fallback set
        if ':' not in tx_out_id:
            print(f"[UTXOManager.register_utxo] ⚠️ Invalid tx_out_id format: {tx_out_id}. Attempting fallback...")
            try:
                fallback_utxos = self.utxo_storage.get_all_utxos_by_tx_id(tx_out_id)  # ✅ FIXED: removed tx_id=
                for utxo in fallback_utxos:
                    try:
                        if isinstance(utxo, TransactionOut):
                            if utxo.tx_out_id == tx_out_id:
                                print(f"[UTXOManager.register_utxo] ⚠️ UTXO {tx_out_id} already exists in fallback (obj). Skipping.")
                                return
                        elif isinstance(utxo, dict):
                            if utxo.get("tx_out_id") == tx_out_id:
                                print(f"[UTXOManager.register_utxo] ⚠️ UTXO {tx_out_id} already exists in fallback (dict). Skipping.")
                                return
                    except Exception as inner_err:
                        print(f"[UTXOManager.register_utxo] ⚠️ Error checking fallback UTXO: {inner_err}")
                        continue
            except Exception as e:
                print(f"[UTXOManager.register_utxo] ❌ Fallback check failed for tx_id={tx_out_id}: {e}")
                return

        # ✅ Store new UTXO
        try:
            utxo_data = tx_out.to_dict()
            self._cache[tx_out_id] = utxo_data
            self.utxo_storage.put(tx_out_id, utxo_data)
            print(f"[UTXOManager.register_utxo] ✅ Registered UTXO {tx_out_id} for peer {self.peer_id}.")
        except Exception as e:
            print(f"[UTXOManager.register_utxo] ❌ Failed to register UTXO {tx_out_id}: {e}")

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


    def update_from_block(self, block: Union[Dict, Block]):
        """
        Update UTXOs from block with comprehensive fallback handling for:
        - Different block formats (Dict vs Block object)
        - Malformed transactions
        - Invalid UTXO references
        - Lock contention issues
        """
        def safe_get_transactions(block_obj):
            """Multi-format transaction extraction"""
            if isinstance(block_obj, Block):
                return block_obj.transactions
            elif isinstance(block_obj, dict):
                return block_obj.get("transactions", [])
            return []

        def safe_process_output(output):
            """Safe output processing with validation"""
            try:
                if isinstance(output, dict):
                    return TransactionOut.from_dict(output)
                elif isinstance(output, TransactionOut):
                    return output
            except Exception as e:
                print(f"[UTXOManager] ⚠️ Invalid output: {e}")
            return None

        if not block:
            print("[UTXOManager] ❌ Empty block provided")
            return

        print(f"[UTXOManager] 🔄 Processing block updates (type: {type(block)})")

        # Fallback 1: Handle lock acquisition failures
        lock_acquired = False
        try:
            lock_acquired = self.lock.acquire(timeout=10)
            if not lock_acquired:
                print("[UTXOManager] ⚠️ Failed to acquire lock after 10s")
                return
        except Exception as e:
            print(f"[UTXOManager] ❌ Lock acquisition failed: {e}")
            return

        try:
            transactions = safe_get_transactions(block)
            if not transactions:
                print("[UTXOManager] ⚠️ No transactions in block")
                return

            # Fallback 2: Handle coinbase transaction
            coinbase = transactions[0] if transactions else None
            if coinbase:
                try:
                    outputs = coinbase.outputs if hasattr(coinbase, 'outputs') else coinbase.get('outputs', [])
                    for output in outputs:
                        tx_out = safe_process_output(output)
                        if tx_out:
                            self.register_utxo(tx_out)
                except Exception as e:
                    print(f"[UTXOManager] ❌ Coinbase processing failed: {e}")

            # Process regular transactions
            for tx in transactions[1:]:
                try:
                    # Fallback 3: Handle transaction format variations
                    inputs = tx.inputs if hasattr(tx, 'inputs') else tx.get('inputs', [])
                    outputs = tx.outputs if hasattr(tx, 'outputs') else tx.get('outputs', [])

                    # Process outputs
                    for output in outputs:
                        tx_out = safe_process_output(output)
                        if tx_out:
                            self.register_utxo(tx_out)

                    # Process inputs
                    for tx_in in inputs:
                        tx_out_id = getattr(tx_in, 'tx_out_id', None) or tx_in.get('tx_out_id')
                        if tx_out_id:
                            try:
                                self.consume_utxo(tx_out_id)
                            except Exception as e:
                                print(f"[UTXOManager] ⚠️ Failed to consume UTXO {tx_out_id}: {e}")
                except Exception as e:
                    print(f"[UTXOManager] ⚠️ Transaction processing failed: {e}")

        finally:
            if lock_acquired:
                self.lock.release()

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
            print(f"[UTXOManager.lock_utxo] ❌ Invalid UTXO ID format: {tx_out_id}")
            return

        with self.lock:
            if ":" in tx_out_id:
                # ✅ Standard format
                utxo = self.get_utxo(tx_out_id)
                if not utxo:
                    print(f"[UTXOManager.lock_utxo] ⚠️ Cannot lock non-existent UTXO {tx_out_id}.")
                    return
                if utxo.locked:
                    print(f"[UTXOManager.lock_utxo] ⚠️ UTXO {tx_out_id} is already locked.")
                    return
                try:
                    utxo.locked = True
                    self.utxo_storage.put(tx_out_id, utxo.to_dict())
                    print(f"[UTXOManager.lock_utxo] 🔒 Successfully locked UTXO {tx_out_id}.")
                except Exception as e:
                    print(f"[UTXOManager.lock_utxo] ❌ Failed to update UTXO {tx_out_id}: {e}")
            else:
                # 🔁 Fallback: Try to lock all UTXOs with this tx_id
                print(f"[UTXOManager.lock_utxo] ⚠️ Invalid tx_out_id format: {tx_out_id}. Attempting fallback using raw tx_id...")
                try:
                    utxos = self.utxo_storage.get_all_utxos_by_tx_id(tx_out_id)  
                    if not utxos:
                        print(f"[UTXOManager.lock_utxo] ❌ No UTXOs found for tx_id={tx_out_id}.")
                        return
                    for utxo_dict in utxos:
                        try:
                            if isinstance(utxo_dict, TransactionOut):
                                utxo_obj = utxo_dict
                            else:
                                utxo_obj = TransactionOut.from_dict(utxo_dict)
                            utxo_obj.locked = True
                            self.utxo_storage.put(utxo_obj.tx_out_id, utxo_obj.to_dict())
                            print(f"[UTXOManager.lock_utxo] 🔒 Fallback locked UTXO {utxo_obj.tx_out_id}.")
                        except Exception as inner_err:
                            print(f"[UTXOManager.lock_utxo] ❌ Fallback lock failed for {utxo_dict.get('tx_out_id', '?')}: {inner_err}")
                except Exception as e:
                    print(f"[UTXOManager.lock_utxo] ❌ Fallback failed while scanning UTXOs for tx_id={tx_out_id}: {e}")


    def unlock_utxo(self, tx_out_id: str):
        """
        Unlock a UTXO after processing. Supports fallback for raw tx_id.
        :param tx_out_id: The UTXO ID to unlock. Format: '<tx_id>:<output_index>' or fallback to '<tx_id>'.
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print(f"[UTXOManager.unlock_utxo] ❌ Invalid UTXO ID format: {tx_out_id}")
            return

        with self.lock:
            if ":" in tx_out_id:
                # ✅ Standard format
                utxo = self.get_utxo(tx_out_id)
                if not utxo:
                    print(f"[UTXOManager.unlock_utxo] ⚠️ Cannot unlock non-existent UTXO {tx_out_id}.")
                    return
                if not utxo.locked:
                    print(f"[UTXOManager.unlock_utxo] ⚠️ UTXO {tx_out_id} is already unlocked.")
                    return
                try:
                    utxo.locked = False
                    self.utxo_storage.put(tx_out_id, utxo.to_dict())
                    print(f"[UTXOManager.unlock_utxo] 🔓 Successfully unlocked UTXO {tx_out_id}.")
                except Exception as e:
                    print(f"[UTXOManager.unlock_utxo] ❌ Failed to update UTXO {tx_out_id}: {e}")
            else:
                # 🔁 Fallback: Unlock all UTXOs for tx_id
                print(f"[UTXOManager.unlock_utxo] ⚠️ Invalid tx_out_id format: {tx_out_id}. Attempting fallback using raw tx_id...")
                try:
                    utxos = self.utxo_storage.get_all_utxos_by_tx_id(tx_out_id)  # ✅ FIXED call
                    if not utxos:
                        print(f"[UTXOManager.unlock_utxo] ❌ No UTXOs found for tx_id={tx_out_id}.")
                        return
                    for utxo_dict in utxos:
                        try:
                            utxo_obj = utxo_dict if isinstance(utxo_dict, TransactionOut) else TransactionOut.from_dict(utxo_dict)
                            utxo_obj.locked = False
                            self.utxo_storage.put(utxo_obj.tx_out_id, utxo_obj.to_dict())
                            print(f"[UTXOManager.unlock_utxo] 🔓 Fallback unlocked UTXO {utxo_obj.tx_out_id}.")
                        except Exception as inner_err:
                            print(f"[UTXOManager.unlock_utxo] ❌ Fallback unlock failed for {utxo_dict.get('tx_out_id', '?')}: {inner_err}")
                except Exception as e:
                    print(f"[UTXOManager.unlock_utxo] ❌ Fallback failed while scanning UTXOs for tx_id={tx_out_id}: {e}")



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
            print(f"[UTXOManager.validate_utxo] ❌ Invalid UTXO ID format: {tx_out_id}")
            return False

        if not isinstance(amount, Decimal) or amount <= 0:
            print(f"[UTXOManager.validate_utxo] ❌ Invalid amount: {amount}")
            return False

        # ✅ Handle full tx_out_id format directly
        if ":" in tx_out_id:
            utxo = self.get_utxo(tx_out_id)
            if not utxo:
                print(f"[UTXOManager.validate_utxo] ❌ UTXO {tx_out_id} does not exist.")
                return False
            if utxo.locked:
                print(f"[UTXOManager.validate_utxo] ❌ UTXO {tx_out_id} is locked.")
                return False
            try:
                utxo_balance = Decimal(str(utxo.amount))
            except Exception as e:
                print(f"[UTXOManager.validate_utxo] ❌ Failed to parse UTXO balance: {e}")
                return False
            if utxo_balance < amount:
                print(f"[UTXOManager.validate_utxo] ❌ UTXO {tx_out_id} has insufficient balance. "
                    f"Required: {amount}, Available: {utxo.amount}")
                return False
            print(f"[UTXOManager.validate_utxo] ✅ UTXO {tx_out_id} is valid. Required: {amount}, Available: {utxo.amount}")
            return True

        # 🔁 Fallback using raw tx_id (aggregate all matching UTXOs)
        print(f"[UTXOManager.validate_utxo] ⚠️ Raw tx_id provided. Checking all UTXOs under tx_id={tx_out_id}")
        try:
            utxos = self.utxo_storage.get_all_utxos_by_tx_id(tx_out_id)  # ✅ FIXED: removed invalid keyword arg
        except Exception as e:
            print(f"[UTXOManager.validate_utxo] ❌ Fallback retrieval failed for tx_id={tx_out_id}: {e}")
            return False

        if not utxos:
            print(f"[UTXOManager.validate_utxo] ❌ No UTXOs found for tx_id={tx_out_id}")
            return False

        total_available = Decimal("0")
        for utxo_dict in utxos:
            try:
                utxo = TransactionOut.from_dict(utxo_dict)
                if not utxo.locked:
                    total_available += Decimal(str(utxo.amount))
            except Exception as e:
                print(f"[UTXOManager.validate_utxo] ⚠️ Skipping fallback UTXO due to parse error: {e}")
                continue

        if total_available < amount:
            print(f"[UTXOManager.validate_utxo] ❌ Combined UTXOs under tx_id={tx_out_id} insufficient. "
                f"Required: {amount}, Available: {total_available}")
            return False

        print(f"[UTXOManager.validate_utxo] ✅ Combined UTXOs under tx_id={tx_out_id} are valid. Available: {total_available}")
        return True
