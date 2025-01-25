

import os
import json
import sys

# Dynamically add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, project_root)

from Zyiron_Chain.blockchain.block import Block  # Import the Block class
import base64
from decimal import Decimal  # Ensure Decimal is imported
from Zyiron_Chain.blockchain.block import Block  # Import the Block class
import base64
from decimal import Decimal


class JSONHandler:
    def __init__(self, filename="blockchain.json"):
        """
        Initialize the JSONHandler with a specific filename.
        """
        self.filename = filename
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        self.file_path = os.path.join(project_root, self.filename)

    def write_on_disk(self, data, file_path):
        """
        Write data to a JSON file with proper serialization handling.
        """
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)  # Ensure directory exists
            with open(file_path, "w") as file:
                json.dump(data, file, indent=4, cls=DecimalEncoder)  # Use custom encoder for Decimal
            print(f"[INFO] Data successfully written to {file_path}")
        except Exception as e:
            print(f"[ERROR] Failed to write data to {file_path}: {e}")
            raise

    def read_from_disk(self, file_path):
        """
        Read data from a JSON file.
        """
        try:
            with open(file_path, "r") as file:
                data = json.load(file)
                print(f"[INFO] Data successfully loaded from {file_path}")
                return data
        except FileNotFoundError:
            print(f"[WARN] File {file_path} not found.")
            return None
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to decode JSON from {file_path}: {e}")
            return None
        except Exception as e:
            print(f"[ERROR] Unexpected error while reading {file_path}: {e}")
            return None

    @staticmethod
    def _handle_serialization(obj):
        """
        Handle unsupported types for JSON serialization.
        """
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def save_keys(self, private_key, public_key, key_file="keys.json"):
        """
        Save public and private keys to a JSON file.
        :param private_key: Private key in bytes.
        :param public_key: Public key in bytes.
        :param key_file: File name to save the keys.
        """
        key_data = {
            "private_key": base64.b64encode(private_key).decode("utf-8"),
            "public_key": base64.b64encode(public_key).decode("utf-8")
        }

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        key_file_path = os.path.join(project_root, key_file)

        try:
            os.makedirs(os.path.dirname(key_file_path), exist_ok=True)
            with open(key_file_path, "w") as file:
                json.dump(key_data, file, indent=4)
            print(f"[INFO] Keys saved to {key_file_path}")
        except Exception as e:
            print(f"[ERROR] Error saving keys to {key_file_path}: {e}")
            raise

    def load_keys(self, key_file="keys.json"):
        """
        Load public and private keys from a JSON file.
        :param key_file: File name to load the keys from.
        :return: Tuple of private key and public key in bytes.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        key_file_path = os.path.join(project_root, key_file)

        if not os.path.exists(key_file_path):
            raise FileNotFoundError(f"[ERROR] Key file {key_file} not found.")

        try:
            with open(key_file_path, "r") as file:
                key_data = json.load(file)

            private_key = base64.b64decode(key_data["private_key"])
            public_key = base64.b64decode(key_data["public_key"])

            print(f"[INFO] Keys loaded from {key_file_path}")
            return private_key, public_key
        except json.JSONDecodeError:
            print(f"[ERROR] Key file {key_file_path} is corrupted.")
            raise
        except Exception as e:
            print(f"[ERROR] Error loading keys from {key_file_path}: {e}")
            raise


class DecimalEncoder(json.JSONEncoder):
    """
    JSON Encoder to handle Decimal objects for serialization.
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)
