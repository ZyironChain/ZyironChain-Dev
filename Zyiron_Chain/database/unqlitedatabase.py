from unqlite import UnQLite
import json
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)

from unqlite import UnQLite
import json
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)

class BlockchainUnqliteDB:
    def __init__(self, db_file="blockchain.db"):
        """
        Initialize the UnQLite database for storing the immutable blockchain.
        """
        self.db = UnQLite(db_file)
        self.transaction_active = False  # ✅ Ensure this attribute is initialized properly
    
    # ✅ Modified get_block method
    def get_block(self, block_hash: str) -> Dict:
        """
        Retrieve a block using proper UnQLite access.
        """
        try:
            return json.loads(self.db[f"block:{block_hash}"])  # ✅ Use `self.db` correctly
        except KeyError:
            print(f"[WARNING] Block {block_hash} not found in UnQLite.")
            return None
        except Exception as e:
            logging.error(f"Error retrieving block: {str(e)}")
            return None


    # --------------------- Transaction Handling (Simulated) ---------------------
    def begin_transaction(self):
        """Start a transaction if UnQLite supported it (simulated)."""
        logging.info("[INFO] Simulating UnQLite transaction.")  # ✅ Just log instead of checking transaction_active


    def commit(self):
        """
        Commit a transaction (simulated).
        """
        if self.transaction_active:
            logging.info("[INFO] Committing UnQLite transaction.")
            self.transaction_active = False  # Reset transaction flag

    def rollback(self):
        """
        Rollback a transaction (UnQLite does not support rollback, so this is a placeholder).
        """
        if self.transaction_active:
            logging.warning("[WARNING] UnQLite does not support rollback. Manual data correction may be required.")
            self.transaction_active = False  # Reset transaction flag

    # --------------------- Blockchain Storage ---------------------
    def store_block(self, block_hash: str, block_header: Dict, transactions: List[Dict], size: int, difficulty: int):
        """
        Store a block in the immutable blockchain database.
        - Fixes missing 'transaction_active' attribute.
        - Ensures proper storage of transactions.
        """
        try:
            self.transaction_active = True  # ✅ Start transaction flag

            if hasattr(block_header, 'to_dict'):
                block_header = block_header.to_dict()

            serialized_transactions = [
                tx.to_dict() if hasattr(tx, 'to_dict') else tx for tx in transactions
            ]

            block_data = {
                "block_header": block_header,
                "transactions": serialized_transactions,
                "size": size,
                "difficulty": difficulty
            }

            self.db[f"block:{block_hash}"] = json.dumps(block_data)  # ✅ Fix storage
            self.transaction_active = False  # ✅ Reset transaction flag

            logging.info(f"[INFO] Block {block_hash} successfully stored.")
        except Exception as e:
            self.transaction_active = False
            logging.error(f"[ERROR] Failed to store block {block_hash}: {e}")
            raise

    def add_block(self, block_hash: str, block_header: dict, transactions: list, size: int, difficulty: int):
        """Store all block components with explicit parameters"""
        block_data = {
            "header": block_header,
            "transactions": transactions,
            "size": size,
            "difficulty": difficulty
        }
        self.db[f"block:{block_hash}"] = json.dumps(block_data)
        logging.info(f"Block {block_hash} stored")

        
    def get_all_blocks(self):
        """
        Retrieve all stored blocks from UnQLite.
        """
        try:
            blocks = []
            for key in self.db.keys():  # ✅ FIX: Use `self.db.keys()` instead of `self.unqlite_db.get_all()`
                if key.startswith("block:"):
                    block_data = json.loads(self.db[key])
                    blocks.append(block_data)

            print(f"[DEBUG] Blocks Retrieved from UnQLite: {blocks}")  # ✅ Log retrieved blocks
            return blocks

        except Exception as e:
            print(f"[ERROR] Failed to retrieve blocks: {str(e)}")
            return []




    def delete_block(self, block_hash: str):
        """
        Delete a block by its hash (should not be used in immutable blockchain, but for testing only).
        :param block_hash: The hash of the block to delete.
        """
        try:
            del self.db[f"block:{block_hash}"]
            logging.info(f"[INFO] Block {block_hash} deleted.")
        except KeyError:
            logging.warning(f"[WARNING] Block {block_hash} not found.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to delete block {block_hash}: {e}")

    # --------------------- Transactions Storage ---------------------
    def store_transaction(self, tx_id: str, block_hash: str, inputs: List[Dict], outputs: List[Dict], timestamp: int):
        """
        Store a transaction in the blockchain.
        :param tx_id: Transaction ID.
        :param block_hash: Hash of the block containing this transaction.
        :param inputs: List of transaction inputs.
        :param outputs: List of transaction outputs.
        :param timestamp: Transaction timestamp.
        """
        try:
            transaction_data = {
                "block_hash": block_hash,
                "inputs": inputs,
                "outputs": outputs,
                "timestamp": timestamp
            }
            self.db[f"transaction:{tx_id}"] = json.dumps(transaction_data)  # Store as JSON
            logging.info(f"[INFO] Transaction {tx_id} stored.")

        except Exception as e:
            logging.error(f"[ERROR] Failed to store transaction {tx_id}: {e}")
            raise

    def get_transaction(self, tx_id: str) -> Dict:
        """
        Retrieve a transaction by its ID.
        :param tx_id: The transaction ID.
        :return: The transaction data as a dictionary, or None if not found.
        """
        try:
            return json.loads(self.db[f"transaction:{tx_id}"])
        except KeyError:
            logging.warning(f"[WARNING] Transaction {tx_id} not found.")
            return None
        except Exception as e:
            logging.error(f"[ERROR] Failed to retrieve transaction {tx_id}: {e}")
            return None

    def get_all_transactions(self) -> List[Dict]:
        """
        Retrieve all transactions stored in the blockchain.
        :return: A list of transaction dictionaries.
        """
        transactions = []
        try:
            for key in self.db.keys():
                if key.startswith("transaction:"):
                    transactions.append(json.loads(self.db[key]))
            logging.info(f"[INFO] Retrieved {len(transactions)} transactions.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to retrieve transactions: {e}")
        return transactions

    # --------------------- Database Utilities ---------------------
    def clear_database(self):
        """
        Completely wipe the blockchain storage (for testing only).
        """
        try:
            for key in list(self.db.keys()):
                del self.db[key]
            logging.info("[INFO] Blockchain database cleared.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to clear database: {e}")

    def close(self):
        """
        Close the database connection.
        """
        try:
            self.db.close()
            logging.info("[INFO] Database connection closed.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to close database connection: {e}")
