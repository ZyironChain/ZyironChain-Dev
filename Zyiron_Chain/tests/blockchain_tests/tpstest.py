import os
import sys
import time
import random
import hashlib
import json
from decimal import Decimal

import sys
import os

# Dynamically add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(project_root)

# Import necessary blockchain components
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction, TransactionIn, TransactionOut
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
from Zyiron_Chain.database.poc import PoC  # Ensures transactions are routed correctly
from Zyiron_Chain.database.sqlitedatabase import SQLiteDB
from Zyiron_Chain.database.lmdatabase import LMDBManager
from Zyiron_Chain.database.unqlitedatabase import BlockchainUnqliteDB
from Zyiron_Chain.database.duckdatabase import AnalyticsNetworkDB
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager
from Zyiron_Chain.accounts.wallet import Wallet

from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction, TransactionIn, TransactionOut
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
from Zyiron_Chain.database.poc import PoC  # Ensures transactions are routed correctly
from Zyiron_Chain.database.sqlitedatabase import SQLiteDB
from Zyiron_Chain.database.lmdatabase import LMDBManager
from Zyiron_Chain.database.unqlitedatabase import BlockchainUnqliteDB
from Zyiron_Chain.database.duckdatabase import AnalyticsNetworkDB
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager
from Zyiron_Chain.accounts.wallet import Wallet
import logging
# Initialize required components
poc = PoC()  # Ensures proper routing
key_manager = KeyManager()
sqlite_db = SQLiteDB()
lmdb_manager = LMDBManager()
unqlite_db = BlockchainUnqliteDB()
analytics_db = AnalyticsNetworkDB()
fee_model = FeeModel(max_supply=Decimal("84096000"))

# **Fixed Function: Fetch Unspent UTXOs**
def get_unspent_utxos():
    """
    Retrieve all unspent UTXOs from SQLite via PoC.
    """
    utxos = poc.sqlite_db.fetch_all_utxos()
    if not utxos:
        logging.warning("[WARNING] No UTXOs available in SQLite.")
    return utxos


# **Falcon 512 Signing from KeyManager**
def sign_transaction(tx_id, network, role="channel"):
    """Sign a transaction using the private key from KeyManager."""
    private_key = key_manager.get_private_key_for_channel(network, role)
    wallet = Wallet()
    return wallet.sign_transaction(tx_id.encode(), network)





def preload_utxos(amount=1000):
    """
    Preload UTXOs into SQLite before running TPS tests.
    """
    print("[INFO] Preloading UTXOs into SQLite...")

    for _ in range(amount):
        utxo_id = hashlib.sha3_384(str(random.randint(1, 999999999)).encode()).hexdigest()
        tx_out_id = hashlib.sha3_384(str(random.randint(1, 999999999)).encode()).hexdigest()
        script_pub_key = key_manager.get_default_public_key("mainnet", "recipient")  # ✅ Use default recipient key
        utxo_data = {
            "tx_out_id": tx_out_id,
            "amount": round(random.uniform(0.1, 10), 8),  # ✅ Random UTXO amount
            "script_pub_key": script_pub_key,
            "locked": False,
            "block_index": 0  # ✅ Default to unconfirmed state
        }

        poc.store_utxo(utxo_id, utxo_data)

    print("[INFO] UTXOs successfully preloaded!")


def generate_random_transaction(prefix: str):
    """
    Generate a transaction using real UTXOs from SQLite.
    """
    utxos = get_unspent_utxos()  # ✅ Get real UTXOs

    if not utxos:
        print("[ERROR] No available UTXOs. Cannot create transaction.")
        return None

    # ✅ Select a valid UTXO
    selected_utxo = random.choice(utxos)

    tx_id = f"{prefix}{random.randint(100000, 999999)}"

    # ✅ Use miner's public key (same as hashed public key)
    miner_public_key = key_manager.get_default_public_key("mainnet", "miner")

    # ✅ Ensure miner has a valid signing key
    if not miner_public_key:
        print("[ERROR] Miner public key is missing.")
        return None

    # ✅ Use a valid input UTXO
    inputs = [
        TransactionIn(
            tx_out_id=selected_utxo["tx_out_id"],
            script_sig=key_manager.sign_transaction(tx_id, "mainnet", "miner")  # ✅ Sign with miner key
        )
    ]

    # ✅ Ensure recipient public key exists
    try:
        recipient_address = key_manager.get_default_public_key("mainnet", "recipient")
    except ValueError:
        print("[WARNING] No recipient key found. Using miner key as recipient.")
        recipient_address = miner_public_key  # Fallback to miner key if recipient key is missing

    # ✅ Deduct transaction fee and prevent negative outputs
    amount_to_send = max(selected_utxo["amount"] - 0.0001, 0)

    # ✅ Create the output (ensures no negative amount)
    outputs = []
    if amount_to_send > 0:
        outputs.append(TransactionOut(script_pub_key=recipient_address, amount=amount_to_send))
    else:
        print("[ERROR] Insufficient UTXO amount after fee deduction. Skipping transaction.")
        return None

    # ✅ Create the transaction
    return Transaction(inputs=inputs, outputs=outputs, tx_id=tx_id)



# **Validate Transaction Lifecycle**
def validate_transaction(tx):
    """Ensure transaction is properly routed and processed."""
    if not tx:
        return False

    # Step 1: Add transaction to mempool (LMDB)
    lmdb_manager.add_transaction(tx.tx_id, tx.to_dict())

    # Step 2: Validate UTXOs before block confirmation
    for inp in tx.inputs:
        utxo = sqlite_db.fetch_utxo(inp.tx_out_id)
        if not utxo:
            print(f"[ERROR] UTXO {inp.tx_out_id} not found in SQLite!")
            return False

    # Step 3: Check transaction in mempool
    pending_tx = lmdb_manager.get_transaction(tx.tx_id)
    if not pending_tx:
        print(f"[ERROR] Transaction {tx.tx_id} not found in mempool!")
        return False

    # Step 4: Simulate block confirmation
    unqlite_db.store_transaction(tx)

    # Step 5: Verify transaction stored in UnQLite
    stored_tx = unqlite_db.get_transaction(tx.tx_id)
    if not stored_tx:
        print(f"[ERROR] Transaction {tx.tx_id} failed to store in blockchain.")
        return False

    print(f"[SUCCESS] Transaction {tx.tx_id} processed successfully.")
    return True




# ✅ Define benchmark_tps() First
def benchmark_tps():
    """
    Runs TPS benchmark:
    1. Generates transactions
    2. Adds them to blocks
    3. Computes Merkle Root
    4. Stores blocks in PoC
    5. Displays TPS
    """
    max_block_size_bytes = 10 * 1024 * 1024  # ✅ Max block size: 10MB
    transactions_per_block = 2000  # ✅ Adjust based on testing needs

    block_index = 0
    total_transactions = 0
    start_time = time.time()

    while total_transactions < 100000:
        print(f"\n[INFO] Creating Block {block_index}...")
        block_transactions = []
        current_block_size = 0

        while len(block_transactions) < transactions_per_block and current_block_size < max_block_size_bytes:
            tx = generate_random_transaction("PID-")

            if tx is None:
                break  # ✅ Stop if no transactions are generated

            block_transactions.append(tx)
            current_block_size += tx.size_bytes  # ✅ Track block size

        # ✅ Ensure transactions processed
        if not block_transactions:
            print("[ERROR] No transactions added. Skipping block.")
            break

        # ✅ Create Block Object (Auto-Calculates Merkle Root)
        block = Block(
            index=block_index,
            previous_hash=poc.get_last_block().hash if block_index > 0 else "0" * 96,
            transactions=block_transactions,
            timestamp=time.time(),
            key_manager=key_manager
        )

        # ✅ Store Block in PoC (which routes it to UnQLite)
        block.store_block()

        # ✅ Print TPS Performance
        elapsed_time = time.time() - start_time
        tps = total_transactions / elapsed_time if elapsed_time > 0 else 0
        print(f"[BLOCK {block_index}] {current_block_size / 1_000_000:.2f}MB Block - Processed {len(block_transactions)} transactions @ {tps:.2f} TPS")

        total_transactions += len(block_transactions)
        block_index += 1



def get_unspent_utxos():
    """
    Retrieve all available UTXOs from SQLite.
    """
    utxos = sqlite_db.fetch_all_utxos()
    
    if not utxos:
        print("[WARNING] No UTXOs available in SQLite.")
        return []

    return utxos


# ✅ Define run_full_tps_test() After benchmark_tps()
def run_full_tps_test():
    """
    Runs the full TPS test including:
    1. Preloading UTXOs
    2. Generating transactions
    3. Processing transactions into blocks
    4. Measuring TPS performance
    """
    print("[INFO] Starting TPS Benchmark...")

    # ✅ Step 1: Preload UTXOs into SQLite
    preload_utxos(1000)  # Preload UTXOs before the test

    # ✅ Step 2: Run TPS Benchmark
    benchmark_tps()

# ✅ Run the test if the script is executed
if __name__ == "__main__":
    run_full_tps_test()
