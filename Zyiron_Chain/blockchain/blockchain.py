import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
from Zyiron_Chain.blockchain.block_manager import BlockManager
from Zyiron_Chain.blockchain.transaction_manager import TransactionManager
from Zyiron_Chain.blockchain.storage_manager import StorageManager
from Zyiron_Chain.blockchain.miner import Miner
from Zyiron_Chain.database.poc import PoC
import hashlib
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
        self.fee_model = FeeModel(max_supply=Decimal('84096000'), base_fee_rate=Decimal('0.00015'))

        self.allocator = FundsAllocator()
        self.tx_service = TransactionService(self.fee_model, self.allocator)
        self.pending_transactions = []
        self.chain = []
        self.ZERO_HASH = '0' * 96
        self.current_block_size = 1  # MB
        self.block_size_adjustment_interval = 288

        # New monetary policy parameters
        self.initial_reward = Decimal('100.00')
        self.halving_interval = 420480  # 4 years in 5-min blocks (4*365*24*12)
        self.max_supply = Decimal('84096000')
        self.total_issued = Decimal('0')
        self.block_time_target = 300  # 5 minutes in seconds

        # Anti-Farm PoW Adjustments
        self.vram_scaling = 8  # Starts at 8MB, increases dynamically
        self.algorithm_rotation_interval = 24  # Rotates every 24 blocks minimum
        self.difficulty_check_interval = 24  # Recalculates every 24 blocks
        self.last_hashrate_check = time.time()  # For 2-hour monitoring



    def _detect_hashrate_spike(self):
        """Check for hashrate spikes every 2 hours."""
        if time.time() - self.last_hashrate_check >= 7200:  # Every 2 hours
            self.last_hashrate_check = time.time()
            previous_difficulty = self.chain[-self.difficulty_check_interval]['header']['difficulty']
            current_difficulty = self.chain[-1]['header']['difficulty']

            # Percentage change in hashrate
            hashrate_change = ((current_difficulty - previous_difficulty) / previous_difficulty) * 100
            return hashrate_change

        return 0


    def _calculate_block_reward(self):
        """Calculate current block reward with halving."""
        blocks = len(self.chain)
        halvings = blocks // self.halving_interval
        reward = self.initial_reward / (2 ** halvings)

        # Cap at remaining supply
        remaining = self.max_supply - self.total_issued
        return min(reward, remaining) if remaining > 0 else Decimal('0')


    def _create_coinbase(self, miner_address: str, fees: Decimal):
        """Create coinbase transaction with protocol rules."""
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
        """Adjust difficulty dynamically to maintain 5-minute block times while preventing extreme fluctuations."""
        if len(self.chain) == 0:
            return 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # 4 Leading Zeros

        if len(self.chain) < self.difficulty_check_interval:
            return self.chain[-1]['header']['difficulty'] if self.chain else 1

        # Calculate actual time for the last difficulty interval
        actual_time = self.chain[-1]['header']['timestamp'] - self.chain[-self.difficulty_check_interval]['header']['timestamp']
        target_time = self.difficulty_check_interval * self.block_time_target

        # Adjust difficulty proportionally with clamping to prevent drastic changes
        ratio = actual_time / target_time
        new_difficulty = int(self.chain[-1]['header']['difficulty'] * max(0.75, min(1.25, ratio)))

        return max(new_difficulty, 1)  # Ensure difficulty is never below 1



    def create_block(self, miner_address: str):
        """Create a new block with Anti-Farm PoW logic, dynamic VRAM scaling, and adaptive block sizes."""
        
        # ✅ Dynamically adjust block size based on network congestion
        self._calculate_block_size()

        # ✅ Calculate total transaction fees
        total_fees = sum(tx['fee'] for tx in self.pending_transactions)

        # ✅ Create coinbase transaction
        coinbase_tx = self._create_coinbase(miner_address, Decimal(total_fees))

        # ✅ Dynamic Block Size Allocation
        max_block_bytes = self.current_block_size * 1024 * 1024  # Converts MB to bytes
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

        # ✅ Anti-Farm PoW Adjustments (Detect Hashrate Spikes & Adjust VRAM + Algorithm)
        hashrate_change = self._detect_hashrate_spike()

        if hashrate_change >= 10:
            self.vram_scaling = min(192, self.vram_scaling * 1.5)  # Increase VRAM Scaling (Max: 192MB)
            self.algorithm_rotation_interval = 24  # Rotate algorithm immediately

        elif 5 <= hashrate_change < 10:
            self.vram_scaling = min(192, self.vram_scaling * 1.2)  # Moderate VRAM scaling increase
            self.algorithm_rotation_interval = 50  # Algorithm rotation slowed down

        # ✅ Assemble Block
        block = {
            "header": {
                "version": 3,
                "prev_hash": self.chain[-1]['header']['hash'] if self.chain else self.ZERO_HASH,
                "merkle_root": self._calculate_merkle_root([coinbase_tx] + selected_transactions),
                "timestamp": int(time.time()),
                "difficulty": self._calculate_difficulty(),
                "nonce": 0,
                "block_size": self.current_block_size,  # ✅ Now dynamic (1MB-10MB)
                "vram_usage": self.vram_scaling,  # ✅ Tracks current VRAM usage
                "reward": float(self._calculate_block_reward())
            },
            "transactions": [coinbase_tx] + selected_transactions,
            "hash": None
        }

        # ✅ Mining Logic (Anti-Farm PoW Mining)
        while True:
            block_data = f"{block['header']}{block['transactions']}"
            block_hash = hashlib.sha3_384(block_data.encode()).hexdigest()

            if block_hash.startswith('0' * self.chain[-1]['header']['difficulty']):  # ✅ Dynamic difficulty targeting
                block["hash"] = block_hash
                break

            block['header']['nonce'] += 1  # Increment nonce for PoW

        # ✅ Append Block to Chain
        self.chain.append(block)

        # ✅ Recalculate Block Size & Difficulty After Each Block
        self._calculate_block_size()
        self._calculate_difficulty()

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


    def _calculate_block_size(self):
        """
        Dynamically adjust block size based on network congestion.
        Block sizes scale linearly from 1MB to 10MB based on transaction count.
        """
        # Measure pending transactions
        pending_tx_count = len(self.pending_transactions)
        
        # Define thresholds based on TPS analysis
        min_tx = 1000     # Minimum transactions for 1MB block
        max_tx = 50000    # Maximum transactions for 10MB block
        min_size = 1.0    # Minimum block size (MB)
        max_size = 10.0   # Maximum block size (MB)
        
        # Ensure linear scaling of block size
        if pending_tx_count <= min_tx:
            new_block_size = min_size
        elif pending_tx_count >= max_tx:
            new_block_size = max_size
        else:
            new_block_size = min_size + ((max_size - min_size) * ((pending_tx_count - min_tx) / (max_tx - min_tx)))
        
        # Ensure block size stays within valid limits
        self.current_block_size = max(min_size, min(new_block_size, max_size))
        
        print(f"[INFO] Block size adjusted to {self.current_block_size:.2f}MB based on {pending_tx_count} transactions.")
