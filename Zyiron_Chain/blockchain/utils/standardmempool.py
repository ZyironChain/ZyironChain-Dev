import sys
import os


# Add the project root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))




import json

from decimal import Decimal
import time
from threading import Lock
from Zyiron_Chain.transactions.fees import FeeModel

import logging

# Remove all existing handlers (prevents log conflicts across modules)
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Set up clean logging for this module
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

log = logging.getLogger(__name__)  # Each module gets its own logger

log.info(f"{__name__} logger initialized.")

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.blockchain.utils.hashing import Hashing
# Ensure this is at the very top of your script, before any other code
from Zyiron_Chain.database.lmdatabase import LMDBManager
import hashlib
class StandardMempool:
    def __init__(self, poc, max_size_mb=None):
        """
        Initialize the Standard Mempool with LMDB-backed storage.

        :param poc: PoC instance for blockchain storage
        :param max_size_mb: Optional override of max size in MB
        """
        self.poc = poc
        self.lock = Lock()
        
        # ✅ Use LMDB for transaction persistence, and fetch the correct DB path using Constants.get_db_path()
        self.lmdb = LMDBManager(Constants.get_db_path("mempool"))

        # ✅ Allow size override while maintaining Constants default
        self.max_size_mb = max_size_mb if max_size_mb is not None else Constants.MEMPOOL_MAX_SIZE_MB
        self.max_size_bytes = self.max_size_mb * 1024 * 1024  # Convert MB to bytes
        
        self.current_size_bytes = 0
        self.timeout = Constants.MEMPOOL_TRANSACTION_EXPIRY
        self.expiry_time = Constants.MEMPOOL_TRANSACTION_EXPIRY
        self.fee_model = FeeModel(max_supply=Decimal(Constants.MAX_SUPPLY))

        # ✅ Load existing transactions from LMDB on initialization
        self._load_pending_transactions()

        logging.info(f"[MEMPOOL] Initialized Standard Mempool with max size {self.max_size_mb} MB")

    def _load_pending_transactions(self):
        """Load pending transactions from LMDB into memory, ensuring double SHA3-384 hash compatibility."""
        with self.lock:
            stored_txs = self.lmdb.get_all_transactions()
            self.current_size_bytes = sum(tx["size"] for tx in stored_txs)

            # ✅ Ensure transaction IDs use double SHA3-384 hashing
            for tx in stored_txs:
                tx["tx_id"] = hashlib.sha3_384(tx["tx_id"].encode()).hexdigest()


            logging.info(f"[MEMPOOL] Loaded {len(stored_txs)} pending transactions from LMDB.")


    def __len__(self):
        """Returns the number of transactions in the LMDB-backed Standard Mempool."""
        try:
            # ✅ Fetch all transaction keys in LMDB under the "mempool:" prefix
            transaction_keys = self.lmdb.get_keys_by_prefix("mempool:")
            return len(transaction_keys)
        except Exception as e:
            logging.error(f"[ERROR] Failed to count transactions in mempool: {e}")
            return 0  # Return 0 if an error occurs


    def add_transaction(self, transaction, smart_contract, fee_model):
        """
        Add a transaction to the Standard Mempool and register it in the smart contract.

        :param transaction: Transaction object with tx_id, fee, size, tx_inputs, and tx_outputs attributes.
        :param smart_contract: Instance of the DisputeResolutionContract.
        :param fee_model: Fee model to calculate minimum acceptable fees.
        :return: True if the transaction was added, False otherwise.
        """
        # ✅ Compute double-hashed transaction ID
        transaction.tx_id = hashlib.sha3_384(transaction.tx_id.encode()).hexdigest()


        # 🚫 Reject Smart Transactions
        if transaction.tx_id.startswith("S-"):
            logging.error(f"[ERROR] Smart Transactions (S-) are not allowed in Standard Mempool. Rejected: {transaction.tx_id}")
            return False

        # 🚫 Validate transaction structure
        if not transaction.inputs or not transaction.outputs:
            logging.error(f"[ERROR] Invalid Transaction {transaction.tx_id}: Must have at least one input and one output.")
            return False

        # 🚫 Ensure all transaction inputs exist in LMDB UTXO set
        if not self.validate_transaction_inputs(transaction):
            logging.warning(f"[WARN] Transaction {transaction.tx_id} rejected: Missing valid UTXO inputs.")
            return False

        transaction_size = transaction.size

        # ✅ Calculate the minimum required fee using Constants
        min_fee_required = fee_model.calculate_fee(
            payment_type="Standard",
            amount=sum(out.amount for out in transaction.outputs),
            tx_size=transaction.size,
            block_size=Constants.MAX_BLOCK_SIZE_BYTES
        )

        # 🚫 Check for insufficient fees
        if transaction.fee < min_fee_required:
            logging.error(f"[ERROR] Transaction {transaction.tx_id} rejected due to insufficient fee. Required: {min_fee_required}, Provided: {transaction.fee}")
            return False

        # 🚫 Check if Mempool is full before adding
        if self.current_size_bytes + transaction_size > self.max_size_bytes:
            logging.info("[INFO] Standard Mempool is full. Evicting low-fee transactions...")
            self.evict_transactions(transaction_size)

        # ✅ Register transaction in Dispute Resolution Contract
        try:
            smart_contract.register_transaction(
                transaction_id=transaction.tx_id,
                parent_id=getattr(transaction, "parent_id", None),
                utxo_id=getattr(transaction, "utxo_id", None),
                sender=getattr(transaction, "sender", None),
                recipient=getattr(transaction, "recipient", None),
                amount=transaction.amount,
                fee=transaction.fee
            )
            logging.info(f"[INFO] Transaction {transaction.tx_id} registered in smart contract.")
        except KeyError as e:
            logging.error(f"[ERROR] Missing transaction field during registration: {e}")
            return False
        except Exception as e:
            logging.error(f"[ERROR] Failed to register transaction in smart contract: {e}")
            return False

        # ✅ Add transaction to LMDB-backed Mempool
        with self.lock:
            self.lmdb.put(f"mempool:{transaction.tx_id}", json.dumps({
                "tx_id": transaction.tx_id,
                "size": transaction_size,
                "fee": transaction.fee,
                "fee_per_byte": transaction.fee / transaction_size,
                "timestamp": time.time(),
                "parents": [hashlib.sha3_384(inp.tx_out_id.encode()).hexdigest() for inp in transaction.inputs],

                "children": [],
                "status": "Pending"
            }))

            self.current_size_bytes += transaction_size

        logging.info(f"[INFO] ✅ Transaction {transaction.tx_id} successfully added to LMDB-backed Standard Mempool.")
        return True




    def allocate_block_space(self, block_size_mb, current_block_height):
        """
        Allocate block space between Standard and Smart Mempools dynamically.

        :param block_size_mb: Current block size in MB.
        :param current_block_height: Current blockchain height for prioritization.
        :return: A list of transactions for block inclusion.
        """
        block_size_bytes = block_size_mb * 1024 * 1024  # Convert MB to bytes

        # ✅ Dynamically allocate space based on Constants
        instant_allocation = int(block_size_bytes * Constants.INSTANT_PAYMENT_ALLOCATION)
        standard_allocation = int(block_size_bytes * Constants.STANDARD_TRANSACTION_ALLOCATION)
        smart_allocation = int(block_size_bytes * Constants.BLOCK_ALLOCATION_SMART)

        # ✅ Fetch transactions dynamically using `Constants.TRANSACTION_MEMPOOL_MAP`
        instant_txs = self.get_pending_transactions(block_size_mb, transaction_type="INSTANT")
        standard_txs = self.get_pending_transactions(block_size_mb, transaction_type="STANDARD")
        smart_txs = self.smart_mempool.get_smart_transactions(block_size_mb, current_block_height)

        # ✅ Calculate allocated space
        total_instant = sum(tx.size for tx in instant_txs)
        total_standard = sum(tx.size for tx in standard_txs)
        total_smart = sum(tx.size for tx in smart_txs)

        # ✅ Dynamic reallocation of unused space
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

        # ✅ Use Constants for dynamic space allocation
        allocation = (
            int(block_size_bytes * Constants.INSTANT_PAYMENT_ALLOCATION)
            if transaction_type == "INSTANT"
            else int(block_size_bytes * Constants.STANDARD_TRANSACTION_ALLOCATION)
        )

        # ✅ Fetch transaction prefixes dynamically
        transaction_prefixes = Constants.TRANSACTION_MEMPOOL_MAP.get(transaction_type, {}).get("prefixes", [])

        with self.lock:
            # ✅ Filter transactions dynamically based on prefix mappings
            filtered_txs = [
                tx for tx in self.lmdb.get_all_transactions()
                if any(tx["tx_id"].startswith(prefix) for prefix in transaction_prefixes)
            ]

            # ✅ Ensure transactions use double SHA3-384 hash format
            for tx in filtered_txs:
                tx["tx_id"] = hashlib.sha3_384(tx["tx_id"].encode()).hexdigest()


            # ✅ Sort transactions by highest fee-per-byte first
            sorted_txs = sorted(filtered_txs, key=lambda x: x["fee_per_byte"], reverse=True)

            # ✅ Select transactions that fit within allocated space
            selected_txs = []
            current_size = 0
            for tx_data in sorted_txs:
                tx_size = tx_data["size"]
                if current_size + tx_size > allocation:
                    break

                # ✅ Ensure the transaction meets the minimum fee requirement
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
                # ✅ Ensure the transaction meets minimum fee requirements
                if tx.fee < Constants.MIN_TRANSACTION_FEE:
                    logging.warning(f"[WARN] Skipping restore for {tx.tx_id} - Below minimum fee requirement.")
                    continue

                # ✅ Ensure the mempool has enough space before adding the transaction
                if self.current_size_bytes + tx.size > Constants.MEMPOOL_MAX_SIZE_MB * 1024 * 1024:
                    logging.warning(f"[WARN] Skipping restore for {tx.tx_id} - Not enough space in mempool.")
                    continue  # Skip transaction if mempool is full

                if tx.tx_id not in self.transactions:
                    # ✅ Prevent division by zero error
                    fee_per_byte = tx.fee / tx.size if tx.size > 0 else 0

                    self.transactions[tx.tx_id] = {
                        "transaction": tx,
                        "timestamp": time.time(),
                        "fee_per_byte": fee_per_byte,
                        "status": "Pending"
                    }
                    self.current_size_bytes += tx.size
                    logging.info(f"[MEMPOOL] Restored transaction {tx.tx_id} after failed mining attempt.")


    def evict_transactions(self, size_needed):
        """
        Evict low-fee transactions to make room for new ones.

        :param size_needed: The size of the new transaction that needs space in bytes.
        """
        with self.lock:
            # ✅ Dynamically adjust max mempool size from Constants
            max_mempool_size_bytes = Constants.MEMPOOL_MAX_SIZE_MB * 1024 * 1024

            # ✅ Sort transactions by lowest fee-per-byte (lowest priority first)
            sorted_txs = sorted(
                self.transactions.items(),
                key=lambda item: item[1]["fee_per_byte"]
            )

            while self.current_size_bytes + size_needed > max_mempool_size_bytes and sorted_txs:
                tx_id, tx_data = sorted_txs.pop(0)

                # ✅ Ensure we don’t evict high-fee transactions unnecessarily
                if tx_data["fee_per_byte"] >= Constants.MIN_TRANSACTION_FEE:
                    logging.warning(f"[WARN] Skipping eviction of high-fee transaction {tx_id}.")
                    continue  # Skip if transaction has a decent fee

                self.remove_transaction(tx_id)
                self.current_size_bytes -= tx_data["transaction"].size
                logging.info(f"[INFO] Evicted transaction {tx_id} to free space.")


    def track_confirmation(self, transaction_id):
        """
        Track a transaction's confirmation status in the mempool.
        
        :param transaction_id: ID of the transaction to track.
        """
        with self.lock:
            transaction = self.transactions.get(transaction_id)
            if not transaction:
                logging.error(f"[ERROR] Transaction {transaction_id} not found in mempool.")
                return

            confirmations = transaction.get("confirmations", 0)
            tx_type = transaction["transaction"].type.name if transaction["transaction"].type else "STANDARD"

            # ✅ Dynamically determine required confirmations from Constants
            required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(tx_type.upper(), Constants.TRANSACTION_CONFIRMATIONS["STANDARD"])

            # ✅ Check if the transaction is still pending or confirmed
            if confirmations < required_confirmations:
                transaction["confirmations"] += 1  # Simulate confirmation tracking
                logging.info(f"[INFO] Transaction {transaction_id} pending ({transaction['confirmations']}/{required_confirmations} confirmations).")
            else:
                transaction["status"] = "Confirmed"
                logging.info(f"[INFO] Transaction {transaction_id} has been fully confirmed.")



    def promote_child_to_parent(self, parent_id):
        """
        Promote the last child transaction to be the new parent if the current parent is confirmed.

        :param parent_id: ID of the confirmed parent transaction.
        :return: The new parent transaction ID if successful, else None.
        """
        with self.lock:
            parent_transaction = self.transactions.get(parent_id)
            if not parent_transaction:
                logging.error(f"[ERROR] Parent transaction {parent_id} not found in mempool.")
                return None

            if parent_transaction["status"] != "Confirmed":
                logging.warning(f"[WARN] Parent transaction {parent_id} is not confirmed yet.")
                return None

            # ✅ Ensure children exist before promoting
            if not parent_transaction["children"]:
                logging.info(f"[INFO] No children available to promote for parent {parent_id}.")
                return None

            # ✅ Sort children by timestamp to promote the **oldest** child
            sorted_children = sorted(
                parent_transaction["children"],
                key=lambda tx_id: self.transactions.get(tx_id, {}).get("timestamp", float('inf'))
            )

            if not sorted_children:
                logging.warning(f"[WARN] No valid children found for promotion under parent {parent_id}.")
                return None

            new_parent_id = sorted_children[0]  # Promote the oldest child

            # ✅ Update the new parent transaction status
            if new_parent_id in self.transactions:
                self.transactions[new_parent_id]["parent_id"] = None
                self.transactions[new_parent_id]["status"] = "Pending"

            # ✅ Remove reference from the old parent
            parent_transaction["children"].remove(new_parent_id)

            logging.info(f"[INFO] ✅ Promoted transaction {new_parent_id} as the new parent of the chain.")
            return new_parent_id


    def cleanup_expired_transactions(self):
        """
        Remove transactions that have been in the mempool beyond the timeout or expiry time.
        """
        current_time = time.time()
        mempool_expiry = Constants.MEMPOOL_TRANSACTION_EXPIRY  # ✅ Use dynamic expiration from Constants

        with self.lock:
            expired_transactions = []

            for tx_hash, data in list(self.transactions.items()):  # ✅ Convert to list for safe iteration
                tx_timestamp = data.get("timestamp", 0)  # ✅ Ensure timestamp exists, default to 0

                # ✅ Compute transaction age safely
                tx_age = current_time - tx_timestamp if tx_timestamp else float('inf')

                if tx_age > mempool_expiry:
                    expired_transactions.append(tx_hash)

            # ✅ Remove expired transactions and log their removal
            for tx_hash in expired_transactions:
                self.remove_transaction(tx_hash)
                logging.info(f"[MEMPOOL] ❌ Removed expired transaction {tx_hash} (Exceeded {mempool_expiry}s).")

        logging.info(f"[MEMPOOL] ✅ Cleanup complete: {len(expired_transactions)} transactions removed.")


    def remove_transaction(self, tx_id, smart_contract):
        """
        Remove a transaction from the mempool and update the smart contract.

        :param tx_id: Transaction ID to remove.
        :param smart_contract: Instance of DisputeResolutionContract.
        """
        with self.lock:
            # ✅ Ensure transaction ID uses double hash
            tx_id_hashed = hashlib.sha3_384(tx_id.encode()).hexdigest()


            # ✅ Fetch transaction from LMDB
            transaction_data = self.lmdb.get(f"mempool:{tx_id_hashed}")
            if not transaction_data:
                logging.warning(f"[MEMPOOL] ⚠️ Attempted to remove non-existent transaction {tx_id_hashed}.")
                return

            transaction = json.loads(transaction_data)

            # ✅ Remove transaction from LMDB
            self.lmdb.delete(f"mempool:{tx_id_hashed}")

            # ✅ Notify smart contract
            if smart_contract:
                try:
                    smart_contract.refund_transaction(tx_id_hashed)
                    logging.info(f"[MEMPOOL] 🔄 Transaction {tx_id_hashed} refunded in smart contract.")
                except Exception as e:
                    logging.error(f"[MEMPOOL] ❌ Failed to refund transaction {tx_id_hashed} in smart contract: {e}")

            logging.info(f"[MEMPOOL] ✅ Transaction {tx_id_hashed} successfully removed.")



    def recommend_fees(self, block_size, payment_type):
        """
        Recommend transaction fees based on current mempool state and congestion levels.

        :param block_size: Current block size in MB.
        :param payment_type: Payment type ("Standard", "Smart", "Instant").
        :return: Recommended fee-per-byte and congestion level.
        """
        with self.lock:
            # ✅ Validate payment type using Constants
            if payment_type not in Constants.TRANSACTION_MEMPOOL_MAP:
                logging.error(f"[MEMPOOL] ❌ Invalid payment type: {payment_type}. Defaulting to 'STANDARD'.")
                payment_type = "STANDARD"

            # ✅ Calculate total size of all transactions in mempool
            total_size = sum(
                tx["transaction"].size for tx in self.transactions.values()
                if hasattr(tx["transaction"], "size") and isinstance(tx["transaction"].size, (int, float))
            )

            # ✅ Prevent division by zero if no transactions are in the mempool
            if total_size == 0:
                logging.info("[MEMPOOL] 🏦 No transactions in mempool. Returning minimum recommended fee.")
                return {
                    "congestion_level": "LOW",
                    "recommended_fee_per_byte": Constants.MIN_TRANSACTION_FEE
                }

            # ✅ Determine congestion level dynamically
            congestion_level = self.fee_model.get_congestion_level(block_size, payment_type, total_size)

            # ✅ Ensure the fee list is valid before using max()
            fee_per_byte_list = [
                tx["fee_per_byte"] for tx in self.transactions.values()
                if isinstance(tx.get("fee_per_byte"), (int, float))
            ]

            if not fee_per_byte_list:
                logging.warning("[MEMPOOL] ⚠️ No transactions with valid fee_per_byte found. Using minimum transaction fee.")
                return {
                    "congestion_level": congestion_level,
                    "recommended_fee_per_byte": Constants.MIN_TRANSACTION_FEE
                }

            # ✅ Sort fee list only if it contains multiple elements
            if len(fee_per_byte_list) > 1:
                fee_per_byte_list.sort()

            recommended_fee = self.fee_model.calculate_fee(
                block_size, payment_type, total_size, max(fee_per_byte_list)
            )

            # ✅ Prevent division by zero and ensure a reasonable fee-per-byte recommendation
            recommended_fee_per_byte = (
                recommended_fee / total_size if total_size > 0 else Constants.MIN_TRANSACTION_FEE
            )

            logging.info(f"[MEMPOOL] 💰 Recommended Fee for {payment_type}: {recommended_fee_per_byte:.8f} (Congestion: {congestion_level})")

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
                # ✅ Filter valid transactions that have a size attribute
                valid_transactions = [
                    tx["transaction"].size for tx in self.transactions.values()
                    if hasattr(tx["transaction"], "size") and isinstance(tx["transaction"].size, (int, float))
                ]

                # ✅ Calculate total size safely
                total_size = sum(valid_transactions) if valid_transactions else 0

                # ✅ Log the current mempool size
                logging.info(f"[MEMPOOL] 📦 Current Mempool Size: {total_size} bytes (Max: {Constants.MEMPOOL_MAX_SIZE_MB * 1024 * 1024} bytes)")

                return total_size

            except Exception as e:
                logging.error(f"[ERROR] ❌ Failed to calculate mempool size: {e}")
                return 0  # ✅ Return 0 if an error occurs


    def trigger_dispute(self, tx_id, smart_contract):
        """
        Trigger a dispute for a transaction.
        """
        with self.lock:
            # ✅ Ensure the transaction exists
            transaction = self.transactions.get(tx_id)
            if not transaction:
                logging.error(f"[ERROR] ❌ Transaction {tx_id} not found in the mempool. Cannot trigger dispute.")
                return False  # ✅ Return False to indicate failure

            # ✅ Prevent redundant dispute triggers
            if transaction.get("status") == "Dispute":
                logging.warning(f"[WARN] ⚠️ Dispute already triggered for transaction {tx_id}. Skipping.")
                return False

            try:
                # ✅ Ensure the dispute is within allowed time (Dynamic TTL)
                current_time = time.time()
                tx_age = current_time - transaction["timestamp"]
                if tx_age > Constants.DISPUTE_RESOLUTION_TTL:
                    logging.warning(f"[WARN] ⏳ Transaction {tx_id} exceeded dispute time limit ({Constants.DISPUTE_RESOLUTION_TTL}s). Skipping.")
                    return False

                # ✅ Trigger dispute in smart contract
                dispute_data = smart_contract.trigger_dispute(tx_id)

                # ✅ Update transaction status after triggering a dispute
                self.transactions[tx_id]["status"] = "Dispute"

                logging.info(f"[INFO] ⚖️ Dispute successfully triggered for transaction {tx_id}: {dispute_data}")
                return True  # ✅ Return True to indicate success

            except Exception as e:
                logging.error(f"[ERROR] ❌ Failed to trigger dispute for transaction {tx_id}: {e}")
                return False  # ✅ Return False if an error occurs





    def rebroadcast_transaction(self, tx_id, smart_contract):
        """
        Rebroadcast a transaction with an increased fee.
        
        :param tx_id: The transaction ID to rebroadcast.
        :param smart_contract: Instance of the DisputeResolutionContract.
        """
        with self.lock:
            # ✅ Ensure transaction ID is double-hashed
            tx_id_hashed = hashlib.sha3_384(tx_id.encode()).hexdigest()


            # ✅ Fetch transaction from LMDB
            transaction_data = self.lmdb.get(f"mempool:{tx_id_hashed}")
            if not transaction_data:
                logging.error(f"[ERROR] Transaction {tx_id_hashed} not found in the mempool. Cannot rebroadcast.")
                return False

            transaction = json.loads(transaction_data)

            # ✅ Prevent rebroadcasting if transaction is already confirmed
            if transaction.get("status") == "Confirmed":
                logging.warning(f"[WARN] Transaction {tx_id_hashed} is already confirmed. Rebroadcasting skipped.")
                return False

            try:
                # ✅ Fetch dynamic increment factor from Constants
                increment_factor = Constants.REBROADCAST_FEE_INCREASE
                if increment_factor <= 1.0:
                    logging.error(f"[ERROR] Invalid increment factor {increment_factor} for transaction {tx_id_hashed}. Must be > 1.0.")
                    return False

                # ✅ Increase the transaction fee dynamically
                old_fee = transaction["fee"]
                new_fee = old_fee * increment_factor
                transaction["fee"] = new_fee

                # ✅ Update transaction in LMDB
                self.lmdb.put(f"mempool:{tx_id_hashed}", json.dumps(transaction))

                # ✅ Call smart contract to rebroadcast transaction
                smart_contract.rebroadcast_transaction(tx_id_hashed, new_fee)

                logging.info(f"[INFO] Transaction {tx_id_hashed} rebroadcasted with new fee: {new_fee:.8f} (Old Fee: {old_fee:.8f})")
                return True  # ✅ Success

            except Exception as e:
                logging.error(f"[ERROR] Failed to rebroadcast transaction {tx_id_hashed}: {e}")
                return False  # ✅ Failure
