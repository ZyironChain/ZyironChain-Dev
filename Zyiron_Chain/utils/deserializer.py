import base64
import json
import binascii
from typing import Union, Any
from Zyiron_Chain.utils.data_encoding import DataEncoding
from Zyiron_Chain.utils.serialization import Serialization
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


class Deserializer:
    """
    Handles automatic deserialization of data when needed.
    - Detects if input is bytes and applies necessary decoding.
    - Converts data from Base64, Base58, Hex, or UTF-8.
    - Converts JSON bytes back to objects if applicable.
    - Handles invalid formats gracefully and logs issues.
    """

    def __init__(self):
        self.encoding = DataEncoding()
        self.serialization = Serialization()
        print("[DESERIALIZER] Initialized with robust auto-detection and error handling.")

    def deserialize(self, data: Union[bytes, str, dict, list]) -> Any:
        """
        Automatically detects if data needs to be deserialized and performs the operation.

        :param data: The input data, which could be bytes, a string, or already deserialized.
        :return: The deserialized object or the original data if deserialization is not needed.
        """
        print(f"[DESERIALIZER] Received data for deserialization: {type(data)}")

        # If it's already a dictionary, list, or deserialized object, return as-is
        if isinstance(data, (dict, list)):
            print("[DESERIALIZER] Data is already deserialized. Returning as-is.")
            return data

        # If it's bytes, attempt to determine its encoding type
        if isinstance(data, bytes):
            return self._deserialize_bytes(data)

        # If it's a string, check if it's a valid JSON and convert to dict/list
        if isinstance(data, str):
            return self._deserialize_string(data)

        # If it's an unrecognized format, return it unchanged
        print("[DESERIALIZER WARNING] Unrecognized format, returning data as-is.")
        return data

    def _deserialize_bytes(self, data: bytes) -> Any:
        """
        Handle deserialization for byte-based data formats.
        """
        try:
            # 1️⃣ Attempt UTF-8 decoding first (common for JSON storage)
            decoded_str = self.encoding.bytes_to_utf8(data)

            # 2️⃣ Check if it's a JSON string
            if self._is_json(decoded_str):
                print("[DESERIALIZER] Detected JSON bytes, converting to dictionary.")
                return json.loads(decoded_str)

            # 3️⃣ Attempt Hex decoding (if it's a valid hex string)
            if self._is_hex(decoded_str):
                print("[DESERIALIZER] Detected Hex encoding, decoding bytes.")
                return self.encoding.hex_to_bytes(decoded_str)

            # 4️⃣ Attempt Base64 decoding
            if self._is_base64(decoded_str):
                print("[DESERIALIZER] Detected Base64 encoding, decoding bytes.")
                return self.encoding.base64_to_bytes(decoded_str)

            # 5️⃣ Attempt Base58 decoding
            if self._is_base58(decoded_str):
                print("[DESERIALIZER] Detected Base58 encoding, decoding bytes.")
                return self.encoding.base58_to_bytes(decoded_str)

            # 6️⃣ Default: return as UTF-8 decoded string
            print("[DESERIALIZER] Returning UTF-8 decoded string.")
            return decoded_str

        except Exception as e:
            print(f"[DESERIALIZER ERROR] Failed to auto-detect byte encoding: {e}")
            return None

    def _deserialize_string(self, data: str) -> Any:
        """
        Handle deserialization for string-based data formats.
        """
        try:
            # 1️⃣ Check if it's JSON
            if self._is_json(data):
                print("[DESERIALIZER] Detected JSON string, converting to object.")
                return json.loads(data)

            # 2️⃣ Check if it's a valid hex string
            if self._is_hex(data):
                print("[DESERIALIZER] Detected Hex string, converting to bytes.")
                return self.encoding.hex_to_bytes(data)

            # 3️⃣ Check if it's Base64
            if self._is_base64(data):
                print("[DESERIALIZER] Detected Base64 string, converting to bytes.")
                return self.encoding.base64_to_bytes(data)

            # 4️⃣ Check if it's Base58
            if self._is_base58(data):
                print("[DESERIALIZER] Detected Base58 string, converting to bytes.")
                return self.encoding.base58_to_bytes(data)

            # 5️⃣ If it's just a regular string, return as-is
            print("[DESERIALIZER] String format unrecognized, returning as-is.")
            return data

        except Exception as e:
            print(f"[DESERIALIZER ERROR] Failed to process string data: {e}")
            return None

    # ------------------------------------------------
    # 🔹 UTILITY METHODS FOR DETECTING DATA FORMATS 🔹
    # ------------------------------------------------

    def _is_json(self, data: str) -> bool:
        """
        Check if the string is a valid JSON format.
        """
        try:
            json.loads(data)
            return True
        except (json.JSONDecodeError, TypeError):
            return False

    def _is_hex(self, data: str) -> bool:
        """
        Check if a string is a valid hex format.
        """
        try:
            binascii.unhexlify(data)
            return True
        except (binascii.Error, ValueError):
            return False

    def _is_base64(self, data: str) -> bool:
        """
        Check if a string is Base64-encoded.
        """
        try:
            base64.b64decode(data, validate=True)
            return True
        except (binascii.Error, ValueError):
            return False

    def _is_base58(self, data: str) -> bool:
        """
        Check if a string is Base58-encoded.
        """
        return all(c in self.encoding._BASE58_ALPHABET for c in data)
