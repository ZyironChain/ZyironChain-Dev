import lmdb
import json
import time


class LMDBManager:
    def __init__(self, db_path="blockchain_lmdb", map_size=10 * 1024 * 1024):  # 10MB
        """
        Initialize the LMDB database.
        :param db_path: Path to the LMDB database directory.
        :param map_size: Maximum size of the database in bytes.
        """
        self.env = lmdb.open(db_path, map_size=map_size, create=True)

    def _serialize(self, data):
        """
        Serialize Python dictionary into JSON string.
        """
        return json.dumps(data).encode()

    def _deserialize(self, data):
        """
        Deserialize JSON string into Python dictionary.
        """
        return json.loads(data.decode())

    # --- Pending Transactions ---
    def add_pending_transaction(self, tx_id, fee_per_byte, size, block_height_added, timestamp, status):
        """
        Add a pending transaction to the database.
        """
        with self.env.begin(write=True) as txn:
            data = {
                "tx_id": tx_id,
                "fee_per_byte": fee_per_byte,
                "size": size,
                "block_height_added": block_height_added,
                "timestamp": timestamp,
                "status": status,
            }
            txn.put(f"pending:{tx_id}".encode(), self._serialize(data))

    def fetch_all_pending_transactions(self):
        """
        Fetch all pending transactions from LMDB.
        """
        transactions = []
        with self.env.begin(db=self.pending_db) as txn:
            cursor = txn.cursor()
            for key, value in cursor:
                transactions.append(json.loads(value.decode("utf-8")))
        return transactions
    
    def delete_pending_transaction(self, tx_id):
        """
        Delete a pending transaction by its ID.
        """
        with self.env.begin(write=True) as txn:
            txn.delete(f"pending:{tx_id}".encode())

    def fetch_all_pending_transactions(self):
        """
        Fetch all pending transactions from the database.
        """
        transactions = []
        with self.env.begin() as txn:
            cursor = txn.cursor()
            for key, value in cursor:
                if key.decode().startswith("pending:"):
                    transactions.append(self._deserialize(value))
        return transactions

    # --- Priority Metadata ---
    def add_priority_metadata(self, tx_id, priority_level, expires_at, mined=False):
        """
        Add priority metadata for a transaction.
        """
        with self.env.begin(write=True) as txn:
            data = {
                "tx_id": tx_id,
                "priority_level": priority_level,
                "expires_at": expires_at,
                "mined": mined,
            }
            txn.put(f"priority:{tx_id}".encode(), self._serialize(data))

    def get_priority_metadata(self, tx_id):
        """
        Retrieve priority metadata for a transaction.
        """
        with self.env.begin() as txn:
            data = txn.get(f"priority:{tx_id}".encode())
            return self._deserialize(data) if data else None

    def delete_priority_metadata(self, tx_id):
        """
        Delete priority metadata for a transaction.
        """
        with self.env.begin(write=True) as txn:
            txn.delete(f"priority:{tx_id}".encode())

    def fetch_all_priority_metadata(self):
        """
        Fetch all priority metadata from the database.
        """
        metadata = []
        with self.env.begin() as txn:
            cursor = txn.cursor()
            for key, value in cursor:
                if key.decode().startswith("priority:"):
                    metadata.append(self._deserialize(value))
        return metadata

    # --- Mempool Metrics ---
    def update_mempool_metrics(self, total_size, total_fees, total_transactions):
        """
        Update the mempool metrics.
        """
        with self.env.begin(write=True) as txn:
            data = {
                "total_size": total_size,
                "total_fees": total_fees,
                "total_transactions": total_transactions,
                "timestamp": time.time(),
            }
            txn.put("mempool:metrics".encode(), self._serialize(data))

    def get_mempool_metrics(self):
        """
        Retrieve the current mempool metrics.
        """
        with self.env.begin() as txn:
            data = txn.get("mempool:metrics".encode())
            return self._deserialize(data) if data else None

    # --- General Utilities ---
    def clear_all_data(self):
        """
        Clear all data from the database.
        """
        with self.env.begin(write=True) as txn:
            cursor = txn.cursor()
            for key, _ in cursor:  # Extract only the `key` for deletion
                txn.delete(key)
        print("[INFO] All data cleared from the database.")

    def close(self):
        """
        Close the LMDB environment.
        """
        self.env.close()


# Example Usage
if __name__ == "__main__":
    db_manager = LMDBManager()

    # Add Pending Transactions
    db_manager.add_pending_transaction(
        tx_id="tx123",
        fee_per_byte=0.5,
        size=250,
        block_height_added=100,
        timestamp=time.time(),
        status="pending"
    )
    db_manager.add_pending_transaction(
        tx_id="tx456",
        fee_per_byte=0.6,
        size=300,
        block_height_added=101,
        timestamp=time.time(),
        status="prioritized"
    )

    # Fetch Pending Transactions
    print("Pending Transactions:", db_manager.fetch_all_pending_transactions())

    # Add Priority Metadata
    db_manager.add_priority_metadata(
        tx_id="tx123",
        priority_level="high",
        expires_at=time.time() + 3600,
        mined=False
    )
    db_manager.add_priority_metadata(
        tx_id="tx456",
        priority_level="medium",
        expires_at=time.time() + 1800,
        mined=True
    )

    # Fetch Priority Metadata
    print("Priority Metadata:", db_manager.fetch_all_priority_metadata())

    # Update and Retrieve Mempool Metrics
    db_manager.update_mempool_metrics(total_size=550, total_fees=0.8, total_transactions=2)
    print("Mempool Metrics:", db_manager.get_mempool_metrics())

    # Clear all data
    db_manager.clear_all_data()
    print("After Clearing Data:")
    print("Pending Transactions:", db_manager.fetch_all_pending_transactions())
    print("Priority Metadata:", db_manager.fetch_all_priority_metadata())
    print("Mempool Metrics:", db_manager.get_mempool_metrics())

    # Close the database
    db_manager.close()
