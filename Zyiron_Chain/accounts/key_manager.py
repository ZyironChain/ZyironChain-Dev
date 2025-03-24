import sys
import os

import os
import sys

# 🔧 Dynamically add the root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# ✅ Now this will work
from Zyiron_Chain.falcon.falcon.encoding import decompress

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
from Zyiron_Chain.falcon.falcon.falcon import HEAD_LEN, SALT_LEN, SecretKey, PublicKey
from Zyiron_Chain.accounts.wallet_api import serialize_complex 
import os
import qrcode
import base64
import textwrap
from PIL import Image, ImageDraw, ImageFont 


SIGNATURE_MAX_LENGTH = 750

class KeyManager:
    def __init__(self, key_file="Keys/KeyManager_Public_Private_Keys.json"):
        self.key_file = key_file
        self.network = "mainnet"  # Default network
        self.keys = {}
        self.MAX_KEYGEN_ATTEMPTS = 10  # Increased from 3 to handle Falcon-512 complexity

        print("\n🔹 Initializing KeyManager...")
        self._ensure_keys_directory_exists()
        self.load_or_initialize_keys()
        self._validate_all_keys()
        self._auto_set_network_defaults()
        print("\n✅ KeyManager Ready.")


    def _ensure_keys_directory_exists(self):
        """Create keys directory if it doesn't exist"""
        keys_dir = os.path.dirname(self.key_file)
        try:
            if keys_dir and not os.path.exists(keys_dir):
                print(f"📁 Creating missing directory: {keys_dir}")
                os.makedirs(keys_dir, exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"Failed to create keys directory: {str(e)}")

        
    def _validate_all_keys(self):
        """Validate basic structure and consistency of loaded keys"""
        print("🔍 Validating all keys...")
        valid_count = 0
        invalid_count = 0
        
        for network in self.keys:
            for key_id, key_data in list(self.keys[network]["keys"].items()):
                try:
                    # 1. Check required fields exist
                    if not all(k in key_data["private_key"] for k in ["f", "g", "F", "G"]):
                        raise ValueError("Missing polynomial components")
                    
                    # 2. Deserialize polynomials (basic format check only)
                    polys = self.deserialize_polynomials(key_data["private_key"])
                    
                    # 3. Verify public key consistency
                    public_key_data = json.loads(base64.b64decode(key_data["public_key"]).decode())
                    recomputed_hash = self._generate_hashed_pubkey(public_key_data["h"], network)
                    
                    if recomputed_hash != key_data["hashed_public_key"]:
                        raise ValueError("Public key hash mismatch")
                        
                    valid_count += 1
                    
                except Exception as e:
                    print(f"❌ Invalid key {network}/{key_id}: {str(e)}")
                    del self.keys[network]["keys"][key_id]
                    invalid_count += 1
                    
        if invalid_count > 0:
            self.save_keys()  # Persist changes if bad keys were removed
            print(f"⚠️ Removed {invalid_count} invalid keys, kept {valid_count} valid ones")
        else:
            print(f"✅ All {valid_count} keys validated successfully")








    def validate_key_pair(self, network: str, identifier: str) -> bool:
        """Validate key consistency using the deserializer"""
        try:
            key_data = self.keys[network]["keys"].get(identifier)
            if not key_data:
                return False
                
            # Will raise exception if invalid
            secret_key, public_key = self.deserialize_falcon_key(key_data)
            
            # Additional consistency checks
            test_msg = b"test_validation"
            sig = secret_key.sign(test_msg)
            if not public_key.verify(test_msg, sig):
                raise ValueError("Key pair failed consistency check")
                
            return True
            
        except Exception as e:
            print(f"❌ Key validation failed for {network}/{identifier}: {str(e)}")
            return False
        
        
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
        """Load keys or initialize new structure with atomic safety"""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if os.path.exists(self.key_file):
                    with open(self.key_file, "r") as f:
                        self.keys = json.load(f)
                    print(f"✅ Loaded existing key file: {self.key_file}")
                    return
                
                # Initialize new key structure
                print(f"⚠️ Key file not found. Creating new key file: {self.key_file}")
                self.initialize_keys_structure()
                return

            except json.JSONDecodeError:
                print("⚠️ Key file corrupted. Attempting recovery...")
                backup_file = f"{self.key_file}.bak.{attempt}"
                os.replace(self.key_file, backup_file)
                print(f"⚠️ Backed up corrupted file to: {backup_file}")
                continue
                
            except Exception as e:
                print(f"⚠️ Load attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_attempts - 1:
                    raise RuntimeError(f"Failed to load keys after {max_attempts} attempts")


    def initialize_keys_structure(self):
        """Initialize with empty validated structure"""
        os.makedirs(os.path.dirname(self.key_file), exist_ok=True)
        self.keys = {
            "testnet": {"keys": {}, "defaults": {"miner": "", "validator": "", "channel": ""}},
            "mainnet": {"keys": {}, "defaults": {"miner": "", "validator": "", "channel": ""}}
        }
        self.save_keys()

    def serialize_polynomials(self, f, g, F, G):
        """
        Serialize Falcon polynomials (f, g, F, G) into Base64-encoded strings.
        """
        return {
            'f': base64.b64encode(json.dumps(f).encode('utf-8')).decode('utf-8'),
            'g': base64.b64encode(json.dumps(g).encode('utf-8')).decode('utf-8'),
            'F': base64.b64encode(json.dumps(F).encode('utf-8')).decode('utf-8'),
            'G': base64.b64encode(json.dumps(G).encode('utf-8')).decode('utf-8')
        }
    
    def deserialize_polynomials(self, key_data):
        """
        Deserialize Base64-encoded strings back into Falcon polynomials (f, g, F, G).
        No longer performs NTRU validation (trusts Falcon's key generation).
        """
        try:
            # Deserialize polynomials from Base64
            f = json.loads(base64.b64decode(key_data['f']).decode('utf-8'))
            g = json.loads(base64.b64decode(key_data['g']).decode('utf-8'))
            F = json.loads(base64.b64decode(key_data['F']).decode('utf-8'))
            G = json.loads(base64.b64decode(key_data['G']).decode('utf-8'))
            
            print("✅ Deserialized polynomials successfully.")
            print(f"f: {f[:5]}... (length: {len(f)})")  # Show first 5 coefficients
            print(f"g: {g[:5]}... (length: {len(g)})")
            print(f"F: {F[:5]}... (length: {len(F)})")
            print(f"G: {G[:5]}... (length: {len(G)})")

            # Validate polynomial lengths match expected dimension
            n = len(f)
            if not all(len(poly) == n for poly in [g, F, G]):
                raise ValueError("Polynomial lengths don't match")

            return {'f': f, 'g': g, 'F': F, 'G': G}

        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            raise ValueError("Invalid polynomial JSON data") from e
        except base64.binascii.Error as e:
            print(f"❌ Base64 decode error: {e}")
            raise ValueError("Invalid Base64 data") from e
        except Exception as e:
            print(f"❌ Unexpected error during deserialization: {e}")
            raise
        
    def _convert_json_complex(self, obj):
        """
        Recursively convert dictionaries with 'real' and 'imag' keys into complex numbers.
        Handles nested structures (lists/dicts) and logs conversion issues for debugging.
        """
        try:
            if isinstance(obj, dict):
                # Convert dicts with 'real' and 'imag' to complex numbers
                if 'real' in obj and 'imag' in obj:
                    try:
                        return complex(float(obj['real']), float(obj['imag']))
                    except (TypeError, ValueError) as e:
                        print(f"⚠️ Failed to convert dict to complex: {obj}. Error: {e}")
                        return obj  # Return original if conversion fails
                
                # Recursively process other dictionaries
                return {k: self._convert_json_complex(v) for k, v in obj.items()}
            
            elif isinstance(obj, list):
                # Recursively process lists
                return [self._convert_json_complex(v) for v in obj]
            
            else:
                # Return non-convertible values as-is
                return obj

        except Exception as e:
            print(f"❌ Critical error in _convert_json_complex: {e}")
            raise ValueError(f"Complex number conversion failed: {e}")
        



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
        Add a new key, trusting Falcon's internal validation.
        """
        network = network.lower()
        if network not in ("testnet", "mainnet"):
            raise ValueError(f"Invalid network '{network}'. Must be 'testnet' or 'mainnet'.")

        # Check for existing key
        if any(k["role"] == role for k in self.keys[network]["keys"].values()):
            print(f"✅ {role} key exists in {network}. Skipping generation.")
            return

        print(f"🔑 Generating {role} key pair for {network.upper()} [{identifier}]...")

        for attempt in range(self.MAX_KEYGEN_ATTEMPTS):
            try:
                # Generate Falcon-512 key pair
                private_key = SecretKey(512)
                public_key = PublicKey(private_key)

                # Serialize key data
                key_data = {
                    "private_key": self.serialize_polynomials(
                        private_key.f, private_key.g, 
                        private_key.F, private_key.G
                    ),
                    "public_key": base64.b64encode(
                        json.dumps({"h": public_key.h}, default=serialize_complex).encode()
                    ).decode(),
                    "hashed_public_key": self._generate_hashed_pubkey(public_key.h, network),
                    "role": role,
                    "network": network,
                    "version": "1.1"
                }

                # Store and set as default if needed
                self.keys[network]["keys"][identifier] = key_data
                if not self.keys[network]["defaults"].get(role):
                    self.keys[network]["defaults"][role] = identifier
                    print(f"⚡ Set default {role} key for {network.upper()}")

                self.save_keys()
                return

            except Exception as e:
                print(f"⚠️ Key generation attempt {attempt + 1} failed: {str(e)}")
                if attempt == self.MAX_KEYGEN_ATTEMPTS - 1:
                    raise RuntimeError(f"Failed to generate key after {self.MAX_KEYGEN_ATTEMPTS} attempts")





    def _generate_hashed_pubkey(self, h, network):
        """Generate network-prefixed hashed public key"""
        raw = json.dumps({"h": h}, default=serialize_complex).encode()
        return ("ZYT" if network == "testnet" else "ZYC") + hashlib.sha3_384(raw).hexdigest()

    def save_keys(self):
        """Save keys with atomic write pattern to prevent corruption"""
        temp_file = f"{self.key_file}.tmp"
        try:
            with open(temp_file, "w") as f:
                json.dump(self.keys, f, indent=4, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic rename
            if os.path.exists(self.key_file):
                os.replace(temp_file, self.key_file)
            else:
                os.rename(temp_file, self.key_file)
                
            print(colored(f"✅ Keys saved atomically to {self.key_file}", "green"))
        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise RuntimeError(f"Key save failed: {str(e)}")
                
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
                # Signing a message
                try:
                    network = input("Enter the network (testnet or mainnet): ").strip().lower()
                    identifier = input("Enter the key identifier: ").strip()
                    message = input("Enter the message to sign: ").strip()
                    
                    # Convert to bytes once (consistent encoding)
                    message_bytes = message.encode('utf-8')

                    # Verify hashed public key consistency
                    recomputed_hash = self.recompute_hashed_public_key(network, identifier)
                    stored_hash = self.keys[network]["keys"][identifier]["hashed_public_key"]
                    
                    if recomputed_hash != stored_hash:
                        print(f"\n⚠️ Updating inconsistent public key hash...")
                        self.keys[network]["keys"][identifier]["hashed_public_key"] = recomputed_hash
                        self.save_keys()

                    # Sign the message
                    signature = self.sign_transaction(message_bytes, network, identifier)
                    signature_b64 = base64.b64encode(signature).decode('utf-8')
                    
                    print("\n✅ Message signed successfully!")
                    print(f"🔹 Signature (Base64): {signature_b64}")
                    print(f"🔹 Message length: {len(message_bytes)} bytes")
                    print(f"🔹 Signature length: {len(signature)} bytes")

                except Exception as e:
                    print(f"\n❌ Signing failed: {str(e)}")

            elif choice == "7":
                # Verifying a message
                try:
                    network = input("Enter the network (testnet or mainnet): ").strip().lower()
                    identifier = input("Enter the key identifier: ").strip()
                    message = input("Enter the original message: ").strip()
                    signature_b64 = input("Enter the Base64 signature: ").strip()
                    
                    # Convert to same format used for signing
                    message_bytes = message.encode('utf-8')
                    signature_bytes = base64.b64decode(signature_b64)

                    # Verify public key consistency
                    recomputed_hash = self.recompute_hashed_public_key(network, identifier)
                    stored_hash = self.keys[network]["keys"][identifier]["hashed_public_key"]
                    
                    if recomputed_hash != stored_hash:
                        print(f"\n⚠️ Updating inconsistent public key hash...")
                        self.keys[network]["keys"][identifier]["hashed_public_key"] = recomputed_hash
                        self.save_keys()

                    # Verify signature
                    if self.verify_transaction(message_bytes, signature_bytes, network, identifier):
                        print("\n✅ Signature is VALID")
                        print(f"🔹 Verified message: '{message}'")
                    else:
                        print("\n❌ Signature is INVALID")
                        print("Possible causes:")
                        print("- Message was modified")
                        print("- Wrong signing key was used")
                        print("- Signature was corrupted")

                except Exception as e:
                    print(f"\n❌ Verification failed: {str(e)}")

            elif choice == "8":
                self.export_keys()
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
        try:
            network = self.network
            role = "miner"
            
            if role not in self.keys[network]["defaults"]:
                raise ValueError(f"No default key for role '{role}' in {network}")

            identifier = self.keys[network]["defaults"][role]
            key_data = self.keys[network]["keys"].get(identifier, {})

            # Get user input and ensure bytes
            user_input = input("\nEnter the message to sign: ").strip()
            message = user_input.encode("utf-8")  # Always encode to bytes

            # Sign
            signature = self.sign_transaction(message, network, identifier)
            signature_base64 = base64.b64encode(signature).decode("utf-8")
            print(f"\n✅ Signature (Base64): {signature_base64}")

            # Verify if requested
            if input("\nVerify signature? (yes/no): ").lower() == "yes":
                is_valid = self.verify_transaction(
                    message,  # Pass same bytes used for signing
                    signature,  # Already in bytes format
                    network,
                    identifier
                )
                print("\n✅ Verification passed!" if is_valid else "\n❌ Verification failed!")

        except Exception as e:
            print(f"\n❌ Error: {e}")

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
        """Sign using the deserialize_falcon_key function"""
        try:
            key_data = self.keys[network]["keys"].get(identifier)
            if not key_data:
                raise ValueError(f"Key '{identifier}' not found")
                
            # Deserialize using centralized function
            secret_key, _ = self.deserialize_falcon_key(key_data)
            
            message_bytes = message.encode('utf-8') if isinstance(message, str) else message
            return secret_key.sign(message_bytes)
            
        except Exception as e:
            print(f"❌ Signing failed: {str(e)}")
            raise



    def deserialize_falcon_key(self, key_data: dict) -> tuple[SecretKey, PublicKey]:
        """
        Fully reconstruct Falcon keys from serialized data with validation.
        Returns: (secret_key, public_key)
        Raises: ValueError if deserialization fails
        """
        try:
            # Deserialize private key polynomials
            private_polys = self.deserialize_polynomials(key_data["private_key"])
            
            # Reconstruct SecretKey
            secret_key = SecretKey(512, polys=[
                private_polys['f'],
                private_polys['g'],
                private_polys['F'],
                private_polys['G']
            ])
            
            # Deserialize public key with complex number handling
            public_key_json = json.loads(
                base64.b64decode(key_data["public_key"]).decode("utf-8"),
                object_hook=self._convert_json_complex
            )
            
            # Reconstruct PublicKey
            public_key = PublicKey(secret_key)  # Creates blank key
            public_key.h = public_key_json["h"]  # Set the actual public values
            
            return secret_key, public_key
            
        except Exception as e:
            raise ValueError(f"Key deserialization failed: {str(e)}")




    def verify_transaction(self, message: bytes, signature: (str|bytes), network: str, identifier: str) -> bool:
        """Verify a signature using the deserialize_falcon_key function"""
        try:
            # Get key data
            key_data = self.keys[network]["keys"].get(identifier)
            if not key_data:
                raise ValueError(f"Key '{identifier}' not found")
            
            # Deserialize keys using centralized function
            _, public_key = self.deserialize_falcon_key(key_data)
            
            # Convert inputs to bytes if needed
            signature_bytes = base64.b64decode(signature) if isinstance(signature, str) else signature
            message_bytes = message.encode('utf-8') if isinstance(message, str) else message
            
            # Verify signature
            is_valid = public_key.verify(message_bytes, signature_bytes)
            
            if is_valid:
                print("✅ Signature valid (squared norm = {public_key.get_squared_norm(signature_bytes)}")
            else:
                print("❌ Signature invalid")
                
            return is_valid
            
        except Exception as e:
            print(f"❌ Verification failed: {str(e)}")
            return False

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