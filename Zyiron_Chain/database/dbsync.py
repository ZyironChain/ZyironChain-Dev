import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Use absolute imports
from Zyiron_Chain.database.unqlitedatabase import BlockchainUnqliteDB
from Zyiron_Chain.database.sqlitedatabase import SQLiteDB
from Zyiron_Chain.database.duckdatabase import AnalyticsNetworkDB
from Zyiron_Chain.database.lmdatabase import LMDBManager
from Zyiron_Chain.database.tinydatabase import TinyDBManager
from Zyiron_Chain.blockchain.constants import Constants
import logging
from datetime import datetime
import time
import logging
from datetime import datetime
import json 



class DatabaseSyncManager:
    """
    Manages cross-database synchronization for blockchain consistency.
    - UnQLite → SQLite
    - SQLite → DuckDB
    - LMDB (Mempool) → SQLite (Transaction Validation)
    - TinyDB (Peer Management) → LMDB (Network Peers)
    - Aggregates blockchain analytics via DuckDB.
    """

    def __init__(self):
        """Initialize all blockchain databases."""
        self.unqlite_db = BlockchainUnqliteDB()
        self.sqlite_db = SQLiteDB()
        self.duckdb_analytics = AnalyticsNetworkDB()
        self.lmdb_manager = LMDBManager()
        self.tinydb_manager = TinyDBManager()







    def prioritize_database_query(self, query_type, **kwargs):
        """
        Dynamically prioritize databases based on the query type.

        :param query_type: The type of query (e.g., 'block_metadata', 'utxo', 'pending_tx')
        :param kwargs: Additional parameters for filtering.
        :return: Query result or None if not found.
        """

        # ✅ **Route Queries Dynamically Based on Priority**
        if query_type == "block_metadata":
            # 🔹 **Prioritize DuckDB first for metadata, then UnQLite**
            result = self.duckdb_analytics.get_block_metadata(kwargs.get("block_hash"))
            if result:
                logging.info(f"[PRIORITY] ✅ Block metadata retrieved from DuckDB.")
                return result
            return self.unqlite_db.get_block(kwargs.get("block_hash"))  # Fallback to UnQLite

        elif query_type == "utxo":
            # 🔹 **SQLite should check DuckDB for UTXO changes first before UnQLite**
            result = self.sqlite_db.get_utxo(kwargs.get("tx_out_id"))
            if result:
                logging.info(f"[PRIORITY] ✅ UTXO found in SQLite.")
                return result
            
            return self.unqlite_db.get_utxo(kwargs.get("tx_out_id"))  # Fallback to UnQLite
        
        elif query_type == "pending_tx":
            # 🔹 **LMDB should check SQLite first before using LMDB mempool**
            result = self.sqlite_db.get_transaction(kwargs.get("tx_id"))
            if result:
                logging.info(f"[PRIORITY] ✅ Pending transaction found in SQLite.")
                return result

            return self.lmdb_manager.get_transaction(kwargs.get("tx_id"))  # Fallback to LMDB

        elif query_type == "peer_config":
            # 🔹 **TinyDB is the fastest for peer connections before LMDB**
            result = self.tinydb_manager.get_peer(kwargs.get("peer_id"))
            if result:
                logging.info(f"[PRIORITY] ✅ Peer data retrieved from TinyDB.")
                return result
            
            return self.lmdb_manager.get_peer(kwargs.get("peer_id"))  # Fallback to LMDB

        elif query_type == "network_analytics":
            # 🔹 **Network analytics should prioritize DuckDB for real-time updates**
            return self.duckdb_analytics.get_network_metrics(kwargs.get("metric_name"))

        else:
            logging.warning(f"[WARNING] No priority routing set for query type: {query_type}")
            return None







    ### -------------------- SYNC UNQLITE → SQLITE (BLOCKCHAIN + UTXOs) -------------------- ###

    def sync_unqlite_to_sqlite(self):
        """
        Synchronize UTXO and block data from UnQLite (Immutable Storage) to SQLite (UTXO Management).
        Ensures UTXOs in SQLite remain consistent with UnQLite blocks.
        """
        logging.info("[SYNC] 🔄 Synchronizing UnQLite to SQLite...")

        try:
            blocks = self.unqlite_db.get_all_blocks()
            for block in blocks:
                block_index = block.get("block_header", {}).get("index", -1)

                if block_index == -1:
                    logging.warning(f"[SYNC] ⚠️ Block missing index. Skipping block: {block['hash']}")
                    continue

                # ✅ Process transactions within the block
                for tx in block.get("transactions", []):
                    for output in tx.get("outputs", []):
                        utxo_id = f"{tx['tx_id']}-{output['amount']}"
                        
                        # ✅ Prevent duplicate UTXOs
                        if self.sqlite_db.get_utxo(utxo_id):
                            continue
                        
                        # ✅ Insert UTXO into SQLite
                        self.sqlite_db.add_utxo(
                            utxo_id=utxo_id,
                            tx_out_id=tx["tx_id"],
                            amount=output["amount"],
                            script_pub_key=output["script_pub_key"],
                            locked=False,
                            block_index=block_index,
                        )

            logging.info("[SYNC] ✅ UnQLite to SQLite synchronization complete.")

        except Exception as e:
            logging.error(f"[SYNC ERROR] ❌ UnQLite to SQLite sync failed: {e}")

    ### -------------------- SYNC SQLITE → DUCKDB (ANALYTICS) -------------------- ###

    def sync_sqlite_to_duckdb(self):
        """
        Update DuckDB with metadata from SQLite.
        - Tracks UTXO balances, wallet activity, and transaction metrics.
        """
        logging.info("[SYNC] 🔄 Synchronizing SQLite to DuckDB...")

        try:
            self.sqlite_db.create_utxos_table()  # Ensure UTXO table exists
            utxos = self.sqlite_db.fetch_all_utxos()  # Fetch UTXOs
            
            for utxo in utxos:
                self.duckdb_analytics.insert_wallet_metadata(
                    wallet_address=utxo["script_pub_key"],
                    balance=utxo["amount"],
                    transaction_count=1,
                    last_updated=datetime.now(),
                )

            logging.info("[SYNC] ✅ SQLite to DuckDB synchronization complete.")

        except Exception as e:
            logging.error(f"[SYNC ERROR] ❌ SQLite to DuckDB sync failed: {e}")

    ### -------------------- SYNC LMDB (MEMPOOL) → SQLITE (TRANSACTION VALIDATION) -------------------- ###

    def sync_lmdb_to_sqlite(self):
        """
        Validate transactions in LMDB mempool against SQLite's UTXO set.
        - Removes invalid transactions with spent/missing inputs.
        """
        logging.info("[SYNC] 🔄 Validating LMDB transactions with SQLite UTXO set...")

        try:
            pending_txs = self.lmdb_manager.fetch_all_pending_transactions()  # ✅ Fixed method call

            for tx in pending_txs:
                inputs_valid = self.sqlite_db.validate_transaction_inputs(tx["inputs"])

                if inputs_valid:
                    logging.info(f"[SYNC] ✅ Transaction {tx['tx_id']} is valid.")
                else:
                    logging.warning(f"[SYNC] ❌ Transaction {tx['tx_id']} is invalid. Removing from LMDB...")
                    self.lmdb_manager.delete_transaction(tx["tx_id"])  # ✅ Remove invalid transactions

            logging.info("[SYNC] ✅ LMDB to SQLite transaction validation complete.")

        except Exception as e:
            logging.error(f"[SYNC ERROR] ❌ LMDB to SQLite sync failed: {e}")


    ### -------------------- SYNC TINYDB (PEERS) → LMDB (NETWORK) -------------------- ###

    def sync_tinydb_to_lmdb(self):
        """
        Synchronize peer node configurations from TinyDB to LMDB.
        - Ensures LMDB stores up-to-date network peers.
        """
        logging.info("[SYNC] 🔄 Synchronizing TinyDB to LMDB...")

        try:
            peers = self.tinydb_manager.get_all_peers()
            for peer in peers:
                self.lmdb_manager.add_peer(peer["peer_address"], peer["port"])

            logging.info("[SYNC] ✅ TinyDB to LMDB synchronization complete.")

        except Exception as e:
            logging.error(f"[SYNC ERROR] ❌ TinyDB to LMDB sync failed: {e}")

    ### -------------------- AGGREGATE ANALYTICS (DUCKDB) -------------------- ###

    def aggregate_analytics(self):
        """
        Aggregate blockchain statistics across databases.
        - Tracks total blocks, UTXOs, and pending transactions.
        """
        logging.info("[ANALYTICS] 🔄 Aggregating blockchain statistics...")

        try:
            total_blocks = len(self.unqlite_db.get_all_blocks())
            total_utxos = len(self.sqlite_db.fetch_all_utxos())
            total_pending_txs = len(self.lmdb_manager.fetch_all_pending_transactions())  # ✅ Fixed call

            self.duckdb_analytics.update_network_analytics("total_blocks", total_blocks, datetime.now())
            self.duckdb_analytics.update_network_analytics("total_utxos", total_utxos, datetime.now())
            self.duckdb_analytics.update_network_analytics("pending_transactions", total_pending_txs, datetime.now())

            logging.info("[ANALYTICS] ✅ Blockchain analytics aggregation complete.")

        except Exception as e:
            logging.error(f"[ANALYTICS ERROR] ❌ Failed to aggregate analytics: {e}")



    ### -------------------- CLEAR ALL DATABASES (RESET) -------------------- ###

    def clear_all_databases(self):
        """
        Clear all blockchain databases for testing or reinitialization.
        """
        logging.warning("[CLEAR] ⚠️ Clearing all databases...")

        try:
            self.unqlite_db.clear()
            self.sqlite_db.clear()
            self.duckdb_analytics.clear_all_metadata()
            self.lmdb_manager.clear_all_data()
            self.tinydb_manager.clear_all_data()

            logging.warning("[CLEAR] ✅ All databases cleared successfully.")

        except Exception as e:
            logging.error(f"[CLEAR ERROR] ❌ Failed to clear databases: {e}")








### -------------------- EXECUTE DATABASE SYNC -------------------- ###

if __name__ == "__main__":
    sync_manager = DatabaseSyncManager()

    logging.info("[TEST] 🚀 Preloading Dummy Data into Databases...")

    # ✅ Insert Dummy Block Data into UnQLite
    dummy_block = {
        "hash": "dummyblock123456",
        "block_header": {
            "index": 1,
            "previous_hash": Constants.ZERO_HASH,
            "merkle_root": "dummymerkleroot789",
            "timestamp": int(time.time()),
            "nonce": 12345,
            "difficulty": Constants.GENESIS_TARGET,
        },
        "transactions": [
            {
                "tx_id": "dummy_tx_001",
                "inputs": [{"tx_out_id": "prev_tx_001", "script_sig": "dummy_signature"}],
                "outputs": [{"amount": 50.0, "script_pub_key": "dummy_pubkey_123"}],
                "timestamp": int(time.time()),
                "type": "STANDARD",
                "fee": 0.1,
                "hash": "dummy_tx_hash_001"
            }
        ]
    }
    sync_manager.unqlite_db.add_block(
        dummy_block["hash"],
        dummy_block["block_header"],
        dummy_block["transactions"],
        len(dummy_block["transactions"]),
        dummy_block["block_header"]["difficulty"]
    )
    logging.info("[TEST] ✅ Dummy Block Data Loaded into UnQLite.")

    # ✅ Insert Dummy UTXO Data into SQLite
    dummy_utxo = {
        "utxo_id": "utxo_001",
        "tx_out_id": "dummy_tx_001",
        "amount": 50.0,
        "script_pub_key": "dummy_pubkey_123",
        "locked": False,
        "block_index": 1
    }
    sync_manager.sqlite_db.insert_utxo(
        dummy_utxo["utxo_id"],
        dummy_utxo["tx_out_id"],
        dummy_utxo["amount"],
        dummy_utxo["script_pub_key"],
        int(dummy_utxo["locked"]),
        dummy_utxo["block_index"]
    )
    logging.info("[TEST] ✅ Dummy UTXO Data Loaded into SQLite.")

    # ✅ Insert Dummy Pending Transaction into LMDB
    dummy_tx = {
        "tx_id": "pending_tx_001",
        "inputs": [{"tx_out_id": "dummy_tx_001", "script_sig": "dummy_signature"}],
        "outputs": [{"amount": 25.0, "script_pub_key": "dummy_pubkey_789"}],
        "timestamp": int(time.time()),
        "type": "STANDARD",
        "fee": 0.05,
        "hash": "dummy_pending_tx_hash"
    }
    sync_manager.lmdb_manager.add_pending_transaction(dummy_tx)
    logging.info("[TEST] ✅ Dummy Pending Transaction Loaded into LMDB.")

    # ✅ Insert Dummy Peer Data into TinyDB
    dummy_peer = {"peer_id": "peer_001", "peer_address": "192.168.1.100", "port": 8333}
    sync_manager.tinydb_manager.add_peer(dummy_peer["peer_address"], dummy_peer["port"])
    logging.info("[TEST] ✅ Dummy Peer Data Loaded into TinyDB.")

    # ✅ Perform Full Synchronization Workflow
    logging.info("[SYNC] 🔄 Running Database Synchronization Workflow...")
    
    sync_manager.sync_unqlite_to_sqlite()
    sync_manager.sync_sqlite_to_duckdb()
    sync_manager.sync_lmdb_to_sqlite()
    sync_manager.sync_tinydb_to_lmdb()
    sync_manager.aggregate_analytics()

    logging.info("[SYNC] ✅ Database synchronization workflow completed successfully.")
