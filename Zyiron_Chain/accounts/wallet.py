import sys
import os
import base64
import json

import hashlib 
from hashlib import sha3_384

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)


from Zyiron_Chain.falcon.falcon.falcon import SecretKey, PublicKey
def serialize_complex(obj):
    """
    Custom serializer for complex numbers.
    """
    if isinstance(obj, complex):
        return {"real": obj.real, "imag": obj.imag}
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

class Wallet:
    """
    Represents a wallet with public and private keys for signing and verifying transactions.
    """

    def __init__(self, wallet_file="Keys/Wallet_API_Keys.json"):
        """
        Generate keys for both testnet and mainnet and save them to a file.
        """
        self.wallet_file = wallet_file
        print("Generating new keys for both testnet and mainnet...")

        # ✅ Ensure the directory exists
        wallet_dir = os.path.dirname(self.wallet_file)
        if wallet_dir and not os.path.exists(wallet_dir):
            os.makedirs(wallet_dir, exist_ok=True)

        # Generate keys for testnet
        self.testnet_secret_key = SecretKey(512)
        self.testnet_public_key = PublicKey(self.testnet_secret_key)

        # Generate keys for mainnet
        self.mainnet_secret_key = SecretKey(512)
        self.mainnet_public_key = PublicKey(self.mainnet_secret_key)

        # Display hashed public keys with prefixes
        print(f"Testnet Hashed Public Key: {self.public_key('testnet')}")
        print(f"Mainnet Hashed Public Key: {self.public_key('mainnet')}")

        # Save keys to file
        self.save_keys()
        print("Keys for both networks generated and saved successfully.")

    def public_key(self, network: str) -> str:
        """
        Retrieve the public key for a specified network and return it in a serialized and hashed format.

        Args:
            network (str): Either "testnet" or "mainnet".

        Returns:
            str: The hashed public key with the network prefix.
        """
        if network == "testnet":
            public_key = self.testnet_public_key
            prefix = "ZYT"
        elif network == "mainnet":
            public_key = self.mainnet_public_key
            prefix = "ZYC"
        else:
            raise ValueError("Invalid network. Choose 'testnet' or 'mainnet'.")

        # Serialize and hash the public key
        serialized_key = json.dumps({"h": public_key.h}, default=serialize_complex).encode("utf-8")
        hashed_key = hashlib.sha3_384(serialized_key).hexdigest()

        # Add network-specific prefix
        return f"{prefix}{hashed_key}"

    def save_keys(self):
        """
        Save the testnet and mainnet keys to a JSON file, including the hashed public key with prefixes.
        """
        keys_to_save = [
            {
                "network": "testnet",
                "private_key": base64.b64encode(
                    json.dumps(self.testnet_secret_key.__dict__, default=serialize_complex).encode("utf-8")
                ).decode("utf-8"),
                "public_key": base64.b64encode(
                    json.dumps({"h": self.testnet_public_key.h}, default=serialize_complex).encode("utf-8")
                ).decode("utf-8"),
                "hashed_public_key": self.public_key("testnet"),
            },
            {
                "network": "mainnet",
                "private_key": base64.b64encode(
                    json.dumps(self.mainnet_secret_key.__dict__, default=serialize_complex).encode("utf-8")
                ).decode("utf-8"),
                "public_key": base64.b64encode(
                    json.dumps({"h": self.mainnet_public_key.h}, default=serialize_complex).encode("utf-8")
                ).decode("utf-8"),
                "hashed_public_key": self.public_key("mainnet"),
            },
        ]

        # Ensure the file exists and initialize it with an empty list if necessary
        if not os.path.exists(self.wallet_file):
            with open(self.wallet_file, "w") as file:
                json.dump([], file)

        # Append the new keys to the existing file
        with open(self.wallet_file, "r+") as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                data = []  # If the file is empty or corrupted, initialize with an empty list

            data.extend(keys_to_save)  # Add the new keys for testnet and mainnet
            file.seek(0)
            json.dump(data, file, indent=4)

    def sign_transaction(self, message: bytes, network: str) -> bytes:
        """
        Sign a transaction using the wallet's private key for the specified network.

        Args:
            message (bytes): The message to sign.
            network (str): Either "testnet" or "mainnet".

        Returns:
            bytes: The generated signature.
        """
        if network not in ["testnet", "mainnet"]:
            raise ValueError(f"Invalid network: {network}. Must be 'testnet' or 'mainnet'.")

        print(f"Signing transaction for {network}...")
        secret_key = (
            self.testnet_secret_key if network == "testnet" else self.mainnet_secret_key
        )
        signature = secret_key.sign(message)
        print("Transaction signed successfully.")
        return signature

    def verify_transaction(self, message: bytes, signature: bytes, network: str) -> bool:
        """
        Verify a transaction signature using the public key for the specified network.

        Args:
            message (bytes): The message to verify.
            signature (bytes): The signature to verify.
            network (str): The network ("testnet" or "mainnet").

        Returns:
            bool: True if the signature is valid, False otherwise.
        """
        if network not in ["testnet", "mainnet"]:
            raise ValueError(f"Invalid network: {network}. Must be 'testnet' or 'mainnet'.")

        print(f"Verifying transaction for {network}...")
        public_key = (
            self.testnet_public_key if network == "testnet" else self.mainnet_public_key
        )
        is_valid = public_key.verify(message, signature)
        if is_valid:
            print("Transaction verified successfully.")
        else:
            print("Transaction verification failed.")
        return is_valid

if __name__ == "__main__":
    try:
        # Create a new wallet (generates keys for both networks)
        wallet = Wallet()

        # Example transaction message
        transaction_message = b"Transaction: Send 10 KC to Address XYZ."

        # Testnet transaction
        print("\n--- Testnet Transaction ---")
        testnet_signature = wallet.sign_transaction(transaction_message, "testnet")
        print(f"Testnet Signature: {testnet_signature}")
        wallet.verify_transaction(transaction_message, testnet_signature, "testnet")

        # Mainnet transaction
        print("\n--- Mainnet Transaction ---")
        mainnet_signature = wallet.sign_transaction(transaction_message, "mainnet")
        print(f"Mainnet Signature: {mainnet_signature}")
        wallet.verify_transaction(transaction_message, mainnet_signature, "mainnet")

    except Exception as e:
        print(f"An error occurred: {e}")
