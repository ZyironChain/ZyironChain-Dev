import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


import pickle
import json
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.transactions. utxo_manager import UTXOManager
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction
import logging
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.blockchain.blockheader import BlockHeader
import logging
import time 
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

from typing import List, Optional
from typing import Dict, Optional
# Ensure this is at the very top of your script, before any other code
import logging
import json
from Zyiron_Chain.blockchain.constants import Constants
class StorageManager:
    def __init__(self, poc_instance, block_manager=None):
        self.poc = poc_instance
        self.utxo_manager = UTXOManager(poc_instance)
        self.block_manager = block_manager

        # Get unqlite_db from PoC with validation
        self.unqlite_db = getattr(poc_instance, "unqlite_db", None)
        if not self.unqlite_db:
            raise AttributeError("[ERROR] PoC instance missing 'unqlite_db'")



    def get_latest_block(self):
        """
        Retrieve the most recent block from storage.
        Returns None if no blocks are found.
        """
        try:
            all_blocks = self.get_all_blocks()
            if not all_blocks:
                logging.warning("[STORAGE] ⚠️ No blocks found in storage. Chain may be empty.")
                return None  # No blocks exist in storage

            # ✅ Sort blocks by index to retrieve the latest one
            latest_block_data = max(all_blocks, key=lambda b: b["header"]["index"])

            # ✅ Ensure hash and difficulty are set with constants
            block_hash = latest_block_data.get("hash", Constants.ZERO_HASH)
            block_difficulty = latest_block_data.get("difficulty", Constants.MIN_DIFFICULTY)

            # ✅ Validate block hash presence
            if block_hash == Constants.ZERO_HASH:
                logging.error(f"[ERROR] ❌ Retrieved block is missing 'hash' key: {latest_block_data}")
                return None  # Skip invalid block

            # ✅ Construct and return the latest block
            return Block(
                index=latest_block_data["header"]["index"],
                previous_hash=latest_block_data["header"]["previous_hash"],
                transactions=[Transaction.from_dict(tx) for tx in latest_block_data["transactions"]],
                timestamp=latest_block_data["header"]["timestamp"],
                nonce=latest_block_data["header"]["nonce"],
                difficulty=block_difficulty,  # ✅ Ensure difficulty is properly set
                miner_address=latest_block_data.get("miner_address", "Unknown")  # ✅ Default fallback
            )

        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to retrieve latest block: {str(e)}")
            return None




        # In StorageManager class
    def purge_chain(self):
        """Delete all blockchain data and ensure proper logging."""
        try:
            self.unqlite_db.delete_all_blocks()
            logging.warning("[STORAGE] ⚠️ All blockchain data purged successfully.")
        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to purge blockchain data: {str(e)}")
            raise


    def get_all_blocks(self):
        """Retrieve and convert stored blocks, ensuring all critical fields are included."""
        try:
            raw_blocks = self.unqlite_db.get_all_blocks()
            processed_blocks = []

            for b in raw_blocks:
                # ✅ Enforce presence of essential block fields
                block_hash = b.get("hash", Constants.ZERO_HASH)
                header = b.get("header", {})
                transactions = b.get("transactions", [])
                size = b.get("size", 0)
                miner_address = b.get("miner_address", "Unknown")

                # ✅ Ensure timestamp is present
                block_timestamp = header.get("timestamp", None)
                if not block_timestamp:
                    logging.error(f"[ERROR] ❌ Block missing 'timestamp' field: {b}")
                    continue  # Skip invalid blocks

                # ✅ Ensure difficulty is always set using Constants
                block_difficulty = int(header.get("difficulty", Constants.MIN_DIFFICULTY), 16)

                # ✅ Process block safely
                processed_blocks.append({
                    "hash": block_hash,  # ✅ Enforce presence of block hash
                    "header": {
                        "index": header.get("index", -1),
                        "previous_hash": header.get("previous_hash", Constants.ZERO_HASH),  # ✅ Default to zero-hash
                        "merkle_root": header.get("merkle_root", Constants.ZERO_HASH),
                        "timestamp": block_timestamp,  # ✅ Ensured presence
                        "nonce": header.get("nonce", 0),
                        "difficulty": block_difficulty,  # ✅ Enforced difficulty integrity
                        "version": header.get("version", 1),
                    },
                    "transactions": transactions,
                    "size": size,
                    "difficulty": block_difficulty,  # ✅ Ensure consistency
                    "miner_address": miner_address
                })

            logging.info(f"[STORAGE] ✅ Successfully retrieved {len(processed_blocks)} blocks from UnQLite.")
            return processed_blocks

        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Exception while retrieving blocks: {str(e)}")
            return []

    def store_block(self, block, difficulty):
        """
        Store a block in UnQLite, ensuring the 'hash' key is included and block size is within limits.
        """
        try:
            # ✅ Convert block header to dictionary if necessary
            block_header = block.header.to_dict() if hasattr(block.header, "to_dict") else block.header

            # ✅ Convert transactions to dictionary format
            transactions = [tx.to_dict() if hasattr(tx, "to_dict") else tx for tx in block.transactions]

            # ✅ Calculate block size in bytes
            size = len(json.dumps(transactions).encode("utf-8"))

            # ✅ Ensure block does not exceed max allowed size
            if size > Constants.MAX_BLOCK_SIZE_BYTES:
                logging.error(f"[ERROR] ❌ Block {block.index} exceeds max size limit ({size} bytes > {Constants.MAX_BLOCK_SIZE_BYTES} bytes).")
                raise ValueError("Block size exceeds the maximum allowed limit.")

            # ✅ Ensure difficulty is properly formatted
            difficulty = max(min(difficulty, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

            # ✅ Ensure 'hash' is included at the top level
            block_data = {
                "hash": block.hash,  # ✅ Ensure block hash is stored
                "header": block_header,
                "transactions": transactions,
                "size": size,
                "difficulty": difficulty
            }

            # ✅ Store block in UnQLite
            self.unqlite_db.add_block(
                block_hash=block.hash,
                block_header=block_header,
                transactions=transactions,
                size=size,
                difficulty=difficulty
            )

            logging.info(f"[STORAGE] ✅ Block {block.index} stored successfully in UnQLite. (Size: {size} bytes, Difficulty: {difficulty})")

        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Block storage failed: {str(e)}")
            raise






    def get_block(self, block_hash):
        """
        Retrieve a block from storage using its hash.
        """
        try:
            # ✅ Validate block hash input
            if not isinstance(block_hash, str) or len(block_hash) != Constants.SHA3_384_HASH_SIZE:
                logging.error(f"[ERROR] ❌ Invalid block hash format: {block_hash}")
                return None

            # ✅ Retrieve raw block data from UnQLite
            raw_data = self.unqlite_db.get_block(block_hash)
            if not raw_data:
                logging.warning(f"[WARNING] Block {block_hash} not found in UnQLite.")
                return None

            # ✅ Validate retrieved block structure
            header_data = raw_data.get("header", {})
            if not header_data:
                logging.error(f"[ERROR] ❌ Retrieved block {block_hash} is missing header data.")
                return None

            # ✅ Rebuild BlockHeader object
            block_header = BlockHeader(
                version=header_data.get("version", 1),
                index=header_data.get("index", 0),
                previous_hash=header_data.get("previous_hash", Constants.ZERO_HASH),
                merkle_root=header_data.get("merkle_root", Constants.ZERO_HASH),
                timestamp=header_data.get("timestamp", int(time.time())),  # Default to current time
                nonce=header_data.get("nonce", 0),
                difficulty=header_data.get("difficulty", Constants.MIN_DIFFICULTY)  # ✅ Ensure valid difficulty
            )

            # ✅ Rebuild transactions from stored data
            transactions = [
                Transaction.from_dict(tx) if isinstance(tx, dict) else tx
                for tx in raw_data.get("transactions", [])
            ]

            # ✅ Create and return the Block object
            block = Block(
                index=header_data["index"],
                previous_hash=header_data["previous_hash"],
                transactions=transactions,
                timestamp=header_data["timestamp"],
                nonce=header_data["nonce"],
                difficulty=header_data["difficulty"],
                miner_address=raw_data.get("miner_address", "Unknown")  # ✅ Use default if missing
            )

            logging.info(f"[STORAGE] ✅ Successfully retrieved Block {block.index} (Hash: {block.hash}).")
            return block

        except KeyError as e:
            logging.error(f"[ERROR] ❌ Missing key in stored block {block_hash}: {str(e)}")
            return None

        except Exception as e:
            logging.error(f"[ERROR] ❌ Unexpected error retrieving block {block_hash}: {str(e)}")
            return None

    # In your StorageManager class
    def verify_block_storage(self, block: Block) -> bool:
        """
        Validate if a block exists in storage using its hash.
        """
        try:
            # ✅ Ensure block has a valid hash before querying storage
            if not isinstance(block.hash, str) or len(block.hash) != Constants.SHA3_384_HASH_SIZE:
                logging.error(f"[ERROR] ❌ Invalid block hash format for verification: {block.hash}")
                return False

            # ✅ Check if the block exists in UnQLite
            stored_data = self.unqlite_db.get_block(block.hash)
            if stored_data:
                logging.info(f"[STORAGE] ✅ Block {block.index} exists in UnQLite.")
                return True
            else:
                logging.warning(f"[WARNING] Block {block.index} ({block.hash}) not found in storage.")
                return False

        except Exception as e:
            logging.error(f"[ERROR] ❌ Storage verification failed for Block {block.index}: {str(e)}")
            return False


    def validate_block_structure(self, block: Block) -> bool:
        """
        Validate that a block contains all required fields.
        """
        required_fields = ["index", "hash", "header", "transactions"]

        # ✅ Ensure the block is a valid Block instance
        if not isinstance(block, Block):
            logging.error(f"[ERROR] ❌ Invalid block type: {type(block)}")
            return False

        # ✅ Check for missing attributes
        missing_fields = [field for field in required_fields if not hasattr(block, field)]
        if missing_fields:
            logging.error(f"[ERROR] ❌ Block {block.index} is missing required fields: {missing_fields}")
            return False

        logging.info(f"[STORAGE] ✅ Block {block.index} passed structure validation.")
        return True


    def save_blockchain_state(self, chain: List[Block], pending_transactions: Optional[List[Transaction]] = None):
        """
        Save the blockchain state, including chain data and pending transactions.
        Uses an atomic write operation to prevent data corruption.
        """
        try:
            # ✅ Validate chain integrity before saving
            if not isinstance(chain, list) or not all(isinstance(b, Block) for b in chain):
                logging.error("[ERROR] ❌ Invalid blockchain data format. Cannot save state.")
                return

            # ✅ Validate transactions
            if pending_transactions and not all(isinstance(tx, Transaction) for tx in pending_transactions):
                logging.error("[ERROR] ❌ Invalid pending transaction data format.")
                return

            # ✅ Convert blockchain data to storage-safe format
            data = {
                "chain": [self._block_to_storage_format(block) for block in chain],
                "pending_transactions": [tx.to_dict() for tx in (pending_transactions or [])]
            }

            # ✅ Perform atomic write operation
            temp_file = "blockchain_state.tmp"
            final_file = "blockchain_state.json"

            with open(temp_file, "w") as f:
                json.dump(data, f, indent=4)

            os.replace(temp_file, final_file)
            logging.info("[STORAGE] ✅ Blockchain state saved successfully.")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to save blockchain state: {str(e)}")
            raise




    def _block_to_storage_format(self, block) -> Dict:
        """Convert a block to a storage-safe format."""
        try:
            return {
                "header": block.header.to_dict() if hasattr(block.header, "to_dict") else block.header,
                "transactions": [tx.to_dict() if hasattr(tx, "to_dict") else tx for tx in block.transactions],
                "hash": block.hash,
                "size": len(block.transactions)
            }
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to format block for storage: {str(e)}")
            return {}

    def load_chain(self):
        """Load the blockchain data via PoC."""
        try:
            return self.poc.load_blockchain_data()
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to load blockchain: {str(e)}")
            return []

    def _store_block_metadata(self, block):
        """Store block metadata in LMDB for analytics and indexing."""
        try:
            metadata = {
                "height": block.index,
                "parent_hash": block.previous_hash,
                "timestamp": block.header.timestamp  # ✅ Fixed timestamp access
            }
            self.poc.lmdb_manager.put(f"block_metadata:{block.hash}", json.dumps(metadata))
            logging.info(f"[INFO] ✅ Block metadata stored for {block.hash}")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to store block metadata: {str(e)}")

    def export_utxos(self):
        """Export all unspent UTXOs into LMDB for faster retrieval."""
        try:
            all_utxos = self.utxo_manager.get_all_utxos()
            for utxo_key, utxo_value in all_utxos.items():
                self.poc.lmdb_manager.put(f"utxo:{utxo_key}", json.dumps(utxo_value))
            logging.info(f"[INFO] ✅ Exported {len(all_utxos)} UTXOs to LMDB.")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to export UTXOs: {str(e)}")

    def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        """Retrieve a transaction from LMDB."""
        try:
            tx_data = self.poc.lmdb_manager.get(f"transaction:{tx_id}")
            return Transaction.from_dict(json.loads(tx_data)) if tx_data else None
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to retrieve transaction {tx_id}: {str(e)}")
            return None




    def _block_to_storage_format(self, block) -> Dict:
        """Convert a block to a storage-safe format with error handling."""
        try:
            return {
                "header": block.header.to_dict() if hasattr(block.header, "to_dict") else block.header,
                "transactions": [tx.to_dict() if hasattr(tx, "to_dict") else tx for tx in block.transactions],
                "hash": block.hash,
                "size": len(block.transactions),
                "difficulty": block.header.difficulty  # ✅ Ensure difficulty is stored
            }
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to format block for storage: {str(e)}")
            return {}

    def load_chain(self):
        """Load the blockchain data via PoC with additional logging."""
        try:
            chain_data = self.poc.load_blockchain_data()
            logging.info(f"[INFO] ✅ Loaded {len(chain_data)} blocks from storage.")
            return chain_data
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to load blockchain: {str(e)}")
            return []

    def _store_block_metadata(self, block):
        """Store block metadata in LMDB for analytics and indexing."""
        try:
            metadata = {
                "height": block.index,
                "parent_hash": block.previous_hash,
                "timestamp": block.header.timestamp,  # ✅ Fixed timestamp access
                "difficulty": block.header.difficulty,  # ✅ Store difficulty for analytics
            }
            self.poc.lmdb_manager.put(f"block_metadata:{block.hash}", json.dumps(metadata))
            logging.info(f"[INFO] ✅ Block metadata stored for {block.hash}")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to store block metadata: {str(e)}")

    def export_utxos(self):
        """Export all unspent UTXOs into LMDB for faster retrieval."""
        try:
            all_utxos = self.utxo_manager.get_all_utxos()
            if not all_utxos:
                logging.warning("[WARNING] No UTXOs available for export.")
                return

            batch_data = {}
            for utxo_key, utxo_value in all_utxos.items():
                batch_data[f"utxo:{utxo_key}"] = json.dumps(utxo_value)

            # ✅ Use LMDB bulk insert for performance improvement
            self.poc.lmdb_manager.bulk_put(batch_data)
            logging.info(f"[INFO] ✅ Exported {len(all_utxos)} UTXOs to LMDB.")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to export UTXOs: {str(e)}")

    def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        """Retrieve a transaction from LMDB with improved error handling."""
        try:
            tx_data = self.poc.lmdb_manager.get(f"transaction:{tx_id}")
            if not tx_data:
                logging.warning(f"[WARNING] Transaction {tx_id} not found in LMDB.")
                return None
            return Transaction.from_dict(json.loads(tx_data))
        except json.JSONDecodeError:
            logging.error(f"[ERROR] ❌ Corrupt transaction data found for {tx_id}.")
            return None
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to retrieve transaction {tx_id}: {str(e)}")
            return None
