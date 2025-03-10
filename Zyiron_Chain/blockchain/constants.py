import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import hashlib
import os
from lmdb import Environment
from decimal import Decimal

#CHANGE NETWORK HERE TO ACESS THE ALL THE NETWORKS WHEN NETWORKS ARE SELECTED IT AUTO SWITCHES TO THE CORRECT PORTS 



import hashlib
import os
import lmdb






def store_transaction_signature(tx_id: bytes, falcon_signature: bytes, txindex_path: str) -> bytes:
    """
    Stores the Falcon-512 signature in `txindex.lmdb` and writes the SHA3-384 
    transaction signature to `block.data`.

    - SHA3-384 Hash (48 bytes) → `block.data`
    - Full Falcon-512 Signature (700 bytes) + 512-byte Salt → `txindex.lmdb`
    
    Args:
        tx_id (bytes): The transaction ID.
        falcon_signature (bytes): The full Falcon-512 signature (700 bytes).
        txindex_path (str): Path to the `txindex.lmdb` database.

    Returns:
        bytes: SHA3-384 hash (48 bytes) stored in block.data.
    """

    # ✅ Generate a 512-byte cryptographic salt
    salt = os.urandom(512)

    # ✅ Compute SHA3-384 hash: Falcon-512 Signature + Salt
    sha3_384_hash = hashlib.sha3_384(falcon_signature + salt).digest()

    # ✅ Ensure the LMDB environment is opened correctly
    env = lmdb.open(txindex_path, map_size=128 * 1024 * 1024, max_dbs=1)

    # ✅ Store full Falcon-512 signature + salt in `txindex.lmdb`
    try:
        with env.begin(write=True) as txn:
            txn.put(tx_id, salt + falcon_signature)  # ✅ Store salt + full signature

        print(f"[INFO] ✅ Falcon-512 Signature stored in `txindex.lmdb` for TX ID {tx_id.hex()}.")

    except Exception as e:
        print(f"[ERROR] ❌ Failed to store Falcon-512 Signature: {e}")

    # ✅ Close LMDB environment after use
    env.close()

    # ✅ Return SHA3-384 hashed signature for block storage (`block.data`)
    return sha3_384_hash





class Constants:
    """
    Centralized blockchain constants with automatic network switching,
    transaction handling, UTXO management, mempool configuration, and storage.
    """

    # 🔹 **Versioning & Network Configuration**
    VERSION = "1.00"

    # 🔹 **Network Configuration**
    AVAILABLE_NETWORKS = ["mainnet", "testnet", "regnet"]
    NETWORK = "mainnet"  # 🌐 Default network (Auto-switching enabled)

    if NETWORK not in AVAILABLE_NETWORKS:
        raise ValueError(f"[ERROR] Invalid network: {NETWORK}. Must be one of {AVAILABLE_NETWORKS}.")

    # 🔹 **Network-Based Folder Names**
    NETWORK_FOLDERS = {
        "mainnet": "BlockData",
        "testnet": "TestBlockData_Testnet",
        "regnet": "RegBlockData_Regnet"
    }
    NETWORK_FOLDER = NETWORK_FOLDERS[NETWORK]

    # 🔹 **Storage Paths**
    BLOCKCHAIN_STORAGE_PATH = f"./blockchain_storage/{NETWORK_FOLDER}/"

    # 🔹 **Address Prefixes**
    NETWORK_ADDRESS_PREFIXES = {
        "mainnet": "ZYC",
        "testnet": "ZYT",
        "regnet": "ZYR"
    }
    ADDRESS_PREFIX = NETWORK_ADDRESS_PREFIXES[NETWORK]


    MAX_LMDB_DATABASES = 200

    # 🔹 **Magic Numbers**
# ✅ Store the magic number in **big endian** (matching block.data format)
    MAGIC_NUMBERS = {
        "mainnet": int.from_bytes(b"\x5A\x59\x43\x31", "big"),
        "testnet": int.from_bytes(b"\x5A\x59\x54\x32", "big"),
        "regnet": int.from_bytes(b"\x5A\x59\x52\x33", "big")
    }
    MAGIC_NUMBER = MAGIC_NUMBERS[NETWORK]

    # 🔹 **UTXO Flags**
    UTXO_FLAGS = {
        "mainnet": "",
        "testnet": "TEST-UTXO",
        "regnet": "REG-UTXO"
    }
    UTXO_FLAG = UTXO_FLAGS[NETWORK]


    LMDB_MAP_SIZE = 128 * 1024 * 1024  # ✅ Convert 128MB → Bytes (128 * 1024 * 1024)

    
    DATABASES = {
        "block_metadata": "block_metadata",
        "txindex": "txindex",
        "utxo": "utxo"
    }




    # 🔹 **Block Header Flags**
    BLOCK_HEADER_FLAGS = {
        "mainnet": "",
        "testnet": "TEST-0002",
        "regnet": "REG-0003"
    }
    BLOCK_HEADER_FLAG = BLOCK_HEADER_FLAGS[NETWORK]

    # 🔹 **Genesis & Mining Parameters**
    GENESIS_TARGET = bytes.fromhex("000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")
    MIN_DIFFICULTY = bytes.fromhex("0000003FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")
    MAX_DIFFICULTY = bytes.fromhex("000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")

    # ABOUT 7 MIN HASH TARGET 0x0000003999999999999A0000000000000000000000000000000000000000000000000000000000000000000000000000
    # ABOUT 1 SEC HASH TARGET GOOD FOR REGNET 0x000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    # ABOUT 5 MIN HASH TARGET GOOF FOR TESTNET/MAINNET 0x0000003FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    # ABOUT 2 MIN HASH TARGET IDEAL FOR TESTNET 0x000000466666666666680000000000000000000000000000000000000000000000000000000000000000000000000000
    # SHA3-384 96 HEX HEX HASH 



    # 🔹 **Difficulty Adjustment Parameters**
    if NETWORK == "regnet":
        TARGET_BLOCK_TIME = 120  # ⏳ **Regnet has a 2-minute block time**
        DIFFICULTY_ADJUSTMENT_INTERVAL = 1  # 🔄 **Adjust difficulty every block**
        MIN_DIFFICULTY_FACTOR = 0.5  # ⬇️ **Regnet allows difficulty reduction by 50%**
        MAX_DIFFICULTY_FACTOR = 10.0  # ⬆️ **Regnet difficulty can increase by 1000%**
    else:
        TARGET_BLOCK_TIME = 300  # ⏳ **5-minute block time (Mainnet & Testnet)**
        DIFFICULTY_ADJUSTMENT_INTERVAL = 2  # 🔄 **Adjust difficulty every 2 blocks**
        MIN_DIFFICULTY_FACTOR = 0.85  # ⬇️ **Max decrease: 15%**
        MAX_DIFFICULTY_FACTOR = 4.0  # ⬆️ **Max increase: 400%**

    # 🔹 **Coin Economics (Fixed Supply Model)**
    MAX_SUPPLY = 77_777_777 if NETWORK == "mainnet" else None  # 🪙 **Fixed supply for mainnet, no max for testnet & regnet**
    INITIAL_COINBASE_REWARD = 7.00  # 🎁 **Fixed block reward per mined block**
    COIN = Decimal("0.00000001")  # ✅ Smallest currency unit (1 ZYC = 100,000,000 units called a Zee)
    

# ✅ **Updated Block Size Range to Allow 0MB - 10MB**
    MAX_BLOCK_SIZE_SETTINGS = {
        "mainnet": (0, 10 * 1024 * 1024),  # ✅ 0MB to 10MB
        "testnet": (0, 10 * 1024 * 1024),  # ✅ 0MB to 10MB
        "regnet": (0, 2 * 1024 * 1024)     # ✅ 0MB to 2MB (for rapid block testing)
    }

    # ✅ **Apply Network-Specific Block Size Limits**
    BLOCK_SIZE_RANGE = MAX_BLOCK_SIZE_SETTINGS[NETWORK]
    MIN_BLOCK_SIZE_BYTES = BLOCK_SIZE_RANGE[0]  # ✅ Minimum Block Size (0MB)
    MAX_BLOCK_SIZE_BYTES = BLOCK_SIZE_RANGE[1]  # ✅ Maximum Block Size (10MB)

    # ✅ **Explicitly Set Initial Block Size**
    INITIAL_BLOCK_SIZE_MB = (MIN_BLOCK_SIZE_BYTES / (1024 * 1024)) if MIN_BLOCK_SIZE_BYTES > 0 else 0  # ✅ Ensures 0MB allowed


    # ✅ **Time Drift Configuration**
    MAX_TIME_DRIFT = 7200  # ⏳ 2-hour time drift buffer



    # 🔹 **Hashing & Security**
    ZERO_HASH = "0" * 96  # 📌 **SHA3-384 produces 96-character hex hashes**
    # 🔹 **SHA3-384 Hash & Difficulty Target Settings**
    SHA3_384_HASH_SIZE = 96  # ✅ **SHA3-384 produces 96-character hex hashes**
    DIFFICULTY_TARGET_SIZE = 384  # ✅ **Target size in bits for SHA3-384 difficulty calculations**
    TRANSACTION_EXPIRY_TIME = 86400  # ⏳ **Transactions expire after 24 hours in mempool**
    DISPUTE_RESOLUTION_TTL = 3600  # ⚖️ **Transactions must be resolved within 1 hour**

    # 🔹 **Multi-Hop Payment Channels**
    MULTIHOP_MIN_CHANNEL_LIFETIME = 3600  # ⏳ **1-hour min channel open time**
    MULTIHOP_MAX_HOPS = 10  # 🔄 **Max 10 hops per transaction**
    MULTIHOP_REBROADCAST_TIMEOUT = 180  # ⏳ **Rebroadcast pending multi-hop transactions after 3 minutes**

    # 🔹 **Instant Payment & HTLC Settings**
    HTLC_LOCK_TIME = 120  # ⏳ **HTLC lock expires in 2 minutes**
    HTLC_EXPIRY_TIME = 7200  # ⏳ **HTLC expires after 2 hours (ZKP-based)**
    INSTANT_PAYMENT_TTL = 600  # ⚡ **Instant payments must be confirmed within 10 minutes**
    PAYMENT_CHANNEL_INACTIVITY_TIMEOUT = 7200  # ⏳ **Payment channels auto-close after 2 hours of inactivity**

    MEMPOOL_MAX_SIZE_MB = 256 # 🏗️ **Total Mempool Storage Capacity (MB)**
    
    # ✅ **Mempool Type Allocations**
    MEMPOOL_STANDARD_ALLOCATION = 0.50  # 🏦 **50% of total mempool reserved for Standard Transactions**
    MEMPOOL_SMART_ALLOCATION = 0.50  # 🧠 **50% of total mempool reserved for Smart Transactions**

    # ✅ **Block Inclusion Allocations (Dynamic per Block)**
    BLOCK_ALLOCATION_SMART = 0.50  # 🧠 **50% of the block is reserved for Smart Transactions**
    BLOCK_ALLOCATION_STANDARD = 0.50  # 🏦 **50% of the block is reserved for Standard Transactions**

    # ✅ **Specialized Space Allocations for Transaction Types**
    INSTANT_PAYMENT_ALLOCATION = 0.30  # ⚡ **Instant Transactions get 30% of the total block space**
    STANDARD_TRANSACTION_ALLOCATION = 0.20  # 🏦 **Standard Transactions get 20% of the total block space**

    # ✅ **Mempool Transaction Expiry Policy**
    MEMPOOL_TRANSACTION_EXPIRY = 86400  # ⏳ **Transactions expire after 24 hours in the mempool**

    # 🔹 **Transaction Confirmation Requirements**
    TRANSACTION_CONFIRMATION_SETTINGS = {
        "mainnet": {"STANDARD": 8, "SMART": 5, "INSTANT": 2, "COINBASE": 12},
        "testnet": {"STANDARD": 3, "SMART": 2, "INSTANT": 1, "COINBASE": 6},
        "regnet": {"STANDARD": 6, "SMART": 4, "INSTANT": 2, "COINBASE": 8}
    }
    TRANSACTION_CONFIRMATIONS = TRANSACTION_CONFIRMATION_SETTINGS[NETWORK]

    # 🔹 **Testnet Faucet**
    ENABLE_FAUCET = True if NETWORK == "testnet" else False


# 🔹 **Database Configuration**
    # Define the maximum block data file size before a new one is created (512 MB)
    BLOCK_DATA_FILE_SIZE_BYTES = 512 * 1024 * 1024  # ✅ Convert MB → Bytes (512MB)



    # ✅ Standardized Block Storage Offsets (Matches block.data format)
    BLOCK_STORAGE_OFFSETS = {
        "magic_number": {
            "start": 0, "size": 4,
            "desc": "4-byte Network Identifier (Magic Number)"
        },
        "block_length": {
            "start": 4, "size": 8,
            "desc": "8-byte Unsigned Long Long, ensures block length within limits"
        },
        "block_hash": {
            "start": 12, "size": 48,
            "desc": "48-byte SHA3-384 Block Hash"
        },
        "previous_hash": {
            "start": 60, "size": 48,
            "desc": "48-byte SHA3-384 Previous Block Hash"
        },
        "merkle_root": {
            "start": 108, "size": 48,
            "desc": "48-byte SHA3-384 Merkle Root"
        },
        "block_height": {
            "start": 156, "size": 8,
            "desc": "8-byte Unsigned Long Long Block Height"
        },
        "timestamp": {
            "start": 164, "size": 8,
            "desc": "8-byte Block Timestamp"
        },
        "difficulty_length": {
            "start": 172, "size": 1,
            "desc": "1-byte Difficulty Length (size marker)"
        },
        "difficulty": {
            "start": 173, "size": 64,
            "desc": "64-byte Difficulty Target"
        },
        "nonce": {
            "start": 237, "size": 8,
            "desc": "8-byte Unsigned Long Long Nonce"
        },
        "miner_address": {
            "start": 245, "size": 128,
            "desc": "128-byte Falcon-512 Public Key of Miner"
        },
        "transaction_signature": {
            "start": 373, "size": 48,
            "desc": "48-byte SHA3-384 Transaction Signature"
        },
        "falcon_signature": {
            "start": 421, "size": 700,
            "desc": "700-byte Falcon-512 Digital Signature"
        },
        "reward": {
            "start": 1121, "size": 8,
            "desc": "8-byte Block Reward"
        },
        "fees_collected": {
            "start": 1129, "size": 8,
            "desc": "8-byte Total Fees Collected"
        },
        "block_version": {
            "start": 1137, "size": 4,
            "desc": "4-byte Block Version"
        },
        "transaction_count": {
            "start": 1141, "size": 4,
            "desc": "4-byte Number of Transactions"
        },
        "metadata": {
            "start": 1145, "size": 256,
            "desc": "256-byte Truncated Metadata (Dynamic Storage)"
        },
        "transactions": {
            "start": 1401, "size": None,
            "desc": "Variable-Length Transactions (Starts after all metadata)"
        }
    }






    # Network Database Configuration
    NETWORK_DATABASES = {
        "mainnet": {
            "folder": f"{BLOCKCHAIN_STORAGE_PATH}",  # 📂 Root blockchain storage directory
            "block_data": f"{BLOCKCHAIN_STORAGE_PATH}block_data/",  # 📦 Stores full block records (binary format)
            "block_metadata": f"{BLOCKCHAIN_STORAGE_PATH}block_metadata.lmdb",  # 📜 Stores block headers & metadata
            "txindex": f"{BLOCKCHAIN_STORAGE_PATH}txindex.lmdb",  # 🔗 Stores transaction IDs + Falcon-512 signatures (salt + signature)
            "utxo": f"{BLOCKCHAIN_STORAGE_PATH}utxo.lmdb",  # 💰 Stores unspent transaction outputs (UTXOs)
            "utxo_history": f"{BLOCKCHAIN_STORAGE_PATH}utxo_history.lmdb",  # 📊 Stores UTXO history (spent & unspent)
            "mempool": f"{BLOCKCHAIN_STORAGE_PATH}mempool.lmdb",  # 🚀 Stores pending transactions (standard & smart)
            "fee_stats": f"{BLOCKCHAIN_STORAGE_PATH}fee_stats.lmdb",  # 📈 Tracks historical fee data for congestion-based fees
            "orphan_blocks": f"{BLOCKCHAIN_STORAGE_PATH}orphan_blocks.lmdb",  # 🏗️ Stores orphaned blocks awaiting parent blocks
            "flag": "MAINNET"  # ✅ Network identifier flag
        },
        "testnet": {
            "folder": f"{BLOCKCHAIN_STORAGE_PATH}",  # 📂 Root blockchain storage directory
            "block_data": f"{BLOCKCHAIN_STORAGE_PATH}block_data/",  # 📦 Stores full block records (binary format)
            "block_metadata": f"{BLOCKCHAIN_STORAGE_PATH}block_metadata_Testnet.lmdb",  # 📜 Stores block headers & metadata
            "txindex": f"{BLOCKCHAIN_STORAGE_PATH}txindex_Testnet.lmdb",  # 🔗 Stores transaction IDs + Falcon-512 signatures (salt + signature)
            "utxo": f"{BLOCKCHAIN_STORAGE_PATH}utxo_Testnet.lmdb",  # 💰 Stores unspent transaction outputs (UTXOs)
            "utxo_history": f"{BLOCKCHAIN_STORAGE_PATH}utxo_history_Testnet.lmdb",  # 📊 Stores UTXO history (spent & unspent)
            "mempool": f"{BLOCKCHAIN_STORAGE_PATH}mempool_Testnet.lmdb",  # 🚀 Stores pending transactions (standard & smart)
            "fee_stats": f"{BLOCKCHAIN_STORAGE_PATH}fee_stats_Testnet.lmdb",  # 📈 Tracks historical fee data for congestion-based fees
            "orphan_blocks": f"{BLOCKCHAIN_STORAGE_PATH}orphan_blocks_Testnet.lmdb",  # 🏗️ Stores orphaned blocks awaiting parent blocks
            "flag": "TESTNET"  # ✅ Network identifier flag
        },
        "regnet": {
            "folder": f"{BLOCKCHAIN_STORAGE_PATH}",  # 📂 Root blockchain storage directory
            "block_data": f"{BLOCKCHAIN_STORAGE_PATH}block_data/",  # 📦 Stores full block records (binary format)
            "block_metadata": f"{BLOCKCHAIN_STORAGE_PATH}block_metadata_Regnet.lmdb",  # 📜 Stores block headers & metadata
            "txindex": f"{BLOCKCHAIN_STORAGE_PATH}txindex_Regnet.lmdb",  # 🔗 Stores transaction IDs + Falcon-512 signatures (salt + signature)
            "utxo": f"{BLOCKCHAIN_STORAGE_PATH}utxo_Regnet.lmdb",  # 💰 Stores unspent transaction outputs (UTXOs)
            "utxo_history": f"{BLOCKCHAIN_STORAGE_PATH}utxo_history_Regnet.lmdb",  # 📊 Stores UTXO history (spent & unspent)
            "mempool": f"{BLOCKCHAIN_STORAGE_PATH}mempool_Regnet.lmdb",  # 🚀 Stores pending transactions (standard & smart)
            "fee_stats": f"{BLOCKCHAIN_STORAGE_PATH}fee_stats_Regnet.lmdb",  # 📈 Tracks historical fee data for congestion-based fees
            "orphan_blocks": f"{BLOCKCHAIN_STORAGE_PATH}orphan_blocks_Regnet.lmdb",  # 🏗️ Stores orphaned blocks awaiting parent blocks
            "flag": "REGNET"  # ✅ Network identifier flag
        }
    }




    # Assign the correct database set based on the selected network
    DATABASES = NETWORK_DATABASES[NETWORK]

    @staticmethod
    def get_db_path(db_name: str) -> str:
        """Returns the correct database path based on the current network and db type."""
        
        # Ensure network is assigned correctly
        network = Constants.NETWORK
        print(f"[DEBUG] Fetching database path for network: {network}")

        # Constants.DATABASES is already the config for the current network
        network_db_config = Constants.DATABASES
        
        print(f"[DEBUG] Found network configuration: {network_db_config}")
        
        if db_name not in network_db_config:
            raise ValueError(f"[ERROR] Database '{db_name}' not found for {network} network.")
        
        # Return the correct path for the requested database
        db_path = network_db_config[db_name]
        print(f"[DEBUG] Database path for '{db_name}': {db_path}")
        return db_path




    # 🔹 **Wallet Address Handling Rules**
    ACCEPTED_ADDRESS_PREFIXES = ["ZYC"] if NETWORK == "mainnet" else ["ZYT"]

    # 🔹 **Fee & Mempool Expiry**
    MIN_TRANSACTION_FEE = 0.0 if NETWORK == "regnet" else 0.100000000
    FEE_INCREMENT_FACTOR = 1.0 if NETWORK == "regnet" else 1.10
    MEMPOOL_TRANSACTION_EXPIRY = {"mainnet": 86400, "testnet": 21600, "regnet": 3600}[NETWORK]

    # 🔹 **Block Propagation Delay**
    BLOCK_PROPAGATION_DELAY = {"mainnet": 15, "testnet": 5, "regnet": 0}[NETWORK]

    # 🔹 **Smart Mempool Priority Blocks**
    SMART_MEMPOOL_PRIORITY_BLOCKS = (4, 5)

    # 🔹 **Rebroadcasting & Fee Scaling**
    REBROADCAST_INTERVAL = 300  # ⏳ **Rebroadcast unconfirmed transactions every 5 minutes**
    REBROADCAST_FEE_INCREASE = 0.10  # 🔼 **Increase fee by 10% upon rebroadcast**


    # 🔹 **Write-Ahead Logging (WAL) & LMDB Batch Flushing (Auto-switch by Network)**
    LMDB_WAL_FLUSH_INTERVAL_SETTINGS = {
        "mainnet": 2,  # ⏳ Flush every 2 seconds for Mainnet
        "testnet": 3,  # ⏳ Flush every 3 seconds for Testnet
        "regnet": 3    # ⏳ Flush every 3 seconds for Regnet
    }
    LMDB_WAL_FLUSH_INTERVAL = LMDB_WAL_FLUSH_INTERVAL_SETTINGS[NETWORK]  # ✅ Auto-switching WAL timer

    # 🔹 **High-Write Databases That Require WAL**
    LMDB_HIGH_WRITE_DATABASES = {
        "mainnet": [
            "mempool.lmdb",
            "utxo.lmdb",
            "txindex.lmdb",
            "fee_stats.lmdb"
        ],
        "testnet": [
            "mempool.lmdb",
            "utxo.lmdb",
            "txindex.lmdb",
            "fee_stats.lmdb"
        ],
        "regnet": [
            "mempool.lmdb",
            "utxo.lmdb",
            "txindex.lmdb",
            "fee_stats.lmdb"
        ]
    }
    HIGH_WRITE_DATABASES = LMDB_HIGH_WRITE_DATABASES[NETWORK]  # ✅ Auto-switching database list

    # 🔹 **WAL Folder Naming & Network Flags**
    WAL_FOLDER_NAMES = {
        "mainnet": "WriteLog",   # 🏦 Standard WAL folder for Mainnet
        "testnet": "WriteLog-Testnet",  # 🏦 WAL labeled for Testnet
        "regnet": "WriteLog-Regnet"  # 🏦 WAL labeled for Regnet
    }
    WAL_FOLDER_NAME = WAL_FOLDER_NAMES[NETWORK]  # ✅ Auto-switching WAL directory name

    # 🔹 **WAL Folder Flags (Prevent Network Confusion)**
    WAL_FOLDER_FLAGS = {
        "mainnet": "",
        "testnet": "TESTNET-WAL",
        "regnet": "REGNET-WAL"
    }
    WAL_FOLDER_FLAG = WAL_FOLDER_FLAGS[NETWORK]  # ✅ Auto-switching WAL flag

    TRANSACTION_MEMPOOL_MAP = {
        "STANDARD": {
            "prefixes": [],
            "mempool": "StandardMempool",
            "database": "LMDB"
        },
        "SMART": {
            "prefixes": ["S-"],
            "mempool": "SmartMempool",
            "database": "LMDB"
        },
        "INSTANT": {
            "prefixes": ["PID-", "CID-"],
            "mempool": "StandardMempool",
            "database": "LMDB"
        },
        "COINBASE": {
            "prefixes": ["COINBASE-"],
            "mempool": "StandardMempool",
            "database": "LMDB"
        }
    }

