import sqlite3
import json
from datetime import datetime


import sqlite3
import json
from datetime import datetime

import sqlite3
import json
from datetime import datetime


class SQLiteDB:
    def __init__(self, db_path="sqlite.db"):
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row  # Return rows as dictionaries
        self.cursor = self.connection.cursor()
        self.create_utxos_table()  # Ensure the UTXOs table exists
        self.create_transactions_table()  # Ensure the Transactions table exists

    def create_utxos_table(self):
        """
        Create the UTXOs table if it does not exist.
        """
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
        """
        Create the Transactions table if it does not exist.
        """
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
        """
        Start a new transaction.
        """
        self.connection.execute("BEGIN TRANSACTION;")

    def commit(self):
        """
        Commit the active transaction.
        """
        self.connection.commit()

    def rollback(self):
        """
        Rollback the last transaction in case of failure.
        """
        self.connection.rollback()

    def insert_utxo(self, utxo_id, tx_out_id, amount, script_pub_key, block_index, locked=False):
        """
        Insert a new UTXO into the database.
        """
        self.cursor.execute("""
        INSERT INTO utxos (utxo_id, tx_out_id, amount, script_pub_key, locked, block_index)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (utxo_id, tx_out_id, amount, script_pub_key, locked, block_index))
        self.connection.commit()

    def update_utxo_lock(self, utxo_id, locked):
        """
        Update the lock status of a UTXO.
        """
        self.cursor.execute("""
        UPDATE utxos SET locked = ? WHERE utxo_id = ?
        """, (locked, utxo_id))
        self.connection.commit()

    def fetch_utxo(self, utxo_id):
        """
        Fetch a UTXO by its ID.
        """
        self.cursor.execute("""
        SELECT * FROM utxos WHERE utxo_id = ?
        """, (utxo_id,))
        return self.cursor.fetchone()

    def delete_utxo(self, utxo_id):
        """
        Delete a UTXO by its ID.
        """
        self.cursor.execute("""
        DELETE FROM utxos WHERE utxo_id = ?
        """, (utxo_id,))
        self.connection.commit()

    def insert_transaction(self, tx_id, inputs, outputs, status="pending"):
        """
        Insert a new transaction into the database.
        """
        timestamp = datetime.now().isoformat()
        self.cursor.execute("""
        INSERT INTO transactions (tx_id, inputs, outputs, timestamp, status)
        VALUES (?, ?, ?, ?, ?)
        """, (tx_id, json.dumps(inputs), json.dumps(outputs), timestamp, status))
        self.connection.commit()

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
        Fetch all UTXOs from the database as dictionaries.
        """
        self.cursor.execute("SELECT * FROM utxos")
        return [dict(row) for row in self.cursor.fetchall()]

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
    db.insert_transaction(
        "tx_1",
        [{"utxo_id": "utxo1", "script_sig": "sig1"}],
        [{"amount": 50.0, "script_pub_key": "script1"}],
    )

    # Fetch and display data
    print("UTXOs:", db.fetch_all_utxos())
    print("Transactions:", db.fetch_all_transactions())

    # Clean up
    db.clear()
    db.close()