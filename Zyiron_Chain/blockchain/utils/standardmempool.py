import sys
import os


# Add the project root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))








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

# Ensure this is at the very top of your script, before any other code

class StandardMempool:
    def __init__(self, poc, max_size_mb=None):  # ✅ Add max_size_mb parameter
        """
        Initialize the Standard Mempool.
        
        :param poc: PoC instance for blockchain storage
        :param max_size_mb: Optional override of max size in MB
        """
        self.poc = poc
        self.transactions = {}
        self.lock = Lock()
        
        # ✅ Allow size override while maintaining Constants default
        self.max_size_mb = max_size_mb if max_size_mb is not None else Constants.MEMPOOL_MAX_SIZE_MB
        self.max_size_bytes = self.max_size_mb * 1024 * 1024  # Convert MB to bytes
        
        self.current_size_bytes = 0
        self.timeout = Constants.MEMPOOL_TRANSACTION_EXPIRY
        self.expiry_time = Constants.MEMPOOL_TRANSACTION_EXPIRY
        self.fee_model = FeeModel(max_supply=Decimal(Constants.MAX_SUPPLY))

        logging.info(f"[MEMPOOL] Initialized Standard Mempool with max size {self.max_size_mb} MB")
        
    def __len__(self):
        """Returns the number of transactions in the mempool."""
        return len(self.transactions)


    def add_transaction(self, transaction, smart_contract, fee_model):
        """
        Add a transaction to the Standard Mempool and register it in the smart contract.

        :param transaction: Transaction object with tx_id, fee, size, tx_inputs, and tx_outputs attributes.
        :param smart_contract: Instance of the DisputeResolutionContract.
        :param fee_model: Fee model to calculate minimum acceptable fees.
        :return: True if the transaction was added, False otherwise.
        """
        # 🚫 Reject Smart Transactions
        if transaction.tx_id.startswith("S-"):
            logging.error(f"[ERROR] Smart Transactions (S-) are not allowed in Standard Mempool. Rejected: {transaction.tx_id}")
            return False

        # 🚫 Validate transaction structure
        if not transaction.inputs or not transaction.outputs:
            logging.error(f"[ERROR] Invalid Transaction {transaction.tx_id}: Must have at least one input and one output.")
            return False

        # 🚫 Ensure all transaction inputs exist in PoC
        if not self.validate_transaction_inputs(transaction):
            logging.warning(f"[WARN] Transaction {transaction.tx_id} rejected: Missing valid UTXO inputs.")
            return False

        # 🚫 Prevent duplicate transactions
        if transaction.tx_id in self.transactions:
            logging.warning(f"[WARN] Transaction {transaction.tx_id} already exists in Standard Mempool.")
            return False

        transaction_size = transaction.size

        # ✅ Calculate the minimum required fee using Constants.MAX_BLOCK_SIZE_BYTES
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

        # ✅ Add transaction to Mempool
        with self.lock:
            self.transactions[transaction.tx_id] = {
                "transaction": transaction,
                "timestamp": time.time(),
                "fee_per_byte": transaction.fee / transaction_size,
                "parents": transaction.tx_inputs,
                "children": set(),
                "status": "Pending"
            }
            self.current_size_bytes += transaction_size

        logging.info(f"[INFO] Transaction {transaction.tx_id} successfully added to the Standard Mempool.")
        return True


    def is_utxo_available(self, tx_out_id):
        """Check if a UTXO exists and is available in the PoC database."""
        utxo = self.poc.get_utxo(tx_out_id)
        return utxo is not None and not utxo.get("locked", False)  # ✅ Ensure UTXO is not locked


    def validate_transaction_inputs(self, transaction):
        """Ensure all transaction inputs exist and are unspent before accepting."""
        return all(self.is_utxo_available(tx_input.tx_out_id) for tx_input in transaction.inputs)


    def reallocate_space(self, remaining_space, current_block_height):
        """
        Dynamically reallocate unused block space to high-priority transactions.

        :param remaining_space: Remaining space in bytes.
        :param current_block_height: Current blockchain height.
        :return: List of overflow transactions.
        """
        with self.lock:
            overflow_txs = []

            # Fetch Standard and Smart transactions
            standard_txs = self.standard_mempool.get_all_transactions()
            smart_txs = self.smart_mempool.get_all_transactions()

            # Calculate available space based on Constants allocation
            standard_allocation = int(Constants.BLOCK_ALLOCATION_STANDARD * remaining_space)
            smart_allocation = int(Constants.BLOCK_ALLOCATION_SMART * remaining_space)

            # Sort transactions by fee-per-byte and urgency (older transactions get priority)
            sorted_standard_txs = sorted(standard_txs, key=lambda x: (-x["fee_per_byte"], current_block_height - x.get("block_added", 0)))
            sorted_smart_txs = sorted(smart_txs, key=lambda x: (-x["fee_per_byte"], current_block_height - x.get("block_added", 0)))

            # Select transactions for reallocation
            current_standard_size, current_smart_size = 0, 0
            for tx in sorted_standard_txs:
                if current_standard_size + tx["transaction"].size <= standard_allocation:
                    overflow_txs.append(tx)
                    current_standard_size += tx["transaction"].size

            for tx in sorted_smart_txs:
                if current_smart_size + tx["transaction"].size <= smart_allocation:
                    overflow_txs.append(tx)
                    current_smart_size += tx["transaction"].size

            return overflow_txs








    def allocate_block_space(self, block_size_mb, current_block_height):
        """
        Allocate block space between Standard and Smart Mempools dynamically.

        :param block_size_mb: Current block size in MB.
        :param current_block_height: Current blockchain height for prioritization.
        :return: A list of transactions for block inclusion.
        """
        block_size_bytes = block_size_mb * 1024 * 1024  # Convert MB to bytes

        # Fetch transactions from each mempool
        instant_txs = self.standard_mempool.get_pending_transactions(block_size_mb, transaction_type="Instant")
        standard_txs = self.standard_mempool.get_pending_transactions(block_size_mb, transaction_type="Standard")
        smart_txs = self.smart_mempool.get_smart_transactions(block_size_mb, current_block_height)

        # Calculate total allocated space
        total_instant = sum(tx.size for tx in instant_txs)
        total_standard = sum(tx.size for tx in standard_txs)
        total_smart = sum(tx.size for tx in smart_txs)

        # Dynamic reallocation of unused space
        remaining_space = max(0, block_size_bytes - (total_instant + total_standard + total_smart))
        if remaining_space > 0:
            overflow_txs = self.reallocate_space(remaining_space, current_block_height)
            return instant_txs + standard_txs + smart_txs + overflow_txs

        return instant_txs + standard_txs + smart_txs







    def get_pending_transactions(self, block_size_mb: float, transaction_type: str = "Standard") -> list:
        """
        Retrieve transactions for block inclusion, prioritizing high fees.
        Allocates space dynamically based on transaction type.

        :param block_size_mb: Current block size in MB.
        :param transaction_type: "Instant" or "Standard" to filter transactions.
        :return: A list of transaction objects.
        """
        block_size_bytes = block_size_mb * 1024 * 1024

        # ✅ Use Constants to dynamically allocate space
        if transaction_type == "Instant":
            allocation = int(block_size_bytes * Constants.INSTANT_PAYMENT_ALLOCATION)
        else:
            allocation = int(block_size_bytes * Constants.STANDARD_TRANSACTION_ALLOCATION)

        with self.lock:
            # ✅ Properly filter transactions by type
            filtered_txs = [
                tx for tx in self.transactions.values()
                if (transaction_type == "Instant" and tx["transaction"].tx_id.startswith(("PID-", "CID-"))) or
                (transaction_type == "Standard" and not tx["transaction"].tx_id.startswith(("PID-", "CID-")))
            ]

            # ✅ Sort transactions by highest fee-per-byte first
            sorted_txs = sorted(filtered_txs, key=lambda x: x["fee_per_byte"], reverse=True)

            # ✅ Select transactions that fit within allocated space
            selected_txs = []
            current_size = 0
            for tx_data in sorted_txs:
                tx_size = tx_data["transaction"].size
                if current_size + tx_size > allocation:
                    break
                selected_txs.append(tx_data["transaction"])
                current_size += tx_size

            return selected_txs



    def restore_transactions(self, transactions):
        """
        Restore transactions back into the mempool if mining fails.

        :param transactions: List of transaction objects to restore.
        """
        with self.lock:
            for tx in transactions:
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
                raise ValueError(f"[ERROR] Transaction {transaction_id} not found in mempool.")

            confirmations = transaction.get("confirmations", 0)
            tx_type = transaction["transaction"].type.name if transaction["transaction"].type else "STANDARD"

            # ✅ Dynamically determine required confirmations from Constants
            required_confirmations = Constants.TRANSACTION_CONFIRMATIONS.get(tx_type, 8)

            # ✅ Check if the transaction is still pending or confirmed
            if confirmations < required_confirmations:
                logging.info(f"[INFO] Transaction {transaction_id} pending ({confirmations}/{required_confirmations} confirmations).")
                transaction["confirmations"] += 1  # Simulate confirmation tracking
            else:
                transaction["status"] = "Confirmed"
                logging.info(f"[INFO] Transaction {transaction_id} has been fully confirmed.")


    def promote_child_to_parent(self, parent_id):
        """
        Promote the last child transaction to be the new parent if the current parent is confirmed.
        :param parent_id: ID of the confirmed parent transaction.
        """
        with self.lock:
            parent_transaction = self.transactions.get(parent_id)
            if not parent_transaction:
                raise ValueError(f"[ERROR] Parent transaction {parent_id} not found in mempool.")

            if parent_transaction["status"] != "Confirmed":
                raise ValueError(f"[ERROR] Parent transaction {parent_id} is not confirmed yet.")

            # ✅ Ensure children are sorted by timestamp to promote the oldest child
            if parent_transaction["children"]:
                sorted_children = sorted(parent_transaction["children"], key=lambda tx_id: self.transactions[tx_id]["timestamp"])
                last_child_id = sorted_children[-1]  # Promote the last child

                # ✅ Update child transaction to become the new parent
                self.transactions[last_child_id]["parent_id"] = None
                self.transactions[last_child_id]["status"] = "Pending"

                # ✅ Remove reference from the old parent
                parent_transaction["children"].remove(last_child_id)

                logging.info(f"[INFO] Promoted transaction {last_child_id} as the new parent of the chain.")
                return last_child_id
            else:
                logging.info(f"[INFO] No children available to promote for parent {parent_id}.")
            return None


    def cleanup_expired_transactions(self):
        """
        Remove transactions that have been in the mempool beyond the timeout or expiry time.
        """
        current_time = time.time()
        mempool_expiry = Constants.MEMPOOL_TRANSACTION_EXPIRY  # ✅ Use dynamic expiration from Constants

        with self.lock:
            expired_transactions = []

            for tx_hash, data in self.transactions.items():
                tx_age = current_time - data["timestamp"]  # ✅ Compute once for efficiency

                if tx_age > mempool_expiry:
                    expired_transactions.append(tx_hash)

            # ✅ Remove expired transactions and log their removal
            for tx_hash in expired_transactions:
                self.remove_transaction(tx_hash)
                logging.info(f"[INFO] Removed expired transaction {tx_hash} from mempool (Exceeded {mempool_expiry}s).")


    def remove_transaction(self, tx_id, smart_contract):
        """
        Remove a transaction from the mempool and update the smart contract.

        :param tx_id: The transaction ID to remove.
        :param smart_contract: Instance of the DisputeResolutionContract.
        """
        with self.lock:
            if tx_id not in self.transactions:
                logging.warning(f"[WARN] Attempted to remove non-existent transaction {tx_id}.")
                return

            tx_data = self.transactions[tx_id]
            tx_size = tx_data["transaction"].size

            # ✅ Ensure size is only subtracted if it is valid
            if tx_size and self.current_size_bytes >= tx_size:
                self.current_size_bytes -= tx_size

            # ✅ Handle parent-child relationships safely
            if "parents" in tx_data and tx_data["parents"]:
                for parent_tx_id in tx_data["parents"]:
                    if parent_tx_id in self.transactions:
                        self.transactions[parent_tx_id]["children"].discard(tx_id)

            # ✅ Notify the smart contract and handle errors gracefully
            try:
                smart_contract.refund_transaction(tx_id)
                logging.info(f"[INFO] Transaction {tx_id} refunded in smart contract.")
            except Exception as e:
                logging.error(f"[ERROR] Failed to refund transaction {tx_id} in smart contract: {e}")

            # ✅ Remove transaction from mempool only after all operations are done
            del self.transactions[tx_id]
            logging.info(f"[INFO] Transaction {tx_id} successfully removed from the mempool.")

    def recommend_fees(self, block_size, payment_type):
        """
        Recommend transaction fees based on current mempool state and congestion levels.

        :param block_size: Current block size in MB.
        :param payment_type: Payment type ("Standard", "Smart", "Instant").
        :return: Recommended fee-per-byte and congestion level.
        """
        with self.lock:
            total_size = sum(tx["transaction"].size for tx in self.transactions.values())
            
            # ✅ Prevent division by zero if no transactions are in the mempool
            if total_size == 0:
                logging.info("[INFO] No transactions in mempool. Returning minimum recommended fee.")
                return {
                    "congestion_level": "LOW",
                    "recommended_fee_per_byte": Constants.MIN_TRANSACTION_FEE
                }

            congestion_level = self.fee_model.get_congestion_level(block_size, payment_type, total_size)

            # ✅ Ensure the fee list is not empty before using max()
            fee_per_byte_list = [tx["fee_per_byte"] for tx in self.transactions.values()]
            if not fee_per_byte_list:
                logging.warning("[WARN] No transactions with valid fee_per_byte found. Using minimum transaction fee.")
                return {
                    "congestion_level": congestion_level,
                    "recommended_fee_per_byte": Constants.MIN_TRANSACTION_FEE
                }

            # ✅ Sort only if there are multiple elements
            if len(fee_per_byte_list) > 1:
                fee_per_byte_list.sort()

            recommended_fee = self.fee_model.calculate_fee(
                block_size, payment_type, total_size, max(fee_per_byte_list)
            )

            recommended_fee_per_byte = recommended_fee / total_size if total_size > 0 else Constants.MIN_TRANSACTION_FEE

            logging.info(f"[INFO] Recommended Fee for {payment_type}: {recommended_fee_per_byte:.8f} (Congestion: {congestion_level})")

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
            total_size = sum(
                tx["transaction"].size for tx in self.transactions.values()
                if hasattr(tx["transaction"], "size") and isinstance(tx["transaction"].size, (int, float))
            )

            logging.info(f"[INFO] Current Mempool Size: {total_size} bytes")
            return total_size


    def trigger_dispute(self, tx_id, smart_contract):
        """
        Trigger a dispute for a transaction.
        """
        with self.lock:
            if tx_id not in self.transactions:
                logging.error(f"[ERROR] Transaction {tx_id} not found in the mempool.")
                return

            transaction = self.transactions[tx_id]

            # ✅ Prevent redundant dispute triggers
            if transaction.get("status") == "Dispute":
                logging.warning(f"[WARN] Dispute already triggered for transaction {tx_id}. Skipping.")
                return

            try:
                dispute_data = smart_contract.trigger_dispute(tx_id)

                # ✅ Update transaction status after triggering a dispute
                self.transactions[tx_id]["status"] = "Dispute"

                logging.info(f"[INFO] Dispute successfully triggered for transaction {tx_id}: {dispute_data}")
            except Exception as e:
                logging.error(f"[ERROR] Failed to trigger dispute for transaction {tx_id}: {e}")





    def rebroadcast_transaction(self, tx_id, increment_factor, smart_contract):
        """
        Rebroadcast a transaction with an increased fee.
        """
        with self.lock:
            if tx_id not in self.transactions:
                logging.error(f"[ERROR] Transaction {tx_id} not found in the mempool.")
                return

            transaction = self.transactions[tx_id]

            # ✅ Prevent rebroadcasting if transaction is already confirmed
            if transaction.get("status") == "Confirmed":
                logging.warning(f"[WARN] Transaction {tx_id} is already confirmed. Rebroadcasting skipped.")
                return

            # ✅ Ensure increment factor is valid
            if increment_factor <= 1.0:
                logging.error(f"[ERROR] Invalid increment factor {increment_factor} for transaction {tx_id}. Must be > 1.0.")
                return

            try:
                # ✅ Call smart contract to rebroadcast transaction
                smart_contract.rebroadcast_transaction(tx_id, increment_factor)

                # ✅ Increase the transaction fee dynamically
                old_fee = transaction["transaction"].fee
                new_fee = old_fee * increment_factor
                transaction["transaction"].fee = new_fee

                logging.info(f"[INFO] Transaction {tx_id} rebroadcasted with new fee: {new_fee:.8f} (Old Fee: {old_fee:.8f})")
            except Exception as e:
                logging.error(f"[ERROR] Failed to rebroadcast transaction {tx_id}: {e}")
