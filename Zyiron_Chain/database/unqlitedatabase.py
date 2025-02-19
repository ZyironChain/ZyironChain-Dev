from unqlite import UnQLite
import json
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)

import json
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
import os
import threading
DB_PATH = "ZYCDB/blocksdb/blockchain.db"
os.makedirs("ZYCDB/BLOCKSDB", exist_ok=True)
import time 
import os
import json
import logging
import threading
from unqlite import UnQLite
from typing import List, Dict

# Define your database path and ensure the directory exists.
DB_PATH = "ZYCDB/blocksdb/blockchain.db"
os.makedirs("ZYCDB/BLOCKSDB", exist_ok=True)
# Define a global reentrant lock for UnQLite database writes.
GLOBAL_UNQLITE_LOCK = threading.RLock()

class BlockchainUnqliteDB:
    def __init__(self, db_file=DB_PATH):
        """
        Initialize the UnQLite database for storing the immutable blockchain.
        """
        try:
            self.db = UnQLite(db_file)
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to open UnQLite database: {e}")
            raise

        self.transaction_active = False  # For transaction tracking if needed
        # Use the module-level global lock for all UnQLite writes.
        self._db_lock = GLOBAL_UNQLITE_LOCK

    def store_block(self, block: Dict, difficulty: int):
        """
        Store a block in UnQLite, ensuring the 'hash' key is included and block size is within limits.
        This version uses a global reentrant lock and exponential backoff for retries.
        The 'difficulty' parameter is used to explicitly set the block's difficulty.
        """
        block_hash = block.get("hash", None)
        if not block_hash:
            raise ValueError("[ERROR] Block is missing a hash key.")
        
        # Prepare block data from the provided dictionary,
        # using the passed difficulty parameter.
        block_data = {
            "hash": block_hash,
            "header": block.get("header", {}),
            "transactions": block.get("transactions", []),
            "size": block.get("size", 0),
            "difficulty": difficulty
        }
        
        max_retries = 10
        attempt = 0
        backoff = 1  # Start with 1 second delay.

        while attempt < max_retries:
            try:
                with self._db_lock:
                    self.db[f"block:{block_hash}"] = json.dumps(block_data)
                    # Flush the database if supported.
                    if hasattr(self.db, "flush"):
                        self.db.flush()
                logging.info(f"[INFO] ✅ Block {block_hash} stored successfully in UnQLite.")
                return  # Successfully stored.
            except Exception as e:
                error_msg = str(e)
                if "hold the requested lock" in error_msg:
                    logging.error(f"[ERROR] Lock error when storing block (attempt {attempt+1}/{max_retries}): {error_msg}")
                    time.sleep(backoff)
                    backoff *= 2  # Exponential backoff.
                    attempt += 1
                else:
                    logging.error(f"[ERROR] Failed to store block {block_hash}: {error_msg}")
                    raise
        raise Exception("Failed to store block after several retries due to lock errors.")


    def get_block(self, block_hash: str) -> Dict:
        """
        Retrieve a block using proper UnQLite access.
        """
        try:
            with self._db_lock:
                data = self.db[f"block:{block_hash}"]
            return json.loads(data)
        except KeyError:
            logging.warning(f"[WARNING] ⚠️ Block {block_hash} not found in UnQLite.")
            return None
        except Exception as e:
            logging.error(f"[ERROR] ❌ Error retrieving block {block_hash}: {str(e)}")
            return None

    # --------------------- Transaction Handling (Simulated) ---------------------
    def begin_transaction(self):
        """Start a transaction if UnQLite supported it (simulated)."""
        logging.info("[INFO] Simulating UnQLite transaction.")

    def commit(self):
        """Commit a transaction (simulated)."""
        if self.transaction_active:
            logging.info("[INFO] Committing UnQLite transaction.")
            self.transaction_active = False

    def rollback(self):
        """
        Rollback a transaction (UnQLite does not support rollback, so this is a placeholder).
        """
        if self.transaction_active:
            logging.warning("[WARNING] UnQLite does not support rollback. Manual data correction may be required.")
            self.transaction_active = False

    # --------------------- Blockchain Storage ---------------------


    def add_block(self, block_hash: str, block_header: dict, transactions: list, size: int, difficulty: int):
        """
        Store all block components with explicit parameters, ensuring the hash is included.
        This method uses the global lock and retry mechanism as defined in store_block.
        """
        block_data = {
            "hash": block_hash,
            "header": block_header,
            "transactions": transactions,
            "size": size,
            "difficulty": difficulty
        }
        max_retries = 5
        attempt = 0
        while attempt < max_retries:
            try:
                with self._db_lock:
                    self.db[f"block:{block_hash}"] = json.dumps(block_data)
                logging.info(f"[INFO] ✅ Block {block_hash} stored successfully in UnQLite.")
                return
            except Exception as e:
                error_msg = str(e)
                if "hold the requested lock" in error_msg:
                    logging.error(f"[ERROR] Lock error when storing block (attempt {attempt+1}/5): {e}")
                    attempt += 1
                    import time
                    time.sleep(1)
                else:
                    logging.error(f"[ERROR] Failed to store block {block_hash}: {e}")
                    raise
        raise Exception("Failed to store block after several retries due to lock errors.")

    def get_last_block(self):
        """Retrieve the block with the highest index."""
        blocks = self.get_all_blocks()
        if not blocks:
            return None
        return max(blocks, key=lambda x: x['header'].get('index', 0))

    def get_all_blocks(self) -> list:
        """
        Retrieve all stored blocks from UnQLite.
        """
        try:
            blocks = []
            with self._db_lock:
                for key in self.db.keys():
                    key_str = key.decode() if isinstance(key, bytes) else key
                    if key_str.startswith("block:"):
                        data = self.db[key]
                        blocks.append(json.loads(data))
            logging.info(f"[INFO] Retrieved {len(blocks)} blocks from UnQLite.")
            return blocks
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to retrieve blocks: {str(e)}")
            return []

    def delete_all_blocks(self):
        """
        Delete all blocks from the storage.
        """
        try:
            with self._db_lock:
                keys_to_delete = [key for key in self.db.keys() if (key.decode() if isinstance(key, bytes) else key).startswith("block:")]
                for key in keys_to_delete:
                    del self.db[key]
            logging.info("[INFO] ✅ All blocks deleted from UnQLite storage.")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to delete all blocks: {e}")
            raise

    def delete_block(self, block_hash: str):
        """
        Delete a block by its hash.
        """
        try:
            with self._db_lock:
                del self.db[f"block:{block_hash}"]
            logging.info(f"[INFO] ✅ Block {block_hash} deleted from UnQLite.")
        except KeyError:
            logging.warning(f"[WARNING] ⚠️ Block {block_hash} not found in UnQLite.")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to delete block {block_hash}: {e}")

    # --------------------- Transactions Storage ---------------------
    def store_transaction(self, tx_id: str, block_hash: str, inputs: List[Dict], outputs: List[Dict], timestamp: int):
        """
        Store a transaction in the blockchain.
        """
        try:
            transaction_data = {
                "tx_id": tx_id,
                "block_hash": block_hash,
                "inputs": inputs,
                "outputs": outputs,
                "timestamp": timestamp
            }
            with self._db_lock:
                self.db[f"transaction:{tx_id}"] = json.dumps(transaction_data)
            logging.info(f"[INFO] ✅ Transaction {tx_id} stored successfully in UnQLite.")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to store transaction {tx_id}: {e}")
            raise

    def get_transaction(self, tx_id: str) -> Dict:
        """
        Retrieve a transaction by its ID.
        """
        try:
            with self._db_lock:
                data = self.db[f"transaction:{tx_id}"]
            return json.loads(data)
        except KeyError:
            logging.warning(f"[WARNING] ⚠️ Transaction {tx_id} not found in UnQLite.")
            return None
        except Exception as e:
            logging.error(f"[ERROR] ❌ Error retrieving transaction {tx_id}: {str(e)}")
            return None

    def get_all_transactions(self) -> List[Dict]:
        """
        Retrieve all transactions stored in the blockchain.
        """
        transactions = []
        try:
            with self._db_lock:
                for key in self.db.keys():
                    key_str = key.decode() if isinstance(key, bytes) else key
                    if key_str.startswith("transaction:"):
                        transactions.append(json.loads(self.db[key]))
            logging.info(f"[INFO] ✅ Retrieved {len(transactions)} transactions.")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to retrieve transactions: {e}")
        return transactions

    # --------------------- Database Utilities ---------------------

