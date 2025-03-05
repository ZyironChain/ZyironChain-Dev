import base64
import base58  # Requires the 'base58' package to be installed
import logging
from typing import Union

# Import Constants to use any constant values if needed.
from Zyiron_Chain.blockchain.constants import Constants

class DataEncoding:
    """
    Handles all data encoding and decoding operations including:
      - Bytes ↔ Hexadecimal
      - Bytes ↔ Base64
      - Bytes ↔ Base58
      - Bytes ↔ UTF-8
    Detailed print statements are provided for internal debugging and error tracing.
    """

    def __init__(self):
        print("[DATA ENCODING] Initialized DataEncoding class for handling data conversion operations.")

    def bytes_to_hex(self, data: bytes) -> str:
        """
        Convert bytes to a hexadecimal string.
        :param data: Data in bytes.
        :return: Hexadecimal string.
        """
        print(f"[DATA ENCODING] bytes_to_hex called with data: {data}")
        if not isinstance(data, bytes):
            print("[DATA ENCODING ERROR] Input must be of type 'bytes'.")
            raise ValueError("Data must be bytes for hex conversion.")
        hex_str = data.hex()
        print(f"[DATA ENCODING] Conversion result (Hex): {hex_str}")
        return hex_str

    def hex_to_bytes(self, hex_str: str) -> bytes:
        """
        Convert a hexadecimal string to bytes.
        :param hex_str: Hexadecimal string.
        :return: Decoded bytes.
        """
        print(f"[DATA ENCODING] hex_to_bytes called with hex_str: {hex_str}")
        if not isinstance(hex_str, str):
            print("[DATA ENCODING ERROR] Input must be of type 'str'.")
            raise ValueError("Hex input must be a string.")
        try:
            data = bytes.fromhex(hex_str)
        except ValueError as e:
            print(f"[DATA ENCODING ERROR] Failed to decode hex string: {e}")
            raise ValueError(f"Invalid hex string: {hex_str}") from e
        print(f"[DATA ENCODING] Conversion result (Bytes): {data}")
        return data

    def bytes_to_base64(self, data: bytes) -> str:
        """
        Convert bytes to a Base64-encoded string.
        :param data: Data in bytes.
        :return: Base64-encoded string.
        """
        print(f"[DATA ENCODING] bytes_to_base64 called with data: {data}")
        if not isinstance(data, bytes):
            print("[DATA ENCODING ERROR] Input must be of type 'bytes'.")
            raise ValueError("Data must be bytes for Base64 conversion.")
        encoded = base64.b64encode(data).decode('utf-8')
        print(f"[DATA ENCODING] Conversion result (Base64): {encoded}")
        return encoded

    def base64_to_bytes(self, b64_str: str) -> bytes:
        """
        Convert a Base64-encoded string back to bytes.
        :param b64_str: Base64 string.
        :return: Decoded bytes.
        """
        print(f"[DATA ENCODING] base64_to_bytes called with b64_str: {b64_str}")
        if not isinstance(b64_str, str):
            print("[DATA ENCODING ERROR] Input must be of type 'str'.")
            raise ValueError("Base64 input must be a string.")
        try:
            data = base64.b64decode(b64_str.encode('utf-8'))
        except Exception as e:
            print(f"[DATA ENCODING ERROR] Failed to decode Base64 string: {e}")
            raise ValueError(f"Invalid Base64 string: {b64_str}") from e
        print(f"[DATA ENCODING] Conversion result (Bytes): {data}")
        return data

    def bytes_to_utf8(self, data: bytes) -> str:
        """
        Convert bytes to a UTF-8 string.
        :param data: Data in bytes.
        :return: UTF-8 decoded string.
        """
        print(f"[DATA ENCODING] bytes_to_utf8 called with data: {data}")
        if not isinstance(data, bytes):
            print("[DATA ENCODING ERROR] Input must be of type 'bytes'.")
            raise ValueError("Data must be bytes for UTF-8 conversion.")
        try:
            text = data.decode('utf-8')
        except Exception as e:
            print(f"[DATA ENCODING ERROR] Failed to decode UTF-8: {e}")
            raise ValueError("Invalid UTF-8 byte sequence.") from e
        print(f"[DATA ENCODING] Conversion result (UTF-8): {text}")
        return text

    def utf8_to_bytes(self, text: str) -> bytes:
        """
        Convert a UTF-8 string to bytes.
        :param text: UTF-8 string.
        :return: Encoded bytes.
        """
        print(f"[DATA ENCODING] utf8_to_bytes called with text: {text}")
        if not isinstance(text, str):
            print("[DATA ENCODING ERROR] Input must be of type 'str'.")
            raise ValueError("Text must be a string for UTF-8 encoding.")
        data = text.encode('utf-8')
        print(f"[DATA ENCODING] Conversion result (Bytes): {data}")
        return data

    def bytes_to_base58(self, data: bytes) -> str:
        """
        Convert bytes to a Base58-encoded string.
        :param data: Data in bytes.
        :return: Base58 string.
        """
        print(f"[DATA ENCODING] bytes_to_base58 called with data: {data}")
        if not isinstance(data, bytes):
            print("[DATA ENCODING ERROR] Input must be of type 'bytes'.")
            raise ValueError("Data must be bytes for Base58 conversion.")
        try:
            b58_str = base58.b58encode(data).decode('utf-8')
        except Exception as e:
            print(f"[DATA ENCODING ERROR] Failed to encode Base58: {e}")
            raise ValueError("Base58 encoding failed.") from e
        print(f"[DATA ENCODING] Conversion result (Base58): {b58_str}")
        return b58_str

    def base58_to_bytes(self, b58_str: str) -> bytes:
        """
        Convert a Base58-encoded string to bytes.
        :param b58_str: Base58 string.
        :return: Decoded bytes.
        """
        print(f"[DATA ENCODING] base58_to_bytes called with b58_str: {b58_str}")
        if not isinstance(b58_str, str):
            print("[DATA ENCODING ERROR] Input must be of type 'str'.")
            raise ValueError("Base58 input must be a string.")
        try:
            data = base58.b58decode(b58_str)
        except Exception as e:
            print(f"[DATA ENCODING ERROR] Failed to decode Base58: {e}")
            raise ValueError("Invalid Base58 string.") from e
        print(f"[DATA ENCODING] Conversion result (Bytes): {data}")
        return data
