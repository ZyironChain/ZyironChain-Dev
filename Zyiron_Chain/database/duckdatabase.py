import duckdb
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
class AnalyticsNetworkDB:
    def __init__(self, db_file="analytics_network.duckdb", read_only=False):
        """
        Initialize the DuckDB connection.
        If read_only is True, opens the database in read-only mode to prevent file locking issues.
        """
        try:
            # Open the database in read-only mode if specified
            self.conn = duckdb.connect(db_file, read_only=read_only)
            if not read_only:
                self.create_tables()  # Create tables only if not in read-only mode
            print("[INFO] Connected to DuckDB.")
        except duckdb.duckdb.IOException as e:
            print(f"[ERROR] Failed to open DuckDB file: {e}")
            raise



    def create_tables(self):
        """
        Create tables in the DuckDB database.
        """
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS block_metadata (
            block_hash TEXT PRIMARY KEY,
            index INTEGER,
            miner TEXT,
            timestamp TIMESTAMP,
            size INTEGER,
            difficulty INTEGER,
            transaction_count INTEGER
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS transaction_metadata (
            tx_id TEXT PRIMARY KEY,
            block_hash TEXT REFERENCES block_metadata(block_hash),
            value DECIMAL,
            fee DECIMAL,
            inputs_count INTEGER,
            outputs_count INTEGER,
            status TEXT,
            timestamp TIMESTAMP
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS wallet_metadata (
            wallet_address TEXT PRIMARY KEY,
            balance DECIMAL,
            transaction_count INTEGER,
            last_updated TIMESTAMP
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS network_analytics (
            metric_name TEXT PRIMARY KEY,
            metric_value DECIMAL,
            timestamp TIMESTAMP
        )
        """)

    def insert_block_metadata(self, index, miner, timestamp, size, difficulty, transaction_count):
        """
        Insert block metadata into DuckDB.
        :param index: The block index.
        :param miner: The miner's address.
        :param timestamp: The block's timestamp.
        :param size: The block's size in bytes.
        :param difficulty: The mining difficulty.
        :param transaction_count: The number of transactions in the block.
        """
        try:
            self.connection.execute(
                """
                INSERT INTO block_metadata (index, miner, timestamp, size, difficulty, transaction_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (index, miner, timestamp, size, difficulty, transaction_count)
            )
            logging.info(f"[INFO] Inserted metadata for block {index} into DuckDB.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to insert block metadata: {e}")
            raise

    def insert_transaction_metadata(self, tx_id, block_hash, transaction_amount, fees, num_inputs, num_outputs, status, timestamp):
        try:
            # First check if the transaction already exists
            existing = self.conn.execute("""
                SELECT COUNT(*) FROM transaction_metadata WHERE tx_id = ?
            """, (tx_id,)).fetchone()

            if existing[0] == 0:
                # Insert if the transaction does not exist
                self.conn.execute("""
                    INSERT INTO transaction_metadata (tx_id, block_hash, transaction_amount, fees, num_inputs, num_outputs, status, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (tx_id, block_hash, transaction_amount, fees, num_inputs, num_outputs, status, timestamp))
            else:
                # Optionally, you can update the existing record
                print(f"Transaction {tx_id} already exists. Skipping insertion.")
        except Exception as e:
            print(f"Error inserting transaction metadata: {e}")


    def insert_wallet_metadata(self, wallet_address, balance, transaction_count, last_updated):
        """
        Insert or update wallet metadata.
        """
        self.conn.execute("""
        INSERT INTO wallet_metadata VALUES (?, ?, ?, ?)
        ON CONFLICT (wallet_address) DO UPDATE SET
            balance = excluded.balance,
            transaction_count = excluded.transaction_count,
            last_updated = excluded.last_updated
        """, (wallet_address, balance, transaction_count, last_updated))


    def update_network_analytics(self, metric_name, metric_value, timestamp):
        """
        Update or insert a network analytics metric.
        """
        self.conn.execute("""
        INSERT INTO network_analytics (metric_name, metric_value, timestamp)
        VALUES (?, ?, ?)
        ON CONFLICT(metric_name) DO UPDATE SET
            metric_value = excluded.metric_value,
            timestamp = excluded.timestamp
        """, (metric_name, metric_value, timestamp))
        self.conn.commit()


    def initialize_tables(self):
        """
        Create required tables if they do not already exist.
        """
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS network_analytics (
            metric_name TEXT PRIMARY KEY,
            metric_value REAL,
            timestamp TIMESTAMP
        )
        """)
        self.conn.commit()



    def insert_network_analytics(self, metric_name, metric_value, timestamp):
        """
        Insert or update network analytics.
        """
        self.conn.execute("""
        INSERT INTO network_analytics VALUES (?, ?, ?)
        ON CONFLICT (metric_name) DO UPDATE SET
            metric_value = excluded.metric_value,
            timestamp = excluded.timestamp
        """, (metric_name, metric_value, timestamp))

    def fetch_block_metadata(self, block_hash):
        """
        Fetch block metadata for a given block hash.
        """
        return self.conn.execute("""
        SELECT * FROM block_metadata WHERE block_hash = ?
        """, (block_hash,)).fetchone()

    def fetch_transaction_metadata(self, tx_id):
        """
        Fetch transaction metadata for a given transaction ID.
        """
        return self.conn.execute("""
        SELECT * FROM transaction_metadata WHERE tx_id = ?
        """, (tx_id,)).fetchone()

    def fetch_wallet_metadata(self, wallet_address):
        """
        Fetch wallet metadata for a given wallet address.
        """
        return self.conn.execute("""
        SELECT * FROM wallet_metadata WHERE wallet_address = ?
        """, (wallet_address,)).fetchone()

    def fetch_network_analytics(self, metric_name):
        """
        Fetch network analytics for a given metric name.
        """
        return self.conn.execute("""
        SELECT * FROM network_analytics WHERE metric_name = ?
        """, (metric_name,)).fetchone()

    def close(self):
        """
        Close the DuckDB connection.
        """
        if self.conn:
            self.conn.close()
            print("[INFO] DuckDB connection closed.")


# Example Usage
if __name__ == "__main__":
    try:
        db = AnalyticsNetworkDB()

        # Insert example data
        db.insert_block_metadata("hash1", 1, "miner1", datetime.now(), 1024, 2, 10)
        db.insert_transaction_metadata("tx1", "hash1", 100.5, 0.5, 2, 3, "confirmed", datetime.now())

        # Fetch and print data
        block = db.fetch_block_metadata("hash1")
        if block:
            print("Block Metadata:", block)
        else:
            logging.warning("[WARN] No block metadata found for hash1.")

    except Exception as e:
        logging.error(f"[ERROR] An error occurred: {e}")

    finally:
        db.close()