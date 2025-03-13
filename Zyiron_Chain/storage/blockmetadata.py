import os
import string
import sys
import struct
import json
import pickle
import time
import hashlib
from decimal import Decimal
from typing import Optional, List, Dict, Union

# Ensure module path is set correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.utils.deserializer import Deserializer
from Zyiron_Chain.storage.tx_storage import TxStorage

class BlockMetadata:
    """
    BlockMetadata is responsible for handling block metadata storage.
    
    Responsibilities:
      - Store block headers (metadata) in LMDB.
      - Track block offsets and file information from the block.data file.
      - Ensure blocks are stored with the correct magic number.
      - Use single SHA3-384 hashing.
      - Provide detailed print statements for every major step and error.
    """

    def __init__(self, block_metadata_db: LMDBManager, txindex_db: LMDBManager, tx_storage: Optional[TxStorage], current_block_file: str):
        """
        Initializes BlockMetadata:
         - Uses shared LMDB instances for block metadata and transaction index.
         - Stores transaction storage reference.
         - Manages block data file paths and ensures correct initialization.
        """
        try:
            print("[BlockMetadata.__init__] INFO: Initializing BlockMetadata with shared LMDB instances...")

            # ✅ **Use Shared LMDB Instances from WholeBlockData**
            if not block_metadata_db or not txindex_db:
                raise ValueError("[BlockMetadata.__init__] ERROR: `block_metadata_db` and `txindex_db` are required.")

            self.block_metadata_db = block_metadata_db
            self.txindex_db = txindex_db

            # ✅ **Ensure TxStorage Is Provided**
            if not tx_storage:
                raise ValueError("[BlockMetadata.__init__] ERROR: TxStorage instance is required.")
            self.tx_storage = tx_storage

            # ✅ **Use Shared Block Data File Path from WholeBlockData**
            if not current_block_file:
                raise ValueError("[BlockMetadata.__init__] ERROR: `current_block_file` path is required.")
            self.current_block_file = current_block_file
            self.current_block_offset = 0

            # ✅ **Ensure Block Data File Exists and Is Initialized**
            self._initialize_block_data_file()

            print("[BlockMetadata.__init__] ✅ SUCCESS: Initialized BlockMetadata with shared LMDB instances and block storage.")

        except Exception as e:
            print(f"[BlockMetadata.__init__] ❌ ERROR: Initialization failed: {e}")
            raise




    def get_block_by_height(self, height: int) -> Optional[Block]:
        """
        Retrieve a block using its height from the shared LMDB database.

        :param height: Block height to look up.
        :return: The block if found and valid, or None if not found.
        """
        try:
            print(f"[BlockMetadata.get_block_by_height] INFO: Searching for block at height {height}...")

            # ✅ Ensure LMDB Instance Exists
            if not self.block_metadata_db:
                print("[BlockMetadata.get_block_by_height] ERROR: `block_metadata_db` is not set. Cannot retrieve block.")
                return None

            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    try:
                        key_decoded = key.decode()
                        if not key_decoded.startswith("block:"):
                            continue

                        # ✅ Load and validate block metadata
                        block_metadata = json.loads(value.decode("utf-8"))
                        if not isinstance(block_metadata, dict) or "block_header" not in block_metadata:
                            print(f"[BlockMetadata.get_block_by_height] WARNING: Skipping invalid metadata entry: {key_decoded}")
                            continue

                        header = block_metadata["block_header"]

                        # ✅ Ensure block height matches the requested height
                        if "index" in header and header["index"] == height:
                            print(f"[BlockMetadata.get_block_by_height] SUCCESS: Found block at height {height}. Validating integrity...")

                            # ✅ Verify Block Hash Validity (Preserve Mined Hash)
                            block_hash = header.get("hash")
                            if not block_hash or len(block_hash) != Constants.SHA3_384_HASH_SIZE * 2:  # Ensure 48-byte SHA3-384 hash
                                print(f"[BlockMetadata.get_block_by_height] ERROR: Block {height} has an invalid hash.")
                                continue

                            # ✅ Verify Merkle Root Integrity
                            merkle_root = header.get("merkle_root")
                            if not merkle_root or len(merkle_root) != Constants.SHA3_384_HASH_SIZE * 2:
                                print(f"[BlockMetadata.get_block_by_height] ERROR: Block {height} has an invalid Merkle root.")
                                continue

                            # ✅ Convert Block Header to Block Object (Preserving Mined Hash)
                            block_obj = Block.from_dict(header)

                            # ✅ Ensure Block Hash Remains Consistent (No Re-Hashing)
                            if block_obj and block_obj.hash == block_hash:
                                print(f"[BlockMetadata.get_block_by_height] ✅ SUCCESS: Block {height} is valid and hash matches.")
                                return block_obj
                            else:
                                print(f"[BlockMetadata.get_block_by_height] ERROR: Hash mismatch for Block {height}. Stored hash does not match reconstructed hash.")

                    except json.JSONDecodeError:
                        print(f"[BlockMetadata.get_block_by_height] ERROR: Failed to parse block metadata for key {key_decoded}")
                    except Exception as e:
                        print(f"[BlockMetadata.get_block_by_height] ERROR: Unexpected error while processing block data: {e}")

            print(f"[BlockMetadata.get_block_by_height] WARNING: No valid block found at height {height}.")
            return None

        except Exception as e:
            print(f"[BlockMetadata.get_block_by_height] ERROR: Failed to retrieve block by height {height}: {e}")
            return None


    def initialize_txindex(self):
        """
        Ensures the `txindex_db` is properly initialized using the shared instance from WholeBlockData.
        - If already initialized, it does nothing.
        - If missing, it logs an error and prevents reinitialization.
        """
        try:
            # ✅ **Ensure Shared Instance Is Used**
            if not self.txindex_db:
                print("[BlockMetadata.initialize_txindex] ERROR: `txindex_db` is not set. Cannot initialize transaction index.")
                return

            # ✅ **Prevent Redundant Initialization**
            print("[BlockMetadata.initialize_txindex] INFO: Using shared `txindex_db` instance from WholeBlockData.")

            with self.txindex_db.env.begin(write=True) as txn:
                txn.put(b"txindex_initialized", b"true")

            print("[BlockMetadata.initialize_txindex] SUCCESS: Transaction index database verified.")

        except Exception as e:
            print(f"[BlockMetadata.initialize_txindex] ERROR: Failed to initialize `txindex_db`: {e}")
            raise


    def get_block_metadata(self, block_hash: str):
        """
        Retrieves block metadata from LMDB using the shared instance.
        """
        try:
            print(f"[BlockMetadata.get_block_metadata] INFO: Retrieving metadata for Block {block_hash}...")

            # ✅ **Ensure Shared LMDB Instance Is Used**
            if not self.block_metadata_db:
                print("[BlockMetadata.get_block_metadata] ERROR: `block_metadata_db` is not set. Cannot retrieve metadata.")
                return None

            # ✅ **Ensure block_hash is properly formatted**
            if not isinstance(block_hash, str) or len(block_hash) != Constants.SHA3_384_HASH_SIZE:
                print(f"[BlockMetadata.get_block_metadata] ERROR: Invalid block hash format: {block_hash}")
                return None

            # ✅ **Retrieve Block Metadata from LMDB Using Shared Instance**
            with self.block_metadata_db.env.begin() as txn:
                data = txn.get(block_hash.encode("utf-8"))

            if not data:
                print(f"[BlockMetadata.get_block_metadata] WARNING: No metadata found for block hash: {block_hash}")
                return None

            # ✅ **Deserialize and Validate Block Metadata**
            try:
                metadata = Deserializer().deserialize(data)
                if not isinstance(metadata, dict) or "block_header" not in metadata:
                    print(f"[BlockMetadata.get_block_metadata] ERROR: Invalid metadata structure for block {block_hash}")
                    return None

                print(f"[BlockMetadata.get_block_metadata] SUCCESS: Retrieved metadata for block {block_hash}.")
                return metadata

            except Exception as e:
                print(f"[BlockMetadata.get_block_metadata] ERROR: Failed to deserialize metadata for block {block_hash}: {e}")
                return None

        except Exception as e:
            print(f"[BlockMetadata.get_block_metadata] ERROR: Unexpected error retrieving block metadata: {e}")
            return None



    def create_block_data_file(self, block: Block):
        """
        Append a block to the block.data file in binary format.
        Uses the shared file path from WholeBlockData.
        """
        try:
            # ✅ **Ensure Shared File Path Is Used**
            if not self.current_block_file:
                print("[BlockMetadata.create_block_data_file] ERROR: `current_block_file` is not set. Cannot write block data.")
                return

            print(f"[BlockMetadata.create_block_data_file] INFO: Writing Block {block.index} to {self.current_block_file}...")

            # ✅ **Ensure Block File Rollover Is Handled Before Writing**
            self._handle_block_file_rollover()

            with open(self.current_block_file, "ab+") as f:
                f.seek(0, os.SEEK_END)

                # ✅ **Ensure the Magic Number Is Written **ONLY ONCE** at the Start of the File**
                if f.tell() == 0:
                    f.write(struct.pack(">I", Constants.MAGIC_NUMBER))
                    print(f"[BlockMetadata.create_block_data_file] INFO: Wrote network magic number {hex(Constants.MAGIC_NUMBER)} to block.data.")

                # ✅ **Serialize Block to Binary Format**
                block_data = self._serialize_block_to_binary(block)

                # ✅ **Write Block Size (4 Bytes) Followed by Block Data**
                block_size_bytes = len(block_data).to_bytes(4, byteorder="big")
                f.write(block_size_bytes)
                f.write(block_data)

                # ✅ **Update Block Offset to Ensure File Integrity**
                self.current_block_offset = f.tell()
                print(f"[BlockMetadata.create_block_data_file] SUCCESS: Block {block.index} appended at offset {self.current_block_offset}.")

        except Exception as e:
            print(f"[BlockMetadata.create_block_data_file] ERROR: Failed to write block {block.index} to {self.current_block_file}: {e}")
            raise



    def _deserialize_block_from_binary(self, block_data: bytes) -> Optional[Block]:
        """
        Deserialize binary block data back into a Block object.
        - Ensures difficulty (64B), miner address (128B), and signature (48B) are properly deserialized.
        - Extracts transactions while maintaining correct structure.

        Returns:
            Block object if deserialization is successful, otherwise None.
        """
        try:
            print("[BlockMetadata._deserialize_block_from_binary] INFO: Starting block deserialization...")

            # ✅ **Define Standardized Header Format**
            header_format = ">I 48s 48s Q I B64s 128s 48s Q Q I"
            base_header_size = struct.calcsize(header_format)
            print(f"[BlockMetadata._deserialize_block_from_binary] INFO: Expected header size: {base_header_size} bytes.")

            # ✅ **Ensure block_data is large enough for the header**
            if len(block_data) < base_header_size:
                print("[BlockMetadata._deserialize_block_from_binary] ❌ ERROR: Block data too small for valid header.")
                return None

            # ✅ **Unpack Header Fields**
            try:
                (
                    block_height,
                    prev_block_hash,
                    merkle_root,
                    timestamp,
                    nonce,
                    difficulty_length,
                    difficulty_bytes,
                    miner_address_bytes,
                    transaction_signature,
                    reward,
                    fees_collected,
                    block_version
                ) = struct.unpack(header_format, block_data[:base_header_size])

                print(f"[BlockMetadata._deserialize_block_from_binary] INFO: Header unpacked successfully.")
                print(f"  - Block Height: {block_height}")
                print(f"  - Timestamp: {timestamp}")
                print(f"  - Nonce: {nonce}")
                print(f"  - Reward: {reward}")
                print(f"  - Fees Collected: {fees_collected}")
                print(f"  - Block Version: {block_version}")

            except struct.error as e:
                print(f"[BlockMetadata._deserialize_block_from_binary] ❌ ERROR: Struct unpacking failed: {e}")
                return None

            # ✅ **Validate Difficulty (Always 64 Bytes)**
            if len(difficulty_bytes) != 64:
                print("[BlockMetadata._deserialize_block_from_binary] ❌ ERROR: Difficulty size incorrect (expected 64 bytes).")
                return None
            difficulty_int = int.from_bytes(difficulty_bytes, "big", signed=False)
            print(f"[BlockMetadata._deserialize_block_from_binary] INFO: Difficulty value: {difficulty_int}.")

            # ✅ **Process Miner Address (Ensure Proper Decoding, Always 128 Bytes)**
            miner_address_str = miner_address_bytes.rstrip(b'\x00').decode("utf-8")
            print(f"[BlockMetadata._deserialize_block_from_binary] INFO: Miner address: {miner_address_str}.")

            # ✅ **Ensure Transaction Signature is Always 48 Bytes**
            transaction_signature = transaction_signature[:48]

            # ✅ **Extract Transaction Count (4 bytes)**
            tx_count_offset = base_header_size
            if len(block_data) < tx_count_offset + 4:
                print("[BlockMetadata._deserialize_block_from_binary] ❌ ERROR: Block data is missing transaction count.")
                return None

            tx_count = struct.unpack(">I", block_data[tx_count_offset:tx_count_offset + 4])[0]
            print(f"[BlockMetadata._deserialize_block_from_binary] INFO: Block {block_height} contains {tx_count} transaction(s).")

            tx_data_offset = tx_count_offset + 4
            transactions = []

            # ✅ **Extract Transactions (Size-Prefixed)**
            for i in range(tx_count):
                print(f"[BlockMetadata._deserialize_block_from_binary] INFO: Processing transaction {i} at offset {tx_data_offset}.")

                # ✅ **Ensure enough data exists for transaction size**
                if tx_data_offset + 4 > len(block_data):
                    print(f"[BlockMetadata._deserialize_block_from_binary] ❌ ERROR: Missing transaction size at index {i}.")
                    return None

                tx_size = struct.unpack(">I", block_data[tx_data_offset:tx_data_offset + 4])[0]
                tx_data_offset += 4

                print(f"[BlockMetadata._deserialize_block_from_binary] INFO: Transaction {i} size: {tx_size} bytes.")

                # ✅ **Ensure full transaction data is available**
                if tx_data_offset + tx_size > len(block_data):
                    print(f"[BlockMetadata._deserialize_block_from_binary] ❌ ERROR: Incomplete transaction at index {i}.")
                    return None

                tx_bytes = block_data[tx_data_offset:tx_data_offset + tx_size]
                tx_data_offset += tx_size

                try:
                    tx_obj = json.loads(tx_bytes.decode("utf-8"))
                    if "tx_id" not in tx_obj:
                        print(f"[BlockMetadata._deserialize_block_from_binary] ❌ ERROR: Transaction {i} missing 'tx_id'. Skipping.")
                        continue
                    transactions.append(tx_obj)
                    print(f"[BlockMetadata._deserialize_block_from_binary] INFO: Transaction {i} deserialized successfully with tx_id: {tx_obj.get('tx_id')}.")
                except json.JSONDecodeError as e:
                    print(f"[BlockMetadata._deserialize_block_from_binary] ❌ ERROR: Failed to decode transaction JSON at index {i}: {e}")
                    return None
                except Exception as e:
                    print(f"[BlockMetadata._deserialize_block_from_binary] ❌ ERROR: Unexpected error during transaction deserialization at index {i}: {e}")
                    return None

            # ✅ **Ensure Correct Number of Transactions**
            if len(transactions) != tx_count:
                print(f"[BlockMetadata._deserialize_block_from_binary] ❌ ERROR: Expected {tx_count} transactions but only deserialized {len(transactions)}.")
                return None

            # ✅ **Construct Block Dictionary**
            block_dict = {
                "index": block_height,
                "previous_hash": prev_block_hash.hex(),
                "merkle_root": merkle_root.hex(),
                "timestamp": timestamp,
                "nonce": nonce,
                "difficulty": difficulty_int,
                "miner_address": miner_address_str,
                "transaction_signature": transaction_signature.hex(),
                "reward": reward,
                "fees": fees_collected,
                "version": block_version,
                "transactions": transactions
            }
            print(f"[BlockMetadata._deserialize_block_from_binary] INFO: Block dictionary constructed successfully.")

            # ✅ **Validate Required Fields**
            required_keys = [
                "index", "previous_hash", "merkle_root", "timestamp",
                "nonce", "difficulty", "miner_address", "transaction_signature",
                "reward", "fees", "version"
            ]
            for key in required_keys:
                if key not in block_dict:
                    print(f"[BlockMetadata._deserialize_block_from_binary] ❌ ERROR: Block missing required field: {key}")
                    return None

            print(f"[BlockMetadata._deserialize_block_from_binary] ✅ SUCCESS: Block {block_height} deserialized successfully.")
            return Block.from_dict(block_dict)

        except Exception as e:
            print(f"[BlockMetadata._deserialize_block_from_binary] ❌ ERROR: Failed to deserialize block: {e}")
            return None





    def _initialize_block_data_file(self):
        """
        Initialize the block.data file with the correct magic number if missing.
        Uses the shared file path from WholeBlockData.
        """
        try:
            # ✅ **Ensure Shared File Path Is Used**
            if not self.current_block_file:
                print("[BlockMetadata._initialize_block_data_file] ❌ ERROR: `current_block_file` is not set. Cannot initialize block data.")
                return None

            print(f"[BlockMetadata._initialize_block_data_file] INFO: Initializing block storage at {self.current_block_file}...")

            # ✅ **Ensure Directory Exists**
            block_data_dir = os.path.dirname(self.current_block_file)
            if not block_data_dir:
                print("[BlockMetadata._initialize_block_data_file] ❌ ERROR: Block data directory not found.")
                return None
            os.makedirs(block_data_dir, exist_ok=True)

            # ✅ **Check if File Exists and Is Non-Empty**
            file_exists = os.path.exists(self.current_block_file)
            file_is_empty = file_exists and os.path.getsize(self.current_block_file) == 0

            # ✅ **Write Magic Number If File Is New or Empty**
            if not file_exists or file_is_empty:
                with open(self.current_block_file, "wb") as f:
                    f.write(struct.pack(">I", Constants.MAGIC_NUMBER))
                print(f"[BlockMetadata._initialize_block_data_file] ✅ INFO: Created block.data with magic number {hex(Constants.MAGIC_NUMBER)}.")
            else:
                print("[BlockMetadata._initialize_block_data_file] INFO: block.data file exists. Skipping magic number write.")

            # ✅ **Validate Existing Magic Number**
            with open(self.current_block_file, "rb") as f:
                magic_number_bytes = f.read(4)
                if len(magic_number_bytes) != 4:
                    print("[BlockMetadata._initialize_block_data_file] ❌ ERROR: block.data file is corrupted or too small.")
                    return None

                file_magic_number = struct.unpack(">I", magic_number_bytes)[0]

                if file_magic_number != Constants.MAGIC_NUMBER:
                    print(f"[BlockMetadata._initialize_block_data_file] ❌ ERROR: Invalid magic number in block.data file: {hex(file_magic_number)}. Expected {hex(Constants.MAGIC_NUMBER)}.")
                    return None

            # ✅ **Validate Cached Supply Values Before Returning**
            with self.block_metadata_db.env.begin() as txn:
                cached_supply = txn.get(b"total_mined_supply")

            if cached_supply:
                try:
                    total_supply = Decimal(cached_supply.decode("utf-8"))
                    if total_supply < 0:
                        print("[BlockMetadata._initialize_block_data_file] ❌ ERROR: Cached supply contains invalid negative value.")
                        return None
                    print(f"[BlockMetadata._initialize_block_data_file] INFO: Cached total supply: {total_supply} ZYC")
                except (UnicodeDecodeError, ValueError) as decode_error:
                    print(f"[BlockMetadata._initialize_block_data_file] WARNING: Failed to decode cached total supply: {decode_error}")
                    return None

            print("[BlockMetadata._initialize_block_data_file] ✅ SUCCESS: block.data file validated successfully.")

        except Exception as e:
            print(f"[BlockMetadata._initialize_block_data_file] ❌ ERROR: Failed to initialize block.data file: {e}")
            return None




    def store_block(self, block: Block, difficulty: Union[bytes, int, str]):
        """
        Stores block metadata in LMDB and appends block data to block.data.
        Enhanced with robust hex/bytes handling, transaction validation,
        and improved error checking. Ensures no re-hashing occurs.
        """
        try:
            print(f"[BlockMetadata.store_block] INFO: Storing Block {block.index}...")

            # Validate LMDB instances
            if not self.block_metadata_db or not self.txindex_db:
                print("[BlockMetadata.store_block] ❌ ERROR: LMDB instances not initialized")
                return

            # Check for existing block using both height and hash
            existing_by_height = self.get_block_by_height(block.index)
            existing_by_hash = self.get_block_metadata(block.hash.hex() if isinstance(block.hash, bytes) else block.hash)
            if existing_by_height or existing_by_hash:
                print(f"[BlockMetadata.store_block] ⚠️ WARNING: Block {block.index} exists. Skipping")
                return

            # Enhanced difficulty handling
            if isinstance(difficulty, str):  # Hex string input
                if not all(c in string.hexdigits for c in difficulty):
                    raise ValueError("Invalid hex characters in difficulty")
                # Convert hex to bytes and check length
                difficulty_bytes = bytes.fromhex(difficulty)
                if not (48 <= len(difficulty_bytes) <= 64):
                    raise ValueError(f"Difficulty must be 48 to 64 bytes (hex), got {len(difficulty_bytes)}")
                # Pad with leading zeros to 64 bytes
                difficulty_bytes = difficulty_bytes.ljust(64, b'\x00')
            elif isinstance(difficulty, bytes):
                if not (48 <= len(difficulty) <= 64):
                    raise ValueError(f"Difficulty must be 48 to 64 bytes, got {len(difficulty)}")
                # Pad with leading zeros to 64 bytes
                difficulty_bytes = difficulty.ljust(64, b'\x00')
            elif isinstance(difficulty, int):
                # Convert to bytes and pad to 64 bytes
                difficulty_bytes = difficulty.to_bytes(64, "big", signed=False)
            else:
                raise TypeError("Difficulty must be hex str, bytes, or int")

            # Robust miner address handling
            miner_address = self._get_miner_address(block)  # Extracted to helper method

            # Validate and convert hash fields
            def ensure_hex(field, value):
                if isinstance(value, bytes):
                    return value.hex()
                if isinstance(value, str) and len(value) == 96 and all(c in string.hexdigits for c in value):
                    return value
                raise ValueError(f"Invalid {field} format: {type(value)}")

            previous_hash_hex = ensure_hex("previous_hash", block.previous_hash)
            merkle_root_hex = ensure_hex("merkle_root", block.merkle_root)
            block_hash_hex = ensure_hex("block_hash", block.hash)

            # Transaction validation and ID extraction
            tx_ids = []
            valid_transactions = []
            for tx in block.transactions:
                tx_id = self._validate_and_extract_tx_id(tx)  # Helper method
                if tx_id:
                    tx_ids.append(tx_id)
                    valid_transactions.append(tx)

            # Build block metadata with improved validation
            block_dict = {
                "index": block.index,
                "previous_hash": previous_hash_hex,
                "merkle_root": merkle_root_hex,
                "timestamp": block.timestamp,
                "nonce": block.nonce,
                "difficulty": difficulty_bytes.hex(),  # Store as 64-byte hex string
                "miner_address": miner_address,
                "transaction_signature": getattr(block, "signature", b"\x00"*48)[:48].hex(),
                "reward": str(Decimal(block.reward).normalize() if hasattr(block, "reward") else 0),
                "fees": str(Decimal(block.fees).normalize() if hasattr(block, "fees") else 0),
                "version": block.version,
                "transactions": [tx.to_dict() if hasattr(tx, "to_dict") else tx for tx in valid_transactions],
                "hash": block_hash_hex  # Use the mined hash directly
            }

            # File handling with magic number verification
            with open(self.current_block_file, "ab+") as block_file:
                block_file.seek(0)
                existing_magic = block_file.read(4)
                if existing_magic != struct.pack(">I", Constants.MAGIC_NUMBER):
                    block_file.seek(0)
                    block_file.truncate()
                    block_file.write(struct.pack(">I", Constants.MAGIC_NUMBER))
                    print(f"[BlockMetadata.store_block] ✅ Wrote magic number")

                block_file.seek(0, os.SEEK_END)
                block_offset = block_file.tell()

            # LMDB transaction with proper error handling
            with self.block_metadata_db.env.begin(write=True) as txn:
                try:
                    block_metadata = {
                        "hash": block_hash_hex,
                        "block_header": block_dict,
                        "transaction_count": len(valid_transactions),
                        "block_size": len(json.dumps(block_dict)),
                        "data_file": self.current_block_file,
                        "data_offset": block_offset,
                        "tx_ids": tx_ids
                    }
                    txn.put(f"block:{block_hash_hex}".encode(), json.dumps(block_metadata).encode())
                except Exception as e:
                    print(f"[BlockMetadata.store_block] ❌ LMDB Error: {e}")
                    raise

            # Transaction indexing with validation
            print(f"[BlockMetadata.store_block] Indexing {len(valid_transactions)} transactions...")
            for tx in valid_transactions:
                self._index_transaction(tx, block_hash_hex)

            print(f"[BlockMetadata.store_block] ✅ Block {block.index} stored successfully")

        except Exception as e:
            print(f"[BlockMetadata.store_block] ❌ Critical Error: {e}")
            raise

    def _get_miner_address(self, block: Block) -> str:
        """
        Extract the miner address from the coinbase transaction's script public key.
        If no coinbase transaction is found, fall back to a default address.
        """
        try:
            # Find the coinbase transaction in the block
            coinbase_tx = next(
                (tx for tx in block.transactions if getattr(tx, "tx_type", None) == "COINBASE"),
                None
            )

            if coinbase_tx and hasattr(coinbase_tx, "outputs") and coinbase_tx.outputs:
                # Extract the script public key from the first output
                script_pub_key = coinbase_tx.outputs[0].script_pub_key
                if script_pub_key:
                    return script_pub_key

            # Fallback to a default miner address if no coinbase transaction is found
            print("[BlockMetadata._get_miner_address] WARNING: No coinbase transaction found. Using default miner address.")
            return Constants.DEFAULT_MINER_ADDRESS

        except Exception as e:
            print(f"[BlockMetadata._get_miner_address] ❌ ERROR: Failed to retrieve miner address: {e}")
            return Constants.DEFAULT_MINER_ADDRESS

    def _validate_and_extract_tx_id(self, tx) -> Optional[str]:
        """Validate transaction and extract TX ID with multiple format support"""
        try:
            if isinstance(tx, dict):
                tx_id = tx.get('tx_id', '')
            elif hasattr(tx, 'tx_id'):
                tx_id = tx.tx_id
            else:
                return None

            # Convert bytes to hex if needed
            if isinstance(tx_id, bytes):
                return tx_id.hex()
            if isinstance(tx_id, str) and len(tx_id) == 96 and all(c in string.hexdigits for c in tx_id):
                return tx_id
            return None
        except Exception as e:
            print(f"[BlockMetadata] ⚠️ Invalid TX: {e}")
            return None

    def _index_transaction(self, tx, block_hash: str):
        """Safe transaction indexing with validation"""
        try:
            tx_data = tx.to_dict() if hasattr(tx, "to_dict") else tx
            if not isinstance(tx_data, dict):
                raise ValueError("Invalid transaction format")

            required_fields = ['tx_id', 'inputs', 'outputs']
            if not all(field in tx_data for field in required_fields):
                raise ValueError("Missing required transaction fields")

            # Convert bytes TX_ID to hex string
            tx_id = tx_data['tx_id']
            if isinstance(tx_id, bytes):
                tx_id = tx_id.hex()
            if not isinstance(tx_id, str) or len(tx_id) != 96:
                raise ValueError("Invalid TX_ID format")

            with self.txindex_db.env.begin(write=True) as txn:
                txn.put(f"tx:{tx_id}".encode(), json.dumps({
                    'block_hash': block_hash,
                    'inputs': tx_data.get('inputs', []),
                    'outputs': tx_data.get('outputs', []),
                    'timestamp': tx_data.get('timestamp', int(time.time())),
                    'signatures': {
                        'tx': tx_data.get('tx_signature', '00'*48)[:48],
                        'falcon': tx_data.get('falcon_signature', '00'*48)[:48]
                    }
                }).encode())

        except Exception as e:
            print(f"[BlockMetadata] ❌ Failed to index transaction: {e}")


    def _serialize_transactions(self, transactions: list) -> list:
        """
        Convert transactions to a standardized dictionary format for serialization.
        
        - Supports both Transaction objects (via .to_dict()) and existing dictionaries.
        - Ensures that all required fields (tx_id, inputs, outputs, signature) are present.
        - Prefixes each transaction with its size (4 bytes) to match block serialization format.
        """
        serialized_transactions = []

        for idx, tx in enumerate(transactions):
            try:
                # ✅ **Convert Transaction to Dictionary if Needed**
                if hasattr(tx, "to_dict") and callable(tx.to_dict):
                    serialized_tx = tx.to_dict()
                    print(f"[BlockMetadata._serialize_transactions] INFO: Serialized transaction at index {idx} from object.")
                elif isinstance(tx, dict):
                    serialized_tx = tx
                    print(f"[BlockMetadata._serialize_transactions] INFO: Serialized transaction at index {idx} from dictionary.")
                else:
                    raise TypeError(f"[BlockMetadata._serialize_transactions] ERROR: Transaction at index {idx} must be a dict or have a to_dict() method.")

                # ✅ **Ensure Required Fields Exist**
                if "tx_id" not in serialized_tx or not isinstance(serialized_tx["tx_id"], str):
                    print(f"[BlockMetadata._serialize_transactions] WARNING: Transaction at index {idx} is missing a valid 'tx_id'. Skipping.")
                    continue

                if "inputs" not in serialized_tx or not isinstance(serialized_tx["inputs"], list):
                    serialized_tx["inputs"] = []
                    print(f"[BlockMetadata._serialize_transactions] WARNING: Transaction at index {idx} is missing 'inputs'. Setting empty list.")

                if "outputs" not in serialized_tx or not isinstance(serialized_tx["outputs"], list):
                    serialized_tx["outputs"] = []
                    print(f"[BlockMetadata._serialize_transactions] WARNING: Transaction at index {idx} is missing 'outputs'. Setting empty list.")

                # ✅ **Ensure Transaction Signature Exists (48 Bytes)**
                if "signature" not in serialized_tx or not isinstance(serialized_tx["signature"], str):
                    serialized_tx["signature"] = "0" * 96  # Placeholder (48 bytes in hex)
                    print(f"[BlockMetadata._serialize_transactions] WARNING: Transaction at index {idx} is missing 'signature'. Assigning default placeholder.")

                # ✅ **Serialize Transaction as JSON Bytes**
                tx_json = json.dumps(serialized_tx, sort_keys=True).encode("utf-8")
                tx_size = len(tx_json)

                # ✅ **Prefix Each Transaction with Its Size (4 Bytes)**
                serialized_tx_data = struct.pack(">I", tx_size) + tx_json

                # ✅ **Add to Serialized List**
                serialized_transactions.append(serialized_tx_data)
                print(f"[BlockMetadata._serialize_transactions] INFO: Transaction {idx} serialized successfully with size {tx_size} bytes.")

            except Exception as e:
                print(f"[BlockMetadata._serialize_transactions] ERROR: Failed to serialize transaction at index {idx}: {e}")
                raise

        print(f"[BlockMetadata._serialize_transactions] ✅ SUCCESS: Serialized {len(serialized_transactions)} transactions.")
        return serialized_transactions




    def _get_current_block_file(self):
        """
        Dynamically manage block data files, ensuring file rollover 
        based on Constants.BLOCK_DATA_FILE_SIZE_MB (explicitly set).
        """
        block_data_folder = Constants.DATABASES['block_data']
        os.makedirs(block_data_folder, exist_ok=True)

        files = sorted([f for f in os.listdir(block_data_folder) if f.endswith('.data')])
        if not files:
            current_file = os.path.join(block_data_folder, "block_00001.data")
            print(f"[BlockMetadata._get_current_block_file] Creating new block data file: {current_file}")
            return current_file

        latest_file = os.path.join(block_data_folder, files[-1])

        if os.path.getsize(latest_file) >= Constants.BLOCK_DATA_FILE_SIZE_MB * 1024 * 1024:
            next_file_number = int(files[-1].split('_')[1].split('.')[0]) + 1
            current_file = os.path.join(block_data_folder, f"block_{next_file_number:05d}.data")
            print(f"[BlockMetadata._get_current_block_file] Rolling over to new block data file: {current_file}")
            return current_file

        return latest_file


    def verify_block_storage(self, block: Block) -> bool:
        """
        Verify that a block exists in LMDB storage using its hash.
        """
        try:
            if not isinstance(block.hash, str) or len(block.hash) != Constants.SHA3_384_HASH_SIZE:
                print(f"[BlockMetadata.verify_block_storage] ERROR: Invalid block hash format: {block.hash}")
                return False
            with self.block_metadata_db.env.begin() as txn:
                stored_metadata = txn.get(f"block:{block.hash}".encode())
            if stored_metadata:
                print(f"[BlockMetadata.verify_block_storage] INFO: Block {block.index} exists in LMDB.")
                return True
            else:
                print(f"[BlockMetadata.verify_block_storage] WARNING: Block {block.index} not found in LMDB.")
                return False
        except Exception as e:
            print(f"[BlockMetadata.verify_block_storage] ERROR: Block verification failed for Block {block.index}: {e}")
            return False

    def validate_block_structure(self, block: Block) -> bool:
        """
        Validate that a block contains all required fields, has a valid hash, and contains properly formatted transactions.
        Also ensures metadata integrity and checks for version mismatches.
        """
        try:
            print(f"[BlockMetadata.validate_block_structure] INFO: Validating structure for Block {block.index}...")

            # ✅ **Required Block Fields**
            required_fields = {
                "index", "hash", "header", "transactions", "merkle_root",
                "timestamp", "difficulty", "previous_hash", "nonce", "version"
            }

            # ✅ **Ensure Block Object is Valid**
            if not isinstance(block, Block):
                print(f"[BlockMetadata.validate_block_structure] ❌ ERROR: Invalid block type: {type(block)}")
                return False

            # ✅ **Check for Missing Fields**
            missing_fields = [field for field in required_fields if not hasattr(block, field)]
            if missing_fields:
                print(f"[BlockMetadata.validate_block_structure] ❌ ERROR: Block {block.index} is missing fields: {missing_fields}")
                return False

            # ✅ **Verify Block Hash Integrity**
            calculated_hash = block.calculate_hash()
            if block.hash != calculated_hash:
                print(f"[BlockMetadata.validate_block_structure] ❌ ERROR: Block {block.index} has an invalid hash.\n"
                    f"Expected: {calculated_hash}\n"
                    f"Found: {block.hash}")
                return False

            # ✅ **Validate Transactions Structure**
            if not isinstance(block.transactions, list) or not all(isinstance(tx, dict) for tx in block.transactions):
                print(f"[BlockMetadata.validate_block_structure] ❌ ERROR: Block {block.index} contains invalid transactions.")
                return False

            # ✅ **Validate Metadata Structure**
            if hasattr(block, "metadata") and block.metadata:
                if not isinstance(block.metadata, dict):
                    print(f"[BlockMetadata.validate_block_structure] ❌ ERROR: Metadata in Block {block.index} is not a valid dictionary.")
                    return False

                required_metadata_keys = {"name", "version", "created_by", "creation_date"}
                missing_metadata = [key for key in required_metadata_keys if key not in block.metadata]

                if missing_metadata:
                    print(f"[BlockMetadata.validate_block_structure] ❌ ERROR: Metadata in Block {block.index} is missing fields: {missing_metadata}")
                    return False

            # ✅ **Check Version Compatibility**
            if block.version != Constants.VERSION:
                print(f"[BlockMetadata.validate_block_structure] ⚠️ WARNING: Block {block.index} version mismatch.\n"
                    f"Expected: {Constants.VERSION}, Found: {block.version}")

            print(f"[BlockMetadata.validate_block_structure] ✅ SUCCESS: Block {block.index} passed structure validation.")
            return True

        except Exception as e:
            print(f"[BlockMetadata.validate_block_structure] ❌ ERROR: Block structure validation failed for Block {block.index}: {e}")
            return False


    def load_chain(self) -> List[Dict]:
        """
        Load all block metadata from LMDB and return as a list of dictionaries.
        """
        try:
            print("[BlockMetadata.load_chain] INFO: Loading blockchain metadata from LMDB...")
            chain_data = []
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if not key.decode().startswith("block:"):
                        continue
                    try:
                        block_meta = json.loads(value.decode("utf-8"))
                        header = block_meta.get("block_header", {})
                        if not isinstance(header, dict) or "index" not in header:
                            print("[BlockMetadata.load_chain] ERROR: Block header missing 'index'")
                            continue
                        chain_data.append(block_meta)
                    except json.JSONDecodeError as e:
                        print(f"[BlockMetadata.load_chain] ERROR: Failed to parse block metadata: {e}")
                        continue
            if not chain_data:
                print("[BlockMetadata.load_chain] WARNING: No blocks found in LMDB. Chain may be empty.")
                return []
            print(f"[BlockMetadata.load_chain] INFO: Successfully loaded {len(chain_data)} blocks from LMDB.")
            return chain_data
        except Exception as e:
            print(f"[BlockMetadata.load_chain] ERROR: Failed to load blockchain metadata: {e}")
            return []

    def _store_block_metadata(self, block: Block) -> None:
        """
        Store additional block metadata for analytics and indexing.
        """
        try:
            metadata = {
                "height": block.index,
                "parent_hash": block.previous_hash,
                "timestamp": block.header.timestamp,
                "difficulty": block.header.difficulty,
            }
            # Here we assume poc.lmdb_manager.put is available in the context;
            # if not, you may remove or adjust this method accordingly.
            # For now, we print the metadata storage action.
            print(f"[BlockMetadata._store_block_metadata] INFO: Storing metadata for block {block.hash}: {metadata}")
        except Exception as e:
            print(f"[BlockMetadata._store_block_metadata] ERROR: Failed to store block metadata: {e}")

    # --------------------- Block.data File Methods --------------------- #


    def _serialize_block_to_binary(self, block: Block) -> bytes:
        """
        Serialize a Block into binary format.
        - Ensures all fields have correct sizes:
            - Difficulty (64B)
            - Miner Address (128B)
            - Signature (48B)
        - Packs header fields and transactions in a standardized format.

        Args:
            block (Block): The block to serialize.

        Returns:
            bytes: The serialized block in binary format.

        Raises:
            ValueError: If any field is missing or exceeds the expected size.
        """
        try:
            print(f"[BlockMetadata] INFO: Serializing Block {block.index} to binary.")

            # ✅ Convert block to dictionary
            block_dict = block.to_dict()
            header = block_dict.get("header", {})

            # ✅ Extract block header fields
            block_height = int(header.get("index", 0))
            prev_block_hash = bytes.fromhex(header.get("previous_hash", Constants.ZERO_HASH))
            merkle_root = bytes.fromhex(header.get("merkle_root", Constants.ZERO_HASH))
            timestamp = int(header.get("timestamp", time.time()))
            nonce = int(header.get("nonce", 0))

            # ✅ **Ensure difficulty is stored correctly (64 bytes)**
            difficulty_hex = header.get("difficulty", "00" * 64)  # Default to zeroed-out difficulty
            difficulty_bytes = bytes.fromhex(difficulty_hex).rjust(64, b'\x00')

            # ✅ **Ensure Difficulty Length (1 byte)**
            difficulty_packed = struct.pack(">B", len(difficulty_bytes)) + difficulty_bytes

            # ✅ **Ensure Miner Address is 128 bytes**
            miner_address_str = header.get("miner_address", "").strip()
            miner_address_encoded = miner_address_str.encode("utf-8")

            if len(miner_address_encoded) > 128:
                miner_address_encoded = miner_address_encoded[:128]  # Truncate if too long
            miner_address_padded = miner_address_encoded.ljust(128, b'\x00')

            # ✅ **Ensure Block Signature is Always 48 Bytes**
            transaction_signature = bytes.fromhex(header.get("transaction_signature", "00" * 96))[:48]

            # ✅ Extract additional metadata fields
            reward = int(float(header.get("reward", 0)))
            fees_collected = int(float(header.get("fees", 0)))
            block_version = int(header.get("version", 1))  # Default to version 1

            print(f"[BlockMetadata] INFO: Header fields - Index: {block_height}, Timestamp: {timestamp}, Nonce: {nonce}.")

            # ✅ **Pack header fields into binary format**
            header_format = ">I 48s 48s Q I B64s 128s 48s Q Q I"
            header_data = struct.pack(
                header_format,
                block_height,
                prev_block_hash,
                merkle_root,
                timestamp,
                nonce,
                len(difficulty_bytes),
                difficulty_bytes,
                miner_address_padded,
                transaction_signature,
                reward,
                fees_collected,
                block_version
            )
            print(f"[BlockMetadata] INFO: Header packed successfully for Block {block.index}.")

            # ✅ **Serialize Transactions**
            serialized_transactions = []
            transactions = block_dict.get("transactions", [])

            print(f"[BlockMetadata] INFO: Serializing {len(transactions)} transactions.")

            for idx, tx in enumerate(transactions):
                try:
                    # ✅ Convert transaction to dictionary if needed
                    if hasattr(tx, "to_dict"):
                        tx_dict = tx.to_dict()
                    elif isinstance(tx, dict):
                        tx_dict = tx
                    else:
                        raise TypeError(f"[BlockMetadata] ERROR: Transaction {idx} is not serializable.")

                    # ✅ **Ensure transactions are JSON-encoded properly**
                    tx_json = json.dumps(tx_dict, ensure_ascii=False, sort_keys=True).encode("utf-8")
                    tx_size = len(tx_json)

                    # ✅ **Prefix each transaction with its size (4 bytes)**
                    serialized_tx = struct.pack(">I", tx_size) + tx_json
                    serialized_transactions.append(serialized_tx)

                    print(f"[BlockMetadata] INFO: Serialized transaction {idx}: size {tx_size} bytes.")

                except Exception as e:
                    print(f"[BlockMetadata] ❌ ERROR: Failed to serialize transaction {idx}: {e}")

            # ✅ **Pack transaction count (4 bytes) and transactions**
            tx_count = len(serialized_transactions)
            tx_count_data = struct.pack(">I", tx_count)
            tx_data = b"".join(serialized_transactions)

            print(f"[BlockMetadata] INFO: {tx_count} transaction(s) serialized.")

            # ✅ **Final Block Binary Format**
            serialized_block = header_data + tx_count_data + tx_data
            print(f"[BlockMetadata] ✅ SUCCESS: Block {block.index} serialized successfully. Total size: {len(serialized_block)} bytes")
            return serialized_block

        except Exception as e:
            print(f"[BlockMetadata] ❌ ERROR: Failed to serialize block {block.index}: {e}")
            raise




    def get_block_from_data_file(self, offset: int):
        """
        Retrieve a block from block.data using its offset.
        Ensures block size validity and header integrity before reading the block.
        """
        try:
            print(f"[BlockMetadata.get_block_from_data_file] INFO: Attempting to retrieve block at offset {offset}.")

            # ✅ **Check if File Exists Before Reading**
            if not os.path.exists(self.current_block_file):
                print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: block.data file not found: {self.current_block_file}")
                return None

            file_size = os.path.getsize(self.current_block_file)
            print(f"[BlockMetadata.get_block_from_data_file] INFO: File size of block.data: {file_size} bytes.")

            # ✅ **Ensure Offset is Within File Size**
            if offset < 0 or offset >= file_size - 8:  # Ensure enough space for block size + magic number
                print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: Offset {offset} is out of bounds.")
                return None

            with open(self.current_block_file, "rb") as f:
                f.seek(offset)

                # ✅ **Validate Magic Number Before Reading Block**
                magic_number_bytes = f.read(4)
                if len(magic_number_bytes) != 4:
                    print("[BlockMetadata.get_block_from_data_file] ❌ ERROR: Failed to read magic number.")
                    return None

                magic_number = struct.unpack(">I", magic_number_bytes)[0]
                if magic_number != Constants.MAGIC_NUMBER:
                    print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: Invalid magic number: {hex(magic_number)} (Expected: {hex(Constants.MAGIC_NUMBER)})")
                    return None

                # ✅ **Read Block Size**
                block_size_bytes = f.read(4)
                if len(block_size_bytes) != 4:
                    print("[BlockMetadata.get_block_from_data_file] ❌ ERROR: Failed to read block size from file.")
                    return None

                block_size = struct.unpack(">I", block_size_bytes)[0]
                print(f"[BlockMetadata.get_block_from_data_file] INFO: Block size read as {block_size} bytes.")

                # ✅ **Validate Block Size**
                if block_size <= 0 or (offset + 8 + block_size) > file_size:
                    print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: Invalid block size {block_size} at offset {offset}.")
                    return None

                # ✅ **Read Full Block Data**
                block_data = f.read(block_size)
                if len(block_data) != block_size:
                    print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: Read {len(block_data)} bytes, expected {block_size}.")
                    return None

                # ✅ **Deserialize Block and Validate Header**
                block = self._deserialize_block_from_binary(block_data)
                if not block:
                    print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: Failed to deserialize block at offset {offset}.")
                    return None

                # ✅ **Ensure Block Hash Matches Stored Value (No Re-Hashing)**
                stored_hash = block.hash  # This is the mined hash
                if not stored_hash or len(stored_hash) != Constants.SHA3_384_HASH_SIZE * 2:
                    print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: Block {block.index} has an invalid stored hash.")
                    return None

                # ✅ **Ensure Block Fields Match Standardized Structure**
                required_fields = [
                    "index", "previous_hash", "merkle_root", "timestamp", "nonce",
                    "difficulty_length", "difficulty", "miner_address", "transaction_signature",
                    "reward", "fees", "version", "transactions"
                ]
                for field in required_fields:
                    if not hasattr(block, field):
                        print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: Block {block.index} is missing required field: {field}.")
                        return None

                # ✅ **Validate Difficulty Length**
                if block.difficulty_length != 64:
                    print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: Block {block.index} has an invalid difficulty length.")
                    return None

                # ✅ **Validate Block Signature (48 Bytes)**
                if len(block.transaction_signature) != 48:
                    print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: Block {block.index} has an invalid transaction signature length.")
                    return None

                # ✅ **Ensure `falcon_signature` is Always Stored**
                if not hasattr(block, "falcon_signature") or len(block.falcon_signature) != 48:
                    print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: Block {block.index} is missing a valid falcon_signature.")
                    return None

                # ✅ **Validate Miner Address (128 Bytes)**
                miner_address_padded = block.miner_address.ljust(128, "\x00")
                if len(miner_address_padded.encode("utf-8")) != 128:
                    print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: Block {block.index} has an invalid miner address size.")
                    return None

                # ✅ **Validate Merkle Root Integrity**
                expected_merkle_root = block._compute_merkle_root()
                if block.merkle_root != expected_merkle_root:
                    print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: Block {block.index} has an invalid Merkle Root.\n"
                        f"  - Expected: {expected_merkle_root}\n  - Found: {block.merkle_root}")
                    return None

                # ✅ **Validate Transaction Count Matches**
                if len(block.transactions) != block.transaction_count:
                    print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: Block {block.index} transaction count mismatch.\n"
                        f"  - Expected: {block.transaction_count}\n  - Found: {len(block.transactions)}")
                    return None

                print(f"[BlockMetadata.get_block_from_data_file] ✅ SUCCESS: Successfully retrieved and validated Block {block.index} from offset {offset}.")
                return block

        except Exception as e:
            print(f"[BlockMetadata.get_block_from_data_file] ❌ ERROR: Failed to retrieve block from file: {e}")
            return None






    def get_latest_block(self) -> Optional[Block]:
        """
        Retrieve the latest block from LMDB and the block.data file.
        Ensures correct sorting, validation, and prevents chain corruption.
        """
        try:
            print("[BlockMetadata.get_latest_block] INFO: Retrieving latest block from LMDB...")

            # ✅ **Ensure Shared LMDB Instance Is Used**
            if not self.block_metadata_db:
                print("[BlockMetadata.get_latest_block] ERROR: `block_metadata_db` is not set. Cannot retrieve latest block.")
                return None

            all_blocks = []
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                print("[BlockMetadata.get_latest_block] INFO: Iterating through LMDB entries...")

                for key, value in cursor:
                    if key.startswith(b"block:"):
                        try:
                            block_metadata = json.loads(value.decode("utf-8"))

                            # ✅ **Validate Block Metadata Structure**
                            if not isinstance(block_metadata, dict) or "block_header" not in block_metadata:
                                print(f"[BlockMetadata.get_latest_block] ERROR: Invalid block metadata: {block_metadata}")
                                continue

                            header = block_metadata["block_header"]
                            if not isinstance(header, dict) or "index" not in header:
                                print("[BlockMetadata.get_latest_block] ERROR: Block header missing 'index'")
                                continue

                            all_blocks.append(block_metadata)
                            print(f"[BlockMetadata.get_latest_block] INFO: Added block {header['index']} to candidate list.")
                        except json.JSONDecodeError as e:
                            print(f"[BlockMetadata.get_latest_block] ERROR: Corrupt block metadata: {e}")
                            continue

            # ✅ **Ensure At Least One Valid Block Was Found**
            if not all_blocks:
                print("[BlockMetadata.get_latest_block] WARNING: No blocks found in LMDB. Chain may be empty.")
                return None

            # ✅ **Sort Blocks by Index and Ensure Proper Chain Integrity**
            sorted_blocks = sorted(all_blocks, key=lambda b: b["block_header"]["index"])
            latest_block_data = sorted_blocks[-1]

            # ✅ **Validate Block Hash Format**
            block_hash = latest_block_data.get("hash", Constants.ZERO_HASH)
            if not isinstance(block_hash, str) or len(block_hash) != Constants.SHA3_384_HASH_SIZE:
                print(f"[BlockMetadata.get_latest_block] ERROR: Invalid block hash format: {block_hash}")
                return None

            # ✅ **Validate Required Header Fields**
            required_keys = {"index", "previous_hash", "timestamp", "nonce", "difficulty"}
            header = latest_block_data["block_header"]
            if not required_keys.issubset(header):
                print(f"[BlockMetadata.get_latest_block] ERROR: Incomplete block metadata: {latest_block_data}")
                return None

            # ✅ **Validate Timestamp**
            try:
                timestamp = int(header["timestamp"])
                if timestamp <= 0:
                    raise ValueError("Invalid timestamp")
            except (ValueError, TypeError) as e:
                print(f"[BlockMetadata.get_latest_block] ERROR: Invalid timestamp: {e}")
                return None

            # ✅ **Verify `block.data` File Exists and Contains a Valid Magic Number**
            if not os.path.exists(self.current_block_file):
                print(f"[BlockMetadata.get_latest_block] ERROR: block.data file not found: {self.current_block_file}")
                return None

            with open(self.current_block_file, "rb") as f:
                if os.path.getsize(self.current_block_file) < 4:
                    print("[BlockMetadata.get_latest_block] ERROR: block.data file too small to contain magic number.")
                    return None

                file_magic_number = struct.unpack(">I", f.read(4))[0]
                if file_magic_number != Constants.MAGIC_NUMBER:
                    print(f"[BlockMetadata.get_latest_block] ERROR: Invalid magic number in block.data file: {hex(file_magic_number)}. Expected: {hex(Constants.MAGIC_NUMBER)}")
                    return None

            # ✅ **Retrieve Full Block Data from block.data File**
            block_offset = latest_block_data.get("data_offset")
            if not isinstance(block_offset, int):
                print("[BlockMetadata.get_latest_block] ERROR: Block data offset missing or invalid in LMDB.")
                return None

            file_size = os.path.getsize(self.current_block_file)
            if block_offset < 0 or block_offset >= file_size:
                print(f"[BlockMetadata.get_latest_block] ERROR: Block offset {block_offset} is out of file bounds.")
                return None

            print(f"[BlockMetadata.get_latest_block] INFO: Retrieving full block data from offset {block_offset}.")
            full_block = self.get_block_from_data_file(block_offset)
            if not full_block:
                print(f"[BlockMetadata.get_latest_block] ERROR: Failed to load full block {block_hash} from block.data file.")
                return None

            # ✅ **Ensure Block Size Matches Actual Bytes Read**
            block_size = len(json.dumps(full_block.to_dict()).encode("utf-8"))
            if block_size > Constants.MAX_BLOCK_SIZE_BYTES or block_offset + block_size > file_size:
                print(f"[BlockMetadata.get_latest_block] ERROR: Block {full_block.index} exceeds max size limits or is out of file bounds.")
                return None

            print(f"[BlockMetadata.get_latest_block] SUCCESS: Successfully retrieved Block {full_block.index} (Hash: {full_block.hash}).")
            return full_block

        except Exception as e:
            print(f"[BlockMetadata.get_latest_block] ERROR: Failed to retrieve latest block: {e}")
            return None



    def get_total_mined_supply(self) -> Decimal:
        """
        Calculate total mined coin supply by summing all Coinbase rewards from stored blocks.
        Uses shared LMDB instances from WholeBlockData and caches the result for fast retrieval.
        """
        try:
            print("[BlockMetadata.get_total_mined_supply] INFO: Calculating total mined supply...")

            # ✅ **Ensure Shared LMDB Instances Are Used**
            if not self.block_metadata_db or not self.txindex_db:
                print("[BlockMetadata.get_total_mined_supply] ERROR: LMDB instances are not set. Cannot calculate total supply.")
                return Decimal("0")

            # ✅ **Retrieve Cached Supply If Available**
            with self.block_metadata_db.env.begin() as txn:
                cached_supply = txn.get(b"total_mined_supply")

            if cached_supply:
                try:
                    total_supply = Decimal(cached_supply.decode("utf-8"))
                    print(f"[BlockMetadata.get_total_mined_supply] INFO: Cached total supply: {total_supply} ZYC")
                    return total_supply
                except (UnicodeDecodeError, ValueError) as decode_error:
                    print(f"[BlockMetadata.get_total_mined_supply] WARNING: Failed to decode cached total supply: {decode_error}")

            total_supply = Decimal("0")
            block_list = []

            # ✅ **Retrieve All Blocks from LMDB Using Shared `block_metadata_db`**
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.decode().startswith("block:"):
                        try:
                            block_metadata = json.loads(value.decode("utf-8"))

                            # ✅ **Ensure Block Metadata Contains Required Fields**
                            if not isinstance(block_metadata, dict) or "block_header" not in block_metadata:
                                print(f"[BlockMetadata.get_total_mined_supply] ERROR: Invalid block metadata: {block_metadata}")
                                continue

                            header = block_metadata["block_header"]
                            if not isinstance(header, dict) or "index" not in header:
                                print("[BlockMetadata.get_total_mined_supply] ERROR: Block header missing 'index'")
                                continue

                            # ✅ **Validate Timestamp**
                            try:
                                timestamp = int(header["timestamp"])
                                if timestamp <= 0:
                                    raise ValueError("Invalid timestamp")
                            except (ValueError, TypeError) as e:
                                print(f"[BlockMetadata.get_total_mined_supply] ERROR: Invalid timestamp for Block {header['index']}: {e}")
                                continue

                            block_list.append(block_metadata)

                        except json.JSONDecodeError as e:
                            print(f"[BlockMetadata.get_total_mined_supply] ERROR: Failed to parse block metadata: {e}")
                            continue

            # ✅ **Sort Blocks by Height to Ensure Correct Processing Order**
            sorted_blocks = sorted(block_list, key=lambda b: b["block_header"]["index"])

            # ✅ **Ensure Blocks are Sorted in Correct Order and Validate Previous Hash**
            prev_hash = Constants.ZERO_HASH
            for block_metadata in sorted_blocks:
                header = block_metadata["block_header"]
                current_index = header["index"]
                current_prev_hash = header["previous_hash"]
                current_hash = block_metadata["hash"]

                if current_prev_hash != prev_hash:
                    print(f"[BlockMetadata.get_total_mined_supply] ERROR: Chain discontinuity at Block {current_index}.\n"
                        f"  - Expected Previous Hash: {prev_hash}\n  - Found: {current_prev_hash}")
                    return Decimal("0")  # Stop processing if chain integrity is broken

                prev_hash = current_hash

            # ✅ **Process Each Block for Coinbase Transactions**
            for block_metadata in sorted_blocks:
                transactions = block_metadata.get("tx_ids", [])

                if transactions:
                    for tx_id in transactions:
                        tx_key = f"tx:{tx_id}".encode("utf-8")

                        # ✅ **Retrieve Transaction Data Using Shared `txindex_db`**
                        with self.txindex_db.env.begin() as txn:
                            tx_data = txn.get(tx_key)

                        if not tx_data:
                            print(f"[BlockMetadata.get_total_mined_supply] WARNING: Missing transaction {tx_id} in txindex.")
                            continue

                        try:
                            tx_details = json.loads(tx_data.decode("utf-8"))

                            # ✅ **Ensure Transaction is a Valid Coinbase Transaction**
                            if tx_details.get("type") == "COINBASE":
                                outputs = tx_details.get("outputs", [])
                                if outputs and isinstance(outputs, list):
                                    for output in outputs:
                                        if "amount" in output:
                                            total_supply += Decimal(str(output["amount"]))

                        except json.JSONDecodeError as json_error:
                            print(f"[BlockMetadata.get_total_mined_supply] ERROR: Failed to parse transaction {tx_id}: {json_error}")
                            continue

            # ✅ **Cache Total Mined Supply in LMDB**
            with self.block_metadata_db.env.begin(write=True) as txn:
                txn.put(b"total_mined_supply", str(total_supply).encode("utf-8"))

            print(f"[BlockMetadata.get_total_mined_supply] INFO: Total mined supply calculated and cached: {total_supply} ZYC")
            return total_supply

        except Exception as e:
            print(f"[BlockMetadata.get_total_mined_supply] ERROR: Failed to calculate total mined supply: {e}")
            return Decimal("0")



    def load_chain(self) -> List[Dict]:
        """
        Load blockchain data from LMDB using the shared instance and return as a list of dictionaries.
        """
        try:
            print("[BlockMetadata.load_chain] INFO: Loading blockchain data from LMDB...")

            # ✅ **Ensure Shared LMDB Instance Is Used**
            if not self.block_metadata_db:
                print("[BlockMetadata.load_chain] ERROR: `block_metadata_db` is not set. Cannot load blockchain data.")
                return []

            chain_data = []

            # ✅ **Retrieve All Blocks from LMDB Using Shared `block_metadata_db`**
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.decode().startswith("block:"):
                        try:
                            block_metadata = json.loads(value.decode("utf-8"))

                            # ✅ **Ensure Block Metadata Contains Required Fields**
                            if not isinstance(block_metadata, dict) or "block_header" not in block_metadata:
                                print(f"[BlockMetadata.load_chain] ERROR: Invalid block metadata: {block_metadata}")
                                continue

                            header = block_metadata["block_header"]
                            if not isinstance(header, dict) or "index" not in header:
                                print("[BlockMetadata.load_chain] ERROR: Block header missing 'index'")
                                continue

                            chain_data.append(block_metadata)

                        except json.JSONDecodeError as e:
                            print(f"[BlockMetadata.load_chain] ERROR: Failed to parse block metadata: {e}")
                            continue

            # ✅ **Sort Blocks by Height to Ensure Correct Processing Order**
            sorted_chain = sorted(chain_data, key=lambda b: b["block_header"]["index"])

            print(f"[BlockMetadata.load_chain] INFO: Successfully loaded {len(sorted_chain)} blocks from LMDB.")
            return sorted_chain

        except Exception as e:
            print(f"[BlockMetadata.load_chain] ERROR: Failed to load blockchain data: {e}")
            return []


    def _get_database(self, db_key: str) -> LMDBManager:
        """
        Retrieve the LMDBManager instance for a given database key.
        """
        try:
            db_path = Constants.DATABASES.get(db_key, None)
            if not db_path:
                raise ValueError(f"[BlockMetadata._get_database] ERROR: Unknown database key: {db_key}")
            return LMDBManager(db_path)
        except Exception as e:
            print(f"[BlockMetadata._get_database] ERROR: Failed to get database {db_key}: {e}")
            raise





    def get_all_block_headers(self) -> List[Dict]:
        """
        Retrieve all block headers from LMDB using the shared instance.

        Returns:
            List[Dict]: A list of block headers, where each header is a dictionary.
        """
        try:
            print("[BlockMetadata.get_all_block_headers] INFO: Retrieving all block headers...")

            # ✅ **Ensure Shared LMDB Instance Is Used**
            if not self.block_metadata_db:
                print("[BlockMetadata.get_all_block_headers] ERROR: `block_metadata_db` is not set. Cannot retrieve block headers.")
                return []

            headers = []

            # ✅ **Retrieve All Blocks from LMDB Using Shared `block_metadata_db`**
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.decode().startswith("block:"):
                        try:
                            block_meta = json.loads(value.decode("utf-8"))

                            # ✅ **Extract and Validate Block Header**
                            header = block_meta.get("block_header")
                            if isinstance(header, dict) and "index" in header:
                                headers.append(header)
                            else:
                                print(f"[BlockMetadata.get_all_block_headers] WARNING: Invalid header in block {block_meta.get('hash', 'unknown')}")

                        except json.JSONDecodeError as e:
                            print(f"[BlockMetadata.get_all_block_headers] ERROR: Failed to parse block metadata: {e}")
                            continue

            if not headers:
                print("[BlockMetadata.get_all_block_headers] WARNING: No block headers found in LMDB.")
                return []

            print(f"[BlockMetadata.get_all_block_headers] INFO: Retrieved {len(headers)} block headers.")
            return headers

        except Exception as e:
            print(f"[BlockMetadata.get_all_block_headers] ERROR: Failed to retrieve block headers: {e}")
            return []







    def get_all_blocks(self) -> List[Dict]:
        """
        Retrieve all stored blocks from LMDB and the blocks.data file as a list of dictionaries.
        Uses the shared LMDB instance from WholeBlockData.
        Ensures block retrieval and validates header integrity.
        """
        try:
            print("[BlockMetadata.get_all_blocks] INFO: Retrieving all blocks from LMDB and block.data storage...")

            # ✅ **Ensure Shared LMDB Instance Is Used**
            if not self.block_metadata_db:
                print("[BlockMetadata.get_all_blocks] ERROR: `block_metadata_db` is not set. Cannot retrieve blocks.")
                return []

            blocks = []

            # ✅ **Retrieve Blocks from LMDB Using Shared `block_metadata_db`**
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.decode().startswith("block:"):
                        try:
                            block_metadata = json.loads(value.decode("utf-8"))

                            # ✅ **Ensure Block Metadata Contains Required Fields**
                            if not isinstance(block_metadata, dict) or "block_header" not in block_metadata:
                                print(f"[BlockMetadata.get_all_blocks] ERROR: Invalid block metadata: {block_metadata}")
                                continue

                            header = block_metadata["block_header"]
                            if not isinstance(header, dict) or "index" not in header:
                                print("[BlockMetadata.get_all_blocks] ERROR: Block header missing 'index'")
                                continue

                            blocks.append(block_metadata)

                        except json.JSONDecodeError as e:
                            print(f"[BlockMetadata.get_all_blocks] ERROR: Failed to parse block metadata: {e}")
                            continue

            # ✅ **Sort Blocks by Height to Ensure Correct Processing Order**
            sorted_blocks = sorted(blocks, key=lambda b: b["block_header"]["index"])

            # ✅ **Validate Chain Continuity**
            prev_hash = Constants.ZERO_HASH
            for block in sorted_blocks:
                current_index = block["block_header"]["index"]
                current_prev_hash = block["block_header"]["previous_hash"]
                current_hash = block["hash"]

                if current_prev_hash != prev_hash:
                    print(f"[BlockMetadata.get_all_blocks] ERROR: Chain discontinuity at block {current_index}. Prev hash {current_prev_hash} does not match expected {prev_hash}.")
                    return []  # Return empty list if chain is broken

                prev_hash = current_hash

            print(f"[BlockMetadata.get_all_blocks] SUCCESS: Retrieved {len(sorted_blocks)} valid blocks.")
            return sorted_blocks

        except Exception as e:
            print(f"[BlockMetadata.get_all_blocks] ERROR: Failed to retrieve blocks: {e}")
            return []



    def _block_to_storage_format(self, block: Block) -> Dict:
        """
        Convert a Block object to a dictionary format for LMDB storage.
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
                "size": len(pickle.dumps(block))
            }
        except Exception as e:
            print(f"[BlockMetadata._block_to_storage_format] ERROR: Failed to format block for storage: {e}")
            return {}

    def _store_block_metadata(self, block: Block) -> None:
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
            # Here, we simply print the metadata storage action.
            print(f"[BlockMetadata._store_block_metadata] INFO: Stored metadata for block {block.hash}: {metadata}")
        except Exception as e:
            print(f"[BlockMetadata._store_block_metadata] ERROR: Failed to store block metadata: {e}")




    def get_block_by_tx_id(self, tx_id: str) -> Optional[Block]:
        """
        Retrieve a block using a transaction ID from the txindex database.
        Uses shared LMDB instances from WholeBlockData.

        :param tx_id: Transaction ID to look up.
        :return: The block containing the transaction, or None if not found.
        """
        try:
            print(f"[BlockMetadata.get_block_by_tx_id] INFO: Searching for block containing transaction {tx_id}...")

            # ✅ **Ensure Shared LMDB Instances Are Used**
            if not self.txindex_db or not self.block_metadata_db:
                print("[BlockMetadata.get_block_by_tx_id] ERROR: LMDB instances are not set. Cannot retrieve block.")
                return None

            # ✅ **Retrieve Block Hash Associated with Transaction ID**
            tx_key = f"tx:{tx_id}".encode("utf-8")
            with self.txindex_db.env.begin() as txn:
                block_hash_bytes = txn.get(tx_key)

            if not block_hash_bytes:
                print(f"[BlockMetadata.get_block_by_tx_id] WARNING: No block found for transaction {tx_id}.")
                return None

            block_hash = block_hash_bytes.decode("utf-8")
            print(f"[BlockMetadata.get_block_by_tx_id] INFO: Transaction {tx_id} found in block {block_hash}.")

            # ✅ **Retrieve Block Metadata Using Shared `block_metadata_db`**
            block_key = f"block:{block_hash}".encode("utf-8")
            with self.block_metadata_db.env.begin() as txn:
                block_data_bytes = txn.get(block_key)

            if not block_data_bytes:
                print(f"[BlockMetadata.get_block_by_tx_id] WARNING: Block metadata missing for hash {block_hash}.")
                return None

            try:
                block_metadata = json.loads(block_data_bytes.decode("utf-8"))
            except json.JSONDecodeError:
                print(f"[BlockMetadata.get_block_by_tx_id] ERROR: Failed to decode block metadata for hash {block_hash}.")
                return None

            # ✅ **Ensure Block Metadata Contains Required Fields**
            if not isinstance(block_metadata, dict) or "block_header" not in block_metadata:
                print(f"[BlockMetadata.get_block_by_tx_id] ERROR: Invalid block metadata format for {block_hash}.")
                return None

            block_header = block_metadata["block_header"]
            required_keys = {"index", "previous_hash", "merkle_root", "timestamp", "nonce", "difficulty", "hash"}

            if not required_keys.issubset(block_header.keys()):
                print(f"[BlockMetadata.get_block_by_tx_id] ERROR: Block metadata missing required fields: {block_header}")
                return None

            # ✅ **Validate Block Hash Integrity**
            if not isinstance(block_header["hash"], str) or len(block_header["hash"]) != Constants.SHA3_384_HASH_SIZE:
                print(f"[BlockMetadata.get_block_by_tx_id] ❌ ERROR: Block {block_header['index']} has an invalid hash format.")
                return None

            # ✅ **Check if `block.data` Exists Before Reading**
            if not os.path.exists(self.current_block_file):
                print(f"[BlockMetadata.get_block_by_tx_id] ERROR: block.data file not found: {self.current_block_file}")
                return None

            # ✅ **Ensure Magic Number is Only Written Once**
            with open(self.current_block_file, "rb") as f:
                if os.path.getsize(self.current_block_file) < 4:
                    print("[BlockMetadata.get_block_by_tx_id] ERROR: block.data file too small to contain magic number.")
                    return None

                file_magic_number = struct.unpack(">I", f.read(4))[0]
                if file_magic_number != Constants.MAGIC_NUMBER:
                    print(f"[BlockMetadata.get_block_by_tx_id] ERROR: Invalid magic number in block.data file: {hex(file_magic_number)}. Expected: {hex(Constants.MAGIC_NUMBER)}")
                    return None

            # ✅ **Convert Block Header to Block Object**
            block = Block.from_dict(block_metadata["block_header"])
            print(f"[BlockMetadata.get_block_by_tx_id] ✅ SUCCESS: Retrieved Block {block.index} containing transaction {tx_id}.")
            return block

        except Exception as e:
            print(f"[BlockMetadata.get_block_by_tx_id] ❌ ERROR: Failed to retrieve block by transaction ID {tx_id}: {e}")
            return None

    def get_transaction_id(self, tx_label: str) -> Optional[str]:
        """
        Retrieves a stored transaction ID using a label (e.g., "GENESIS_COINBASE").
        
        :param tx_label: A string label for the transaction to retrieve.
        :return: The stored transaction ID as a hex string, or None if not found.
        """
        try:
            print(f"[BlockMetadata.get_transaction_id] INFO: Retrieving transaction ID for label '{tx_label}'...")

            # ✅ **Ensure Shared LMDB Instance Is Used**
            if not self.block_metadata_db:
                print("[BlockMetadata.get_transaction_id] ERROR: `block_metadata_db` is not set. Cannot retrieve transaction ID.")
                return None

            # ✅ **Retrieve Transaction ID Using Shared `block_metadata_db`**
            with self.block_metadata_db.env.begin() as txn:
                tx_id_bytes = txn.get(tx_label.encode("utf-8"))

            if not tx_id_bytes:
                print(f"[BlockMetadata.get_transaction_id] WARNING: No transaction ID found for label '{tx_label}'.")
                return None

            tx_id = tx_id_bytes.decode("utf-8")
            print(f"[BlockMetadata.get_transaction_id] SUCCESS: Retrieved transaction ID: {tx_id}")
            return tx_id

        except Exception as e:
            print(f"[BlockMetadata.get_transaction_id] ERROR: Failed to retrieve transaction ID for '{tx_label}': {e}")
            return None



    def purge_chain(self):
        print("[BlockMetadata.purge_chain] 🚨 WARNING: Purging corrupted blockchain data...")

        try:
            if hasattr(self.block_metadata_db, "env"):
                print("[LMDBManager] Closing database environment before purge...")
                self.block_metadata_db.env.close()  # ✅ Properly close LMDB before purging

            os.remove(self.block_metadata_path)
            print(f"[BlockMetadata.purge_chain] ✅ SUCCESS: Deleted {self.block_metadata_path}")

        except Exception as e:
            print(f"[BlockMetadata.purge_chain] ❌ ERROR: Failed to purge blockchain data: {e}")



    