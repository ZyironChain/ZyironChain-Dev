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

    def store_block(self, block: Block, difficulty) -> None:
        """
        Store block metadata in LMDB and append full block data to block.data.
        
        Steps:
          1. Ensure block header has a merkle root; if not, recompute.
          2. Compute block hash using single SHA3-384 and update header.
          3. Prepare metadata dictionary with all required fields.
          4. Write metadata to LMDB.
          5. Append the full block to block.data file.
        """
        try:
            print(f"[BlockMetadata.store_block] INFO: Storing metadata for Block {block.index} ...")
            # Recompute merkle root if missing
            if not hasattr(block.header, "merkle_root") or not block.header.merkle_root:
                print(f"[BlockMetadata.store_block] WARNING: Block {block.index} missing Merkle root. Recomputing...")
                # (Assuming _calculate_merkle_root is implemented elsewhere)
                block.header.merkle_root = self._calculate_merkle_root(block.transactions)
            # Ensure transactions is a list
            if not isinstance(block.transactions, list):
                print(f"[BlockMetadata.store_block] ERROR: Block {block.index} transactions is not a list.")
                return
            # Compute block hash using single SHA3-384 (processing data as bytes)
            computed_hash = hashlib.sha3_384(block.calculate_hash().encode()).hexdigest()
            block.hash = computed_hash
            # Ensure merkle root is stored as string
            block.header.merkle_root = str(block.header.merkle_root)
            # Prepare metadata dictionary
            current_timestamp = block.timestamp if isinstance(block.timestamp, int) else int(time.time())
            try:
                difficulty_val = int(difficulty)
            except ValueError:
                print(f"[BlockMetadata.store_block] ERROR: Difficulty must be an integer; received {difficulty}.")
                return
            tx_ids = [tx.tx_id for tx in block.transactions if hasattr(tx, "tx_id") and isinstance(tx.tx_id, str)]
            if len(tx_ids) < len(block.transactions):
                print(f"[BlockMetadata.store_block] WARNING: Some transactions in Block {block.index} are missing valid tx_id.")
            block_metadata = {
                "hash": str(block.hash),
                "block_header": {
                    "index": block.index,
                    "previous_hash": str(block.previous_hash),
                    "merkle_root": str(block.header.merkle_root),
                    "timestamp": current_timestamp,
                    "nonce": getattr(block, "nonce", 0),
                    "difficulty": difficulty_val,
                },
                "transaction_count": len(block.transactions),
                "block_size": len(json.dumps(block.to_dict(), ensure_ascii=False).encode("utf-8")),
                "data_file": self.current_block_file,
                "data_offset": self.current_block_offset,
                "tx_ids": tx_ids,
            }
            with self.block_metadata_db.env.begin(write=True) as txn:
                txn.put(f"block:{block.hash}".encode(), json.dumps(block_metadata).encode("utf-8"))
            print(f"[BlockMetadata.store_block] INFO: Metadata for Block {block.index} stored in LMDB.")
            try:
                self.create_block_data_file(block)
            except Exception as e:
                print(f"[BlockMetadata.store_block] ERROR: Failed to write Block {block.index} to block.data: {e}")
                with self.block_metadata_db.env.begin(write=True) as txn:
                    txn.delete(f"block:{block.hash}".encode())
                return
            print(f"[BlockMetadata.store_block] INFO: Block {block.index} stored successfully.")
        except Exception as e:
            print(f"[BlockMetadata.store_block] ERROR: Failed to store Block {block.index}: {e}")
            raise

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
        Serialize a Block object into binary format.
        The header fields are packed in fixed-length binary, and transaction data
        is appended as UTF-8 encoded JSON with newline delimiters.
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
            difficulty_bytes = difficulty_int.to_bytes(48, "big", signed=False)
            if len(difficulty_bytes) > 48:
                raise ValueError(f"Difficulty {difficulty_int} exceeds 48 bytes.")
            miner_address_encoded = header["miner_address"].encode("utf-8")
            if len(miner_address_encoded) > 128:
                raise ValueError("Miner address exceeds 128 bytes.")
            miner_address_padded = miner_address_encoded.ljust(128, b'\x00')
            header_format = ">I32s32sQI48s128s"
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
            tx_data_list = []
            for tx in block_dict["transactions"]:
                tx_json = json.dumps(tx, sort_keys=True)
                tx_data_list.append(tx_json)
            tx_data = "\n".join(tx_data_list).encode("utf-8")
            tx_count = len(block_dict["transactions"])
            tx_count_data = struct.pack(">I", tx_count)
            return header_data + tx_count_data + tx_data
        except Exception as e:
            print(f"[BlockMetadata._serialize_block_to_binary] ERROR: Failed to serialize block: {e}")
            raise

    def _deserialize_block_from_binary(self, block_data: bytes) -> Optional[Block]:
        """
        Deserialize binary data into a Block object.
        """
        try:
            header_format = ">I32s32sQI48s128s"
            header_size = struct.calcsize(header_format)
            (block_height,
             prev_block_hash,
             merkle_root,
             timestamp,
             nonce,
             difficulty_bytes,
             miner_address_bytes) = struct.unpack(header_format, block_data[0:header_size])
            difficulty_int = int.from_bytes(difficulty_bytes, "big", signed=False)
            miner_address_str = miner_address_bytes.rstrip(b'\x00').decode("utf-8")
            tx_count_offset = header_size
            tx_count = struct.unpack(">I", block_data[tx_count_offset:tx_count_offset + 4])[0]
            tx_data = block_data[tx_count_offset + 4:]
            tx_jsons = tx_data.split(b'\n')
            transactions = []
            for tx_json in tx_jsons:
                if not tx_json.strip():
                    continue
                transactions.append(json.loads(tx_json.decode("utf-8")))
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
            return Block.from_dict(block_dict)
        except Exception as e:
            print(f"[BlockMetadata._deserialize_block_from_binary] ERROR: Failed to deserialize block: {e}")
            return None

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
