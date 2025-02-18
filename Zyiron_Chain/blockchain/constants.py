import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from decimal import Decimal





class Constants:
    """
    Centralized configuration for blockchain constants, covering mining, transaction fees, UTXO management,
    mempool, smart contracts, and network behavior.
    """
        # 🔹 **Versioning & Network Configuration**
    VERSION = "1.0.0"  # ✅ Defines the current version of the blockchain

    # 🔹 **Network Configuration**
    AVAILABLE_NETWORKS = ["mainnet", "testnet"]  # ✅ Allowed network types
    NETWORK = "mainnet"  # 🌐 Default network (Switch to 'testnet' when needed)

    # ✅ Validate the network setting
    if NETWORK not in AVAILABLE_NETWORKS:
        raise ValueError(f"[ERROR] Invalid network: {NETWORK}. Must be 'mainnet' or 'testnet'.")

    # 🔹 **Address Prefixes (Mainnet & Testnet)**
    MAINNET_ADDRESS_PREFIX = "KYC"
    TESTNET_ADDRESS_PREFIX = "KYT"

    # ✅ Dynamically selects the correct address prefix
    ADDRESS_PREFIX = MAINNET_ADDRESS_PREFIX if NETWORK == "mainnet" else TESTNET_ADDRESS_PREFIX

    # 🔹 **Genesis & Mining Parameters**
    GENESIS_TARGET = 0x000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  
    MIN_DIFFICULTY = 0x000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  
    MAX_DIFFICULTY = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  

    # 🔹 **Difficulty Adjustment Parameters**
    TARGET_BLOCK_TIME = 300  # ⏳ **5-minute block time**
    DIFFICULTY_ADJUSTMENT_INTERVAL = 2  # 🔄 **Adjust difficulty every 2 blocks**
    MIN_DIFFICULTY_FACTOR = 0.85  # ⬇️ **Max decrease: 15%**
    MAX_DIFFICULTY_FACTOR = 4.0  # ⬆️ **Max increase: 400%**
    
    # 🔹 **Hashing & Security**
    ZERO_HASH = "0" * 96  # 📌 **SHA3-384 produces 96-character hex hashes**
    # 🔹 **SHA3-384 Hash & Difficulty Target Settings**
    SHA3_384_HASH_SIZE = 96  # ✅ **SHA3-384 produces 96-character hex hashes**
    DIFFICULTY_TARGET_SIZE = 384  # ✅ **Target size in bits for SHA3-384 difficulty calculations**
    # 🔹 **Maximum Block Size**
    MAX_BLOCK_SIZE_BYTES = 10 * 1024 * 1024  # 🚀 10MB (10 * 1024 * 1024 bytes)

    # 🔹 **Coin Economics**
    MAX_SUPPLY = 84_096_000  # 🪙 **Max coin supply**
    INITIAL_COINBASE_REWARD = 100.00  # 🎁 **Initial mining reward**
    BLOCKCHAIN_HALVING_BLOCK_HEIGHT = 420_480  # 📉 **Halves every ~4 years (~5 min block time) until max supply**
    # 🔹 **Smallest Unit Definition**
    COIN = Decimal("0.00000001")  # ✅ Smallest unit of the currency 


# 🔹 **Transaction Confirmation Requirements**
    TRANSACTION_CONFIRMATIONS = {
        "STANDARD": 8,   # ✅ Standard transactions require 8 confirmations
        "SMART": 5,      # ✅ Smart contract transactions require 5 confirmations
        "INSTANT": 2,    # ✅ Instant transactions require 2 confirmations
        "COINBASE": 12   # ✅ Coinbase transactions require 12 confirmations
    }

    # 🔹 **Mempool Configuration**
    # 🔹 **Mempool Storage & Allocation Settings**
    MEMPOOL_MAX_SIZE_MB = 2048  # 🏗️ **Total Mempool Storage Capacity (MB)**
    
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
    MAX_LMDB_DATABASES= 10


    # 🔹 **Instant Payment & HTLC Settings**a
    HTLC_LOCK_TIME = 120  # ⏳ **HTLC lock expires in 2 minutes**
    HTLC_EXPIRY_TIME = 7200  # ⏳ **HTLC expires after 2 hours (ZKP-based)**
    INSTANT_PAYMENT_TTL = 600  # ⚡ **Instant payments must be confirmed within 10 minutes**
    PAYMENT_CHANNEL_INACTIVITY_TIMEOUT = 7200  # ⏳ **Payment channels auto-close after 2 hours of inactivity**

    # 🔹 **Dynamic Fee Adjustment**
    MIN_TRANSACTION_FEE = 0.100000000  # ⚠️ **Minimum possible fee per transaction**
    FEE_INCREMENT_FACTOR = 1.10  # 🔼 **Increase fee by 10% if rebroadcasted**

    # 🔹 **Transaction Expiry & Disputes**
    TRANSACTION_EXPIRY_TIME = 86400  # ⏳ **Transactions expire after 24 hours in mempool**
    DISPUTE_RESOLUTION_TTL = 3600  # ⚖️ **Transactions must be resolved within 1 hour**

    # 🔹 **Multi-Hop Payment Channels**
    MULTIHOP_MIN_CHANNEL_LIFETIME = 3600  # ⏳ **1-hour min channel open time**
    MULTIHOP_MAX_HOPS = 10  # 🔄 **Max 10 hops per transaction**
    MULTIHOP_REBROADCAST_TIMEOUT = 180  # ⏳ **Rebroadcast pending multi-hop transactions after 3 minutes**

    # 🔹 **Storage Layer (Databases & Routing)**
    DATABASES = {
        "blockchain": "UnQLite",
        "mempool": "LMDB",
        "utxo": "SQLite",
        "analytics": "DuckDB",
        "tinydb": "TinyDB",  # ✅ **Added TinyDB for lightweight storage**
    }

    # 🔹 **Smart Mempool Priority Blocks**
    SMART_MEMPOOL_PRIORITY_BLOCKS = (4, 5)  # ✅ **Smart transactions prioritized in block confirmations**

    # 🔹 **Rebroadcasting & Fee Scaling**
    REBROADCAST_INTERVAL = 300  # ⏳ **Rebroadcast unconfirmed transactions every 5 minutes**
    REBROADCAST_FEE_INCREASE = 0.10  # 🔼 **Increase fee by 10% upon rebroadcast**



    # 🔹 **Confirmation Definitions**
    CONFIRMATION_RULES = {
        "description": "A transaction confirmation occurs when a block containing the transaction is mined and added to the blockchain. Each new block built on top of this confirms the transaction further.",
        "minimum_required": 1,  # ✅ Minimum confirmations for a transaction to be considered valid
        "finalization_threshold": 6,  # ✅ Number of confirmations required for finalization (irreversible status)
        "coinbase_requirement": 12,  # ✅ Coinbase transactions require 12 confirmations before funds are spendable
    }



    # 🔹 **Transaction Prefixes & Mempool Routing**
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
            "database": "UnQLite"
        }
    }
