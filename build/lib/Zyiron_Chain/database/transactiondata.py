

import leveldb
import json




class TransactionData:
    def __init__(self, db_path='./blockchain_db/transactions'):
        self.db = leveldb.LevelDB(db_path, create_if_missing=True)

    def store_transaction_index(self, txid, block_hash, transaction_offset):
        key = f"tx_index:{txid}".encode()
        value = json.dumps({
            "block_hash": block_hash,
            "transaction_offset": transaction_offset
        }).encode()
        self.db.put(key, value)

    def get_transaction_index(self, txid):
        key = f"tx_index:{txid}".encode()
        try:
            return json.loads(self.db.get(key).decode())
        except KeyError:
            print(f"[INFO] Transaction {txid} not found.")
            return None
