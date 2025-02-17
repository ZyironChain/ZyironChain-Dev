from unqlite import UnQLite
import json
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)

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
        self.transaction_active = False  # Ensure this attribute is initialized properly

    def get_block(self, block_hash: str) -> Dict:
        """
        Retrieve a block using proper UnQLite access.
        """
        try:
            return json.loads(self.db[f"block:{block_hash}"])
        except KeyError:
            logging.warning(f"[WARNING] Block {block_hash} not found in UnQLite.")
            return None
        except Exception as e:
            logging.error(f"[ERROR] Error retrieving block: {str(e)}")
            return None

    # --------------------- Transaction Handling (Simulated) ---------------------
    def begin_transaction(self):
        """Start a transaction if UnQLite supported it (simulated)."""
        logging.info("[INFO] Simulating UnQLite transaction.")

    def commit(self):
        """
        Commit a transaction (simulated).
        """
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
    def store_block(self, block, difficulty):
        """
        Store a block in UnQLite, ensuring all required fields are passed.
        """
        try:
            # Ensure block header is a dictionary
            block_header = block.header.to_dict() if hasattr(block.header, "to_dict") else block.header

            # Ensure transactions are properly formatted
            transactions = []
            for tx in block.transactions:
                if hasattr(tx, "to_dict"):
                    transactions.append(tx.to_dict())
                elif isinstance(tx, dict):
                    transactions.append(tx)  # Already a dict
                else:
                    logging.warning(f"[WARNING] Skipping invalid transaction format: {tx}")

            # ✅ Ensure size is the correct transaction count
            size = len(transactions)

            # ✅ Call `add_block()` with all required parameters
            self.unqlite_db.add_block(
                block_hash=block.hash,
                block_header=block_header,
                transactions=transactions,
                size=size,
                difficulty=difficulty
            )

            logging.info(f"[INFO] Block {block.index} stored successfully in UnQLite.")

        except Exception as e:
            logging.error(f"[ERROR] Block storage failed: {str(e)}")
            raise


    def add_block(self, block_hash: str, block_header: dict, transactions: list, size: int, difficulty: int):
        """Store all block components with explicit parameters, ensuring the hash is included."""
        block_data = {
            "hash": block_hash,  # ✅ Ensure hash is explicitly stored
            "header": block_header,
            "transactions": transactions,
            "size": size,
            "difficulty": difficulty
        }
        self.db[f"block:{block_hash}"] = json.dumps(block_data)  # ✅ Store properly
        logging.info(f"✅ Block {block_hash} stored successfully in UnQLite.")



    def get_all_blocks(self):
        """
        Retrieve all stored blocks from UnQLite.
        """
        try:
            blocks = []
            for key in self.db.keys():
                # Convert key to string if it is in bytes
                key_str = key.decode() if isinstance(key, bytes) else key
                if key_str.startswith("block:"):
                    block_data = json.loads(self.db[key])
                    blocks.append(block_data)
            logging.debug(f"[DEBUG] Blocks Retrieved from UnQLite: {blocks}")
            return blocks
        except Exception as e:
            logging.error(f"[ERROR] Failed to retrieve blocks: {str(e)}")
            return []

    def delete_all_blocks(self):
        """
        Delete all blocks from the storage.
        """
        try:
            # Gather keys to delete (ensuring proper decoding if keys are bytes)
            keys_to_delete = []
            for key in self.db.keys():
                key_str = key.decode() if isinstance(key, bytes) else key
                if key_str.startswith("block:"):
                    keys_to_delete.append(key)
            for key in keys_to_delete:
                del self.db[key]
            logging.info("[INFO] All blocks deleted from UnQLite storage.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to delete all blocks: {e}")
            raise

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
            self.db[f"transaction:{tx_id}"] = json.dumps(transaction_data)
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
                key_str = key.decode() if isinstance(key, bytes) else key
                if key_str.startswith("transaction:"):
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

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    db = BlockchainUnqliteDB()

    # ✅ Insert test block
    block_data = {
        "hash": "dummyhash",
        "header": {
            "index": 0,
            "previous_hash": "0",
            "timestamp": 1234567890,
            "nonce": 0,
            "difficulty": 1000
        },
        "transactions": [
            {"tx_id": "tx_dummy", "inputs": [], "outputs": [], "timestamp": 1234567890}
        ],
        "size": 1,
        "difficulty": 1000
    }

    db.store_block(block_data)  # ✅ Pass entire block dictionary

    # ✅ Insert test transaction
    tx_data = {
        "tx_id": "tx_dummy",
        "block_hash": "dummyhash",
        "inputs": [{"tx_out_id": "utxo1", "script_sig": "sig1"}],
        "outputs": [{"script_pub_key": "pubkey1", "amount": 100.5}],
        "timestamp": 1234567890
    }

    db.store_transaction(tx_data)  # ✅ Pass transaction dictionary

    # ✅ Fetch and display data
    print("Blocks:", json.dumps(db.get_all_blocks(), indent=4))  # Pretty print
    print("Transactions:", json.dumps(db.get_all_transactions(), indent=4))

    # ✅ Delete all blocks (for testing)
    db.delete_all_blocks()

    # ✅ Display data after deletion
    print("After deletion, Blocks:", db.get_all_blocks())

    # ✅ Clean up
    db.clear_database()
    db.close()
