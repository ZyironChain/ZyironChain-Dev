import hashlib
from re import Pattern
import re
import time

class BlockHeader:
    _HASH_PATTERN: Pattern[str] = re.compile(r'^[a-fA-F0-9]{96}$')  # Class-level compiled pattern

    def __init__(self, version, index, previous_hash, merkle_root, timestamp, nonce, difficulty):
        """
        Initialize a BlockHeader.
        :param version: The block version.
        :param index: The block index.
        :param previous_hash: The hash of the previous block.
        :param merkle_root: The Merkle root of the transactions.
        :param timestamp: The block creation timestamp.
        :param nonce: The nonce used for mining.
        :param difficulty: The mining difficulty.
        """
        self.version = version
        self.index = index
        self.previous_hash = previous_hash
        self.merkle_root = merkle_root
        self.timestamp = timestamp
        self.nonce = nonce
        self.difficulty = difficulty

    def to_dict(self):
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
            version=data["version"],
            index=data["index"],
            previous_hash=data["previous_hash"],
            merkle_root=data["merkle_root"],
            timestamp=data["timestamp"],
            nonce=data["nonce"],
            difficulty=data.get("difficulty", 0)
        )

    def calculate_hash(self):
        """
        Calculates the SHA3-384 hash of the block header.
        """
        header_string = (
            f"{self.version}{self.index}{self.previous_hash}"
            f"{self.merkle_root}{self.timestamp}{self.nonce}"
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
        
        # Validate version
        if not isinstance(self.version, int) or self.version != 1:
            validation_errors.append("Invalid version: Must be integer 1")
        
        # Validate index
        if not isinstance(self.index, int) or self.index < 0:
            validation_errors.append("Invalid index: Must be non-negative integer")
        
        # Validate hashes using class-level pattern
        if not self._HASH_PATTERN.fullmatch(str(self.previous_hash)):
            validation_errors.append("Invalid previous_hash: 96-character hex required")
        if not self._HASH_PATTERN.fullmatch(str(self.merkle_root)):
            validation_errors.append("Invalid merkle_root: 96-character hex required")
        
        # Validate timestamp
        max_time_drift = 7200  # 2 hours
        current_time = time.time()
        try:
            ts = float(self.timestamp)
            if not (current_time - max_time_drift <= ts <= current_time + max_time_drift):
                validation_errors.append(f"Invalid timestamp: Drift exceeds 2 hours (value: {ts})")
        except (TypeError, ValueError):
            validation_errors.append("Invalid timestamp format: Must be numeric")
        
        # Validate mining parameters
        if not isinstance(self.nonce, int) or self.nonce < 0:
            validation_errors.append("Invalid nonce: Must be non-negative integer")
        if not isinstance(self.difficulty, int) or self.difficulty <= 0:
            validation_errors.append("Invalid difficulty: Must be positive integer")
        
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