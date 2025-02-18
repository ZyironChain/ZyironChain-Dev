

import os 
import duckdb
from datetime import datetime
import logging


logging.basicConfig(level=logging.INFO)
import os
import logging
import duckdb

import os
import logging
import duckdb


# ✅ Set the correct database directory and file name
DB_DIR = "ZYCDB/blockmetadata"
DB_PATH = os.path.join(DB_DIR, "blockmetadata.duckdb")  # ✅ Renamed to `blockmetadata.duckdb`

# ✅ Ensure necessary directories exist
os.makedirs(DB_DIR, exist_ok=True)  # ✅ Ensure `blockmetadata` directory exists


logging.basicConfig(level=logging.INFO)

class AnalyticsNetworkDB:
    def __init__(self, db_file=DB_PATH, read_only=False):
        """
        Initialize the DuckDB connection.
        If read_only is True, opens the database in read-only mode to prevent file locking issues.
        """
        try:
            # ✅ Ensure the database file exists before opening in read-only mode
            if not os.path.exists(db_file) and read_only:
                raise FileNotFoundError(f"[ERROR] ❌ DuckDB file not found: {db_file}")

            # ✅ Open the database in read-only mode if specified
            self.conn = duckdb.connect(db_file, read_only=read_only)

            if not read_only:
                self.create_tables()  # ✅ Create tables only if not in read-only mode
            
            logging.info("[INFO] ✅ Connected to DuckDB.")

        except duckdb.IOException as e:
            logging.error(f"[ERROR] ❌ Failed to open DuckDB file: {e}")
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

    def insert_block_metadata(self, block_hash, index, miner, timestamp, size, difficulty, transaction_count):
        """
        Insert block metadata into DuckDB with conflict resolution.
        """
        try:
            self.conn.execute(
                """
                INSERT INTO block_metadata (block_hash, index, miner, timestamp, size, difficulty, transaction_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(block_hash) DO UPDATE SET 
                    miner = excluded.miner,
                    timestamp = excluded.timestamp,
                    size = excluded.size,
                    difficulty = excluded.difficulty,
                    transaction_count = excluded.transaction_count
                """,
                (block_hash, index, miner, timestamp, size, difficulty, transaction_count)
            )
            logging.info(f"[INFO] ✅ Inserted/Updated metadata for block {block_hash} in DuckDB.")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to insert block metadata: {e}")
            raise

    def insert_transaction_metadata(self, tx_id, block_hash, transaction_amount, fees, num_inputs, num_outputs, status, timestamp):
        """
        Insert or update transaction metadata in DuckDB.
        """
        try:
            self.conn.execute("""
                INSERT INTO transaction_metadata (tx_id, block_hash, value, fee, inputs_count, outputs_count, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tx_id) DO UPDATE SET
                    block_hash = excluded.block_hash,
                    value = excluded.value,
                    fee = excluded.fee,
                    inputs_count = excluded.inputs_count,
                    outputs_count = excluded.outputs_count,
                    status = excluded.status,
                    timestamp = excluded.timestamp
            """, (tx_id, block_hash, transaction_amount, fees, num_inputs, num_outputs, status, timestamp))
            logging.info(f"[INFO] ✅ Inserted/Updated transaction {tx_id} in DuckDB.")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to insert/update transaction metadata: {e}")



    def insert_wallet_metadata(self, wallet_address, balance, transaction_count, last_updated):
        """
        Insert or update wallet metadata in DuckDB.
        """
        try:
            self.conn.execute("""
                INSERT INTO wallet_metadata (wallet_address, balance, transaction_count, last_updated)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(wallet_address) DO UPDATE SET
                    balance = excluded.balance,
                    transaction_count = excluded.transaction_count,
                    last_updated = excluded.last_updated
            """, (wallet_address, balance, transaction_count, last_updated))
            logging.info(f"[INFO] ✅ Wallet {wallet_address} metadata inserted/updated.")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to insert/update wallet metadata: {e}")


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
        Returns None if block is not found.
        """
        try:
            result = self.conn.execute("""
                SELECT * FROM block_metadata WHERE block_hash = ?
            """, (block_hash,)).fetchone()
            if result:
                return dict(result)
            else:
                logging.warning(f"[WARNING] Block {block_hash} not found in metadata.")
                return None
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to fetch block metadata: {e}")
            return None

    def fetch_transaction_metadata(self, tx_id):
        """
        Fetch transaction metadata for a given transaction ID.
        Returns None if transaction is not found.
        """
        try:
            result = self.conn.execute("""
                SELECT * FROM transaction_metadata WHERE tx_id = ?
            """, (tx_id,)).fetchone()
            if result:
                return dict(result)
            else:
                logging.warning(f"[WARNING] Transaction {tx_id} not found in metadata.")
                return None
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to fetch transaction metadata: {e}")
            return None

    def fetch_wallet_metadata(self, wallet_address):
        """
        Fetch wallet metadata for a given wallet address.
        Returns None if the wallet is not found.
        """
        try:
            result = self.conn.execute("""
                SELECT * FROM wallet_metadata WHERE wallet_address = ?
            """, (wallet_address,)).fetchone()
            
            if result:
                return dict(result)  # ✅ Convert to dictionary for consistency
            else:
                logging.warning(f"[WARNING] Wallet {wallet_address} not found in metadata.")
                return None
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to fetch wallet metadata: {e}")
            return None

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
        # ✅ Ensure the database instance is created before calling any function
        db = AnalyticsNetworkDB()

        # ✅ Insert example data to test
        db.insert_block_metadata("hash1", 1, "miner1", datetime.now(), 1024, 2, 10)
        db.insert_transaction_metadata("tx1", "hash1", 100.5, 0.5, 2, 3, "confirmed", datetime.now())

        # ✅ Fetch and print data to verify
        block = db.fetch_block_metadata("hash1")
        if block:
            print("🟢 Block Metadata:", block)
        else:
            logging.warning("[WARN] No block metadata found for hash1.")

    except Exception as e:
        logging.error(f"[ERROR] ❌ An error occurred: {e}")

    finally:
        # ✅ Only close the database if `db` is properly initialized
        if "db" in locals():
            db.close()
            logging.info("[INFO] ✅ DuckDB connection closed.")



