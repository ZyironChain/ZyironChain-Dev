import json
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))



from threading import Lock
import time
from decimal import Decimal
import importlib

def get_fee_model():
    """Lazy load FeeModel to prevent circular imports"""
    module = importlib.import_module("Zyiron_Chain.transactions.fees")
    return getattr(module, "FeeModel")


import logging
from threading import Lock
from decimal import Decimal
from typing import Dict, List, Optional
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.smartpay.smartpay import SmartTransaction
from Zyiron_Chain.storage.lmdatabase import LMDBManager

from Zyiron_Chain.network.peerconstant import PeerConstants
from Zyiron_Chain.utils.deserializer import Deserializer

class SmartMempool:
    """Manages the Smart Mempool with dynamic transaction prioritization."""

    def __init__(self, utxo_storage, peer_id: str = None, max_size_mb=None):
        """
        Initialize the Smart Mempool.

        :param utxo_storage: UTXOStorage instance for validating UTXOs
        :param peer_id: Optional peer identifier (defaults to current user)
        :param max_size_mb: Optional override for mempool size
        """
        self.utxo_storage = utxo_storage
        self.peer_id = peer_id if peer_id is not None else f"peer_{PeerConstants.PEER_USER_ID}"
        self.transactions = {}  # In-memory transaction tracking
        self.lock = Lock()  # Handle concurrency

        self.max_size_mb = max_size_mb if max_size_mb is not None else Constants.MEMPOOL_MAX_SIZE_MB
        self.max_size_bytes = self.max_size_mb * 1024 * 1024
        self.current_size_bytes = 0
        self.confirmation_blocks = Constants.SMART_MEMPOOL_PRIORITY_BLOCKS

        # Use LMDB for smart mempool storage
        self.lmdb = LMDBManager(f"./blockchain_storage/BlockData/smart_mempool_{self.peer_id}.lmdb")

        print(f"[MEMPOOL] ✅ Initialized Smart Mempool with max size {self.max_size_mb} MB and peer_id {self.peer_id}")


    def add_transaction(self, transaction: SmartTransaction, current_block_height: int):
        """
        Add a Smart Transaction to the mempool if valid.

        :param transaction: SmartTransaction object.
        :param current_block_height: Current blockchain height.
        :return: True if added, False otherwise.
        """
        with self.lock:
            try:
                print(f"[SmartMempool.add_transaction] 🔄 Attempting to add TX: {transaction.tx_id}")

                # ✅ Validate transaction ID prefix
                if not transaction.tx_id.startswith("S-"):
                    print(f"[SmartMempool.add_transaction] ❌ Invalid Smart Transaction ID prefix for {transaction.tx_id}. Must start with 'S-'.")
                    return False

                # ✅ Check for duplicate transaction
                if transaction.tx_id in self.transactions:
                    print(f"[SmartMempool.add_transaction] ⚠️ Transaction {transaction.tx_id} already exists in the Smart Mempool.")
                    return False

                # ✅ Validate minimum transaction fee
                if transaction.fee < Constants.MIN_TRANSACTION_FEE:
                    print(f"[SmartMempool.add_transaction] ❌ Transaction {transaction.tx_id} has an insufficient fee: {transaction.fee}.")
                    return False

                # ✅ Prevent expired transactions based on block lock height
                expiry_blocks = Constants.TRANSACTION_EXPIRY_TIME
                tx_age_blocks = current_block_height - transaction.block_height_at_lock
                if tx_age_blocks >= expiry_blocks:
                    print(f"[SmartMempool.add_transaction] ⚠️ Transaction {transaction.tx_id} expired. Age: {tx_age_blocks} blocks (Limit: {expiry_blocks})")
                    return False

                # ✅ Check space in mempool
                transaction_size = transaction.size
                if self.current_size_bytes + transaction_size > self.max_size_bytes:
                    print(f"[SmartMempool.add_transaction] ℹ️ Mempool full. Evicting low-priority transactions to free {transaction_size} bytes...")
                    self.evict_transactions(transaction_size)

                # ✅ Add transaction to in-memory pool
                self.transactions[transaction.tx_id] = {
                    "transaction": transaction,
                    "fee_per_byte": float(transaction.fee / transaction_size),
                    "block_added": current_block_height,
                    "status": "Pending"
                }
                self.current_size_bytes += transaction_size

                # ✅ Persist transaction to LMDB
                if hasattr(self, "lmdb") and self.lmdb:
                    self.lmdb.put(
                        transaction.tx_id.encode(),
                        json.dumps(transaction.to_dict(), sort_keys=True).encode("utf-8")
                    )
                    print(f"[SmartMempool.add_transaction] ✅ Persisted TX {transaction.tx_id} to LMDB.")
                else:
                    print(f"[SmartMempool.add_transaction] ⚠️ LMDB not initialized; transaction not persisted.")

                print(f"[SmartMempool.add_transaction] ✅ Smart Transaction {transaction.tx_id} successfully added.")
                return True

            except Exception as e:
                print(f"[SmartMempool.add_transaction] ❌ ERROR: Failed to add TX {getattr(transaction, 'tx_id', '?')}: {e}")
                return False




    def evict_transactions(self, size_needed: int):
        """
        Evict low-priority transactions to free space.

        :param size_needed: Size of the new transaction in bytes.
        """
        with self.lock:
            sorted_txs = sorted(self.transactions.items(), key=lambda item: item[1]["fee_per_byte"])

            while self.current_size_bytes + size_needed > self.max_size_bytes and sorted_txs:
                tx_id, tx_data = sorted_txs.pop(0)
                self.remove_transaction(tx_id, reason="Low Priority Eviction")


    def get_pending_transactions(self, block_size_mb: float, current_block_height: int):
        """
        Retrieve Smart Transactions for block inclusion.

        :param block_size_mb: Current block size in MB.
        :param current_block_height: Current blockchain height.
        :return: A list of Smart Transaction objects allocated dynamically.
        """
        with self.lock:
            block_size_bytes = block_size_mb * 1024 * 1024
            smart_allocation = int(block_size_bytes * Constants.BLOCK_ALLOCATION_SMART)

            sorted_txs = sorted(
                self.transactions.values(),
                key=lambda x: (
                    current_block_height - x["block_added"] >= self.confirmation_blocks[1],  # ✅ Priority threshold
                    current_block_height - x["block_added"] >= self.confirmation_blocks[2],  # ✅ Failure threshold
                    -x["fee_per_byte"]
                )
            )

            selected_txs = []
            current_size = 0
            for tx_data in sorted_txs:
                if current_block_height - tx_data["block_added"] >= self.confirmation_blocks[2]:
                    logging.error(f"[ERROR] Smart Transaction {tx_data['transaction'].tx_id} failed due to confirmation window expiration.")
                    self.remove_transaction(tx_data['transaction'].tx_id, reason="Confirmation Expired")
                    continue

                if current_size + tx_data["transaction"].size > smart_allocation:
                    break
                selected_txs.append(tx_data["transaction"])
                current_size += tx_data["transaction"].size

            return selected_txs


    def remove_transaction(self, tx_id: str, reason: str = "Manual Removal"):
        """
        Remove a transaction from the mempool and LMDB storage.

        :param tx_id: Transaction ID to remove.
        :param reason: Reason for removal (for logging).
        """
        with self.lock:
            if tx_id in self.transactions:
                tx_size = self.transactions[tx_id]["transaction"].size
                self.current_size_bytes -= tx_size
                del self.transactions[tx_id]

            # ✅ Remove from LMDB
            self.lmdb.delete(tx_id)

            logging.info(f"[INFO] Smart Transaction {tx_id} removed from the mempool. Reason: {reason}")


    def track_inclusion(self, tx_id: str, block_height: int):
        """
        Track inclusion of a Smart Transaction in a block and remove it from the mempool.

        :param tx_id: Transaction ID included in a block.
        :param block_height: The height of the block containing the transaction.
        """
        with self.lock:
            if tx_id in self.transactions:
                self.remove_transaction(tx_id, reason=f"Confirmed in Block {block_height}")

    def get_smart_transactions(self, block_size_mb: float, current_block_height: int):
        """
        Retrieve Smart Transactions for block inclusion.

        :param block_size_mb: Current block size in MB.
        :param current_block_height: Current blockchain height.
        :return: A list of Smart Transaction objects.
        """
        block_size_bytes = block_size_mb * 1024 * 1024
        smart_allocation = int(block_size_bytes * Constants.BLOCK_ALLOCATION_SMART)

        with self.lock:
            sorted_txs = sorted(
                self.transactions.values(),
                key=lambda x: (
                    current_block_height - x["block_added"],
                    -x["fee_per_byte"]
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





    def get_transaction(self, tx_id: str):
        """Retrieve and deserialize a Smart Transaction from the mempool."""
        data = self.lmdb.get(tx_id)
        return Deserializer().deserialize(data) if data else None
