import os
import sys
import struct
import json
import pickle
import time
from decimal import Decimal
from typing import Optional, List, Dict

# Ensure module path is set correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.storage.blockmetadata import BlockMetadata
from Zyiron_Chain.storage.tx_storage import TxStorage
import struct
import os
from threading import Lock

import struct
from threading import Lock

class WholeBlockData:
    """
    WholeBlockData manages block storage and metadata using LMDB and block.data files.
    """

    def __init__(self, tx_storage: TxStorage):
        """
        Initializes WholeBlockData with LMDB databases and ensures TxStorage is passed.
        """
        try:
            print("[WholeBlockData.__init__] INFO: Initializing block storage...")

            if not tx_storage:
                raise ValueError("[WholeBlockData.__init__] ❌ ERROR: TxStorage instance is required.")

            # ✅ **Store TxStorage reference**
            self.tx_storage = tx_storage  

            # ✅ **Initialize LMDB databases for block metadata and transaction indexing**
            self.block_metadata_db = LMDBManager(Constants.DATABASES["block_metadata"])
            self.txindex_db = LMDBManager(Constants.DATABASES["txindex"])

            # ✅ **Thread safety lock for writing**
            self.write_lock = Lock()

            # ✅ **Set up the blockchain storage directory & block.data file**
            self._setup_block_storage()

            # ✅ **Pass shared instances to BlockMetadata**
            self.block_metadata = BlockMetadata(
                block_metadata_db=self.block_metadata_db,
                txindex_db=self.txindex_db,
                tx_storage=self.tx_storage,
                current_block_file=self.current_block_file
            )

            print("[WholeBlockData.__init__] ✅ SUCCESS: Block storage initialized successfully.")

        except Exception as e:
            print(f"[WholeBlockData.__init__] ❌ ERROR: Failed to initialize block storage: {e}")
            raise

    def store_block_securely(self, block):
        """
        Store block with thread safety to prevent corruption.
        Uses `write_lock` to ensure that only one thread writes at a time.
        """
        with self.write_lock:  # ✅ Prevents concurrent writes
            self._write_to_block_data_securely(block)


    def validate_block_data_file(self) -> bool:
        """
        Validates the block.data file by:
          - Checking the magic number.
          - Reading the block size.
          - Ensuring that the block data is complete.
        
        :return: True if the file is valid; False otherwise.
        """
        try:
            with open(self.current_block_file, "rb") as f:
                # Read the magic number (first 4 bytes)
                magic_number = f.read(4)
                if magic_number != struct.pack(">I", Constants.MAGIC_NUMBER):
                    print(f"[WholeBlockData.validate_block_data_file] ERROR: Invalid magic number in block.data: {magic_number.hex()}")
                    return False

                # Read block size (next 4 bytes)
                block_size_bytes = f.read(4)
                if len(block_size_bytes) != 4:
                    print("[WholeBlockData.validate_block_data_file] ERROR: Failed to read block size from block.data.")
                    return False

                block_size = struct.unpack(">I", block_size_bytes)[0]
                print(f"[WholeBlockData.validate_block_data_file] INFO: Block size: {block_size} bytes.")

                # Read the block data based on the block size
                block_data = f.read(block_size)
                if len(block_data) != block_size:
                    print(f"[WholeBlockData.validate_block_data_file] ERROR: Incomplete block data. Expected {block_size} bytes, got {len(block_data)}.")
                    return False

                print("[WholeBlockData.validate_block_data_file] INFO: block.data file is valid.")
                return True

        except Exception as e:
            print(f"[WholeBlockData.validate_block_data_file] ERROR: Failed to validate block.data file: {e}")
            return False

    

    def _setup_block_storage(self):
        """
        Ensures the blockchain storage directory exists and initializes block.data.
        """
        try:
            blockchain_storage_dir = os.path.join(os.getcwd(), "blockchain_storage")
            block_data_dir = os.path.join(blockchain_storage_dir, "block_data")
            os.makedirs(block_data_dir, exist_ok=True)  # ✅ Ensure directory exists

            # ✅ **Set up block.data file paths**
            self.current_block_file = os.path.join(block_data_dir, "block.data")

            # ✅ **Initialize block data file if necessary**
            self._initialize_block_data_file()

        except Exception as e:
            print(f"[WholeBlockData._setup_block_storage] ❌ ERROR: Failed to initialize block storage directory: {e}")
            raise

    def _write_to_block_data_securely(self, block):
        """Serialize and write block data to block.data file securely."""
        try:
            # ✅ **Ensure BlockMetadata Uses the Same File Path**
            if self.block_metadata:
                self.block_metadata.current_block_file = self.current_block_file
                print("[WholeBlockData._write_to_block_data_securely] INFO: BlockMetadata now using the same block.data file path.")

            with open(self.current_block_file, "ab") as f:
                offset_before_write = f.tell()
                serialized_block = self._serialize_block_to_binary(block)

                # ✅ Store block size as 4-byte integer (max 4GB)
                block_size_bytes = struct.pack(">I", len(serialized_block))

                f.write(block_size_bytes + serialized_block)
                f.flush()

                print(f"[WholeBlockData._write_to_block_data_securely] SUCCESS: Block {block.index} securely stored at offset {offset_before_write}.")

        except Exception as e:
            print(f"[WholeBlockData._write_to_block_data_securely] ERROR: Failed to store block {block.index}: {e}")


    def block_meta(self):
        """
        Ensures `BlockMetadata` is initialized and returns the instance.
        ✅ Reuses shared LMDB instances (`block_metadata_db` & `txindex_db`) instead of reinitializing.
        ✅ Ensures `tx_storage` is available before proceeding.
        """
        try:
            # ✅ **Ensure `block_metadata` is Properly Initialized**
            if not hasattr(self, "block_metadata") or self.block_metadata is None:
                print("[WholeBlockData.block_meta] WARNING: `block_metadata` is missing. Initializing now...")

                # ✅ **Ensure Required Dependencies Exist Before Initialization**
                missing_components = []
                if not hasattr(self, "tx_storage") or self.tx_storage is None:
                    missing_components.append("tx_storage")
                if not hasattr(self, "block_metadata_db") or self.block_metadata_db is None:
                    missing_components.append("block_metadata_db")
                if not hasattr(self, "txindex_db") or self.txindex_db is None:
                    missing_components.append("txindex_db")

                if missing_components:
                    print(f"[WholeBlockData.block_meta] ERROR: Missing dependencies ({', '.join(missing_components)}). Cannot initialize BlockMetadata.")
                    return None

                # ✅ **Initialize BlockMetadata with Shared LMDB Instances**
                self.block_metadata = BlockMetadata(
                    block_metadata_db=self.block_metadata_db, 
                    txindex_db=self.txindex_db, 
                    tx_storage=self.tx_storage
                )
                print("[WholeBlockData.block_meta] ✅ SUCCESS: `BlockMetadata` initialized with shared LMDB instances.")

            return self.block_metadata  # ✅ **Always Return the `BlockMetadata` Instance**

        except Exception as e:
            print(f"[WholeBlockData.block_meta] ❌ ERROR: Failed to initialize BlockMetadata: {e}")
            return None  # ✅ Prevents crashes by returning `None` in case of failure





    def store_block(self, block: Block, difficulty: int):
        """
        Stores a block in `block.data`, ensuring:
        - Blocks are appended **AFTER** the magic number.
        - Block size is validated (0MB - 10MB).
        - Block metadata is stored correctly.
        - No redundant magic numbers are written.

        :param block: The block to store.
        :param difficulty: The difficulty target of the block.
        """
        try:
            print(f"[WholeBlockData.store_block] INFO: Storing Block {block.index} with difficulty {difficulty}.")

            # ✅ **Ensure `BlockMetadata` Uses the Shared Instance**
            if not self.block_metadata:
                print("[WholeBlockData.store_block] ERROR: `block_metadata` is not initialized. Cannot store block.")
                return

            # ✅ **Serialize Block Before Writing**
            block_bytes = self._serialize_block_to_binary(block)

            # ✅ **Verify Block Size Before Writing**
            block_size = len(block_bytes)
            if block_size == 0:
                print(f"[WholeBlockData.store_block] ERROR: Block {block.index} has invalid size (0 bytes). Skipping storage.")
                return

            if block_size > Constants.MAX_BLOCK_SIZE_BYTES:
                print(f"[WholeBlockData.store_block] ERROR: Block {block.index} exceeds max size ({block_size} bytes). Skipping storage.")
                return

            print(f"[WholeBlockData.store_block] INFO: Block {block.index} size verified: {block_size} bytes.")

            # ✅ **Append Block to `block.data` Correctly**
            with open(self.current_block_file, "ab") as f:
                offset_before_write = f.tell()

                # ✅ **Ensure Magic Number is Written Only Once**
                if offset_before_write == 0:
                    f.write(struct.pack(">I", Constants.MAGIC_NUMBER))
                    print(f"[WholeBlockData.store_block] INFO: Magic number {hex(Constants.MAGIC_NUMBER)} written to block.data.")

                # ✅ **Store Block Size + Block Data**
                block_size_bytes = struct.pack(">I", block_size)
                f.write(block_size_bytes + block_bytes)
                f.flush()

                print(f"[WholeBlockData.store_block] SUCCESS: Block {block.index} stored at offset {offset_before_write}.")

            # ✅ **Store Block Metadata Using the Existing Instance**
            self.block_metadata.store_block(block, difficulty)
            print(f"[WholeBlockData.store_block] SUCCESS: Block {block.index} fully stored and indexed.")

        except Exception as e:
            print(f"[WholeBlockData.store_block] ERROR: Failed to store block {block.index}: {e}")
            raise





    def _initialize_block_data_file(self):
        """
        Initialize `block.data` file with the correct magic number if missing, and ensure correct offset handling.
        """
        try:
            print(f"[WholeBlockData._initialize_block_data_file] INFO: Block data file path set to: {self.current_block_file}")

            # ✅ **Ensure Block Data Directory Exists**
            block_data_dir = os.path.dirname(self.current_block_file)
            if not block_data_dir:
                print("[WholeBlockData._initialize_block_data_file] ❌ ERROR: Block data directory not found.")
                return
            os.makedirs(block_data_dir, exist_ok=True)

            # ✅ **Check if File Exists and is Empty**
            file_exists = os.path.exists(self.current_block_file)
            file_is_empty = os.path.getsize(self.current_block_file) == 0 if file_exists else True

            # ✅ **Write Magic Number Only if File is Missing or Empty**
            if not file_exists or file_is_empty:
                with open(self.current_block_file, "wb") as f:
                    f.write(struct.pack(">I", Constants.MAGIC_NUMBER))  # ✅ Write magic number
                print(f"[WholeBlockData._initialize_block_data_file] ✅ INFO: Created block.data with magic number {hex(Constants.MAGIC_NUMBER)}.")
            else:
                print("[WholeBlockData._initialize_block_data_file] INFO: block.data file exists. Skipping magic number rewrite.")

            # ✅ **Validate Magic Number in Existing File**
            with open(self.current_block_file, "rb") as f:
                file_magic_number = struct.unpack(">I", f.read(4))[0]

            if file_magic_number != Constants.MAGIC_NUMBER:
                print(f"[WholeBlockData._initialize_block_data_file] ❌ ERROR: Invalid magic number in block.data file: {hex(file_magic_number)} "
                    f"(Expected: {hex(Constants.MAGIC_NUMBER)}).")
                print("[WholeBlockData._initialize_block_data_file] ❌ WARNING: Storage corruption detected. Manual intervention required!")
                return

            print(f"[WholeBlockData._initialize_block_data_file] ✅ SUCCESS: Block storage validated at {self.current_block_file}.")

        except Exception as e:
            print(f"[WholeBlockData._initialize_block_data_file] ❌ ERROR: Failed to initialize block storage: {e}")
            raise










    def create_block_data_file(self, block: Block):
        """
        Append a block to the block.data file in binary format.
        Writes the block length (4 bytes) followed by the serialized block.
        """
        try:
            if not self.current_block_file:
                raise ValueError("[WholeBlockData.create_block_data_file] ERROR: Current block file is not set.")

            with open(self.current_block_file, "ab+") as f:
                f.seek(0, os.SEEK_END)

                # ✅ Ensure magic number is written only once at file creation
                if f.tell() == 0:
                    f.write(struct.pack(">I", Constants.MAGIC_NUMBER))
                    print(f"[WholeBlockData] INFO: Wrote network magic number {hex(Constants.MAGIC_NUMBER)} to block.data.")

                # ✅ Serialize block data correctly
                block_data = self._serialize_block_to_binary(block)
                block_size_bytes = struct.pack(">I", len(block_data))  # ✅ Store block length separately

                # ✅ Append block in correct [size][block] format
                f.write(block_size_bytes + block_data)
                self.current_block_offset = f.tell()

                print(f"[WholeBlockData] SUCCESS: Appended Block {block.index} to block.data file at offset {self.current_block_offset}.")

        except Exception as e:
            print(f"[WholeBlockData.create_block_data_file] ERROR: Failed to write block {block.index} to block.data file: {e}")
            raise


    
    def _deserialize_block_from_binary(self, block_data: bytes) -> Optional[Block]:
        """
        Deserialize binary block data back into a Block object.
        Ensures valid structure, transactions, and header parsing.
        """
        try:
            print("[WholeBlockData] INFO: Starting block deserialization...")

            # ✅ **Define Standardized Header Format**
            header_format = ">I Q 48s 48s 48s Q Q B 64s Q 128s 48s Q Q I"
            base_header_size = struct.calcsize(header_format)
            print(f"[WholeBlockData] INFO: Expected header size: {base_header_size} bytes.")

            # ✅ **Ensure block data contains at least the header size**
            if len(block_data) < base_header_size:
                raise ValueError("Block data too short for header.")

            # ✅ **Unpack standardized header fields**
            (
                magic_number, block_length, block_hash, prev_block_hash, merkle_root,
                block_height, timestamp, difficulty_length, difficulty_bytes, nonce,
                miner_address_bytes, transaction_signature, reward, fees, version
            ) = struct.unpack(header_format, block_data[:base_header_size])

            # ✅ **Check Magic Number**
            if magic_number != Constants.MAGIC_NUMBER:
                raise ValueError(f"Invalid magic number: {hex(magic_number)} (Expected: {hex(Constants.MAGIC_NUMBER)})")

            print(f"[WholeBlockData] INFO: Magic Number Verified: {hex(magic_number)}")
            print(f"[WholeBlockData] INFO: Block Length: {block_length} bytes")
            print(f"[WholeBlockData] INFO: Header unpacked: index={block_height}, timestamp={timestamp}, nonce={nonce}.")
            print(f"[WholeBlockData] INFO: Difficulty: {int.from_bytes(difficulty_bytes, 'big', signed=False)}")
            print(f"[WholeBlockData] INFO: Miner Address: {miner_address_bytes.rstrip(b'\x00').decode('utf-8')}")
            print(f"[WholeBlockData] INFO: Transaction Signature: {transaction_signature.hex()}")
            print(f"[WholeBlockData] INFO: Reward: {reward}, Fees: {fees}, Version: {version}")

            # ✅ **Extract Miner Address (Remove Null Padding)**
            miner_address_str = miner_address_bytes.rstrip(b'\x00').decode("utf-8")

            # ✅ **Extract Difficulty Value**
            difficulty_int = int.from_bytes(difficulty_bytes, "big", signed=False)

            # ✅ **Determine Transaction Count Offset**
            tx_count_offset = base_header_size

            # ✅ **Ensure Transaction Count Field Exists**
            if len(block_data) < tx_count_offset + 4:
                raise ValueError("Block data too short for transaction count.")
            tx_count = struct.unpack(">I", block_data[tx_count_offset:tx_count_offset + 4])[0]
            print(f"[WholeBlockData] INFO: Block {block_height} claims {tx_count} transaction(s).")

            # ✅ **Unpack Transactions (Each Prefixed with 4-Byte Size)**
            tx_data_offset = tx_count_offset + 4
            transactions = []

            for i in range(tx_count):
                print(f"[WholeBlockData] INFO: Processing transaction {i} at offset {tx_data_offset}.")

                # ✅ **Check for transaction size field (4 bytes)**
                if len(block_data) < tx_data_offset + 4:
                    raise ValueError(f"Not enough data to read size of transaction {i} in block {block_height}.")
                
                tx_size = struct.unpack(">I", block_data[tx_data_offset:tx_data_offset + 4])[0]
                tx_data_offset += 4

                print(f"[WholeBlockData] INFO: Transaction {i} size: {tx_size} bytes.")

                # ✅ **Ensure full transaction data is available**
                if len(block_data) < tx_data_offset + tx_size:
                    raise ValueError(f"Incomplete transaction data for transaction {i} in block {block_height}. Expected {tx_size} bytes.")

                tx_bytes = block_data[tx_data_offset:tx_data_offset + tx_size]
                tx_data_offset += tx_size

                try:
                    tx_obj = json.loads(tx_bytes.decode("utf-8"))
                    if "tx_id" not in tx_obj:
                        print(f"[WholeBlockData] ❌ ERROR: Transaction {i} in block {block_height} missing 'tx_id'. Skipping.")
                        continue

                    print(f"[WholeBlockData] INFO: Transaction {i} deserialized successfully with tx_id: {tx_obj.get('tx_id')}.")
                    transactions.append(tx_obj)

                except Exception as e:
                    print(f"[WholeBlockData] ❌ ERROR: Failed to deserialize transaction {i} in block {block_height}: {e}")
                    continue

            # ✅ **Verify Transaction Count Matches Deserialized Transactions**
            if len(transactions) != tx_count:
                raise ValueError(f"Expected {tx_count} transactions, but deserialized {len(transactions)}.")

            # ✅ **Construct Standardized Block Dictionary**
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
                "fees": fees,
                "version": version,
                "transactions": transactions
            }

            print(f"[WholeBlockData] ✅ SUCCESS: Block {block_height} deserialized successfully with {len(transactions)} transaction(s).")
            return Block.from_dict(block_dict)

        except Exception as e:
            print(f"[WholeBlockData] ❌ ERROR: Failed to deserialize block: {e}")
            return None






    def _serialize_block_to_binary(self, block: Block) -> bytes:
        """
        Serialize a Block into binary format.
        Packs header fields, extra metadata (reward, fees, version), and transaction data.
        """
        try:
            print(f"[WholeBlockData] INFO: Serializing Block {block.index} to binary.")

            # Convert block to dictionary and extract header information.
            block_dict = block.to_dict()
            header = block_dict.get("header")
            if header is None:
                raise ValueError("[WholeBlockData] ❌ ERROR: Block header is missing.")
            print("[WholeBlockData] INFO: Block header retrieved successfully.")

            # --- Standardized Fixed Header Fields ---
            block_height = int(header["index"])
            prev_block_hash = bytes.fromhex(header["previous_hash"])
            merkle_root = bytes.fromhex(header["merkle_root"])
            timestamp = int(header["timestamp"])
            nonce = int(header["nonce"])
            print(f"[WholeBlockData] INFO: Fixed header fields - index: {block_height}, timestamp: {timestamp}, nonce: {nonce}.")

            # ✅ **Fix: Convert difficulty from hex properly**
            difficulty_value = int(header["difficulty"], 16)  # Convert from hex string
            difficulty_bytes = difficulty_value.to_bytes(64, "big", signed=False).rjust(64, b'\x00')  # Ensure 64 bytes
            difficulty_length = len(difficulty_bytes)
            difficulty_packed = struct.pack(">B", difficulty_length) + difficulty_bytes
            print(f"[WholeBlockData] INFO: Difficulty processed - length: {difficulty_length} bytes.")

            # ✅ **Fix: Ensure Miner Address is 128 bytes**
            miner_address_str = header["miner_address"]
            miner_address_encoded = miner_address_str.encode("utf-8")
            if len(miner_address_encoded) > 128:
                raise ValueError("[WholeBlockData] ❌ ERROR: Miner address exceeds 128 bytes.")
            miner_address_padded = miner_address_encoded.ljust(128, b'\x00')
            print(f"[WholeBlockData] INFO: Miner address processed and padded.")

            # ✅ **Fix: Ensure Transaction Signature is Always 48 Bytes**
            transaction_signature = bytes.fromhex(header["transaction_signature"]) if "transaction_signature" in header else b"\x00" * 48

            # --- Extra Header Fields ---
            reward = int(float(header.get("reward", "0")))
            fees_collected = int(float(header.get("fees", "0")))

            # ✅ **Fix: Convert block version safely**
            version_raw = header.get("version", "1.0.0")  # Default version if missing
            try:
                block_version = int(float(version_raw))  # Convert '1.0.0' -> 1
            except ValueError:
                print(f"[WholeBlockData] ❌ ERROR: Invalid block version format '{version_raw}', defaulting to 1.")
                block_version = 1  # Fallback to 1 if invalid
            print(f"[WholeBlockData] INFO: Block version processed: {block_version}")

            # ✅ **Fix: Pack the header fields correctly**
            fixed_header_format = ">I48s48sQI B64s 128s 48s Q Q I"
            fixed_header_data = struct.pack(
                fixed_header_format,
                block_height,
                prev_block_hash,
                merkle_root,
                timestamp,
                nonce,
                difficulty_length,
                difficulty_bytes,
                miner_address_padded,
                transaction_signature,
                reward,
                fees_collected,
                block_version
            )
            print(f"[WholeBlockData] INFO: Fixed header packed successfully.")

            # --- Serialize Transactions ---
            serialized_transactions = []
            transactions = block_dict.get("transactions", [])
            print(f"[WholeBlockData] INFO: Serializing {len(transactions)} transaction(s).")

            for idx, tx in enumerate(transactions):
                try:
                    if hasattr(tx, "to_dict"):
                        tx_dict = tx.to_dict()
                    elif isinstance(tx, dict):
                        tx_dict = tx
                    else:
                        raise TypeError(f"Transaction at index {idx} is not serializable.")

                    # ✅ **Fix: Ensure all transactions are JSON-encoded properly**
                    tx_json = json.dumps(tx_dict, ensure_ascii=False, sort_keys=True).encode("utf-8")
                    tx_size = len(tx_json)

                    # ✅ **Prefix each transaction with its size (4 bytes)**
                    serialized_tx = struct.pack(">I", tx_size) + tx_json
                    serialized_transactions.append(serialized_tx)
                    print(f"[WholeBlockData] INFO: Serialized transaction {idx}: size {tx_size} bytes.")
                except Exception as e:
                    print(f"[WholeBlockData] ❌ ERROR: Failed to serialize transaction at index {idx}: {e}")

            # ✅ **Pack Transaction Count (4 bytes) + Transactions (Size-Prefixed)**
            tx_count = len(serialized_transactions)
            tx_count_data = struct.pack(">I", tx_count)
            tx_data = b"".join(serialized_transactions)

            print(f"[WholeBlockData] INFO: {tx_count} transaction(s) serialized.")

            # ✅ **Combine Everything into Final Block Binary Format**
            serialized_block = fixed_header_data + tx_count_data + tx_data
            print(f"[WholeBlockData] ✅ SUCCESS: Block {block.index} serialized successfully. Total size: {len(serialized_block)} bytes")
            return serialized_block

        except Exception as e:
            print(f"[WholeBlockData] ❌ ERROR: Failed to serialize block {block.index}: {e}")
            raise








    def get_block_from_data_file(self, offset: int):
        """
        Retrieve a block from block.data using its offset.
        Ensures block size validity and header integrity before reading the block.
        """
        try:
            print(f"[WholeBlockData.get_block_from_data_file] INFO: Attempting to retrieve block at offset {offset}.")

            # ✅ **Check if File Exists Before Reading**
            if not os.path.exists(self.current_block_file):
                print(f"[WholeBlockData.get_block_from_data_file] ❌ ERROR: block.data file not found: {self.current_block_file}")
                return None

            file_size = os.path.getsize(self.current_block_file)
            print(f"[WholeBlockData.get_block_from_data_file] INFO: File size of block.data: {file_size} bytes.")

            # ✅ **Ensure Offset is Correct (Skip Magic Number)**
            if offset < 4:  # Blocks should not be read before offset 4 (first 4 bytes are the magic number)
                print(f"[WholeBlockData.get_block_from_data_file] ❌ ERROR: Invalid offset {offset}. Adjusting to 4.")
                offset = 4

            # ✅ **Ensure Offset is Within File Size**
            if offset + 4 > file_size:  # Ensure enough space for block size read
                print(f"[WholeBlockData.get_block_from_data_file] ❌ ERROR: Invalid offset {offset} for file size {file_size}.")
                return None

            with open(self.current_block_file, "rb") as f:
                f.seek(offset)

                # ✅ **Read Block Size (First 4 Bytes)**
                block_size_bytes = f.read(4)
                if len(block_size_bytes) != 4:
                    print("[WholeBlockData.get_block_from_data_file] ❌ ERROR: Failed to read block size from file.")
                    return None

                block_size = struct.unpack(">I", block_size_bytes)[0]
                print(f"[WholeBlockData.get_block_from_data_file] INFO: Block size read as {block_size} bytes.")

                # ✅ **Validate Block Size (0MB - 10MB)**
                if block_size > 10 * 1024 * 1024:
                    print(f"[WholeBlockData.get_block_from_data_file] ❌ ERROR: Invalid block size {block_size}. Maximum allowed is 10MB.")
                    return None

                # ✅ **Ensure Full Block Data Exists**
                if offset + 4 + block_size > file_size:
                    print(f"[WholeBlockData.get_block_from_data_file] ❌ ERROR: Incomplete block at offset {offset}. Expected {block_size} bytes.")
                    return None

                # ✅ **Read Full Block Data**
                block_data = f.read(block_size)
                if len(block_data) != block_size:
                    print(f"[WholeBlockData.get_block_from_data_file] ❌ ERROR: Read {len(block_data)} bytes, expected {block_size}.")
                    return None

                # ✅ **Deserialize Block**
                block = self._deserialize_block_from_binary(block_data)
                if not block:
                    print(f"[WholeBlockData.get_block_from_data_file] ❌ ERROR: Failed to deserialize block at offset {offset}.")
                    return None

                print(f"[WholeBlockData.get_block_from_data_file] ✅ SUCCESS: Retrieved Block {block.index} from offset {offset}.")
                return block

        except Exception as e:
            print(f"[WholeBlockData.get_block_from_data_file] ❌ ERROR: Failed to retrieve block from file: {e}")
            return None



    def get_latest_block(self) -> Optional[Block]:
        """
        Retrieve the most recent block using LMDB metadata and then from block.data.
        Ensures LMDB data integrity, correct hash format, and magic number consistency.
        """
        try:
            print("[WholeBlockData.get_latest_block] INFO: Retrieving latest block from LMDB...")

            all_blocks = []

            # ✅ **Retrieve All Block Metadata from LMDB**
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.startswith(b"block:"):  # Ensure key is bytes
                        try:
                            block_metadata = json.loads(value.decode("utf-8"))

                            # ✅ **Validate Block Metadata Structure**
                            if not isinstance(block_metadata, dict):
                                print(f"[WholeBlockData.get_latest_block] ERROR: Invalid block metadata (not dict): {block_metadata}")
                                continue

                            header = block_metadata.get("block_header", {})
                            if not isinstance(header, dict) or "index" not in header:
                                print("[WholeBlockData.get_latest_block] ERROR: Block header missing 'index'.")
                                continue

                            all_blocks.append(block_metadata)

                        except json.JSONDecodeError as e:
                            print(f"[WholeBlockData.get_latest_block] ERROR: Corrupt block metadata in LMDB: {e}")
                            continue

            # ✅ **Ensure at Least One Valid Block Was Found**
            if not all_blocks:
                print("[WholeBlockData.get_latest_block] WARNING: No blocks found in LMDB. Blockchain may be empty.")
                return None

            # ✅ **Find the Block with the Highest Index**
            latest_block_data = max(all_blocks, key=lambda b: b["block_header"]["index"], default=None)
            if not latest_block_data:
                print("[WholeBlockData.get_latest_block] ERROR: Could not determine latest block.")
                return None

            # ✅ **Validate Block Hash**
            block_hash = latest_block_data.get("hash", Constants.ZERO_HASH)
            if not isinstance(block_hash, str) or not all(c in "0123456789abcdefABCDEF" for c in block_hash):
                print(f"[WholeBlockData.get_latest_block] ERROR: Invalid block hash format: {block_hash}")
                return None

            # ✅ **Validate Required Header Fields**
            required_keys = {"index", "previous_hash", "timestamp", "nonce", "difficulty"}
            header = latest_block_data["block_header"]
            if not required_keys.issubset(header):
                print(f"[WholeBlockData.get_latest_block] ERROR: Incomplete block metadata: {latest_block_data}")
                return None

            # ✅ **Validate Timestamp**
            try:
                timestamp = int(header["timestamp"])
                if timestamp <= 0:
                    raise ValueError("Invalid timestamp")
            except (ValueError, TypeError) as e:
                print(f"[WholeBlockData.get_latest_block] ERROR: Invalid timestamp format: {e}")
                return None

            # ✅ **Verify `block.data` File Exists and Contains Valid Magic Number**
            if not os.path.exists(self.current_block_file):
                print(f"[WholeBlockData.get_latest_block] ERROR: block.data file not found: {self.current_block_file}")
                return None

            with open(self.current_block_file, "rb") as f:
                if os.path.getsize(self.current_block_file) < 4:
                    print("[WholeBlockData.get_latest_block] ERROR: block.data file too small to contain magic number.")
                    return None

                file_magic_number = struct.unpack(">I", f.read(4))[0]
                if file_magic_number != Constants.MAGIC_NUMBER:
                    print(f"[WholeBlockData.get_latest_block] ERROR: Invalid magic number in block.data file: {hex(file_magic_number)}. Expected: {hex(Constants.MAGIC_NUMBER)}")
                    return None

            # ✅ **Retrieve Block Offset from LMDB and Validate**
            block_offset = latest_block_data.get("data_offset")
            if not isinstance(block_offset, int):
                print("[WholeBlockData.get_latest_block] ERROR: Block data offset missing or invalid in LMDB.")
                return None

            file_size = os.path.getsize(self.current_block_file)
            if block_offset < 0 or block_offset >= file_size:
                print(f"[WholeBlockData.get_latest_block] ERROR: Block offset {block_offset} exceeds file size {file_size}.")
                return None

            # ✅ **Retrieve Full Block Data from block.data File**
            print(f"[WholeBlockData.get_latest_block] INFO: Retrieving full block data from offset {block_offset}.")
            full_block = self.get_block_from_data_file(block_offset)
            if not full_block:
                print(f"[WholeBlockData.get_latest_block] ERROR: Failed to load full block {block_hash} from block.data file.")
                return None

            print(f"[WholeBlockData.get_latest_block] SUCCESS: Retrieved Block {full_block.index} (Hash: {full_block.hash}).")
            return full_block

        except Exception as e:
            print(f"[WholeBlockData.get_latest_block] ERROR: Failed to retrieve latest block: {e}")
            return None




    def _validate_block_file(self):
        """
        Validates the block data file.
        - If the file exceeds BLOCK_DATA_FILE_SIZE_MB (512MB from Constants), it will be regenerated.
        """
        if os.path.exists(self.current_block_file):
            with open(self.current_block_file, "rb") as f:
                f.seek(0, os.SEEK_END)
                file_size_mb = f.tell() / (1024 * 1024)  # Convert bytes to MB
                if file_size_mb > Constants.BLOCK_DATA_FILE_SIZE_MB:
                    print(f"[ERROR] Block data file exceeds {Constants.BLOCK_DATA_FILE_SIZE_MB}MB - regenerating")
                    os.remove(self.current_block_file)
                    self._initialize_block_data_file()



    def get_total_mined_supply(self) -> Optional[Decimal]:
        """
        Calculate the total mined coin supply by summing all Coinbase rewards from stored blocks.
        Caches the result in LMDB for fast future retrieval.
        Returns None if no blocks exist instead of throwing an error.
        """
        try:
            # ✅ **Retrieve Cached Supply from LMDB**
            with self.block_metadata_db.env.begin() as txn:
                cached_supply = txn.get(b"total_mined_supply")

            if cached_supply:
                try:
                    total_supply = Decimal(cached_supply.decode("utf-8"))
                    print(f"[WholeBlockData] INFO: Cached total mined supply retrieved: {total_supply} ZYC")
                    return total_supply
                except (UnicodeDecodeError, ValueError) as decode_error:
                    print(f"[WholeBlockData] WARNING: Failed to decode cached total supply: {decode_error}")

            total_supply = Decimal("0")
            blocks_found = False

            # ✅ **Iterate Through Stored Blocks in LMDB**
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.decode().startswith("block:"):
                        try:
                            block_metadata = json.loads(value.decode("utf-8"))
                            transactions = block_metadata.get("tx_ids", [])

                            if transactions:
                                blocks_found = True
                                for tx_id in transactions:
                                    tx_key = f"tx:{tx_id}".encode("utf-8")
                                    tx_data = self.txindex_db.get(tx_key)

                                    if not tx_data:
                                        print(f"[WholeBlockData] WARNING: Missing transaction {tx_id} in txindex.")
                                        continue

                                    try:
                                        tx_details = json.loads(tx_data.decode("utf-8"))
                                        if tx_details.get("type") == "COINBASE":
                                            outputs = tx_details.get("outputs", [])
                                            if isinstance(outputs, list):
                                                for output in outputs:
                                                    if "amount" in output:
                                                        total_supply += Decimal(str(output["amount"]))
                                    except json.JSONDecodeError as json_error:
                                        print(f"[WholeBlockData] ERROR: Failed to parse transaction data for {tx_id}: {json_error}")
                                        continue

                        except json.JSONDecodeError as e:
                            print(f"[WholeBlockData] ERROR: Failed to parse block metadata: {e}")
                            continue

            # ✅ **Handle Empty Blockchain Case**
            if not blocks_found:
                print("[WholeBlockData] WARNING: No blocks found in LMDB. Returning None.")
                return None

            # ✅ **Cache Total Mined Supply for Faster Future Retrieval**
            with self.block_metadata_db.env.begin(write=True) as txn:
                txn.put(b"total_mined_supply", str(total_supply).encode("utf-8"))

            print(f"[WholeBlockData] INFO: Total mined supply calculated & cached: {total_supply} ZYC")
            return total_supply

        except Exception as e:
            print(f"[WholeBlockData] ERROR: Failed to calculate total mined supply: {e}")
            return None


    def load_blockchain_data(self) -> List[Dict]:
        """Load blockchain data from LMDB, ensuring data integrity."""
        try:
            print("[WholeBlockData] INFO: Loading blockchain data from LMDB...")

            # ✅ **Retrieve Blockchain Database**
            blockchain_db = self._get_database("block_metadata")
            if not blockchain_db:
                print("[WholeBlockData] ERROR: Block metadata database is missing. Returning empty chain.")
                return []

            raw_blocks = blockchain_db.get_all_blocks()
            if not raw_blocks:
                print("[WholeBlockData] WARNING: No blocks found in LMDB. Blockchain may be empty.")
                return []

            self.chain = []

            # ✅ **Iterate Over Retrieved Blocks**
            for block in raw_blocks:
                if isinstance(block, bytes):
                    try:
                        block = pickle.loads(block)
                    except pickle.UnpicklingError as e:
                        print(f"[WholeBlockData] ERROR: Failed to deserialize block data: {e}")
                        continue

                # ✅ **Validate Block Structure**
                if not isinstance(block, dict) or "hash" not in block or not isinstance(block["hash"], str):
                    print(f"[WholeBlockData] WARNING: Retrieved block missing 'hash' or invalid structure: {block}")
                    continue

                # ✅ **Catch JSON Decoding Errors in Transactions**
                try:
                    if "transactions" in block and isinstance(block["transactions"], bytes):
                        block["transactions"] = json.loads(block["transactions"].decode("utf-8"))
                except json.JSONDecodeError as e:
                    print(f"[WholeBlockData] ERROR: Failed to decode transaction data for block {block['hash']}: {e}")
                    continue

                self.chain.append(block)

            print(f"[WholeBlockData] INFO: Successfully loaded {len(self.chain)} blocks from LMDB.")
            return self.chain

        except Exception as e:
            print(f"[WholeBlockData] ERROR: Failed to load blockchain data: {e}")
            return []


    def _get_database(self, db_key: str) -> LMDBManager:
        """Retrieve the LMDBManager instance for a given database key."""
        try:
            db_path = Constants.DATABASES.get(db_key, None)
            if not db_path:
                raise ValueError(f"[WholeBlockData] ERROR: Unknown database key: {db_key}")
            return LMDBManager(db_path)
        except Exception as e:
            print(f"[WholeBlockData] ERROR: Failed to get database {db_key}: {e}")
            raise

    def get_all_blocks(self) -> List[Dict]:
        """Retrieve all stored blocks from LMDB as a list of dictionaries, ensuring metadata validation."""
        try:
            print("[WholeBlockData.get_all_blocks] INFO: Retrieving all stored blocks from LMDB...")

            # ✅ **Retrieve Blockchain Database**
            blockchain_db = self._get_database("block_metadata")
            if not blockchain_db:
                print("[WholeBlockData.get_all_blocks] ERROR: Block metadata database not found. Returning empty list.")
                return []

            raw_blocks = blockchain_db.get_all_blocks()
            if not raw_blocks:
                print("[WholeBlockData.get_all_blocks] WARNING: No blocks found in LMDB. Returning empty list.")
                return []

            decoded_blocks = []

            # ✅ **Iterate Over Retrieved Blocks**
            for block in raw_blocks:
                if isinstance(block, bytes):
                    try:
                        block = pickle.loads(block)
                    except Exception as e:
                        print(f"[WholeBlockData.get_all_blocks] ERROR: Failed to decode block: {e}")
                        continue

                # ✅ **Validate Block Metadata**
                if not isinstance(block, dict) or not all(k in block for k in ["hash", "header", "transactions"]):
                    print(f"[WholeBlockData.get_all_blocks] WARNING: Block missing required fields: {block}")
                    continue

                # ✅ **Ensure Block Hash is Valid**
                if not isinstance(block["hash"], str) or len(block["hash"]) != 96:
                    print(f"[WholeBlockData.get_all_blocks] WARNING: Invalid block hash format. Replacing with Merkle root.")
                    block["hash"] = block["header"].get("merkle_root", Constants.ZERO_HASH)

                decoded_blocks.append(block)

            # ✅ **Sort Blocks by Index**
            decoded_blocks.sort(key=lambda b: b["header"]["index"])

            # ✅ **Verify Block Hash Continuity**
            prev_hash = Constants.ZERO_HASH
            for block in decoded_blocks:
                if block["header"]["previous_hash"] != prev_hash:
                    print(f"[WholeBlockData.get_all_blocks] ERROR: Chain discontinuity detected at block {block['header']['index']}. Returning empty list.")
                    return []
                prev_hash = block["hash"]

            print(f"[WholeBlockData.get_all_blocks] SUCCESS: Retrieved {len(decoded_blocks)} valid blocks from storage.")
            return decoded_blocks

        except Exception as e:
            print(f"[WholeBlockData.get_all_blocks] ERROR: Failed to retrieve blocks: {e}")
            return []


    def _block_to_storage_format(self, block: Block) -> Dict:
        """
        Convert a Block object to a dictionary format suitable for LMDB storage.
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
            print(f"[WholeBlockData] ERROR: Failed to format block for storage: {e}")
            return {}


    def purge_chain(self):
        """
        Purge corrupted blockchain data by resetting LMDB storage and block data files.
        """
        try:
            print("[WholeBlockData.purge_chain] 🚨 WARNING: Purging corrupted blockchain data...")

            # ✅ **Close LMDB databases before deletion**
            self.block_metadata_db.close()
            self.txindex_db.close()

            # ✅ **Delete LMDB Storage & Block Data Files**
            for db_path in [Constants.DATABASES["block_metadata"], Constants.DATABASES["txindex"], self.current_block_file]:
                if os.path.exists(db_path):
                    os.remove(db_path)
                    print(f"[WholeBlockData.purge_chain] INFO: Deleted {db_path}")

            # ✅ **Reinitialize Storage**
            self.block_metadata_db = LMDBManager(Constants.DATABASES["block_metadata"])
            self.txindex_db = LMDBManager(Constants.DATABASES["txindex"])

            # ✅ **Recreate block.data with the correct magic number**
            with open(self.current_block_file, "wb") as f:
                f.write(struct.pack(">I", Constants.MAGIC_NUMBER))
            print(f"[WholeBlockData.purge_chain] INFO: Recreated block.data with magic number {hex(Constants.MAGIC_NUMBER)}.")

            print("[WholeBlockData.purge_chain] ✅ SUCCESS: Blockchain storage reset.")
        
        except Exception as e:
            print(f"[WholeBlockData.purge_chain] ❌ ERROR: Failed to purge blockchain data: {e}")
