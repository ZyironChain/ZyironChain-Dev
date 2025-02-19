import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from decimal import Decimal

import pickle
import json
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.transactions. utxo_manager import UTXOManager
from Zyiron_Chain.transactions.tx import Transaction
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
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from decimal import Decimal

import pickle
import json
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.transactions.tx import Transaction
import logging
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.blockchain.blockheader import BlockHeader
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

log = logging.getLogger(__name__)
log.info(f"{__name__} logger initialized.")

from typing import List, Optional, Dict
from Zyiron_Chain.blockchain.constants import Constants

class StorageManager:
    def __init__(self, poc_instance, block_manager=None):
        self.poc = poc_instance
        self.utxo_manager = UTXOManager(poc_instance)
        self.block_manager = block_manager

        # Rely on the PoC to provide the UnQLite database instance.
        self.unqlite_db = getattr(poc_instance, "unqlite_db", None)
        if not self.unqlite_db:
            raise AttributeError("[ERROR] PoC instance missing 'unqlite_db'")

    def get_latest_block(self):
        """
        Retrieve the most recent block from storage.
        Returns a Block object representing the latest block, or None if no valid block is found.
        """
        try:
            all_blocks = self.get_all_blocks()
            if not all_blocks:
                logging.warning("[STORAGE] ⚠️ No blocks found in storage. Chain may be empty.")
                return None

            # Sort blocks by header index and select the one with the highest index
            latest_block_data = max(all_blocks, key=lambda b: b["header"].get("index", 0))
            block_hash = latest_block_data.get("hash", Constants.ZERO_HASH)
            block_difficulty = latest_block_data.get("difficulty", Constants.MIN_DIFFICULTY)

            if block_hash == Constants.ZERO_HASH:
                logging.error(f"[ERROR] Retrieved block is missing a valid 'hash': {latest_block_data}")
                return None

            # Ensure required header fields exist and are valid.
            header = latest_block_data.get("header", {})
            if "index" not in header or "previous_hash" not in header or "timestamp" not in header or "nonce" not in header:
                logging.error(f"[ERROR] Incomplete block header in block data: {latest_block_data}")
                return None

            # Convert timestamp to integer (if not already)
            try:
                timestamp = int(header["timestamp"])
            except Exception as e:
                logging.error(f"[ERROR] Invalid timestamp format in block header: {e}")
                return None

            # Lazy import for Block and Transaction to avoid circular dependencies.
            from Zyiron_Chain.blockchain.block import Block
            from Zyiron_Chain.transactions.tx import Transaction

            latest_block = Block(
                index=header["index"],
                previous_hash=header["previous_hash"],
                transactions=[Transaction.from_dict(tx) for tx in latest_block_data.get("transactions", [])],
                timestamp=timestamp,
                nonce=header["nonce"],
                difficulty=block_difficulty,
                miner_address=latest_block_data.get("miner_address", "Unknown")
            )
            logging.info(f"[STORAGE] ✅ Successfully retrieved Block {latest_block.index} (Hash: {latest_block.hash}).")
            return latest_block

        except Exception as e:
            logging.error(f"[STORAGE ERROR] Failed to retrieve latest block: {str(e)}")
            return None


    def purge_chain(self):
        """
        Delete all blockchain data by delegating the deletion to the PoC.
        """
        try:
            self.poc.unqlite_db.delete_all_blocks()
            logging.warning("[STORAGE] ⚠️ All blockchain data purged successfully.")
        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to purge blockchain data: {str(e)}")
            raise

    def get_total_mined_supply(self) -> Decimal:
        """
        Calculate the total coin supply mined by summing the coinbase rewards from all stored blocks.
        Assumes the coinbase transaction is the first transaction in each block and that its dictionary
        representation includes an 'outputs' list whose first element has an 'amount'.
        Returns a Decimal representing the total mined coin supply.
        """
        total = Decimal("0")
        try:
            blocks = self.get_all_blocks()
            for block in blocks:
                transactions = block.get("transactions", [])
                if not transactions:
                    continue  # Skip blocks with no transactions
                coinbase_tx = transactions[0]
                # Convert coinbase_tx to a dict if needed
                if not isinstance(coinbase_tx, dict) and hasattr(coinbase_tx, "to_dict"):
                    coinbase_tx = coinbase_tx.to_dict()
                outputs = coinbase_tx.get("outputs", [])
                if outputs and isinstance(outputs, list) and "amount" in outputs[0]:
                    amount = outputs[0].get("amount")
                    if amount is not None:
                        try:
                            total += Decimal(str(amount))
                        except Exception as conv_e:
                            logging.error(f"[STORAGE ERROR] Failed to convert coinbase amount '{amount}' to Decimal: {conv_e}")
            return total
        except Exception as e:
            logging.error(f"[STORAGE ERROR] Failed to calculate total mined supply: {e}")
            return Decimal("0")

    def get_all_blocks(self):
        """
        Retrieve and convert stored blocks from UnQLite via the PoC, ensuring all critical fields are included.
        """
        try:
            raw_blocks = self.poc.unqlite_db.get_all_blocks()
            processed_blocks = []
            for b in raw_blocks:
                # If stored as bytes, decode using pickle
                if isinstance(b, bytes):
                    try:
                        b = pickle.loads(b)
                    except (pickle.UnpicklingError, TypeError) as e:
                        logging.error(f"[ERROR] Failed to decode block: {str(e)}")
                        continue
                # Ensure essential fields exist
                block_hash = b.get("hash", Constants.ZERO_HASH)
                header = b.get("header", {})
                transactions = b.get("transactions", [])
                size = b.get("size", 0)
                miner_address = b.get("miner_address", "Unknown")
                # Ensure timestamp is present
                block_timestamp = header.get("timestamp")
                if not block_timestamp:
                    logging.error(f"[ERROR] Block missing 'timestamp' field: {b}")
                    continue  # Skip invalid blocks
                # Safely convert difficulty
                difficulty_val = header.get("difficulty", Constants.MIN_DIFFICULTY)
                if isinstance(difficulty_val, int):
                    block_difficulty = difficulty_val
                else:
                    try:
                        block_difficulty = int(str(difficulty_val), 16)
                    except Exception as conv_e:
                        logging.error(f"[ERROR] Failed to convert difficulty value '{difficulty_val}': {conv_e}")
                        continue
                processed_blocks.append({
                    "hash": block_hash,
                    "header": {
                        "index": header.get("index", -1),
                        "previous_hash": header.get("previous_hash", Constants.ZERO_HASH),
                        "merkle_root": header.get("merkle_root", Constants.ZERO_HASH),
                        "timestamp": block_timestamp,
                        "nonce": header.get("nonce", 0),
                        "difficulty": block_difficulty,
                        "version": header.get("version", 1),
                    },
                    "transactions": transactions,
                    "size": size,
                    "difficulty": block_difficulty,
                    "miner_address": miner_address
                })
            logging.info(f"[STORAGE] ✅ Successfully retrieved {len(processed_blocks)} blocks from UnQLite.")
            return processed_blocks
        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Exception while retrieving blocks: {str(e)}")
            return []

    def store_block(self, block, difficulty):
        """
        Store a block by delegating the operation to the PoC instance.
        The PoC is the only component allowed to write to UnQLite.
        """
        try:
            self.poc.store_block(block, difficulty)
        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to store block: {str(e)}")
            raise

    def add_block(self, block_hash: str, block_header: dict, transactions: list, size: int, difficulty: int):
        """
        Store all block components with explicit parameters by delegating the operation to the PoC instance.
        """
        try:
            self.poc.unqlite_db.add_block(block_hash, block_header, transactions, size, difficulty)
        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to add block: {str(e)}")
            raise

    def delete_all_blocks(self):
        """
        Delete all blocks by delegating the deletion to the PoC instance.
        """
        try:
            self.poc.unqlite_db.delete_all_blocks()
            logging.info("[STORAGE] ✅ All blocks deleted from UnQLite storage.")
        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to delete all blocks: {e}")
            raise

    def delete_block(self, block_hash: str):
        """
        Delete a block by its hash by delegating the deletion to the PoC instance.
        """
        try:
            self.poc.unqlite_db.delete_block(block_hash)
        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to delete block {block_hash}: {e}")

    def store_transaction(self, tx_id: str, block_hash: str, inputs: List[Dict], outputs: List[Dict], timestamp: int):
        """
        Store a transaction by delegating the operation to the PoC instance.
        """
        try:
            self.poc.store_transaction(tx_id, block_hash, inputs, outputs, timestamp)
        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to store transaction {tx_id}: {e}")
            raise

    def get_transaction(self, tx_id: str) -> Dict:
        """
        Retrieve a transaction by delegating the operation to the PoC instance.
        """
        try:
            return self.poc.unqlite_db.get_transaction(tx_id)
        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to retrieve transaction {tx_id}: {e}")
            return None

    def get_all_transactions(self) -> List[Dict]:
        """
        Retrieve all transactions by delegating the operation to the PoC instance.
        """
        try:
            return self.poc.unqlite_db.get_all_transactions()
        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to retrieve transactions: {e}")
            return []

    def clear_database(self):
        """
        Completely wipe the blockchain storage by delegating to the PoC instance.
        """
        try:
            self.poc.unqlite_db.clear_database()
        except Exception as e:
            logging.error(f"[STORAGE ERROR] Failed to clear database: {e}")

    def close(self):
        """
        Close the database connection by delegating to the PoC instance.
        """
        try:
            self.poc.unqlite_db.close()
        except Exception as e:
            logging.error(f"[STORAGE ERROR] Failed to close database connection: {e}")

    def verify_block_storage(self, block: Block) -> bool:
        """
        Validate if a block exists in storage using its hash.
        """
        try:
            if not isinstance(block.hash, str) or len(block.hash) != Constants.SHA3_384_HASH_SIZE:
                logging.error(f"[ERROR] ❌ Invalid block hash format for verification: {block.hash}")
                return False
            stored_data = self.poc.unqlite_db.get_block(block.hash)
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
        if not isinstance(block, Block):
            logging.error(f"[ERROR] ❌ Invalid block type: {type(block)}")
            return False
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
            if not isinstance(chain, list) or not all(isinstance(b, Block) for b in chain):
                logging.error("[ERROR] ❌ Invalid blockchain data format. Cannot save state.")
                return
            if pending_transactions and not all(isinstance(tx, Transaction) for tx in pending_transactions):
                logging.error("[ERROR] ❌ Invalid pending transaction data format.")
                return
            data = {
                "chain": [self._block_to_storage_format(block) for block in chain],
                "pending_transactions": [tx.to_dict() for tx in (pending_transactions or [])]
            }
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
        """
        Convert a block to a storage-safe format with error handling.
        """
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
        """
        Load the blockchain data via PoC with additional logging.
        """
        try:
            chain_data = self.poc.load_blockchain_data()
            logging.info(f"[INFO] ✅ Loaded {len(chain_data)} blocks from storage.")
            return chain_data
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to load blockchain: {str(e)}")
            return []

    def _store_block_metadata(self, block):
        """
        Store block metadata in LMDB for analytics and indexing.
        """
        try:
            metadata = {
                "height": block.index,
                "parent_hash": block.previous_hash,
                "timestamp": block.header.timestamp,
                "difficulty": block.header.difficulty,
            }
            self.poc.lmdb_manager.put(f"block_metadata:{block.hash}", json.dumps(metadata))
            logging.info(f"[INFO] ✅ Block metadata stored for {block.hash}")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to store block metadata: {str(e)}")

    def export_utxos(self):
        """
        Export all unspent UTXOs into LMDB for faster retrieval.
        """
        try:
            all_utxos = self.utxo_manager.get_all_utxos()
            if not all_utxos:
                logging.warning("[WARNING] No UTXOs available for export.")
                return
            batch_data = {}
            for utxo_key, utxo_value in all_utxos.items():
                batch_data[f"utxo:{utxo_key}"] = json.dumps(utxo_value)
            self.poc.lmdb_manager.bulk_put(batch_data)
            logging.info(f"[INFO] ✅ Exported {len(all_utxos)} UTXOs to LMDB.")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to export UTXOs: {str(e)}")

    def get_transaction_confirmations(self, tx_id: str) -> Optional[int]:
        """
        Retrieve the number of confirmations for the given transaction ID.
        Confirmations are calculated as:
            confirmations = (current chain length) - (block index where tx is found)
        If the transaction is not found, return None.
        """
        try:
            blocks = self.get_all_blocks()  # Returns list of block dictionaries
            if not blocks:
                logging.warning("[STORAGE] ⚠️ No blocks available to calculate confirmations.")
                return None
            blocks = sorted(blocks, key=lambda b: b["header"]["index"])
            current_chain_length = len(blocks)
            for b in blocks:
                for tx in b.get("transactions", []):
                    if tx.get("tx_id") == tx_id:
                        block_index = b["header"].get("index", 0)
                        confirmations = current_chain_length - block_index
                        return confirmations
            return None
        except Exception as e:
            logging.error(f"[STORAGE ERROR] Failed to get confirmations for transaction {tx_id}: {e}")
            return None

    def _block_to_storage_format(self, block) -> Dict:
        """
        Convert a block to a storage-safe format with error handling.
        """
        try:
            return {
                "header": block.header.to_dict() if hasattr(block.header, "to_dict") else block.header,
                "transactions": [tx.to_dict() if hasattr(tx, "to_dict") else tx for tx in block.transactions],
                "hash": block.hash,
                "size": len(block.transactions),
                "difficulty": block.header.difficulty
            }
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to format block for storage: {str(e)}")
            return {}

    def load_chain(self):
        """
        Load the blockchain data via PoC with additional logging.
        """
        try:
            chain_data = self.poc.load_blockchain_data()
            logging.info(f"[INFO] ✅ Loaded {len(chain_data)} blocks from storage.")
            return chain_data
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to load blockchain: {str(e)}")
            return []

    def _store_block_metadata(self, block):
        """
        Store block metadata in LMDB for analytics and indexing.
        """
        try:
            metadata = {
                "height": block.index,
                "parent_hash": block.previous_hash,
                "timestamp": block.header.timestamp,
                "difficulty": block.header.difficulty,
            }
            self.poc.lmdb_manager.put(f"block_metadata:{block.hash}", json.dumps(metadata))
            logging.info(f"[INFO] ✅ Block metadata stored for {block.hash}")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to store block metadata: {str(e)}")

    def export_utxos(self):
        """
        Export all unspent UTXOs into LMDB for faster retrieval.
        """
        try:
            all_utxos = self.utxo_manager.get_all_utxos()
            if not all_utxos:
                logging.warning("[WARNING] No UTXOs available for export.")
                return
            batch_data = {}
            for utxo_key, utxo_value in all_utxos.items():
                batch_data[f"utxo:{utxo_key}"] = json.dumps(utxo_value)
            self.poc.lmdb_manager.bulk_put(batch_data)
            logging.info(f"[INFO] ✅ Exported {len(all_utxos)} UTXOs to LMDB.")
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to export UTXOs: {str(e)}")

    def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        """
        Retrieve a transaction from LMDB with improved error handling.
        """
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
