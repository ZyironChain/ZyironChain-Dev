import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))



# helper.py
import importlib

def get_poc():
    """Lazy import PoC using importlib to avoid circular imports."""
    module = importlib.import_module("Zyiron_Chain.database.poc")
    return getattr(module, "PoC")

def get_block():
    """Lazy import Block using importlib to avoid circular imports."""
    module = importlib.import_module("Zyiron_Chain.blockchain.block")
    return getattr(module, "Block")

def get_transaction():
    """Lazy import Transaction using importlib to avoid circular imports."""
    module = importlib.import_module("Zyiron_Chain.transactions.Blockchain_transaction")
    return getattr(module, "Transaction")

def get_coinbase_tx():
    """Lazy import CoinbaseTx using importlib to avoid circular imports."""
    module = importlib.import_module("Zyiron_Chain.transactions.Blockchain_transaction")
    return getattr(module, "CoinbaseTx")

def get_block_header():
    """Lazy import BlockHeader using importlib to avoid circular imports."""
    module = importlib.import_module("Zyiron_Chain.blockchain.blockheader")
    return getattr(module, "BlockHeader")


def get_fee_model():
    """Lazy import FeeModel to break circular dependencies."""
    module = importlib.import_module("Zyiron_Chain.transactions.fees")
    return getattr(module, "FeeModel")
