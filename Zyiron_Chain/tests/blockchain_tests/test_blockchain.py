import sys
import os
import unittest
import time
import hashlib
import random
import numpy as np
from decimal import Decimal

# Add the project root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

# Import blockchain modules
from Zyiron_Chain.blockchain. block import Block
from Zyiron_Chain.blockchain.blockheader import BlockHeader
from Zyiron_Chain.blockchain. miner import Miner
from Zyiron_Chain. transactions.Blockchain_transaction import Transaction, TransactionIn, TransactionOut, CoinbaseTx
from Zyiron_Chain. transactions.transactiontype import PaymentTypeManager
from Zyiron_Chain. transactions.fees import FeeModel
from Zyiron_Chain. transactions.txout import TransactionOut
from Zyiron_Chain. transactions.utxo_manager import UTXOManager
from Zyiron_Chain. database.poc import PoC
from Zyiron_Chain. database.unqlitedatabase import BlockchainUnqliteDB
from Zyiron_Chain. database.sqlitedatabase import SQLiteDB
from Zyiron_Chain. database.duckdatabase import AnalyticsNetworkDB
from Zyiron_Chain. database.lmdatabase import LMDBManager
from Zyiron_Chain. database.tinydatabase import TinyDBManager
from Zyiron_Chain. offchain.instantpay import PaymentChannel
from Zyiron_Chain. offchain.multihop import MultiHop
from Zyiron_Chain. offchain.dispute import DisputeResolutionContract
from Zyiron_Chain. blockchain.utils.standardmempool import StandardMempool
from Zyiron_Chain. smartpay.smartmempool import SmartMempool
import logging

logging.basicConfig(level=logging.INFO)
import unittest
import time
from decimal import Decimal
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.blockchain.block_manager import BlockManager
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction, CoinbaseTx, TransactionIn, TransactionOut
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.blockchain.miner import Miner
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.blockchain.utils.standardmempool import StandardMempool
from Zyiron_Chain.smartpay.smartmempool import SmartMempool

class BlockchainTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize complete blockchain ecosystem with anti-farm measures"""
        print("\n[SETUP] Building Full Blockchain Test Environment...\n")
        
        cls.poc = PoC()
        cls.fee_model = FeeModel(max_supply=Decimal('84096000'))
        cls.allocator = FundsAllocator(cls.fee_model.max_supply)
        
        # ✅ Cold Start Protocol
        if not cls.poc.get_last_block():
            genesis = Block(
                index=0,
                previous_hash="0" * 96,
                transactions=[CoinbaseTx(block_height=0, miner_address="genesis")],
                timestamp=int(time.time())
            )
            genesis.calculate_hash()
            cls.poc.store_block(genesis, difficulty=0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF)
        
        # 🛡️ Initialize Anti-Farm Components
        cls.miner = Miner(cls.poc.block_manager, cls.poc.transaction_manager, cls.poc.storage_manager)
        cls.miner.base_vram = 8 * 1024 * 1024  # Reset to base VRAM

    def setUp(self):
        """Fresh environment for each test"""
        self.poc.clear_blockchain()
        self.standard_mempool = StandardMempool()
        self.smart_mempool = SmartMempool()

    # --------------------- Core Blockchain Tests ---------------------
    def test_01_block_validation(self):
        """Test full block lifecycle from creation to chain inclusion"""
        print("\n[TEST] Comprehensive Block Validation Test...")
        
        # 🧪 Test 1: Valid Block
        valid_block = self.create_valid_block()
        self.assertTrue(valid_block.validate_transactions(self.fee_model, self.standard_mempool, 1),
                       "Valid block failed validation")

        # 🧪 Test 2: Tampered Block Data
        tampered_block = valid_block.copy()
        tampered_block.transactions[0].outputs[0].amount += 1
        self.assertFalse(tampered_block.validate_transactions(self.fee_model, self.standard_mempool, 1),
                        "Tampered block passed validation")

        # 🧪 Test 3: Block Size Enforcement
        oversize_block = self.create_oversized_block()
        self.assertGreater(oversize_block.get_total_size(), self.poc.block_manager.current_block_size * 1024 * 1024,
                          "Block size limits not enforced")

    def test_02_transaction_lifecycle(self):
        """Test transaction flow from creation to blockchain inclusion"""
        print("\n[TEST] Complete Transaction Lifecycle Test...")
        
        # 🧪 Create Valid Transaction
        tx = self.create_valid_transaction()
        self.assertTrue(self.poc.validate_transaction(tx, []), 
                       "Valid transaction failed validation")

        # 🧪 Add to Mempool
        self.standard_mempool.add_transaction(tx, self.poc.dispute_contract, self.fee_model)
        self.assertIn(tx.tx_id, self.standard_mempool.transactions,
                     "Transaction not added to mempool")

        # 🧪 Mine Block with Transaction
        mined_block = self.miner.mine_block()
        self.assertIn(tx, mined_block.transactions,
                     "Transaction not included in mined block")

        # 🧪 Verify UTXO Updates
        for output in tx.outputs:
            utxo = self.poc.get_utxo(output.tx_out_id)
            self.assertIsNotNone(utxo, "UTXO not created for transaction output")

    # --------------------- Mempool Stress Tests ---------------------
    def test_03_mempool_operations(self):
        """Test mempool behavior under high load with dependency tracking"""
        print("\n[TEST] Mempool Stress & Dependency Test...")
        
        # 🧪 Parent-Child Transaction Chain
        parent_tx = self.create_valid_transaction("PID-PARENT-001")
        child_tx = self.create_child_transaction(parent_tx.tx_id, "CID-CHILD-001")
        
        # Test 1: Orphan Transaction Handling
        self.standard_mempool.add_transaction(child_tx, self.poc.dispute_contract, self.fee_model)
        self.assertNotIn(child_tx.tx_id, self.standard_mempool.transactions,
                        "Orphan child transaction was accepted")

        # Test 2: Valid Transaction Chain
        self.standard_mempool.add_transaction(parent_tx, self.poc.dispute_contract, self.fee_model)
        self.standard_mempool.add_transaction(child_tx, self.poc.dispute_contract, self.fee_model)
        self.assertIn(child_tx.tx_id, self.standard_mempool.transactions,
                    "Valid child transaction rejected")

        # Test 3: Mempool Eviction Priority
        low_fee_tx = self.create_low_fee_transaction()
        self.standard_mempool.add_transaction(low_fee_tx, self.poc.dispute_contract, self.fee_model)
        
        # Force eviction by adding large transaction
        large_tx = self.create_large_transaction()
        self.standard_mempool.add_transaction(large_tx, self.poc.dispute_contract, self.fee_model)
        self.assertNotIn(low_fee_tx.tx_id, self.standard_mempool.transactions,
                        "Low-fee transaction not evicted properly")

    # --------------------- Anti-Farm Mechanism Tests ---------------------
    def test_04_anti_farm_measures(self):
        """Test VRAM scaling and algorithm rotation under attack conditions"""
        print("\n[TEST] Anti-Farm Countermeasure Validation...")
        
        # 🧪 Simulate Hashrate Spike
        initial_vram = self.miner.base_vram
        self.miner.previous_hashrate = 50000  # Initial hashrate
        self.miner.check_hashrate_adjustment(55000)  >10% increase
        
        # Test 1: VRAM Scaling
        self.assertGreater(self.miner.base_vram, initial_vram,
                         "VRAM did not scale during hashrate spike")
        
        # Test 2: Algorithm Rotation
        self.assertEqual(self.miner.algorithm_rotation_interval, 24,
                        "Algorithm rotation interval not reset during spike")

        # Test 3: Difficulty Adjustment Clamping
        self.poc.block_manager.difficulty_target = 1000
        self.poc.block_manager._adjust_target(2000)  # Simulate 100% increase
        self.assertAlmostEqual(self.poc.block_manager.difficulty_target, 1250, delta=1,
                              "Difficulty adjustment exceeded 25% clamp")

    # --------------------- Layer 2 Protocol Tests ---------------------
    def test_05_layer2_operations(self):
        """Test payment channels and multi-hop routing with real network conditions"""
        print("\n[TEST] Layer 2 Protocol Validation...")
        
        # 🧪 Payment Channel Lifecycle
        channel = PaymentChannel("CH-001", "A", "B", ["UTXO-1"], self.poc)
        channel.open_channel()
        self.assertTrue(self.poc.get_utxo("UTXO-1").locked,
                      "Channel UTXO not locked during opening")

        # 🧪 HTLC Execution
        htlc = channel.create_htlc("A", "B", 10.0, "HASH-123", expiry=3600)
        self.assertEqual(len(channel.htlcs), 1,
                        "HTLC not added to payment channel")

        # 🧪 MultiHop Pathfinding
        network = MultiHop()
        network.add_channel("A", "B", 1)
        network.add_channel("B", "C", 1)
        self.assertEqual(network.find_shortest_path("A", "C"), ["A", "B", "C"],
                        "MultiHop pathfinding failed")

    # --------------------- Edge Case Tests ---------------------
    def test_06_edge_cases(self):
        """Test blockchain behavior under extreme/unexpected conditions"""
        print("\n[TEST] Edge Case Validation...")
        
        # 🧪 Empty Block Mining
        empty_block = self.miner.mine_block(include_transactions=False)
        self.assertEqual(len(empty_block.transactions), 1,  # Coinbase only
                        "Empty block contains unexpected transactions")

        # 🧪 Double Spend Attack
        tx1 = self.create_valid_transaction("TX-001")
        tx2 = self.create_double_spend_transaction("TX-001")
        self.standard_mempool.add_transaction(tx1, self.poc.dispute_contract, self.fee_model)
        self.assertFalse(self.standard_mempool.add_transaction(tx2, self.poc.dispute_contract, self.fee_model),
                        "Double spend transaction accepted")

        # 🧪 Maximum Supply Enforcement
        self.poc.block_manager.total_issued = self.fee_model.max_supply - Decimal('50')
        coinbase_tx = CoinbaseTx(block_height=999999, miner_address="test")
        self.assertEqual(coinbase_tx.outputs[0].amount, 50.0,
                        "Block reward not adjusted near max supply")
        self.poc.block_manager.total_issued = self.fee_model.max_supply
        zero_reward_tx = CoinbaseTx(block_height=1000000, miner_address="test")
        self.assertEqual(zero_reward_tx.outputs[0].amount, 0.0,
                        "Coinbase transaction issued coins after max supply")

    # --------------------- Helper Methods ---------------------
    def create_valid_block(self):
        """Generate a block meeting all consensus rules"""
        last_block = self.poc.get_last_block()
        return Block(
            index=last_block.index + 1,
            previous_hash=last_block.hash,
            transactions=[],
            timestamp=int(time.time())
        )

    def create_oversized_block(self):
        """Generate block exceeding size limits"""
        block = self.create_valid_block()
        for _ in range(10000):
            block.transactions.append(self.create_large_transaction())
        return block

    def create_valid_transaction(self, tx_id="TX-TEST"):
        """Generate transaction with valid inputs/outputs"""
        return Transaction(
            tx_id=tx_id,
            inputs=[TransactionIn(tx_out_id="UTXO-1", script_sig="SIG-1")],
            outputs=[TransactionOut(script_pub_key="ADDR-1", amount=10.0)]
        )

    def create_child_transaction(self, parent_id, tx_id):
        """Generate child transaction with parent dependency"""
        return Transaction(
            tx_id=tx_id,
            inputs=[TransactionIn(tx_out_id=parent_id, script_sig="SIG-CHILD")],
            outputs=[TransactionOut(script_pub_key="ADDR-2", amount=9.5)]
        )

    @classmethod
    def tearDownClass(cls):
        """Cleanup blockchain state after all tests"""
        print("\n[TEARDOWN] Final Blockchain Environment Cleanup...")
        cls.poc.clear_blockchain()

if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)