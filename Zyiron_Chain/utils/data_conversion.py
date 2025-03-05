import base64

class Conversion:
    """
    Provides methods to convert bytes into various encodings (Hex, Base58, Base64, UTF-8)
    and convert them back to bytes. Includes super-detailed print statements for debugging.
    """

    # Base58 Alphabet (commonly used in Bitcoin-like systems)
    _BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

    def __init__(self):
        print("[CONVERSION] Initialized the Conversion class for various byte-encoding operations.")

    def bytes_to_hex(self, data: bytes) -> str:
        """
        Convert bytes to a hex-encoded string.
        
        :param data: The raw bytes to be converted.
        :return: Hexadecimal string representation of the input bytes.
        """
        print(f"[CONVERSION] bytes_to_hex called with data: {data}")
        if not isinstance(data, bytes):
            print("[CONVERSION ERROR] Input must be of type 'bytes'.")
            raise ValueError("Data must be bytes for hex conversion.")

        hex_str = data.hex()
        print(f"[CONVERSION] Conversion result (Hex): {hex_str}")
        return hex_str

    def hex_to_bytes(self, hex_str: str) -> bytes:
        """
        Convert a hex-encoded string back to raw bytes.
        
        :param hex_str: The hex string to decode.
        :return: Decoded raw bytes.
        """
        print(f"[CONVERSION] hex_to_bytes called with hex_str: {hex_str}")
        if not isinstance(hex_str, str):
            print("[CONVERSION ERROR] Input must be of type 'str'.")
            raise ValueError("Hex input must be a string.")

        try:
            decoded_bytes = bytes.fromhex(hex_str)
        except ValueError as e:
            print(f"[CONVERSION ERROR] Failed to decode hex string: {e}")
            raise ValueError(f"Invalid hex string: {hex_str}") from e

        print(f"[CONVERSION] Conversion result (Bytes): {decoded_bytes}")
        return decoded_bytes

    def bytes_to_base64(self, data: bytes) -> str:
        """
        Convert bytes to a Base64-encoded string.
        
        :param data: The raw bytes to be converted.
        :return: Base64 string representation of the input bytes.
        """
        print(f"[CONVERSION] bytes_to_base64 called with data: {data}")
        if not isinstance(data, bytes):
            print("[CONVERSION ERROR] Input must be of type 'bytes'.")
            raise ValueError("Data must be bytes for Base64 conversion.")

        encoded_str = base64.b64encode(data).decode('utf-8')
        print(f"[CONVERSION] Conversion result (Base64): {encoded_str}")
        return encoded_str

    def base64_to_bytes(self, b64_str: str) -> bytes:
        """
        Convert a Base64-encoded string back to raw bytes.
        
        :param b64_str: The Base64 string to decode.
        :return: Decoded raw bytes.
        """
        print(f"[CONVERSION] base64_to_bytes called with b64_str: {b64_str}")
        if not isinstance(b64_str, str):
            print("[CONVERSION ERROR] Input must be of type 'str'.")
            raise ValueError("Base64 input must be a string.")

        try:
            decoded_bytes = base64.b64decode(b64_str.encode('utf-8'))
        except Exception as e:
            print(f"[CONVERSION ERROR] Failed to decode Base64 string: {e}")
            raise ValueError(f"Invalid Base64 string: {b64_str}") from e

        print(f"[CONVERSION] Conversion result (Bytes): {decoded_bytes}")
        return decoded_bytes

    def bytes_to_utf8(self, data: bytes) -> str:
        """
        Convert bytes to a UTF-8 string.
        
        :param data: The raw bytes to be converted.
        :return: UTF-8 string representation of the input bytes.
        """
        print(f"[CONVERSION] bytes_to_utf8 called with data: {data}")
        if not isinstance(data, bytes):
            print("[CONVERSION ERROR] Input must be of type 'bytes'.")
            raise ValueError("Data must be bytes for UTF-8 conversion.")

        try:
            utf8_str = data.decode('utf-8')
        except UnicodeDecodeError as e:
            print(f"[CONVERSION ERROR] Failed to decode bytes to UTF-8: {e}")
            raise ValueError("Invalid UTF-8 data.") from e

        print(f"[CONVERSION] Conversion result (UTF-8): {utf8_str}")
        return utf8_str

    def utf8_to_bytes(self, text: str) -> bytes:
        """
        Convert a UTF-8 string back to raw bytes.
        
        :param text: The UTF-8 string to encode.
        :return: Encoded raw bytes.
        """
        print(f"[CONVERSION] utf8_to_bytes called with text: {text}")
        if not isinstance(text, str):
            print("[CONVERSION ERROR] Input must be of type 'str'.")
            raise ValueError("UTF-8 input must be a string.")

        encoded_bytes = text.encode('utf-8')
        print(f"[CONVERSION] Conversion result (Bytes): {encoded_bytes}")
        return encoded_bytes

    def bytes_to_base58(self, data: bytes) -> str:
        """
        Convert bytes to a Base58-encoded string.
        
        :param data: The raw bytes to be converted.
        :return: Base58 string representation of the input bytes.
        """
        print(f"[CONVERSION] bytes_to_base58 called with data: {data}")
        if not isinstance(data, bytes):
            print("[CONVERSION ERROR] Input must be of type 'bytes'.")
            raise ValueError("Data must be bytes for Base58 conversion.")

        # Convert bytes to a big integer
        int_val = int.from_bytes(data, byteorder='big')
        print(f"[CONVERSION] Intermediate integer value for Base58: {int_val}")

        # Special case for 0
        if int_val == 0:
            print("[CONVERSION] Data is zero; returning '1' as Base58 representation.")
            return "1"

        # Build the Base58 string
        result = []
        while int_val > 0:
            int_val, remainder = divmod(int_val, len(self._BASE58_ALPHABET))
            result.append(self._BASE58_ALPHABET[remainder])

        result.reverse()
        base58_str = "".join(result)

        # Preserve leading zero bytes
        # Each leading 0 byte in data is a "1" in Base58
        leading_zeros = len(data) - len(data.lstrip(b'\x00'))
        base58_str = ("1" * leading_zeros) + base58_str

        print(f"[CONVERSION] Conversion result (Base58): {base58_str}")
        return base58_str

    def base58_to_bytes(self, b58_str: str) -> bytes:
        """
        Convert a Base58-encoded string back to raw bytes.
        
        :param b58_str: The Base58 string to decode.
        :return: Decoded raw bytes.
        """
        print(f"[CONVERSION] base58_to_bytes called with b58_str: {b58_str}")
        if not isinstance(b58_str, str):
            print("[CONVERSION ERROR] Input must be of type 'str'.")
            raise ValueError("Base58 input must be a string.")

        int_val = 0
        for char in b58_str:
            if char not in self._BASE58_ALPHABET:
                print(f"[CONVERSION ERROR] Invalid Base58 character encountered: {char}")
                raise ValueError(f"Invalid Base58 character: {char}")
            int_val = int_val * 58 + self._BASE58_ALPHABET.index(char)

        # Convert the integer to bytes
        # We build the result in big-endian
        result_bytes = int_val.to_bytes((int_val.bit_length() + 7) // 8, byteorder='big')

        # Handle leading '1's as leading zero bytes
        leading_ones = 0
        for char in b58_str:
            if char == '1':
                leading_ones += 1
            else:
                break

        final_bytes = (b'\x00' * leading_ones) + result_bytes
        print(f"[CONVERSION] Conversion result (Bytes): {final_bytes}")
        return final_bytes
