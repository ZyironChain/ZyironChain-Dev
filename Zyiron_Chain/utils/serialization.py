import base64
import json
import logging
from decimal import Decimal



class Serialization:
    """
    Provides methods to convert bytes and objects into various human-readable formats
    (Hex, Base64, UTF-8, and JSON) and back to their original formats.
    This class uses single hashing where applicable and detailed print statements
    to trace each step.
    """

    def __init__(self):
        print("[SERIALIZATION] Initialized Serialization class for multi-format conversions.")

    # ----------------------------
    # Byte <-> Hex Conversions
    # ----------------------------
    def bytes_to_hex(self, data: bytes) -> str:
        print(f"[SERIALIZATION] Converting bytes to hex. Input bytes: {data}")
        if not isinstance(data, bytes):
            print("[SERIALIZATION ERROR] Data must be bytes for hex conversion.")
            raise ValueError("Data must be bytes for hex conversion.")
        hex_str = data.hex()
        print(f"[SERIALIZATION] Converted to Hex: {hex_str}")
        return hex_str

    def hex_to_bytes(self, hex_str: str) -> bytes:
        print(f"[SERIALIZATION] Converting hex to bytes. Input hex: {hex_str}")
        if not isinstance(hex_str, str):
            print("[SERIALIZATION ERROR] Input must be a string for hex conversion.")
            raise ValueError("Hex input must be a string.")
        try:
            data = bytes.fromhex(hex_str)
            print(f"[SERIALIZATION] Converted to Bytes: {data}")
            return data
        except ValueError as e:
            print(f"[SERIALIZATION ERROR] Error converting hex to bytes: {e}")
            raise

    # ----------------------------
    # Byte <-> Base64 Conversions
    # ----------------------------
    def bytes_to_base64(self, data: bytes) -> str:
        print(f"[SERIALIZATION] Converting bytes to Base64. Input bytes: {data}")
        if not isinstance(data, bytes):
            print("[SERIALIZATION ERROR] Data must be bytes for Base64 conversion.")
            raise ValueError("Data must be bytes for Base64 conversion.")
        b64 = base64.b64encode(data).decode('utf-8')
        print(f"[SERIALIZATION] Converted to Base64: {b64}")
        return b64

    def base64_to_bytes(self, b64_str: str) -> bytes:
        print(f"[SERIALIZATION] Converting Base64 to bytes. Input Base64: {b64_str}")
        if not isinstance(b64_str, str):
            print("[SERIALIZATION ERROR] Input must be a string for Base64 conversion.")
            raise ValueError("Base64 input must be a string.")
        try:
            data = base64.b64decode(b64_str.encode('utf-8'))
            print(f"[SERIALIZATION] Converted to Bytes: {data}")
            return data
        except Exception as e:
            print(f"[SERIALIZATION ERROR] Error converting Base64 to bytes: {e}")
            raise

    # ----------------------------
    # Byte <-> UTF-8 Conversions
    # ----------------------------
    def bytes_to_utf8(self, data: bytes) -> str:
        print(f"[SERIALIZATION] Converting bytes to UTF-8. Input bytes: {data}")
        if not isinstance(data, bytes):
            print("[SERIALIZATION ERROR] Data must be bytes for UTF-8 conversion.")
            raise ValueError("Data must be bytes for UTF-8 conversion.")
        try:
            text = data.decode('utf-8')
            print(f"[SERIALIZATION] Converted to UTF-8: {text}")
            return text
        except UnicodeDecodeError as e:
            print(f"[SERIALIZATION ERROR] Failed to decode bytes to UTF-8: {e}")
            raise

    def utf8_to_bytes(self, text: str) -> bytes:
        print(f"[SERIALIZATION] Converting UTF-8 to bytes. Input text: {text}")
        if not isinstance(text, str):
            print("[SERIALIZATION ERROR] Input must be a string for UTF-8 conversion.")
            raise ValueError("UTF-8 input must be a string.")
        data = text.encode('utf-8')
        print(f"[SERIALIZATION] Converted to Bytes: {data}")
        return data

    # ----------------------------
    # Object <-> JSON Conversions
    # ----------------------------
    def object_to_json(self, obj: object, indent: int = 4) -> str:
        """
        Convert a Python object (e.g., dict, list) to a human-readable JSON string.
        """
        print(f"[SERIALIZATION] Converting object to JSON. Object: {obj}")
        try:
            json_str = json.dumps(obj, indent=indent, sort_keys=True)
            print(f"[SERIALIZATION] Converted object to JSON string:\n{json_str}")
            return json_str
        except (TypeError, ValueError) as e:
            print(f"[SERIALIZATION ERROR] Failed to convert object to JSON: {e}")
            raise

    def json_to_object(self, json_str: str) -> object:
        """
        Parse a JSON string and return the corresponding Python object.
        """
        print(f"[SERIALIZATION] Parsing JSON string to object. JSON string: {json_str}")
        if not isinstance(json_str, str):
            print("[SERIALIZATION ERROR] Input must be a string for JSON parsing.")
            raise ValueError("JSON input must be a string.")
        try:
            obj = json.loads(json_str)
            print(f"[SERIALIZATION] Parsed JSON to object: {obj}")
            return obj
        except json.JSONDecodeError as e:
            print(f"[SERIALIZATION ERROR] Failed to parse JSON string: {e}")
            raise

    # ----------------------------
    # Object <-> Bytes via JSON
    # ----------------------------
    def object_to_bytes(self, obj: object, indent: int = 4) -> bytes:
        """
        Convert a Python object to bytes by first converting it to a JSON string.
        """
        print(f"[SERIALIZATION] Converting object to bytes via JSON. Object: {obj}")
        json_str = self.object_to_json(obj, indent=indent)
        data_bytes = json_str.encode('utf-8')
        print(f"[SERIALIZATION] Converted object to bytes: {data_bytes}")
        return data_bytes

    def bytes_to_object(self, data: bytes) -> object:
        """
        Convert bytes (assumed to be a JSON string) back to a Python object.
        """
        print(f"[SERIALIZATION] Converting bytes to object via JSON. Input bytes: {data}")
        json_str = self.bytes_to_utf8(data)
        obj = self.json_to_object(json_str)
        print(f"[SERIALIZATION] Converted bytes to object: {obj}")
        return obj
