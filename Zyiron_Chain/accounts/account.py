import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)


import secrets
from  Zyiron_Chain.falcon.falcon.falcon import SecretKey, PublicKey
from  Zyiron_Chain.falcon.falcon.common import q


class Account:
    """
    Represents a user account with Falcon-based public/private keys for signing and verification.
    """

    def __init__(self):
        self.secret_key = None
        self.public_key = None

    def generate_keys(self, n=512):
        """
        Generate a Falcon keypair.
        :param n: Security parameter, defaults to 1024.
        """
        print("Generating Falcon keys...")
        self.secret_key = SecretKey(n)
        self.public_key = PublicKey(self.secret_key)
        print("Keys generated successfully.")

    def sign_message(self, message):
        """
        Sign a message using the private key.
        :param message: The message to sign (string).
        :return: The generated signature (bytes).
        """
        if not self.secret_key:
            raise ValueError("No private key found. Please generate keys first.")

        print("Signing message...")
        signature = self.secret_key.sign(message.encode())
        print("Message signed successfully.")
        return signature

    def verify_message(self, message, signature):
        """
        Verify a signature using the public key.
        :param message: The original message (string).
        :param signature: The signature to verify (bytes).
        :return: True if the signature is valid, False otherwise.
        """
        if not self.public_key:
            raise ValueError("No public key found. Please generate keys first.")

        print("Verifying signature...")
        is_valid = self.public_key.verify(message.encode(), signature)
        if is_valid:
            print("Signature verified successfully.")
        else:
            print("Signature verification failed.")
        return is_valid


# Example usage
if __name__ == "__main__":
    try:
        # Create an account instance
        account = Account()

        # Generate Falcon keys
        account.generate_keys()  # Generates 1024-bit Falcon keys by default

        # Message to sign
        message = "This is a test message for Falcon signature."

        # Signing the message
        signature = account.sign_message(message)
        print("Generated Signature:", signature)

        # Verifying the signature
        is_valid = account.verify_message(message, signature)
        print("Is the signature valid?", is_valid)

    except Exception as e:
        print(f"An error occurred: {e}")
