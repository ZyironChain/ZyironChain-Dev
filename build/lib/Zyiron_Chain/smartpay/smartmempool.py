from threading import Lock
import time
from decimal import Decimal

class SmartMempool:
    def __init__(self, max_size_mb=500, confirmation_blocks=(4, 5, 6)):
        """
        Initialize the Smart Mempool.

        :param max_size_mb: Maximum size of the mempool in MB (default: 500 MB).
        :param confirmation_blocks: Tuple defining the confirmation window: (priority start, priority end, failure block).
        """
        self.transactions = {}  # Store transactions with their hash as key
        self.lock = Lock()      # To handle concurrency
        self.max_size_bytes = max_size_mb * 1024 * 1024  # Convert MB to bytes
        self.current_size_bytes = 0  # Track current memory usage
        self.confirmation_blocks = confirmation_blocks  # Block confirmation thresholds

    def add_transaction(self, transaction, current_block_height):
        """
        Add a Smart Transaction to the mempool if valid.

        :param transaction: Transaction object with tx_id, fee, size, etc.
        :param current_block_height: Current blockchain height for confirmation tracking.
        :return: True if added, False otherwise.
        """
        # Validate transaction ID prefix
        if not transaction.tx_id.startswith("S-"):
            print("[ERROR] Invalid Smart Transaction ID prefix. Must start with 'S-'.")
            return False

        # Check for duplicate transaction
        if transaction.tx_id in self.transactions:
            print("[WARN] Transaction already exists in the Smart Mempool.")
            return False

        # Validate transaction structure
        if not hasattr(transaction, "fee") or not hasattr(transaction, "size"):
            print("[ERROR] Transaction must include 'fee' and 'size' attributes.")
            return False

        # Ensure enough space in the mempool
        transaction_size = transaction.size
        if self.current_size_bytes + transaction_size > self.max_size_bytes:
            print("[INFO] Smart Mempool is full. Evicting low-priority transactions...")
            self.evict_transactions(transaction_size)

        # Add transaction to the mempool
        with self.lock:
            self.transactions[transaction.tx_id] = {
                "transaction": transaction,
                "fee_per_byte": transaction.fee / transaction_size,
                "block_added": current_block_height,  # Block height when added
                "status": "Pending"  # Track transaction status
            }
            self.current_size_bytes += transaction_size

        print(f"[INFO] Smart Transaction {transaction.tx_id} added to the mempool.")
        return True


       
    def evict_transactions(self, size_needed):
        """
        Evict low-priority transactions to free space.

        :param size_needed: Size of the new transaction in bytes.
        """
        with self.lock:
            sorted_txs = sorted(
                self.transactions.items(),
                key=lambda item: item[1]["fee_per_byte"]
            )
            while self.current_size_bytes + size_needed > self.max_size_bytes and sorted_txs:
                tx_id, tx_data = sorted_txs.pop(0)
                self.remove_transaction(tx_id)
                print(f"[INFO] Evicted Smart Transaction {tx_id} to free space.")

    def get_pending_transactions(self, block_size_mb, current_block_height):
        """
        Retrieve Smart Transactions for block inclusion.

        :param block_size_mb: Current block size in MB.
        :param current_block_height: Current blockchain height to prioritize transactions.
        :return: A list of transaction objects allocated 60% of the block size.
        """
        with self.lock:
            block_size_bytes = block_size_mb * 1024 * 1024
            smart_allocation = int(block_size_bytes * 0.6)

            sorted_txs = sorted(
                self.transactions.values(),
                key=lambda x: (
                    current_block_height - x["block_added"] >= self.confirmation_blocks[1],  # Priority end
                    current_block_height - x["block_added"] >= self.confirmation_blocks[2],  # Failure block
                    -x["fee_per_byte"]
                )
            )

            selected_txs = []
            current_size = 0
            for tx_data in sorted_txs:
                if current_block_height - tx_data["block_added"] >= self.confirmation_blocks[2]:
                    print(f"[ERROR] Smart Transaction {tx_data['transaction'].tx_id} failed due to exceeding confirmation window.")
                    self.remove_transaction(tx_data['transaction'].tx_id)
                    continue

                if current_size + tx_data["transaction"].size > smart_allocation:
                    break
                selected_txs.append(tx_data["transaction"])
                current_size += tx_data["transaction"].size

            return selected_txs

    def remove_transaction(self, tx_id):
        """
        Remove a transaction from the mempool.

        :param tx_id: Transaction ID to remove.
        """
        with self.lock:
            if tx_id in self.transactions:
                tx_size = self.transactions[tx_id]["transaction"].size
                self.current_size_bytes -= tx_size
                del self.transactions[tx_id]
                print(f"[INFO] Smart Transaction {tx_id} removed from the mempool.")

    def track_inclusion(self, tx_id, block_height):
        """
        Track inclusion of a Smart Transaction in a block and remove it from the mempool.

        :param tx_id: Transaction ID that has been included.
        :param block_height: The height of the block including the transaction.
        """
        with self.lock:
            if tx_id in self.transactions:
                self.remove_transaction(tx_id)
                print(f"[INFO] Smart Transaction {tx_id} confirmed in block {block_height}.")



    def get_smart_transactions(self, block_size_mb, current_block_height):
        """
        Retrieve Smart Transactions for block inclusion.
        Allocates 50% of the block size to Smart Transactions.

        :param block_size_mb: Current block size in MB.
        :param current_block_height: Current blockchain height.
        :return: A list of Smart Transaction objects.
        """
        block_size_bytes = block_size_mb * 1024 * 1024
        smart_allocation = int(block_size_bytes * 0.50)  # 50% allocation

        with self.lock:
            sorted_txs = sorted(
                self.transactions.values(),
                key=lambda x: (
                    current_block_height - x["block_added"],  # Age in blocks
                    -x["fee_per_byte"]  # Higher fees are prioritized
                )
            )

            selected_txs = []
            current_size = 0
            for tx_data in sorted_txs:
                if current_size + tx_data["transaction"].size > smart_allocation:
                    break
                selected_txs.append(tx_data["transaction"])
                current_size += tx_data["transaction"].size

            return selected_txs
