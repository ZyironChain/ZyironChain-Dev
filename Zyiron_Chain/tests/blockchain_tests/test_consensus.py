import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if project_root not in sys.path:
    sys.path.append(project_root)

import unittest
import time
import logging
from decimal import Decimal

# Import necessary components from the blockchain framework
from Zyiron_Chain.blockchain.block_manager import BlockManager
from Zyiron_Chain.blockchain.transaction_manager import TransactionManager
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.blockchain.miner import Miner
from Zyiron_Chain.blockchain.storage_manager import StorageManager
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction, CoinbaseTx
from Zyiron_Chain.blockchain.blockheader import BlockHeader
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
class MinerTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Initialize the test environment:
        - PoC instance
        - Storage Manager (Fixes missing 'poc_instance')
        - Block Manager
        - Transaction Manager (Fixes missing key_manager reference)
        - Miner
        """
        print("\n[SETUP] Initializing Miner Test Environment...\n")

        # ✅ Fix: Initialize PoC
        cls.poc = PoC()

        # ✅ Fix: Pass `poc_instance` to StorageManager
        cls.storage_manager = StorageManager(cls.poc)

        # ✅ Ensure `key_manager` is retrieved correctly
        key_manager = None

        # ✅ Check various locations for `key_manager`
        if hasattr(cls.poc, "key_manager"):
            key_manager = cls.poc.key_manager
        elif hasattr(cls.storage_manager, "key_manager"):
            key_manager = cls.storage_manager.key_manager
        elif hasattr(cls.poc.lmdb_manager, "key_manager"):  # Check in LMDB if needed
            key_manager = cls.poc.lmdb_manager.key_manager
        elif KeyManager:  # ✅ If `KeyManager` exists, initialize it manually
            key_manager = KeyManager()
        else:
            raise AttributeError("[ERROR] `key_manager` is missing and could not be initialized.")

        # ✅ Setup block manager, transaction manager, and miner
        cls.block_manager = BlockManager(cls.storage_manager)
        cls.transaction_manager = TransactionManager(cls.storage_manager, key_manager)  # ✅ Fixed key_manager reference
        cls.miner = Miner(cls.block_manager, cls.transaction_manager, cls.storage_manager)

        # ✅ Ensure Genesis Block exists
        if not cls.block_manager.chain:
            cls.block_manager.create_genesis_block(key_manager)  # ✅ Fixed key_manager reference

    def setUp(self):
        """Reset the blockchain and pending transactions before each test."""
        self.block_manager.chain.clear()
        self.transaction_manager.standard_mempool.clear_mempool()

    def test_01_miner_initialization(self):
        """✅ Test that the miner initializes correctly."""
        self.assertIsInstance(self.miner, Miner, "[ERROR] Miner instance was not created properly.")
        self.assertGreater(self.miner.base_vram, 0, "[ERROR] VRAM allocation is incorrect.")
        self.assertIsNotNone(self.miner.block_manager, "[ERROR] Miner has no block manager assigned.")


    def test_02_dynamic_vram_scaling(self):
        """✅ Test whether VRAM allocation scales dynamically with network hashrate."""
        low_hashrate = 5e12  # Small network
        high_hashrate = 1e14  # Large network

        low_vram = self.miner.get_dynamic_vram(low_hashrate)
        high_vram = self.miner.get_dynamic_vram(high_hashrate)

        self.assertGreater(high_vram, low_vram, "[ERROR] VRAM scaling did not increase with hashrate.")
        self.assertLessEqual(high_vram, self.miner.max_vram, "[ERROR] VRAM exceeded maximum limit.")


    def test_03_mine_block(self):
        """✅ Test that the miner can successfully mine a block."""
        prev_chain_length = len(self.block_manager.chain)
        success = self.miner.mine_block()

        self.assertTrue(success, "[ERROR] Miner failed to mine a block.")
        self.assertEqual(len(self.block_manager.chain), prev_chain_length + 1, "[ERROR] Block was not added to the chain.")


    def test_04_validate_mined_block(self):
        """
        ✅ Test that a mined block is valid and contains correct transactions.
        """
        self.miner.mine_block()
        latest_block = self.block_manager.chain[-1]

        self.assertIsInstance(latest_block, Block, "[ERROR] Latest block is not a valid Block instance.")
        self.assertGreaterEqual(len(latest_block.transactions), 1, "[ERROR] Mined block contains no transactions.")
        self.assertEqual(latest_block.index, len(self.block_manager.chain) - 1, "[ERROR] Block index is incorrect.")

    def test_05_coinbase_transaction(self):
        """
        ✅ Ensure that the coinbase transaction is correctly included in a mined block.
        """
        self.miner.mine_block()
        latest_block = self.block_manager.chain[-1]
        coinbase_tx = latest_block.transactions[0]

        self.assertIsInstance(coinbase_tx, CoinbaseTx, "[ERROR] First transaction is not a valid Coinbase transaction.")
        self.assertGreater(coinbase_tx.outputs[0].amount, 0, "[ERROR] Coinbase transaction has no reward.")

    def test_06_transaction_selection(self):
        """
        ✅ Ensure that transactions are properly selected for mining.
        """
        # Create a few transactions
        tx1 = Transaction(
            tx_id="TX-1",
            inputs=[],
            outputs=[{"script_pub_key": "ADDR-1", "amount": Decimal("5.0")}],
        )
        tx2 = Transaction(
            tx_id="TX-2",
            inputs=[],
            outputs=[{"script_pub_key": "ADDR-2", "amount": Decimal("3.0")}],
        )

        self.transaction_manager.store_transaction_in_mempool(tx1)
        self.transaction_manager.store_transaction_in_mempool(tx2)

        selected_txs = self.transaction_manager.select_transactions_for_block()
        self.assertIn(tx1, selected_txs, "[ERROR] TX-1 was not selected for the block.")
        self.assertIn(tx2, selected_txs, "[ERROR] TX-2 was not selected for the block.")

    def test_07_network_countermeasures(self):
        """
        ✅ Simulate a hashrate spike and ensure countermeasures are activated.
        """
        initial_vram = self.miner.base_vram
        self.miner.previous_hashrate = 50000

        # Simulate a large hashrate increase
        self.miner.check_hashrate_adjustment(60000)

        self.assertGreater(self.miner.base_vram, initial_vram, "[ERROR] VRAM did not increase after hashrate spike.")
        self.assertNotEqual(self.miner.algorithm_version, "v1", "[ERROR] Algorithm rotation did not occur.")

    def test_08_block_difficulty_adjustment(self):
        """
        ✅ Ensure that the block difficulty adjusts correctly based on mining speed.
        """
        self.block_manager.chain.append(
            Block(
                index=1,
                previous_hash="0" * 96,
                transactions=[],
                timestamp=int(time.time() - 1200),  # 20 minutes ago (slow block)
                nonce=0
            )
        )
        self.block_manager.chain.append(
            Block(
                index=2,
                previous_hash="0" * 96,
                transactions=[],
                timestamp=int(time.time() - 300),  # 5 minutes ago (normal block)
                nonce=0
            )
        )

        new_difficulty = self.block_manager._calculate_difficulty()

        self.assertGreater(new_difficulty, 1, "[ERROR] Difficulty did not adjust correctly.")
        self.assertNotEqual(new_difficulty, self.block_manager.chain[-1].header.difficulty, "[ERROR] Difficulty remained unchanged.")

    def test_09_asics_resistant_pow(self):
        """
        ✅ Ensure ASIC-resistant PoW hashing functions as expected.
        """
        last_block = self.block_manager.chain[-1]
        block_header = last_block.header
        target = self.block_manager.calculate_target()

        nonce, mined_hash = self.miner.asic_resistant_pow(block_header, target, self.miner.previous_hashrate)

        self.assertIsInstance(nonce, int, "[ERROR] Nonce is not an integer.")
        self.assertIsInstance(mined_hash, str, "[ERROR] Hash is not a string.")
        self.assertTrue(mined_hash.startswith('0000'), "[ERROR] Mined hash does not meet difficulty target.")

    def test_10_mining_loop(self):
        """
        ✅ Test that the mining loop can successfully mine multiple blocks.
        """
        initial_blocks = len(self.block_manager.chain)

        for _ in range(3):
            self.miner.mine_block()

        self.assertEqual(len(self.block_manager.chain), initial_blocks + 3, "[ERROR] Mining loop did not mine the expected number of blocks.")

    @classmethod
    def tearDownClass(cls):
        """Clean up the test environment after all tests run."""
        print("\n[TEARDOWN] Cleaning up Miner Test Environment...")
        cls.block_manager.chain.clear()

if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
