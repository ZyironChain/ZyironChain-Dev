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

from decimal import Decimal
import time

class Blockchain:
    def __init__(self):
        # Existing initialization
        self.fee_model = FeeModel(base_fee_rate=Decimal('0.00015'))
        self.allocator = FundsAllocator()
        self.tx_service = TransactionService(self.fee_model, self.allocator)
        self.pending_transactions = []
        self.chain = []
        self.ZERO_HASH = '0' * 96
        self.current_block_size = 1  # MB
        self.block_size_adjustment_interval = 2016
        
        # New monetary policy parameters
        self.initial_reward = Decimal('100.00')
        self.halving_interval = 420480  # 4 years in 5-min blocks (4*365*24*12)
        self.max_supply = Decimal('84096000')
        self.total_issued = Decimal('0')
        self.block_time_target = 300  # 5 minutes in seconds

    def _calculate_block_reward(self):
        """Calculate current block reward with halving"""
        blocks = len(self.chain)
        halvings = blocks // self.halving_interval
        reward = self.initial_reward / (2 ** halvings)
        
        # Cap at remaining supply
        remaining = self.max_supply - self.total_issued
        return min(reward, remaining) if remaining > 0 else Decimal('0')

    def _create_coinbase(self, miner_address: str, fees: Decimal):
        """Create coinbase transaction with protocol rules"""
        block_reward = self._calculate_block_reward()
        total_reward = block_reward + fees
        
        # Update total issued supply
        self.total_issued += block_reward
        
        return {
            "version": 1,
            "inputs": [],
            "outputs": [{
                "address": miner_address,
                "amount": float(total_reward),
                "script_pub_key": f"COINBASE-{len(self.chain)}"
            }],
            "locktime": 0
        }

    def _calculate_difficulty(self):
        """Adjust difficulty to maintain 5-minute block times"""
        if len(self.chain) % 2016 != 0 or len(self.chain) == 0:
            return self.chain[-1]['header']['difficulty'] if self.chain else 1
        
        # Calculate actual time for last 2016 blocks
        actual_time = self.chain[-1]['header']['timestamp'] - self.chain[-2016]['header']['timestamp']
        target_time = 2016 * self.block_time_target
        
        # Adjust difficulty
        ratio = actual_time / target_time
        new_diff = self.chain[-1]['header']['difficulty'] * ratio
        return max(new_diff, 1)

    def create_block(self, miner_address: str):
        # Calculate total fees first
        total_fees = sum(tx['fee'] for tx in self.pending_transactions)
        
        # Create coinbase transaction
        coinbase_tx = self._create_coinbase(miner_address, Decimal(total_fees))
        
        # Select transactions (existing logic)
        max_block_bytes = self.current_block_size * 1024 * 1024
        current_block_size = 0
        selected_transactions = []
        
        for tx in list(self.pending_transactions):
            tx_size = self._calculate_transaction_size(tx)
            if current_block_size + tx_size <= max_block_bytes:
                selected_transactions.append(tx)
                current_block_size += tx_size
                self.pending_transactions.remove(tx)
            else:
                break

        # Assemble block with new header fields
        block = {
            "header": {
                "version": 3,
                "prev_hash": self.chain[-1]['header']['hash'] if self.chain else self.ZERO_HASH,
                "merkle_root": self._calculate_merkle_root([coinbase_tx] + selected_transactions),
                "timestamp": int(time.time()),
                "difficulty": self._calculate_difficulty(),
                "nonce": 0,
                "block_size": self.current_block_size,
                "reward": float(self._calculate_block_reward())
            },
            "transactions": [coinbase_tx] + selected_transactions,
            "hash": None
        }

        # Mine block (existing logic)
        while True:
            block_data = f"{block['header']}{block['transactions']}"
            block_hash = sha3_384_hash(block_data)
            if block_hash.startswith('0' * self.current_difficulty()):
                block["hash"] = block_hash
                break
            block['header']['nonce'] += 1

        self.chain.append(block)
        self._calculate_block_size()  # Existing size adjustment
        return block

    def _create_genesis_block(self):
        """Initialize genesis block with special rules"""
        genesis = {
            "header": {
                "version": 1,
                "prev_hash": self.ZERO_HASH,
                "merkle_root": sha3_384_hash("genesis"),
                "timestamp": int(time.time()),
                "difficulty": 1,
                "nonce": 0,
                "block_size": 1,
                "reward": float(self.initial_reward)
            },
            "transactions": [self._create_coinbase(
                miner_address="genesis",
                fees=Decimal('0')
            )],
            "hash": None
        }
        genesis['header']['hash'] = self._calculate_block_hash(genesis)
        self.chain.append(genesis)
        self.total_issued += self.initial_reward