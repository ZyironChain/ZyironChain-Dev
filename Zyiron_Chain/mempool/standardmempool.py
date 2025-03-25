import sys
import os
import json
from decimal import Decimal
import time
from threading import Lock
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.storage.lmdatabase import LMDBManager
import hashlib
from Zyiron_Chain.utils.deserializer import Deserializer
import sys
import os

# Adjust Python path for project structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

from threading import Lock
from decimal import Decimal
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.storage.lmdatabase import LMDBManager

class StandardMempool:
    def __init__(self, utxo_storage, max_size_mb=None):
        """
        Initialize the Standard Mempool with LMDB-backed storage.

        :param utxo_storage: UTXOStorage instance for validating UTXOs
        :param max_size_mb: Optional override of max size in MB
        """
        self.utxo_storage = utxo_storage
        self.lock = Lock()

        # Use LMDB for transaction persistence
        self.lmdb = LMDBManager(Constants.get_db_path("mempool"))

        # Set maximum size
        self.max_size_mb = max_size_mb if max_size_mb is not None else Constants.MEMPOOL_MAX_SIZE_MB
        self.max_size_bytes = self.max_size_mb * 1024 * 1024  # Convert MB to bytes

        # Runtime parameters
        self.current_size_bytes = 0
        self.timeout = Constants.MEMPOOL_TRANSACTION_EXPIRY
        self.expiry_time = Constants.MEMPOOL_TRANSACTION_EXPIRY
        self.fee_model = FeeModel(max_supply=Decimal(Constants.MAX_SUPPLY))

        # Load persisted transactions on startup
        self._load_pending_transactions()

        print(f"[MEMPOOL] ✅ Initialized Standard Mempool with max size {self.max_size_mb} MB")


    def _load_pending_transactions(self):
        """Load pending transactions from LMDB into memory."""
        with self.lock:
            stored_txs = self.lmdb.get_all_transactions()  # Use the new method
            self.current_size_bytes = sum(tx["size"] for tx in stored_txs)

            # Ensure transaction IDs use double SHA3-384 hashing
            for tx in stored_txs:
                tx["tx_id"] = hashlib.sha3_384(tx["tx_id"].encode()).hexdigest()

            print(f"[MEMPOOL] Loaded {len(stored_txs)} pending transactions from LMDB.")

    def validate_transaction_inputs(self, transaction):
        """
        Validate transaction inputs using UTXOStorage.
        """
        with self.lock:
            for inp in transaction.inputs:
                utxo = self.utxo_storage.get_utxo(inp.tx_out_id)
                if not utxo:
                    print(f"[WARN] ⚠️ UTXO {inp.tx_out_id} not found in storage.")
                    return False
                if utxo.locked or utxo.amount < inp.amount:
                    print(f"[WARN] ⚠️ UTXO {inp.tx_out_id} is locked or has insufficient balance.")
                    return False
            return True

    def __len__(self):
        """Returns the number of transactions in the LMDB-backed Standard Mempool."""
        try:
            # Fetch all transaction keys in LMDB under the "mempool:" prefix
            transaction_keys = self.lmdb.get_keys_by_prefix("mempool:")
            return len(transaction_keys)
        except Exception as e:
            print(f"[ERROR] Failed to count transactions in mempool: {e}")
            return 0  # Return 0 if an error occurs

    def add_transaction(self, transaction, smart_contract, fee_model):
        """
        Add a transaction to the Standard Mempool and register it in the smart contract.

        Key Features:
        - Uses single SHA3-384 hashing for transaction IDs
        - Validates transaction structure and UTXO inputs
        - Enforces minimum fee requirements
        - Implements smart contract registration
        - LMDB-backed storage with size management

        Args:
            transaction (Transaction): Transaction object with:
                - tx_id: Transaction identifier
                - inputs: List of transaction inputs
                - outputs: List of transaction outputs
                - fee: Transaction fee
                - size: Transaction size in bytes
            smart_contract (DisputeResolutionContract): Instance for transaction registration
            fee_model (FeeModel): Model for calculating minimum fees

        Returns:
            bool: True if transaction was added successfully, False otherwise

        Raises:
            ValueError: If transaction validation fails
        """
        try:
            # Convert bytes tx_id to string if needed
            tx_id = transaction.tx_id
            if isinstance(tx_id, bytes):
                tx_id = tx_id.decode('utf-8')

            # Single SHA3-384 hashing for transaction ID
            hashed_tx_id = hashlib.sha3_384(tx_id.encode()).hexdigest()
            print(f"[StandardMempool] Processing transaction: {hashed_tx_id[:12]}...")

            # Reject Smart Transactions (S- prefix)
            if hashed_tx_id.startswith("S-"):
                print(f"[ERROR] Smart transactions not allowed in Standard Mempool: {hashed_tx_id}")
                return False

            # Validate transaction structure
            if not all([transaction.inputs, transaction.outputs]):
                print("[ERROR] Transaction must contain both inputs and outputs")
                return False

            # Validate UTXO inputs exist and are unspent
            if not self._validate_utxo_inputs(transaction.inputs):
                print("[ERROR] Invalid or spent UTXO inputs detected")
                return False

            # Calculate minimum required fee
            min_fee = fee_model.calculate_fee(
                payment_type="STANDARD",
                amount=sum(out.amount for out in transaction.outputs),
                tx_size=transaction.size,
                block_size=Constants.MAX_BLOCK_SIZE_MB
            )

            # Verify transaction fee meets minimum
            if transaction.fee < min_fee:
                print(f"[ERROR] Insufficient fee: {transaction.fee} < {min_fee}")
                return False

            # Check mempool capacity and evict if needed
            if self._exceeds_capacity(transaction.size):
                self._evict_low_priority_transactions(transaction.size)

            # Register with smart contract
            try:
                smart_contract.register_transaction(
                    transaction_id=hashed_tx_id,
                    parent_id=getattr(transaction, 'parent_id', None),
                    utxo_id=getattr(transaction, 'utxo_id', None),
                    sender=getattr(transaction, 'sender', None),
                    recipient=getattr(transaction, 'recipient', None),
                    amount=sum(out.amount for out in transaction.outputs),
                    fee=transaction.fee
                )
            except Exception as e:
                print(f"[ERROR] Smart contract registration failed: {str(e)}")
                return False

            # Store transaction in LMDB
            tx_data = {
                'tx_id': hashed_tx_id,
                'size': transaction.size,
                'fee': transaction.fee,
                'fee_per_byte': transaction.fee / transaction.size,
                'timestamp': int(time.time()),
                'inputs': [inp.tx_out_id for inp in transaction.inputs],
                'outputs': [out.script_pub_key for out in transaction.outputs],
                'status': 'PENDING'
            }

            with self.lock:
                self.lmdb.put(f"mempool:{hashed_tx_id}", json.dumps(tx_data).encode())
                self.current_size_bytes += transaction.size

            print(f"[SUCCESS] Transaction {hashed_tx_id[:12]} added to mempool")
            return True

        except Exception as e:
            print(f"[CRITICAL] Unexpected error: {str(e)}")
            return False

    def _validate_utxo_inputs(self, inputs):
        """Validate all transaction inputs exist and are unspent"""
        for tx_in in inputs:
            utxo = self.utxo_manager.get_utxo(tx_in.tx_out_id)
            if not utxo or utxo.get('spent', False):
                return False
        return True

    def _exceeds_capacity(self, tx_size):
        """Check if transaction would exceed mempool capacity"""
        return (self.current_size_bytes + tx_size) > self.max_size_bytes

    def _evict_low_priority_transactions(self, required_space):
        """Evict lowest fee-per-byte transactions to make space"""
        # Implementation of eviction logic
        pass

    def allocate_block_space(self, block_size_mb, current_block_height):
        """
        Allocate block space between Standard and Smart Mempools dynamically.

        :param block_size_mb: Current block size in MB.
        :param current_block_height: Current blockchain height for prioritization.
        :return: A list of transactions for block inclusion.
        """
        block_size_bytes = block_size_mb * 1024 * 1024  # Convert MB to bytes

        # Dynamically allocate space based on Constants
        instant_allocation = int(block_size_bytes * Constants.INSTANT_PAYMENT_ALLOCATION)
        standard_allocation = int(block_size_bytes * Constants.STANDARD_TRANSACTION_ALLOCATION)
        smart_allocation = int(block_size_bytes * Constants.BLOCK_ALLOCATION_SMART)

        # Fetch transactions dynamically using `Constants.TRANSACTION_MEMPOOL_MAP`
        instant_txs = self.get_pending_transactions(block_size_mb, transaction_type="INSTANT")
        standard_txs = self.get_pending_transactions(block_size_mb, transaction_type="STANDARD")
        smart_txs = self.smart_mempool.get_smart_transactions(block_size_mb, current_block_height)

        # Calculate allocated space
        total_instant = sum(tx.size for tx in instant_txs)
        total_standard = sum(tx.size for tx in standard_txs)
        total_smart = sum(tx.size for tx in smart_txs)

        # Dynamic reallocation of unused space
        remaining_space = max(0, block_size_bytes - (total_instant + total_standard + total_smart))
        if remaining_space > 0:
            overflow_txs = self.reallocate_space(remaining_space, current_block_height)
            return instant_txs + standard_txs + smart_txs + overflow_txs

        return instant_txs + standard_txs + smart_txs

    def get_pending_transactions(self, block_size_mb: float, transaction_type: str = "STANDARD") -> list:
        """
        Retrieve transactions for block inclusion, prioritizing high fees.
        
        :param block_size_mb: Block size in MB.
        :param transaction_type: "INSTANT" or "STANDARD".
        :return: List of transaction objects.
        """
        block_size_bytes = block_size_mb * 1024 * 1024  # Convert MB to bytes

        # Use Constants for dynamic space allocation
        allocation = (
            int(block_size_bytes * Constants.INSTANT_PAYMENT_ALLOCATION)
            if transaction_type == "INSTANT"
            else int(block_size_bytes * Constants.STANDARD_TRANSACTION_ALLOCATION)
        )

        # Fetch transaction prefixes dynamically
        transaction_prefixes = Constants.TRANSACTION_MEMPOOL_MAP.get(transaction_type, {}).get("prefixes", [])

        with self.lock:
            # Filter transactions dynamically based on prefix mappings
            filtered_txs = [
                tx for tx in self.lmdb.get_all_transactions()
                if any(tx["tx_id"].startswith(prefix) for prefix in transaction_prefixes)
            ]

            # Ensure transactions use double SHA3-384 hash format
            for tx in filtered_txs:
                tx["tx_id"] = hashlib.sha3_384(tx["tx_id"].encode()).hexdigest()

            # Sort transactions by highest fee-per-byte first
            sorted_txs = sorted(filtered_txs, key=lambda x: x["fee_per_byte"], reverse=True)

            # Select transactions that fit within allocated space
            selected_txs = []
            current_size = 0
            for tx_data in sorted_txs:
                tx_size = tx_data["size"]
                if current_size + tx_size > allocation:
                    break

                # Ensure the transaction meets the minimum fee requirement
                if tx_data["fee_per_byte"] >= Constants.MIN_TRANSACTION_FEE:
                    selected_txs.append(tx_data)
                    current_size += tx_size

            return selected_txs

    def restore_transactions(self, transactions):
        """
        Restore transactions back into the mempool if mining fails.

        :param transactions: List of transaction objects to restore.
        """
        with self.lock:
            for tx in transactions:
                # Ensure the transaction meets minimum fee requirements
                if tx.fee < Constants.MIN_TRANSACTION_FEE:
                    print(f"[WARN] Skipping restore for {tx.tx_id} - Below minimum fee requirement.")
                    continue

                # Ensure the mempool has enough space before adding the transaction
                if self.current_size_bytes + tx.size > Constants.MEMPOOL_MAX_SIZE_MB * 1024 * 1024:
                    print(f"[WARN] Skipping restore for {tx.tx_id} - Not enough space in mempool.")
                    continue  # Skip transaction if mempool is full

                if tx.tx_id not in self.transactions:
                    # Prevent division by zero error
                    fee_per_byte = tx.fee / tx.size if tx.size > 0 else 0

                    self.transactions[tx.tx_id] = {
                        "transaction": tx,
                        "timestamp": time.time(),
                        "fee_per_byte": fee_per_byte,
                        "status": "Pending"
                    }
                    self.current_size_bytes += tx.size
                    print(f"[MEMPOOL] Restored transaction {tx.tx_id} after failed mining attempt.")

    def evict_transactions(self, size_needed):
        """
        Evict low-fee transactions to make room for new ones.

        :param size_needed: The size of the new transaction that needs space in bytes.
        """
        with self.lock:
            # Dynamically adjust max mempool size from Constants
            max_mempool_size_bytes = Constants.MEMPOOL_MAX_SIZE_MB * 1024 * 1024

            # Sort transactions by lowest fee-per-byte (lowest priority first)
            sorted_txs = sorted(
                self.transactions.items(),
                key=lambda item: item[1]["fee_per_byte"]
            )

            while self.current_size_bytes + size_needed > max_mempool_size_bytes and sorted_txs:
                tx_id, tx_data = sorted_txs.pop(0)

                # Ensure we don’t evict high-fee transactions unnecessarily
                if tx_data["fee_per_byte"] >= Constants.MIN_TRANSACTION_FEE:
                    print(f"[WARN] Skipping eviction of high-fee transaction {tx_id}.")
                    continue  # Skip if transaction has a decent fee

                self.remove_transaction(tx_id)
                self.current_size_bytes -= tx_data["transaction"].size
                print(f"[INFO] Evicted transaction {tx_id} to free space.")

    def track_confirmation(self, transaction_id):
        """
        Track a transaction's confirmation status in the mempool.
        
        :param transaction_id: ID of the transaction to track.
        """
        with self.lock:
            transaction = self.transactions.get(transaction_id)
            if not transaction:
                print(f"[ERROR] Transaction {transaction_id} not found in mempool.")
                return

            confirmations = transaction.get("confirmations", 0)
            tx_type = transaction["transaction"].type.name if transaction["transaction"].type else "STANDARD"

            # Dynamically determine required confirmations from Constants
            required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(tx_type.upper(), Constants.TRANSACTION_CONFIRMATIONS["STANDARD"])

            # Check if the transaction is still pending or confirmed
            if confirmations < required_confirmations:
                transaction["confirmations"] += 1  # Simulate confirmation tracking
                print(f"[INFO] Transaction {transaction_id} pending ({transaction['confirmations']}/{required_confirmations} confirmations).")
            else:
                transaction["status"] = "Confirmed"
                print(f"[INFO] Transaction {transaction_id} has been fully confirmed.")

    def promote_child_to_parent(self, parent_id):
        """
        Promote the last child transaction to be the new parent if the current parent is confirmed.

        :param parent_id: ID of the confirmed parent transaction.
        :return: The new parent transaction ID if successful, else None.
        """
        with self.lock:
            parent_transaction = self.transactions.get(parent_id)
            if not parent_transaction:
                print(f"[ERROR] Parent transaction {parent_id} not found in mempool.")
                return None

            if parent_transaction["status"] != "Confirmed":
                print(f"[WARN] Parent transaction {parent_id} is not confirmed yet.")
                return None

            # Ensure children exist before promoting
            if not parent_transaction["children"]:
                print(f"[INFO] No children available to promote for parent {parent_id}.")
                return None

            # Sort children by timestamp to promote the **oldest** child
            sorted_children = sorted(
                parent_transaction["children"],
                key=lambda tx_id: self.transactions.get(tx_id, {}).get("timestamp", float('inf'))
            )

            if not sorted_children:
                print(f"[WARN] No valid children found for promotion under parent {parent_id}.")
                return None

            new_parent_id = sorted_children[0]  # Promote the oldest child

            # Update the new parent transaction status
            if new_parent_id in self.transactions:
                self.transactions[new_parent_id]["parent_id"] = None
                self.transactions[new_parent_id]["status"] = "Pending"

            # Remove reference from the old parent
            parent_transaction["children"].remove(new_parent_id)

            print(f"[INFO] ✅ Promoted transaction {new_parent_id} as the new parent of the chain.")
            return new_parent_id

    def cleanup_expired_transactions(self):
        """
        Remove transactions that have been in the mempool beyond the timeout or expiry time.
        """
        current_time = time.time()
        mempool_expiry = Constants.MEMPOOL_TRANSACTION_EXPIRY  # Use dynamic expiration from Constants

        with self.lock:
            expired_transactions = []

            for tx_hash, data in list(self.transactions.items()):
                tx_timestamp = data.get("timestamp", 0)  # Ensure timestamp exists, default to 0
                tx_age = current_time - tx_timestamp if tx_timestamp else float('inf')

                if tx_age > mempool_expiry:
                    expired_transactions.append(tx_hash)

            # Remove expired transactions and print their removal
            for tx_hash in expired_transactions:
                self.remove_transaction(tx_hash)
                print(f"[MEMPOOL] ❌ Removed expired transaction {tx_hash} (Exceeded {mempool_expiry}s).")

        print(f"[MEMPOOL] ✅ Cleanup complete: {len(expired_transactions)} transactions removed.")

    def remove_transaction(self, tx_id, smart_contract=None):
        """
        Remove a transaction from the mempool and update the smart contract.

        :param tx_id: Transaction ID to remove.
        :param smart_contract: Instance of a contract that may need to be notified (e.g., refund).
        """
        with self.lock:
            try:
                # Ensure `tx_id` is a string before encoding
                if isinstance(tx_id, bytes):
                    tx_id = tx_id.decode("utf-8")

                # Single SHA3-384 hashing of transaction ID
                single_hashed_tx_id = hashlib.sha3_384(tx_id.encode()).hexdigest()

                # Fetch transaction from LMDB
                transaction_data = self.lmdb.get(f"mempool:{single_hashed_tx_id}")
                if not transaction_data:
                    print(f"[MEMPOOL][WARN] ⚠️ Attempted to remove non-existent transaction {single_hashed_tx_id}.")
                    return

                transaction = json.loads(transaction_data)

                # Remove transaction from LMDB
                self.lmdb.delete(f"mempool:{single_hashed_tx_id}")

                # Notify smart contract if provided
                if smart_contract:
                    try:
                        smart_contract.refund_transaction(single_hashed_tx_id)
                        print(f"[MEMPOOL][INFO] 🔄 Transaction {single_hashed_tx_id} refunded in smart contract.")
                    except Exception as e:
                        print(f"[MEMPOOL][ERROR] ❌ Failed to refund transaction {single_hashed_tx_id} in smart contract: {e}")

                print(f"[MEMPOOL][INFO] ✅ Transaction {single_hashed_tx_id} successfully removed.")

            except Exception as e:
                print(f"[MEMPOOL][ERROR] ❌ Unexpected error while removing transaction {tx_id}: {str(e)}")

    def recommend_fees(self, block_size, payment_type):
        """
        Recommend transaction fees based on current mempool state and congestion levels.

        :param block_size: Current block size in MB.
        :param payment_type: Payment type ("Standard", "Smart", "Instant").
        :return: Recommended fee-per-byte and congestion level.
        """
        with self.lock:
            if payment_type not in Constants.TRANSACTION_MEMPOOL_MAP:
                print(f"[MEMPOOL][ERROR] ❌ Invalid payment type: {payment_type}. Defaulting to 'STANDARD'.")
                payment_type = "STANDARD"

            # Calculate total size of all transactions in mempool
            total_size = sum(
                tx["transaction"].size for tx in self.transactions.values()
                if hasattr(tx["transaction"], "size") and isinstance(tx["transaction"].size, (int, float))
            )

            # If no transactions, return minimum recommended fee
            if total_size == 0:
                print("[MEMPOOL][INFO] 🏦 No transactions in mempool. Returning minimum recommended fee.")
                return {
                    "congestion_level": "LOW",
                    "recommended_fee_per_byte": Constants.MIN_TRANSACTION_FEE
                }

            # Determine congestion level
            congestion_level = self.fee_model.get_congestion_level(block_size, payment_type, total_size)

            # Gather fee_per_byte from mempool
            fee_per_byte_list = [
                tx["fee_per_byte"] for tx in self.transactions.values()
                if isinstance(tx.get("fee_per_byte"), (int, float))
            ]

            if not fee_per_byte_list:
                print("[MEMPOOL][WARN] ⚠️ No transactions with valid fee_per_byte found. Using minimum transaction fee.")
                return {
                    "congestion_level": congestion_level,
                    "recommended_fee_per_byte": Constants.MIN_TRANSACTION_FEE
                }

            if len(fee_per_byte_list) > 1:
                fee_per_byte_list.sort()

            recommended_fee = self.fee_model.calculate_fee(
                block_size, payment_type, total_size, max(fee_per_byte_list)
            )

            recommended_fee_per_byte = recommended_fee / total_size if total_size > 0 else Constants.MIN_TRANSACTION_FEE

            print(f"[MEMPOOL][INFO] 💰 Recommended Fee for {payment_type}: {recommended_fee_per_byte:.8f} (Congestion: {congestion_level})")

            return {
                "congestion_level": congestion_level,
                "recommended_fee_per_byte": recommended_fee_per_byte
            }

    def get_total_size(self):
        """
        Calculate the total size of all transactions in the mempool.
        :return: Total size in bytes.
        """
        with self.lock:
            try:
                valid_transactions = [
                    tx["transaction"].size for tx in self.transactions.values()
                    if hasattr(tx["transaction"], "size") and isinstance(tx["transaction"].size, (int, float))
                ]
                total_size = sum(valid_transactions) if valid_transactions else 0
                print(f"[MEMPOOL][INFO] 📦 Current Mempool Size: {total_size} bytes "
                      f"(Max: {Constants.MEMPOOL_MAX_SIZE_MB * 1024 * 1024} bytes)")
                return total_size

            except Exception as e:
                print(f"[ERROR] ❌ Failed to calculate mempool size: {e}")
                return 0

    def trigger_dispute(self, tx_id, smart_contract):
        """
        Trigger a dispute for a transaction.
        """
        with self.lock:
            # Ensure the transaction exists
            transaction = self.transactions.get(tx_id)
            if not transaction:
                print(f"[ERROR] ❌ Transaction {tx_id} not found in the mempool. Cannot trigger dispute.")
                return False

            if transaction.get("status") == "Dispute":
                print(f"[WARN] ⚠️ Dispute already triggered for transaction {tx_id}. Skipping.")
                return False

            try:
                current_time = time.time()
                tx_age = current_time - transaction["timestamp"]
                if tx_age > Constants.DISPUTE_RESOLUTION_TTL:
                    print(f"[WARN] ⏳ Transaction {tx_id} exceeded dispute time limit "
                          f"({Constants.DISPUTE_RESOLUTION_TTL}s). Skipping.")
                    return False

                dispute_data = smart_contract.trigger_dispute(tx_id)
                self.transactions[tx_id]["status"] = "Dispute"
                print(f"[INFO] ⚖️ Dispute successfully triggered for transaction {tx_id}: {dispute_data}")
                return True

            except Exception as e:
                print(f"[ERROR] ❌ Failed to trigger dispute for transaction {tx_id}: {e}")
                return False

    def rebroadcast_transaction(self, tx_id, smart_contract):
        """
        Rebroadcast a transaction with an increased fee.

        :param tx_id: The transaction ID to rebroadcast.
        :param smart_contract: Instance of the DisputeResolutionContract or similar.
        :return: True if the transaction was rebroadcasted, False otherwise.
        """
        with self.lock:
            try:
                if isinstance(tx_id, bytes):
                    tx_id = tx_id.decode("utf-8")

                single_hashed_tx_id = hashlib.sha3_384(tx_id.encode()).hexdigest()
                transaction_data = self.lmdb.get(f"mempool:{single_hashed_tx_id}")
                if not transaction_data:
                    print(f"[ERROR] ❌ Transaction {single_hashed_tx_id} not found in the mempool. Cannot rebroadcast.")
                    return False

                transaction = json.loads(transaction_data)
                if transaction.get("status") == "Confirmed":
                    print(f"[WARN] ⚠️ Transaction {single_hashed_tx_id} is already confirmed. Rebroadcasting skipped.")
                    return False

                increment_factor = Constants.REBROADCAST_FEE_INCREASE
                if increment_factor <= 1.0:
                    print(f"[ERROR] ❌ Invalid increment factor {increment_factor} for transaction {single_hashed_tx_id}. Must be > 1.0.")
                    return False

                old_fee = transaction.get("fee", 0)
                new_fee = old_fee * increment_factor
                transaction["fee"] = new_fee

                self.lmdb.put(f"mempool:{single_hashed_tx_id}", json.dumps(transaction))
                smart_contract.rebroadcast_transaction(single_hashed_tx_id, new_fee)

                print(f"[INFO] ✅ Transaction {single_hashed_tx_id} rebroadcasted with new fee: {new_fee:.8f} "
                      f"(Old Fee: {old_fee:.8f})")
                return True

            except Exception as e:
                print(f"[ERROR] ❌ Failed to rebroadcast transaction {tx_id}: {e}")
                return False
            




    def get_transaction(self, tx_id: str):
        """Retrieve and deserialize a Standard Transaction from the mempool."""
        data = self.lmdb.get(f"mempool:{tx_id}")
        return Deserializer().deserialize(data) if data else None

