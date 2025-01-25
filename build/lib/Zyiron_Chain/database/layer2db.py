import os
import leveldb
import json 






class Level2DB:
    def __init__(self, db_path="layer2_db"):
        """
        Initialize the Level2DB for managing Layer 2 data storage.

        :param db_path: Path to the LevelDB database directory.
        """
        self.db_path = os.path.abspath(db_path)
        try:
            self.db = leveldb.LevelDB(self.db_path, create_if_missing=True)
            print(f"[INFO] Level2DB initialized at {self.db_path}")
        except Exception as e:
            raise Exception(f"[ERROR] Failed to initialize Level2DB: {e}")

    def store_channel(self, channel_id, data):
        """
        Store channel data in the database.

        :param channel_id: Unique identifier for the channel.
        :param data: Channel data to store (dictionary or JSON serializable object).
        """
        try:
            self.db.Put(channel_id.encode(), json.dumps(data).encode())
            print(f"[INFO] Channel {channel_id} stored in Level2DB.")
        except Exception as e:
            print(f"[ERROR] Failed to store channel {channel_id}: {e}")

    def get_channel(self, channel_id):
        """
        Retrieve channel data from the database.

        :param channel_id: Unique identifier for the channel.
        :return: Channel data (dictionary) or None if not found.
        """
        try:
            data = self.db.Get(channel_id.encode())
            return json.loads(data.decode())
        except KeyError:
            print(f"[INFO] Channel {channel_id} not found in Level2DB.")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to retrieve channel {channel_id}: {e}")
            return None

    def delete_channel(self, channel_id):
        """
        Delete channel data from the database.

        :param channel_id: Unique identifier for the channel.
        """
        try:
            self.db.Delete(channel_id.encode())
            print(f"[INFO] Channel {channel_id} deleted from Level2DB.")
        except KeyError:
            print(f"[INFO] Channel {channel_id} does not exist in Level2DB.")
        except Exception as e:
            print(f"[ERROR] Failed to delete channel {channel_id}: {e}")

    def store_htlc(self, htlc_id, data):
        """
        Store HTLC (Hashed Time-Locked Contract) data in the database.

        :param htlc_id: Unique identifier for the HTLC.
        :param data: HTLC data to store (dictionary or JSON serializable object).
        """
        try:
            self.db.Put(htlc_id.encode(), json.dumps(data).encode())
            print(f"[INFO] HTLC {htlc_id} stored in Level2DB.")
        except Exception as e:
            print(f"[ERROR] Failed to store HTLC {htlc_id}: {e}")

    def get_htlc(self, htlc_id):
        """
        Retrieve HTLC data from the database.

        :param htlc_id: Unique identifier for the HTLC.
        :return: HTLC data (dictionary) or None if not found.
        """
        try:
            data = self.db.Get(htlc_id.encode())
            return json.loads(data.decode())
        except KeyError:
            print(f"[INFO] HTLC {htlc_id} not found in Level2DB.")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to retrieve HTLC {htlc_id}: {e}")
            return None

    def delete_htlc(self, htlc_id):
        """
        Delete HTLC data from the database.

        :param htlc_id: Unique identifier for the HTLC.
        """
        try:
            self.db.Delete(htlc_id.encode())
            print(f"[INFO] HTLC {htlc_id} deleted from Level2DB.")
        except KeyError:
            print(f"[INFO] HTLC {htlc_id} does not exist in Level2DB.")
        except Exception as e:
            print(f"[ERROR] Failed to delete HTLC {htlc_id}: {e}")

    def list_all_keys(self):
        """
        List all keys in the database.

        :return: List of keys in the database.
        """
        try:
            keys = [key.decode() for key, _ in self.db.RangeIter()]
            return keys
        except Exception as e:
            print(f"[ERROR] Failed to list keys in Level2DB: {e}")
            return []

    def clear_database(self):
        """
        Clear all data in the database.
        """
        try:
            for key, _ in self.db.RangeIter():
                self.db.Delete(key)
            print("[INFO] All data cleared from Level2DB.")
        except Exception as e:
            print(f"[ERROR] Failed to clear Level2DB: {e}")
