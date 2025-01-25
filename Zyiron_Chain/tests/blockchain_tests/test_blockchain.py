import sys
import os

# Add the project root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

import time
import hashlib
import json
from decimal import Decimal
from threading import Lock
from unittest.mock import MagicMock
from collections import defaultdict

from Zyiron_Chain.blockchain.blockchain import Blockchain
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
from Zyiron_Chain.blockchain.utils.data_storage import JSONHandler
from Zyiron_Chain.transactions.Blockchain_transaction import (
    Transaction, TransactionIn, TransactionOut, CoinbaseTx
)
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.transactions.sendZYC import SendZYC
from Zyiron_Chain.smartpay.smartmempool import SmartMempool
from Zyiron_Chain.blockchain.utils.standardmempool import StandardMempool
from Zyiron_Chain.offchain.multihop import MultiHop, NetworkGraph

import sys
import os
import unittest
import time
import hashlib
import json
from decimal import Decimal

# Add the project root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from Zyiron_Chain.blockchain.blockchain import Blockchain
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
from Zyiron_Chain.blockchain.utils.data_storage import JSONHandler
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx, Transaction, TransactionOut, TransactionIn
from Zyiron_Chain.blockchain.block import Block
from Zyiron_Chain.transactions.sendZYC import SendZYC
from Zyiron_Chain.offchain.instantpay import PaymentChannel
from Zyiron_Chain.offchain.multihop import MultiHop
from Zyiron_Chain.offchain.dispute import DisputeResolutionContract
from Zyiron_Chain.blockchain.utils.standardmempool import StandardMempool
from Zyiron_Chain.smartpay.smartmempool import SmartMempool

class BlockchainTestSuite(unittest.TestCase):

    def test_key_manager(self):
        """Test KeyManager initialization and key generation."""
        key_manager = KeyManager()
        key_manager.generate_keys()  # Ensure this method exists
        self.assertGreater(len(key_manager.keys["testnet"]["keys"]), 0)
        self.assertGreater(len(key_manager.keys["mainnet"]["keys"]), 0)

    def test_blockchain_initialization(self):
        """Test blockchain initialization and genesis block creation."""
        key_manager = KeyManager()
        blockchain = Blockchain(key_manager)
        blockchain.create_genesis_block()
        self.assertEqual(len(blockchain.chain), 1)
        self.assertEqual(blockchain.chain[0].index, 0)

    def test_utxo_management(self):
        """Test UTXO creation and consumption."""
        key_manager = KeyManager()
        blockchain = Blockchain(key_manager)
        blockchain.create_genesis_block()

        tx_out = TransactionOut("recipient_key", 50.0)
        blockchain.utxo_manager.add_utxo("tx1", 0, tx_out)
        self.assertTrue(blockchain.utxo_manager.get_utxo("tx1", 0))

        blockchain.utxo_manager.consume_utxo("tx1", 0)
        self.assertIsNone(blockchain.utxo_manager.get_utxo("tx1", 0))

    def test_mempool(self):
        """Test Standard and Smart Mempool functionality."""
        standard_mempool = StandardMempool()
        smart_mempool = SmartMempool()

        # Create sample transactions
        tx_standard = Transaction(
            tx_inputs=[TransactionIn("utxo1", "script_sig")],
            tx_outputs=[TransactionOut("recipient", 50.0)]
        )
        tx_smart = Transaction(
            tx_inputs=[TransactionIn("utxo2", "script_sig")],
            tx_outputs=[TransactionOut("recipient", 30.0)]
        )
        tx_smart.tx_id = "S-smart_tx_id"

        # Add transactions to mempools
        self.assertTrue(standard_mempool.add_transaction(tx_standard, None))
        self.assertTrue(smart_mempool.add_transaction(tx_smart, 100))

    def test_layer2_multihop(self):
        """Test MultiHop routing and pathfinding."""
        multihop = MultiHop()
        multihop.add_channel("A", "B", 1)
        multihop.add_channel("B", "C", 1)

        path = multihop.find_shortest_path("A", "C")
        self.assertEqual(path, ["A", "B", "C"])

    def test_dispute_resolution(self):
        """Test dispute resolution logic."""
        contract = DisputeResolutionContract()
        contract.register_transaction(
            transaction_id="tx1",
            parent_id=None,
            utxo_id="utxo1",
            sender="party_a",
            recipient="party_b",
            amount=Decimal("10.0"),
            fee=Decimal("0.1")
        )
        self.assertIn("tx1", contract.transactions)

    def test_payment_channels(self):
        """Test payment channel opening, closing, and HTLC creation."""
        channel = PaymentChannel(
            channel_id="channel1",
            party_a="party_a",
            party_b="party_b",
            utxos={},
            wallet=None,
            network_prefix="testnet"
        )
        channel.open_channel()
        self.assertTrue(channel.is_open)
        channel.close_channel()
        self.assertFalse(channel.is_open)

if __name__ == "__main__":
    unittest.main()
