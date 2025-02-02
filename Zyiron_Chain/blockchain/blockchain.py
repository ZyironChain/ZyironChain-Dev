import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
from Zyiron_Chain.blockchain.block_manager import BlockManager
from Zyiron_Chain.blockchain.transaction_manager import TransactionManager
from Zyiron_Chain.blockchain.storage_manager import StorageManager
from Zyiron_Chain.blockchain.miner import Miner
from Zyiron_Chain.database.poc import PoC

from decimal import Decimal
import time
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx, TransactionFactory, sha3_384_hash
from Zyiron_Chain.transactions.transaction_services import TransactionService
from Zyiron_Chain.transactions.fees import FeeModel, FundsAllocator

class Blockchain:
    def __init__(self):
        self.fee_model = FeeModel(base_fee_rate=Decimal('0.00015'))
        self.allocator = FundsAllocator()
        self.tx_service = TransactionService(self.fee_model, self.allocator)
        self.pending_transactions = []
        self.chain = []
        self.ZERO_HASH = '0' * 96  # 384-bit zero hash for SHA3-384
        self.current_block_size = 1  # MB - starting size
        self.block_size_adjustment_interval = 2016  # Similar to Bitcoin's difficulty adjustment



    def _calculate_block_size(self):
        """Dynamic block size adjustment based on network conditions"""
        # Get recent block fill rates
        last_blocks = self.chain[-self.block_size_adjustment_interval:]
        fill_rate = sum(b['size']/(b['max_size']*1024*1024) for b in last_blocks) / len(last_blocks)

        # Adjust size based on fill rate (simple example)
        if fill_rate > 0.9:  # Blocks are 90%+ full
            self.current_block_size = min(10, self.current_block_size * 1.1)
        elif fill_rate < 0.7:  # Blocks under 70% full
            self.current_block_size = max(1, self.current_block_size * 0.9)



    def _calculate_merkle_root(self, transactions: list) -> str:
        """SHA3-384-based Merkle root calculation"""
        hashes = [tx.hash for tx in transactions]
        while len(hashes) > 1:
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + (hashes[i+1] if i+1 < len(hashes) else hashes[i])
                new_hashes.append(sha3_384_hash(combined))
            hashes = new_hashes
        return hashes[0] if hashes else self.ZERO_HASH

    def create_block(self, miner_address: str):
        # Convert MB to bytes
        max_block_bytes = self.current_block_size * 1024 * 1024
        current_block_size = 0
        selected_transactions = []

        # Select transactions that fit
        for tx in list(self.pending_transactions):
            tx_size = self._calculate_transaction_size(tx)
            if current_block_size + tx_size <= max_block_bytes:
                selected_transactions.append(tx)
                current_block_size += tx_size
                self.pending_transactions.remove(tx)
            else:
                break

        # Create block with selected transactions
        block = self._assemble_block(selected_transactions, miner_address)
        self._calculate_block_size()  # Adjust for next block
        return block

    def _assemble_block(self, transactions, miner_address):
        block = {
            "header": {
                "version": 2,
                "max_size": self.current_block_size,  # MB
                "actual_size": 0,  # Will be calculated
                # ... other header fields
            },
            "transactions": [],
            "hash": None
        }

        # Add transactions and calculate actual size
        total_size = 0
        for tx in transactions:
            tx_size = self._calculate_transaction_size(tx)
            if total_size + tx_size <= block['header']['max_size'] * 1024 * 1024:
                block['transactions'].append(tx)
                total_size += tx_size
        block['header']['actual_size'] = total_size

        # Add coinbase transaction
        coinbase_tx = self._create_coinbase(miner_address)
        block['transactions'].insert(0, coinbase_tx)
        
        return block