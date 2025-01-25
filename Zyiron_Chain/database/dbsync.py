import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Use absolute imports
from Zyiron_Chain.database.unqlitedatabase import BlockchainUnqliteDB
from Zyiron_Chain.database.sqlitedatabase import SQLiteDB
from Zyiron_Chain.database.duckdatabase import AnalyticsNetworkDB
from Zyiron_Chain.database.lmdatabase import LMDBManager
from Zyiron_Chain.database.tinydatabase import TinyDBManager

import logging
from datetime import datetime

import logging
from datetime import datetime


logging.basicConfig(level=logging.INFO)

class DatabaseSyncManager:
    def __init__(self):
        self.unqlite_db = BlockchainUnqliteDB()
        self.sqlite_db = SQLiteDB()
        self.duckdb_analytics = AnalyticsNetworkDB()
        self.lmdb_manager = LMDBManager()
        self.tinydb_manager = TinyDBManager()

    def sync_unqlite_to_sqlite(self):
        """
        Synchronize UTXO and block data from UnQLite to SQLite.
        """
        logging.info("[SYNC] Synchronizing UnQLite to SQLite...")
        blocks = self.unqlite_db.get_all_blocks()
        for block in blocks:
            # Update UTXO states in SQLite
            for tx in block["transactions"]:
                for output in tx["outputs"]:
                    self.sqlite_db.add_utxo(
                        utxo_id=f"{tx['tx_id']}-{output['amount']}",
                        tx_out_id=tx["tx_id"],
                        amount=output["amount"],
                        script_pub_key=output["script_pub_key"],
                        locked=False,
                        block_index=block["block_header"]["index"],
                    )
        logging.info("[SYNC] UnQLite to SQLite synchronization complete.")

    def sync_sqlite_to_duckdb(self):
        """
        Update DuckDB with metadata from SQLite.
        """
        logging.info("[SYNC] Synchronizing SQLite to DuckDB...")
        self.sqlite_db.create_utxos_table()  # Ensure the table exists
        utxos = self.sqlite_db.fetch_all_utxos()  # Fetch UTXOs as dictionaries
        for utxo in utxos:
            self.duckdb_analytics.insert_wallet_metadata(
                wallet_address=utxo["script_pub_key"],
                balance=utxo["amount"],
                transaction_count=1,
                last_updated=datetime.now(),
            )
        logging.info("[SYNC] SQLite to DuckDB synchronization complete.")


    def sync_lmdb_to_sqlite(self):
        """
        Validate mempool transactions from LMDB with SQLite.
        """
        logging.info("[SYNC] Validating transactions in LMDB with SQLite...")
        pending_txs = self.lmdb_manager.fetch_all_pending_transactions()

        for tx in pending_txs:
            inputs_valid = self.sqlite_db.validate_transaction_inputs(tx["inputs"])
            if inputs_valid:
                logging.info(f"[SYNC] Transaction {tx['tx_id']} is valid.")
            else:
                logging.warning(f"[SYNC] Transaction {tx['tx_id']} is invalid and will be removed.")
                self.lmdb_manager.delete_transaction(tx["tx_id"])
        logging.info("[SYNC] LMDB to SQLite synchronization complete.")

    def sync_tinydb_to_lmdb(self):
        """
        Provide peer configurations from TinyDB to LMDB.
        """
        logging.info("[SYNC] Synchronizing TinyDB to LMDB...")
        peers = self.tinydb_manager.get_all_peers()
        for peer in peers:
            self.lmdb_manager.add_peer(peer["peer_address"], peer["port"])
        logging.info("[SYNC] TinyDB to LMDB synchronization complete.")

    def aggregate_analytics(self):
        """
        Pull aggregated data from multiple databases for analytics.
        """
        logging.info("[ANALYTICS] Aggregating data for analytics...")
        total_blocks = len(self.unqlite_db.get_all_blocks())
        total_utxos = len(self.sqlite_db.fetch_all_utxos())
        total_pending_txs = len(self.lmdb_manager.fetch_all_pending_transactions())

        self.duckdb_analytics.update_network_analytics(
            metric_name="total_blocks",
            metric_value=total_blocks,
            timestamp=datetime.now(),
        )
        self.duckdb_analytics.update_network_analytics(
            metric_name="total_utxos",
            metric_value=total_utxos,
            timestamp=datetime.now(),
        )
        self.duckdb_analytics.update_network_analytics(
            metric_name="pending_transactions",
            metric_value=total_pending_txs,
            timestamp=datetime.now(),
        )
        logging.info("[ANALYTICS] Data aggregation complete.")



    def clear_all_databases(self):
        """
        Clear all data from the databases (for testing or reinitialization).
        """
        logging.warning("[CLEAR] Clearing all databases...")
        self.unqlite_db.clear()
        self.sqlite_db.clear()
        self.duckdb_analytics.clear_all_metadata()
        self.lmdb_manager.clear_all_data()
        self.tinydb_manager.clear_all_data()
        logging.warning("[CLEAR] All databases cleared.")

if __name__ == "__main__":
    sync_manager = DatabaseSyncManager()

    # Example workflow
    sync_manager.sync_unqlite_to_sqlite()
    sync_manager.sync_sqlite_to_duckdb()
    sync_manager.sync_lmdb_to_sqlite()
    sync_manager.sync_tinydb_to_lmdb()
    sync_manager.aggregate_analytics()
    logging.info("[SYNC] Database synchronization workflow complete.")
