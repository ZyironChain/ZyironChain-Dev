import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)





import hashlib


def sha3_384(s):
    """Two rounds of SHA3-384"""
    return hashlib.sha3_384(hashlib.sha3_384(s).digest()).digest()

