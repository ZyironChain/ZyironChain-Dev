from unqlite import UnQLite
import json
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)

class BlockchainUnqliteDB:
    def __init__(self, db_file="blockchain.db"):
        """
        Initialize the UnQLite database for blockchain storage.
        :param db_file: Path to the UnQLite database file.
        """
        self.db = UnQLite(db_file)

    # --------------------- Blocks Management ---------------------
    def add_block(self, block_hash: str, block_header: Dict, transactions: List[Dict], size: int, difficulty: int):
        """
        Add a block to the database.
        :param block_hash: The hash of the block.
        :param block_header: The block header (as a dictionary or object with to_dict method).
        :param transactions: List of transactions (as dictionaries or objects with to_dict method).
        :param size: The size of the block in bytes.
        :param difficulty: The mining difficulty of the block.
        """
        try:
            # Ensure block_header is a dictionary (serialize if necessary)
            if hasattr(block_header, 'to_dict'):
                block_header = block_header.to_dict()  # Convert BlockHeader object to dictionary

            # Ensure all transactions are dictionaries (serialize if necessary)
            serialized_transactions = []
            for tx in transactions:
                if hasattr(tx, 'to_dict'):
                    serialized_transactions.append(tx.to_dict())  # Convert Transaction object to dictionary
                else:
                    serialized_transactions.append(tx)  # Assume it's already a dictionary

            # Validate required fields
            required_fields = ["index", "previous_hash", "merkle_root", "timestamp", "nonce"]
            for field in required_fields:
                if field not in block_header:
                    raise ValueError(f"Block header is missing required field: {field}")

            block_data = {
                "block_header": block_header,
                "transactions": serialized_transactions,
                "size": size,
                "difficulty": difficulty
            }
            self.db[f"block:{block_hash}"] = json.dumps(block_data)  # Store as JSON string with prefix
            logging.info(f"[INFO] Block {block_hash} added.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to add block {block_hash}: {e}")
            raise

    def get_block(self, block_hash: str) -> Dict:
        """
        Retrieve a block by its hash.
        :param block_hash: The hash of the block to retrieve.
        :return: The block data as a dictionary, or None if not found.
        """
        try:
            return json.loads(self.db[f"block:{block_hash}"])  # Decode JSON string with prefix
        except KeyError:
            logging.error(f"[ERROR] Block {block_hash} not found.")
            return None
        except Exception as e:
            logging.error(f"[ERROR] Failed to retrieve block {block_hash}: {e}")
            return None

    def get_all_blocks(self) -> List[Dict]:
        """
        Retrieve all blocks in the database.
        :return: A list of block data dictionaries.
        """
        blocks = []
        try:
            for key in self.db.keys():
                if key.startswith("block:"):
                    blocks.append(json.loads(self.db[key]))
            logging.info(f"[INFO] Retrieved {len(blocks)} blocks.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to retrieve blocks: {e}")
        return blocks

    def delete_block(self, block_hash: str):
        """
        Delete a block by its hash.
        :param block_hash: The hash of the block to delete.
        """
        try:
            del self.db[f"block:{block_hash}"]
            logging.info(f"[INFO] Block {block_hash} deleted.")
        except KeyError:
            logging.error(f"[ERROR] Block {block_hash} not found.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to delete block {block_hash}: {e}")

    # --------------------- Transactions Management ---------------------
    def add_transaction(self, tx_id: str, block_hash: str, inputs: List[Dict], outputs: List[Dict], timestamp: int):
        """
        Add a transaction to the database.
        :param tx_id: The ID of the transaction.
        :param block_hash: The hash of the block containing the transaction.
        :param inputs: List of transaction inputs.
        :param outputs: List of transaction outputs.
        :param timestamp: The timestamp of the transaction.
        """
        try:
            transaction_data = {
                "block_hash": block_hash,
                "inputs": inputs,
                "outputs": outputs,
                "timestamp": timestamp
            }
            self.db[f"transaction:{tx_id}"] = json.dumps(transaction_data)  # Store as JSON string with prefix
            logging.info(f"[INFO] Transaction {tx_id} added.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to add transaction {tx_id}: {e}")
            raise

    def get_transaction(self, tx_id: str) -> Dict:
        """
        Retrieve a transaction by its ID.
        :param tx_id: The ID of the transaction to retrieve.
        :return: The transaction data as a dictionary, or None if not found.
        """
        try:
            return json.loads(self.db[f"transaction:{tx_id}"])  # Decode JSON string with prefix
        except KeyError:
            logging.error(f"[ERROR] Transaction {tx_id} not found.")
            return None
        except Exception as e:
            logging.error(f"[ERROR] Failed to retrieve transaction {tx_id}: {e}")
            return None

    def get_all_transactions(self) -> List[Dict]:
        """
        Retrieve all transactions in the database.
        :return: A list of transaction data dictionaries.
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

    def delete_transaction(self, tx_id: str):
        """
        Delete a transaction by its ID.
        :param tx_id: The ID of the transaction to delete.
        """
        try:
            del self.db[f"transaction:{tx_id}"]
            logging.info(f"[INFO] Transaction {tx_id} deleted.")
        except KeyError:
            logging.error(f"[ERROR] Transaction {tx_id} not found.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to delete transaction {tx_id}: {e}")

    # --------------------- UTXO Management ---------------------
    def add_spent_utxo(self, tx_out_id: str, consumed_by: str, block_hash: str):
        """
        Add a spent UTXO to the database.
        :param tx_out_id: The ID of the UTXO.
        :param consumed_by: The transaction ID that consumed the UTXO.
        :param block_hash: The hash of the block containing the transaction.
        """
        try:
            utxo_data = {
                "consumed_by": consumed_by,
                "block_hash": block_hash
            }
            self.db[f"spent_utxo:{tx_out_id}"] = json.dumps(utxo_data)  # Store as JSON string with prefix
            logging.info(f"[INFO] Spent UTXO {tx_out_id} added.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to add spent UTXO {tx_out_id}: {e}")
            raise

    def get_spent_utxo(self, tx_out_id: str) -> Dict:
        """
        Retrieve a spent UTXO by its ID.
        :param tx_out_id: The ID of the UTXO to retrieve.
        :return: The UTXO data as a dictionary, or None if not found.
        """
        try:
            return json.loads(self.db[f"spent_utxo:{tx_out_id}"])  # Decode JSON string with prefix
        except KeyError:
            logging.error(f"[ERROR] Spent UTXO {tx_out_id} not found.")
            return None
        except Exception as e:
            logging.error(f"[ERROR] Failed to retrieve spent UTXO {tx_out_id}: {e}")
            return None

    def get_all_spent_utxos(self) -> List[Dict]:
        """
        Retrieve all spent UTXOs in the database.
        :return: A list of spent UTXO data dictionaries.
        """
        utxos = []
        try:
            for key in self.db.keys():
                if key.startswith("spent_utxo:"):
                    utxos.append(json.loads(self.db[key]))
            logging.info(f"[INFO] Retrieved {len(utxos)} spent UTXOs.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to retrieve spent UTXOs: {e}")
        return utxos

    def delete_spent_utxo(self, tx_out_id: str):
        """
        Delete a spent UTXO by its ID.
        :param tx_out_id: The ID of the UTXO to delete.
        """
        try:
            del self.db[f"spent_utxo:{tx_out_id}"]
            logging.info(f"[INFO] Spent UTXO {tx_out_id} deleted.")
        except KeyError:
            logging.error(f"[ERROR] Spent UTXO {tx_out_id} not found.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to delete spent UTXO {tx_out_id}: {e}")

    # --------------------- General Utilities ---------------------
    def clear_database(self):
        """
        Clear all data in the database.
        """
        try:
            for key in list(self.db.keys()):
                del self.db[key]
            logging.info("[INFO] Database cleared.")
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

# --------------------- Test Script ---------------------
if __name__ == "__main__":
    blockchain_db = BlockchainUnqliteDB(":mem:")  # Use in-memory for testing

    # Test adding a block
    blockchain_db.add_block(
        block_hash="block1",
        block_header={"index": 1, "previous_hash": "0", "merkle_root": "abc123", "timestamp": 1234567890, "nonce": 1000, "miner": "miner1"},
        transactions=[{"tx_id": "tx1", "inputs": [], "outputs": [{"amount": 50, "script_pub_key": "miner1"}]}],
        size=1024,
        difficulty=2
    )

    # Test retrieving a block
    print("Block:", blockchain_db.get_block("block1"))

    # Test clearing the database
    blockchain_db.clear_database()
    blockchain_db.close()