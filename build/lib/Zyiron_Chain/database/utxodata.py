import leveldb
import json










class UTXOData:
    def __init__(self, db_path='./utxo_db'):
        """
        Initialize the UTXOData with a LevelDB database.
        """
        self.db = leveldb.LevelDB(db_path, create_if_missing=True)

    def store_utxo(self, txid, index, value, script_pub_key, block_hash, locked=False):
        """
        Store a UTXO in the LevelDB database.
        """
        key = f"utxo:{txid}:{index}".encode()
        value_data = {
            "value": value,
            "script_pub_key": script_pub_key,
            "block_hash": block_hash,
            "locked": locked
        }
        self.db.Put(key, json.dumps(value_data).encode())
        print(f"[INFO] Stored UTXO: {key.decode()}")

    def get_utxo(self, txid, index):
        """
        Retrieve a UTXO by transaction ID and index.
        """
        key = f"utxo:{txid}:{index}".encode()
        try:
            value = json.loads(self.db.Get(key).decode())
            return value
        except KeyError:
            print(f"[INFO] UTXO {txid}:{index} not found.")
            return None

    def delete_utxo(self, txid, index):
        """
        Delete a UTXO from the database.
        """
        key = f"utxo:{txid}:{index}".encode()
        try:
            self.db.Delete(key)
            print(f"[INFO] Deleted UTXO: {key.decode()}")
        except KeyError:
            print(f"[ERROR] UTXO {txid}:{index} does not exist.")

    def lock_utxo(self, txid, index):
        """
        Lock a UTXO to prevent it from being spent.
        """
        utxo = self.get_utxo(txid, index)
        if utxo:
            if utxo.get("locked", False):
                raise ValueError(f"UTXO {txid}:{index} is already locked.")
            utxo["locked"] = True
            self.store_utxo(txid, index, utxo["value"], utxo["script_pub_key"], utxo["block_hash"], locked=True)
            print(f"[INFO] Locked UTXO: {txid}:{index}")

    def unlock_utxo(self, txid, index):
        """
        Unlock a previously locked UTXO.
        """
        utxo = self.get_utxo(txid, index)
        if utxo:
            utxo["locked"] = False
            self.store_utxo(txid, index, utxo["value"], utxo["script_pub_key"], utxo["block_hash"], locked=False)
            print(f"[INFO] Unlocked UTXO: {txid}:{index}")

    def export_utxos(self, export_path='./exported_utxos.json'):
        """
        Export all UTXOs to a JSON file for human readability.
        """
        utxos = {}
        for key, value in self.db.RangeIter():
            if key.startswith(b"utxo:"):
                utxos[key.decode()] = json.loads(value.decode())

        with open(export_path, 'w') as f:
            json.dump(utxos, f, indent=4)
        print(f"[INFO] Exported UTXOs to {export_path}")

    def import_utxos(self, import_path='./exported_utxos.json'):
        """
        Import UTXOs from a JSON file into the LevelDB database.
        """
        try:
            with open(import_path, 'r') as f:
                utxos = json.load(f)

            for key, value in utxos.items():
                self.db.Put(key.encode(), json.dumps(value).encode())
            print(f"[INFO] Imported UTXOs from {import_path}")
        except Exception as e:
            print(f"[ERROR] Failed to import UTXOs: {e}")

    def clear_utxos(self):
        """
        Clear all UTXOs from the database.
        """
        keys_to_delete = [key for key, _ in self.db.RangeIter() if key.startswith(b"utxo:")]
        for key in keys_to_delete:
            self.db.Delete(key)
        print("[INFO] Cleared all UTXOs from the database.")
