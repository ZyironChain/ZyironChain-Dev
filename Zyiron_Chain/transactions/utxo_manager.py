import json
import sys
import os
import time

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


    def lock_utxo(self, tx_out_id: str) -> bool:
        """
        Lock a UTXO for transaction processing. Falls back to lock all outputs for a given tx_id if format is invalid.
        Handles both 'locked' and 'is_locked' key formats for backward compatibility.
        
        Args:
            tx_out_id: The UTXO ID to lock. Format: '<tx_id>:<output_index>' or fallback to '<tx_id>'.
            
        Returns:
            bool: True if locking was successful (or already locked), False otherwise.
        """
        # Validate input format
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print(f"[UTXOManager.lock_utxo] ❌ Invalid UTXO ID format: {tx_out_id}")
            return False

        tx_out_id = tx_out_id.strip()
        success = False

        with self.lock:
            try:
                if ":" in tx_out_id:
                    # Standard format with output index
                    success = self._lock_single_utxo(tx_out_id)
                else:
                    # Fallback for raw tx_id format
                    print(f"[UTXOManager.lock_utxo] ⚠️ Raw tx_id format, locking all UTXOs for {tx_out_id}")
                    success = self._lock_all_utxos_for_tx(tx_out_id)
                    
            except Exception as e:
                print(f"[UTXOManager.lock_utxo] ❌ Critical error locking UTXO(s): {e}")
                return False
                
        return success

    def _lock_single_utxo(self, tx_out_id: str) -> bool:
        """Lock a single UTXO with standard tx_id:output_index format."""
        try:
            # Validate UTXO ID structure
            parts = tx_out_id.split(':')
            if len(parts) != 2:
                print(f"[UTXOManager] ❌ Malformed UTXO ID: {tx_out_id}")
                return False
                
            tx_id, output_index = parts
            try:
                output_index = int(output_index)
            except ValueError:
                print(f"[UTXOManager] ❌ Invalid output index in {tx_out_id}")
                return False

            # Retrieve the UTXO
            utxo = self.get_utxo(tx_out_id)
            if not utxo:
                print(f"[UTXOManager] ⚠️ UTXO not found: {tx_out_id}")
                return False

            # Check lock status
            if isinstance(utxo, dict):
                is_locked = utxo.get('locked', utxo.get('is_locked', False))
            else:
                is_locked = getattr(utxo, 'locked', False)

            if is_locked:
                print(f"[UTXOManager] ⚠️ UTXO already locked: {tx_out_id}")
                return True  # Consider already locked as success

            # Update lock status
            if isinstance(utxo, dict):
                utxo['locked'] = True
                utxo['is_locked'] = True  # Maintain backward compatibility
            else:
                utxo.locked = True

            # Store updated UTXO
            self.utxo_storage.put(
                tx_out_id,
                utxo.to_dict() if hasattr(utxo, 'to_dict') else utxo
            )
            print(f"[UTXOManager] 🔒 Locked UTXO: {tx_out_id}")
            return True

        except Exception as e:
            print(f"[UTXOManager] ❌ Failed to lock UTXO {tx_out_id}: {e}")
            return False

    def _lock_all_utxos_for_tx(self, tx_id: str) -> bool:
        """
        Lock all UTXOs for a given transaction ID with comprehensive error recovery
        and transaction type awareness.
        """
        try:
            # Convert bytes to hex if needed
            if isinstance(tx_id, bytes):
                tx_id = tx_id.hex()
                print(f"[UTXOManager] ℹ️ Converted bytes tx_id to hex: {tx_id}")

            # Determine transaction type
            tx_type = None
            for t_type, config in Constants.TRANSACTION_MEMPOOL_MAP.items():
                for prefix in config["prefixes"]:
                    if tx_id.startswith(prefix):
                        tx_type = t_type
                        break
                if tx_type:
                    break

            print(f"[UTXOManager] 🔒 Locking UTXOs for {tx_type or 'STANDARD'} tx: {tx_id}")
            
            # Get all UTXOs (handles both raw tx_id and utxo:tx_id:index formats)
            utxos = self.utxo_storage.get_all_utxos_by_tx_id(tx_id)
            if not utxos:
                print(f"[UTXOManager] ❌ No UTXOs found for {tx_id}")
                return False

            success_count = 0
            for utxo in utxos:
                utxo_id = None
                try:
                    # Handle both dict and object UTXO formats
                    if isinstance(utxo, dict):
                        utxo_id = f"utxo:{utxo['tx_id']}:{utxo['output_index']}"
                        if utxo.get('locked', False):
                            print(f"[UTXOManager] ⚠️ UTXO {utxo_id} already locked")
                            continue
                            
                        # Add type-specific metadata
                        if tx_type:
                            utxo['lock_reason'] = f"{tx_type} transaction"
                            utxo['lock_time'] = int(time.time())
                        utxo['locked'] = True
                    else:
                        utxo_id = utxo.tx_out_id
                        if utxo.locked:
                            print(f"[UTXOManager] ⚠️ UTXO {utxo_id} already locked")
                            continue
                        utxo.locked = True
                        if tx_type:
                            if not hasattr(utxo, 'metadata'):
                                utxo.metadata = {}
                            utxo.metadata.update({
                                'lock_reason': f"{tx_type} transaction",
                                'lock_time': int(time.time())
                            })

                    # Update UTXO in storage
                    if isinstance(utxo, dict):
                        self.utxo_storage.put(utxo_id, utxo)
                    else:
                        self.utxo_storage.put(utxo_id, utxo.to_dict())
                    
                    print(f"[UTXOManager] 🔒 Locked UTXO {utxo_id}")
                    success_count += 1
                    
                except Exception as e:
                    print(f"[UTXOManager] ⚠️ Failed to lock UTXO {utxo_id or 'UNKNOWN'}: {e}")
                    continue

            print(f"[UTXOManager] ✅ Locked {success_count}/{len(utxos)} UTXOs for {tx_id}")
            return success_count > 0

        except Exception as e:
            print(f"[UTXOManager] ❌ Failed to lock UTXOs for {tx_id}: {e}")
            return False

    def lock_selected_utxos(self, tx_out_ids: list):
        """
        Lock multiple UTXOs given a list of tx_out_ids (supporting both full and raw tx_id formats).
        Maintains backward compatibility with both 'locked' and 'is_locked' key formats.
        
        :param tx_out_ids: List of UTXO IDs to lock
        """
        if not isinstance(tx_out_ids, list) or not tx_out_ids:
            print("[UTXOManager ERROR] ❌ lock_selected_utxos: Invalid list of UTXO IDs.")
            return

        print(f"[UTXOManager INFO] 🔒 Locking {len(tx_out_ids)} UTXOs...")
        
        success_count = 0
        for tx_out_id in tx_out_ids:
            try:
                self.lock_utxo(tx_out_id)
                success_count += 1
            except Exception as e:
                print(f"[UTXOManager ERROR] ❌ Failed to lock UTXO {tx_out_id}: {e}")
        
        print(f"[UTXOManager INFO] ✅ Successfully locked {success_count}/{len(tx_out_ids)} UTXOs")


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







    def unlock_selected_utxos(self, tx_out_ids: list):
        """
        Unlock multiple UTXOs given a list of tx_out_ids (supporting both full and raw tx_id formats).
        Handles both 'locked' and 'is_locked' key formats for backward compatibility.
        
        :param tx_out_ids: List of UTXO IDs to unlock
        """
        if not isinstance(tx_out_ids, list) or not tx_out_ids:
            print("[UTXOManager ERROR] ❌ unlock_selected_utxos: Invalid list of UTXO IDs.")
            return

        print(f"[UTXOManager INFO] 🔓 Unlocking {len(tx_out_ids)} UTXOs...")
        
        success_count = 0
        for tx_out_id in tx_out_ids:
            try:
                if ":" in tx_out_id:  # Standard format
                    utxo = self.get_utxo(tx_out_id)
                    if not utxo:
                        print(f"[UTXOManager] ⚠️ Cannot unlock non-existent UTXO {tx_out_id}")
                        continue
                        
                    if isinstance(utxo, dict):
                        # Handle both key formats in dictionary
                        if 'locked' in utxo or 'is_locked' in utxo:
                            if not utxo.get('locked', utxo.get('is_locked', True)):
                                print(f"[UTXOManager] ⚠️ UTXO {tx_out_id} is already unlocked")
                                continue
                                
                            utxo['locked'] = False
                            utxo['is_locked'] = False
                            self.utxo_storage.put(tx_out_id, utxo)
                        else:
                            print(f"[UTXOManager] ❌ UTXO {tx_out_id} missing lock status fields")
                            continue
                    else:
                        # TransactionOut object
                        if not utxo.locked:
                            print(f"[UTXOManager] ⚠️ UTXO {tx_out_id} is already unlocked")
                            continue
                        utxo.locked = False
                        self.utxo_storage.put(tx_out_id, utxo.to_dict())
                        
                    success_count += 1
                    print(f"[UTXOManager] ✅ Unlocked UTXO {tx_out_id}")
                else:
                    # Fallback for raw tx_id
                    print(f"[UTXOManager] ⚠️ Raw tx_id format, unlocking all UTXOs for {tx_out_id}")
                    utxos = self.utxo_storage.get_all_utxos_by_tx_id(tx_out_id)
                    for utxo in utxos:
                        try:
                            if isinstance(utxo, dict):
                                if 'locked' in utxo or 'is_locked' in utxo:
                                    utxo['locked'] = False
                                    utxo['is_locked'] = False
                                    self.utxo_storage.put(
                                        f"{utxo['tx_id']}:{utxo['output_index']}",
                                        utxo
                                    )
                            else:
                                utxo.locked = False
                                self.utxo_storage.put(utxo.tx_out_id, utxo.to_dict())
                            success_count += 1
                        except Exception as e:
                            print(f"[UTXOManager] ❌ Failed to unlock UTXO: {e}")
            except Exception as e:
                print(f"[UTXOManager] ❌ Error processing UTXO {tx_out_id}: {e}")
        
        print(f"[UTXOManager] ✅ Successfully unlocked {success_count}/{len(tx_out_ids)} UTXOs")

    def validate_utxo(self, tx_out_id: str, amount: Decimal) -> bool:
        """
        Validate that a UTXO exists, is unlocked, and has sufficient balance.
        Supports both 'locked' and 'is_locked' key formats and handles raw tx_id fallback.
        """
        if not isinstance(tx_out_id, str) or not tx_out_id.strip():
            print(f"[UTXOManager] ❌ Invalid UTXO ID format: {tx_out_id}")
            return False

        if not isinstance(amount, Decimal) or amount <= 0:
            print(f"[UTXOManager] ❌ Invalid amount: {amount}")
            return False

        # Handle full tx_out_id format
        if ":" in tx_out_id:
            utxo = self.get_utxo(tx_out_id)
            if not utxo:
                print(f"[UTXOManager] ❌ UTXO {tx_out_id} not found")
                return False
                
            # Handle both object and dict formats
            if isinstance(utxo, dict):
                is_locked = utxo.get('locked', utxo.get('is_locked', False))
                utxo_amount = Decimal(str(utxo.get('amount', 0)))
            else:
                is_locked = utxo.locked
                utxo_amount = Decimal(str(utxo.amount))

            if is_locked:
                print(f"[UTXOManager] ❌ UTXO {tx_out_id} is locked")
                return False
                
            if utxo_amount < amount:
                print(f"[UTXOManager] ❌ Insufficient balance. Needed: {amount}, Available: {utxo_amount}")
                return False
                
            return True

        # Fallback for raw tx_id
        print(f"[UTXOManager] ⚠️ Raw tx_id format, validating all UTXOs for {tx_out_id}")
        try:
            utxos = self.utxo_storage.get_all_utxos_by_tx_id(tx_out_id)
            if not utxos:
                print(f"[UTXOManager] ❌ No UTXOs found for tx_id={tx_out_id}")
                return False

            total = Decimal(0)
            for utxo in utxos:
                try:
                    if isinstance(utxo, dict):
                        is_locked = utxo.get('locked', utxo.get('is_locked', False))
                        utxo_amount = Decimal(str(utxo.get('amount', 0)))
                    else:
                        is_locked = utxo.locked
                        utxo_amount = Decimal(str(utxo.amount))
                        
                    if not is_locked:
                        total += utxo_amount
                        if total >= amount:
                            return True
                except Exception as e:
                    print(f"[UTXOManager] ⚠️ Skipping invalid UTXO: {e}")
                    continue

            print(f"[UTXOManager] ❌ Combined balance insufficient. Needed: {amount}, Available: {total}")
            return False
            
        except Exception as e:
            print(f"[UTXOManager] ❌ Validation failed: {e}")
            return False