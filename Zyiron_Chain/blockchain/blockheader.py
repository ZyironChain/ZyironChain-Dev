import hashlib
from re import Pattern
import re
import time

import re
import hashlib
import time
from Zyiron_Chain.blockchain.constants import Constants  # ✅ Import latest constants

class BlockHeader:
    _HASH_PATTERN: re.Pattern = re.compile(r'^[a-fA-F0-9]{96}$')  # ✅ Ensures SHA3-384 96-character hex

    def __init__(self, version, index, previous_hash, merkle_root, timestamp, nonce, difficulty):
        """
        Initialize a BlockHeader.
        :param version: The block version (from Constants).
        :param index: The block index.
        :param previous_hash: The hash of the previous block.
        :param merkle_root: The Merkle root of the transactions.
        :param timestamp: The block creation timestamp.
        :param nonce: The nonce used for mining.
        :param difficulty: The mining difficulty.
        """
        self.version = Constants.VERSION  # ✅ Always set to current blockchain version
        self.index = index
        self.previous_hash = previous_hash
        self.merkle_root = merkle_root

        # ✅ Enforce proper timestamp validation
        self.timestamp = int(timestamp if timestamp else time.time())

        # ✅ Ensure difficulty is within predefined limits
        self.difficulty = self._adjust_difficulty(difficulty)

        self.nonce = nonce

    def _adjust_difficulty(self, difficulty):
        """Ensure difficulty is within predefined min/max from Constants."""
        return max(min(difficulty, Constants.MAX_DIFFICULTY), Constants.MIN_DIFFICULTY)

    def to_dict(self):
        """Convert BlockHeader into a dictionary."""
        return {
            "version": self.version,
            "index": self.index,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "difficulty": self.difficulty
        }

    @classmethod
    def from_dict(cls, data):
        """
        Create a BlockHeader instance from a dictionary.
        :param data: Dictionary representation of a block header.
        :return: BlockHeader instance.
        """
        return cls(
            version=data.get("version", Constants.VERSION),  # ✅ Fallback to latest version
            index=data["index"],
            previous_hash=data["previous_hash"],
            merkle_root=data["merkle_root"],
            timestamp=data["timestamp"],
            nonce=data["nonce"],
            difficulty=data.get("difficulty", Constants.GENESIS_TARGET)  # ✅ Ensure difficulty exists
        )

    def calculate_hash(self):
        """
        Calculates the SHA3-384 hash of the block header.
        """
        header_string = (
            f"{self.version}{self.index}{self.previous_hash}"
            f"{self.merkle_root}{self.timestamp}{self.nonce}{self.difficulty}"
        )
        return hashlib.sha3_384(header_string.encode()).hexdigest()

    @property
    def hash_block(self):
        """
        Returns the hash of the block header.
        """
        return self.calculate_hash()

    def validate(self):
        """
        Comprehensive header validation with precise checks
        """
        validation_errors = []
        
        # ✅ Validate version
        if not isinstance(self.version, str) or self.version != Constants.VERSION:
            validation_errors.append(f"Invalid version: Must match Constants.VERSION ({Constants.VERSION})")

        # ✅ Validate index
        if not isinstance(self.index, int) or self.index < 0:
            validation_errors.append("Invalid index: Must be non-negative integer")
        
        # ✅ Validate hashes using class-level pattern
        if not self._HASH_PATTERN.fullmatch(str(self.previous_hash)):
            validation_errors.append("Invalid previous_hash: 96-character hex required")
        if not self._HASH_PATTERN.fullmatch(str(self.merkle_root)):
            validation_errors.append("Invalid merkle_root: 96-character hex required")
        
        # ✅ Validate timestamp
        max_time_drift = Constants.CONFIRMATION_RULES["maximum_timestamp_drift"]  # ✅ Dynamic max drift
        current_time = time.time()
        try:
            ts = float(self.timestamp)
            if not (current_time - max_time_drift <= ts <= current_time + max_time_drift):
                validation_errors.append(f"Invalid timestamp: Drift exceeds {max_time_drift // 3600} hours (value: {ts})")
        except (TypeError, ValueError):
            validation_errors.append("Invalid timestamp format: Must be numeric")
        
        # ✅ Validate mining parameters
        if not isinstance(self.nonce, int) or self.nonce < 0:
            validation_errors.append("Invalid nonce: Must be non-negative integer")
        if not isinstance(self.difficulty, int) or self.difficulty < Constants.MIN_DIFFICULTY:
            validation_errors.append(f"Invalid difficulty: Must be ≥ {Constants.MIN_DIFFICULTY}")

        if validation_errors:
            raise ValueError("BlockHeader validation failed:\n- " + "\n- ".join(validation_errors))

    def __repr__(self):
        """
        Debug-friendly representation
        """
        return (
            f"BlockHeader(version={self.version}, index={self.index}, "
            f"previous_hash={self.previous_hash[:10]}..., "
            f"merkle_root={self.merkle_root[:10]}..., nonce={self.nonce}, "
            f"timestamp={self.timestamp}, difficulty={hex(self.difficulty)})"
        )
