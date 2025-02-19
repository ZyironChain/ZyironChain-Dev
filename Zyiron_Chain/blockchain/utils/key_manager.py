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
    def __init__(self, key_file="Keys/KeyManager_Public_Private_Keys.json"):
        self.key_file = key_file
        self.network = Constants.NETWORK
        self.keys = {}
        self.load_or_initialize_keys()
        self._auto_set_network_defaults()

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
        """Auto-configure keys for current network"""
        network = self.network
        
        # Ensure network exists in keys structure
        if network not in self.keys:
            self.keys[network] = {"keys": {}, "defaults": {}}
        
        # Check for missing default miner key
        if "miner" not in self.keys[network]["defaults"]:
            logging.info(f"[AUTO-SET] Generating new miner key for {network}")
            self.add_key(network, "miner", f"miner_{len(self.keys[network]['keys']) + 1}")
        
        # Verify other essential roles
        for role in ["validator", "channel"]:
            if role not in self.keys[network]["defaults"]:
                self.add_key(network, role, f"{role}_{len(self.keys[network]['keys']) + 1}")

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
        """Initialize the key structure with essential roles"""
        self.keys = {
            "testnet": {
                "keys": {},
                "defaults": {"miner": "", "validator": "", "channel": ""}
            },
            "mainnet": {
                "keys": {},
                "defaults": {"miner": "", "validator": "", "channel": ""}
            }
        }
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

    def get_default_public_key(self, network=None, role="miner"):
        """
        Retrieve the default public key for the given network and role.
        
        :param network: (Optional) Network name (e.g., 'mainnet' or 'testnet'). 
                        If not provided, uses the active network (self.network).
        :param role: Role of the key (e.g., 'miner', 'validator').
        :return: The hashed public key (scriptPubKey).
        """
        # Use provided network if available, otherwise default to self.network
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
        Automatically sets as default for its role if no default exists.
        
        :param network: Network name ('testnet' or 'mainnet')
        :param role: Key role ('miner', 'validator', etc)
        :param identifier: Unique identifier for key management
        """
        # Validate network input
        network = network.lower()
        if network not in ("testnet", "mainnet"):
            raise ValueError(f"Invalid network '{network}'. Must be 'testnet' or 'mainnet'.")

        # Check for existing identifier
        if identifier in self.keys[network]["keys"]:
            existing_role = next(
                (r for r, id in self.keys[network]["defaults"].items() if id == identifier),
                None
            )
            msg = (f"Key identifier '{identifier}' already exists in {network} "
                   f"(used for {existing_role or 'unknown role'}).")
            logging.warning(msg)
            return

        logging.info(f"🔑 Generating {role} key pair for {network.upper()} [{identifier}]...")

        try:
            # Generate network-specific keys
            wallet = Wallet()
            if network == "testnet":
                private_key = wallet.testnet_secret_key
                public_key = wallet.testnet_public_key
            else:
                private_key = wallet.mainnet_secret_key
                public_key = wallet.mainnet_public_key

            # Serialize keys
            private_serialized = base64.b64encode(
                json.dumps(private_key.__dict__, default=self._serialize_complex).encode("utf-8")
            ).decode("utf-8")
            
            public_serialized = base64.b64encode(
                json.dumps({"h": public_key.h}, default=self._serialize_complex).encode("utf-8")
            ).decode("utf-8")

            # Generate scriptPubKey hash
            hashed_pubkey = wallet.public_key(network)
            if not hashed_pubkey:
                raise ValueError("Failed to generate public key hash")

        except Exception as e:
            logging.error(f"Key generation failed: {str(e)}")
            raise RuntimeError("Key pair generation aborted due to errors")

        # Store key data
        self.keys[network]["keys"][identifier] = {
            "private_key": private_serialized,
            "public_key": public_serialized,
            "hashed_public_key": hashed_pubkey,
            "role": role,
            "network": network
        }

        # Set as default if no default exists for this role
        current_default = self.keys[network]["defaults"].get(role)
        if not current_default or current_default not in self.keys[network]["keys"]:
            self.keys[network]["defaults"][role] = identifier
            logging.info(f"⚡ Set default {role} key for {network.upper()}: {identifier}")

        self.save_keys()
        
        logging.info(f"✅ Successfully generated {network.upper()} {role} key")
        logging.debug(f"Public Hash: {hashed_pubkey}")
        logging.debug(f"Stored Identifier: {identifier}")

        return hashed_pubkey
    
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
