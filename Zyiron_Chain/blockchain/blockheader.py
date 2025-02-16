import hashlib
import time

class BlockHeader:
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
        self.difficulty = difficulty  # Add this line

    def to_dict(self):
        return {
            "version": self.version,
            "index": self.index,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "difficulty": self.difficulty  # Include difficulty in the dictionary
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
            difficulty=data.get("difficulty", 0)  # Include difficulty
        )

    def calculate_hash(self):
        """
        Calculates the SHA3-384 hash of the block header.
        """
        header_string = (
            f"{self.version}{self.index}{self.previous_hash}{self.merkle_root}{self.timestamp}{self.nonce}"
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
        Validate the integrity of the BlockHeader fields.
        """
        if not isinstance(self.version, int) or self.version <= 0:
            raise ValueError("Invalid version: Must be a positive integer.")
        if not isinstance(self.index, int) or self.index < 0:
            raise ValueError("Invalid index: Must be a non-negative integer.")
        if not isinstance(self.previous_hash, str) or len(self.previous_hash) != 96:
            raise ValueError("Invalid previous_hash: Must be a 96-character string.")
        if not isinstance(self.merkle_root, str) or len(self.merkle_root) != 96:
            raise ValueError("Invalid merkle_root: Must be a 96-character string.")
        if not isinstance(self.timestamp, (int, float)) or self.timestamp <= 0:
            raise ValueError("Invalid timestamp: Must be a positive number.")
        if not isinstance(self.nonce, int) or self.nonce < 0:
            raise ValueError("Invalid nonce: Must be a non-negative integer.")
        if not isinstance(self.difficulty, int) or self.difficulty <= 0:
            raise ValueError("Invalid difficulty: Must be a positive integer.")

    def __repr__(self):
        """
        Returns a string representation of the block header for debugging.
        """
        return (
            f"BlockHeader(version={self.version}, index={self.index}, previous_hash={self.previous_hash[:10]}..., "
            f"merkle_root={self.merkle_root[:10]}..., nonce={self.nonce}, timestamp={self.timestamp}, "
            f"difficulty={hex(self.difficulty)})"
        )