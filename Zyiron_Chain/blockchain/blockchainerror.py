
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))



import time 
from Zyiron_Chain.blockchain.constants import Constants
import json 









class BlockchainInitError(Exception):
    """Specialized error for initialization failures"""
    def __init__(self, message, original=None):
        super().__init__(message)
        self.original_error = original
        self.timestamp = time.time()
        self.context = {
            'network': Constants.NETWORK,
            'blockchain_version': Constants.VERSION
        }

    def __str__(self):
        return (f"{super().__str__()}\n"
                f"Original Error: {self.original_error}\n"
                f"Failure Context: {json.dumps(self.context)}")