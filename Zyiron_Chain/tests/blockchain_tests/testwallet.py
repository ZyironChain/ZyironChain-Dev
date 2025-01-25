import os
import json
import base64
import hashlib
import unittest
import sys
import time
# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
sys.path.append(project_root)

from Zyiron_Chain.accounts.wallet import Wallet, serialize_complex
from Zyiron_Chain.falcon.falcon.falcon import SecretKey, PublicKey


from hashlib import sha3_384
from Zyiron_Chain.accounts.wallet import Wallet

from Zyiron_Chain.accounts.wallet import Wallet, serialize_complex

def test_wallet():
    """
    Comprehensive test for Wallet functionality with performance metrics.
    """
    print("\n--- Starting Wallet Tests ---")

    # Initialize test variables
    wallet_file = "test_wallet_keys.json"
    test_message = b"This is a test transaction."

    # Step 1: Test Key Generation
    print("\n[1] Testing Key Generation")
    start_time = time.perf_counter()
    wallet = Wallet(wallet_file=wallet_file)
    end_time = time.perf_counter()

    assert wallet.testnet_secret_key is not None, "Testnet private key not generated."
    assert wallet.mainnet_secret_key is not None, "Mainnet private key not generated."
    assert wallet.testnet_public_key is not None, "Testnet public key not generated."
    assert wallet.mainnet_public_key is not None, "Mainnet public key not generated."

    print(f"Key generation: SUCCESS (Time taken: {end_time - start_time:.4f} seconds)")

    # Step 2: Test Key Serialization and Hashing
    print("\n[2] Testing Key Serialization and Hashing")
    start_time = time.perf_counter()
    testnet_hashed_public_key = wallet.public_key("testnet")
    mainnet_hashed_public_key = wallet.public_key("mainnet")
    end_time = time.perf_counter()

    assert testnet_hashed_public_key.startswith("KCT"), "Testnet public key prefix incorrect."
    assert mainnet_hashed_public_key.startswith("KYZ"), "Mainnet public key prefix incorrect."

    print(f"Testnet hashed public key: {testnet_hashed_public_key}")
    print(f"Mainnet hashed public key: {mainnet_hashed_public_key}")
    print(f"Key serialization and hashing: SUCCESS (Time taken: {end_time - start_time:.4f} seconds)")

    # Step 3: Test Key Storage
    print("\n[3] Testing Key Storage")
    start_time = time.perf_counter()
    assert os.path.exists(wallet_file), "Wallet file not created."

    with open(wallet_file, "r") as file:
        data = json.load(file)
        testnet_stored_key = next((item for item in data if item["network"] == "testnet"), None)
        mainnet_stored_key = next((item for item in data if item["network"] == "mainnet"), None)

        assert testnet_stored_key is not None, "Testnet key not stored in wallet file."
        assert mainnet_stored_key is not None, "Mainnet key not stored in wallet file."
    end_time = time.perf_counter()

    print(f"Key storage: SUCCESS (Time taken: {end_time - start_time:.4f} seconds)")

    # Step 4: Test Message Signing and Verification
    print("\n[4] Testing Message Signing and Verification")

    # Testnet signing and verification
    start_time = time.perf_counter()
    testnet_signature = wallet.sign_transaction(test_message, "testnet")
    assert wallet.verify_transaction(test_message, testnet_signature, "testnet"), \
        "Testnet signature verification failed."
    end_time = time.perf_counter()

    print(f"Testnet signature: {testnet_signature}")
    print(f"Testnet signing and verification: SUCCESS (Time taken: {end_time - start_time:.4f} seconds)")

    # Mainnet signing and verification
    start_time = time.perf_counter()
    mainnet_signature = wallet.sign_transaction(test_message, "mainnet")
    assert wallet.verify_transaction(test_message, mainnet_signature, "mainnet"), \
        "Mainnet signature verification failed."
    end_time = time.perf_counter()

    print(f"Mainnet signature: {mainnet_signature}")
    print(f"Mainnet signing and verification: SUCCESS (Time taken: {end_time - start_time:.4f} seconds)")

    # Step 5: Test Cross-Check Between Networks
    print("\n[5] Testing Cross-Network Signing and Verification")

    start_time = time.perf_counter()
    assert not wallet.verify_transaction(test_message, testnet_signature, "mainnet"), \
        "Testnet signature incorrectly verified on mainnet."
    assert not wallet.verify_transaction(test_message, mainnet_signature, "testnet"), \
        "Mainnet signature incorrectly verified on testnet."
    end_time = time.perf_counter()

    print(f"Cross-network verification: SUCCESS (Time taken: {end_time - start_time:.4f} seconds)")

    # Step 6: Test Error Handling
    print("\n[6] Testing Error Handling")

    start_time = time.perf_counter()
    try:
        wallet.sign_transaction(test_message, "invalid_network")
        assert False, "Invalid network did not raise an error."
    except ValueError as e:
        print(f"Caught expected error for invalid network: {e}")

    try:
        wallet.verify_transaction(test_message, b"invalid_signature", "testnet")
        assert False, "Invalid signature did not raise an error."
    except Exception as e:
        print(f"Caught expected error for invalid signature: {e}")
    end_time = time.perf_counter()

    print(f"Error handling: SUCCESS (Time taken: {end_time - start_time:.4f} seconds)")

    print("\n--- All Wallet Tests Completed Successfully ---")

if __name__ == "__main__":
    test_wallet()
