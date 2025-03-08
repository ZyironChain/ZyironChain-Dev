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
from Zyiron_Chain.utils.deserializer import Deserializer
from Zyiron_Chain.storage.blockmetadata import BlockMetadata
from Zyiron_Chain.storage.tx_storage import TxStorage

import os
from threading import Lock

import struct
from threading import Lock

class WholeBlockData:
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

            # ✅ **Ensure `block_metadata` starts as None**
            self.block_metadata = None  

            # ✅ **Thread safety lock for writing**
            self.write_lock = Lock()

            # ✅ **Set up the blockchain storage directory & block.data file**
            self._setup_block_storage()

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
            self.current_block_offset = 0

            # ✅ **Initialize block data file if necessary**
            self._initialize_block_data_file()

        except Exception as e:
            print(f"[WholeBlockData._setup_block_storage] ❌ ERROR: Failed to initialize block storage directory: {e}")
            raise

    def _write_to_block_data_securely(self, block):
        """
        Serialize and write block data to block.data file securely.
        Ensures data integrity and prevents unnecessary magic number writes.
        """
        try:
            with open(self.current_block_file, "ab") as f:
                offset_before_write = f.tell()  # ✅ Save the starting offset

                serialized_block = self._serialize_block_to_binary(block)
                block_size_bytes = struct.pack(">I", len(serialized_block))

                f.write(block_size_bytes + serialized_block)  # ✅ Prevents extra magic number writes
                f.flush()

                print(f"[WholeBlockData] ✅ Block {block.index} securely stored at offset {offset_before_write}.")

        except Exception as e:
            print(f"[WholeBlockData] ❌ ERROR: Failed to store block {block.index}: {e}")



    def block_meta(self):
        """
        Ensures `BlockMetadata` is initialized and returns the instance.
        ✅ If `block_metadata` is missing, it initializes it with TxStorage automatically.
        """
        try:
            # ✅ **Ensure `block_metadata` is Properly Initialized**
            if not hasattr(self, "block_metadata") or self.block_metadata is None:
                print("[WholeBlockData.block_meta] WARNING: `block_metadata` is missing. Initializing now...")

                # ✅ **Ensure `tx_storage` is Available Before Passing It**
                if not hasattr(self, "tx_storage") or self.tx_storage is None:
                    print("[WholeBlockData.block_meta] ERROR: `tx_storage` is missing. Cannot initialize BlockMetadata.")
                    return None

                # ✅ **Initialize BlockMetadata with TxStorage**
                self.block_metadata = BlockMetadata(tx_storage=self.tx_storage)
                print("[WholeBlockData.block_meta] SUCCESS: `BlockMetadata` initialized successfully.")

            return self.block_metadata  # ✅ **Always Return the `BlockMetadata` Instance**

        except Exception as e:
            print(f"[WholeBlockData.block_meta] ERROR: Failed to initialize BlockMetadata: {e}")
            return None  # ✅ Prevents crashes by returning `None` in case of failure




    def store_block(self, block: Block, difficulty: int):
        """
        Stores a block using `BlockMetadata.store_block()`, ensuring correct storage without redundant magic numbers.

        :param block: The block to store.
        :param difficulty: The difficulty target of the block.
        """
        try:
            print(f"[WholeBlockData.store_block] INFO: Storing Block {block.index} with difficulty {difficulty}.")

            # ✅ **Ensure `BlockMetadata` Exists Before Storing**
            block_metadata_instance = self.block_meta()
            if not block_metadata_instance:
                print("[WholeBlockData.store_block] ERROR: `BlockMetadata` is not initialized. Cannot store block.")
                return

            # ✅ **Use `_serialize_block_to_binary()` Instead of `to_bytes()`**
            block_bytes = self._serialize_block_to_binary(block)

            # ✅ **Verify Block Size Before Writing**
            block_size = len(block_bytes)
            if block_size == 0:
                print(f"[WholeBlockData.store_block] ERROR: Block {block.index} has invalid size. Skipping storage.")
                return

            print(f"[WholeBlockData.store_block] INFO: Block {block.index} size verified: {block_size} bytes.")

            # ✅ **Store the Block Correctly**
            block_metadata_instance.store_block(block, difficulty)

            print(f"[WholeBlockData.store_block] SUCCESS: Block {block.index} stored successfully in block.data.")

        except Exception as e:
            print(f"[WholeBlockData.store_block] ERROR: Failed to store block {block.index}: {e}")
            raise




    def _initialize_block_data_file(self):
        """Initialize block.data file with correct magic number only if it is missing."""
        try:
            # ✅ **Ensure Block Data Directory Exists**
            block_data_dir = Constants.DATABASES.get("block_data")
            if not block_data_dir:
                print("[WholeBlockData._initialize_block_data_file] ERROR: Block data directory not found in Constants.DATABASES.")
                return
            os.makedirs(block_data_dir, exist_ok=True)

            # ✅ **Set Block Data File Path**
            self.current_block_file = os.path.join(block_data_dir, "block.data")
            print(f"[WholeBlockData] INFO: Block data file path set to: {self.current_block_file}")

            # ✅ **Check if File Exists and is Empty**
            file_exists = os.path.exists(self.current_block_file)
            file_is_empty = (os.path.getsize(self.current_block_file) == 0) if file_exists else True

            # ✅ **Write Magic Number Only if File is Missing or Empty**
            if not file_exists or file_is_empty:
                with open(self.current_block_file, "wb") as f:
                    f.write(struct.pack(">I", Constants.MAGIC_NUMBER))
                print(f"[WholeBlockData] INFO: Created block.data with magic number {hex(Constants.MAGIC_NUMBER)}.")
            else:
                print("[WholeBlockData] INFO: block.data file exists. Skipping magic number rewrite.")

            # ✅ **Validate Magic Number in Existing File**
            with open(self.current_block_file, "rb") as f:
                file_magic_number = struct.unpack(">I", f.read(4))[0]
                if file_magic_number != Constants.MAGIC_NUMBER:
                    print(f"[WholeBlockData] ERROR: Invalid magic number in block.data file: {hex(file_magic_number)}. "
                        f"Expected: {hex(Constants.MAGIC_NUMBER)}")
                    return

            print("[WholeBlockData] SUCCESS: Block storage initialized and validated successfully.")

        except Exception as e:
            print(f"[WholeBlockData] ERROR: Failed to initialize block storage: {e}")
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

            # ✅ **Unpack Header Fields**
            header_format = ">I32s32sQI"
            base_header_size = struct.calcsize(header_format)
            (
                block_height,
                prev_block_hash,
                merkle_root,
                timestamp,
                nonce
            ) = struct.unpack(header_format, block_data[:base_header_size])

            # ✅ **Unpack Difficulty**
            difficulty_length_offset = base_header_size
            difficulty_length = struct.unpack(">B", block_data[difficulty_length_offset:difficulty_length_offset + 1])[0]
            difficulty_offset = difficulty_length_offset + 1
            difficulty_bytes = block_data[difficulty_offset:difficulty_offset + difficulty_length]
            difficulty_int = int.from_bytes(difficulty_bytes, "big", signed=False)

            # ✅ **Unpack Miner Address**
            miner_address_offset = difficulty_offset + difficulty_length
            miner_address_bytes = block_data[miner_address_offset:miner_address_offset + 128]
            miner_address_str = miner_address_bytes.rstrip(b'\x00').decode("utf-8")

            # ✅ **Unpack Transaction Count**
            tx_count_offset = miner_address_offset + 128
            tx_count = struct.unpack(">I", block_data[tx_count_offset:tx_count_offset + 4])[0]
            print(f"[WholeBlockData] INFO: Block {block_height} contains {tx_count} transactions.")

            # ✅ **Unpack Transactions (Read Size-Prefixed Transactions)**
            tx_data_offset = tx_count_offset + 4
            transactions = []
            i = 0

            while i < tx_count:
                try:
                    # ✅ **Read Transaction Size First**
                    tx_size = struct.unpack(">I", block_data[tx_data_offset:tx_data_offset + 4])[0]
                    tx_data_offset += 4

                    # ✅ **Extract Transaction JSON Bytes**
                    tx_bytes = block_data[tx_data_offset:tx_data_offset + tx_size]
                    tx_data_offset += tx_size

                    # ✅ **Deserialize Transaction JSON**
                    transactions.append(json.loads(tx_bytes.decode("utf-8")))

                except Exception as e:
                    print(f"[WholeBlockData] ❌ ERROR: Failed to deserialize transaction {i} in block {block_height}: {e}")

                i += 1

            # ✅ **Reconstruct Block Dictionary**
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

            print(f"[WholeBlockData] ✅ SUCCESS: Block {block_height} deserialized successfully.")
            return Block.from_dict(block_dict)

        except Exception as e:
            print(f"[WholeBlockData] ❌ ERROR: Failed to deserialize block: {e}")
            return None  

    def _serialize_block_to_binary(self, block: Block) -> bytes:
        """
        Serialize a Block into binary format.
        Packs the header fields into fixed-length binary and appends transaction data.
        """
        try:
            print(f"[WholeBlockData] INFO: Serializing Block {block.index} to binary.")

            block_dict = block.to_dict()
            header = block_dict["header"]

            # ✅ **Extract Block Header Fields**
            block_height = int(header["index"])
            prev_block_hash = bytes.fromhex(header["previous_hash"])
            merkle_root = bytes.fromhex(header["merkle_root"])
            timestamp = int(header["timestamp"])
            nonce = int(header["nonce"])

            # ✅ **Convert Difficulty Dynamically (Prefix with 1-byte Length + Difficulty Bytes)**
            difficulty_bytes = int(header["difficulty"]).to_bytes(48, "big", signed=False).lstrip(b'\x00')
            difficulty_length = len(difficulty_bytes)
            difficulty_packed = struct.pack(">B", difficulty_length) + difficulty_bytes

            # ✅ **Process Miner Address (Max 128 Bytes, Padded)**
            miner_address_str = header["miner_address"]
            miner_address_encoded = miner_address_str.encode("utf-8")
            if len(miner_address_encoded) > 128:
                raise ValueError("[WholeBlockData] ❌ ERROR: Miner address exceeds 128 bytes.")
            miner_address_padded = miner_address_encoded.ljust(128, b'\x00')

            # ✅ **Pack Header Fields (Index, Previous Hash, Merkle Root, Timestamp, Nonce, Difficulty, Miner Address)**
            header_format = f">I32s32sQI{len(difficulty_packed)}s128s"
            header_data = struct.pack(
                header_format,
                block_height,
                prev_block_hash,
                merkle_root,
                timestamp,
                nonce,
                difficulty_packed,
                miner_address_padded
            )

            # ✅ **Serialize Transactions into Binary Format**
            serialized_transactions = []
            for tx in block_dict["transactions"]:
                try:
                    tx_bytes = json.dumps(tx, sort_keys=True).encode("utf-8")
                    serialized_transactions.append(struct.pack(">I", len(tx_bytes)) + tx_bytes)  # Store each transaction with size prefix
                except Exception as e:
                    print(f"[WholeBlockData] ❌ ERROR: Failed to serialize transaction: {e}")

            tx_data = b"".join(serialized_transactions)
            tx_count = len(serialized_transactions)
            tx_count_data = struct.pack(">I", tx_count)

            # ✅ **Return Complete Serialized Block**
            serialized_block = header_data + tx_count_data + tx_data
            print(f"[WholeBlockData] ✅ SUCCESS: Block {block.index} serialized successfully. Size: {len(serialized_block)} bytes")
            return serialized_block

        except Exception as e:
            print(f"[WholeBlockData] ❌ ERROR: Failed to serialize block {block.index}: {e}")
            raise  


    def get_block_from_data_file(self, offset: int) -> Optional[Block]:
        """
        Retrieve a block from the block.data file using its offset.
        Ensures proper structure reading: [size][block].
        """
        try:
            print(f"[WholeBlockData.get_block_from_data_file] INFO: Retrieving block at offset {offset}.")

            # ✅ **Ensure File Exists Before Reading**
            if not os.path.exists(self.current_block_file):
                print(f"[WholeBlockData.get_block_from_data_file] ERROR: block.data file not found: {self.current_block_file}")
                return None

            file_size = os.path.getsize(self.current_block_file)

            # ✅ **Validate Offset Position**
            if offset < 0 or offset >= file_size - 4:  # Ensure space for at least block size
                print(f"[WholeBlockData.get_block_from_data_file] ERROR: Invalid offset {offset} for file size {file_size}.")
                return None

            with open(self.current_block_file, "rb") as f:
                f.seek(offset, os.SEEK_SET)

                # ✅ **Read Block Size (First 4 Bytes)**
                block_size_bytes = f.read(4)
                if len(block_size_bytes) != 4:
                    print(f"[WholeBlockData.get_block_from_data_file] ERROR: Failed to read block size at offset {offset}.")
                    return None

                block_size = struct.unpack(">I", block_size_bytes)[0]

                # ✅ **Ensure Block Size is Valid**
                if block_size <= 0 or offset + 4 + block_size > file_size:
                    print(f"[WholeBlockData.get_block_from_data_file] ERROR: Invalid block size {block_size} at offset {offset}.")
                    return None

                # ✅ **Read Full Block Data**
                block_data = f.read(block_size)
                if len(block_data) != block_size:
                    print(f"[WholeBlockData.get_block_from_data_file] ERROR: Incomplete block data at offset {offset}. Expected {block_size}, got {len(block_data)}.")
                    return None

                # ✅ **Deserialize Block**
                block = self._deserialize_block_from_binary(block_data)
                if not block:
                    print(f"[WholeBlockData.get_block_from_data_file] ERROR: Failed to deserialize block at offset {offset}.")
                    return None

                print(f"[WholeBlockData.get_block_from_data_file] SUCCESS: Retrieved Block {block.index} (Hash: {block.hash}) from offset {offset}.")
                return block

        except Exception as e:
            print(f"[WholeBlockData.get_block_from_data_file] ERROR: Exception retrieving block from data file: {e}")
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
