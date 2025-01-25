import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if project_root not in sys.path:
    sys.path.append(project_root)

import time
import hashlib
from decimal import Decimal

# Import your blockchain classes and methods
from Kyiron_Chain.blockchain.blockchain import Blockchain
from Kyiron_Chain.blockchain.Blockchain_transaction import Transaction, TransactionIn, TransactionOut
from Kyiron_Chain.blockchain.block import Block
from Kyiron_Chain.blockchain.utils.key_manager import KeyManager


def validate_block_headers(blockchain):
    """
    Validate the block headers in the blockchain.
    """
    for i in range(1, len(blockchain.chain)):
        current_block = blockchain.chain[i]
        previous_block = blockchain.chain[i - 1]

        # Check previous hash linkage
        if current_block.header.previous_hash != previous_block.calculate_hash():
            print(f"[FAIL] Block {i}: Invalid previous hash linkage.")
            return False

        # Validate Merkle root
        computed_merkle_root = current_block.calculate_merkle_root()
        if current_block.header.merkle_root != computed_merkle_root:
            print(f"[FAIL] Block {i}: Invalid Merkle root. Expected: {computed_merkle_root}, Found: {current_block.header.merkle_root}")
            return False

        # Validate block hash meets target
        block_hash = int(current_block.calculate_hash(), 16)
        if block_hash > current_block.header.target:
            print(f"[FAIL] Block {i}: Hash does not meet target difficulty.")
            return False

    print("[PASS] All block headers are valid.")
    return True


def run_consensus_test():
    """
    Test the consensus mechanism and block header validity.
    """
    print("[INFO] Running consensus and block header validation test...")

    # Initialize KeyManager
    key_manager = KeyManager()  # Create the key manager

    # Initialize blockchain with KeyManager
    blockchain = Blockchain(key_manager=key_manager)

    # Simulate adding blocks
    for _ in range(3):
        # Create dummy transactions with valid inputs and outputs
        transactions = [
            Transaction(
                tx_inputs=[
                    TransactionIn(
                        tx_out_id="dummy_tx_out_id",
                        script_sig="dummy_signature"
                    )
                ],
                tx_outputs=[
                    TransactionOut(
                        amount=10,  # Ensure this matches the class definition
                        script_pub_key="test_address"  # Adjust if necessary
                    )
                ]
            )
        ]
        blockchain.add_block(transactions)

    # Validate the blockchain
    print("[INFO] Validating the blockchain...")
    if validate_block_headers(blockchain):
        print("[PASS] Blockchain consensus test passed.")
    else:
        print("[FAIL] Blockchain consensus test failed.")


if __name__ == "__main__":
    run_consensus_test()
