# WHITE PAPER VERISON 1.0 DEV VERISON HIGH OVERVIEW 


#Goal 

Be the most secure, democratic, efficent Payment 
system in the crypto space and address the biggest promblems 
suchs as PQC cheap teansactions, security and
having voices heard to move the project in the direction 
of the communities best instrest 

# Zyiron Chain - PQC Payment System Overview

Zyiron Chain is a Post-Quantum Cryptography (PQC) resistant payment system designed to provide secure, scalable, and efficient transactions. It leverages SHA3-384 for hashing and Falcon 1024 for digital signatures, ensuring quantum-resistant security. The system is structured into three layers:

Layer 1: Protocol Layer - The foundational layer handling core blockchain operations, including block creation, consensus, and transaction validation.

Layer 2: Instant Payments - A layer dedicated to fast, low-latency transactions using advanced routing and batching techniques.

Layer 3: Governance - A governance layer (still under development) that will manage network upgrades, dispute resolution, and community-driven decision-making.

# Key Features
Quantum-Resistant Security: Utilizes SHA3-384 for hashing and Falcon 1024 for digital signatures, ensuring resistance against quantum computing attacks.

Three-Layer Architecture: Separates protocol, instant payments, and governance for modularity and scalability.

Instant Payments: Supports fast, low-latency transactions with multi-hop routing and batching.

Smart Transactions: Enables programmable logic for advanced payment scenarios.

Community-Driven Development: Prioritizes community involvement, code refactoring, and debugging to ensure a robust and user-friendly system.

# Technologies Used
SHA3-384: A cryptographic hash function used for secure hashing of transactions and blocks. NTRU for custodal wallets 

Falcon 1024: A post-quantum digital signature algorithm used for signing transactions and ensuring authenticity.

Blockchain Fundamentals: Proof-of-Work (PoW), UTXO model, and Merkle trees for transaction validation and block integrity.

a 5 database system to ensure scalability and speed 

Dyamic block sizes 1-10 mb depending on network traffic 
TPS estiamte 7-150 

2 mempools that are desinged to pirotize PID CID= istnat payments 
S- = smart payemtns based on these rules which a deailed white paper will be written about 

Max supply will be 84,096,000
block times 5 mins 

also governace will have the ablity to mint up 
2x the max once all supply has been mined up to 25% 
of the total at a time or about 25 million ZYC 
once evey 50 years up to 2x the amount of the max suppy 
if community votes 90% on these proposals 
but thats a goverance thing and im working on the book 
for the rules 


# Code Structure
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


# Getting Started
Prerequisites
Python 3.8 or higher
Required Python packages: unqlite, lmdb, duckdb, sqlite, tinydb, 
pip install -r requirements.txt
needs to be updated but they all python native installs 
The lsit is blank but will be updated 

# Run the blockchain: 
go to blockchan.py and just run the script 

# Generate Falcon keys
Genrating Keys 
go to keymanager.py and generate the keys there is an interactive menu and just set them as default 



# License
This project is licensed under the MIT License. See the LICENSE file for details.

# Commit Approavls 

you must email @zyironchain@gmail.com 
message on instagram @zyironchain 
or telegram @Zyiron_Chain
expalin your improvements 
where you made changes and why 
who you are 
and anything else you would like to add 

# Custodial Wallets and keys 
will be made using NTRU a PQC encryption 
which will store the private keys for the wallets 
and the public keys 
because falcon keys I created the key Manager 
the script pub key or public key is a sha3-384 hash 
of the raw public key 

the wallet.py will hold the APIs for exahnges and third 
parties becuase they have there own way of storing things 
so it provides raw keys 

the custodal wallets for the apple and andorid store 
wallets will be made with some of the strongest encryption 
PQC ready which is what I will recommend ZYC holders 
to store in and olus you have more control. 







# Things that need to be worked on 
there is alot if work these are just a few 
the p2p needs to be built 
the wallet using NTRU 
debugging logic refinement 
code refactoring 
frontend 
Database Management:
Off-Chain and Smart Payment Logic has been built about 70 percent 
Testing it all 
making sure all the databases communicate and work togther 
building the goversnce layer or layer 3with the tax model 
I created a tax model evrybody gets rewards 
AI for goverance to reduce human needs to a minium 
off chain pay or instant oay needs refined or layer 3
smart pay logic 
security audits on the blockchain 



# Community Development: Engage the community in testing, feedback, and contributions.

We welcome contributions from the community! If you'd like to contribute, please follow the steps 


























# FILE STRUCTURE OPEN UP FULL READ ME TO VIEW 





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
