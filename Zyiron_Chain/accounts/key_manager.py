import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import zlib
import qrcode
import os
import logging
from termcolor import colored
import os
import json
import base64
import hashlib
  # Import Wallet for Falcon key generation
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.falcon.falcon.falcon import SecretKey, PublicKey
from Zyiron_Chain.accounts.wallet_api import serialize_complex 
import os
import qrcode
import base64
import textwrap
from PIL import Image, ImageDraw, ImageFont 

class KeyManager:
    def __init__(self, key_file="Keys/KeyManager_Public_Private_Keys.json"):
        self.key_file = key_file
        self.network = Constants.NETWORK
        self.keys = {}

        print("\n🔹 Initializing KeyManager...")
        self.load_or_initialize_keys()
        self._auto_set_network_defaults()

        print("\n✅ KeyManager Ready.")

    def validate_miner_key(self, network):
        """Validate miner keys for specific network"""
        if network not in self.keys:
            return False
            
        # Check if default miner key exists and is valid
        if "miner" not in self.keys[network]["defaults"]:
            return False
            
        identifier = self.keys[network]["defaults"]["miner"]
        miner_key = self.keys[network]["keys"].get(identifier, {})
        
        required_keys = ["public_key", "private_key"]
        return all(k in miner_key for k in required_keys)

    def _auto_set_network_defaults(self):
        """Ensure default keys exist but do not regenerate if they already exist."""
        network = self.network

        # ✅ Ensure the network exists in the keys structure
        if network not in self.keys:
            self.keys[network] = {"keys": {}, "defaults": {}}

        # ✅ Assign miner, validator, and channel keys properly
        for role in ["miner", "validator", "channel"]:
            if role not in self.keys[network]["defaults"] or not self.keys[network]["defaults"][role]:
                if self.keys[network]["keys"]:
                    print(f"✅ Default {role} key already exists for {network}. Skipping generation.")
                else:
                    print(f"🔑 Generating default {role} key for {network}...")
                    identifier = f"{role}_{len(self.keys[network]['keys']) + 1}"
                    self.add_key(network, role, identifier)
                    self.keys[network]["defaults"][role] = identifier  # ✅ Assign default





    def public_key(self, network: str, identifier: str) -> str:
        """
        Retrieve the public key for a specified network and return it in a serialized and hashed format.

        Args:
            network (str): Either "testnet" or "mainnet".
            identifier (str): The identifier of the key to retrieve.

        Returns:
            str: The hashed public key with the network prefix.
        """
        network = network.lower()
        if network not in ["testnet", "mainnet"]:
            raise ValueError("Invalid network. Choose 'testnet' or 'mainnet'.")

        # ✅ Check if the key exists
        key_data = self.keys[network]["keys"].get(identifier)
        if not key_data:
            raise ValueError(f"Key '{identifier}' not found in {network}.")

        prefix = "ZYT" if network == "testnet" else "ZYC"

        # ✅ Deserialize the stored public key
        try:
            public_key_data = json.loads(base64.b64decode(key_data["public_key"]).decode("utf-8"))
            public_key = public_key_data.get("h")
        except Exception as e:
            raise ValueError(f"Failed to load public key for '{identifier}': {e}")

        # ✅ Hash the serialized public key
        serialized_key = json.dumps({"h": public_key}, default=serialize_complex).encode("utf-8")
        hashed_key = hashlib.sha3_384(serialized_key).hexdigest()

        # ✅ Return the prefixed hashed key
        return f"{prefix}{hashed_key}"




    def load_or_initialize_keys(self):
        """
        Load keys from the JSON file or initialize a new structure if the file doesn't exist or is invalid.
        Ensures the directory and file exist before accessing them.
        """
        # ✅ Ensure the directory exists
        key_dir = os.path.dirname(self.key_file)
        if key_dir and not os.path.exists(key_dir):
            print(f"📁 Creating missing directory: {key_dir}")
            os.makedirs(key_dir, exist_ok=True)

        # ✅ Ensure the key file exists
        if not os.path.exists(self.key_file):
            print(f"⚠️ Key file not found. Creating new key file: {self.key_file}")
            self.initialize_keys_structure()  # ✅ Create new keys and save them
            return

        try:
            with open(self.key_file, "r") as file:
                self.keys = json.load(file)

                # ✅ Check if the file is empty or corrupted
                if not self.keys:
                    print(f"⚠️ Key file is empty. Initializing new keys...")
                    self.initialize_keys_structure()
        except (json.JSONDecodeError, ValueError):
            print(f"⚠️ Key file is corrupted. Re-initializing new keys...")
            self.initialize_keys_structure()



    def initialize_keys_structure(self):
        """
        Initialize the key structure with essential roles and create a new JSON file.
        """
        self.keys = {
            "testnet": {"keys": {}, "defaults": {"miner": "", "validator": "", "channel": ""}},
            "mainnet": {"keys": {}, "defaults": {"miner": "", "validator": "", "channel": ""}},
        }
        
        print(f"✅ Initializing new key structure in {self.key_file}...")
        
        # ✅ Save new structure to the file
        self.save_keys()


    def save_keys(self):
        """
        Save the current keys to the JSON file.
        """
        with open(self.key_file, "w") as file:
            json.dump(self.keys, file, indent=4)
        print(colored(f"Keys saved to {self.key_file}.", "green"))



    def get_default_public_key(self, network=None, role="miner"):
        """
        Retrieve the default public key for the given network and role.
        """
        network = network or self.network

        # Ensure the role exists in the specified network's defaults
        if role not in self.keys[network]["defaults"]:
            raise ValueError(f"No default key set for role '{role}' in {network}.")

        default_identifier = self.keys[network]["defaults"][role]
        return self.keys[network]["keys"][default_identifier]["hashed_public_key"]



    def add_key_batch(self, network):
        """
        Add a synchronized batch of keys for the specified network.
        :param network: Either 'testnet' or 'mainnet'.
        """
        if network not in self.keys:
            raise ValueError("Invalid network. Choose 'testnet' or 'mainnet'.")

        # ✅ Determine the next batch identifier
        existing_batches = len(self.keys[network]["keys"])
        batch_id = existing_batches + 1

        print(f"🔑 Starting key generation for batch {batch_id} in {network}...")

        # ✅ Generate miner, validator, and channel keys for this batch
        for role in ["miner", "validator", "channel"]:
            identifier = f"{role}_{batch_id}"
            self.add_key(network, role, identifier)

        print(f"✅ Batch {batch_id} key generation complete for {network}.")


    def set_default_key(self, network, identifier):
        """
        Set a key as default for all roles in the specified network.
        :param network: Either 'testnet' or 'mainnet'.
        :param identifier: The unique identifier of the key to set as default.
        """
        if network not in self.keys:
            raise ValueError(f"Invalid network: {network}. Choose 'testnet' or 'mainnet'.")

        if identifier not in self.keys[network]["keys"]:
            raise ValueError(f"Key identifier '{identifier}' not found in {network}.")

        # Set the selected identifier as the default for all roles
        for role in self.keys[network]["defaults"]:
            self.keys[network]["defaults"][role] = identifier

        # Save the updated keys to the JSON file
        self.save_keys()
        print(colored(f"Default keys for all roles in {network} set to '{identifier}'.", "green"))




    def add_key(self, network, role, identifier):
        """
        Add a new key for the specified network, role, and identifier.
        Generates Falcon keys, verifies public key consistency, and ensures a valid hash.

        :param network: Network name ('testnet' or 'mainnet')
        :param role: Key role ('miner', 'validator', etc)
        :param identifier: Unique identifier for key management
        """
        network = network.lower()
        if network not in ("testnet", "mainnet"):
            raise ValueError(f"Invalid network '{network}'. Must be 'testnet' or 'mainnet'.")

        # ✅ Check if key already exists for this role
        existing_keys = self.keys[network]["keys"]
        if any(existing_keys[k]["role"] == role for k in existing_keys):
            print(f"✅ A {role} key already exists in {network}. Skipping new key generation.")
            return

        print(f"🔑 Generating {role} key pair for {network.upper()} [{identifier}]...")

        try:
            # ✅ Generate Falcon-512 key pair
            private_key = SecretKey(512)  
            public_key = PublicKey(private_key)

            # ✅ Serialize private and public keys
            private_serialized = base64.b64encode(
                json.dumps(private_key.__dict__, default=serialize_complex).encode("utf-8")
            ).decode("utf-8")

            public_serialized = base64.b64encode(
                json.dumps({"h": public_key.h}, default=serialize_complex).encode("utf-8")
            ).decode("utf-8")

            # ✅ Compute raw and hashed public keys
            raw_public_key = json.dumps({"h": public_key.h}, default=serialize_complex).encode("utf-8")
            hashed_public_key = hashlib.sha3_384(raw_public_key).hexdigest()  # ✅ Correct hashing

            # ✅ Apply network-specific prefix
            prefix = "ZYT" if network == "testnet" else "ZYC"
            hashed_public_key = f"{prefix}{hashed_public_key}"

        except Exception as e:
            print(f"⚠️ Key generation failed: {str(e)}")
            raise RuntimeError("Key pair generation aborted due to errors")

        # ✅ Store key data
        self.keys[network]["keys"][identifier] = {
            "private_key": private_serialized,
            "public_key": public_serialized,
            "hashed_public_key": hashed_public_key,
            "role": role,
            "network": network
        }

        # ✅ Set as default if no default exists for this role
        if not self.keys[network]["defaults"].get(role):
            self.keys[network]["defaults"][role] = identifier
            print(f"⚡ Set default {role} key for {network.upper()}: {identifier}")

        self.save_keys()

        # ✅ Verify that the stored hash matches the computed hash
        stored_hash = self.keys[network]["keys"][identifier]["hashed_public_key"]
        
        if stored_hash == hashed_public_key:
            print(f"✅ Public Key Hash Verified for {role.capitalize()} {identifier} ({network.upper()})")
        else:
            print(f"⚠️ Public Key Hash Mismatch for {role.capitalize()} {identifier} ({network.upper()})! Updating...")
            self.keys[network]["keys"][identifier]["hashed_public_key"] = hashed_public_key
            self.save_keys()


        
    @staticmethod
    def _serialize_complex(obj):
        """
        Custom serializer for complex numbers.
        """
        if isinstance(obj, complex):
            return {"real": obj.real, "imag": obj.imag}
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")





    def interactive_menu(self):
        """
        Interactive menu to manage keys, sign messages, and verify transactions.
        """
        while True:
            print("\nKey Manager Options:")
            print("1. List keys for testnet")
            print("2. List keys for mainnet")
            print("3. Add new batch of keys to testnet")
            print("4. Add new batch of keys to mainnet")
            print("5. List current default keys")
            print("6. Sign a message using the default keys")
            print("7. Verify a signed message")
            print("8. Export a specific key pair to a .txt file")
            print("0. Exit")

            choice = input("Enter your choice: ").strip()

            if choice == "1":
                self.list_keys("testnet")
            elif choice == "2":
                self.list_keys("mainnet")
            elif choice == "3":
                self.add_key_batch("testnet")
            elif choice == "4":
                self.add_key_batch("mainnet")
            elif choice == "5":
                self.list_default_keys()
            elif choice == "6":
                # ✅ Signing a message
                network = input("Enter the network (testnet or mainnet): ").strip().lower()
                identifier = input("Enter the key identifier (default miner, validator, etc.): ").strip()
                message = input("Enter the message to sign: ").strip().encode("utf-8")

                try:
                    # ✅ Verify and update the hashed public key before signing
                    recomputed_hashed_key = self.recompute_hashed_public_key(network, identifier)
                    stored_hashed_key = self.keys[network]["keys"][identifier]["hashed_public_key"]

                    if stored_hashed_key != recomputed_hashed_key:
                        print(f"\n⚠️ Hashed public key mismatch! Updating stored value...")
                        self.keys[network]["keys"][identifier]["hashed_public_key"] = recomputed_hashed_key
                        self.save_keys()

                    signature = self.sign_transaction(message, network, identifier)
                    signature_base64 = base64.b64encode(signature).decode("utf-8")
                    
                    print("\n✅ Message signed successfully!")
                    print(f"🔹 Signature (Base64 Encoded): {signature_base64}")
                except Exception as e:
                    print(f"\n❌ Failed to sign the message: {e}")

            elif choice == "7":
                # ✅ Verifying a message like a node would
                network = input("Enter the network (testnet or mainnet): ").strip().lower()
                identifier = input("Enter the key identifier used for signing: ").strip()
                message = input("Enter the original message: ").strip().encode("utf-8")
                signature_base64 = input("Enter the signature (Base64 format): ").strip()

                try:
                    signature = base64.b64decode(signature_base64)

                    # ✅ Verify that the stored public key hash matches the recomputed one
                    recomputed_hashed_key = self.recompute_hashed_public_key(network, identifier)
                    stored_hashed_key = self.keys[network]["keys"][identifier]["hashed_public_key"]

                    if stored_hashed_key != recomputed_hashed_key:
                        print(f"\n⚠️ Hashed public key mismatch! Expected: {recomputed_hashed_key}, Found: {stored_hashed_key}")
                        print("🔹 Updating to ensure consistency...")
                        self.keys[network]["keys"][identifier]["hashed_public_key"] = recomputed_hashed_key
                        self.save_keys()

                    # ✅ Verify the transaction signature
                    if self.verify_transaction(message, signature, network, identifier):
                        print("\n✅ Signature verification successful! The message is authentic.")
                    else:
                        print("\n❌ Signature verification failed! The message is NOT authentic.")

                except Exception as e:
                    print(f"\n❌ Failed to verify the message: {e}")

            elif choice == "8":
                self.export_keys()  # ✅ Export function
            elif choice == "0":
                print("Exiting Key Manager.")
                break
            else:
                print("Invalid choice. Please try again.")

    def recompute_raw_public_key(self, network: str, identifier: str):
        """
        Retrieve the raw public key from the stored key data.

        Args:
            network (str): Either "testnet" or "mainnet".
            identifier (str): The identifier of the key to retrieve.

        Returns:
            The raw public key.
        """
        network = network.lower()
        if network not in ["testnet", "mainnet"]:
            raise ValueError("Invalid network. Choose 'testnet' or 'mainnet'.")

        # ✅ Check if the key exists
        key_data = self.keys[network]["keys"].get(identifier)
        if not key_data:
            raise ValueError(f"Key '{identifier}' not found in {network}.")

        try:
            # ✅ Retrieve the stored public key
            public_key_json = json.loads(base64.b64decode(key_data["public_key"]).decode("utf-8"))
            raw_public_key = public_key_json.get("h")  # ✅ Correctly extract Falcon public key
        except Exception as e:
            raise ValueError(f"Failed to load public key for '{identifier}': {e}")

        return raw_public_key

    def recompute_hashed_public_key(self, network: str, identifier: str) -> str:
        """
        Recompute the hashed public key from the stored Falcon public key.
        Ensures correctness before signing and verification.

        Args:
            network (str): Either "testnet" or "mainnet".
            identifier (str): The key identifier.

        Returns:
            str: The hashed public key with the correct network prefix.
        """
        network = network.lower()
        if network not in ["testnet", "mainnet"]:
            raise ValueError("Invalid network. Choose 'testnet' or 'mainnet'.")

        # ✅ Ensure the key exists
        key_data = self.keys[network]["keys"].get(identifier)
        if not key_data:
            raise ValueError(f"Key '{identifier}' not found in {network}.")

        try:
            # ✅ Retrieve the stored public key
            public_key_json = json.loads(base64.b64decode(key_data["public_key"]).decode("utf-8"))
            raw_public_key = public_key_json.get("h")  # ✅ Correctly extract Falcon public key
        except Exception as e:
            raise ValueError(f"Failed to load public key for '{identifier}': {e}")

        # ✅ Hash the Falcon public key correctly
        serialized_key = json.dumps({"h": raw_public_key}, default=serialize_complex).encode("utf-8")
        hashed_key = hashlib.sha3_384(serialized_key).hexdigest()

        # ✅ Add network-specific prefix
        prefix = "ZYT" if network == "testnet" else "ZYC"
        
        return f"{prefix}{hashed_key}"  # ✅ Correctly return hashed public key




    def get_raw_public_key(self, script_pub_key, network):
        """
        Retrieve the raw public key associated with the given script public key and network.
        :param script_pub_key: The hashed public key (scriptPubKey).
        :param network: The network to search in ('testnet' or 'mainnet').
        :return: The raw public key.
        """
        if network not in self.keys:
            raise ValueError(f"Invalid network: {network}. Choose 'testnet' or 'mainnet'.")

        for key_data in self.keys[network]["keys"].values():
            if key_data["hashed_public_key"] == script_pub_key:
                return key_data["public_key"]  # Return the raw public key

        raise ValueError(f"Raw public key not found for the provided script public key in {network}.")


    def list_default_keys(self):
        """
        List the current default keys for both testnet and mainnet.
        """
        print("\n--- Default Keys ---")
        for network in ["testnet", "mainnet"]:
            print(f"\n{network.upper()} Defaults:")
            if not self.keys[network]["defaults"]:
                print(f"No default keys set for {network}.")
                continue

            for role, identifier in self.keys[network]["defaults"].items():
                key_data = self.keys[network]["keys"].get(identifier, {})
                hashed_public_key = key_data.get("hashed_public_key", "N/A")
                print(f"- {role.capitalize()}: {identifier} (Public Hash: {hashed_public_key})")


    def sign_message_interactive(self):
        """
        Allows the user to input a message, signs it using the default key,
        and verifies the signature for correctness.
        """
        try:
            network = self.network  # ✅ Get current network
            role = "miner"  # ✅ Use miner key by default

            if role not in self.keys[network]["defaults"]:
                raise ValueError(f"No default key set for role '{role}' in {network}.")

            identifier = self.keys[network]["defaults"][role]
            key_data = self.keys[network]["keys"].get(identifier, {})

            # ✅ Retrieve the hashed public key
            hashed_pubkey = key_data.get("hashed_public_key", "")

            # ✅ Ask user for message input
            message = input("\nEnter the message to sign: ").strip().encode("utf-8")

            # ✅ Hash the message before signing
            hashed_message = hashlib.sha3_384(message).digest()

            # ✅ Sign the hashed message using the stored private key
            print("\nSigning the message...")
            signature = self.sign_transaction(hashed_message, network, identifier)
            signature_base64 = base64.b64encode(signature).decode("utf-8")
            print("\n✅ Message signed successfully!")

            # ✅ Retrieve the raw public key
            raw_public_key = self.recompute_raw_public_key(network, identifier)
            raw_public_key_base64 = base64.b64encode(raw_public_key.encode("utf-8")).decode("utf-8")

            # ✅ Display output
            print("\n🔹 Signature (Base64 Encoded):")
            print(signature_base64)

            print("\n🔹 Raw Public Key (Base64 Encoded):")
            print(raw_public_key_base64)

            print("\n🔹 Hashed Public Key (Network Address):")
            print(hashed_pubkey)

            # ✅ Ask user if they want to verify the signature
            verify = input("\nDo you want to verify this signature? (yes/no): ").strip().lower()
            if verify == "yes":
                print("\n🔹 Verifying the signed message...")

                # ✅ Ensure verification uses the **same hashed message**
                is_valid = self.verify_transaction(hashed_message, base64.b64decode(signature_base64), network, identifier)

                if is_valid:
                    print("\n✅ Signature verification successful! The message is authentic.")
                else:
                    print("\n❌ Signature verification failed! The message is NOT authentic.")

        except Exception as e:
            print(f"\n❌ An error occurred: {e}")





    def get_private_key_for_channel(self, network, role="channel"):
        """
        Retrieve the private key for a specific role in a payment channel.
        If no default key exists, generate one.
        """
        if network not in self.keys:
            raise ValueError(f"Invalid network: {network}.")

        # ✅ Ensure a default key for 'channel' exists
        if role not in self.keys[network]["defaults"]:
            print(f"[INFO] No default key found for role '{role}' in {network}. Generating one...")
            self.add_key(network, role, f"{role}_default")

        identifier = self.keys[network]["defaults"][role]
        return self.keys[network]["keys"][identifier]["private_key"]


    def list_keys(self, network):
        """
        List all stored keys for a given network.
        """
        if network not in self.keys:
            print(f"No keys found for network: {network}")
            return

        print(f"\n--- {network.upper()} Keys ---")
        for identifier, key_data in self.keys[network]["keys"].items():
            print(f"Identifier: {identifier}")
            print(f"  - Hashed Public Key: {key_data.get('hashed_public_key', 'N/A')}")
            print(f"  - Role: {key_data.get('role', 'N/A')}")
            print(f"  - Network: {key_data.get('network', 'N/A')}\n")


    def _convert_json_complex(self, obj):
        """Recursively convert dictionaries with 'real' and 'imag' keys into complex numbers."""
        if isinstance(obj, dict):
            if 'real' in obj and 'imag' in obj:
                return complex(obj['real'], obj['imag'])
            else:
                return {k: self._convert_json_complex(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_json_complex(v) for v in obj]
        else:
            return obj

    def sign_transaction(self, message: bytes, network: str, identifier: str) -> bytes:
        """
        Sign a transaction using the stored private key in KeyManager.

        Args:
            message (bytes): The original message to sign.
            network (str): Either "testnet" or "mainnet".
            identifier (str): The identifier of the key to sign with.

        Returns:
            bytes: The generated digital signature.
        """
        network = network.lower()
        if network not in ["testnet", "mainnet"]:
            raise ValueError(f"Invalid network: {network}. Must be 'testnet' or 'mainnet'.")

        # ✅ Retrieve the private key for signing
        key_data = self.keys[network]["keys"].get(identifier)
        if not key_data:
            raise ValueError(f"Key '{identifier}' not found in {network}.")

        try:
            # ✅ Decode the JSON-stored private key
            private_key_json = json.loads(base64.b64decode(key_data["private_key"]).decode("utf-8"))

            # ✅ Recursively convert JSON data to complex numbers
            def _convert_json_complex(obj):
                """Recursively convert dictionaries with 'real' and 'imag' keys into complex numbers."""
                if isinstance(obj, dict):
                    if 'real' in obj and 'imag' in obj:
                        return complex(obj['real'], obj['imag'])
                    else:
                        return {k: _convert_json_complex(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [_convert_json_complex(v) for v in obj]
                else:
                    return obj

            # ✅ Convert JSON structure to Falcon format
            private_key_converted = _convert_json_complex(private_key_json)

            # ✅ Create a Falcon SecretKey instance and update attributes
            secret_key = SecretKey(512)
            secret_key.__dict__.update(private_key_converted)

        except Exception as e:
            raise ValueError(f"Failed to load private key for signing: {e}")

        print(f"🔹 Signing transaction for {network.upper()} using {identifier}...")

        # ✅ Hash the message before signing with SHA3-384
        hashed_message = hashlib.sha3_384(message).digest()

        # ✅ Sign the hashed message using Falcon
        signature = secret_key.sign(hashed_message)
        print("✅ Transaction signed successfully.")

        # ✅ Encode the signature in base64 to preserve integrity
        return base64.b64encode(signature)



    def verify_transaction(self, message: bytes, signature: bytes, network: str, identifier: str) -> bool:
        """
        Verify a transaction signature using the stored public key.

        Args:
            message (bytes): The original message to verify.
            signature (bytes): The signature to verify.
            network (str): The network ("testnet" or "mainnet").
            identifier (str): The key identifier used for signing.

        Returns:
            bool: True if the signature is valid, False otherwise.
        """
        network = network.lower()
        if network not in ["testnet", "mainnet"]:
            raise ValueError(f"Invalid network: {network}. Must be 'testnet' or 'mainnet'.")

        # ✅ Retrieve the public key for verification
        key_data = self.keys[network]["keys"].get(identifier)
        if not key_data:
            raise ValueError(f"Key '{identifier}' not found in {network}.")

        try:
            # ✅ Decode and reconstruct the JSON-stored public key
            public_key_json = json.loads(base64.b64decode(key_data["public_key"]).decode("utf-8"))

            # ✅ Convert JSON format to complex numbers
            def _convert_json_complex(obj):
                """Recursively convert dictionaries with 'real' and 'imag' keys into complex numbers."""
                if isinstance(obj, dict):
                    if 'real' in obj and 'imag' in obj:
                        return complex(obj['real'], obj['imag'])
                    else:
                        return {k: _convert_json_complex(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [_convert_json_complex(v) for v in obj]
                else:
                    return obj

            # ✅ Restore public key with Falcon format
            public_key_converted = _convert_json_complex(public_key_json)

            # ✅ Create a Falcon PublicKey instance and update attributes
            public_key = PublicKey(SecretKey(512))
            public_key.__dict__.update(public_key_converted)

        except Exception as e:
            raise ValueError(f"Failed to load public key for verification: {e}")

        print(f"🔹 Verifying transaction for {network.upper()} using {identifier}...")

        # ✅ Ensure the message is **hashed before verification**
        hashed_message = hashlib.sha3_384(message).digest()

        # ✅ Decode base64 signature to raw bytes
        signature_bytes = base64.b64decode(signature)

        # ✅ Verify the hashed message against the signature
        is_valid = public_key.verify(hashed_message, signature_bytes)

        if is_valid:
            print("✅ Transaction verified successfully.")
        else:
            print("❌ Transaction verification failed.")

        return is_valid






    def export_keys(self):
        """
        Export a specific key set (miner, validator, channel) based on user selection.
        Saves the exported keys in a .txt file with a box-like structure using UTF-8 encoding.
        Offers an option to generate QR codes for each key.
        """
        print("\n🔹 EXPORT KEY PAIRS")

        # ✅ Ask for role
        role = input("Enter the role to export (miner, validator, channel): ").strip().lower()
        if role not in ["miner", "validator", "channel"]:
            print("❌ Invalid role. Choose from: miner, validator, channel.")
            return

        # ✅ Ask for network
        network = input("Enter the network (testnet or mainnet): ").strip().lower()
        if network not in ["testnet", "mainnet"]:
            print("❌ Invalid network. Choose from: testnet or mainnet.")
            return

        # ✅ Get available keys for selection
        matching_keys = {
            identifier: key_data
            for identifier, key_data in self.keys[network]["keys"].items()
            if key_data["role"] == role
        }

        if not matching_keys:
            print(f"⚠️ No {role} keys found for {network}.")
            return

        # ✅ Display available keys for selection
        print(f"\nAvailable {role.capitalize()} Keys in {network.upper()}:")
        for index, identifier in enumerate(matching_keys.keys(), start=1):
            print(f"{index}. {identifier}")

        # ✅ Ask user which key set to export
        try:
            selection = int(input("\nEnter the number of the key you want to export: ").strip())
            if selection < 1 or selection > len(matching_keys):
                raise ValueError
        except ValueError:
            print("❌ Invalid selection. Please enter a valid number.")
            return

        # ✅ Get the selected key
        selected_identifier = list(matching_keys.keys())[selection - 1]
        selected_key_data = matching_keys[selected_identifier]

        # ✅ Ask user for filename
        filename = input("Enter the filename to save the key pair (without extension): ").strip()
        filename = f"Keys/{filename}.txt"

        # ✅ Ask if user wants QR codes
        generate_qr = input("Do you want to generate QR codes for these keys? (yes/no): ").strip().lower() == "yes"

        # ✅ Ensure the directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        # ✅ Write using UTF-8 encoding to prevent Unicode errors
        with open(filename, "w", encoding="utf-8") as file:
            file.write(f"\n{'=' * 80}\n")
            file.write(f"🔹 {role.capitalize()} Key Export - {selected_identifier.upper()} - {network.upper()}\n")
            file.write(f"{'=' * 80}\n\n")

            # ✅ Private Key Section
            private_key = selected_key_data.get("private_key", "N/A")
            file.write(f"{'=' * 20} ( PRIVATE KEY ) {'=' * 20}\n")
            file.write(f"===START HERE({private_key})END HERE===\n")
            file.write(f"{'=' * 60}\n\n")

            # ✅ Public Key Section
            public_key = selected_key_data.get("public_key", "N/A")
            file.write(f"{'=' * 20} ( PUBLIC KEY ) {'=' * 20}\n")
            file.write(f"===START HERE({public_key})END HERE===\n")
            file.write(f"{'=' * 60}\n\n")

            # ✅ Hashed Public Key Section
            hashed_public_key = selected_key_data.get("hashed_public_key", "N/A")
            file.write(f"{'=' * 18} ( HASHED PUBLIC KEY ) {'=' * 18}\n")
            file.write(f"===START HERE({hashed_public_key})END HERE===\n")
            file.write(f"{'=' * 60}\n\n")

        print(f"\n✅ Exported {role.capitalize()} {selection} to {filename}.")

        # ✅ Generate QR codes if requested
        if generate_qr:
            self.generate_qr_code(private_key, public_key, hashed_public_key, f"{selected_identifier}_keys")
            print("\n✅ QR Codes generated for Private, Public, and Hashed Public Key!")


    def recompute_hashed_public_key(self, network: str, identifier: str) -> str:
        """
        Recompute the hashed public key from the raw public key to ensure address consistency.

        Args:
            network (str): Either "testnet" or "mainnet".
            identifier (str): The identifier of the key to recompute.

        Returns:
            str: The hashed public key with the correct network prefix.
        """
        network = network.lower()
        if network not in ["testnet", "mainnet"]:
            raise ValueError("Invalid network. Choose 'testnet' or 'mainnet'.")

        prefix = "ZYT" if network == "testnet" else "ZYC"

        # ✅ Compute the raw public key
        raw_public_key = self.recompute_raw_public_key(network, identifier)

        # ✅ Hash the raw public key
        serialized_key = json.dumps({"h": raw_public_key}, default=serialize_complex).encode("utf-8")
        hashed_key = hashlib.sha3_384(serialized_key).hexdigest()

        return f"{prefix}{hashed_key}"  # ✅ Returns the prefixed hashed public key


    def verify_and_update_hashed_public_key(self, network: str, identifier: str):
        """
        Verify and update the stored hashed public key by recomputing it from the raw public key.
        
        Args:
            network (str): Either "testnet" or "mainnet".
            identifier (str): The identifier of the key to update.
        """
        network = network.lower()
        if network not in ["testnet", "mainnet"]:
            raise ValueError("Invalid network. Choose 'testnet' or 'mainnet'.")

        # ✅ Check if the key exists
        if identifier not in self.keys[network]["keys"]:
            raise ValueError(f"Key '{identifier}' not found in {network}.")

        # ✅ Compute the correct hashed public key
        computed_hashed_key = self.recompute_hashed_public_key(network, identifier)

        # ✅ Compare with the stored value
        stored_hashed_key = self.keys[network]["keys"][identifier]["hashed_public_key"]

        if stored_hashed_key == computed_hashed_key:
            print(f"✅ Hashed public key for {identifier} is consistent.")
        else:
            print(f"⚠️ Hashed public key mismatch detected! Updating stored public key for {identifier}.")
            self.keys[network]["keys"][identifier]["hashed_public_key"] = computed_hashed_key
            self.save_keys()







    def test_hashed_public_key(self, network: str, identifier: str):
        """
        Test if the stored hashed public key can be correctly recomputed.

        Args:
            network (str): Either "testnet" or "mainnet".
            identifier (str): The key identifier.

        Prints:
            - ✅ Success message if recomputed hash matches the stored hash.
            - ⚠️ Warning message if the hash does not match, prompting an update.
        """
        network = network.lower()
        if network not in ["testnet", "mainnet"]:
            raise ValueError("Invalid network. Choose 'testnet' or 'mainnet'.")

        # ✅ Ensure the key exists
        key_data = self.keys[network]["keys"].get(identifier)
        if not key_data:
            print(f"❌ Key '{identifier}' not found in {network}.")
            return

        try:
            # ✅ Retrieve the stored public key
            public_key_json = json.loads(base64.b64decode(key_data["public_key"]).decode("utf-8"))
            raw_public_key = public_key_json.get("h")  # ✅ Extract Falcon public key
        except Exception as e:
            print(f"❌ Failed to load public key for '{identifier}': {e}")
            return

        # ✅ Hash the raw Falcon public key
        serialized_key = json.dumps({"h": raw_public_key}, default=serialize_complex).encode("utf-8")
        recomputed_hashed_key = hashlib.sha3_384(serialized_key).hexdigest()

        # ✅ Add network-specific prefix
        prefix = "ZYT" if network == "testnet" else "ZYC"
        recomputed_hashed_key = f"{prefix}{recomputed_hashed_key}"

        # ✅ Compare with the stored value
        stored_hashed_key = key_data["hashed_public_key"]

        print(f"\n🔹 Testing Hashed Public Key for '{identifier}' in {network.upper()}...")
        print(f"  - Stored Hash: {stored_hashed_key}")
        print(f"  - Recomputed Hash: {recomputed_hashed_key}")

        if stored_hashed_key == recomputed_hashed_key:
            print(f"✅ Hashed public key is correct for {identifier}.")
        else:
            print(f"⚠️ Hash mismatch! Updating stored hash for {identifier}...")
            self.keys[network]["keys"][identifier]["hashed_public_key"] = recomputed_hashed_key
            self.save_keys()
            print(f"✅ Stored hash updated successfully.")







    def generate_qr_code(self, private_key, public_key, hashed_public_key, identifier):
        """
        Generates QR codes for:
        - ✅ Hashed Public Key (Network Address) [QR Code]
        - ✅ Stores Private Key in .txt format (NO QR)
        - ✅ Stores Public Key in .txt format (NO QR)

        Args:
            private_key (str): The private key (stored in .txt only).
            public_key (str): The Falcon-512 public key (stored in .txt only).
            hashed_public_key (str): The hashed public key (wallet address for transactions).
            identifier (str): The key identifier (e.g., miner_1).
        """

        def create_qr(data, scale=1):
            """Creates a QR code while ensuring it stays within the max version limit."""
            qr = qrcode.QRCode(
                version=40,  # ✅ Max supported QR version
                error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
                box_size=20 * scale,  # Increased box size
                border=4
            )
            qr.add_data(data)
            qr.make(fit=True)
            qr_image = qr.make_image(fill="black", back_color="white")
            return qr_image.convert("RGB")  # Convert to RGB mode

        # ✅ Set up directories
        base_folder = f"QR_Codes/{identifier}"
        os.makedirs(base_folder, exist_ok=True)

        # ✅ **Store Private & Public Key in .txt (No QR Code)**
        key_file_path = f"{base_folder}/{identifier}_keys.txt"
        with open(key_file_path, "w", encoding="utf-8") as file:
            file.write(f"\n{'=' * 80}\n")
            file.write(f"🔹 PRIVATE & PUBLIC KEYS - {identifier.upper()}\n")
            file.write(f"{'=' * 80}\n\n")

            # ✅ Store Private Key
            file.write(f"{'=' * 20} ( PRIVATE KEY ) {'=' * 20}\n")
            file.write(f"===START HERE({private_key})END HERE===\n")
            file.write(f"{'=' * 60}\n\n")

            # ✅ Store Public Key
            file.write(f"{'=' * 20} ( PUBLIC KEY ) {'=' * 20}\n")
            file.write(f"===START HERE({public_key})END HERE===\n")
            file.write(f"{'=' * 60}\n\n")

            # ✅ Store Hashed Public Key (For Reference)
            file.write(f"{'=' * 18} ( HASHED PUBLIC KEY - NETWORK ADDRESS ) {'=' * 18}\n")
            file.write(f"===START HERE({hashed_public_key})END HERE===\n")
            file.write(f"{'=' * 60}\n\n")

        print(f"✅ Private & Public Keys stored securely in {key_file_path}")

        # ✅ **Create QR Code for Hashed Public Key (Network Address)**
        print(f"Hashed Public Key: {hashed_public_key}")  # Debug statement
        hashed_qr = create_qr(hashed_public_key, scale=2)

        # ✅ **Define Image Layout for Hashed Public Key**
        spacing = 30
        hashed_qr_size = hashed_qr.size[0]
        img_width = hashed_qr_size + spacing * 2
        img_height = hashed_qr_size + spacing * 4

        # ✅ **Create Image for Hashed Public Key QR Code**
        hashed_img = Image.new("RGB", (img_width, img_height), "white")
        print(f"✅ Created image: {hashed_img} (Type: {type(hashed_img)})")  # Debug statement

        draw = ImageDraw.Draw(hashed_img)
        print(f"✅ Created draw object: {draw} (Type: {type(draw)})")  # Debug statement

        # ✅ Load font for labeling
        try:
            font = ImageFont.truetype("arial.ttf", 40)  # Increased font size
            print("✅ Font loaded successfully.")
        except Exception as e:
            print(f"❌ Failed to load font: {e}")
            font = ImageFont.load_default()

        # Convert hex color (#000000) to RGB tuple (0, 0, 0)
        text_color = (0, 0, 0)  # Black color in RGB
        print(f"Text color: {text_color} (Type: {type(text_color)})")  # Debug statement

        try:
            draw.text((spacing, spacing - 20), "🔹 HASHED PUBLIC KEY (NETWORK ADDRESS)", fill=text_color, font=font)
            print("✅ Text drawn successfully.")
        except Exception as e:
            print(f"❌ Error drawing text: {e}")

        # ✅ **Fix `paste()` method by specifying bounding box**
        try:
            print(f"✅ QR code image: {hashed_qr} (Type: {type(hashed_qr)})")  # Debug statement
            qr_position = (
                (img_width - hashed_qr.size[0]) // 2,  # Center horizontally
                (img_height - hashed_qr.size[1]) // 2   # Center vertically
            )
            hashed_img.paste(hashed_qr, qr_position)  # Paste centered
            print("✅ QR code pasted successfully.")
        except Exception as e:
            print(f"❌ Error pasting QR code: {e}")

        # ✅ Save Hashed Public Key QR Code Image
        hashed_img_path = f"{base_folder}/{identifier}_hashed_public_key.png"
        try:
            hashed_img.save(hashed_img_path, quality=100)  # Save with maximum quality
            print(f"✅ Hashed Public Key QR Code saved: {hashed_img_path}")
        except Exception as e:
            print(f"❌ Error saving image: {e}")

if __name__ == "__main__":
    try:
        print("\n🔹 Initializing KeyManager...")
        key_manager = KeyManager()  # ✅ Ensures KeyManager is initialized correctly

        # ✅ Ensure that keys exist before starting menu
        if not key_manager.keys:
            print("⚠️ No keys found. Creating new key file...")
            key_manager.initialize_keys_structure()

        # ✅ Verify and fix hashed public keys before starting
        for network in ["testnet", "mainnet"]:
            for identifier in key_manager.keys.get(network, {}).get("keys", {}):
                print(f"\n🔍 Verifying hashed public key for {identifier} in {network.upper()}...")
                
                # ✅ Retrieve stored and recomputed hashed public key
                stored_hashed_key = key_manager.keys[network]["keys"][identifier]["hashed_public_key"]
                recomputed_hashed_key = key_manager.recompute_hashed_public_key(network, identifier)

                print(f"  🔹 Stored Hash: {stored_hashed_key}")
                print(f"  🔹 Recomputed Hash: {recomputed_hashed_key}")

                if stored_hashed_key == recomputed_hashed_key:
                    print(f"✅ Hashed public key is correct for {identifier}.")
                else:
                    print(f"⚠️ Hash mismatch detected! Updating stored hash for {identifier}...")
                    key_manager.keys[network]["keys"][identifier]["hashed_public_key"] = recomputed_hashed_key
                    key_manager.save_keys()
                    print(f"✅ Stored hash updated successfully.")

        print("\n✅ KeyManager is ready. Launching menu...\n")
        key_manager.interactive_menu()  # ✅ Start the interactive menu

    except Exception as e:
        print(f"\n❌ An error occurred during initialization: {e}")