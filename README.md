# Zyiron Chain - Post-Quantum Payment System
### Version: 1.0 (Development)

## 🔹 Vision & Mission
Zyiron Chain is designed to be the most secure, efficient, and community-driven payment system. By leveraging post-quantum cryptography (PQC), efficient blockchain storage, and decentralized governance, it ensures robust security, seamless payments, and network scalability.

---

## 🔹 Blockchain Overview
Zyiron Chain utilizes **SHA3-384** hashing and **Falcon 512** for digital signatures, making it quantum-resistant.:

1️⃣ **Layer 1: Core Protocol** – Handles block creation, PoW consensus, and transaction validation.
2️⃣ **Layer 2: Instant Payments** – Supports multi-hop routing and batching for low-latency payments.


> **Current Status:** Layer 1 is fully implemented, and being debugged while Layer 2 is till under active development.

---

## 🔹 Key Features
✅ **Quantum-Resistant Security**: SHA3-384 hashing & Falcon 512 signatures.
✅ **Three-Layer Architecture**: Separation of core, payments, and governance.
✅ **Instant Payments**: Multi-hop routing for fast transactions.
✅ **Smart Transactions**: Programmable logic for automated transactions.Also know as SmartPay (under active development)
✅ **Decentralized Governance**: Community-driven blockchain upgrades.
✅ **Dynamic Block Sizes**: 1MB-10MB per block, depending on network traffic 300 second blocks
✅ **Two Mempools**:
   - **Standard Mempool** → Regular & Instant Transactions.
   - **Smart Mempool** → Smart Contract Transactions.
✅ **Proof-of-Work Consensus**: SHA3-384 PoW with dynamic difficulty adjustments.
✅ **Max Supply**: 77,777,777 ZYC,ƶ no havling fixed block reward a 7 ZYC, utill max supply is mined 
   - **Smart Fund** 
✅ **Optimized Storage System**:
   - **LMDB**: Stores UTXOs, mempool, transactions, orphan blocks, fees, and analytics.
   - **TinyDB**: Manages node configurations & session data.
   - **block.data**: Full blockchain stored in indexed 512mb binary files.

---

## 🔹 Updated Code Structure
The project is modular and divided into key components:

### 🔹 **Accounts & Wallet Management**
1️⃣ **`wallet.py`** – Manages Falcon-based keys, signing, and wallet interactions.
2️⃣ **`key_manager.py`** – Generates and secures Falcon keys.

### 🔹 **Blockchain Core**
3️⃣ **`block.py`** – Defines block structure, validation, and mining operations.
4️⃣ **`blockchain.py`** – Manages the chain, storage, and validation processes.
5️⃣ **`block_manager.py`** – Handles block indexing in LMDB.
6️⃣ **`blockheader.py`** – Separates block header logic.

### 🔹 **Mempool & Transaction Handling**
7️⃣ **`standardmempool.py`** – Handles standard and instant transactions.
8️⃣ **`smartmempool.py`** – Manages smart contract transactions.
9️⃣ **`transaction_manager.py`** – Routes transactions to the correct mempool.
🔟 **`fees.py`** – Implements dynamic fee scaling based on congestion.

### 🔹 **Payment Channels & Multi-Hop Routing**
1️⃣1️⃣ **`payment_channel.py`** – Manages HTLC-based off-chain transactions.
1️⃣2️⃣ **`multihop.py`** – Implements multi-hop routing for faster payments.

### 🔹 **Database & Storage**
1️⃣3️⃣ **`block_storage.py`** – Stores full blocks in `block.data`.
1️⃣4️⃣ **`blockmetadata.py`** – Stores LMDB-based block headers.
1️⃣5️⃣ **`tx_storage.py`** – Manages indexed transaction storage.
1️⃣6️⃣ **`utxostorage.py`** – Stores UTXOs with LMDB.
1️⃣7️⃣ **`lmdatabase.py`** – Manages blockchain-related LMDB interactions.

### 🔹 **Mining & Proof-of-Work**
1️⃣8️⃣ **`miner.py`** – Implements SHA3-384 mining with dynamic difficulty.
1️⃣9️⃣ **`pow.py`** – Manages Proof-of-Work calculations.

### 🔹 ** Dispute Resolution**
2️⃣0️⃣ **`dispute.py`** – Smart contract logic for resolving disputes.


---

## 🔹 Getting Started

### 1️⃣ **Install Dependencies**
```bash
pip install -r requirements.txt
```

### 2️⃣ **Run the Blockchain**
```bash
python start.py
```
*Genesis Block will be created automatically if not found.*

### 3️⃣ **Generate Falcon Keys**
```bash
python key_manager.py
```
*Interactive menu for key generation & management.*

---

## 🔹 How to Contribute

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/ZyironChain/ZyironChain-Dev.git
```

### 2️⃣ Create a New Branch
```bash
git checkout -b feature-branch
```

### 3️⃣ Commit & Push
```bash
git add .
git commit -m "Your commit message"
git push origin feature-branch
```

### 4️⃣ Submit a Pull Request
*All contributions must go through Pull Requests (PRs) and be reviewed.*

#### 🔒 **Branch Protection Rules:**
- No direct pushes to `main` – PR approval required.
- At least **1 approval required** before merging.
- Auto-merge is disabled – Maintainers review each PR.

#### 🔒 **Repository Access Policy**
- **You must request approval before contributing.**
- Send an email to **zyironchain@gmail.com** or contact **@Zyiron_Chain** on Telegram.
- Provide your **GitHub username** and reason for contributing.
- Only approved contributors will be granted push/pull access.

---

## 🔹 Contact for PR Approval
📩 **Email:** zyironchain@gmail.com
📷 **Instagram:** @zyironchain
💬 **Telegram:** @Zyiron_Chain

---

## 🔹 Development Roadmap

✅ **Built:**
- Core Blockchain (Block, Transactions, Mempools, Mining)
- SHA3-384 Proof-of-Work
- Instant & Smart Transactions
- LMDB & File-Based Storage

🛠 **Needs Work:**
- P2P Networking
- Custodial Wallets (BIP39 Mnemonic Support)
- HTLC Smart Contracts for Instant Pay
- Block Explorer & Analytics APIs
- Code Debugging & Security Audits
- Multi-Hop Payment Optimization

---

## 🔹 Final Thoughts
🔹 Zyiron Chain is **secure, scalable, and truly decentralized**.
🔹 **Community involvement is key** – anyone can contribute.
🔹 Have questions? Email **zyironchain@gmail.com** or request a Zoom call.

🚀 **Join us in building the future of decentralized payments!** 🚀

