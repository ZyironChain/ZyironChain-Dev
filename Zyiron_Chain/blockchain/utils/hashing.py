import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)




import hashlib

def sha3_384_hash(data: str) -> str:
    """Standardized SHA3-384 hashing function"""
    return hashlib.sha3_384(data.encode()).hexdigest()

def validate_hash(hash_str: str) -> bool:
    """Validate SHA3-384 hash format"""
    return len(hash_str) == 96 and all(c in '0123456789abcdef' for c in hash_str)

def hash_transaction(tx_data: dict) -> str:
    """Hash transaction data with SHA3-384"""
    serialized = "".join(f"{k}{v}" for k, v in sorted(tx_data.items()))
    return sha3_384_hash(serialized)
