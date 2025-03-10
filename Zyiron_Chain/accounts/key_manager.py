import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


import logging
from termcolor import colored
import os
import json
import base64
import hashlib
  # Import Wallet for Falcon key generation
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.falcon.falcon.falcon import SecretKey, PublicKey
from Zyiron_Chain.keys.wallet_api import serialize_complex 

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
        and displays the signature, public key, and hashed public key.
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

            # ✅ Sign the message using the stored private key
            print("\nSigning the message...")
            signature = self.sign_transaction(message, network, identifier)
            print("Message signed successfully.")

            # ✅ Retrieve the raw public key
            raw_public_key = self.recompute_raw_public_key(network, identifier)

            # ✅ Convert everything to Base64 for better display
            signature_base64 = base64.b64encode(signature).decode("utf-8")
            raw_public_key_base64 = base64.b64encode(raw_public_key.encode("utf-8")).decode("utf-8")

            # ✅ Display output
            print("\nSignature (Base64):")
            print(signature_base64)

            print("\nRaw Public Key (Base64):")
            print(raw_public_key_base64)

            print("\nHashed Public Key:")
            print(hashed_pubkey)

        except Exception as e:
            print(f"An error occurred: {e}")




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




    def sign_transaction(self, message: bytes, network: str, identifier: str) -> bytes:
        """
        Sign a transaction using the stored private key in KeyManager.

        Args:
            message (bytes): The message to sign.
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
            
            # ✅ Create a new Falcon SecretKey instance
            secret_key = SecretKey(512)

            # ✅ Convert stored JSON complex values back to real complex numbers
            for key, value in private_key_json.items():
                if isinstance(value, dict) and "real" in value and "imag" in value:
                    # ✅ Convert back to complex number
                    setattr(secret_key, key, complex(value["real"], value["imag"]))
                else:
                    setattr(secret_key, key, value)  # ✅ Set other values normally

        except Exception as e:
            raise ValueError(f"Failed to load private key for signing: {e}")

        print(f"🔹 Signing transaction for {network.upper()} using {identifier}...")

        # ✅ Sign the message using Falcon
        signature = secret_key.sign(message)
        print("✅ Transaction signed successfully.")
        
        return signature




    def verify_transaction(self, message: bytes, signature: bytes, network: str, identifier: str) -> bool:
        """
        Verify a transaction signature using the stored public key.

        Args:
            message (bytes): The message to verify.
            signature (bytes): The signature to verify.
            network (str): The network ("testnet" or "mainnet").
            identifier (str): The key identifier to verify with.

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
            public_key_json = json.loads(base64.b64decode(key_data["public_key"]).decode("utf-8"))
            public_key = PublicKey(SecretKey(512))  # ✅ Create Falcon public key
            public_key.__dict__.update(public_key_json)  # ✅ Restore public key data
        except Exception as e:
            raise ValueError(f"Failed to load public key for verification: {e}")

        print(f"🔹 Verifying transaction for {network.upper()} using {identifier}...")

        # ✅ Verify the message signature
        is_valid = public_key.verify(message, signature)

        if is_valid:
            print("✅ Transaction verified successfully.")
        else:
            print("❌ Transaction verification failed.")

        return is_valid



    def export_keys(self):
        """
        Export a specific key set (miner, validator, channel) based on user selection.
        Saves the exported keys in a .txt file with a box-like structure using UTF-8 encoding.
        """
        print("\n🔹 Export Key Pairs")

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

        # ✅ Ensure the directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        # ✅ Write using UTF-8 encoding to prevent Unicode errors
        with open(filename, "w", encoding="utf-8") as file:
            file.write(f"\n{'=' * 80}\n")
            file.write(f"🔹 {role.capitalize()} Key Export - {selected_identifier.upper()} - {network.upper()}\n")
            file.write(f"{'=' * 80}\n\n")
            file.write(f"{'|' + ' ' * 30 + 'PRIVATE KEY' + ' ' * 30 + '|'}\n")
            file.write(f"{'=' * 80}\n")
            file.write(f"{'| '}{selected_key_data.get('private_key', 'N/A')}{' |'}\n")
            file.write(f"{'=' * 80}\n\n")

            file.write(f"{'|' + ' ' * 31 + 'PUBLIC KEY' + ' ' * 31 + '|'}\n")
            file.write(f"{'=' * 80}\n")
            file.write(f"{'| '}{selected_key_data.get('public_key', 'N/A')}{' |'}\n")
            file.write(f"{'=' * 80}\n\n")

            file.write(f"{'|' + ' ' * 28 + 'HASHED PUBLIC KEY' + ' ' * 28 + '|'}\n")
            file.write(f"{'=' * 80}\n")
            file.write(f"{'| '}{selected_key_data.get('hashed_public_key', 'N/A')}{' |'}\n")
            file.write(f"{'=' * 80}\n\n")

        print(f"\n✅ Exported {role.capitalize()} {selection} to {filename}.")

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




if __name__ == "__main__":
    try:
        print("\n🔹 Initializing KeyManager...")
        key_manager = KeyManager()  # ✅ Ensures KeyManager is initialized correctly

        # ✅ Ensure that keys exist before starting menu
        if not key_manager.keys:
            print("⚠️ No keys found. Creating new key file...")
            key_manager.initialize_keys_structure()

        print("\n✅ KeyManager is ready. Launching menu...\n")
        key_manager.interactive_menu()  # ✅ Start the interactive menu

    except Exception as e:
        print(f"\n❌ An error occurred during initialization: {e}")
