import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import sqlite3
import json
from datetime import datetime
from typing import Optional
from decimal import Decimal
import sqlite3
import json
from datetime import datetime
import logging
from Zyiron_Chain.transactions.Blockchain_transaction import  TransactionIn, TransactionOut, CoinbaseTx
def get_transaction():
    """Lazy import Transaction to break circular dependencies."""
    from Zyiron_Chain.transactions.Blockchain_transaction import Transaction
    return Transaction

class SQLiteDB:
    def __init__(self, db_path="sqlite.db"):
        self.connection = sqlite3.connect(db_path, check_same_thread=False)  # ✅ Ensure connection
        self.connection.row_factory = sqlite3.Row  # ✅ Enables fetching rows as dictionaries
        self.cursor = self.connection.cursor()

        # ✅ Ensure UTXO and Transactions tables exist
        self.create_utxos_table()
        self.create_transactions_table()

    def create_utxos_table(self):
        """Create the UTXOs table if it does not exist."""
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS utxos (
            utxo_id TEXT PRIMARY KEY,
            tx_out_id TEXT NOT NULL,
            amount REAL NOT NULL,
            script_pub_key TEXT NOT NULL,
            locked BOOLEAN NOT NULL DEFAULT 0,
            block_index INTEGER
        )
        """)
        self.connection.commit()

    def create_transactions_table(self):
        """Create the Transactions table if it does not exist."""
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            tx_id TEXT PRIMARY KEY,
            inputs TEXT NOT NULL,
            outputs TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """)
        self.connection.commit()

    def begin_transaction(self):
        """Start a new database transaction."""
        if self.connection:  # ✅ Ensure connection exists before executing
            self.connection.execute("BEGIN TRANSACTION;")
        else:
            logging.error("[ERROR] SQLite connection is not initialized.")


    def commit(self):
        """Commit the active transaction."""
        if self.connection:
            self.connection.commit()
        else:
            logging.error("[ERROR] SQLite connection is not initialized.")

    def rollback(self):
        """Rollback the last transaction in case of failure."""
        if self.connection:
            self.connection.rollback()
        else:
            logging.error("[ERROR] SQLite connection is not initialized.")





    def update_utxo_lock(self, utxo_id, locked):
        """
        Update the lock status of a UTXO.
        """
        self.cursor.execute("""
        UPDATE utxos SET locked = ? WHERE utxo_id = ?
        """, (locked, utxo_id))
        self.connection.commit()

    def get_utxo(self, tx_out_id):
        """Retrieve UTXO from SQLite database."""
        try:
            self.cursor.execute("SELECT * FROM utxos WHERE tx_out_id = ?", (tx_out_id,))
            utxo = self.cursor.fetchone()
            if utxo:
                return {
                    "utxo_id": utxo["utxo_id"],
                    "tx_out_id": utxo["tx_out_id"],
                    "amount": Decimal(utxo["amount"]),  # ✅ Convert to Decimal
                    "script_pub_key": utxo["script_pub_key"],
                    "locked": bool(utxo["locked"]),  # ✅ Convert to boolean
                    "block_index": int(utxo["block_index"])
                }
            else:
                logging.warning(f"[WARNING] UTXO {tx_out_id} not found in SQLite.")
                return None

        except sqlite3.Error as e:
            logging.error(f"[ERROR] SQLite failed to fetch UTXO {tx_out_id}: {e}")
            return None







    def delete_utxo(self, utxo_id):
        """
        Delete a UTXO by its ID.
        """
        self.cursor.execute("""
        DELETE FROM utxos WHERE utxo_id = ?
        """, (utxo_id,))
        self.connection.commit()

    def insert_utxo(self, utxo_id, tx_out_id, amount, script_pub_key, block_index, locked=False):
        """
        Insert a new UTXO into the database while preventing duplicate entries.
        Ensures Decimal values are converted to float and boolean values are stored as integers.
        """
        try:
            # ✅ Ensure Decimal values are converted to float
            amount = float(amount)

            # ✅ Ensure 'locked' is stored as an integer (0 or 1)
            locked = int(locked)

            # ✅ Ensure 'block_index' is an integer
            block_index = int(block_index)

            # ✅ Check if UTXO already exists to prevent duplicate insertion
            self.cursor.execute("SELECT 1 FROM utxos WHERE utxo_id = ?", (utxo_id,))
            if self.cursor.fetchone():
                logging.warning(f"[WARNING] Skipping duplicate UTXO insertion: {utxo_id}")
                return  # ✅ Prevent duplicate insertion

            # ✅ Proceed with insertion if UTXO does not exist
            self.cursor.execute("""
                INSERT INTO utxos (utxo_id, tx_out_id, amount, script_pub_key, locked, block_index)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (utxo_id, tx_out_id, amount, script_pub_key, locked, block_index))
            
            self.connection .commit()
            logging.info(f"[INFO] UTXO {utxo_id} stored in SQLite successfully.")
        
        except sqlite3.IntegrityError as e:
            logging.error(f"[ERROR] Failed to insert UTXO {utxo_id}: {e}")
        
        except Exception as e:
            logging.error(f"[ERROR] Unexpected error while inserting UTXO {utxo_id}: {e}")


    def update_transaction_status(self, tx_id, status):
        """
        Update the status of a transaction.
        """
        self.cursor.execute("""
        UPDATE transactions SET status = ? WHERE tx_id = ?
        """, (status, tx_id))
        self.connection.commit()

    def fetch_transaction(self, tx_id):
        """
        Fetch a transaction by its ID.
        """
        self.cursor.execute("""
        SELECT * FROM transactions WHERE tx_id = ?
        """, (tx_id,))
        return self.cursor.fetchone()

    def delete_transaction(self, tx_id):
        """
        Delete a transaction by its ID.
        """
        self.cursor.execute("""
        DELETE FROM transactions WHERE tx_id = ?
        """, (tx_id,))
        self.connection.commit()

    def fetch_all_utxos(self):
        """
        Fetch all **unspent** UTXOs from the database.
        """
        try:
            self.cursor.execute("SELECT * FROM utxos WHERE locked = 0")
            utxos = self.cursor.fetchall()
            
            if not utxos:
                logging.warning("[WARNING] No unspent UTXOs found in SQLite.")
            
            return [dict(row) for row in utxos]  # Convert to dictionary format
        except Exception as e:
            logging.error(f"[ERROR] Failed to fetch UTXOs from SQLite: {e}")
            return []


    def fetch_all_transactions(self):
        """
        Fetch all transactions.
        """
        self.cursor.execute("""
            SELECT * FROM transactions
        """)
        return [dict(row) for row in self.cursor.fetchall()]  # Convert rows to dictionary format

    def clear(self):
        """
        Clear all data from the database (for testing purposes).
        """
        self.cursor.execute("DELETE FROM utxos")
        self.cursor.execute("DELETE FROM transactions")
        self.connection.commit()

    def close(self):
        """
        Close the SQLite database connection.
        """
        self.connection.close()

# Example Usage
if __name__ == "__main__":
    db = SQLiteDB()

    # Insert test data
    db.insert_utxo("utxo1", "tx1", 100.5, "script1", 1, locked=False)
    db.delete_transaction("tx_1")


    # Fetch and display data
    print("UTXOs:", db.fetch_all_utxos())
    print("Transactions:", db.fetch_all_transactions())

    # Clean up
    db.clear()
    db.close()
