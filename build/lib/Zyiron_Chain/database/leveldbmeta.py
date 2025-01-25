import leveldb
import json

import leveldb
import json

class LevelDBMeta:
    def __init__(self, db_path='./metadata_db'):
        self.db = leveldb.LevelDB(db_path, create_if_missing=True)

    def store_block_metadata(self, block_hash, file_number, byte_offset, block_height, chain_work, parent_hash, timestamp):
        """
        Store metadata for a block in the LevelDB.
        """
        key = f"block_index:{block_hash}".encode()
        value = json.dumps({
            "file_number": file_number,
            "byte_offset": byte_offset,
            "block_height": block_height,
            "chain_work": chain_work,
            "parent_hash": parent_hash,
            "timestamp": timestamp
        }).encode()
        self.db.put(key, value)

    def get_block_metadata(self, block_hash):
        """
        Retrieve metadata for a specific block by hash.
        """
        key = f"block_index:{block_hash}".encode()
        try:
            value = json.loads(self.db.get(key).decode())
            return value
        except KeyError:
            print(f"Metadata for block {block_hash} not found.")
            return None

    def update_chain_state(self, best_block_hash, total_work, block_height):
        """
        Update the current chain state in LevelDB.
        """
        key = b"chain_state:best_block"
        value = json.dumps({
            "best_block_hash": best_block_hash,
            "total_work": total_work,
            "block_height": block_height
        }).encode()
        self.db.put(key, value)

    def get_chain_state(self):
        """
        Retrieve the current chain state.
        """
        try:
            value = json.loads(self.db.get(b"chain_state:best_block").decode())
            return value
        except KeyError:
            print("Chain state not found.")
            return None

    def store_utxo(self, txid, output_index, value, script_pub_key, block_hash, locked=False):
        """
        Store a UTXO in LevelDB.
        """
        key = f"utxo:{txid}:{output_index}".encode()
        value = json.dumps({
            "value": value,
            "script_pub_key": script_pub_key,
            "block_hash": block_hash,
            "locked": locked
        }).encode()
        self.db.put(key, value)

    def get_utxo(self, txid, output_index):
        """
        Retrieve a UTXO by transaction ID and output index.
        """
        key = f"utxo:{txid}:{output_index}".encode()
        try:
            value = json.loads(self.db.get(key).decode())
            return value
        except KeyError:
            print(f"UTXO {txid}:{output_index} not found.")
            return None

    def delete_utxo(self, txid, output_index):
        """
        Delete a UTXO by transaction ID and output index.
        """
        key = f"utxo:{txid}:{output_index}".encode()
        self.db.delete(key)

    def lock_utxo(self, txid, output_index):
        """
        Lock a UTXO to prevent it from being spent.
        """
        key = f"utxo:{txid}:{output_index}".encode()
        try:
            utxo = json.loads(self.db.get(key).decode())
            if utxo.get("locked", False):
                raise ValueError(f"UTXO {txid}:{output_index} is already locked.")
            utxo["locked"] = True
            self.db.put(key, json.dumps(utxo).encode())
            print(f"[INFO] Locked UTXO {txid}:{output_index}")
        except KeyError:
            print(f"[ERROR] UTXO {txid}:{output_index} not found.")

    def unlock_utxo(self, txid, output_index):
        """
        Unlock a previously locked UTXO.
        """
        key = f"utxo:{txid}:{output_index}".encode()
        try:
            utxo = json.loads(self.db.get(key).decode())
            utxo["locked"] = False
            self.db.put(key, json.dumps(utxo).encode())
            print(f"[INFO] Unlocked UTXO {txid}:{output_index}")
        except KeyError:
            print(f"[ERROR] UTXO {txid}:{output_index} not found.")

    def store_transaction_index(self, txid, block_hash, transaction_offset):
        """
        Store transaction index information.
        """
        key = f"tx_index:{txid}".encode()
        value = json.dumps({
            "block_hash": block_hash,
            "transaction_offset": transaction_offset
        }).encode()
        self.db.put(key, value)

    def get_transaction_index(self, txid):
        """
        Retrieve transaction index information by transaction ID.
        """
        key = f"tx_index:{txid}".encode()
        try:
            value = json.loads(self.db.get(key).decode())
            return value
        except KeyError:
            print(f"Transaction {txid} not found.")
            return None
