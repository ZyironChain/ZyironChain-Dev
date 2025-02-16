import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))



import json
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.transactions. utxo_manager import UTXOManager
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction
import logging
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.blockchain.blockheader import BlockHeader
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
import logging
import json

class StorageManager:
    def __init__(self, poc_instance, block_manager=None):
        self.poc = poc_instance
        self.utxo_manager = UTXOManager(poc_instance)
        self.block_manager = block_manager

        # Get unqlite_db from PoC with validation
        self.unqlite_db = getattr(poc_instance, "unqlite_db", None)
        if not self.unqlite_db:
            raise AttributeError("[ERROR] PoC instance missing 'unqlite_db'")


    def get_all_blocks(self):
        """Retrieve and convert stored blocks"""
        try:
            raw_blocks = self.unqlite_db.get_all_blocks()
            return [
                {
                    'header': {
                        'index': b['header']['index'],
                        'previous_hash': b['header']['previous_hash'],
                        'merkle_root': b['header']['merkle_root'],
                        'timestamp': b['header']['timestamp'],
                        'nonce': b['header']['nonce'],
                        'difficulty': b['header']['difficulty'],
                        'version': b['header'].get('version', 1)
                    },
                    'transactions': b['transactions'],
                    'miner_address': b.get('miner_address')
                }
                for b in raw_blocks
            ]
        except KeyError as e:
            logging.error(f"Invalid block format in storage: {str(e)}")
            return []

    def store_block(self, block, difficulty):
        try:
            self.unqlite_db.add_block(
                block_hash=block.hash,  # ✅ Keep as keyword argument
                block_header=block.header.to_dict(),
                transactions=[tx.to_dict() for tx in block.transactions],
                size=len(block.transactions),
                difficulty=difficulty
            )
        except Exception as e:
            logging.error(f"Block storage failed: {str(e)}")
            raise


    def get_block(self, block_hash):
        try:
            raw_data = self.unqlite_db.get_block(block_hash)
            if not raw_data:
                return None
                
            # Rebuild block header properly
            header_data = raw_data["header"]
            block_header = BlockHeader(
                version=header_data["version"],
                index=header_data["index"],  # Now included
                previous_hash=header_data["previous_hash"],
                merkle_root=header_data["merkle_root"],
                timestamp=header_data["timestamp"],
                nonce=header_data["nonce"],
                difficulty=header_data["difficulty"]
            )
            
            transactions = [
                Transaction.from_dict(tx) 
                for tx in raw_data["transactions"]
            ]
            
            return Block(
                index=header_data["index"],
                previous_hash=header_data["previous_hash"],
                transactions=transactions,
                timestamp=header_data["timestamp"],
                nonce=header_data["nonce"],
                difficulty=header_data["difficulty"],
                miner_address=None  # Add if available
            )
        
        except KeyError as e:
            logging.error(f"Missing key in stored block: {str(e)}")
            return None
# In your StorageManager class
    def verify_block_storage(self, block: Block) -> bool:
        """Validate block exists using its hash"""
        try:
            stored_data = self.unqlite_db.get_block(block.hash)
            return stored_data is not None
        except Exception as e:
            logging.error(f"Storage verification failed: {str(e)}")
            return False

    def validate_block_structure(self, block):
        """Validate critical block fields"""
        required_fields = ['index', 'hash', 'header', 'transactions']
        return all(hasattr(block, field) for field in required_fields)

    def save_blockchain_state(self, chain, pending_transactions=None):
        """Save state with atomic write operations"""
        data = {
            "chain": [self._block_to_storage_format(block) for block in chain],
            "pending_transactions": [tx.to_dict() for tx in pending_transactions or []]
        }
        
        try:
            # Atomic write using temp file
            with open("blockchain_state.tmp", "w") as f:
                json.dump(data, f)
            os.replace("blockchain_state.tmp", "blockchain_state.json")
        except Exception as e:
            logging.error(f"State save failed: {str(e)}")
            raise

    def _block_to_storage_format(self, block):
        """Convert block to storage-safe format"""
        return {
            "header": block.header.to_dict(),
            "transactions": [tx.to_dict() for tx in block.transactions],
            "hash": block.hash,
            "size": len(block.transactions)
        }

    # Maintained existing methods with attribute access fixes
    def load_chain(self):
        return self.poc.load_blockchain_data()

    def _store_block_metadata(self, block):
        metadata = {
            "height": block.index,
            "parent_hash": block.previous_hash,
            "timestamp": block.header.timestamp  # Fixed timestamp access
        }
        self.poc.lmdb_manager.put(f"block_metadata:{block.hash}", json.dumps(metadata))

    def export_utxos(self):
        for utxo_key, utxo_value in self.utxo_manager.get_all_utxos().items():
            self.poc.lmdb_manager.put(f"utxo:{utxo_key}", json.dumps(utxo_value))

    def get_transaction(self, tx_id):
        tx_data = self.poc.lmdb_manager.get(f"transaction:{tx_id}")
        return Transaction.from_dict(json.loads(tx_data)) if tx_data else None