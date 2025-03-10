import sys
import os
import json 
# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
sys.path.append(project_root)



from termcolor import colored




import argparse
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager

def load_keys_from_json_or_generate(key_manager, file_path="keys.json"):
    """
    Load keys from the JSON dump or generate them if no keys exist.
    :param key_manager: The KeyManager instance.
    :param file_path: Path to the JSON file where keys are stored.
    :return: The keys dictionary.
    """
    try:
        with open(file_path, "r") as file:
            keys = json.load(file)
            if not keys or not any(keys[network]["keys"] for network in ["testnet", "mainnet"]):
                raise ValueError("Key file is empty or contains no keys.")
            return keys
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        print("No keys found. Generating new keys...")
        key_manager.generate_default_keys()
        with open(file_path, "r") as file:
            return json.load(file)

def list_keys_with_defaults(keys):
    """
    Display all keys from the JSON dump along with their current defaults.
    """
    print("\n--- Testnet Keys ---")
    testnet_keys = keys.get("testnet", {}).get("keys", {})
    for i, (identifier, key_data) in enumerate(testnet_keys.items(), 1):
        is_default = any(
            keys["testnet"]["defaults"].get(role) == identifier
            for role in keys["testnet"]["defaults"]
        )
        default_marker = "(Default)" if is_default else ""
        print(f"{i}. {identifier} {default_marker} (Public Hash: {key_data['hashed_public_key']})")

    print("\n--- Mainnet Keys ---")
    mainnet_keys = keys.get("mainnet", {}).get("keys", {})
    for i, (identifier, key_data) in enumerate(mainnet_keys.items(), 1):
        is_default = any(
            keys["mainnet"]["defaults"].get(role) == identifier
            for role in keys["mainnet"]["defaults"]
        )
        default_marker = "(Default)" if is_default else ""
        print(f"{i}. {identifier} {default_marker} (Public Hash: {key_data['hashed_public_key']})")

def change_defaults_interactively(keys, key_manager):
    """
    Allow the user to interactively select a default key for testnet or mainnet.
    """
    print("\nChoose a network to update defaults:")
    print("1. Testnet")
    print("2. Mainnet")
    network_choice = input("Enter your choice (1/2): ").strip()

    if network_choice == "1":
        network = "testnet"
    elif network_choice == "2":
        network = "mainnet"
    else:
        print("Invalid choice. Exiting.")
        return

    # List available keys for the selected network
    available_keys = keys[network]["keys"]
    print(f"\nAvailable keys for {network}:")
    for i, identifier in enumerate(available_keys.keys(), 1):
        print(f"{i}. {identifier}")

    try:
        selected_index = int(input(f"\nSelect a key by number to set as default for {network}: ").strip())
        if selected_index < 1 or selected_index > len(available_keys):
            print("Invalid selection. Exiting.")
            return
        selected_identifier = list(available_keys.keys())[selected_index - 1]

        # Update defaults for all roles in the selected network
        key_manager.set_default_key(network, selected_identifier)
        print(f"\nDefault keys for all roles in {network} set to '{selected_identifier}'.")
    except ValueError:
        print("Invalid input. Exiting.")
        return

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

    # Save updated defaults
    self.save_keys()
    print(colored(f"Default keys for all roles in {network} set to '{identifier}'.", "green"))




if __name__ == "__main__":
    # Initialize KeyManager
    key_manager = KeyManager()

    # Step 1: Load keys or generate them if necessary
    keys = load_keys_from_json_or_generate(key_manager)

    # Step 2: List all keys with defaults
    list_keys_with_defaults(keys)

    # Step 3: Prompt to change defaults
    print("\nWould you like to update the default keys? (y/n)")
    if input().strip().lower() == "y":
        change_defaults_interactively(keys, key_manager)
    else:
        print("No changes made. Exiting.")
