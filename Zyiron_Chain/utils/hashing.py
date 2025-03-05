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
    Centralized hashing utilities for the blockchain system.
    Always uses single SHA3-384 hashing and returns the hash as bytes.
    All input data must be provided as bytes.
    """

    @staticmethod
    def sha3_384(data: bytes) -> bytes:
        """
        Compute a single SHA3-384 hash.

        :param data: Input data in bytes format.
        :return: SHA3-384 hashed output as bytes.
        """
        try:
            # Compute hash and get digest in bytes
            result = hashlib.sha3_384(data).digest()
            print(f"[Hashing.sha3_384] Successfully computed hash for data (length={len(data)}).")
            return result
        except Exception as e:
            print(f"[Hashing.sha3_384] ERROR: Failed to compute hash. Exception: {e}")
            raise

    @classmethod
    def hash(cls, data: bytes) -> bytes:
        """
        Compute a single SHA3-384 hash for the input data using the single hashing method.
        This method ensures that the output is always in bytes.

        :param data: Input data in bytes format.
        :return: SHA3-384 hash as bytes.
        """
        print(f"[Hashing.hash] Called with data length: {len(data)} bytes.")
        return cls.sha3_384(data)
