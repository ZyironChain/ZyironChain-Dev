import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from decimal import Decimal


import hashlib

import hashlib

import hashlib

import hashlib

class Hashing:
    """
    Utility class for hashing operations using SHA3-384.
    """
    DEBUG = False  # Set to False to disable debug prints

    @staticmethod
    def sha3_384(data: bytes) -> bytes:
        """
        Compute the SHA3-384 hash of the input data.

        :param data: Input data as bytes.
        :return: SHA3-384 hash as bytes.
        """
        if not isinstance(data, bytes):
            raise TypeError("Input data must be of type bytes.")
        if Hashing.DEBUG:
            print(f"[Hashing.sha3_384] Successfully computed hash for data (length={len(data)}).")
        return hashlib.sha3_384(data).digest()

    @staticmethod
    def hash(data: bytes) -> bytes:
        """
        Compute the hash of the input data using SHA3-384.

        :param data: Input data as bytes.
        :return: SHA3-384 hash as bytes.
        """
        if not isinstance(data, bytes):
            raise TypeError("Input data must be of type bytes.")
        if Hashing.DEBUG:
            print(f"[Hashing.hash] Called with data length: {len(data)} bytes.")
        return Hashing.sha3_384(data)