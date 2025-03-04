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
import threading
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
import os
import struct
import json
import pickle
import logging
from decimal import Decimal
from typing import Optional, List, Dict
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.database.lmdatabase import LMDBManager
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.transactions.tx import Transaction

logging.basicConfig(level=logging.INFO)
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
import hashlib
from typing import List, Optional, Dict
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.blockchain.utils.hashing import Hashing

class StorageManager:
    def __init__(self, poc_instance):
        self.poc = poc_instance

        # Ensure the blockchain_storage and block_data folders exist
        blockchain_storage_dir = os.path.join(os.getcwd(), "blockchain_storage")
        block_data_dir = os.path.join(blockchain_storage_dir, "block_data")
        os.makedirs(block_data_dir, exist_ok=True)

        # Initialize LMDB databases
        self.block_metadata_db = LMDBManager(Constants.DATABASES["block_metadata"])
        self.txindex_db = LMDBManager(Constants.DATABASES["txindex"])
        self.utxo_db = LMDBManager(Constants.DATABASES["utxo"])
        self.utxo_history_db = LMDBManager(Constants.DATABASES["utxo_history"])
        self.mempool_db = LMDBManager(Constants.DATABASES["mempool"])

        # Thread safety
        self._db_lock = threading.Lock()

        # Block storage initialization
        self.current_block_file = os.path.join(block_data_dir, "block.data")
        self.current_block_offset = 0
        self._initialize_block_data_file()





    def _initialize_block_data_file(self):
        """
        Initialize block.data file with the correct magic number.
        - Creates the block data directory if it doesn't exist.
        - Writes the magic number if file is new/empty.
        - Validates the magic number on startup.
        """
        try:
            # ✅ Ensure block data directory exists
            block_data_dir = Constants.DATABASES.get("block_data")
            if not block_data_dir:
                raise ValueError("[ERROR] Block data directory not found in Constants.DATABASES.")

            os.makedirs(block_data_dir, exist_ok=True)

            # ✅ Set the block data file path
            self.current_block_file = os.path.join(block_data_dir, "block.data")
            logging.info(f"[STORAGE] Block data file path set to: {self.current_block_file}")

            file_is_new_or_empty = (not os.path.exists(self.current_block_file) or os.path.getsize(self.current_block_file) == 0)

            if file_is_new_or_empty:
                # Write the magic number to a new or empty file
                with open(self.current_block_file, "wb") as f:
                    f.write(struct.pack(">I", Constants.MAGIC_NUMBER))
                logging.info(f"[STORAGE] ✅ Created block.data with magic number {hex(Constants.MAGIC_NUMBER)}.")
            else:
                logging.info("[STORAGE] block.data file exists. Skipping rewrite of magic number...")

            # ✅ Validate the magic number
            with open(self.current_block_file, "rb") as f:
                file_magic_number = struct.unpack(">I", f.read(4))[0]
                if file_magic_number != Constants.MAGIC_NUMBER:
                    logging.error(
                        f"[STORAGE ERROR] ❌ Invalid magic number in block.data file: {hex(file_magic_number)}. "
                        f"Expected: {hex(Constants.MAGIC_NUMBER)}"
                    )
                    return None

            logging.info(f"[STORAGE] ✅ Block storage initialized successfully.")

        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to initialize block storage: {e}")
            raise










    def create_block_data_file(self, block: Block):
        """
        Append a block to the block.data file in binary format with all details.
        Ensures that the file is available and starts with the network-specific magic number
        if the file is empty.
        """
        try:
            # Check that the block file path has been set
            if not self.current_block_file:
                raise ValueError("Current block file is not set.")

            with open(self.current_block_file, "ab+") as f:
                # If file is empty, write the magic number at the start
                f.seek(0, os.SEEK_END)
                if f.tell() == 0:
                    f.write(struct.pack(">I", Constants.MAGIC_NUMBER))
                    logging.info(f"[STORAGE] Wrote network magic number {hex(Constants.MAGIC_NUMBER)} to block.data.")

                # Serialize the block (using your _serialize_block_to_binary method)
                block_data = self._serialize_block_to_binary(block)

                # Write the length of the block data (4 bytes) followed by the block data
                f.write(struct.pack(">I", len(block_data)))
                f.write(block_data)

                # Update the current block offset
                self.current_block_offset = f.tell()
                logging.info(f"[STORAGE] Appended Block {block.index} to block.data file at offset {self.current_block_offset}.")

        except Exception as e:
            logging.error(f"[STORAGE ERROR] Failed to write block to block.data file: {e}")
            raise



    def create_block_data_file(self, block: Block):
        """
        Append a block to the block.data file in binary format with all details.
        Ensures that the file is available and starts with the network-specific magic number.
        """
        try:
            # Check that the block file path has been set
            if not self.current_block_file:
                raise ValueError("Current block file is not set.")

            with open(self.current_block_file, "ab+") as f:
                # If file is empty, write the magic number at the start.
                f.seek(0, os.SEEK_END)
                if f.tell() == 0:
                    f.write(struct.pack(">I", Constants.MAGIC_NUMBER))
                    logging.info(f"[STORAGE] Wrote network magic number {hex(Constants.MAGIC_NUMBER)} to block.data.")

                # Serialize the block (using your _serialize_block_to_binary method)
                block_data = self._serialize_block_to_binary(block)
                # Write the length of the block data (4 bytes) followed by the block data.
                f.write(struct.pack(">I", len(block_data)))
                f.write(block_data)

                # Update the current block offset.
                self.current_block_offset = f.tell()
                logging.info(f"[STORAGE] Appended Block {block.index} to block.data file at offset {self.current_block_offset}.")

        except Exception as e:
            logging.error(f"[STORAGE ERROR] Failed to write block to block.data file: {e}")
            raise




    def get_block_from_data_file(self, offset: int) -> Optional[Block]:
        """
        Retrieve a block from the block.data file using its offset.
        Ensures the file contains the correct network magic number and validates block integrity.
        """
        try:
            # ✅ Ensure the block.data file exists
            if not os.path.exists(self.current_block_file):
                logging.error(f"[STORAGE ERROR] Block data file not found: {self.current_block_file}")
                return None

            file_size = os.path.getsize(self.current_block_file)

            # ✅ Ensure offset is within valid bounds
            if offset < 4 or offset >= file_size:
                logging.error(f"[STORAGE ERROR] ❌ Invalid offset {offset} for block.data file of size {file_size}.")
                return None

            with open(self.current_block_file, "rb") as f:
                f.seek(offset, os.SEEK_SET)

                block_size_bytes = f.read(4)
                if len(block_size_bytes) != 4:
                    logging.error(f"[STORAGE ERROR] ❌ Failed to read block size at offset {offset}.")
                    return None

                block_size = struct.unpack(">I", block_size_bytes)[0]

                # ✅ Validate the block size before reading data
                if block_size <= 0 or offset + block_size > file_size:
                    logging.error(f"[STORAGE ERROR] ❌ Block size {block_size} at offset {offset} is invalid.")
                    return None

                block_data = f.read(block_size)
                if len(block_data) != block_size:
                    logging.error(f"[STORAGE ERROR] ❌ Incomplete block data at offset {offset}.")
                    return None

                # ✅ Deserialize the block data
                block = self._deserialize_block_from_binary(block_data)
                if not block:
                    logging.error(f"[STORAGE ERROR] ❌ Failed to deserialize block at offset {offset}.")
                    return None

                logging.info(f"[STORAGE] ✅ Successfully retrieved Block {block.index} from offset {offset}")
                return block

        except struct.error as e:
            logging.error(f"[STORAGE ERROR] ❌ Struct unpacking failed at offset {offset}: {e}")
            return None


    def _serialize_block_to_binary(self, block: Block) -> bytes:
        """
        Serialize a block into binary format for storage.
        Ensures all fields are properly formatted and validated.

        Args:
            block (Block): The block to serialize.

        Returns:
            bytes: The serialized block data.

        Raises:
            ValueError: If any field is invalid or exceeds size limits.
        """
        try:
            block_dict = block.to_dict()

            # Validate and extract header fields
            header = block_dict["header"]
            block_height = int(header["index"])
            prev_block_hash = bytes.fromhex(header["previous_hash"])
            merkle_root = bytes.fromhex(header["merkle_root"])
            timestamp = int(header["timestamp"])
            nonce = int(header["nonce"])
            difficulty_int = int(header["difficulty"])

            # Convert difficulty to 48 bytes (big-endian)
            difficulty_bytes = difficulty_int.to_bytes(48, "big", signed=False)
            if len(difficulty_bytes) > 48:
                raise ValueError(f"Difficulty {difficulty_int} exceeds 48 bytes.")

            # Process miner address (max 128 bytes, padded if necessary)
            miner_address_str = header["miner_address"]
            miner_address_encoded = miner_address_str.encode("utf-8")
            if len(miner_address_encoded) > 128:
                raise ValueError("Miner address exceeds 128 bytes.")
            miner_address_padded = miner_address_encoded.ljust(128, b'\x00')

            # Pack header fields
            header_format = ">I32s32sQI48s128s"  # Block height, prev hash, merkle root, timestamp, nonce, difficulty, miner address
            header_data = struct.pack(
                header_format,
                block_height,
                prev_block_hash,
                merkle_root,
                timestamp,
                nonce,
                difficulty_bytes,
                miner_address_padded
            )

            # Serialize transactions
            tx_data = b""
            for tx in block_dict["transactions"]:
                tx_data += self._serialize_transaction_to_binary(tx)

            # Pack the number of transactions (unsigned int)
            tx_count = len(block_dict["transactions"])
            tx_count_data = struct.pack(">I", tx_count)

            # Combine header, transaction count, and transaction data
            return header_data + tx_count_data + tx_data

        except struct.error as e:
            logging.error(f"[SERIALIZE ERROR] ❌ Struct packing failed: {e}")
            raise
        except ValueError as e:
            logging.error(f"[SERIALIZE ERROR] ❌ Invalid block data: {e}")
            raise
        except Exception as e:
            logging.error(f"[SERIALIZE ERROR] ❌ Unexpected error during block serialization: {e}")
            raise



    def _deserialize_block_from_binary(self, block_data: bytes) -> Optional[Block]:
        """
        Deserialize binary block data into a Block object.
        Ensures all fields are properly validated and formatted.

        Args:
            block_data (bytes): The binary block data to deserialize.

        Returns:
            Optional[Block]: The deserialized Block object, or None if deserialization fails.
        """
        try:
            # Validate magic number (first 4 bytes)
            magic_number = struct.unpack(">I", block_data[:4])[0]
            if magic_number != Constants.MAGIC_NUMBER:
                logging.error(f"[DESERIALIZE ERROR] ❌ Invalid magic number: {hex(magic_number)}")
                return None

            # Unpack header fields
            header_format = ">I32s32sQI48s128s"  # Block height, prev hash, merkle root, timestamp, nonce, difficulty, miner address
            header_size = struct.calcsize(header_format)

            (
                block_height,
                prev_block_hash,
                merkle_root,
                timestamp,
                nonce,
                difficulty_bytes,
                miner_address_bytes
            ) = struct.unpack(header_format, block_data[4:header_size + 4])

            # Convert difficulty to integer
            difficulty_int = int.from_bytes(difficulty_bytes, "big", signed=False)

            # Decode miner address (strip padding)
            miner_address_str = miner_address_bytes.rstrip(b'\x00').decode("utf-8")

            # Unpack the number of transactions (next 4 bytes)
            tx_count_offset = header_size + 4
            tx_count = struct.unpack(">I", block_data[header_size + 4:tx_count_offset + 4])[0]

            # Deserialize transactions
            tx_data = block_data[tx_count_offset + 4:]
            transactions = []
            for _ in range(tx_count):
                tx, tx_size = self._deserialize_transaction_from_binary(tx_data)
                transactions.append(tx)
                tx_data = tx_data[tx_size:]

            # Construct block dictionary
            block_dict = {
                "header": {
                    "index": block_height,
                    "previous_hash": prev_block_hash.hex(),
                    "merkle_root": merkle_root.hex(),
                    "timestamp": timestamp,
                    "nonce": nonce,
                    "difficulty": difficulty_int,
                    "miner_address": miner_address_str,
                },
                "transactions": transactions
            }

            # Convert to Block object
            return Block.from_dict(block_dict)

        except struct.error as e:
            logging.error(f"[DESERIALIZE ERROR] ❌ Struct unpacking failed: {e}")
            return None
        except UnicodeDecodeError as e:
            logging.error(f"[DESERIALIZE ERROR] ❌ Failed to decode miner address: {e}")
            return None
        except Exception as e:
            logging.error(f"[DESERIALIZE ERROR] ❌ Unexpected error during block deserialization: {e}")
            return None

                



    def _serialize_transaction_to_binary(self, tx: Dict) -> bytes:
        """
        Serialize a transaction to binary format with all details.
        Uses Constants.COIN to standardize amounts.
        """
        try:
            # Serialize transaction header
            tx_id = bytes.fromhex(tx["tx_id"])
            tx_type = tx["tx_type"].encode("utf-8")
            timestamp = int(tx["timestamp"])  # Ensure timestamp is an integer
            fee = int(Decimal(tx["fee"]) / Constants.COIN)  # Convert fee to smallest unit (integer)

            # Pack transaction header: 32-byte tx_id, 8-byte tx_type, 8-byte timestamp (Q), and 4-byte fee (I)
            tx_header = struct.pack(
                ">32s8sQI",
                tx_id,
                tx_type,
                timestamp,
                fee
            )

            # Serialize inputs
            inputs_data = b""
            for inp in tx["inputs"]:
                inputs_data += self._serialize_input_to_binary(inp)

            # Serialize outputs
            outputs_data = b""
            for out in tx["outputs"]:
                outputs_data += self._serialize_output_to_binary(out)

            # Combine transaction header with the number of inputs and outputs and the serialized data
            return tx_header + struct.pack(">II", len(tx["inputs"]), len(tx["outputs"])) + inputs_data + outputs_data

        except Exception as e:
            logging.error(f"[STORAGE ERROR] Failed to serialize transaction to binary: {e}")
            raise




    def _serialize_input_to_binary(self, inp: Dict) -> bytes:
        """
        Serialize a transaction input to binary format.
        """
        try:
            tx_out_id = bytes.fromhex(inp["tx_out_id"])
            script_sig = inp["script_sig"].encode("utf-8")
            sequence = inp["sequence"]

            return struct.pack(
                ">32s32sI",
                tx_out_id,
                script_sig,
                sequence
            )
        except Exception as e:
            logging.error(f"[STORAGE ERROR] Failed to serialize input to binary: {e}")
            raise

    def _serialize_output_to_binary(self, out: Dict) -> bytes:
        """
        Serialize a transaction output to binary format.
        Uses Constants.COIN for amount conversion.
        """
        try:
            amount = int(Decimal(out["amount"]) / Constants.COIN)  # Convert to smallest unit
            script_pub_key = out["script_pub_key"].encode("utf-8")

            return struct.pack(
                ">Q32s",
                amount,
                script_pub_key
            )
        except Exception as e:
            logging.error(f"[STORAGE ERROR] Failed to serialize output to binary: {e}")
            raise



    def get_latest_block(self) -> Optional[Block]:
        """
        Retrieve the most recent block from LMDB storage.
        Returns a Block object representing the latest block, or None if no valid block is found.
        Ensures:
        - LMDB data integrity.
        - Proper hash format validation.
        - Magic number consistency in block.data.
        """
        try:
            logging.info("[STORAGE] 🔄 Retrieving latest block from LMDB...")

            # ✅ Step 1: Retrieve all stored block metadata
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                all_blocks = []
                for key, value in cursor:
                    if key.decode().startswith("block:"):
                        try:
                            block_metadata = json.loads(value.decode("utf-8"))
                            if not isinstance(block_metadata, dict):
                                logging.error(f"[STORAGE ERROR] ❌ Invalid block format (not a dict): {block_metadata}")
                                continue

                            header = block_metadata.get("block_header")
                            if not isinstance(header, dict) or "index" not in header:
                                logging.error("[STORAGE ERROR] ❌ Block header missing 'index'")
                                continue

                            all_blocks.append(block_metadata)

                        except json.JSONDecodeError as e:
                            logging.error(f"[STORAGE ERROR] ❌ Corrupt block metadata in LMDB: {e}")
                            continue

            if not all_blocks:
                logging.warning("[STORAGE] ⚠️ No blocks found in LMDB. Blockchain may be empty.")
                return None

            # ✅ Step 2: Identify the latest block by index
            latest_block_data = max(all_blocks, key=lambda b: b["block_header"]["index"], default=None)
            if not latest_block_data:
                logging.error("[ERROR] ❌ Could not determine latest block.")
                return None

            # ✅ Step 3: Validate block hash format
            block_hash = latest_block_data.get("hash", Constants.ZERO_HASH)
            if not isinstance(block_hash, str) or not all(c in "0123456789abcdefABCDEF" for c in block_hash):
                logging.error(f"[ERROR] ❌ Invalid block hash format: {block_hash}")
                return None

            # ✅ Step 4: Ensure block header contains all required fields
            required_keys = {"index", "previous_hash", "timestamp", "nonce", "difficulty"}
            header = latest_block_data["block_header"]
            if not required_keys.issubset(header):
                logging.error(f"[ERROR] ❌ Incomplete block metadata: {latest_block_data}")
                return None

            # ✅ Step 5: Validate timestamp
            try:
                timestamp = int(header["timestamp"])
                if timestamp <= 0:
                    raise ValueError("Invalid timestamp")
            except (ValueError, TypeError) as e:
                logging.error(f"[ERROR] ❌ Invalid timestamp format: {e}")
                return None

            # ✅ Step 6: Verify block.data magic number (Ensures valid block storage)
            if not os.path.exists(self.current_block_file):
                logging.error(f"[STORAGE ERROR] ❌ block.data file not found: {self.current_block_file}")
                return None

            try:
                with open(self.current_block_file, "rb") as f:
                    if os.path.getsize(self.current_block_file) < 4:
                        logging.error(f"[STORAGE ERROR] ❌ block.data file is too small to contain magic number.")
                        return None

                    file_magic_number = struct.unpack(">I", f.read(4))[0]
                    if file_magic_number != Constants.MAGIC_NUMBER:
                        logging.error(
                            f"[STORAGE ERROR] ❌ Invalid magic number in block.data file: {hex(file_magic_number)}. "
                            f"Expected: {hex(Constants.MAGIC_NUMBER)}"
                        )
                        return None

            except (struct.error, OSError) as e:
                logging.error(f"[STORAGE ERROR] ❌ Failed to read magic number: {e}")
                return None

            # ✅ Step 7: Fetch block from `block.data` using its stored offset
            block_offset = latest_block_data.get("data_offset")
            if not isinstance(block_offset, int):
                logging.error("[ERROR] ❌ Block data offset missing or invalid in LMDB. Cannot retrieve block.")
                return None

            full_block = self.get_block_from_data_file(block_offset)
            if not full_block:
                logging.error(f"[ERROR] ❌ Failed to load full block {block_hash} from block.data file.")
                return None

            logging.info(f"[STORAGE] ✅ Successfully retrieved Block {full_block.index} (Hash: {full_block.hash}).")
            return full_block

        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to retrieve latest block: {str(e)}")
            return None





    def get_total_mined_supply(self) -> Decimal:
        """
        Calculate the total mined coin supply by summing all Coinbase rewards from stored blocks.
        Optimized by caching the total supply in LMDB for fast retrieval.
        """
        try:
            # ✅ Step 1: Check if the total supply is already cached in LMDB
            with self.block_metadata_db.env.begin() as txn:
                cached_supply = txn.get(b"total_mined_supply")

            if cached_supply:
                # ✅ If cached value exists, return it directly
                try:
                    total_supply = Decimal(cached_supply.decode("utf-8"))
                    logging.info(f"[STORAGE] ✅ Cached total mined supply retrieved: {total_supply} ZYC")
                    return total_supply
                except (UnicodeDecodeError, ValueError) as decode_error:
                    logging.warning(f"[STORAGE WARNING] Failed to decode cached total supply: {decode_error}")

            # -------------------------------------------------------------------------------------
            # ✅ Step 2: If no cached supply, iterate through blocks to calculate it
            # -------------------------------------------------------------------------------------
            total_supply = Decimal("0")
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.decode().startswith("block:"):
                        try:
                            block_metadata = json.loads(value.decode("utf-8"))
                            transactions = block_metadata.get("tx_ids", [])

                            # ✅ Ensure at least one transaction exists
                            if transactions:
                                for tx_id in transactions:
                                    # ✅ Ensure tx_id is a string before encoding
                                    tx_key = f"tx:{tx_id}".encode("utf-8") if isinstance(tx_id, str) else b"tx:" + tx_id

                                    # ✅ Retrieve transaction details from txindex LMDB
                                    tx_data = self.txindex_db.get(tx_key)

                                    if not tx_data:
                                        logging.warning(f"[STORAGE WARNING] Missing transaction {tx_id} in txindex.")
                                        continue  # Skip if transaction doesn't exist

                                    try:
                                        tx_details = json.loads(tx_data.decode("utf-8") if isinstance(tx_data, bytes) else tx_data)

                                        # ✅ Ensure transaction is a Coinbase transaction
                                        if tx_details.get("type") == "COINBASE":
                                            coinbase_outputs = tx_details.get("outputs", [])

                                            # ✅ Validate outputs before accessing amount
                                            if coinbase_outputs and isinstance(coinbase_outputs, list):
                                                for output in coinbase_outputs:
                                                    if "amount" in output:
                                                        total_supply += Decimal(str(output["amount"]))

                                    except json.JSONDecodeError as json_error:
                                        logging.error(f"[STORAGE ERROR] ❌ Failed to parse transaction data: {json_error}")
                                        continue  # ✅ Skip corrupted transactions instead of stopping

                        except json.JSONDecodeError as e:
                            logging.error(f"[STORAGE ERROR] ❌ Failed to parse block metadata: {e}")
                            continue  # ✅ Skip corrupted blocks instead of stopping

            # ✅ Step 3: Cache the calculated total supply in LMDB for faster future lookups
            with self.block_metadata_db.env.begin(write=True) as txn:
                txn.put(b"total_mined_supply", str(total_supply).encode("utf-8"))

            logging.info(f"[STORAGE] ✅ Total mined supply calculated & cached: {total_supply} ZYC")
            return total_supply

        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to calculate total mined supply: {str(e)}")
            return Decimal("0")





    def get_all_blocks(self) -> List[Dict]:
        """
        Retrieve complete block data with full transactions from storage.
        """
        processed_blocks = []
        try:
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if not key.decode().startswith("block:"):
                        continue

                    try:
                        block_meta = json.loads(value.decode("utf-8") if isinstance(value, bytes) else value)
                        header = block_meta.get("block_header", {})

                        # Get full transactions from txindex
                        full_transactions = []
                        for tx_id in block_meta.get("tx_ids", []):
                            tx_key = f"tx:{tx_id}".encode("utf-8") if isinstance(tx_id, str) else b"tx:" + tx_id
                            tx_data = self.txindex_db.get(tx_key)

                            if tx_data:
                                try:
                                    tx_details = json.loads(tx_data.decode("utf-8") if isinstance(tx_data, bytes) else tx_data)
                                    full_transactions.append(tx_details)
                                except json.JSONDecodeError as json_error:
                                    logging.error(f"Error decoding transaction {tx_id}: {json_error}")
                            else:
                                logging.warning(f"Missing transaction {tx_id} in txindex.")

                        processed_blocks.append({
                            "hash": block_meta.get("hash"),
                            "header": {
                                "index": header.get("index"),
                                "previous_hash": header.get("previous_hash"),
                                "merkle_root": header.get("merkle_root"),
                                "timestamp": header.get("timestamp"),
                                "nonce": header.get("nonce"),
                                "difficulty": int(header.get("difficulty", Constants.GENESIS_TARGET)),
                                "version": header.get("version", 1)
                            },
                            "transactions": full_transactions,
                            "size": block_meta.get("block_size", 0),
                            "miner_address": block_meta.get("miner_address", "Unknown"),
                            "data_offset": block_meta.get("data_offset")  # Critical for block.data loading
                        })

                    except json.JSONDecodeError as json_error:
                        logging.error(f"[STORAGE ERROR] ❌ Failed to parse block metadata {key}: {json_error}")
                    except Exception as e:
                        logging.error(f"[STORAGE ERROR] ❌ Error processing block {key}: {str(e)}")

            # Sort blocks by height and add chain order validation
            processed_blocks.sort(key=lambda b: b["header"]["index"])
            prev_hash = Constants.ZERO_HASH

            for block in processed_blocks:
                if block["header"]["previous_hash"] != prev_hash:
                    logging.error(f"❌ Chain discontinuity at block {block['header']['index']}")
                    return []
                prev_hash = block["hash"]

            logging.info(f"✅ Retrieved {len(processed_blocks)} valid blocks from storage.")
            return processed_blocks

        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Critical storage error: {str(e)}")
            self.purge_chain()
            return []




    def store_block(self, block, difficulty):
        """
        Store a block in LMDB-based storage.
        - Metadata is stored in `block_metadata.lmdb`
        - Transactions are indexed in `txindex.lmdb`
        - The full block is written to `block.data`
        """
        try:
            with self.block_metadata_db.env.begin(write=True) as txn:
                if not hasattr(block, "header") or not hasattr(block.header, "merkle_root"):
                    logging.warning(f"[STORAGE WARNING] ⚠️ Block {block.index} missing Merkle Root. Recomputing Merkle root.")
                    block.header.merkle_root = self._calculate_merkle_root(block.transactions)

                # ✅ Ensure transactions attribute is a proper list
                if not isinstance(block.transactions, list):
                    logging.error(f"[STORAGE ERROR] ❌ Block {block.index} has an invalid transactions format (must be list).")
                    return

                # ✅ Fix: Compute block hash before storing and ensure it's a hex string
                block.hash = hashlib.sha3_384(block.calculate_hash().encode()).hexdigest()  # 🔥 Fix applied here

                # ✅ Fix: Ensure Merkle root is stored as a string
                block.header.merkle_root = str(block.header.merkle_root)

                # -------------------------------------------------------------------------------------
                # ✅ Step 2: Prepare block metadata for LMDB
                # -------------------------------------------------------------------------------------
                timestamp = (
                    block.timestamp if isinstance(block.timestamp, int) else int(time.time())
                )

                # ✅ Ensure difficulty is stored as an integer
                try:
                    difficulty_val = int(difficulty)
                except ValueError:
                    logging.error(f"[STORAGE ERROR] ❌ Difficulty must be an integer; received: {difficulty}")
                    return

                # ✅ Fix: Validate and store only valid transaction IDs
                tx_ids = [
                    tx.tx_id for tx in block.transactions if hasattr(tx, "tx_id") and isinstance(tx.tx_id, str)
                ]
                if len(tx_ids) < len(block.transactions):
                    logging.warning(f"[STORAGE WARNING] ⚠️ Some transactions in Block {block.index} are missing valid tx_id.")

                block_metadata = {
                    "hash": str(block.hash),  # ✅ Ensure correct hash serialization
                    "block_header": {
                        "index": block.index,
                        "previous_hash": str(block.previous_hash),  # 🔥 Ensure it's stored as a string
                        "merkle_root": str(block.header.merkle_root),  # 🔥 Fix: Convert Merkle root to string
                        "timestamp": timestamp,
                        "nonce": getattr(block, "nonce", 0),
                        "difficulty": difficulty_val,
                    },
                    "transaction_count": len(block.transactions),
                    "block_size": len(json.dumps(block.to_dict(), ensure_ascii=False).encode("utf-8")),
                    "data_file": self.current_block_file,
                    "data_offset": self.current_block_offset,
                    "tx_ids": tx_ids,  # ✅ Now only storing valid tx_ids
                }

                # ✅ Store block metadata in LMDB
                txn.put(
                    f"block:{block.hash}".encode(),
                    json.dumps(block_metadata).encode("utf-8")
                )

            # ✅ Step 3: Append full block data to `block.data` file with error handling
            try:
                self.create_block_data_file(block)
            except Exception as e:
                logging.error(f"[STORAGE ERROR] ❌ Failed to write block {block.index} to block.data file: {e}")

                # ✅ Fix: Remove block metadata from LMDB if writing to `block.data` fails
                with self.block_metadata_db.env.begin(write=True) as txn:
                    txn.delete(f"block:{block.hash}".encode())

                return

            logging.info(f"[STORAGE] ✅ Block {block.index} stored successfully in LMDB.")

        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to store block {block.index}: {e}")
            raise



    def store_transaction(self, tx_id: str, block_hash: str, inputs: List[Dict], outputs: List[Dict], timestamp: int):
        """
        Store a transaction in LMDB.
        - Saves transaction metadata in `txindex.lmdb`
        - Ensures transactions are linked to their block
        - Supports atomic writes for integrity
        """
        try:
            # ✅ Validate inputs and outputs structure
            if not isinstance(inputs, list) or not all(isinstance(i, dict) for i in inputs):
                logging.error(f"[STORAGE ERROR] ❌ Invalid inputs structure for transaction {tx_id}. Expected a list of dictionaries.")
                return

            if not isinstance(outputs, list) or not all(isinstance(o, dict) for o in outputs):
                logging.error(f"[STORAGE ERROR] ❌ Invalid outputs structure for transaction {tx_id}. Expected a list of dictionaries.")
                return

            # ✅ Ensure timestamp is a valid integer
            if not isinstance(timestamp, int):
                logging.error(f"[STORAGE ERROR] ❌ Invalid timestamp format for transaction {tx_id}. Expected an integer.")
                return

            # ✅ Ensure tx_id and block_hash are strings
            if not isinstance(tx_id, str):
                logging.error(f"[STORAGE ERROR] ❌ Invalid transaction ID format: {tx_id}. Expected a string.")
                return
            
            if not isinstance(block_hash, str):
                logging.error(f"[STORAGE ERROR] ❌ Invalid block hash format for transaction {tx_id}. Expected a string.")
                return

            # ✅ Prepare transaction data for storage
            transaction_data = {
                "tx_id": tx_id,
                "block_hash": block_hash,
                "inputs": inputs,
                "outputs": outputs,
                "timestamp": timestamp
            }

            # ✅ Serialize transaction data to JSON safely
            try:
                serialized_data = json.dumps(transaction_data).encode("utf-8")
            except (TypeError, ValueError) as e:
                logging.error(f"[STORAGE ERROR] ❌ Failed to serialize transaction data for {tx_id}: {e}")
                return

            # ✅ Generate LMDB key safely
            tx_key = f"tx:{tx_id}".encode("utf-8")

            # ✅ Store the transaction data in the index
            with self.txindex_db.env.begin(write=True) as txn:
                txn.put(tx_key, serialized_data)

            logging.info(f"[STORAGE] ✅ Transaction {tx_id} stored successfully in LMDB.")

        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to store transaction {tx_id}: {e}")
            raise




    def get_transaction(self, tx_id: str) -> Optional[Dict]:
        """
        Retrieve a transaction from LMDB.
        - Queries `txindex.lmdb` for transaction data
        - Returns None if transaction does not exist
        """
        try:
            # ✅ Validate transaction ID format
            if not isinstance(tx_id, (str, bytes)):
                logging.error(f"[STORAGE ERROR] ❌ Invalid transaction ID format: {tx_id}. Expected str or bytes.")
                return None

            # ✅ Ensure tx_id is properly formatted and encoded
            tx_key = f"tx:{tx_id}".encode("utf-8") if isinstance(tx_id, str) else b"tx:" + tx_id

            # ✅ Query LMDB for transaction data
            with self.txindex_db.env.begin() as txn:
                tx_data = txn.get(tx_key)

            # ✅ Handle missing transactions
            if not tx_data:
                logging.warning(f"[STORAGE] ⚠️ Transaction {tx_id} not found in LMDB.")
                return None

            # ✅ Decode and parse transaction data safely
            try:
                return json.loads(tx_data.decode("utf-8") if isinstance(tx_data, bytes) else tx_data)
            except (json.JSONDecodeError, UnicodeDecodeError) as decode_error:
                logging.error(f"[STORAGE ERROR] ❌ Corrupt transaction data for {tx_id}: {decode_error}")
                return None

        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to retrieve transaction {tx_id}: {e}")
            return None


    def get_all_transactions(self) -> List[Dict]:
        """
        Retrieve all stored transactions from LMDB.
        - Queries `txindex.lmdb` for transaction data
        - Returns a list of transaction dictionaries
        """
        transactions = []
        try:
            with self.txindex_db.env.begin() as txn:
                cursor = txn.cursor()
                
                # Iterate through all key-value pairs in the database
                for key, value in cursor:
                    try:
                        # Decode key and check if it's a transaction
                        key_str = key.decode("utf-8")
                        if key_str.startswith("tx:"):
                            # Safely decode and parse transaction data
                            tx_data = value.decode("utf-8")
                            transaction = json.loads(tx_data)
                            
                            # Validate basic transaction structure
                            if not isinstance(transaction, dict):
                                log.warning(f"Invalid transaction format for key {key_str}")
                                continue
                                
                            # Add valid transaction to results
                            transactions.append(transaction)
                            
                    except (UnicodeDecodeError, json.JSONDecodeError) as e:
                        log.error(f"Failed to decode transaction {key_str}: {str(e)}")
                        continue
                    except Exception as e:
                        log.error(f"Unexpected error processing transaction {key_str}: {str(e)}")
                        continue

            log.info(f"Retrieved {len(transactions)} transactions from LMDB")
            return transactions

        except Exception as e:
            log.error(f"Failed to retrieve transactions: {str(e)}")
            return []

    def clear_database(self):
        """
        Completely wipe all LMDB blockchain storage.
        - Deletes transaction index, mempool, UTXO, and block metadata databases
        - Ensures proper cleanup of LMDB storage
        """
        try:
            with self.txindex_db.env.begin(write=True) as txn:
                txn.drop(self.txindex_db.db, delete=True)

            with self.block_metadata_db.env.begin(write=True) as txn:
                txn.drop(self.block_metadata_db.db, delete=True)

            with self.utxo_db.env.begin(write=True) as txn:
                txn.drop(self.utxo_db.db, delete=True)

            with self.mempool_db.env.begin(write=True) as txn:
                txn.drop(self.mempool_db.db, delete=True)

            logging.warning("[STORAGE] ⚠️ All LMDB blockchain data cleared successfully.")

        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to clear LMDB database: {e}")
            raise

    def close(self):
        """
        Close all LMDB database connections safely.
        """
        try:
            self.block_metadata_db.env.close()
            self.txindex_db.env.close()
            self.utxo_db.env.close()
            self.utxo_history_db.env.close()
            self.mempool_db.env.close()
            
            logging.info("[STORAGE] ✅ All LMDB database connections closed successfully.")
        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to close LMDB databases: {e}")

    def verify_block_storage(self, block: Block) -> bool:
        """
        Validate if a block exists in LMDB storage using its hash.
        - Queries `block_metadata.lmdb` instead of UnQLite
        """
        try:
            if not isinstance(block.hash, str) or len(block.hash) != Constants.SHA3_384_HASH_SIZE:
                logging.error(f"[ERROR] ❌ Invalid block hash format for verification: {block.hash}")
                return False

            with self.block_metadata_db.env.begin() as txn:
                block_metadata = txn.get(f"block:{block.hash}".encode())

            if block_metadata:
                logging.info(f"[STORAGE] ✅ Block {block.index} exists in LMDB.")
                return True
            else:
                logging.warning(f"[WARNING] Block {block.index} ({block.hash}) not found in LMDB.")
                return False

        except Exception as e:
            logging.error(f"[ERROR] ❌ Block verification failed for {block.index}: {str(e)}")
            return False


    def validate_block_structure(self, block: Block) -> bool:
        """
        Validate that a block contains all required fields before storing in LMDB.
        """
        required_fields = ["index", "hash", "header", "transactions", "merkle_root", "timestamp", "difficulty"]
        
        if not isinstance(block, Block):
            logging.error(f"[ERROR] ❌ Invalid block type: {type(block)}")
            return False

        missing_fields = [field for field in required_fields if not hasattr(block, field)]
        if missing_fields:
            logging.error(f"[ERROR] ❌ Block {block.index} is missing required fields: {missing_fields}")
            return False

        # ✅ Ensure the block hash is valid and matches the calculated value
        calculated_hash = block.calculate_hash()
        if block.hash != calculated_hash:
            logging.error(f"[ERROR] ❌ Block {block.index} has an invalid hash. Expected {calculated_hash}, got {block.hash}")
            return False

        # ✅ Ensure transactions are valid
        if not isinstance(block.transactions, list) or not all(isinstance(tx, dict) for tx in block.transactions):
            logging.error(f"[ERROR] ❌ Block {block.index} contains invalid transactions.")
            return False

        logging.info(f"[STORAGE] ✅ Block {block.index} passed structure validation.")
        return True


    def save_blockchain_state(self, chain: List[Block], pending_transactions: Optional[List[Transaction]] = None):
        """
        Save the blockchain state, including chain data and pending transactions in LMDB.
        Uses atomic transactions to prevent data corruption.
        """
        try:
            if not isinstance(chain, list) or not all(isinstance(b, Block) for b in chain):
                logging.error("[ERROR] ❌ Invalid blockchain data format. Cannot save state.")
                return
            if pending_transactions and not all(isinstance(tx, Transaction) for tx in pending_transactions):
                logging.error("[ERROR] ❌ Invalid pending transaction data format.")
                return

            with self.block_metadata_db.env.begin(write=True) as txn:
                # ✅ Save blocks in LMDB
                for block in chain:
                    block_data = pickle.dumps(self._block_to_storage_format(block))
                    txn.put(f"block:{block.hash}".encode(), block_data)

                # ✅ Save pending transactions in LMDB
                for tx in pending_transactions or []:
                    txn.put(f"pending_tx:{tx.tx_id}".encode(), pickle.dumps(tx.to_dict()))

            logging.info(f"[STORAGE] ✅ Blockchain state saved in LMDB with {len(chain)} blocks and {len(pending_transactions or [])} pending transactions.")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to save blockchain state in LMDB: {str(e)}")
            raise


    def _block_to_storage_format(self, block) -> Dict:
        """
        Convert a block to a storage-safe format optimized for LMDB storage.
        """
        try:
            return {
                "index": block.index,
                "previous_hash": block.previous_hash,
                "hash": block.hash,
                "merkle_root": block.header.merkle_root if hasattr(block.header, "merkle_root") else None,
                "timestamp": block.timestamp,
                "nonce": block.nonce,
                "difficulty": block.header.difficulty if hasattr(block.header, "difficulty") else Constants.MIN_DIFFICULTY,
                "miner_address": block.miner_address if hasattr(block, "miner_address") else "Unknown",
                "transactions": [tx.to_dict() if hasattr(tx, "to_dict") else tx for tx in block.transactions],
                "size": len(pickle.dumps(block))  # ✅ Ensure binary size is correctly stored
            }
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to format block for LMDB storage: {str(e)}")
            return {}


    def load_chain(self):
        """
        Load the blockchain data from LMDB storage, ensuring optimal retrieval.
        """
        try:
            chain_data = []
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.decode().startswith("block:"):
                        try:
                            block_data = pickle.loads(value)
                            chain_data.append(block_data)
                        except pickle.UnpicklingError as e:
                            logging.error(f"[ERROR] ❌ Failed to decode block from LMDB: {e}")
                            continue

            logging.info(f"[INFO] ✅ Loaded {len(chain_data)} blocks from LMDB storage.")
            return chain_data

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to load blockchain from LMDB: {str(e)}")
            return []


    def export_utxos(self):
        """
        Export all unspent UTXOs into LMDB for faster retrieval and indexing.
        """
        try:
            all_utxos = self.utxo_manager.get_all_utxos()
            if not all_utxos:
                logging.warning("[WARNING] No UTXOs available for export.")
                return

            batch_data = {}
            with self.utxo_db.env.begin(write=True) as txn:
                for utxo_key, utxo_value in all_utxos.items():
                    try:
                        batch_data[f"utxo:{utxo_key}"] = pickle.dumps(utxo_value)
                    except pickle.PicklingError as e:
                        logging.error(f"[ERROR] ❌ Failed to serialize UTXO {utxo_key}: {e}")
                        continue

                self.utxo_db.bulk_put(batch_data, txn)

            logging.info(f"[INFO] ✅ Successfully exported {len(all_utxos)} UTXOs to LMDB.")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to export UTXOs to LMDB: {str(e)}")

    def get_transaction_confirmations(self, tx_id: str) -> Optional[int]:
        """
        Retrieve the number of confirmations for a given transaction ID from LMDB.
        Confirmations are calculated as:
            confirmations = (current chain length) - (block index where tx is found)
        If the transaction is not found, return None.
        """
        try:
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                blocks = []
                for key, value in cursor:
                    if key.decode().startswith("block:"):
                        try:
                            block_data = pickle.loads(value)
                            blocks.append(block_data)
                        except pickle.UnpicklingError as e:
                            logging.error(f"[ERROR] ❌ Failed to decode block metadata: {e}")
                            continue

            if not blocks:
                logging.warning("[STORAGE] ⚠️ No blocks available to calculate confirmations.")
                return None

            # ✅ Sort blocks by index
            blocks = sorted(blocks, key=lambda b: b["index"])
            current_chain_length = len(blocks)

            # ✅ Search for the transaction
            for block in blocks:
                if any(tx.get("tx_id") == tx_id for tx in block.get("transactions", [])):
                    confirmations = current_chain_length - block["index"]
                    return confirmations

            return None

        except Exception as e:
            logging.error(f"[STORAGE ERROR] ❌ Failed to get confirmations for transaction {tx_id}: {e}")
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
        Export all unspent UTXOs into LMDB for optimized retrieval and indexing.
        """
        try:
            all_utxos = self.utxo_manager.get_all_utxos()
            if not all_utxos:
                logging.warning("[WARNING] No UTXOs available for export.")
                return

            batch_data = {}
            with self.utxo_db.env.begin(write=True) as txn:
                for utxo_key, utxo_value in all_utxos.items():
                    try:
                        batch_data[f"utxo:{utxo_key}"] = pickle.dumps(utxo_value)
                    except pickle.PicklingError as e:
                        logging.error(f"[ERROR] ❌ Failed to serialize UTXO {utxo_key}: {e}")
                        continue

                self.utxo_db.bulk_put(batch_data, txn)

            logging.info(f"[INFO] ✅ Successfully exported {len(all_utxos)} UTXOs to LMDB.")

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to export UTXOs to LMDB: {str(e)}")


    def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        """
        Retrieve a transaction from LMDB with improved error handling.
        """
        try:
            with self.poc.lmdb_manager.env.begin() as txn:
                tx_data = txn.get(f"transaction:{tx_id}".encode())

            if not tx_data:
                logging.warning(f"[WARNING] Transaction {tx_id} not found in LMDB.")
                return None

            try:
                transaction_dict = pickle.loads(tx_data)
                return Transaction.from_dict(transaction_dict)
            except (pickle.UnpicklingError, json.JSONDecodeError) as e:
                logging.error(f"[ERROR] ❌ Corrupt transaction data for {tx_id}: {e}")
                return None

        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to retrieve transaction {tx_id}: {str(e)}")
            return None


    def purge_chain(self):
        """
        Delete all stored blocks from LMDB and reinitialize block storage.
        This method purges the blockchain metadata, transactions, and UTXOs,
        then reinitializes the block file and storage.
        """
        try:
            # ✅ Delete all blocks from LMDB metadata storage
            with self.block_metadata_db.env.begin(write=True) as txn:
                cursor = txn.cursor()
                for key, _ in cursor:
                    if key.decode().startswith("block:"):
                        txn.delete(key)
                cursor.close()  # Close the cursor after use
                logging.info("[PURGE] ✅ Deleted all blocks from block_metadata database.")

            # ✅ Delete all transactions from txindex LMDB
            with self.txindex_db.env.begin(write=True) as txn:
                cursor = txn.cursor()
                for key, _ in cursor:
                    if key.decode().startswith("tx:"):
                        txn.delete(key)
                cursor.close()  # Close the cursor after use
                logging.info("[PURGE] ✅ Deleted all transactions from txindex database.")

            # ✅ Delete all UTXOs from UTXO database
            with self.utxo_db.env.begin(write=True) as txn:
                cursor = txn.cursor()
                for key, _ in cursor:
                    if key.decode().startswith("utxo:"):
                        txn.delete(key)
                cursor.close()  # Close the cursor after use
                logging.info("[PURGE] ✅ Deleted all UTXOs from utxo database.")

            # ✅ Delete the block.data file if it exists
            if os.path.exists(self.current_block_file):
                os.remove(self.current_block_file)
                logging.info(f"[PURGE] ✅ Deleted block.data file: {self.current_block_file}")

            # ✅ Reinitialize block storage
            self._initialize_block_data_file()
            logging.info("[PURGE] ✅ Block storage reinitialized successfully.")


        except OSError as e:
            logging.error(f"[PURGE ERROR] ❌ File operation failed: {e}")
            raise
        except Exception as e:
            logging.error(f"[PURGE ERROR] ❌ Unexpected error during chain purge: {e}")
            raise

    def get_pending_transactions(self) -> List[Transaction]:
        transactions = []
        try:
            with self.mempool_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.decode().startswith("tx:"):
                        tx_data = json.loads(value.decode("utf-8"))
                        # Convert dict to Transaction object
                        tx = Transaction.from_dict(tx_data)
                        transactions.append(tx)
            return transactions
        except Exception as e:
            logging.error(f"[ERROR] ❌ Failed to retrieve pending transactions: {e}")
            return []        


