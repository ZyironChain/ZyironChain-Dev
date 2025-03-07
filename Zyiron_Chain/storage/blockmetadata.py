import os
import sys
import struct
import json
import pickle
import time
import hashlib
from decimal import Decimal
from typing import Optional, List, Dict

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
      - Ensure blocks are stored with correct magic numbers.
      - Use single SHA3-384 hashing.
      - Provide detailed print statements for every major step and error.
    """

    def __init__(self, tx_storage: Optional[TxStorage] = None):
        """
        Initializes BlockMetadata:
        - Sets up LMDB storage for block metadata.
        - Initializes TxStorage for transaction indexing.
        - Manages block data file paths and ensures correct initialization.
        """
        try:
            print("[BlockMetadata.__init__] INFO: Initializing BlockMetadata...")

            # ✅ Initialize LMDB for block metadata
            self.block_metadata_db = LMDBManager(Constants.DATABASES["block_metadata"])

            # ✅ Ensure TxStorage is provided
            if tx_storage is None:
                raise ValueError("[BlockMetadata.__init__] ERROR: TxStorage instance is required.")
            self.tx_storage = tx_storage

            # ✅ Set block data file path dynamically
            block_data_folder = Constants.DATABASES.get("block_data")
            if not block_data_folder:
                raise ValueError("[BlockMetadata.__init__] ERROR: 'block_data' path missing in Constants.DATABASES.")

            os.makedirs(block_data_folder, exist_ok=True)  # Ensure directory exists
            self.current_block_file = os.path.join(block_data_folder, "block_00001.data")
            self.current_block_offset = 0

            # ✅ Initialize block data file with correct magic number
            self._initialize_block_data_file()

            print("[BlockMetadata.__init__] SUCCESS: Initialized BlockMetadata with LMDB and TxStorage.")

        except Exception as e:
            print(f"[BlockMetadata.__init__] ERROR: Initialization failed: {e}")
            raise


    def get_block_metadata(self, block_hash):
        """Retrieve block metadata and deserialize if needed."""
        data = self.block_metadata_db.get(block_hash.encode("utf-8"))
        return Deserializer().deserialize(data) if data else None

    def create_block_data_file(self, block: Block):
        """
        Append a block to the block.data file in binary format.
        Writes the block length (4 bytes) followed by the serialized block.
        """
        try:
            if not self.current_block_file:
                raise ValueError("[BlockMetadata.create_block_data_file] ERROR: Current block file is not set.")

            # ✅ Ensure block file rollover is handled before writing the new block
            self._handle_block_file_rollover()

            with open(self.current_block_file, "ab+") as f:
                f.seek(0, os.SEEK_END)

                # ✅ Ensure the magic number is written **ONLY ONCE** at the start of the file
                if f.tell() == 0:
                    f.write(struct.pack(">I", Constants.MAGIC_NUMBER))
                    print(f"[BlockMetadata.create_block_data_file] INFO: Wrote network magic number {hex(Constants.MAGIC_NUMBER)} to block.data.")

                # ✅ Serialize block to binary format
                block_data = self._serialize_block_to_binary(block)

                # ✅ Write block size (4 bytes) followed by block data
                block_size_bytes = len(block_data).to_bytes(4, byteorder='big')
                f.write(block_size_bytes)
                f.write(block_data)

                # ✅ Update block offset
                self.current_block_offset = f.tell()
                print(f"[BlockMetadata.create_block_data_file] SUCCESS: Appended Block {block.index} to block.data file at offset {self.current_block_offset}.")

        except Exception as e:
            print(f"[BlockMetadata.create_block_data_file] ERROR: Failed to write block to block.data file: {e}")
            raise


    def _initialize_block_data_file(self):
        """Initialize the block.data file with the correct magic number."""
        try:
            os.makedirs(os.path.dirname(self.current_block_file), exist_ok=True)
            file_is_new_or_empty = (not os.path.exists(self.current_block_file) or os.path.getsize(self.current_block_file) == 0)
            if file_is_new_or_empty:
                with open(self.current_block_file, "wb") as f:
                    f.write(struct.pack(">I", Constants.MAGIC_NUMBER))
                print(f"[BlockMetadata._initialize_block_data_file] INFO: Created block.data with magic number {hex(Constants.MAGIC_NUMBER)}.")
            else:
                print("[BlockMetadata._initialize_block_data_file] INFO: block.data file exists. Skipping magic number write.")
            with open(self.current_block_file, "rb") as f:
                file_magic_number = struct.unpack(">I", f.read(4))[0]
                if file_magic_number != Constants.MAGIC_NUMBER:
                    print(f"[BlockMetadata._initialize_block_data_file] ERROR: Invalid magic number in block.data file: {hex(file_magic_number)}. Expected {hex(Constants.MAGIC_NUMBER)}.")
                    return None
            print("[BlockMetadata._initialize_block_data_file] INFO: Block.data file validated successfully.")
        except Exception as e:
            print(f"[BlockMetadata._initialize_block_data_file] ERROR: Failed to initialize block.data file: {e}")
            raise




    def store_block(self, block, difficulty):
        """
        Store block metadata in LMDB, index transactions, and append full block data to block.data.

        Steps:
        1. Compute Merkle root if missing.
        2. Preserve explicitly mined hash (NO recomputation).
        3. Prepare detailed block metadata (miner address, reward, difficulty, fees, transactions).
        4. Store block metadata in LMDB.
        5. Index each transaction in txindex.lmdb.
        6. Serialize and append entire block data (WITHOUT MAGIC NUMBER) to block.data.
        7. Handle block file rollover based on Constants.BLOCK_DATA_FILE_SIZE_MB.
        """
        try:
            print(f"[BlockMetadata.store_block] INFO: Starting storage for Block {block.index}...")

            # Step 1: Compute Merkle root if missing explicitly
            if not hasattr(block, "merkle_root") or not block.merkle_root:
                print(f"[BlockMetadata.store_block] WARNING: Merkle root missing for Block {block.index}. Recomputing...")
                block.merkle_root = block._compute_merkle_root()
                print(f"[BlockMetadata.store_block] INFO: Merkle root computed: {block.merkle_root}.")

            # Step 2: Explicitly preserve existing mined hash (NO recomputation)
            print(f"[BlockMetadata.store_block] INFO: Using preserved mined hash {block.hash} for Block {block.index}.")

            # Step 3: Serialize transactions
            print(f"[BlockMetadata.store_block] INFO: Serializing transactions for Block {block.index}...")
            serialized_transactions = []
            for tx in block.transactions:
                if hasattr(tx, "to_dict"):
                    serialized_transactions.append(tx.to_dict())
                elif isinstance(tx, dict):
                    serialized_transactions.append(tx)
                else:
                    raise TypeError(f"[BlockMetadata.store_block] ERROR: Transaction serialization failed: {tx}")

            # Extract coinbase transaction
            coinbase_tx = next(
                (tx for tx in block.transactions if getattr(tx, 'tx_type', None) == "COINBASE"), None
            )
            miner_address = coinbase_tx.outputs[0].script_pub_key if coinbase_tx else block.miner_address
            reward_amount = coinbase_tx.outputs[0].amount if coinbase_tx else Constants.INITIAL_COINBASE_REWARD
            total_fees = sum(Decimal(str(tx.get('fee', 0))) for tx in serialized_transactions)
            print(f"[BlockMetadata.store_block] INFO: Total fees for Block {block.index}: {total_fees} ZYC.")

            # Step 4: Prepare block metadata
            print(f"[BlockMetadata.store_block] INFO: Preparing block metadata for Block {block.index}...")
            block_dict = {
                "index": block.index,
                "previous_hash": block.previous_hash,
                "merkle_root": block.merkle_root,
                "timestamp": block.timestamp,
                "nonce": block.nonce,
                "difficulty": difficulty,
                "miner_address": miner_address,
                "reward": str(reward_amount),
                "fees": str(total_fees),
                "version": block.version,
                "transactions": serialized_transactions,
                "hash": block.hash
            }

            block_metadata = {
                "hash": block.hash,
                "block_header": block_dict,
                "transaction_count": len(serialized_transactions),
                "block_size": len(json.dumps(block_dict).encode("utf-8")),
                "data_file": self.current_block_file,
                "data_offset": self.current_block_offset,
                "tx_ids": [tx["tx_id"] for tx in serialized_transactions]
            }

            # Step 5: Store metadata in LMDB
            print(f"[BlockMetadata.store_block] INFO: Storing metadata in LMDB for Block {block.index}...")
            with self.block_metadata_db.env.begin(write=True) as txn:
                lmdb_key = f"block:{block.hash}".encode("utf-8")
                txn.put(lmdb_key, json.dumps(block_metadata).encode("utf-8"))
                print(f"[BlockMetadata.store_block] INFO: Metadata stored in LMDB for Block {block.index}.")

            # Step 6: Index transactions in txindex.lmdb
            print(f"[BlockMetadata.store_block] INFO: Indexing transactions for Block {block.index}...")
            for tx in serialized_transactions:
                tx_id = tx["tx_id"]
                inputs = tx.get("inputs", [])
                outputs = tx.get("outputs", [])
                timestamp = tx.get("timestamp", int(time.time()))
                self.tx_storage.store_transaction(tx_id, block.hash, inputs, outputs, timestamp)
                print(f"[BlockMetadata.store_block] INFO: Indexed transaction {tx_id} for Block {block.index}.")

            # Step 7: Append block data to block.data file
            print(f"[BlockMetadata.store_block] INFO: Appending block data to block.data file...")

            block_bytes = json.dumps(block_dict, ensure_ascii=False).encode('utf-8')
            block_size_bytes = len(block_bytes).to_bytes(4, byteorder='big')

            serialized_block_full = block_size_bytes + block_bytes  # ✅ No magic number added

            current_file_path = self._get_current_block_file()
            with open(current_file_path, "ab") as block_file:
                offset_before_write = block_file.tell()
                block_file.write(serialized_block_full)
                block_file.flush()
                print(f"[BlockMetadata.store_block] SUCCESS: Block {block.index} written to block.data at offset {offset_before_write}.")

                # Step 8: Handle block file rollover
                current_file_size_mb = block_file.tell() / (1024 * 1024)
                if current_file_size_mb >= Constants.BLOCK_DATA_FILE_SIZE_MB:
                    print(f"[BlockMetadata.store_block] INFO: File {current_file_path} reached size limit ({Constants.BLOCK_DATA_FILE_SIZE_MB} MB). New file will be created on next block.")

            print(f"[BlockMetadata.store_block] SUCCESS: Block {block.index} fully stored and indexed successfully.")

        except Exception as e:
            print(f"[BlockMetadata.store_block] ERROR: Exception while storing Block {block.index}: {e}")
            raise


    def _serialize_transactions(self, transactions: list):
        """
        Explicitly convert transactions into dictionary format, handling both Transaction objects and dicts.

        :param transactions: List of transactions (Transaction instances or dictionaries).
        :return: List of transaction dictionaries.
        """
        serialized_transactions = []
        for idx, tx in enumerate(transactions):
            if hasattr(tx, "to_dict") and callable(getattr(tx, "to_dict")):
                serialized_tx = tx.to_dict()
                print(f"[BlockMetadata._serialize_transactions] INFO: Transaction at index {idx} serialized from object.")
            elif isinstance(tx, dict):
                serialized_tx = tx
                print(f"[BlockMetadata._serialize_transactions] INFO: Transaction at index {idx} already a dictionary.")
            else:
                raise TypeError(f"[BlockMetadata._serialize_transactions] ERROR: Transaction at index {idx} is neither dict nor object with to_dict.")
            serialized_transactions.append(serialized_tx)
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
        Validate that a block contains all required fields and that its hash is correct.
        """
        required_fields = ["index", "hash", "header", "transactions", "merkle_root", "timestamp", "difficulty"]
        if not isinstance(block, Block):
            print(f"[BlockMetadata.validate_block_structure] ERROR: Invalid block type: {type(block)}")
            return False
        missing_fields = [field for field in required_fields if not hasattr(block, field)]
        if missing_fields:
            print(f"[BlockMetadata.validate_block_structure] ERROR: Block {block.index} is missing fields: {missing_fields}")
            return False
        calculated_hash = block.calculate_hash()
        if block.hash != calculated_hash:
            print(f"[BlockMetadata.validate_block_structure] ERROR: Block {block.index} has an invalid hash. Expected {calculated_hash}, got {block.hash}")
            return False
        if not isinstance(block.transactions, list) or not all(isinstance(tx, dict) for tx in block.transactions):
            print(f"[BlockMetadata.validate_block_structure] ERROR: Block {block.index} contains invalid transactions.")
            return False
        print(f"[BlockMetadata.validate_block_structure] INFO: Block {block.index} passed structure validation.")
        return True

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
        Packs the header fields into fixed-length binary and appends transaction data.
        """
        try:
            print(f"[BlockMetadata] INFO: Serializing Block {block.index} to binary.")

            block_dict = block.to_dict()
            header = block_dict["header"]

            # Extract block header fields
            block_height = int(header["index"])
            prev_block_hash = bytes.fromhex(header["previous_hash"])
            merkle_root = bytes.fromhex(header["merkle_root"])
            timestamp = int(header["timestamp"])
            nonce = int(header["nonce"])
            difficulty_bytes = int(header["difficulty"]).to_bytes(128, "big", signed=False).lstrip(b"\x00")

            # ✅ Dynamic Difficulty Length Storage
            difficulty_length = len(difficulty_bytes)  # Length of difficulty field (1-128 bytes)
            if difficulty_length > 128:
                raise ValueError(f"[BlockMetadata] ERROR: Difficulty length {difficulty_length} exceeds 128 bytes.")

            # ✅ Process miner address (max 128 bytes, padded)
            miner_address_str = header["miner_address"]
            miner_address_encoded = miner_address_str.encode("utf-8")
            if len(miner_address_encoded) > 128:
                raise ValueError("[BlockMetadata] ERROR: Miner address exceeds 128 bytes.")
            miner_address_padded = miner_address_encoded.ljust(128, b'\x00')

            # ✅ Pack header fields with Dynamic Difficulty Length
            header_format = f">I48s48sQI B{difficulty_length}s 128s"
            header_data = struct.pack(
                header_format,
                block_height,
                prev_block_hash,
                merkle_root,
                timestamp,
                nonce,
                difficulty_length,  # ✅ 1-byte difficulty length
                difficulty_bytes,    # ✅ Dynamic difficulty size
                miner_address_padded
            )

            print(f"[BlockMetadata] INFO: Difficulty stored as {difficulty_length} bytes.")

            # ✅ Serialize transactions as JSON and encode as bytes
            tx_data_list = []
            for tx in block_dict["transactions"]:
                try:
                    tx_json = json.dumps(tx, sort_keys=True)
                    tx_data_list.append(tx_json)
                except Exception as e:
                    print(f"[BlockMetadata] ERROR: Failed to serialize transaction: {e}")

            tx_data = "\n".join(tx_data_list).encode("utf-8")
            tx_count = len(block_dict["transactions"])
            tx_count_data = struct.pack(">I", tx_count)

            # ✅ Return complete serialized block
            serialized_block = header_data + tx_count_data + tx_data
            print(f"[BlockMetadata] SUCCESS: Block {block.index} serialized successfully. Size: {len(serialized_block)} bytes")
            return serialized_block

        except Exception as e:
            print(f"[BlockMetadata] ERROR: Failed to serialize block {block.index}: {e}")
            raise




    def get_block_from_data_file(self, offset: int):
        """
        Retrieve a block from block.data using its offset.
        Ensures block size validity before reading the block.
        """
        try:
            print(f"[BlockMetadata.get_block_from_data_file] INFO: Attempting to retrieve block at offset {offset}.")

            # Check if file exists before reading
            if not os.path.exists(self.current_block_file):
                print(f"[BlockMetadata.get_block_from_data_file] ERROR: block.data file not found: {self.current_block_file}")
                return None

            file_size = os.path.getsize(self.current_block_file)
            print(f"[BlockMetadata.get_block_from_data_file] INFO: File size of block.data: {file_size} bytes.")

            # Ensure offset is within file size
            if offset >= file_size:
                print(f"[BlockMetadata.get_block_from_data_file] ERROR: Offset {offset} is out of bounds.")
                return None

            with open(self.current_block_file, "rb") as f:
                f.seek(offset)  # ✅ Start at exact offset (No Magic Number Skipping)

                # Read block size
                block_size_bytes = f.read(4)
                if len(block_size_bytes) != 4:
                    print("[BlockMetadata.get_block_from_data_file] ERROR: Failed to read block size from file.")
                    return None

                block_size = struct.unpack(">I", block_size_bytes)[0]
                print(f"[BlockMetadata.get_block_from_data_file] INFO: Block size read as {block_size} bytes.")

                # Validate block size
                if block_size <= 0 or (offset + 4 + block_size) > file_size:
                    print(f"[BlockMetadata.get_block_from_data_file] ERROR: Invalid block size {block_size} at offset {offset}.")
                    return None

                # Read block data
                block_data = f.read(block_size)
                if len(block_data) != block_size:
                    print(f"[BlockMetadata.get_block_from_data_file] ERROR: Read {len(block_data)} bytes, expected {block_size}.")
                    return None

                print(f"[BlockMetadata.get_block_from_data_file] SUCCESS: Successfully retrieved block from offset {offset}.")
                return block_data

        except Exception as e:
            print(f"[BlockMetadata.get_block_from_data_file] ERROR: Failed to retrieve block from file: {e}")
            return None



    def get_latest_block(self) -> Optional[Block]:
        """
        Retrieve the latest block from LMDB and the block.data file.
        Ensures correct sorting, validation, and prevents chain corruption.
        """
        try:
            print("[BlockMetadata.get_latest_block] INFO: Retrieving latest block from LMDB...")

            all_blocks = []
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                print("[BlockMetadata.get_latest_block] INFO: Iterating through LMDB entries...")

                for key, value in cursor:
                    if key.startswith(b"block:"):
                        try:
                            block_metadata = json.loads(value.decode("utf-8"))

                            # Validate block metadata structure
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

            # Ensure at least one valid block was found
            if not all_blocks:
                print("[BlockMetadata.get_latest_block] WARNING: No blocks found in LMDB. Chain may be empty.")
                return None

            # Sort blocks by index and ensure proper chain integrity
            sorted_blocks = sorted(all_blocks, key=lambda b: b["block_header"]["index"])
            latest_block_data = sorted_blocks[-1]

            # Validate block hash format
            block_hash = latest_block_data.get("hash", Constants.ZERO_HASH)
            if not isinstance(block_hash, str) or len(block_hash) != 96:
                print(f"[BlockMetadata.get_latest_block] ERROR: Invalid block hash format: {block_hash}")
                return None

            # Validate required header fields
            required_keys = {"index", "previous_hash", "timestamp", "nonce", "difficulty"}
            header = latest_block_data["block_header"]
            if not required_keys.issubset(header):
                print(f"[BlockMetadata.get_latest_block] ERROR: Incomplete block metadata: {latest_block_data}")
                return None

            # Validate timestamp
            try:
                timestamp = int(header["timestamp"])
                if timestamp <= 0:
                    raise ValueError("Invalid timestamp")
            except (ValueError, TypeError) as e:
                print(f"[BlockMetadata.get_latest_block] ERROR: Invalid timestamp: {e}")
                return None

            # Verify `block.data` file exists and contains valid magic number
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

            # Retrieve full block data from block.data file
            block_offset = latest_block_data.get("data_offset")
            if not isinstance(block_offset, int):
                print("[BlockMetadata.get_latest_block] ERROR: Block data offset missing or invalid in LMDB.")
                return None

            print(f"[BlockMetadata.get_latest_block] INFO: Retrieving full block data from offset {block_offset}.")
            full_block = self.get_block_from_data_file(block_offset)
            if not full_block:
                print(f"[BlockMetadata.get_latest_block] ERROR: Failed to load full block {block_hash} from block.data file.")
                return None

            print(f"[BlockMetadata.get_latest_block] SUCCESS: Successfully retrieved Block {full_block.index} (Hash: {full_block.hash}).")
            return full_block

        except Exception as e:
            print(f"[BlockMetadata.get_latest_block] ERROR: Failed to retrieve latest block: {e}")
            return None

    def get_total_mined_supply(self) -> Decimal:
        """
        Calculate total mined coin supply by summing all Coinbase rewards from stored blocks.
        Caches the result in LMDB for future fast retrieval.
        """
        try:
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
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.decode().startswith("block:"):
                        try:
                            block_metadata = json.loads(value.decode("utf-8"))
                            transactions = block_metadata.get("tx_ids", [])
                            if transactions:
                                for tx_id in transactions:
                                    tx_key = f"tx:{tx_id}".encode("utf-8")
                                    tx_data = self.txindex_db.get(tx_key)
                                    if not tx_data:
                                        print(f"[BlockMetadata.get_total_mined_supply] WARNING: Missing transaction {tx_id} in txindex.")
                                        continue
                                    try:
                                        tx_details = json.loads(tx_data.decode("utf-8"))
                                        if tx_details.get("type") == "COINBASE":
                                            outputs = tx_details.get("outputs", [])
                                            if outputs and isinstance(outputs, list):
                                                for output in outputs:
                                                    if "amount" in output:
                                                        total_supply += Decimal(str(output["amount"]))
                                    except json.JSONDecodeError as json_error:
                                        print(f"[BlockMetadata.get_total_mined_supply] ERROR: Failed to parse transaction {tx_id}: {json_error}")
                                        continue
                        except json.JSONDecodeError as e:
                            print(f"[BlockMetadata.get_total_mined_supply] ERROR: Failed to parse block metadata: {e}")
                            continue
            with self.block_metadata_db.env.begin(write=True) as txn:
                txn.put(b"total_mined_supply", str(total_supply).encode("utf-8"))
            print(f"[BlockMetadata.get_total_mined_supply] INFO: Total mined supply calculated and cached: {total_supply} ZYC")
            return total_supply
        except Exception as e:
            print(f"[BlockMetadata.get_total_mined_supply] ERROR: Failed to calculate total mined supply: {e}")
            return Decimal("0")

    def load_chain(self) -> List[Dict]:
        """
        Load blockchain data from LMDB and return as a list of dictionaries.
        """
        try:
            print("[BlockMetadata.load_chain] INFO: Loading blockchain data from LMDB...")
            blockchain_db = self._get_database("block_metadata")
            raw_blocks = blockchain_db.get_all_blocks()
            self.chain = []
            for block in raw_blocks:
                if isinstance(block, bytes):
                    try:
                        block = pickle.loads(block)
                    except Exception as e:
                        print(f"[BlockMetadata.load_chain] ERROR: Failed to decode block: {e}")
                        continue
                if "hash" not in block or not isinstance(block["hash"], str):
                    print(f"[BlockMetadata.load_chain] WARNING: Block missing 'hash': {block}")
                    continue
                self.chain.append(block)
            print(f"[BlockMetadata.load_chain] INFO: Loaded {len(self.chain)} blocks from LMDB.")
            return self.chain
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
        Retrieve all block headers from the LMDB storage.

        Returns:
            List[Dict]: A list of block headers, where each header is a dictionary.
        """
        try:
            print("[BlockMetadata.get_all_block_headers] INFO: Retrieving all block headers...")
            headers = []
            
            # Open a read transaction for the LMDB database
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                
                # Iterate through all key-value pairs in the database
                for key, value in cursor:
                    # Filter for keys that start with "block:"
                    if key.decode().startswith("block:"):
                        try:
                            # Deserialize the block metadata
                            block_meta = json.loads(value.decode("utf-8"))
                            
                            # Extract the block header
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
        Retrieve all stored blocks from the blocks.data file and LMDB as a list of dictionaries.
        Ensures proper block retrieval without treating magic numbers incorrectly.
        """
        try:
            print("[BlockMetadata.get_all_blocks] INFO: Retrieving all blocks from storage...")
            blocks = []

            if not os.path.exists(self.current_block_file):
                print(f"[BlockMetadata.get_all_blocks] ERROR: blocks.data file not found at {self.current_block_file}.")
                return []

            with open(self.current_block_file, "rb") as f:
                file_size = os.path.getsize(self.current_block_file)
                print(f"[BlockMetadata.get_all_blocks] INFO: File size of block.data: {file_size} bytes.")

                # ✅ Read the global magic number (first 4 bytes only)
                global_magic_number = f.read(4)
                if global_magic_number != struct.pack(">I", Constants.MAGIC_NUMBER):
                    print(f"[BlockMetadata.get_all_blocks] ERROR: Invalid magic number {global_magic_number.hex()} at start of file. Expected {hex(Constants.MAGIC_NUMBER)}")
                    return []

                while True:
                    # ✅ Read block size
                    block_size_bytes = f.read(4)
                    if not block_size_bytes:
                        break  # End of file

                    if len(block_size_bytes) != 4:
                        print("[BlockMetadata.get_all_blocks] ERROR: Incomplete block size field. File may be corrupted.")
                        break

                    block_size = struct.unpack(">I", block_size_bytes)[0]
                    if block_size <= 0 or block_size > Constants.MAX_BLOCK_SIZE_BYTES:
                        print(f"[BlockMetadata.get_all_blocks] ERROR: Invalid block size {block_size}. Skipping block.")
                        continue

                    # ✅ Read block data
                    block_data = f.read(block_size)
                    if len(block_data) != block_size:
                        print(f"[BlockMetadata.get_all_blocks] ERROR: Incomplete block data. Expected {block_size}, got {len(block_data)}.")
                        continue

                    # ✅ Deserialize block
                    try:
                        block_dict = json.loads(block_data.decode("utf-8"))
                        blocks.append(block_dict)
                    except json.JSONDecodeError as e:
                        print(f"[BlockMetadata.get_all_blocks] ERROR: Failed to decode block data: {e}")
                        continue

            # ✅ Sort blocks and validate chain continuity
            blocks.sort(key=lambda b: b["header"]["index"])
            prev_hash = Constants.ZERO_HASH

            for block in blocks:
                current_hash = block["hash"]
                if block["header"]["previous_hash"] != prev_hash:
                    print(f"[BlockMetadata.get_all_blocks] ERROR: Chain discontinuity at block {block['header']['index']}. "
                        f"Prev hash {block['header']['previous_hash']} vs expected {prev_hash}")
                    return []  # Prevent returning corrupted chains
                prev_hash = current_hash

            print(f"[BlockMetadata.get_all_blocks] SUCCESS: Retrieved {len(blocks)} valid blocks.")
            return blocks

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





    def get_block_by_tx_id(self, tx_id: str):
        """
        Retrieve a block using a transaction ID from the txindex database.

        :param tx_id: Transaction ID to look up.
        :return: The block containing the transaction, or None if not found.
        """
        try:
            print(f"[BlockMetadata.get_block_by_tx_id] INFO: Searching for block containing transaction {tx_id}...")

            # Retrieve the block hash associated with the transaction ID
            tx_key = f"tx:{tx_id}".encode("utf-8")
            with self.txindex_db.env.begin() as txn:
                block_hash_bytes = txn.get(tx_key)

            if not block_hash_bytes:
                print(f"[BlockMetadata.get_block_by_tx_id] WARNING: No block found for transaction {tx_id}.")
                return None

            block_hash = block_hash_bytes.decode("utf-8")
            print(f"[BlockMetadata.get_block_by_tx_id] INFO: Transaction {tx_id} found in block {block_hash}.")

            # Retrieve block metadata
            block_key = f"block:{block_hash}".encode("utf-8")
            with self.block_metadata_db.env.begin() as txn:
                block_data_bytes = txn.get(block_key)

            if not block_data_bytes:
                print(f"[BlockMetadata.get_block_by_tx_id] WARNING: Block metadata missing for hash {block_hash}.")
                return None

            block_metadata = json.loads(block_data_bytes.decode("utf-8"))
            if not isinstance(block_metadata, dict) or "block_header" not in block_metadata:
                print(f"[BlockMetadata.get_block_by_tx_id] ERROR: Invalid block metadata format for {block_hash}.")
                return None

            # Deserialize the block
            return Block.from_dict(block_metadata["block_header"])

        except Exception as e:
            print(f"[BlockMetadata.get_block_by_tx_id] ERROR: Failed to retrieve block by transaction ID {tx_id}: {e}")
            return None



    def get_transaction_id(self, tx_label: str) -> str:
        """
        Retrieves a stored transaction ID using a label (e.g., "GENESIS_COINBASE").
        :param tx_label: A string label for the transaction to retrieve.
        :return: The stored transaction ID as a hex string.
        """
        try:
            print(f"[BlockMetadata.get_transaction_id] INFO: Retrieving transaction ID for label '{tx_label}'...")

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
        """Purges corrupted blockchain data."""
        print("[BlockMetadata.purge_chain] .......")

    @staticmethod
    def _serialize_to_bytes(data) -> bytes:
        """
        Converts data into a JSON-encoded byte format.
        Ensures all storage and retrieval operations use bytes.
        """
        if isinstance(data, dict):
            return json.dumps(data, ensure_ascii=False).encode("utf-8")
        elif isinstance(data, str):
            return data.encode("utf-8")
        elif isinstance(data, bytes):
            return data  # Already bytes, return as is
        else:
            raise TypeError(f"Unsupported data type for serialization: {type(data)}")

    @staticmethod
    def _deserialize_from_bytes(data: bytes):
        """
        Decodes a JSON-encoded byte format back into a dictionary or string.
        Ensures correct retrieval from storage.
        """
        if isinstance(data, bytes):
            try:
                return json.loads(data.decode("utf-8"))  # Convert bytes to dict
            except json.JSONDecodeError:
                return data.decode("utf-8")  # Convert to string if not JSON
        return data  # Return as is if not bytes



    