# WHITE PAPER VERISON 1.0 DEV VERISON HIGH OVERVIEW 


# Vison & Mission

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

A 5 database system to ensure scalability and speed 

Dyamic block sizes 1-10 mb depending on network traffic 
TPS estiamte 7-150 

2 mempools that are desinged to pirotize PID CID= istnat payments 
S- = smart payemtns based on these rules which a deailed white paper will be written about 

Max supply will be 84,096,000
block times 5 min block confirmation 
POW is the consensus using Sha3-384 which is also PQC resistant 


# Governance insight 

 governace will have the ablity to mint up 
2x the max once all supply has been mined up to 25% 
of the total at a time or about 25 million ZYC 
once evey 50 years up to 2x the amount of the max suppy 
if community votes 90% on these proposals 
but thats a goverance thing and im working on the book 
for the rules ablities to upgrade security 
the blockchain will be backwards compatible to insure 
we are furthre proofing and its bere long after the founders 
all this is still being worked on im writting up a
small book of the governace rules and guidelines 
there is also a tax model 3 differnt fund 
Goverance Fund
Smart Fund 
Contributors Fund

these 3 funds have been very well defined in the book 
and there roles 

The goverance is a true democratic system 
with a economy inside of an economy 

Also 

The analysis and analyics models 
I have support this growth and how sustainable it is 
All the addtional Governance Documents I can 
email over to any party interested learning more 


# Code Structure
The codebase is organized into several key components:

1. Account and Wallet Management
Account Class: Manages user accounts with Falcon-based public/private keys for signing and verifying messages.

Wallet Class: Handles key generation, transaction signing, and verification for both testnet and mainnet.

2. Blockchain Core
Block Class: Represents a block in the blockchain, including block headers, transactions, and mining logic.

3.Blockchain Class: Manages the blockchain, including block creation, validation, and UTXO management.

4.Mempool Classes: Handles pending transactions, fee calculation, and transaction prioritization.

5. Transaction Handling
Transaction Class: Represents a blockchain transaction with inputs, outputs, and fees.

6.Smart Transactions: Supports advanced transaction types with programmable logic.

7.Fee Model: Calculates transaction fees based on block size, congestion, and payment type.

8.Payment Channels and Multi-Hop Routing
PaymentChannel Class: Manages off-chain payment channels for instant transactions.

9.MultiHop Class: Implements multi-hop routing for efficient transaction batching and forwarding.

10.Database and Storage
UnQLite, SQLite, LMDB, DuckDB: Various databases for storing blockchain data, UTXOs, and analytics.

11.DatabaseSyncManager: Synchronizes data across multiple databases for consistency and redundancy.

12.Governance and Dispute Resolution
DisputeResolutionContract: Handles dispute resolution for transactions and payment channels.


# Getting Started
Prerequisites
Python 3.8 or higher
Required Python packages: unqlite, lmdb, duckdb, sqlite, tinydb, 
pip install -r requirements.txt
needs to be updated but they all python native installs 
The lsit is blank but will be updated 

# Run the blockchain: 
Go to blockchain.py and just run the script 
there will be erros updates get submitted daily

# Generate Falcon keys
Genrating Keys 
go to keymanager.py and generate the keys there is an interactive menu and just set them as default 



# License
This project is licensed under the MIT License. See the LICENSE file for details.

# Commit Approavls 

you must email @zyironchain@gmail.com 
message on instagram @zyironchain 
or telegram @Zyiron_Chain
details about your improvements 
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

# The custodial HKTD wallet 

HKTD Wallet System Summary
The HKTD Wallet is a high-security custodial wallet designed to provide secure key management, encryption, and transaction obfuscation using AES-256-GCM encryption and Falcon 1024 cryptography. It ensures secure wallet recovery, private key protection, and transaction privacy.

1. Master Seed & Recovery System
The wallet is powered by a 2048-bit hexadecimal master seed, serving as the ultimate key for:
Recovering lost wallets
Decrypting all stored wallet data, including private keys
Signing transactions when needed
This master seed allows for full wallet restoration, ensuring seamless access to encrypted data while maintaining security.

2. Dual Use of Falcon Cryptography
A. Falcon for Address Generation (ZYC & ZYT Networks)
The HKTD Wallet generates addresses for the ZYC (Mainnet) and ZYT (Testnet) networks using Falcon 1024.
Process:

Key Pair Generation: A Falcon 1024 private and public key pair is created.
Public Key Hashing: The public key is hashed to create a base address hash.
Network-Specific Prefixing:

ZYC (Mainnet) addresses start with KYZ
ZYT (Testnet) addresses start with KCT
Final Address Generation: The network prefix is added, and the address is finalized.
B. Falcon + AES-256-GCM for Wallet Encryption

Private keys, master seed, and sensitive data are encrypted using AES-256-GCM, ensuring high-security protection.
Falcon 1024 is also used to generate digital signatures that ensure the authenticity and integrity of encrypted wallet data.
Decryption & Access Control:
The master seed is required to decrypt private keys.
Each key is stored in an encrypted vault within the wallet, accessible only after authentication.
Multi-Factor Authentication (MFA) adds additional security to prevent unauthorized access.

4. Transaction Lifecycle & Privacy Mechanism
To enhance transaction privacy and prevent tracking, every transaction follows a salted and cryptographic validation process:

Step 1: Transaction Creation
Input Selection:
The wallet selects UTXOs that are tied to salted hashes for spending.
Transaction Details Include:
Salted Hash: Ensures that transactions cannot be linked through predictable patterns.
Raw Public Key: Allows recomputation of the base hash for ownership verification.
Salt: Required to recompute the salted hash and validate the transaction.
Signature: The transaction is signed using the Falcon private key.

Step 2: Transaction Validation
Recompute Salted Hash:
Formula: recomputed_hash = SHA3_384(public_key + salt)
Ownership Verification:
The base hash derived from the public key is compared with the UTXO database hash.
Signature Validation:
The Falcon public key is used to verify that the transaction signature is authentic.
 Signing & Secure Key Access
 
The wallet derives Falcon key pairs from the master seed for:
Address generation (ZYC & ZYT networks)
Transaction signing & authentication
Private keys are encrypted and only accessible through the master seed, ensuring they remain secure and hidden at all times.
Transaction signing is performed using Falcon cryptography, providing strong authentication and integrity for blockchain transactions.


# Where the project currently is 
Zyiron Chain is about 40% done 
there is alot of work that needs to be done 
im inviting the community to build this with me 
The core has been built alot of the Algorithms in place 
and everything in overview 
for the most part has been built and it has reached 
a point where I need help to help humanity 




# Things that need to be worked on 
there is alot if work these are just a few 

the p2p needs to be built 

the wallet using NTRU 

debugging logic refinement 

code refactoring 

frontend / block explore / analytics APIS

Database Management

Off-Chain and Smart Payment Logic has been built about 70 percent 

Testing it all 

making sure all the databases communicate and work togther 

building the goversnce layer or layer 3with the tax model 

I created a tax model evrybody gets rewards 

AI for goverance to reduce human needs

off chain pay or instant oay needs refined or layer 3

smart pay logic 

security audits on the blockchain 

instant pay HTLC hash locked contract for the smart pay

the POC or point of contact where data bases 

and blockchain meet to get routed to where they need to be 



# Community Development: Engage the community in testing, feedback, and contributions.

We welcome contributions from the community! If you'd like to contribute, please follow the steps 

im welcome to all questions about the project and would 

love to answer them everything cant be answered 

in this read me but 9/10 I have already thought about it 

Just havent go to it yet please email me 

ask all the questions im also open to zoom calls 

zyironchain@gmail.com 



























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

there is always constant updates 

Update documentation to reflect any changes.
