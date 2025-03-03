# Zyiron Chain - Post-Quantum Payment System
Version: 1.0 (Development)

# Vision & Mission
Zyiron Chain aims to be the most secure, efficient, and democratic payment system in the crypto space. It addresses key challenges such as PQC security, transaction efficiency, and governance that aligns with the community's best interests.

# Blockchain Overview
Zyiron Chain is a Post-Quantum Cryptography (PQC) resistant blockchain utilizing SHA3-384 for hashing and Falcon 1024 for digital signatures. It is structured into three layers:

Layer 1: Protocol Layer – Handles block creation, consensus (PoW with SHA3-384), and transaction validation.( what is being worked on the core protcol)
Layer 2: Instant Payments – Facilitates low-latency payments with multi-hop routing and batching. (under development)
Layer 3: Governance – A democratic system for upgrades, dispute resolution, and community voting (under development).


# Key Features
✅ Quantum-Resistant Security: SHA3-384 hashing & Falcon 1024 signatures.

✅ Three-Layer Architecture: Separation of core, payments, and governance.

✅ Instant Payments: Multi-hop routing for fast transactions.

✅ Smart Transactions: Programmable logic for automated transactions.

✅ Decentralized Governance: Community-driven blockchain upgrades.

✅ Dynamic Block Sizes: 1-10MB per block, depending on network traffic.

✅ Two Mempools:

✅ Standard Mempool → For regular and instant transactions.

✅Smart Mempool → For smart contract payments.

✅ Proof-of-Work Consensus: SHA3-384 PoW with 5-minute block times.

✅ Max Supply: 84,096,000 ZYC with halving every 420,480 blocks (~4 years).

✅ Governance Minting: Community can vote to mint up to 2x the total supply every 50 years with 90% approval.

✅ 3-Tier Tax Model:
Governance Fund
Smart Fund
Contributors Fund

✅ Database Architecture (Now fully using LMDB & TinyDB for storage):
LMDB stores UTXOs, mempool, transaction indexes, orphan blocks, fee stats, analytics.
TinyDB stores node configurations & session data.
block.data files store full blockchain data (1GB per file with magic numbers for easy retrieval).

✅ File-Based Blockchain Storage:

Blocks stored in block.data files 
Fast lookup via LMDB indexing.
1GB limit per block.data file, auto-rotates.
Updated Code Structure
The project is modular and divided into key components:

# Accounts and More 
1️⃣ Account & Wallet Management
wallet.py – Manages Falcon-based keys, transaction signing, and wallet interactions.
key_manager.py – Generates and secures Falcon keys with 


2️⃣ Blockchain Core
block.py – Defines block structure, validation, and PoW mining.
blockchain.py – Main blockchain logic, manages block creation, storage, and validation.
block_manager.py – Handles block storage and indexing in LMDB.
blockheader.py – Separates block header logic.


3️⃣ Mempools & Transaction Handling
standardmempool.py – Manages Standard & Instant Payments.
smartmempool.py – Handles Smart Transactions & priority processing.
transaction_manager.py – Routes transactions to the correct mempool.
transaction_services.py – Provides fee calculation, validation, and processing.
fees.py – Implements dynamic fee scaling based on congestion.

4️⃣ Payment Channels & Multi-Hop Routing
payment_channel.py – Handles HTLC-based off-chain transactions.
multihop.py – Implements multi-hop routing for faster payments.

5️⃣ Database & Storage
storage_manager.py – Manages block storage, UTXOs, mempool, and analytics.
poc.py – Point-of-Contact that routes data to the correct storage layer.

6️⃣ Mining & PoW
miner.py – SHA3-384 mining with dynamic difficulty adjustment.
coinbase.py – Handles block rewards and miner payouts.

7️⃣ Governance & Dispute Resolution
dispute.py – Smart contract for resolving transaction disputes.
governance.py – (Planned) Manages on-chain voting & protocol upgrades.
Getting Started

# 1️⃣ Install Dependencies

pip install -r requirements.txt

# 2️⃣ Run the Blockchain

python blockchain.py
(Genesis Block will be created automatically if not found.)

# 3️⃣ Generate Falcon Keys

python key_manager.py
(Interactive menu for key generation & management.)

# How to Contribute
1️⃣ Clone the Repository

git clone https://github.com/ZyironChain/ZyironChain-Dev.git
2️⃣ Create a New Branch

git checkout -b feature-branch
3️⃣ Commit & Push


4️⃣ Submit a Pull Request
All contributions must go through Pull Requests (PRs) and be reviewed.

# 🔒Branch Protection Rules:

No direct pushes to main – PR approval required.
At least 1 approval required before merging.
Auto-merge is disabled – Maintainers review each PR.

#🔒 **Repository Access Policy**

- **You must request approval before contributing.**
  
- Send an email to **zyironchain@gmail.com**
  
- or contact @Zyiron_Chain on Telegram.

- Provide your GitHub username and reason for contributing.
  
- Only approved contributors will be granted push/pull access.



# 5️⃣ Contact for PR Approval

Email: zyironchain@gmail.com

Instagram: @zyironchain

Telegram: @Zyiron_Chain

# Development Roadmap
Zyiron Chain is 60% complete. The core is functional, but key areas still need development:

# ✅ Built:

Core Blockchain (Block, Transactions, Mempools, Mining)
POW
Instant & Smart Transactions
LMDB & File-Based Storage
🛠 Needs Work:

# P2P Networking
Custodial Wallets BIP 39 MEMOPHRASE 
HTLC Smart Contracts for Instant Pay
Block Explorer & Analytics APIs
Code Debugging & Security Audits
Automated Fee Scaling
Multi-Hop Payment Optimization
Final Thoughts
🔹 Zyiron Chain is designed to be secure, scalable, and truly decentralized.
🔹 Community involvement is key – anyone can contribute.
🔹 Have questions? Email zyironchain@gmail.com or request a Zoom call.

🚀 Join us in building the future of decentralized payments! 🚀

