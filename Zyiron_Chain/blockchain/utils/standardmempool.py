








import time
from threading import Lock
from Zyiron_Chain.transactions.fees import FeeModel



class StandardMempool:
    def __init__(self, max_size_mb=500, timeout=86400, expiry_time=86400):
        """
        Initialize the Standard Mempool.

        :param max_size_mb: Maximum size of the mempool in MB (default: 500 MB).
        :param timeout: Transaction expiration time in seconds (default: 24 hours).
        :param expiry_time: Transaction expiry time in seconds (default: 24 hours).
        """
        self.transactions = {}  # Store transactions with their hash as key
        self.dependencies = {}  # Track parent-child relationships
        self.timeout = timeout  # Time in seconds for a transaction to expire
        self.expiry_time = expiry_time  # Time in seconds for a transaction to expire if not confirmed
        self.lock = Lock()      # To handle concurrency
        self.max_size_bytes = max_size_mb * 1024 * 1024  # Convert MB to bytes
        self.current_size_bytes = 0  # Track current memory usage
        self.fee_model = FeeModel()  # Fee model instance for fee calculations

    def add_transaction(self, transaction, smart_contract, fee_model):
        """
        Add a transaction to the Standard Mempool and register it in the smart contract.

        :param transaction: Transaction object with tx_id, fee, size, tx_inputs, and tx_outputs attributes.
        :param smart_contract: Instance of the DisputeResolutionContract.
        :param fee_model: Fee model to calculate minimum acceptable fees.
        :return: True if the transaction was added, False otherwise.
        """
        # 🚨 Validate transaction type & structure
        if transaction.tx_id.startswith("S-"):
            print("[ERROR] Smart Transactions are not allowed in Standard Mempool.")
            return False
        elif transaction.tx_id.startswith(("PID-", "CID-")):
            transaction_type = "Instant" if transaction.tx_id.startswith("PID-,") else "Child"
        else:
            transaction_type = "Standard"

        if not transaction.tx_inputs or not transaction.tx_outputs:
            print(f"[ERROR] Invalid {transaction_type} Transaction: Must have at least one input and one output.")
            return False

        # 🛑 Reject orphan transactions (Inputs must exist in chain or mempool)
        if not self.validate_transaction_inputs(transaction):
            print(f"[WARN] {transaction_type} Transaction {transaction.tx_id} rejected due to missing inputs.")
            return False

        # 🔄 Check for duplicate transactions
        if transaction.tx_id in self.transactions:
            print(f"[WARN] {transaction_type} Transaction already exists in the Standard Mempool.")
            return False

        # 🏦 Ensure minimum fee threshold based on network congestion
        transaction_size = transaction.size
        min_fee_required = fee_model.calculate_fee(transaction_size)
        if transaction.fee < min_fee_required:
            print(f"[ERROR] {transaction_type} Transaction {transaction.tx_id} rejected due to insufficient fee.")
            return False

        # 📏 Ensure mempool does not exceed max size
        if self.current_size_bytes + transaction_size > self.max_size_bytes:
            print("[INFO] Standard Mempool is full. Evicting low-fee transactions...")
            self.evict_transactions(transaction_size)

        # 🔒 Lock mempool before adding transaction
        with self.lock:
            try:
                # 🏛️ Register transaction in Dispute Resolution Contract
                smart_contract.register_transaction(
                    transaction_id=transaction.tx_id,
                    parent_id=getattr(transaction, "parent_id", None),
                    utxo_id=transaction.utxo_id,
                    sender=transaction.sender,
                    recipient=transaction.recipient,
                    amount=transaction.amount,
                    fee=transaction.fee
                )
                print(f"[INFO] {transaction_type} Transaction {transaction.tx_id} registered in smart contract.")

                # 📜 Add transaction to mempool
                self.transactions[transaction.tx_id] = {
                    "transaction": transaction,
                    "timestamp": time.time(),
                    "fee_per_byte": transaction.fee / transaction_size,
                    "parents": transaction.tx_inputs,
                    "children": set(),
                    "status": "Pending"
                }
                self.current_size_bytes += transaction_size

                # 🔗 Maintain parent-child relationships for validation
                for parent_tx_id in transaction.tx_inputs:
                    if parent_tx_id in self.transactions:
                        self.transactions[parent_tx_id]["children"].add(transaction.tx_id)

                print(f"[INFO] {transaction_type} Transaction {transaction.tx_id} added to the Standard Mempool.")
                return True

            except KeyError as e:
                print(f"[ERROR] Missing transaction field: {e}")
            except Exception as e:
                print(f"[ERROR] Failed to register {transaction_type} Transaction in smart contract: {e}")
                return False


    def validate_transaction_inputs(self, transaction):
        """Ensure all transaction inputs exist before accepting."""
        for tx_input in transaction.tx_inputs:
            if not self.is_utxo_available(tx_input.tx_out_id):
                return False
        return True

    def get_pending_transactions(self, block_size_mb, transaction_type="Standard"):
        """
        Retrieve transactions for block inclusion, prioritizing high fees.
        Allocates space based on transaction type: Instant (25%) or Standard (25%).

        :param block_size_mb: Current block size in MB.
        :param transaction_type: "Instant" or "Standard" to filter transactions.
        :return: A list of transaction objects.
        """
        block_size_bytes = block_size_mb * 1024 * 1024
        allocation = int(block_size_bytes * 0.25)  # 25% allocation for each type

        with self.lock:
            # Filter transactions by type
            filtered_txs = [
                tx for tx in self.transactions.values()
                if (transaction_type == "Instant" and tx["transaction"].tx_id.startswith("PID-")) or
                (transaction_type == "Standard" and not tx["transaction"].tx_id.startswith(("PID-", "CID-")))
            ]

            # Sort transactions by fee-per-byte
            sorted_txs = sorted(filtered_txs, key=lambda x: x["fee_per_byte"], reverse=True)

            # Select transactions within allocation
            selected_txs = []
            current_size = 0
            for tx_data in sorted_txs:
                if current_size + tx_data["transaction"].size > allocation:
                    break
                selected_txs.append(tx_data["transaction"])
                current_size += tx_data["transaction"].size

            return selected_txs






    def reallocate_space(self, remaining_space, current_block_height):
        """
        Dynamically reallocate unused block space to high-priority transactions.

        :param remaining_space: Remaining space in bytes.
        :param current_block_height: Current blockchain height.
        :return: List of overflow transactions.
        """
        with self.lock:
            overflow_txs = []

            # Combine all transactions from Standard and Smart Mempools
            all_txs = (
                self.standard_mempool.get_all_transactions() +
                self.smart_mempool.get_all_transactions()
            )

            # Sort by fee-per-byte and urgency
            sorted_txs = sorted(all_txs, key=lambda x: (
                -x["fee_per_byte"],
                current_block_height - x.get("block_added", 0)  # Smart transaction urgency
            ))

            # Select transactions to fill the remaining space
            current_size = 0
            for tx in sorted_txs:
                if current_size + tx.size > remaining_space:
                    break
                overflow_txs.append(tx)
                current_size += tx.size

            return overflow_txs








    def allocate_block_space(self, block_size_mb, current_block_height):
        """
        Allocate block space between Standard and Smart Mempools dynamically.

        :param block_size_mb: Current block size in MB.
        :param current_block_height: Current blockchain height for prioritization.
        :return: A list of transactions for block inclusion.
        """
        block_size_bytes = block_size_mb * 1024 * 1024

        # Fetch transactions from each mempool
        instant_txs = self.standard_mempool.get_pending_transactions(block_size_mb, transaction_type="Instant")
        standard_txs = self.standard_mempool.get_pending_transactions(block_size_mb, transaction_type="Standard")
        smart_txs = self.smart_mempool.get_smart_transactions(block_size_mb, current_block_height)

        # Calculate total allocated space
        total_instant = sum(tx.size for tx in instant_txs)
        total_standard = sum(tx.size for tx in standard_txs)
        total_smart = sum(tx.size for tx in smart_txs)

        # Dynamic reallocation of unused space
        remaining_space = block_size_bytes - (total_instant + total_standard + total_smart)
        if remaining_space > 0:
            overflow_txs = self.reallocate_space(remaining_space, current_block_height)
            return instant_txs + standard_txs + smart_txs + overflow_txs

        return instant_txs + standard_txs + smart_txs







    def get_pending_transactions(self, block_size_mb, transaction_type="Standard"):
        """
        Retrieve transactions for block inclusion, prioritizing high fees.
        Allocates space based on transaction type: Instant (25%) or Standard (25%).

        :param block_size_mb: Current block size in MB.
        :param transaction_type: "Instant" or "Standard" to filter transactions.
        :return: A list of transaction objects.
        """
        block_size_bytes = block_size_mb * 1024 * 1024
        allocation = int(block_size_bytes * 0.25)  # 25% allocation for each type

        with self.lock:
            # Filter transactions by type
            filtered_txs = [
                tx for tx in self.transactions.values()
                if (transaction_type == "Instant" and tx["transaction"].tx_id.startswith("PID- CID")) or
                (transaction_type == "Standard" and not tx["transaction"].tx_id.startswith(("PID-CID ")))
            ]

            # Sort transactions by fee-per-byte
            sorted_txs = sorted(filtered_txs, key=lambda x: x["fee_per_byte"], reverse=True)

            # Select transactions within allocation
            selected_txs = []
            current_size = 0
            for tx_data in sorted_txs:
                if current_size + tx_data["transaction"].size > allocation:
                    break
                selected_txs.append(tx_data["transaction"])
                current_size += tx_data["transaction"].size

            return selected_txs







    def evict_transactions(self, size_needed):
        """
        Evict low-fee transactions to make room for new ones.

        :param size_needed: The size of the new transaction that needs space in bytes.
        """
        with self.lock:
            sorted_txs = sorted(
                self.transactions.items(),
                key=lambda item: item[1]["fee_per_byte"]
            )
            while self.current_size_bytes + size_needed > self.max_size_bytes and sorted_txs:
                tx_id, tx_data = sorted_txs.pop(0)
                self.remove_transaction(tx_id)
                print(f"[INFO] Evicted transaction {tx_id} to free space.")

    def track_confirmation(self, transaction_id):
        """
        Track a transaction's confirmation status in the mempool.
        :param transaction_id: ID of the transaction to track.
        """
        with self.lock:
            transaction = self.transactions.get(transaction_id)
            if not transaction:
                raise ValueError("Transaction not found in mempool.")

            # Check if confirmed
            if transaction["status"] == "Pending":
                print(f"[INFO] Transaction {transaction_id} is still pending.")
            elif transaction["status"] == "Confirmed":
                print(f"[INFO] Transaction {transaction_id} has been confirmed.")

    def promote_child_to_parent(self, parent_id):
        """
        Promote the last child transaction to be the new parent if the current parent is confirmed.
        :param parent_id: ID of the confirmed parent transaction.
        """
        with self.lock:
            parent_transaction = self.transactions.get(parent_id)
            if not parent_transaction:
                raise ValueError("Parent transaction not found in mempool.")

            if parent_transaction["status"] != "Confirmed":
                raise ValueError("Parent transaction is not confirmed.")

            # Promote the last child
            if parent_transaction["children"]:
                last_child_id = list(parent_transaction["children"])[-1]
                print(f"[INFO] Promoting {last_child_id} as the new parent.")
                return last_child_id
            else:
                print("[INFO] No children to promote.")
                return None

    def cleanup_expired_transactions(self):
        """
        Remove transactions that have been in the mempool beyond the timeout or expiry time.
        """
        current_time = time.time()
        with self.lock:
            expired = [
                tx_hash for tx_hash, data in self.transactions.items()
                if current_time - data["timestamp"] > self.timeout or
                   current_time - data["timestamp"] > self.expiry_time
            ]
            for tx_hash in expired:
                self.remove_transaction(tx_hash)

    def remove_transaction(self, tx_id, smart_contract):
        """
        Remove a transaction from the mempool and update the smart contract.

        :param tx_id: The transaction ID to remove.
        :param smart_contract: Instance of the DisputeResolutionContract.
        """
        with self.lock:
            if tx_id in self.transactions:
                tx_size = self.transactions[tx_id]["transaction"].size
                self.current_size_bytes -= tx_size

                # Handle parent-child relationships
                for parent_tx_id in self.transactions[tx_id]["parents"]:
                    if parent_tx_id in self.transactions:
                        self.transactions[parent_tx_id]["children"].discard(tx_id)

                # Notify the smart contract
                try:
                    smart_contract.refund_transaction(tx_id)
                    print(f"[INFO] Transaction {tx_id} refunded in smart contract.")
                except Exception as e:
                    print(f"[ERROR] Failed to refund transaction {tx_id} in smart contract: {e}")

                del self.transactions[tx_id]
                print(f"[INFO] Transaction {tx_id} removed from the mempool.")

    def recommend_fees(self, block_size, payment_type):
        """
        Recommend transaction fees based on current mempool state and congestion levels.

        :param block_size: Current block size in MB.
        :param payment_type: Payment type ("Standard", "Smart", "Instant").
        :return: Recommended fee-per-byte.
        """
        with self.lock:
            total_size = sum(tx["transaction"].size for tx in self.transactions.values())
            congestion_level = self.fee_model.get_congestion_level(block_size, payment_type, total_size)

            fee_per_byte_list = [
                tx["fee_per_byte"] for tx in self.transactions.values()
            ]
            fee_per_byte_list.sort()
            recommended_fee = self.fee_model.calculate_fee(
                block_size, payment_type, total_size, max(fee_per_byte_list)
            )
            return {
                "congestion_level": congestion_level,
                "recommended_fee_per_byte": recommended_fee / total_size,
            }

    def get_total_size(self):
        """
        Calculate the total size of all transactions in the mempool.
        :return: Total size in bytes.
        """
        return sum(tx["transaction"].size for tx in self.transactions.values())


    def trigger_dispute(self, tx_id, smart_contract):
        """
        Trigger a dispute for a transaction.
        """
        if tx_id not in self.transactions:
            raise ValueError(f"Transaction {tx_id} not found in the mempool.")

        try:
            dispute_data = smart_contract.trigger_dispute(tx_id)
            print(f"[INFO] Dispute triggered for transaction {tx_id}: {dispute_data}")
        except Exception as e:
            print(f"[ERROR] Failed to trigger dispute for transaction {tx_id}: {e}")




    def rebroadcast_transaction(self, tx_id, increment_factor, smart_contract):
        """
        Rebroadcast a transaction with an increased fee.
        """
        if tx_id not in self.transactions:
            raise ValueError(f"Transaction {tx_id} not found in the mempool.")

        try:
            smart_contract.rebroadcast_transaction(tx_id, increment_factor)
            print(f"[INFO] Transaction {tx_id} rebroadcasted with increased fee.")
        except Exception as e:
            print(f"[ERROR] Failed to rebroadcast transaction {tx_id}: {e}")