import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
sys.path.append(project_root)


import logging
from termcolor import colored
import os
import json
import base64
import hashlib
from Zyiron_Chain.accounts.wallet import Wallet  # Import Wallet for Falcon key generation
from Zyiron_Chain.blockchain.constants import Constants

class KeyManager:
    def __init__(self, key_file="keys.json"):
        """
        Initialize the KeyManager with a JSON file for key storage.
        :param key_file: Path to the JSON file where keys are stored.
        """
        self.key_file = key_file
        self.network = Constants.NETWORK  # ✅ Dynamically fetch the active network

        # Ensure the directory exists
        key_dir = os.path.dirname(self.key_file)
        if key_dir and not os.path.exists(key_dir):
            os.makedirs(key_dir)

        self.keys = {}
        self.load_or_initialize_keys()

        # ✅ Auto-set default keys for active network
        self._auto_set_network_defaults()


    def load_or_initialize_keys(self):
        """
        Load keys from the JSON file or initialize a new structure if the file doesn't exist or is invalid.
        """
        if os.path.exists(self.key_file):
            try:
                with open(self.key_file, "r") as file:
                    self.keys = json.load(file)
                    if not self.keys:
                        raise ValueError("Key file is empty.")
            except (json.JSONDecodeError, ValueError):
                logging.error("Key file is empty or invalid. Initializing new keys...")
                self.initialize_keys_structure()
        else:
            logging.error("Key file not found. Initializing new keys...")
            self.initialize_keys_structure()


    def initialize_keys_structure(self):
        """
        Initialize the key structure for testnet and mainnet.
        """
        self.keys = {"testnet": {"keys": {}, "defaults": {}}, "mainnet": {"keys": {}, "defaults": {}}}
        self.save_keys()

    def save_keys(self):
        """
        Save the current keys to the JSON file.
        """
        with open(self.key_file, "w") as file:
            json.dump(self.keys, file, indent=4)
        print(colored(f"Keys saved to {self.key_file}.", "green"))

    def _auto_set_network_defaults(self):
        """
        Auto-set the default key for the currently active network.
        This ensures that the correct key is used when switching networks dynamically.
        """
        if not self.keys[self.network]["defaults"]:
            logging.info(f"[AUTO-SET] No default keys found for {self.network}. Generating new batch...")
            self.add_key_batch(self.network)
        else:
            logging.info(f"[AUTO-SET] Default keys are already set for {self.network}.")

    def get_default_public_key(self, role="miner"):
            """
            Retrieve the default public key for the active network and role.
            :param role: Role of the key (e.g., 'miner', 'validator').
            :return: The hashed public key (scriptPubKey).
            """
            if role not in self.keys[self.network]["defaults"]:
                raise ValueError(f"No default key set for role '{role}' in {self.network}.")

            default_identifier = self.keys[self.network]["defaults"][role]
            return self.keys[self.network]["keys"][default_identifier]["hashed_public_key"]

    def add_key_batch(self, network):
        """
        Add a synchronized batch of keys for the specified network.
        :param network: Either 'testnet' or 'mainnet'.
        """
        if network not in self.keys:
            raise ValueError("Invalid network. Choose 'testnet' or 'mainnet'.")

        # Determine the next batch identifier
        existing_batches = len({key.split("_")[1] for key in self.keys[network]["keys"].keys()})
        batch_id = existing_batches + 1

        logging.info(f"Starting key generation for batch {batch_id} in {network}...")

        # Generate keys for both roles in the batch
        self.add_key(network, "miner", f"miner_{batch_id}")
        self.add_key(network, "validator", f"validator_{batch_id}")

        logging.info(f"Batch {batch_id} key generation complete for {network}.")

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
        :param network: Either 'testnet' or 'mainnet'.
        :param role: The role of the key (e.g., 'miner', 'validator').
        :param identifier: Unique identifier for the key (e.g., 'miner_1').
        """
        if network not in self.keys:
            raise ValueError("Invalid network. Choose 'testnet' or 'mainnet'.")

        if identifier in self.keys[network]["keys"]:
            logging.warning(f"Key identifier '{identifier}' already exists in {network}. Skipping.")
            return

        logging.info(f"Generating {role} key for {identifier} in {network}...")

        # Generate keys using Wallet
        wallet = Wallet()
        private_key = wallet.testnet_secret_key if network == "testnet" else wallet.mainnet_secret_key
        public_key = wallet.testnet_public_key if network == "testnet" else wallet.mainnet_public_key

        private_key_serialized = base64.b64encode(
            json.dumps(private_key.__dict__, default=self._serialize_complex).encode("utf-8")
        ).decode("utf-8")
        public_key_serialized = base64.b64encode(
            json.dumps({"h": public_key.h}, default=self._serialize_complex).encode("utf-8")
        ).decode("utf-8")


        # Hash public key (used as scriptPubKey)
        hashed_public_key = wallet.public_key(network)

        # Add the new key
        self.keys[network]["keys"][identifier] = {
            "private_key": private_key_serialized,
            "public_key": public_key_serialized,
            "hashed_public_key": hashed_public_key,  # This serves as scriptPubKey
        }

        # ✅ Auto-set default key for the role if none exists
        if role not in self.keys[network]["defaults"]:
            self.keys[network]["defaults"][role] = identifier

        self.save_keys()

        logging.info(f"{network.upper()} {role.capitalize()} Key Generated: {identifier}")
        logging.info(f"Public Hash (scriptPubKey): {hashed_public_key}")

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
        Interactive menu to manage keys.
        """
        while True:
            print("\nKey Manager Options:")
            print("1. List keys for testnet")
            print("2. List keys for mainnet")
            print("3. Add new batch of keys to testnet")
            print("4. Add new batch of keys to mainnet")
            print("5. List current default keys")
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
            elif choice == "0":
                print("Exiting Key Manager.")
                break
            else:
                print(colored("Invalid choice. Please try again.", "red"))

    def validate_miner_key(self) -> bool:
        """
        Verify existence of default miner key without auto-generation.
        :return: True if valid miner key exists, False otherwise.
        """
        try:
            self.get_default_public_key("miner")
            return True
        except ValueError:
            return False

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

    def sign_transaction(self, message, role="channel"):
        """
        Sign a transaction using the wallet's private key stored in the KeyManager.
        :param message: The transaction data (tx_id or block data).
        :param role: The role of the key to use for signing (e.g., 'miner', 'channel').
        :return: The digital signature.
        """
        network = Constants.NETWORK  # ✅ Automatically detect active network

        if network not in self.keys:
            raise ValueError(f"[ERROR] Invalid network: {network}. Choose 'testnet' or 'mainnet'.")

        if role not in self.keys[network]["defaults"]:
            raise ValueError(f"[ERROR] No default key set for role '{role}' in {network}.")

        identifier = self.keys[network]["defaults"][role]

        # ✅ Retrieve the serialized private key
        private_key_serialized = self.keys[network]["keys"][identifier].get("private_key")
        if not private_key_serialized:
            raise ValueError(f"[ERROR] No private key found for role '{role}' in {network}.")

        try:
            # ✅ Decode the private key (base64 → JSON → SecretKey object)
            private_key_json = json.loads(base64.b64decode(private_key_serialized).decode("utf-8"))

            # ✅ Use the Wallet class to sign the transaction
            wallet = Wallet()
            signature = wallet.sign_transaction(message.encode(), network)  # ✅ Ensure message is bytes

            logging.info(f"[SIGNATURE] ✅ Transaction signed successfully for role '{role}' in {network}.")
            return signature

        except Exception as e:
            logging.error(f"[ERROR] Failed to sign transaction: {str(e)}")
            return None  # ✅ Return `None` if signing fails




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











if __name__ == "__main__":
    key_manager = KeyManager()

    # Launch the interactive menu
    key_manager.interactive_menu()
