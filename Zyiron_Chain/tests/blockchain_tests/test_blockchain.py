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

class BlockchainTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Setup the test blockchain environment.
        """
        print("\n[SETUP] Initializing Blockchain Test Environment...\n")

        cls.poc = PoC()

        # Ensure Genesis Block Exists
        last_block = cls.poc.get_last_block()
        if not last_block:
            print("[INFO] Creating Genesis Block...")
            genesis_block = Block(
                index=0,
                previous_hash="0" * 96,
                transactions=[],
                timestamp=int(time.time()),
                key_manager=None
            )
            genesis_block.calculate_hash()
            cls.poc.store_block(genesis_block, difficulty=0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF)
            print("[SUCCESS] Genesis Block Created & Stored.")


    def test_block_creation(self):
        """
        Test block creation and validation.
        """
        last_block = self.poc.get_last_block()  # Get last block
        new_block = Block(
            index=last_block.index + 1,
            previous_hash=last_block.hash,  # Now correct type
            transactions=[],
            timestamp=int(time.time())
        )
        new_block.calculate_hash()
        self.assertTrue(new_block.hash.startswith("0000"))  # Ensure difficulty condition met
        print("[SUCCESS] Block creation and validation passed.")

    def test_mining(self):
        """Test ASIC-resistant mining with randomized PoW."""
        print("\n[TEST] ASIC-Resistant Mining Test...\n")
        result = self.miner.mine_block()
        self.assertTrue(result)
        print("[SUCCESS] Block successfully mined and added to chain.\n")

    def test_transaction_processing(self):
        """Test transaction creation, validation, and mempool handling."""
        print("\n[TEST] Transaction Processing & Mempool Test...\n")

        tx_inputs = [{"tx_out_id": "input1", "amount": 10.0}]
        tx_outputs = [{"recipient": "recipient_address", "amount": 9.5}]
        transaction = Transaction("T-12345678", tx_inputs, tx_outputs)

        self.assertTrue(self.poc.validate_transaction(transaction, []))
        self.poc.add_pending_transaction(transaction)
        self.assertIn(transaction, self.poc.get_pending_transactions_from_mempool())

        print("[SUCCESS] Transaction created, validated, and added to mempool.\n")

    def test_utxo_handling(self):
        """Test UTXO creation, validation, and consumption."""
        print("\n[TEST] UTXO Handling Test...\n")

        utxo = TransactionOut(script_pub_key="test_address", amount=20.0)
        self.utxo_manager.register_utxo(utxo)

        fetched_utxo = self.utxo_manager.get_utxo(utxo.tx_out_id)
        self.assertIsNotNone(fetched_utxo)
        self.assertEqual(fetched_utxo.amount, 20.0)

        self.utxo_manager.consume_utxo(utxo.tx_out_id)
        self.assertIsNone(self.utxo_manager.get_utxo(utxo.tx_out_id))

        print("[SUCCESS] UTXO creation, validation, and consumption passed.\n")

    def test_mempool(self):
        """Test Standard and Smart Mempool functionality."""
        print("\n[TEST] Mempool Functionality Test...\n")

        standard_mempool = StandardMempool()
        smart_mempool = SmartMempool()

        tx_standard = Transaction(
            tx_inputs=[TransactionIn("utxo1", "script_sig")],
            tx_outputs=[TransactionOut("recipient", 50.0)]
        )
        tx_smart = Transaction(
            tx_inputs=[TransactionIn("utxo2", "script_sig")],
            tx_outputs=[TransactionOut("recipient", 30.0)]
        )
        tx_smart.tx_id = "S-smart_tx_id"

        self.assertTrue(standard_mempool.add_transaction(tx_standard, None))
        self.assertTrue(smart_mempool.add_transaction(tx_smart, 100))

        print("[SUCCESS] Mempool validated for Standard & Smart Transactions.\n")

    def test_layer2_multihop(self):
        """Test MultiHop routing and pathfinding."""
        print("\n[TEST] MultiHop Routing Test...\n")

        multihop = MultiHop()
        multihop.add_channel("A", "B", 1)
        multihop.add_channel("B", "C", 1)

        path = multihop.find_shortest_path("A", "C")
        self.assertEqual(path, ["A", "B", "C"])

        print("[SUCCESS] MultiHop pathfinding successful.\n")

    @classmethod
    def tearDownClass(cls):
        """Cleanup test environment."""
        print("\n[TEARDOWN] Cleaning up blockchain test environment...\n")

        # Ensure TinyDB is closed properly
        if hasattr(cls.tinydb_manager, 'db'):
            cls.tinydb_manager.db.close()

        cls.poc.clear_blockchain()
        print("[SUCCESS] Test blockchain environment cleaned up.\n")


if __name__ == "__main__":
    unittest.main()