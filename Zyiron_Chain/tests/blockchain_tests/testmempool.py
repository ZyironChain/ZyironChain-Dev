import sys
import os

# Add the root directory of the project to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))



import hashlib
from decimal import Decimal
from Zyiron_Chain.transactions.sendZYC import SendZYC
from Zyiron_Chain.blockchain.utils.standardmempool import Mempool
from Zyiron_Chain.transactions.fees import FeeModel

class MockKeyManager:
    def __init__(self):
        self.keys = {
            "mainnet": {
                "defaults": {"miner": "miner1"},
                "keys": {
                    "miner1": {
                        "hashed_public_key": "mock_miner_public_key",
                        "private_key": "mock_private_key"
                    }
                }
            }
        }

    def get_default_public_key(self, network, role="miner"):
        return self.keys[network]["keys"][self.keys[network]["defaults"][role]]["hashed_public_key"]

    def get_private_key(self):
        return self.keys["mainnet"]["keys"]["miner1"]["private_key"]

class MockUTXOManager:
    def __init__(self):
        self.utxos = {
            "utxo1": {"amount": 1.0, "script_pub_key": "mock_script1"},
            "utxo2": {"amount": 2.0, "script_pub_key": "mock_script2"}
        }
        self.locked_utxos = set()

    def select_utxos(self, required_amount):
        total = 0
        selected = {}
        for utxo_id, utxo_data in self.utxos.items():
            if utxo_id not in self.locked_utxos:
                selected[utxo_id] = utxo_data
                total += utxo_data["amount"]
                if total >= required_amount:
                    break
        if total < required_amount:
            raise ValueError("Insufficient funds.")
        return selected

    def lock_selected_utxos(self, utxo_ids):
        for utxo_id in utxo_ids:
            self.locked_utxos.add(utxo_id)

# Test Script
if __name__ == "__main__":
    # Initialize components
    key_manager = MockKeyManager()
    utxo_manager = MockUTXOManager()
    mempool = Mempool()
    fee_model = FeeModel()

    # Instantiate SendZYC
    send_zyc = SendZYC(key_manager, utxo_manager, mempool, fee_model, network="mainnet")

    # Simulate transaction details
    recipient_script_pub_key = "mock_recipient_script"
    amount = Decimal("0.5")  # Send 0.5 ZYC
    block_size = 10  # Assume 10 MB block size
    payment_type = "Standard"  # Standard payment type

    print("\n[TEST] Starting Transaction Workflow Test...\n")

    try:
        # Step 1: Estimate transaction size
        estimated_tx_size = 250  # Example size in bytes
        print(f"[INFO] Estimated Transaction Size: {estimated_tx_size} bytes")

        # Step 2: Calculate the fee using FeeModel
        fee = send_zyc.calculate_fee(block_size, payment_type, estimated_tx_size)
        print(f"[INFO] Calculated Fee: {fee:.8f} ZYC")

        # Step 3: Prepare and create the transaction
        print("[INFO] Preparing transaction...")
        transaction = send_zyc.prepare_transaction(
            recipient_script_pub_key,
            amount,
            block_size,
            payment_type
        )
        print(f"[INFO] Transaction Created: {transaction}")

        # Step 4: Validate transaction in Mempool
        tx_id = transaction.tx_id
        if tx_id in mempool.transactions:
            print(f"[PASS] Transaction {tx_id} successfully added to the Mempool.")
        else:
            print(f"[FAIL] Transaction {tx_id} not found in the Mempool.")

        # Step 5: Output detailed transaction info
        print("\n[DETAILED TRANSACTION REPORT]")
        print(f"Transaction ID: {tx_id}")
        print(f"Inputs: {len(transaction.tx_inputs)}")
        print(f"Outputs: {len(transaction.tx_outputs)}")
        for i, tx_in in enumerate(transaction.tx_inputs, 1):
            print(f"  Input {i}: {tx_in.tx_out_id}")
        for i, tx_out in enumerate(transaction.tx_outputs, 1):
            print(f"  Output {i}: {tx_out.amount:.8f} to {tx_out.script_pub_key}")

    except Exception as e:
        print(f"[ERROR] {e}")

    print("\n[TEST] Transaction Workflow Test Complete.")
