
zyironchain@gmail.com



Zyiron Chain - PQC Payment System
Overview
Zyiron Chain is a Post-Quantum Cryptography (PQC) resistant payment system designed to provide secure, scalable, and efficient transactions. It leverages SHA3-384 for hashing and Falcon 1024 for digital signatures, ensuring quantum-resistant security. The system is structured into three layers:

Layer 1: Protocol Layer - The foundational layer handling core blockchain operations, including block creation, consensus, and transaction validation.

Layer 2: Instant Payments - A layer dedicated to fast, low-latency transactions using advanced routing and batching techniques.

Layer 3: Governance - A governance layer (still under development) that will manage network upgrades, dispute resolution, and community-driven decision-making.

Key Features
Quantum-Resistant Security: Utilizes SHA3-384 for hashing and Falcon 1024 for digital signatures, ensuring resistance against quantum computing attacks.

Three-Layer Architecture: Separates protocol, instant payments, and governance for modularity and scalability.

Instant Payments: Supports fast, low-latency transactions with multi-hop routing and batching.

Smart Transactions: Enables programmable logic for advanced payment scenarios.

Community-Driven Development: Prioritizes community involvement, code refactoring, and debugging to ensure a robust and user-friendly system.

Technologies Used
SHA3-384: A cryptographic hash function used for secure hashing of transactions and blocks.

Falcon 1024: A post-quantum digital signature algorithm used for signing transactions and ensuring authenticity.

Python: The primary programming language for the implementation.

Blockchain Fundamentals: Proof-of-Work (PoW), UTXO model, and Merkle trees for transaction validation and block integrity.

Code Structure
The codebase is organized into several key components:

1. Account and Wallet Management
Account Class: Manages user accounts with Falcon-based public/private keys for signing and verifying messages.

Wallet Class: Handles key generation, transaction signing, and verification for both testnet and mainnet.

2. Blockchain Core
Block Class: Represents a block in the blockchain, including block headers, transactions, and mining logic.

Blockchain Class: Manages the blockchain, including block creation, validation, and UTXO management.

Mempool Classes: Handles pending transactions, fee calculation, and transaction prioritization.

3. Transaction Handling
Transaction Class: Represents a blockchain transaction with inputs, outputs, and fees.

Smart Transactions: Supports advanced transaction types with programmable logic.

Fee Model: Calculates transaction fees based on block size, congestion, and payment type.

4. Payment Channels and Multi-Hop Routing
PaymentChannel Class: Manages off-chain payment channels for instant transactions.

MultiHop Class: Implements multi-hop routing for efficient transaction batching and forwarding.

5. Database and Storage
UnQLite, SQLite, LMDB, DuckDB: Various databases for storing blockchain data, UTXOs, and analytics.

DatabaseSyncManager: Synchronizes data across multiple databases for consistency and redundancy.

6. Governance and Dispute Resolution
DisputeResolutionContract: Handles dispute resolution for transactions and payment channels.

Governance Layer: (Under development) Will manage network upgrades and community-driven decisions.

Getting Started
Prerequisites
Python 3.8 or higher

Required Python packages: unqlite, lmdb, duckdb, sqlite3, tinydb

Installation
Clone the repository:

bash
Copy
git clone https://github.com/your-repo/zyiron-chain.git
cd zyiron-chain
Install dependencies:

bash
Copy
pip install -r requirements.txt
Run the blockchain:

bash
Copy
python main.py
Example Usage
Generating Keys and Signing a Message
python
Copy
from Zyiron_Chain.accounts.wallet import Wallet

# Create a new wallet
wallet = Wallet()

# Generate Falcon keys
wallet.generate_keys()

# Sign a message
message = "Hello, Zyiron Chain!"
signature = wallet.sign_message(message)

# Verify the signature
is_valid = wallet.verify_message(message, signature)
print(f"Is the signature valid? {is_valid}")
Creating and Mining a Block
python
Copy
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.blockchain.blockchain import Blockchain
from Zyiron_Chain.accounts.wallet import Wallet

# Initialize the blockchain
key_manager = KeyManager()
poc = PoC()
blockchain = Blockchain(key_manager, poc)

# Create a new block
block = Block(index=1, previous_hash="0", transactions=["tx1", "tx2"])

# Mine the block
block.mine(target=blockchain.calculate_target(), fee_model=blockchain.fee_model, mempool=blockchain.mempool, block_size=1)

# Add the block to the blockchain
blockchain.add_block(block)
Sending a Transaction
python
Copy
from Zyiron_Chain.transactions.send_zyc import SendZYC
from Zyiron_Chain.accounts.wallet import Wallet

# Initialize the SendZYC class
send_zyc = SendZYC(key_manager, utxo_manager, mempool, fee_model, network="mainnet")

# Prepare and send a transaction
recipient_script_pub_key = "recipient_public_key_hash"
amount = 10.0  # Amount to send
block_size = 1  # Current block size in MB
transaction = send_zyc.prepare_transaction(recipient_script_pub_key, amount, block_size)
Roadmap
Layer 3 Governance: Develop the governance layer for community-driven decision-making.

Code Refactoring: Continuously improve code quality and performance.

Community Development: Engage the community in testing, feedback, and contributions.

Documentation: Expand documentation to include detailed API references and tutorials.

Contributing
We welcome contributions from the community! If you'd like to contribute, please follow these steps:

Fork the repository.

Create a new branch for your feature or bugfix.

Submit a pull request with a detailed description of your changes.

License
This project is licensed under the MIT License. See the LICENSE file for details.







Observations and Suggestions
Cryptography Implementation:

The falcon/ directory is well-detailed, but the ntru-main/ directory is mentioned in the Key Highlights section without being present in the file structure. If NTRU is part of the project, ensure it is added to the structure.

Consider adding a cryptography/ parent directory to group falcon/ and ntru-main/ (if applicable) for better organization.

Database Management:

The database/ directory contains multiple files for different database operations (layer2db.py, leveldbblocks.py, etc.). Consider grouping related files into subdirectories (e.g., database/leveldb/, database/lmdb/) for better modularity.

The reset.py file suggests a reset functionality. Ensure this is well-documented in the docs/ directory to avoid accidental misuse.

Off-Chain and Smart Payment Logic:

The offchain/ and smartpay/ directories are well-defined. Ensure there is clear documentation on how these modules interact with the core blockchain logic (blockchain/) and transactions (transactions/).

Testing:

The tests/ directory is divided into backend_tests/, blockchain_tests/, and frontend_tests/. Ensure that all critical components (e.g., cryptography, database, transactions) have corresponding test cases.

Consider adding a tests/integration_tests/ directory for end-to-end testing of the system.

Documentation:

The docs/ directory is well-structured. Consider adding a docs/security.md file to detail cryptographic implementations, key management, and security best practices.

Add a docs/testing.md file to outline the testing strategy, including unit, integration, and performance tests.

Virtual Environment:

The .venv/ directory is included, which is great for local development. Ensure that the requirements.txt file is kept up-to-date with all dependencies.

Build and Distribution:

The build/ and dist/ directories suggest the project is packaged for distribution. Ensure the setup.py or pyproject.toml file is included in the root directory for proper package configuration.

Frontend (if applicable):

If the project includes a frontend (e.g., a web interface), consider adding a frontend/ directory to the root structure. This would include UI code, assets, and frontend tests.

Logging and Monitoring:

The scripts/monitoring.py file suggests monitoring capabilities. Consider adding a logs/ directory for storing system logs and a monitoring/ directory for advanced monitoring tools and configurations.

Configuration Files:

The .vscode/ directory contains editor-specific configurations. Consider adding a config/ directory for project-wide configurations (e.g., network settings, cryptographic parameters).

Proposed Refinements
Here’s an updated version of the file structure with some of the above suggestions incorporated:

Copy
Zyiron_Chain/
├── .vscode/                         # VSCode configuration files
│   ├── c_cpp_properties.json
│   ├── launch.json
│   └── settings.json
├── blockchain_lmdb/                 # LMDB database files
│   ├── data.mdb
│   └── lock.mdb
├── build/                           # Build artifacts
│   ├── bdist.win-amd64/
│   └── lib/
│       └── Zyiron_Chain/            # Compiled Python modules
├── config/                          # Project-wide configurations
│   ├── network_config.json
│   └── crypto_config.json
├── dist/                            # Distribution packages
│   └── kc-0.1-py3.12.egg
├── logs/                            # System logs
│   └── system.log
├── metadata_db/                     # Metadata database files
│   ├── 000003.log
│   ├── CURRENT
│   ├── LOCK
│   └── MANIFEST-000002
├── utxo_db/                         # UTXO database files
│   ├── 000003.log
│   ├── CURRENT
│   ├── LOCK
│   └── MANIFEST-000002
├── zyc/                             # Blockchain data
│   └── blockchain_data/
│       ├── blockchain.json
│       └── test_blockchain.json
├── Zyiron_Chain/                    # Core project directory
│   ├── accounts/                    # Wallet and account management
│   │   ├── account.py
│   │   ├── wallet.py
│   │   └── __init__.py
│   ├── backend/                     # Backend application
│   │   ├── app.py
│   │   └── routes/                  # API routes
│   │       ├── admin_routes.py
│   │       ├── block_routes.py
│   │       ├── transaction_routes.py
│   │       └── wallet_routes.py
│   ├── blockchain/                  # Core blockchain logic
│   │   ├── block.py
│   │   ├── blockchain.py
│   │   └── network/                 # Network management
│   │       ├── messaging.py
│   │       ├── node.py
│   │       └── peer_manager.py
│   ├── cryptography/                # Cryptographic implementations
│   │   ├── falcon/                  # Falcon cryptography
│   │   └── ntru/                    # NTRU cryptography (if applicable)
│   ├── database/                    # Database management
│   │   ├── leveldb/                 # LevelDB-specific files
│   │   │   ├── leveldbblocks.py
│   │   │   └── leveldbmeta.py
│   │   ├── lmdb/                    # LMDB-specific files
│   │   │   ├── dataquery.py
│   │   │   └── layer2db.py
│   │   ├── reset.py
│   │   ├── transactiondata.py
│   │   ├── utxodata.py
│   │   └── __init__.py
│   ├── offchain/                    # Off-chain transaction handling
│   │   ├── dispute.py
│   │   ├── instantpay.py
│   │   ├── multihop.py
│   │   └── __init__.py
│   ├── scripts/                     # Utility scripts
│   │   ├── deploy.py
│   │   ├── generate_genesis_block.py
│   │   ├── monitoring.py
│   │   ├── performance_tests.py
│   │   └── reset_blockchain.py
│   ├── smartpay/                    # Smart payment logic
│   │   ├── smartmempool.py
│   │   ├── smartpay.py
│   │   └── __init__.py
│   ├── transactions/                # Transaction handling
│   │   ├── Blockchain_transaction.py
│   │   ├── fees.py
│   │   ├── sendZYC.py
│   │   ├── transactiontype.py
│   │   ├── txout.py
│   │   └── __init__.py
│   ├── tests/                       # Test cases
│   │   ├── backend_tests/
│   │   ├── blockchain_tests/
│   │   ├── cryptography_tests/
│   │   ├── database_tests/
│   │   ├── frontend_tests/
│   │   └── integration_tests/
│   ├── docs/                        # Documentation
│   │   ├── api_reference.md
│   │   ├── architecture.md
│   │   ├── blockchain_spec.md
│   │   ├── faq.md
│   │   ├── security.md
│   │   ├── setup_guide.md
│   │   └── testing.md
│   ├── path.py                      # Path configuration
│   ├── README.md                    # Project overview
│   ├── requirements.txt             # Python dependencies
│   └── __init__.py                  # Package initialization
└── .venv/                           # Virtual environment
Next Steps
Review the updated structure and ensure all components are aligned with the project's goals.

Add any missing files or directories (e.g., ntru/, frontend/).

Update documentation to reflect any changes.