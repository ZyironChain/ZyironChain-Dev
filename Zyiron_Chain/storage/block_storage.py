import os
import re
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
from Zyiron_Chain.accounts.key_manager import KeyManager
import struct
from threading import Lock

from threading import Lock

class WholeBlockData:
    def __init__(self, tx_storage: TxStorage, key_manager: KeyManager):
        """
        Initializes block storage with proper setup of directories, metadata, and transactions.

        Args:
            tx_storage (TxStorage): Transaction storage handler.
            key_manager (KeyManager): Key manager for signing and verifying keys.
        """
        try:
            print("[WholeBlockData.__init__] INFO: Initializing block storage...")

            # ✅ **Ensure `tx_storage` and `key_manager` are provided**
            if not tx_storage:
                raise ValueError("[WholeBlockData.__init__] ❌ ERROR: `tx_storage` instance is required.")
            if not key_manager:
                raise ValueError("[WholeBlockData.__init__] ❌ ERROR: `key_manager` instance is required.")

            self.tx_storage = tx_storage
            self.key_manager = key_manager  # ✅ Store key manager for later use
            self.write_lock = Lock()  # ✅ Ensure thread safety

            # ✅ **Step 1: Initialize LMDB Databases**
            self.block_metadata_db = LMDBManager(Constants.DATABASES["block_metadata"])
            self.txindex_db = LMDBManager(Constants.DATABASES["txindex"])

            # ✅ **Step 2: Set up directories & determine current block file path**
            self._setup_directories_and_paths()

            # ✅ **Step 3: Initialize block metadata (after directories are set)**
            self.block_metadata = BlockMetadata(
                block_metadata_db=self.block_metadata_db,
                txindex_db=self.txindex_db,
                tx_storage=self.tx_storage,
                current_block_file=self.current_block_file
            )

            # ✅ **Step 4: Initialize Block Data File (Ensures storage consistency)**
            self._initialize_block_data_file()

            print("[WholeBlockData.__init__] ✅ SUCCESS: Block storage initialized successfully.")

        except Exception as e:
            print(f"[WholeBlockData.__init__] ❌ ERROR: Failed to initialize block storage: {e}")
            raise


    def _setup_directories_and_paths(self):
        """
        Sets up the necessary directories and file paths without initializing the data file.
        """
        try:
            blockchain_storage_dir = os.path.join(os.getcwd(), "blockchain_storage")
            block_data_dir = os.path.join(blockchain_storage_dir, "block_data")
            os.makedirs(block_data_dir, exist_ok=True)

            self.current_block_file = os.path.join(block_data_dir, "block.data")

        except Exception as e:
            print(f"[WholeBlockData._setup_directories_and_paths] ❌ ERROR: Failed to setup directories: {e}")
            raise




    def store_block_at_offset(self, block, offset):
        print(f"[WholeBlockData] DEBUG: Storing Block at Offset {offset}")
        print(f"[WholeBlockData] DEBUG: Block Hash Before Storage: {block.hash}")

        serialized_block = self.serialize_block(block)
        with open(self.current_block_file, "r+b") as f:
            f.seek(offset)
            f.write(serialized_block)

        print(f"[WholeBlockData] DEBUG: Stored Block {block.index} at Offset {offset}")





    def store_block_securely(self, block):
        """
        Store block with thread safety to prevent corruption.
        Uses `write_lock` to ensure that only one thread writes at a time.
        """
        try:
            if not isinstance(block, Block):
                print("[WholeBlockData.store_block_securely] ❌ ERROR: Invalid block type. Expected a Block instance.")
                return

            with self.write_lock:  # ✅ Prevents concurrent writes
                print(f"[WholeBlockData.store_block_securely] INFO: Acquiring lock to store Block {block.index}...")
                self._write_to_block_data_securely(block)
                print(f"[WholeBlockData.store_block_securely] ✅ SUCCESS: Block {block.index} stored securely.")

        except Exception as e:
            print(f"[WholeBlockData.store_block_securely] ❌ ERROR: Failed to store block securely: {e}")









    def validate_block_data_file(self) -> bool:
        """
        Validates the `block.data` file by:
        - Checking the magic number.
        - Ensuring the file is large enough to contain valid block data.
        - Reading and verifying the block size using **8-byte block size validation (`>Q`).**
        - Ensuring that block data is fully readable.

        :return: True if the file is valid; False otherwise.
        """
        try:
            # ✅ **Check if File Exists and is Readable**
            if not os.path.exists(self.current_block_file):
                print("[WholeBlockData.validate_block_data_file] ERROR: block.data file does not exist.")
                return False
            
            file_size = os.path.getsize(self.current_block_file)
            if file_size < 12:  # ✅ At least 12 bytes required (Magic Number + Block Size)
                print(f"[WholeBlockData.validate_block_data_file] ERROR: block.data file is too small ({file_size} bytes).")
                return False

            with open(self.current_block_file, "rb") as f:
                # ✅ **Read and Validate Magic Number**
                magic_number_bytes = f.read(4)
                expected_magic_number = struct.pack(">I", Constants.MAGIC_NUMBER)

                if magic_number_bytes != expected_magic_number:
                    print(f"[WholeBlockData.validate_block_data_file] ERROR: Invalid magic number in block.data. Found: {magic_number_bytes.hex()}, Expected: {expected_magic_number.hex()}.")
                    return False

                # ✅ **Read Block Size (8 Bytes)**
                block_size_bytes = f.read(8)
                if len(block_size_bytes) != 8:
                    print("[WholeBlockData.validate_block_data_file] ERROR: Failed to read block size from block.data.")
                    return False

                block_size = struct.unpack(">Q", block_size_bytes)[0]  # ✅ Now uses 8-byte format
                print(f"[WholeBlockData.validate_block_data_file] INFO: Block size: {block_size} bytes.")

                # ✅ **Ensure Block Size is Reasonable (1MB - 10MB)**
                if not (Constants.MIN_BLOCK_SIZE_BYTES <= block_size <= Constants.MAX_BLOCK_SIZE_BYTES):
                    print(f"[WholeBlockData.validate_block_data_file] ERROR: Block size {block_size} bytes is out of allowed range ({Constants.MIN_BLOCK_SIZE_BYTES} - {Constants.MAX_BLOCK_SIZE_BYTES} bytes).")
                    return False

                # ✅ **Read the Block Data Based on the Block Size**
                block_data = f.read(block_size)
                if len(block_data) != block_size:
                    print(f"[WholeBlockData.validate_block_data_file] ERROR: Incomplete block data. Expected {block_size} bytes, got {len(block_data)}.")
                    return False

                print("[WholeBlockData.validate_block_data_file] SUCCESS: block.data file is valid.")
                return True

        except Exception as e:
            print(f"[WholeBlockData.validate_block_data_file] ERROR: Failed to validate block.data file: {e}")
            return False



        

    def _write_to_block_data_securely(self, block):
        """ 
        Serialize and write block data to block.data file securely. 
        Ensures:
        - Magic number is written before every block.
        - Blocks are appended with correct alignment.
        - Block size is validated and written correctly.
        """
        try:
            # ✅ **Ensure BlockMetadata Uses the Same File Path**
            if self.block_metadata:
                self.block_metadata.current_block_file = self.current_block_file
                print("[WholeBlockData._write_to_block_data_securely] INFO: BlockMetadata now using the same block.data file path.")

            with open(self.current_block_file, "ab") as f:
                offset_before_write = f.tell()

                # ✅ **Write Magic Number Before Every Block**
                f.write(struct.pack(">I", Constants.MAGIC_NUMBER))
                print(f"[WholeBlockData._write_to_block_data_securely] INFO: Magic number {hex(Constants.MAGIC_NUMBER)} written before block {block.index}.")

                # ✅ **Serialize Block**
                serialized_block = self._serialize_block_to_binary(block)

                # ✅ **Store Block Size as 8 Bytes (`>Q` for Unsigned Long Long)**
                block_size_bytes = struct.pack(">Q", len(serialized_block))

                # ✅ **Write Block Data**
                f.write(block_size_bytes + serialized_block)
                f.flush()

                print(f"[WholeBlockData._write_to_block_data_securely] SUCCESS: Block {block.index} securely stored at offset {offset_before_write}.")

        except Exception as e:
            print(f"[WholeBlockData._write_to_block_data_securely] ERROR: Failed to store block {block.index}: {e}")
            raise




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
        - Ensures `difficulty_length` (1 byte), `difficulty` (48 bytes), and `fees_collected` (8 bytes) match `BLOCK_STORAGE_OFFSETS`.

        :param block: The block to store.
        :param difficulty: The difficulty target of the block.
        """
        try:
            print(f"[WholeBlockData.store_block] INFO: Storing Block {block.index} with difficulty {difficulty}.")

            # ✅ **Ensure `BlockMetadata` Uses the Shared Instance**
            if not self.block_metadata:
                print("[WholeBlockData.store_block] ERROR: `block_metadata` is not initialized. Cannot store block.")
                return

            # ✅ **Ensure Difficulty is Exactly 48 Bytes (per BLOCK_STORAGE_OFFSETS)**
            difficulty_bytes = difficulty.to_bytes(Constants.BLOCK_STORAGE_OFFSETS["difficulty"]["size"], "big")

            # ✅ **Ensure Difficulty Length is Exactly 1 Byte**
            difficulty_length = 1  # Always 1 byte
            difficulty_length_bytes = difficulty_length.to_bytes(Constants.BLOCK_STORAGE_OFFSETS["difficulty_length"]["size"], "big")

            # ✅ **Ensure Fees Collected is Exactly 8 Bytes**
            if not hasattr(block, "fees"):
                block.fees = 0  # Default to 0 if fees is missing
            fees_collected_int = int(block.fees * (10**8))  # Convert Decimal to int
            fees_collected_bytes = fees_collected_int.to_bytes(Constants.BLOCK_STORAGE_OFFSETS["fees_collected"]["size"], "big")

            print(f"[WholeBlockData.store_block] INFO: Difficulty Length (1 byte): {difficulty_length_bytes.hex()}")
            print(f"[WholeBlockData.store_block] INFO: Difficulty (48 bytes): {difficulty_bytes.hex()}")
            print(f"[WholeBlockData.store_block] INFO: Fees Collected (8 bytes): {fees_collected_bytes.hex()}")

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

            # ✅ **Write to `block.data` with Correct Alignment**
            with open(self.current_block_file, "ab") as f:
                offset_before_write = f.tell()

                # ✅ **Store Block Size as 8 Bytes (`>Q`)**
                block_size_bytes = struct.pack(">Q", block_size)

                # ✅ **Write Block Data**
                f.write(block_size_bytes + difficulty_length_bytes + difficulty_bytes + fees_collected_bytes + block_bytes)
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
        - Ensures Genesis block is checked directly instead of using `GenesisBlockManager`.
        - Prevents inconsistent Genesis formatting affecting hash validation.
        - Uses `BLOCK_STORAGE_OFFSETS` for precise placement.
        """
        try:
            print(f"[WholeBlockData._initialize_block_data_file] INFO: Block data file path set to: {self.current_block_file}")

            # ✅ Retrieve Magic Number from Constants
            MAGIC_NUMBER = Constants.MAGIC_NUMBER
            print(f"[WholeBlockData._initialize_block_data_file] INFO: Expected Magic Number: {hex(MAGIC_NUMBER)}")

            # ✅ Ensure Block Data Directory Exists
            block_data_dir = os.path.dirname(self.current_block_file)
            if not block_data_dir:
                print("[WholeBlockData._initialize_block_data_file] ❌ ERROR: Block data directory path is invalid.")
                return
            os.makedirs(block_data_dir, exist_ok=True)  # ✅ Ensure parent directory exists

            # ✅ Check if File Exists and is Empty
            file_exists = os.path.exists(self.current_block_file)
            file_is_empty = os.path.getsize(self.current_block_file) == 0 if file_exists else True

            # ✅ Write Magic Number Only if File is Missing or Empty
            if not file_exists or file_is_empty:
                with open(self.current_block_file, "wb") as f:
                    f.write(struct.pack(">I", MAGIC_NUMBER))  # ✅ Write magic number
                print(f"[WholeBlockData._initialize_block_data_file] ✅ INFO: Created block.data with magic number {hex(MAGIC_NUMBER)}.")
            else:
                print("[WholeBlockData._initialize_block_data_file] INFO: block.data file exists. Skipping magic number rewrite.")

            # ✅ Validate Magic Number in Existing File
            with open(self.current_block_file, "rb") as f:
                magic_number_bytes = f.read(4)
                if len(magic_number_bytes) != 4:
                    print("[WholeBlockData._initialize_block_data_file] ❌ ERROR: Magic number read failed. File may be corrupted.")
                    self._repair_block_data_file()
                    return

                file_magic_number = struct.unpack(">I", magic_number_bytes)[0]

            if file_magic_number != MAGIC_NUMBER:
                print(f"[WholeBlockData._initialize_block_data_file] ❌ ERROR: Invalid magic number in block.data file: {hex(file_magic_number)} "
                    f"(Expected: {hex(MAGIC_NUMBER)}).")
                print("[WholeBlockData._initialize_block_data_file] ❌ WARNING: Storage corruption detected! Attempting recovery...")

                # ✅ Automatically Repair Corrupt File
                self._repair_block_data_file()
                return

            print(f"[WholeBlockData._initialize_block_data_file] ✅ SUCCESS: Block storage validated at {self.current_block_file}.")

            # ✅ Check if Genesis Block Exists in LMDB Metadata
            print("[WholeBlockData._initialize_block_data_file] INFO: Checking for existing Genesis Block before mining.")
            genesis_block = self.block_metadata.get_block_by_height(0)

            if genesis_block and hasattr(genesis_block, "hash"):
                print(f"[WholeBlockData._initialize_block_data_file] ✅ INFO: Genesis Block already exists with hash {genesis_block.hash}")
                return  # ✅ Genesis block already exists, no need to do anything

            print("[WholeBlockData._initialize_block_data_file] WARNING: No valid Genesis block found in metadata. Checking block.data...")

            # ✅ Check if Genesis Block Exists in Block Storage (`block.data`)
            genesis_block_offset = Constants.BLOCK_STORAGE_OFFSETS["block_height"]["start"]

            if os.path.exists(self.current_block_file):
                with open(self.current_block_file, "rb") as f:
                    f.seek(0, os.SEEK_END)
                    file_size = f.tell()

                if file_size >= genesis_block_offset:
                    block_from_storage = self.get_block_from_data_file(genesis_block_offset)  # ✅ **FIXED: Use self.get_block_from_data_file()**

                    if block_from_storage and hasattr(block_from_storage, "index") and block_from_storage.index == 0:
                        print(f"[WholeBlockData._initialize_block_data_file] ✅ SUCCESS: Genesis Block retrieved from block.data with hash: {block_from_storage.hash}")

                        # ✅ Validate Genesis Block Hash
                        expected_genesis_hash = Hashing.hash(json.dumps(block_from_storage.to_dict(), sort_keys=True).encode()).hex()
                        if block_from_storage.hash == expected_genesis_hash:
                            print("[WholeBlockData._initialize_block_data_file] ✅ SUCCESS: Genesis Block matches expected hash.")
                            return
                        else:
                            print("[WholeBlockData._initialize_block_data_file] ❌ ERROR: Genesis Block hash mismatch! Expected:", expected_genesis_hash)
                            print("[WholeBlockData._initialize_block_data_file] ❌ WARNING: Corrupt Genesis Block detected. A fix may be required.")

            else:
                print("[WholeBlockData._initialize_block_data_file] WARNING: `block.data` file not found.")

            # 🚫 Do not mine the Genesis Block here
            print("[WholeBlockData._initialize_block_data_file] ❌ ERROR: No valid Genesis block found. This must be handled by the correct system component.")

        except Exception as e:
            print(f"[WholeBlockData._initialize_block_data_file] ❌ ERROR: Failed to initialize block storage: {e}")
            raise




    def _repair_block_data_file(self):
        """
        Repairs the `block.data` file by regenerating it with a correct magic number.
        """
        try:
            print("[WholeBlockData._repair_block_data_file] 🚨 WARNING: Repairing corrupted block.data file...")

            # ✅ **Backup Existing Corrupt File**
            backup_path = self.current_block_file + ".bak"
            os.rename(self.current_block_file, backup_path)
            print(f"[WholeBlockData._repair_block_data_file] INFO: Backed up corrupt file to {backup_path}.")

            # ✅ **Recreate Fresh `block.data` File**
            with open(self.current_block_file, "wb") as f:
                f.write(struct.pack(">I", Constants.MAGIC_NUMBER))
            print(f"[WholeBlockData._repair_block_data_file] ✅ SUCCESS: Recreated block.data with magic number {hex(Constants.MAGIC_NUMBER)}.")

        except Exception as e:
            print(f"[WholeBlockData._repair_block_data_file] ❌ ERROR: Failed to repair block.data file: {e}")
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

            # ✅ Retrieve Magic Number from Constants
            MAGIC_NUMBER = Constants.MAGIC_NUMBER
            print(f"[WholeBlockData] INFO: Expected Magic Number: {hex(MAGIC_NUMBER)}")

            # ✅ Define Standardized Header Format (Aligned with BLOCK_STORAGE_OFFSETS)
            header_format = ">I Q 48s 48s 48s Q Q B 48s Q 128s 48s 700s Q Q I"
            base_header_size = struct.calcsize(header_format)
            print(f"[WholeBlockData] INFO: Expected header size: {base_header_size} bytes.")

            # ✅ Ensure block data contains at least the header size
            if len(block_data) < base_header_size:
                raise ValueError("[WholeBlockData] ❌ ERROR: Block data too short for header.")

            # ✅ Unpack standardized header fields
            try:
                (
                    magic_number, block_size, prev_block_hash, merkle_root, difficulty_bytes,
                    block_height, timestamp, difficulty_length, difficulty_target,
                    nonce, miner_address_bytes, transaction_signature, falcon_signature,
                    reward, fees, version
                ) = struct.unpack(header_format, block_data[:base_header_size])

            except struct.error as e:
                raise ValueError(f"[WholeBlockData] ❌ ERROR: Struct unpacking failed: {e}")

            # ✅ Validate Magic Number
            if magic_number != MAGIC_NUMBER:
                raise ValueError(f"[WholeBlockData] ❌ ERROR: Invalid magic number {hex(magic_number)} (Expected: {hex(MAGIC_NUMBER)})")

            print(f"[WholeBlockData] INFO: Magic Number Verified: {hex(magic_number)}")
            print(f"[WholeBlockData] INFO: Header unpacked: index={block_height}, timestamp={timestamp}, block size={block_size}.")
            print(f"[WholeBlockData] INFO: Reward: {reward}, Fees: {fees}, Version: {version}")

            # ✅ Extract Miner Address (Ensure Exactly 128 Bytes)
            miner_address_str = miner_address_bytes.rstrip(b'\x00').decode("utf-8")
            print(f"[WholeBlockData] INFO: Miner Address: {miner_address_str}")

            # ✅ Extract Difficulty Value (Ensure Exactly 48 Bytes)
            difficulty_int = int.from_bytes(difficulty_target, "big", signed=False)
            print(f"[WholeBlockData] INFO: Difficulty: {difficulty_int}")

            # ✅ Extract Transaction Signature (Ensure Exactly 48 Bytes)
            transaction_signature_hex = transaction_signature.hex()
            print(f"[WholeBlockData] INFO: Transaction Signature: {transaction_signature_hex}")

            # ✅ Extract Falcon Signature (Ensure Exactly 700 Bytes)
            falcon_signature_hex = falcon_signature.rstrip(b'\x00').hex()
            print(f"[WholeBlockData] INFO: Falcon Signature Verified: {falcon_signature_hex[:20]}... (700 bytes)")

            # ✅ Retrieve Transaction Count Using `BLOCK_STORAGE_OFFSETS`
            tx_count_offset = Constants.BLOCK_STORAGE_OFFSETS["transaction_count"]["start"]

            if len(block_data) < tx_count_offset + 4:
                raise ValueError("[WholeBlockData] ❌ ERROR: Block data too short for transaction count.")

            tx_count = struct.unpack(">I", block_data[tx_count_offset:tx_count_offset + 4])[0]
            print(f"[WholeBlockData] INFO: Block {block_height} claims {tx_count} transaction(s).")

            # ✅ Unpack Transactions (Each Prefixed with 4-Byte Size)
            tx_data_offset = tx_count_offset + 4
            transactions = []

            for i in range(tx_count):
                print(f"[WholeBlockData] INFO: Processing transaction {i} at offset {tx_data_offset}.")

                # ✅ Check for transaction size field (4 bytes)
                if len(block_data) < tx_data_offset + 4:
                    print(f"[WholeBlockData] ❌ ERROR: Not enough data to read size of transaction {i} in block {block_height}. Skipping.")
                    break  

                tx_size = struct.unpack(">I", block_data[tx_data_offset:tx_data_offset + 4])[0]
                tx_data_offset += 4

                print(f"[WholeBlockData] INFO: Transaction {i} size: {tx_size} bytes.")

                # ✅ Ensure full transaction data is available
                if len(block_data) < tx_data_offset + tx_size:
                    print(f"[WholeBlockData] ❌ ERROR: Incomplete transaction data for transaction {i} in block {block_height}. Skipping.")
                    break  

                tx_bytes = block_data[tx_data_offset:tx_data_offset + tx_size]
                tx_data_offset += tx_size

                try:
                    tx_obj = json.loads(tx_bytes.decode("utf-8"))
                    if not isinstance(tx_obj, dict) or "tx_id" not in tx_obj:
                        print(f"[WholeBlockData] ❌ ERROR: Transaction {i} missing 'tx_id'. Skipping.")
                        continue  

                    print(f"[WholeBlockData] INFO: Transaction {i} deserialized successfully with tx_id: {tx_obj.get('tx_id')}.")
                    transactions.append(tx_obj)

                except Exception as e:
                    print(f"[WholeBlockData] ❌ ERROR: Failed to deserialize transaction {i} in block {block_height}: {e}")
                    continue

            # ✅ Verify Transaction Count Matches Deserialized Transactions
            if len(transactions) != tx_count:
                print(f"[WholeBlockData] ❌ ERROR: Expected {tx_count} transactions, but deserialized {len(transactions)}. Adjusting count.")
                tx_count = len(transactions)  

            # ✅ Construct Standardized Block Dictionary
            block_dict = {
                "index": block_height,
                "previous_hash": prev_block_hash.hex(),
                "merkle_root": merkle_root.hex(),
                "difficulty": difficulty_int,
                "nonce": nonce,
                "miner_address": miner_address_str,
                "transaction_signature": transaction_signature_hex,
                "falcon_signature": falcon_signature_hex,  # ✅ Falcon Signature Stored
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
        - Ensures block size is 8 bytes (>Q format).
        - Packs header fields, extra metadata (reward, fees, version), and transaction data.
        - Ensures `difficulty` is exactly **48 bytes** before serialization.
        - Ensures `falcon_signature` is **exactly 700 bytes** to prevent offset mismatches.
        - Aligns all block elements with BLOCK_STORAGE_OFFSETS.
        - Retrieves magic number from Constants instead of hardcoding.
        - ✅ Only serializes valid transactions.
        """

        try:
            print(f"[WholeBlockData] INFO: Serializing Block {block.index} to binary.")

            # Retrieve magic number from Constants
            MAGIC_NUMBER = Constants.MAGIC_NUMBER  # ✅ Now using Constants
            print(f"[WholeBlockData] INFO: Using Magic Number: {MAGIC_NUMBER:#X}")

            # Convert block to dictionary and extract header information.
            block_dict = block.to_dict()
            header = block_dict.get("header")
            if header is None:
                raise ValueError("[WholeBlockData] ❌ ERROR: Block header is missing.")
            print("[WholeBlockData] INFO: Block header retrieved successfully.")

            # --- Standardized Fixed Header Fields ---
            try:
                block_height = int(header["index"])
                prev_block_hash = bytes.fromhex(header["previous_hash"]).ljust(48, b'\x00')[:48]
                merkle_root = bytes.fromhex(header["merkle_root"]).ljust(48, b'\x00')[:48]
                timestamp = int(header["timestamp"])
                nonce = int(header["nonce"])
                print(f"[WholeBlockData] INFO: Fixed header fields - index: {block_height}, timestamp: {timestamp}, nonce: {nonce}.")
            except (KeyError, ValueError, TypeError) as e:
                print(f"[WholeBlockData] ❌ ERROR: Failed to extract header fields: {e}")
                raise

            # ✅ Ensure difficulty_bytes is exactly 48 bytes
            try:
                difficulty_hex = header.get("difficulty", "00" * 48)
                difficulty_bytes = bytes.fromhex(difficulty_hex).ljust(48, b'\x00')[:48]
                print(f"[WholeBlockData] INFO: Difficulty processed - length: {len(difficulty_bytes)} bytes.")
            except (ValueError, TypeError) as e:
                print(f"[WholeBlockData] ❌ ERROR: Failed to process difficulty: {e}")
                raise

            # ✅ Ensure Miner Address is exactly 128 bytes
            try:
                miner_address_str = header["miner_address"]
                miner_address_encoded = miner_address_str.encode("utf-8")
                miner_address_padded = miner_address_encoded.ljust(128, b'\x00')[:128]
                print(f"[WholeBlockData] INFO: Miner address processed and padded.")
            except (KeyError, UnicodeEncodeError) as e:
                print(f"[WholeBlockData] ❌ ERROR: Failed to process miner address: {e}")
                raise

            # ✅ Ensure Transaction Signature is exactly 48 Bytes
            try:
                transaction_signature = bytes.fromhex(header.get("transaction_signature", "00" * 48))[:48]
            except (ValueError, TypeError) as e:
                print(f"[WholeBlockData] ❌ ERROR: Failed to process transaction signature: {e}")
                raise

            # ✅ Ensure Falcon Signature is exactly 700 Bytes
            try:
                falcon_signature = bytes.fromhex(header.get("falcon_signature", "00" * 700))[:700].ljust(700, b'\x00')
                print(f"[WholeBlockData] INFO: Falcon signature processed and padded to 700 bytes.")
            except (ValueError, TypeError) as e:
                print(f"[WholeBlockData] ❌ ERROR: Failed to process Falcon signature: {e}")
                raise

            # --- Extra Header Fields ---
            try:
                reward = int(float(header.get("reward", "0")))
                fees_collected = int(float(header.get("fees", "0")))
            except (ValueError, TypeError) as e:
                print(f"[WholeBlockData] ❌ ERROR: Failed to process reward or fees: {e}")
                raise

            # ✅ Convert block version safely
            try:
                block_version = int(float(header.get("version", 1)))
                print(f"[WholeBlockData] INFO: Block version processed: {block_version}")
            except (ValueError, TypeError) as e:
                print(f"[WholeBlockData] ❌ ERROR: Invalid block version format '{header.get('version')}', defaulting to 1.")
                block_version = 1

            # ✅ Pack the header fields correctly (Aligned to BLOCK_STORAGE_OFFSETS)
            try:
                fixed_header_format = ">I Q 48s 48s 48s Q Q B 48s Q 128s 48s 700s Q Q I"
                fixed_header_data = struct.pack(
                    fixed_header_format,
                    MAGIC_NUMBER,  # ✅ Magic Number from Constants
                    0,  # Placeholder for block size (will be updated later)
                    prev_block_hash,
                    merkle_root,
                    difficulty_bytes,
                    block_height,
                    timestamp,
                    len(difficulty_bytes),
                    difficulty_bytes,
                    nonce,
                    miner_address_padded,
                    transaction_signature,
                    falcon_signature,
                    reward,
                    fees_collected,
                    block_version
                )
                print(f"[WholeBlockData] INFO: Fixed header packed successfully.")
            except struct.error as e:
                print(f"[WholeBlockData] ❌ ERROR: Failed to pack header fields: {e}")
                raise

            # --- Serialize Transactions ---
            serialized_transactions = []
            transactions = block_dict.get("transactions", [])
            valid_transactions = []

            print(f"[WholeBlockData] INFO: Serializing {len(transactions)} transaction(s).")

            for idx, tx in enumerate(transactions):
                try:
                    # ✅ Ensure transactions are valid before serialization
                    if hasattr(tx, "to_dict"):
                        tx_dict = tx.to_dict()
                    elif isinstance(tx, dict):
                        tx_dict = tx
                    else:
                        print(f"[WholeBlockData] ❌ ERROR: Transaction at index {idx} is not serializable. Skipping.")
                        continue  

                    # ✅ Check if the transaction is valid
                    if "tx_id" not in tx_dict or not isinstance(tx_dict["tx_id"], str):
                        print(f"[WholeBlockData] ❌ ERROR: Transaction {idx} is missing a valid 'tx_id'. Skipping.")
                        continue  

                    valid_transactions.append(tx_dict)

                    tx_json = json.dumps(tx_dict, ensure_ascii=False, sort_keys=True).encode("utf-8")
                    tx_size = len(tx_json)

                    serialized_tx = struct.pack(">I", tx_size) + tx_json
                    serialized_transactions.append(serialized_tx)
                    print(f"[WholeBlockData] INFO: Serialized transaction {idx}: size {tx_size} bytes.")
                except (json.JSONDecodeError, TypeError, struct.error) as e:
                    print(f"[WholeBlockData] ❌ ERROR: Failed to serialize transaction at index {idx}: {e}")
                    continue  

            # ✅ Pack Transaction Count (4 bytes) + Transactions
            try:
                tx_count = len(valid_transactions)  # ✅ Use only valid transactions
                tx_count_data = struct.pack(">I", tx_count)
                tx_data = b"".join(serialized_transactions)
                print(f"[WholeBlockData] INFO: {tx_count} valid transaction(s) serialized.")
            except struct.error as e:
                print(f"[WholeBlockData] ❌ ERROR: Failed to pack transaction count: {e}")
                raise

            # ✅ Combine Everything into Final Block Binary Format
            try:
                serialized_block = fixed_header_data + tx_count_data + tx_data
                block_size = len(serialized_block)

                # ✅ Correct the block size value in header
                serialized_block = serialized_block[:4] + struct.pack(">Q", block_size) + serialized_block[12:]

                print(f"[WholeBlockData] ✅ SUCCESS: Block {block.index} serialized successfully. Total size: {block_size} bytes")
                return serialized_block
            except Exception as e:
                print(f"[WholeBlockData] ❌ ERROR: Failed to combine block data: {e}")
                raise

        except Exception as e:
            print(f"[WholeBlockData] ❌ ERROR: Failed to serialize block {block.index}: {e}")
            raise









    def get_block_from_data_file(self, offset: int):
        """
        Retrieve a block from block.data using its offset.
        - Ensures block size validity using **8-byte (`>Q`) format**.
        - Validates offset correctness before reading.
        - Prevents incomplete block reads due to file corruption.

        :param offset: The byte offset to read the block from.
        :return: The deserialized Block object, or None if retrieval fails.
        """
        try:
            print(f"[WholeBlockData.get_block_from_data_file] INFO: Attempting to retrieve block at offset {offset}.")

            # ✅ **Check if File Exists Before Reading**
            if not os.path.exists(self.current_block_file):
                print(f"[WholeBlockData.get_block_from_data_file] ❌ ERROR: block.data file not found: {self.current_block_file}")
                return None

            file_size = os.path.getsize(self.current_block_file)
            print(f"[WholeBlockData.get_block_from_data_file] INFO: File size of block.data: {file_size} bytes.")

            # ✅ **Ensure Offset is Valid**
            if offset < 4:  # Offset should be at least 4 to skip the magic number
                print(f"[WholeBlockData.get_block_from_data_file] ❌ ERROR: Invalid offset {offset}. Adjusting to 4.")
                offset = 4

            if offset >= file_size:
                print(f"[WholeBlockData.get_block_from_data_file] ❌ ERROR: Offset {offset} is beyond file size {file_size}.")
                return None

            with open(self.current_block_file, "rb") as f:
                f.seek(offset)

                # ✅ **Read Block Size as 8 Bytes (`>Q`)**
                block_size_bytes = f.read(8)
                if len(block_size_bytes) != 8:
                    print("[WholeBlockData.get_block_from_data_file] ❌ ERROR: Failed to read block size from file.")
                    return None

                block_size = struct.unpack(">Q", block_size_bytes)[0]  # ✅ Now uses 8-byte format
                print(f"[WholeBlockData.get_block_from_data_file] INFO: Block size read as {block_size} bytes.")

                # ✅ **Validate Block Size (1B - 10MB)**
                if block_size <= 0 or block_size > 10 * 1024 * 1024:
                    print(f"[WholeBlockData.get_block_from_data_file] ❌ ERROR: Invalid block size {block_size}. Allowed range: 1 - 10MB.")
                    return None

                # ✅ **Ensure Full Block Data Exists**
                if offset + 8 + block_size > file_size:
                    print(f"[WholeBlockData.get_block_from_data_file] ❌ ERROR: Incomplete block at offset {offset}. Expected {block_size} bytes, file size is {file_size}.")
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
        Retrieve the most recent block efficiently using LMDB metadata.
        Ensures LMDB data integrity, correct hash format, and magic number consistency.
        """
        try:
            print("[WholeBlockData.get_latest_block] INFO: Retrieving latest block from LMDB...")

            # ✅ **Retrieve Highest Index Block from LMDB Directly**
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                if not cursor.last():  # Move to the last key (highest index block)
                    print("[WholeBlockData.get_latest_block] WARNING: No blocks found in LMDB. Blockchain may be empty.")
                    return None

                key, value = cursor.item()
                if not key.startswith(b"block:"):
                    print(f"[WholeBlockData.get_latest_block] ERROR: Unexpected key format in LMDB: {key}")
                    return None

                try:
                    latest_block_data = json.loads(value.decode("utf-8"))
                except json.JSONDecodeError as e:
                    print(f"[WholeBlockData.get_latest_block] ERROR: Corrupt block metadata in LMDB: {e}")
                    return None

            # ✅ **Validate Block Metadata Structure**
            if not isinstance(latest_block_data, dict):
                print("[WholeBlockData.get_latest_block] ERROR: Block metadata is not in a valid format.")
                return None

            header = latest_block_data.get("block_header", {})
            if not isinstance(header, dict) or "index" not in header:
                print("[WholeBlockData.get_latest_block] ERROR: Block header is missing 'index'.")
                return None

            # ✅ **Validate Block Hash Format**
            block_hash = latest_block_data.get("hash", Constants.ZERO_HASH)
            if not isinstance(block_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{96}", block_hash):
                print(f"[WholeBlockData.get_latest_block] ERROR: Invalid block hash format: {block_hash}")
                return None

            # ✅ **Validate Required Header Fields**
            required_keys = {"index", "previous_hash", "timestamp", "nonce", "difficulty"}
            if not required_keys.issubset(header):
                print(f"[WholeBlockData.get_latest_block] ERROR: Incomplete block metadata. Missing fields: {required_keys - header.keys()}")
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
            if not isinstance(block_offset, int) or block_offset < 0:
                print("[WholeBlockData.get_latest_block] ERROR: Block data offset missing or invalid in LMDB.")
                return None

            file_size = os.path.getsize(self.current_block_file)
            if block_offset >= file_size:
                print(f"[WholeBlockData.get_latest_block] ERROR: Block offset {block_offset} exceeds file size {file_size}.")
                return None

            # ✅ **Retrieve Full Block Data from block.data File**
            print(f"[WholeBlockData.get_latest_block] INFO: Retrieving full block data from offset {block_offset}.")
            full_block = self.get_block_from_data_file(block_offset)
            if not full_block:
                print(f"[WholeBlockData.get_latest_block] ERROR: Failed to load full block {block_hash} from block.data file.")
                print(f"[WholeBlockData.get_latest_block] ❌ WARNING: Block {latest_block_data['block_header']['index']} may be corrupt. Consider reindexing the blockchain.")
                return None

            print(f"[WholeBlockData.get_latest_block] ✅ SUCCESS: Retrieved Block {full_block.index} (Hash: {full_block.hash}).")
            return full_block

        except Exception as e:
            print(f"[WholeBlockData.get_latest_block] ERROR: Failed to retrieve latest block: {e}")
            return None







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
