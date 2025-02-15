import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))



import json
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.transactions. utxo_manager import UTXOManager
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction
import logging
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
        """
        Store a block in UnQLite database.
        :param block: The block to store.
        :param difficulty: The difficulty at which this block was mined.
        """
        print(f"[DEBUG] Storing Block {block.index} - Difficulty: {hex(difficulty)}")

        try:
            stored_data = {
                "index": block.index,
                "hash": block.hash,
                "block_header": block.header.to_dict(),
                "transactions": [tx.to_dict() for tx in block.transactions],
                "size": len(block.transactions),
                "difficulty": difficulty  # ✅ Ensure difficulty is stored correctly
            }

            if hasattr(self.unqlite_db, "add_block"):
                self.unqlite_db.add_block(
                    block.hash, stored_data, stored_data["transactions"], stored_data["size"], difficulty
                )
                print(f"[DEBUG] Successfully stored Block {block.index} with Difficulty: {hex(difficulty)}")
            else:
                raise AttributeError("[ERROR] 'unqlite_db' does not have 'add_block' method.")

        except Exception as e:
            print(f"[ERROR] Failed to store block {block.index}: {str(e)}")
            raise


    def get_block(self, block_hash):
        """
        Retrieve a block from the UnQLite database.
        :param block_hash: The hash of the block to retrieve.
        :return: Block data if found, else None.
        """
        try:
            if hasattr(self.unqlite_db, "get_block"):
                block_data = self.unqlite_db.get_block(block_hash)
                if block_data:
                    print(f"[DEBUG] Retrieved Block {block_hash} - Difficulty: {hex(block_data['block_header']['difficulty'])}")
                    return block_data
            else:
                raise AttributeError("[ERROR] 'unqlite_db' does not have 'get_block' method.")
        except Exception as e:
            print(f"[ERROR] Failed to retrieve block {block_hash}: {str(e)}")
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

    def save_blockchain_state(self, chain, pending_transactions):
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
