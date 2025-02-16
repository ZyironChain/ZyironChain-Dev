import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))



import json
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.transactions. utxo_manager import UTXOManager
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction
import logging

import logging

# Remove all existing handlers (prevents log conflicts across modules)
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Set up clean logging for this module
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

log = logging.getLogger(__name__)  # Each module gets its own logger

log.info(f"{__name__} logger initialized.")


# Ensure this is at the very top of your script, before any other code
class StorageManager:
    def __init__(self, poc_instance, block_manager=None):
        """
        Initialize the Storage Manager.
        :param poc_instance: PoC instance for routing transactions.
        :param block_manager: (Optional) BlockManager instance.
        """
        self.poc = poc_instance  # ✅ Store PoC instance
        self.utxo_manager = UTXOManager(poc_instance)  # ✅ Initialize UTXO Manager
        self.block_manager = block_manager  # ✅ Ensure block_manager is stored properly

        # ✅ FIX: Ensure `unqlite_db` is correctly assigned from PoC
        if hasattr(self.poc, "unqlite_db"):
            self.unqlite_db = self.poc.unqlite_db
        else:
            raise AttributeError("[ERROR] PoC instance does not have 'unqlite_db'.")

    def store_block(self, block, difficulty):
        try:
            stored_data = {
                "index": block.index,
                "hash": block.hash,
                "block_header": block.header.to_dict(),
                "transactions": [tx.to_dict() for tx in block.transactions],
                "size": len(block.transactions),
                "difficulty": difficulty
            }

            if hasattr(self.unqlite_db, "add_block"):
                self.unqlite_db.add_block(
                    block.hash, stored_data, stored_data["transactions"], stored_data["size"], difficulty
                )
                logging.debug(f"Successfully stored Block {block.index} with Difficulty: {hex(difficulty)}")
            else:
                raise AttributeError("'unqlite_db' does not have 'add_block' method.")

            # ✅ Debugging: Verify block retrieval
            stored_block = self.get_block(block.hash)
            if not stored_block:
                raise RuntimeError(f"[ERROR] Block {block.index} failed to store in UnQLite!")

        except AttributeError as e:
            logging.error(f"Attribute error while storing block {block.index}: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error while storing block {block.index}: {str(e)}")
            raise




    def get_block(self, block_hash):
        """
        Retrieves a block from UnQLite and verifies that it was correctly stored.
        """
        try:
            # 🚨 DEBUGGING: Check if `unqlite_db.get_block()` exists
            if not hasattr(self.unqlite_db, "get_block"):
                raise AttributeError("[ERROR] 'unqlite_db' does not have 'get_block' method.")

            block_data = self.unqlite_db.get_block(block_hash)

            # ✅ DEBUG: Print retrieved block information
            if block_data:
                logging.info(f"[DEBUG] Retrieved Block {block_hash} - Difficulty: {hex(block_data['block_header']['difficulty'])}")
                return block_data
            else:
                logging.error(f"[ERROR] Block {block_hash} was not found in UnQLite!")
                return None

        except Exception as e:
            logging.error(f"[ERROR] Failed to retrieve block {block_hash}: {str(e)}")
            return None




    def load_chain(self):
        self.poc.load_blockchain_data()
        return self.poc.get_blockchain_data()






    def _store_block_metadata(self, block):
        metadata = {
            "height": block.index,
            "parent_hash": block.previous_hash,
            "timestamp": block.timestamp,
        }
        self.poc.lmdb_manager.put(f"block_metadata:{block.hash}", json.dumps(metadata))

    def save_blockchain_state(self, chain, pending_transactions=None):
        """
        Save the current state of the blockchain.
        :param chain: The blockchain (list of blocks).
        :param pending_transactions: (Optional) List of pending transactions.
        """
        if pending_transactions is None:
            pending_transactions = []  # Default to an empty list if not provided

        data = {
            "chain": [block.to_dict() for block in chain],
            "pending_transactions": [tx.to_dict() for tx in pending_transactions]
        }
        with open("blockchain_state.json", "w") as f:
            json.dump(data, f, indent=4)


    def export_utxos(self):
        for utxo_key, utxo_value in self.utxo_manager.get_all_utxos().items():
            self.poc.lmdb_manager.put(f"utxo:{utxo_key}", json.dumps(utxo_value))

    def get_transaction(self, tx_id):
        tx_data = self.poc.lmdb_manager.get(f"transaction:{tx_id}")
        return Transaction.from_dict(json.loads(tx_data)) if tx_data else None
