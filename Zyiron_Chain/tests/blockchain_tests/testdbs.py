import sys
import os

# Use the absolute path to the top-level Zyiron_Chain directory
sys.path.append('C:/Users/PC/Desktop/Zyiron_Chain')
from Zyiron_Chain.database.sqlitedatabase import SQLiteDB

sqlite_db = SQLiteDB()
import hashlib
#import hashlib
import random
from decimal import Decimal
from Zyiron_Chain.database.sqlitedatabase import SQLiteDB
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager

# Initialize databases and key manager
sqlite_db = SQLiteDB()
key_manager = KeyManager()

def preload_utxos():
    """
    Preload 100 UTXOs into SQLite to ensure transactions can be created.
    """
    print("[INFO] Preloading UTXOs into SQLite...")

    for i in range(100):  # Generate 100 UTXOs
        utxo_id = hashlib.sha3_384(f"utxo-{i}".encode()).hexdigest()
        script_pub_key = key_manager.get_default_public_key("mainnet", "miner")

        utxo_data = {
            "tx_out_id": utxo_id,
            "amount": Decimal(random.uniform(0.01, 5)),  # Random amounts between 0.01 and 5 ZYC
            "script_pub_key": script_pub_key,
            "locked": False,
            "block_index": random.randint(1, 1000)  # Simulating previous block inclusion
        }

        sqlite_db.add_utxo(
            utxo_id=utxo_data["tx_out_id"],
            tx_out_id=utxo_data["tx_out_id"],
            amount=utxo_data["amount"],
            script_pub_key=utxo_data["script_pub_key"],
            locked=utxo_data["locked"],
            block_index=utxo_data["block_index"]
        )

        print(f"[INFO] UTXO {utxo_id} added with {utxo_data['amount']} ZYC.")

    print("[INFO] Preloading complete!")

if __name__ == "__main__":
    preload_utxos()
