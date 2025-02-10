import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))



import json
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.transactions. utxo_manager import UTXOManager
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction

class StorageManager:
    def __init__(self, poc_instance):
        self.poc = poc_instance
        self.utxo_manager = UTXOManager(poc_instance)

    def load_chain(self):
        self.poc.load_blockchain_data()
        return self.poc.get_blockchain_data()

    def store_block(self, block, difficulty):
        self.poc.store_block(block, difficulty)
        self._store_block_metadata(block)

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
