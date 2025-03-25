import sys
import os

import sys
import os
from typing import List, Optional
# Adjust Python path for project structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

from decimal import Decimal
import lmdb

from Zyiron_Chain.blockchain.constants import Constants  # ✅ Import primary blockchain constants


class PeerConstants:
    """
    Comprehensive peer configuration settings:
    - Network flag validation (prevents cross-network issues)
    - Secure RPC restrictions (limits access to trusted IPs)
    - Bandwidth limitations & spam protection
    - Auto-failover & backup bootstrapping
    - Firewall rules & encryption for security
    """

    # 🔹 **Fail-Safe: Ensure Node is on the Correct Network**
    NETWORK_FLAGS = {
        "mainnet": "MAINNET",
        "testnet": "TESTNET",
        "regnet": "REGNET"
    }
    NODE_NETWORK_FLAG = NETWORK_FLAGS[Constants.NETWORK]  # 🔍 Assigned network flag

    # 🔹 **Fix: Ensure DATABASES Contains "flag"**
    DATABASES_FLAG = Constants.DATABASES.get("flag", None)

    if DATABASES_FLAG is None:
        print("⚠️ [WARNING] `flag` is missing in Constants.DATABASES. Setting default...")
        DATABASES_FLAG = NODE_NETWORK_FLAG  # Fallback to expected flag

    NETWORK_DB_FLAG = DATABASES_FLAG  # 🔍 Validate against database flag

    @classmethod
    def validate_network(cls):
        """ Ensures node is connected to the correct network """
        if cls.NETWORK_DB_FLAG != cls.NODE_NETWORK_FLAG:
            raise ValueError(
                f"🚨 [ERROR] Node is on the WRONG network! Expected {cls.NODE_NETWORK_FLAG}, "
                f"but found {cls.NETWORK_DB_FLAG}. Auto-disconnecting."
            )

    def __init__(self):
        """ Ensures validation occurs upon initialization """
        self.validate_network()

    # 🔹 **Network Peer ID**
    PEER_USER_ID = 0  # Unique identifier for a peer on the network

    # 🔹 **Peer & Node Connection Limits (Auto-switching by Network)**
    MAX_PEERS_SETTINGS = {
        "mainnet": 50,   # 🌐 Mainnet allows 50 max peer connections
        "testnet": 100,  # 🔬 Testnet allows 100 peer connections
        "regnet": 20     # 🛠️ Regnet allows 20 peer connections
    }
    MAX_PEERS = MAX_PEERS_SETTINGS[Constants.NETWORK]  # ✅ Auto-switching

    # 🔹 **Peer Synchronization Settings**
    CONNECTION_TIMEOUT = 10  # ⏳ Timeout before disconnecting inactive peers (seconds)
    PEER_SYNC_TIMEOUT = 15  # 🔄 Time before resyncing with another node
    PEER_DISCOVERY_INTERVAL = 300  # 🔍 Time interval for discovering new peers (seconds)
    PEER_KEEPALIVE_INTERVAL = 120  # ⚡ Interval to check if peers are still responsive (seconds)

    # 🔹 **Latency & Network Performance**
    MAX_PEER_LATENCY = 100  # ⚡ Max acceptable network latency (milliseconds)
    PEER_RETRY_LIMIT = 5  # 🔁 Maximum retries before dropping a connection

    # 🔹 **Peer Security & Banning Settings**
    PEER_BAN_TIME = 3600  # ⛔ Time a misbehaving peer is banned (seconds)
    ALLOW_ANONYMOUS_PEERS = False  # ❌ Whether to allow peers without authentication
    ENABLE_PEER_BANNING = True  # ✅ Auto-bans malicious peers
    MAX_ORPHAN_PEERS = 5  # 🏚️ Max orphan nodes before discarding them

    # 🔹 **Firewall & Connection Security**
    PEER_BLACKLIST = []  # 🚫 List of permanently banned nodes
    PEER_WHITELIST = []  # ✅ Trusted nodes that bypass connection limits

    # 🔹 **Auto-Network Assigned Ports**
    NETWORK_PORTS = {
        "mainnet": {
            "p2p": 56000,
            "rpc": 56100,
            "websocket": 56200,
            "monitoring": 56300
        },
        "testnet": {
            "p2p": 57000,
            "rpc": 57100,
            "websocket": 57200,
            "monitoring": 57300
        },
        "regnet": {
            "p2p": 58000,
            "rpc": 58100,
            "websocket": 58200,
            "monitoring": 58300
        }
    }
    
    P2P_PORT = NETWORK_PORTS[Constants.NETWORK]["p2p"]  # 📡 Peer-to-Peer Port
    RPC_PORT = NETWORK_PORTS[Constants.NETWORK]["rpc"]  # 🔗 Remote Procedure Call Port
    WEBSOCKET_PORT = NETWORK_PORTS[Constants.NETWORK]["websocket"]  # 🌍 WebSocket Port
    MONITORING_PORT = NETWORK_PORTS[Constants.NETWORK]["monitoring"]  # 📊 Network Health Monitoring Port

    # 🔹 **WebSocket & P2P Optimization**
    ENABLE_FAST_PROPAGATION = True  # 🚀 Enables compact block relays
    BLOOM_FILTER_SUPPORT = True  # 🏦 Reduces transaction bandwidth usage
    MIN_PEER_VERSION = "1.0.0"  # 🔖 Minimum required node version
    ALLOW_SPV_NODES = True  # ✅ Supports light nodes for mobile clients
    MAX_MESSAGE_SIZE = 1 * 1024 * 1024  # 📦 Maximum P2P message size (1MB)

    # 🔹 **Transaction Relay & Mempool Optimization**
    MEMPOOL_MAX_TRANSACTIONS = 50_000  # 💾 Max TXs stored before pruning
    TRANSACTION_BROADCAST_LIMIT = 10  # 🚀 Max TXs per peer per second
    ENABLE_FEE_MARKET = True  # ⚖️ Adjusts transaction fees dynamically
    ENABLE_RELAY_RBF = True  # 🔄 Supports Replace-By-Fee (RBF)

    # 🔹 **Security & Encryption**
    ENABLE_TLS = True  # 🔒 Encrypts RPC/WebSocket communication
    MAX_FAILED_RPC_ATTEMPTS = 5  # ❌ Failed logins before banning IP
    RPC_SESSION_TIMEOUT = 600  # ⏳ Auto-disconnect RPC clients after inactivity
    ENCRYPT_PEER_MESSAGES = True  # 🔑 Uses end-to-end encryption

    # 🔹 **Blockchain Syncing Optimization**
    SYNC_MAX_REQUEST_SIZE = 4 * 1024 * 1024  # 📡 Max blockchain data request size (4MB)
    SYNC_BATCH_SIZE = 500  # ⏳ Number of blocks synced per batch
    ENABLE_PARALLEL_SYNCING = True  # 🚀 Faster initial sync using multiple connections

    # 🔹 **Firewall Best Practices**
    FIREWALL_RULES = {
        "p2p": "Restrict to trusted nodes where possible",
        "rpc": "Restrict RPC access to whitelisted IPs",
        "tls": "Require strong credentials and TLS encryption"
    }

    # 🔹 **Secure RPC Access**
    RPC_ALLOWED_IPS = ["127.0.0.1"]  # Default: Localhost only
    RPC_RATE_LIMIT = 5  # Max RPC requests per second
    REQUIRE_RPC_AUTH = True  # ✅ Require authentication for RPC access

    # 🔹 **Bandwidth Control**
    MAX_UPLOAD_BANDWIDTH = 10 * 1024 * 1024  # 🚀 Max upload speed (10MB/s)
    MAX_DOWNLOAD_BANDWIDTH = 20 * 1024 * 1024  # 🚀 Max download speed (20MB/s)
    NODE_THROTTLING = True  # ✅ Enable network throttling
    ENABLE_RATE_LIMITING = True  # ✅ Prevent spam connections

    # 🔹 **WAL (Write-Ahead Logging) & LMDB Batch Flushing**
    LMDB_WAL_FLUSH_INTERVAL = Constants.LMDB_WAL_FLUSH_INTERVAL  # ✅ Uses blockchain WAL settings


# ✅ **Create an instance to validate the network on startup**
peer_constants = PeerConstants()
