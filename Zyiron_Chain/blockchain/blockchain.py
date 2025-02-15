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
from Zyiron_Chain.blockchain.block import Block
from decimal import Decimal
import time

class Blockchain:
    def __init__(self, storage_manager, transaction_manager, block_manager, key_manager):
        """
        Initialize the blockchain.
        - Ensures the Genesis block exists at startup.
        - Manages block storage, difficulty adjustment, and block rewards.
        - Manages key handling via key_manager.
        """
        self.storage_manager = storage_manager
        self.transaction_manager = transaction_manager
        self.block_manager = block_manager
        self.key_manager = key_manager  # Add this line to store key_manager
        self.fee_model = FeeModel(max_supply=Decimal('84096000'), base_fee_rate=Decimal('0.00015'))

        self.chain = []
        self.ZERO_HASH = '0' * 96
        self.current_block_size = 1  # MB
        self.block_size_adjustment_interval = 288

        self.initial_reward = Decimal('100.00')
        self.halving_interval = 420480  # 4 years in 5-min blocks
        self.max_supply = Decimal('84096000')
        self.total_issued = Decimal('0')
        self.block_time_target = 300  # 5 minutes

        # Ensure the Genesis block exists
        self._ensure_genesis_block()

        # Initialize the Miner (pass key_manager)
        self.miner = Miner(self.block_manager, self.transaction_manager, self.storage_manager, self.key_manager)


    def _ensure_genesis_block(self):
        """
        Ensure the Genesis block exists in the blockchain.
        - Tries to load the last stored block from UnQLite.
        - If no block is found, mines a new Genesis block.
        """
        print("[INFO] Checking for stored blockchain data...")

        try:
            # ✅ FIX: Use the correct function from PoC instead of `get_all_blocks()`
            stored_genesis = self.storage_manager.poc.get_block("block:0")

            if stored_genesis:
                print("[INFO] Loaded stored Genesis block from UnQLite.")
                last_block = Block.from_dict(stored_genesis)
                self.chain.append(last_block)
                self.block_manager.chain.append(last_block)
                return

        except AttributeError as e:
            print(f"[ERROR] UnQLite Retrieval Issue: {e}")
        
        print("[INFO] No stored blockchain data found. Auto-mining Genesis block...")
        
        genesis_block = self._create_genesis_block()

        print(f"[DEBUG] Genesis Block Difficulty Before Storing: {hex(genesis_block.header.difficulty)}")

        self.chain.append(genesis_block)
        self.block_manager.chain.append(genesis_block)

        # ✅ FIX: Use the correct function to store a block
        self.storage_manager.store_block(genesis_block, genesis_block.header.difficulty)

        print("[SUCCESS] Genesis block auto-mined and stored!")










    def _calculate_block_reward(self):
        """Calculate current block reward with halving."""
        blocks = len(self.chain)
        halvings = blocks // self.halving_interval
        reward = self.initial_reward / (2 ** halvings)

        # Cap at remaining supply
        remaining = self.max_supply - self.total_issued
        return min(reward, remaining) if remaining > 0 else Decimal('0')


    def _create_coinbase(self, miner_address: str, fees: Decimal):
        """
        Create coinbase transaction with protocol rules.
        Fetch the miner address from the KeyManager based on the network and role.
        """
        # Fetch the miner's public key from KeyManager
        miner_address = self.key_manager.get_default_public_key("mainnet", "miner")  # Assuming 'mainnet' and 'miner' roles

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





    def add_block(self, new_block):
        """
        Add a mined block to the blockchain.
        - Stores the block in memory.
        - Saves it to persistent storage.
        - Ensures correct difficulty recalculation.
        """
        print(f"[INFO] Adding Block #{new_block.index} to blockchain...")

        # ✅ Append to in-memory chain
        self.chain.append(new_block)

        # ✅ Store Block in UnQLite
        self.storage_manager.store_block(new_block, difficulty=new_block.header.difficulty)

        # ✅ Save Blockchain State
        self.storage_manager.save_blockchain_state(self.chain, [])

        print(f"[SUCCESS] Block #{new_block.index} added successfully!")



    def create_block(self):
        """
        Delegate mining to the Miner class and create a new block.
        """
        # The miner mines a block and returns it
        return self.miner.mine_block(network="mainnet")






    def _create_genesis_block(self):
        """
        Creates the Genesis block with an all-zero previous hash.
        - Uses SHA3-384 hashing.
        - Ensures correct difficulty initialization.
        """
        print("[INFO] Creating Genesis Block...")

        coinbase_tx = CoinbaseTx(
            block_height=0,
            miner_address="genesis",
            reward=self.initial_reward
        )

        genesis_block = Block(
            index=0,
            previous_hash="0" * 96,  # ✅ Ensures All-Zero Previous Hash
            transactions=[coinbase_tx],
            timestamp=int(time.time()),
            nonce=0
        )

        # ✅ Lower Genesis Difficulty
        genesis_difficulty = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        genesis_block.header.difficulty = genesis_difficulty  
        genesis_block.hash = genesis_block.calculate_hash()

        print(f"[SUCCESS] Genesis block created with Difficulty: {hex(genesis_block.header.difficulty)}")

        return genesis_block

    def _adjust_difficulty(self, block_height):
        """
        Adjust difficulty every `difficulty_adjustment_interval` blocks based on the mining time.
        """
        if block_height % self.difficulty_adjustment_interval == 0:
            # Check average mining time
            avg_mining_time = self.average_block_time / self.difficulty_adjustment_interval
            print(f"[DEBUG] Average Mining Time for last {self.difficulty_adjustment_interval} blocks: {avg_mining_time:.2f}s")

            if avg_mining_time > self.block_time_target:
                # If mining is too slow, decrease difficulty (more blocks should be mined in less time)
                print("[INFO] Mining too slow, lowering difficulty.")
                self._lower_difficulty()
            elif avg_mining_time < self.block_time_target:
                # If mining is too fast, increase difficulty
                print("[INFO] Mining too fast, increasing difficulty.")
                self._increase_difficulty()

            # Reset the mining time tracker
            self.average_block_time = 0

    def _lower_difficulty(self):
        """Lower the mining difficulty."""
        current_difficulty = self.block_manager.calculate_target()
        new_difficulty = current_difficulty * 2  # Make it easier to mine
        self.block_manager.difficulty_target = new_difficulty
        print(f"[INFO] New Difficulty (lowered): {hex(new_difficulty)}")

    def _increase_difficulty(self):
        """Increase the mining difficulty."""
        current_difficulty = self.block_manager.calculate_target()
        new_difficulty = current_difficulty // 2  # Make it harder to mine
        self.block_manager.difficulty_target = new_difficulty
        print(f"[INFO] New Difficulty (increased): {hex(new_difficulty)}")
    def _calculate_block_size(self):
        """
        Dynamically adjust block size based on the number of pending transactions.
        Block sizes scale linearly from 1MB to 10MB based on transaction count.
        """
        pending_tx_count = len(self.transaction_manager.mempool)

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


if __name__ == "__main__":
    import time
    from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
    from Zyiron_Chain.blockchain.blockchain import Blockchain
    from Zyiron_Chain.blockchain.miner import Miner
    from Zyiron_Chain.blockchain.storage_manager import StorageManager
    from Zyiron_Chain.blockchain.transaction_manager import TransactionManager
    from Zyiron_Chain.blockchain.block_manager import BlockManager
    from Zyiron_Chain.database.poc import PoC

    # Initialize PoC instance
    poc_instance = PoC()

    # Initialize KeyManager
    key_manager = KeyManager()

    # Initialize StorageManager with PoC instance
    storage_manager = StorageManager(poc_instance)

    # Initialize TransactionManager
    transaction_manager = TransactionManager(storage_manager, key_manager, poc_instance)

    # Initialize BlockManager
    block_manager = BlockManager(storage_manager, transaction_manager)

    # Initialize Blockchain with KeyManager passed to Miner
    blockchain = Blockchain(storage_manager, transaction_manager, block_manager, key_manager)

    # Initialize Miner with KeyManager passed
    miner = Miner(block_manager, transaction_manager, storage_manager, key_manager)

    # Start the mining process
    miner.mine_block(network="mainnet")
