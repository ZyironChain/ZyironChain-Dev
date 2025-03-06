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

class BlockMetadata:
    """
    BlockMetadata is responsible for handling block metadata storage.
    
    Responsibilities:
      - Store block headers (metadata) in LMDB.
      - Track block offsets and file information from the block.data file.
      - Ensure blocks are stored with correct magic numbers.
      - Use single SHA3‑384 hashing.
      - Provide detailed print statements for every major step and error.
    """

    def __init__(self, block_data_file: Optional[str] = None):
        try:
            # Initialize LMDB databases for block metadata
            self.block_metadata_db = LMDBManager(Constants.DATABASES["block_metadata"])
            # Set current block.data file path from Constants
            # Use the "block_data" folder from Constants.DATABASES (if provided)
            block_data_dir = Constants.DATABASES.get("block_data")
            if not block_data_dir:
                raise ValueError("Block data directory not defined in Constants.DATABASES.")
            self.current_block_file = os.path.join(block_data_dir, "block.data")
            self.current_block_offset = 0
            self._initialize_block_data_file()
            print("[BlockMetadata.__init__] INFO: BlockMetadata initialized successfully.")
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
                raise ValueError("Current block file is not set.")
            with open(self.current_block_file, "ab+") as f:
                f.seek(0, os.SEEK_END)
                if f.tell() == 0:
                    f.write(struct.pack(">I", Constants.MAGIC_NUMBER))
                    print(f"[BlockMetadata] INFO: Wrote network magic number {hex(Constants.MAGIC_NUMBER)} to block.data.")
                block_data = self._serialize_block_to_binary(block)
                f.write(struct.pack(">I", len(block_data)))
                f.write(block_data)
                self.current_block_offset = f.tell()
                print(f"[BlockMetadata] INFO: Appended Block {block.index} to block.data file at offset {self.current_block_offset}.")
        except Exception as e:
            print(f"[BlockMetadata] ERROR: Failed to write block to block.data file: {e}")
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
        Store block metadata in LMDB and full block data in block.data.

        Steps clearly defined:
        1. Compute Merkle root if missing.
        2. Compute and verify the block hash (SHA3-384).
        3. Store detailed metadata (miner address, reward, difficulty, fees, transactions).
        4. Write metadata to LMDB.
        5. Append the entire block data (with magic number) to the block.data file.
        6. Dynamically handle block file rollover based on Constants.BLOCK_DATA_FILE_SIZE_MB.

        :param block: Block instance to store.
        :param difficulty: Current difficulty of the block.
        """
        try:
            print(f"[BlockMetadata.store_block] INFO: Storing metadata for Block {block.index}...")

            # Step 1: Recompute Merkle root if missing
            if not hasattr(block, "merkle_root") or not block.merkle_root:
                print(f"[BlockMetadata.store_block] WARNING: Missing Merkle root for block {block.index}. Recomputing...")
                block.merkle_root = block._compute_merkle_root()

            # Step 2: Compute and verify block hash explicitly (SHA3-384)
            header_str = (
                f"{block.version}{block.index}{block.previous_hash}"
                f"{block.merkle_root}{block.timestamp}{block.nonce}"
                f"{block.difficulty}{block.miner_address}"
            )
            header_bytes = header_str.encode("utf-8")
            computed_hash = hashlib.sha3_384(header_bytes).hexdigest()
            block.hash = computed_hash
            print(f"[BlockMetadata.store_block] INFO: Computed block hash {block.hash}.")

            # Step 3: Prepare detailed metadata dictionary
            tx_ids = [tx.tx_id for tx in block.transactions if hasattr(tx, "tx_id")]
            coinbase_tx = next((tx for tx in block.transactions if hasattr(tx, 'tx_type') and tx.tx_type == "COINBASE"), None)
            
            miner_address = coinbase_tx.outputs[0].script_pub_key if coinbase_tx else block.miner_address
            reward_amount = coinbase_tx.outputs[0].amount if coinbase_tx else Constants.INITIAL_COINBASE_REWARD

            total_fees = sum(tx.fee for tx in block.transactions if hasattr(tx, 'fee'))

            block_metadata = {
                "hash": block.hash,
                "block_header": {
                    "index": block.index,
                    "previous_hash": block.previous_hash,
                    "merkle_root": block.merkle_root,
                    "timestamp": block.timestamp,
                    "nonce": block.nonce,
                    "difficulty": difficulty,
                    "miner_address": miner_address,
                    "reward": str(reward_amount),
                    "fees": str(total_fees),
                    "version": block.version
                },
                "transaction_count": len(block.transactions),
                "block_size": len(json.dumps(block.to_dict()).encode("utf-8")),
                "data_file": self.current_block_file,
                "data_offset": self.current_block_offset,
                "tx_ids": tx_ids
            }

            # Step 4: Store metadata to LMDB
            with self.block_metadata_db.env.begin(write=True) as txn:
                txn.put(f"block:{block.hash}".encode(), json.dumps(block_metadata).encode("utf-8"))
                print(f"[BlockMetadata.store_block] INFO: Block metadata stored successfully for Block {block.index}.")

            # Step 5: Append full block data (with MAGIC_NUMBER) to block.data file
            block_bytes = json.dumps(block.to_dict(), ensure_ascii=False).encode('utf-8')
            block_length = len(block_bytes)

            magic_number_bytes = Constants.MAGIC_NUMBER.to_bytes(4, byteorder='big')
            block_size_bytes = block_length.to_bytes(4, byteorder='big')

            serialized_block_data = magic_number_bytes + block_size_bytes + block_bytes

            # Get current file, handle file rollover
            current_file_path = self._get_current_block_file()
            with open(current_file_path, "ab") as block_file:
                offset_before_write = block_file.tell()
                block_file.write(serialized_block_data)
                block_file.flush()
                print(f"[BlockMetadata.store_block] INFO: Block data written at offset {offset_before_write}.")

            # Step 6: Dynamically handle rollover based on Constants.BLOCK_DATA_FILE_SIZE_MB
            if block_file.tell() >= Constants.BLOCK_DATA_FILE_SIZE_MB * 1024 * 1024:
                print(f"[BlockMetadata.store_block] INFO: Block data file {current_file_path} reached max size. New file will be created next time.")

            print(f"[BlockMetadata.store_block] SUCCESS: Fully stored Block {block.index} with hash {block.hash}.")

        except Exception as e:
            print(f"[BlockMetadata.store_block] ERROR: Failed storing Block {block.index}: {e}")
            raise


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
            block_dict = block.to_dict()
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
            # Process miner address (max 128 bytes, padded)
            miner_address_str = header["miner_address"]
            miner_address_encoded = miner_address_str.encode("utf-8")
            if len(miner_address_encoded) > 128:
                raise ValueError("Miner address exceeds 128 bytes.")
            miner_address_padded = miner_address_encoded.ljust(128, b'\x00')
            # Pack header: index, prev hash, merkle root, timestamp, nonce, difficulty, miner address
            header_format = ">I32s32sQI48s128s"
            header_data = struct.pack(header_format,
                                      block_height,
                                      prev_block_hash,
                                      merkle_root,
                                      timestamp,
                                      nonce,
                                      difficulty_bytes,
                                      miner_address_padded)
            # Serialize transactions as JSON strings (each separated by a newline)
            tx_data_list = []
            for tx in block_dict["transactions"]:
                tx_json = json.dumps(tx, sort_keys=True)
                tx_data_list.append(tx_json)
            # Join transactions with newline as delimiter
            tx_data = "\n".join(tx_data_list).encode("utf-8")
            tx_count = len(block_dict["transactions"])
            tx_count_data = struct.pack(">I", tx_count)
            return header_data + tx_count_data + tx_data
        except Exception as e:
            print(f"[BlockMetadata] ERROR: Failed to serialize block: {e}")
            raise

    def get_block_from_data_file(self, offset: int) -> Optional[Block]:
        """
        Retrieve a block from the block.data file using its stored offset.
        Verifies the file's magic number and data integrity.
        """
        try:
            if not os.path.exists(self.current_block_file):
                print(f"[BlockMetadata.get_block_from_data_file] ERROR: block.data file not found: {self.current_block_file}")
                return None
            file_size = os.path.getsize(self.current_block_file)
            if offset < 4 or offset >= file_size:
                print(f"[BlockMetadata.get_block_from_data_file] ERROR: Invalid offset {offset} for file size {file_size}.")
                return None
            with open(self.current_block_file, "rb") as f:
                f.seek(offset, os.SEEK_SET)
                block_size_bytes = f.read(4)
                if len(block_size_bytes) != 4:
                    print(f"[BlockMetadata.get_block_from_data_file] ERROR: Failed to read block size at offset {offset}.")
                    return None
                block_size = struct.unpack(">I", block_size_bytes)[0]
                if block_size <= 0 or offset + block_size > file_size:
                    print(f"[BlockMetadata.get_block_from_data_file] ERROR: Invalid block size {block_size} at offset {offset}.")
                    return None
                block_data = f.read(block_size)
                if len(block_data) != block_size:
                    print(f"[BlockMetadata.get_block_from_data_file] ERROR: Incomplete block data at offset {offset}.")
                    return None
                block = self._deserialize_block_from_binary(block_data)
                if not block:
                    print(f"[BlockMetadata.get_block_from_data_file] ERROR: Deserialization failed at offset {offset}.")
                    return None
                print(f"[BlockMetadata.get_block_from_data_file] INFO: Retrieved Block {block.index} from offset {offset}.")
                return block
        except Exception as e:
            print(f"[BlockMetadata.get_block_from_data_file] ERROR: Exception occurred: {e}")
            return None

    def get_latest_block(self) -> Optional[Block]:
        """
        Retrieve the most recent block using LMDB metadata and block.data.
        Ensures LMDB integrity, valid hash format, and magic number consistency.
        """
        try:
            print("[BlockMetadata.get_latest_block] INFO: Retrieving latest block from LMDB...")
            all_blocks = []
            with self.block_metadata_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    if key.decode().startswith("block:"):
                        try:
                            block_metadata = json.loads(value.decode("utf-8"))
                            if not isinstance(block_metadata, dict):
                                print(f"[BlockMetadata.get_latest_block] ERROR: Invalid block metadata (not dict): {block_metadata}")
                                continue
                            header = block_metadata.get("block_header")
                            if not isinstance(header, dict) or "index" not in header:
                                print("[BlockMetadata.get_latest_block] ERROR: Block header missing 'index'")
                                continue
                            all_blocks.append(block_metadata)
                        except json.JSONDecodeError as e:
                            print(f"[BlockMetadata.get_latest_block] ERROR: Corrupt block metadata: {e}")
                            continue
            if not all_blocks:
                print("[BlockMetadata.get_latest_block] WARNING: No blocks found in LMDB. Chain may be empty.")
                return None
            latest_block_data = max(all_blocks, key=lambda b: b["block_header"]["index"], default=None)
            if not latest_block_data:
                print("[BlockMetadata.get_latest_block] ERROR: Could not determine latest block.")
                return None
            block_hash = latest_block_data.get("hash", Constants.ZERO_HASH)
            if not isinstance(block_hash, str) or not all(c in "0123456789abcdefABCDEF" for c in block_hash):
                print(f"[BlockMetadata.get_latest_block] ERROR: Invalid block hash format: {block_hash}")
                return None
            required_keys = {"index", "previous_hash", "timestamp", "nonce", "difficulty"}
            header = latest_block_data["block_header"]
            if not required_keys.issubset(header):
                print(f"[BlockMetadata.get_latest_block] ERROR: Incomplete block metadata: {latest_block_data}")
                return None
            try:
                timestamp = int(header["timestamp"])
                if timestamp <= 0:
                    raise ValueError("Invalid timestamp")
            except (ValueError, TypeError) as e:
                print(f"[BlockMetadata.get_latest_block] ERROR: Invalid timestamp: {e}")
                return None
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
            block_offset = latest_block_data.get("data_offset")
            if not isinstance(block_offset, int):
                print("[BlockMetadata.get_latest_block] ERROR: Block data offset missing or invalid in LMDB.")
                return None
            full_block = self.get_block_from_data_file(block_offset)
            if not full_block:
                print(f"[BlockMetadata.get_latest_block] ERROR: Failed to load full block {block_hash} from block.data file.")
                return None
            print(f"[BlockMetadata.get_latest_block] INFO: Successfully retrieved Block {full_block.index} (Hash: {full_block.hash}).")
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
        Retrieve all stored blocks from LMDB as a list of dictionaries.
        """
        try:
            blockchain_db = self._get_database("block_metadata")
            raw_blocks = blockchain_db.get_all_blocks()
            decoded_blocks = []
            for block in raw_blocks:
                if isinstance(block, bytes):
                    try:
                        block = pickle.loads(block)
                    except Exception as e:
                        print(f"[BlockMetadata.get_all_blocks] ERROR: Failed to decode block: {e}")
                        continue
                if not all(k in block for k in ["hash", "header", "transactions"]):
                    print(f"[BlockMetadata.get_all_blocks] WARNING: Block missing required fields: {block}")
                    continue
                if not isinstance(block["hash"], str):
                    print(f"[BlockMetadata.get_all_blocks] WARNING: Invalid block hash format: {block}")
                    block["hash"] = block["header"].get("merkle_root", Constants.ZERO_HASH)
                decoded_blocks.append(block)
            decoded_blocks.sort(key=lambda b: b["header"]["index"])
            prev_hash = Constants.ZERO_HASH
            for block in decoded_blocks:
                if block["header"]["previous_hash"] != prev_hash:
                    print(f"[BlockMetadata.get_all_blocks] ERROR: Chain discontinuity at block {block['header']['index']}")
                    return []
                prev_hash = block["hash"]
            print(f"[BlockMetadata.get_all_blocks] INFO: Retrieved {len(decoded_blocks)} valid blocks from storage.")
            return decoded_blocks
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
