import hashlib
from re import Pattern
import re
import time

import re
import hashlib
import time
from Zyiron_Chain.blockchain.constants import Constants  # ✅ Import latest constants
from Zyiron_Chain.blockchain.utils.hashing import Hashing


import re
import time
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.blockchain.utils.hashing import Hashing


class BlockHeader:
    _HASH_PATTERN: re.Pattern = re.compile(r'^[a-fA-F0-9]{96}$')  # Ensures SHA3-384 hash format

    def __init__(self, version, index, previous_hash, merkle_root, timestamp, nonce, difficulty, miner_address):
        """
        Initialize a BlockHeader with all required fields.
        """
        self.version = version
        self.index = index
        self.previous_hash = previous_hash
        self.merkle_root = merkle_root
        self.timestamp = timestamp
        self.nonce = nonce
        self.difficulty = self._adjust_difficulty(difficulty)  # Ensure difficulty is within bounds
        self.miner_address = miner_address  # Miner's address is stored

    def to_dict(self):
        return {
            "version": self.version,
            "index": self.index,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
            "miner_address": self.miner_address
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            version=data.get("version", Constants.VERSION),
            index=data["index"],
            previous_hash=data["previous_hash"],
            merkle_root=data["merkle_root"],
            timestamp=data["timestamp"],
            nonce=data["nonce"],
            difficulty=data.get("difficulty", Constants.GENESIS_TARGET),
            miner_address=data.get("miner_address", "Unknown")
        )







    def _adjust_difficulty(self, difficulty):
        """
        Ensure difficulty is within predefined min/max from Constants.
        """
        return max(min(difficulty, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)
    def calculate_hash(self):
        """
        Calculate the block header's double SHA3-384 hash.
        """
        header_string = (
            f"{self.version}{self.index}{self.previous_hash}"
            f"{self.merkle_root}{self.timestamp}{self.nonce}{self.difficulty}"
        ).encode()
        return Hashing.double_sha3_384(header_string)

    @property
    def hash_block(self):
        """
        Returns the hash of the block header (double SHA3-384).
        """
        return self.calculate_hash()

    def validate(self):
        """
        Comprehensive header validation, with precise checks for version, index, timestamps, etc.
        """
        validation_errors = []

        # Validate version
        if not isinstance(self.version, str) or self.version != Constants.VERSION:
            validation_errors.append(f"Invalid version: must match Constants.VERSION ({Constants.VERSION})")

        # Validate index
        if not isinstance(self.index, int) or self.index < 0:
            validation_errors.append("Invalid index: must be a non-negative integer")

        # Validate hashes using class-level pattern
        if not self._HASH_PATTERN.fullmatch(str(self.previous_hash)):
            validation_errors.append("Invalid previous_hash: must be 96-char hex for SHA3-384")
        if not self._HASH_PATTERN.fullmatch(str(self.merkle_root)):
            validation_errors.append("Invalid merkle_root: must be 96-char hex for SHA3-384")

        # Validate timestamp
        max_time_drift = Constants.TRANSACTION_CONFIRMATIONS.get("maximum_timestamp_drift", 7200)  # Default: 2 hours
        current_time = time.time()
        try:
            ts = float(self.timestamp)
            if not (current_time - max_time_drift <= ts <= current_time + max_time_drift):
                validation_errors.append(
                    f"Invalid timestamp: drift exceeds {max_time_drift // 3600} hours (value: {ts})"
                )
        except (TypeError, ValueError):
            validation_errors.append("Invalid timestamp format: must be numeric")

        # Validate nonce
        if not isinstance(self.nonce, int) or self.nonce < 0:
            validation_errors.append("Invalid nonce: must be a non-negative integer")

        # Validate difficulty
        if not isinstance(self.difficulty, int) or self.difficulty < Constants.MIN_DIFFICULTY:
            validation_errors.append(f"Invalid difficulty: must be >= {Constants.MIN_DIFFICULTY}")

        # Validate miner address
        if not isinstance(self.miner_address, str) or not self.miner_address.strip():
            validation_errors.append("Invalid miner_address: must be a non-empty string")

        if validation_errors:
            raise ValueError("BlockHeader validation failed:\n- " + "\n- ".join(validation_errors))

    def __repr__(self):
        """
        Debug-friendly representation.
        """
        return (
            f"BlockHeader(version={self.version}, index={self.index}, "
            f"previous_hash={self.previous_hash[:10]}..., "
            f"merkle_root={self.merkle_root[:10]}..., nonce={self.nonce}, "
            f"timestamp={self.timestamp}, difficulty={hex(self.difficulty)}, "
            f"miner_address={self.miner_address})"
        )