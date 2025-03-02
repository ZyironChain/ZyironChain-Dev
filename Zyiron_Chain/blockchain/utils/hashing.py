import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from decimal import Decimal


import hashlib

import hashlib

class Hashing:
    """
    Centralized hashing utilities for the blockchain system.
    Supports both single and double SHA3-384 hashing.
    """

    # 🔹 **Enable Double Hashing**
    DOUBLE_HASHING_ENABLED = True  # ✅ Toggle between single and double SHA3-384 hashing

    @staticmethod
    def sha3_384(data: bytes) -> str:
        """
        Compute a single SHA3-384 hash.

        :param data: Input data in bytes format.
        :return: SHA3-384 hashed hex string.
        """
        return hashlib.sha3_384(data).hexdigest()

    @staticmethod
    def double_sha3_384(data: bytes) -> str:
        """
        Compute a double SHA3-384 hash for enhanced security.

        :param data: Input data in bytes format.
        :return: Double SHA3-384 hashed hex string.
        """
        first_hash = hashlib.sha3_384(data).digest()
        return hashlib.sha3_384(first_hash).hexdigest()

    @classmethod
    def hash(cls, data: bytes) -> str:
        """
        Compute the appropriate hash based on DOUBLE_HASHING_ENABLED.

        :param data: Input data in bytes format.
        :return: Hash string (single or double based on configuration).
        """
        if cls.DOUBLE_HASHING_ENABLED:
            return cls.double_sha3_384(data)
        return cls.sha3_384(data)
