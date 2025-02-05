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

import unittest
import time
from decimal import Decimal
from Zyiron_Chain.blockchain.helper import get_block
Block = get_block()  # ✅ Lazy import
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
from Zyiron_Chain.blockchain.blockheader import BlockHeader
from Zyiron_Chain.blockchain.miner import Miner
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction, TransactionIn, TransactionOut, CoinbaseTx
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.database.unqlitedatabase import BlockchainUnqliteDB
from Zyiron_Chain.database.sqlitedatabase import SQLiteDB
from Zyiron_Chain.database.duckdatabase import AnalyticsNetworkDB
from Zyiron_Chain.database.lmdatabase import LMDBManager
from Zyiron_Chain.database.tinydatabase import TinyDBManager
from Zyiron_Chain.offchain.instantpay import PaymentChannel
from Zyiron_Chain.offchain.multihop import MultiHop
from Zyiron_Chain.offchain.dispute import DisputeResolutionContract
from Zyiron_Chain.blockchain.utils.standardmempool import StandardMempool
from Zyiron_Chain.smartpay.smartmempool import SmartMempool
from Zyiron_Chain.transactions.fees import FundsAllocator
import logging
import copy  # ✅ Import copy module at the top
logging.basicConfig(level=logging.INFO)

class BlockchainTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize complete blockchain ecosystem with anti-farm measures"""
        print("\n[SETUP] Building Full Blockchain Test Environment...\n")
        
        # ✅ Initialize PoC and other core components
        cls.poc = PoC()
        cls.fee_model = FeeModel(max_supply=Decimal('84096000'))
        cls.allocator = FundsAllocator(cls.fee_model.max_supply)
        
        # ✅ Check if a genesis block exists
        if not cls.poc.get_last_block():
            genesis = Block(
                index=0,
                previous_hash="0" * 96,
                transactions=[CoinbaseTx(block_height=0, miner_address="genesis", reward=Decimal("50.0"))],
                timestamp=int(time.time()),
                key_manager=KeyManager(),  # ✅ Ensure KeyManager is available
                nonce=0,
                poc=cls.poc  # ✅ Pass `poc`
            )

            # ✅ Ensure transactions are correctly processed
            genesis.transactions = genesis._ensure_transactions(genesis.transactions, cls.poc)

            # ✅ Compute the correct Merkle root
            genesis.merkle_root = genesis.calculate_merkle_root()

            # ✅ Store the block through PoC
            cls.poc.store_block(
                genesis,
                difficulty=0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
            )

        # ✅ Initialize mining components
        cls.miner = Miner(cls.poc.block_manager, cls.poc.standard_mempool, cls.poc.storage_manager)
        cls.miner.base_vram = 8 * 1024 * 1024  # Start at 8MB VRAM



    def setUp(self):
        self.poc.clear_blockchain()
        self.standard_mempool = StandardMempool()
        self.smart_mempool = SmartMempool()



    def test_01_block_validation(self):
        """
        Ensure that a valid block passes validation, but a tampered one fails.
        """
        valid_block = self.create_valid_block()
        self.assertTrue(valid_block.validate_transactions(self.fee_model, self.standard_mempool, 1))

        # ✅ Tamper with the block
        tampered_block = copy.deepcopy(valid_block)
        tampered_block.transactions[0].outputs[0].amount += Decimal("1.0")  # Modify output amount

        # ✅ Ensure that the tampered transaction is detected as invalid
        self.assertFalse(tampered_block.validate_transactions(self.fee_model, self.standard_mempool, 1),
                        "[ERROR] Tampered transaction should have failed validation!")


    def test_02_transaction_lifecycle(self):
        tx = self.create_valid_transaction()
        self.assertTrue(self.poc.validate_transaction(tx, []))
        
        self.standard_mempool.add_transaction(tx, self.poc.dispute_contract, self.fee_model)
        self.assertIn(tx.tx_id, self.standard_mempool.transactions)
        
        mined_block = self.miner.mine_block()
        self.assertIn(tx, mined_block.transactions)

    def test_03_mempool_operations(self):
        parent_tx = self.create_valid_transaction("PID-PARENT-001")
        child_tx = self.create_child_transaction(parent_tx.tx_id, "CID-CHILD-001")
        
        self.standard_mempool.add_transaction(child_tx, self.poc.dispute_contract, self.fee_model)
        self.assertNotIn(child_tx.tx_id, self.standard_mempool.transactions)
        
        self.standard_mempool.add_transaction(parent_tx, self.poc.dispute_contract, self.fee_model)
        self.standard_mempool.add_transaction(child_tx, self.poc.dispute_contract, self.fee_model)
        self.assertIn(child_tx.tx_id, self.standard_mempool.transactions)

    def test_04_anti_farm_measures(self):
        initial_vram = self.miner.base_vram
        self.miner.previous_hashrate = 50000
        self.miner.check_hashrate_adjustment(55000)
        
        self.assertGreater(self.miner.base_vram, initial_vram)
        self.assertEqual(self.miner.algorithm_rotation_interval, 24)
        
        self.poc.block_manager.difficulty_target = 1000
        self.poc.block_manager._adjust_target(2000)
        expected_difficulty = min(self.poc.block_manager.difficulty_target * 1.25, 2000)
        self.assertAlmostEqual(self.poc.block_manager.difficulty_target, expected_difficulty, delta=1)

    def create_valid_block(self):
        """Create a valid block with at least one valid transaction."""
        last_block = self.poc.get_last_block()

        # ✅ Ensure a UTXO exists before creating a transaction
        test_utxo = {
            "tx_out_id": "UTXO-1",
            "amount": Decimal("10.0"),
            "script_pub_key": "test-address"
        }
        self.poc.store_utxo("UTXO-1", test_utxo)  # ✅ Store a dummy UTXO for testing

        # ✅ Create a valid transaction
        sample_transaction = Transaction(
            tx_id="TX-VALID-1",
            inputs=[TransactionIn(tx_out_id="UTXO-1", script_sig="TEST-SIG")],  # ✅ Use a valid UTXO
            outputs=[TransactionOut(script_pub_key="test-address", amount=Decimal("9.5"))],  # ✅ Valid output
        )

        # ✅ Create block with valid transactions
        return Block(
            index=last_block.index + 1,
            previous_hash=last_block.hash,
            transactions=[sample_transaction],  # ✅ Include valid transaction
            timestamp=int(time.time())
        )


    
    def create_valid_transaction(self, tx_id="TX-TEST"):
        return Transaction(
            tx_id=tx_id,
            inputs=[TransactionIn(tx_out_id="UTXO-1", script_sig="SIG-1")],
            outputs=[TransactionOut(script_pub_key="ADDR-1", amount=10.0)]
        )

    def create_child_transaction(self, parent_id, tx_id):
        return Transaction(
            tx_id=tx_id,
            inputs=[TransactionIn(tx_out_id=parent_id, script_sig="SIG-CHILD")],
            outputs=[TransactionOut(script_pub_key="ADDR-2", amount=9.5)]
        )

    @classmethod
    def tearDownClass(cls):
        print("\n[TEARDOWN] Final Blockchain Environment Cleanup...")
        cls.poc.clear_blockchain()

if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
