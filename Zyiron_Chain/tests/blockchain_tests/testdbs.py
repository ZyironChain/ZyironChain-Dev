import sys
import os

# Use the absolute path to the top-level Zyiron_Chain directory
sys.path.append('C:/Users/PC/Desktop/Zyiron_Chain')

# Test the import
try:
    from Zyiron_Chain.database.unqlitedatabase import BlockchainUnqliteDB
    print("Zyiron_Chain module imported successfully!")
except ImportError as e:
    print(f"Error importing module: {e}")




import logging
import json
from datetime import datetime
from Zyiron_Chain.database.unqlitedatabase import BlockchainUnqliteDB
from Zyiron_Chain.database.sqlitedatabase import SQLiteDB
from Zyiron_Chain.database.duckdatabase import AnalyticsNetworkDB
from Zyiron_Chain.database.lmdatabase import LMDBManager
from Zyiron_Chain.database.tinydatabase import TinyDBManager
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.transactions.transactiontype import TransactionType
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.database.poc import PoC  # Import PoC layer to test

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize databases and PoC
unqlite_db = BlockchainUnqliteDB()
sqlite_db = SQLiteDB()
duckdb_analytics = AnalyticsNetworkDB()
lmdb_manager = LMDBManager()
tinydb_manager = TinyDBManager()
poc = PoC()

def test_poc_and_databases():
    # Step 1: Insert dummy data into databases
    
    # UnQLite - Store a block with transaction data
    block_data = Block(index=1, previous_hash="0", transactions=["tx1", "tx2"])
    serialized_block = poc.serialize_data(block_data)
    unqlite_db.add_block(serialized_block)  # Store serialized block in UnQLite
    logging.info("Dummy block data inserted into UnQLite.")
    
    # SQLite - Add UTXO data
    utxo_data = {
        "tx_id": "tx1",
        "output_index": 0,
        "amount": 100,
        "script_pub_key": "public_key_1",
        "locked": False
    }
    sqlite_db.add_utxo(utxo_data["tx_id"], utxo_data["output_index"], utxo_data["amount"], utxo_data["script_pub_key"], utxo_data["locked"])
    logging.info("Dummy UTXO data inserted into SQLite.")
    
    # DuckDB - Insert wallet metadata and analytics
    wallet_data = {
        "wallet_address": "public_key_1",
        "balance": 100,
        "transaction_count": 1,
        "last_updated": datetime.now()
    }
    duckdb_analytics.insert_wallet_metadata(wallet_data["wallet_address"], wallet_data["balance"], wallet_data["transaction_count"], wallet_data["last_updated"])
    logging.info("Dummy wallet metadata inserted into DuckDB.")
    
    # LMDB - Add pending transactions
    transaction_data = {
        "tx_id": "tx1",
        "inputs": [{"tx_id": "tx0", "index": 0}],
        "outputs": [{"address": "public_key_1", "amount": 100}],
        "fee": 0.01
    }
    lmdb_manager.add_transaction(transaction_data["tx_id"], transaction_data["inputs"], transaction_data["outputs"], transaction_data["fee"])
    logging.info("Dummy transaction data inserted into LMDB.")
    
    # TinyDB - Store node configuration
    node_config = {
        "node_id": "Node_1",
        "peer_address": "192.168.1.1",
        "port": 9000,
        "role": "Full Node"
    }
    tinydb_manager.add_node_config(node_config["node_id"], node_config["peer_address"], node_config["port"], node_config["role"])
    logging.info("Dummy node configuration inserted into TinyDB.")
    
    # Step 2: Query data using PoC layer and verify correct deserialization
    
    # Query UnQLite for block data
    block_query = poc.handle_block_request(None, "block_hash_1")
    assert block_query == block_data, "Block data mismatch in UnQLite!"
    logging.info("Block data retrieved successfully from UnQLite.")
    
    # Query SQLite for UTXO data
    utxo_query = poc.handle_utxo_request(None, "tx1")
    assert utxo_query == utxo_data, "UTXO data mismatch in SQLite!"
    logging.info("UTXO data retrieved successfully from SQLite.")
    
    # Query DuckDB for wallet data
    wallet_query = poc.handle_metadata_request(None)
    assert wallet_query["wallet_address"] == wallet_data["wallet_address"], "Wallet data mismatch in DuckDB!"
    logging.info("Wallet metadata retrieved successfully from DuckDB.")
    
    # Query LMDB for pending transaction data
    transaction_query = poc.handle_transaction_request(None, "tx1")
    assert transaction_query == transaction_data, "Transaction data mismatch in LMDB!"
    logging.info("Transaction data retrieved successfully from LMDB.")
    
    # Query TinyDB for node configuration
    node_query = tinydb_manager.get_all_peers()
    assert node_query[0]["node_id"] == node_config["node_id"], "Node config mismatch in TinyDB!"
    logging.info("Node configuration retrieved successfully from TinyDB.")
    
    # Step 3: Test the overall integration by querying all databases for all data
    all_data_query = poc.route_request(None, "block", "block_hash_1")
    assert all_data_query == block_data, "All data flow through PoC layer failed!"
    logging.info("All data flows correctly through PoC.")

    # Step 4: Test the PoC's serialization and deserialization
    serialized_data = poc.serialize_data(block_data)
    deserialized_data = poc.deserialize_data(serialized_data)
    assert deserialized_data == block_data, "Deserialization mismatch!"
    logging.info("Serialization and deserialization work as expected.")
    
    # Step 5: Check database communication efficiency by asserting correct data
    assert unqlite_db.get_block("block_hash_1") == serialized_block, "UnQLite communication failed!"
    assert sqlite_db.fetch_utxo("tx1") == utxo_data, "SQLite communication failed!"
    assert duckdb_analytics.fetch_network_analytics("avg_fee") == {"wallet_address": "public_key_1", "balance": 100}, "DuckDB communication failed!"
    assert lmdb_manager.fetch_all_pending_transactions() == [transaction_data], "LMDB communication failed!"
    assert tinydb_manager.get_all_peers() == [node_config], "TinyDB communication failed!"
    
    logging.info("Test complete: All database interactions are functioning correctly.")

if __name__ == "__main__":
    test_poc_and_databases()
