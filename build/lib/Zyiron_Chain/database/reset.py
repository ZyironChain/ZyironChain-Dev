import os
import leveldb

import leveldb
import os
import shutil

class DatabaseReset:
    def __init__(self, db_path="blockchain_db"):
        self.db_path = db_path

    def reset_database(self):
        """
        Reset the LevelDB database by deleting all keys and recreating it.
        """
        try:
            # Delete the existing database directory
            if os.path.exists(self.db_path):
                shutil.rmtree(self.db_path)
                print(f"[INFO] Deleted existing database at '{self.db_path}'.")
            
            # Reinitialize the database
            db = leveldb.DB(self.db_path, create_if_missing=True)
            print(f"[INFO] LevelDB database at '{self.db_path}' has been reinitialized.")
        except Exception as e:
            print(f"[ERROR] Failed to reset LevelDB database: {e}")

if __name__ == "__main__":
    resetter = DatabaseReset()
    resetter.reset_database()

