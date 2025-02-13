import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


from Zyiron_Chain.transactions.Blockchain_transaction import Transaction, CoinbaseTx
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.blockchain.utils.standardmempool import StandardMempool
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager
from threading import Lock
from Zyiron_Chain.smartpay.smartmempool import SmartMempool  # Add this import
from decimal import Decimal

import logging


class TransactionManager:
    def __init__(self, storage_manager, key_manager, poc):
        """
        Initialize the Transaction Manager.
        - Standard Mempool: Handles regular transactions.
        - Smart Mempool: Manages smart contract transactions.
        - Locking mechanism for concurrent mempool access.
        """
        self.storage_manager = storage_manager
        self.key_manager = key_manager
        self.poc = poc  # ✅ Store PoC instance for transaction routing

        # ✅ Fix: Pass `poc` when initializing StandardMempool
        self.standard_mempool = StandardMempool(self.poc, timeout=86400)
        self.smart_mempool = SmartMempool()

        self.mempool_lock = Lock()  # ✅ Ensure mempool lock is properly initialized

    def store_transaction_in_mempool(self, transaction):
        """
        Store a transaction in the appropriate mempool and route it via PoC.
        - Standard transactions go to StandardMempool.
        - Smart transactions (S-) go to SmartMempool.
        - Ensures replay attack protection by checking nonce and network_id.
        """
        with self.mempool_lock:
            if transaction.tx_id.startswith("S-"):
                current_height = len(self.storage_manager.block_manager.chain)
                success = self.smart_mempool.add_transaction(transaction, current_height)
            else:
                success = self.standard_mempool.add_transaction(transaction)

            if success:
                self.storage_manager.poc.route_transaction_to_mempool(transaction)
            else:
                logging.error(f"[ERROR] Failed to store transaction {transaction.tx_id} in the mempool.")

    def select_transactions_for_block(self, max_block_size_mb=10):
        """
        Select transactions for the next block, prioritizing high-fee transactions.
        - Includes transactions from both mempools.
        - Ensures the selected transactions fit within the block size.
        """
        max_size = max_block_size_mb * 1024 * 1024
        current_height = len(self.storage_manager.block_manager.chain)

        # Fetch transactions from both mempools
        smart_txs = self.smart_mempool.get_smart_transactions(max_block_size_mb, current_height)

        # ✅ Fix: Pass `block_size_mb` to `get_pending_transactions()`
        standard_txs = self.standard_mempool.get_pending_transactions(block_size_mb=max_block_size_mb)

        # Sort by fee per byte for optimal inclusion
        all_txs = sorted(smart_txs + standard_txs, key=lambda tx: tx.fee / self._calculate_transaction_size(tx), reverse=True)

        # Select transactions that fit in the block
        selected_txs, current_size = [], 0
        for tx in all_txs:
            tx_size = self._calculate_transaction_size(tx)
            if current_size + tx_size <= max_size and self.validate_transaction(tx):
                selected_txs.append(tx)
                current_size += tx_size

        return selected_txs


    def _calculate_transaction_size(self, tx):
        """
        Calculate transaction size for block inclusion.
        - Uses SHA3-384-based size estimation.
        """
        return sum(
            len(str(inp.to_dict())) + len(str(out.to_dict()))
            for inp, out in zip(tx.inputs, tx.outputs)

        )

    def validate_transaction(self, tx):
        """
        Validate transaction integrity:
        - Signature verification.
        - Input/output balance check.
        - Prevent replay attacks by ensuring unique nonce and network_id.
        """
        try:
            if not tx.verify_signature():
                return False

            input_sum = sum(inp.amount for inp in tx.tx_inputs)
            output_sum = sum(out.amount for out in tx.tx_outputs)

            if input_sum < output_sum:
                return False

            # Check for replay attack prevention
            if self.storage_manager.poc.check_transaction_exists(tx.tx_id, tx.nonce, tx.network_id):
                logging.error(f"[ERROR] Replay attack detected for transaction {tx.tx_id}.")
                return False

            return True

        except Exception as e:
            logging.error(f"[ERROR] Transaction validation failed: {str(e)}")
            return False

    def create_coinbase_tx(self, total_fees, network, block_height):
        """
        Create a coinbase transaction for block rewards.
        - Uses the key manager to generate the miner's address.
        - Includes both block reward and collected transaction fees.
        """
        miner_address = self.key_manager.get_default_public_key(network, "miner")  # ✅ Get miner address

        # ✅ Fix: Remove `key_manager`, add `block_height`
        return CoinbaseTx(
            block_height=block_height,  # ✅ Required for transaction ID
            miner_address=miner_address,  # ✅ Use miner's address instead
            reward=Decimal(100.00) + total_fees  # ✅ Include transaction fees
        )

    def store_transaction_in_mempool(self, transaction):
        """
        Store a transaction in PoC's routing system.
        - Ensures transactions are handled according to network rules.
        """
        self.storage_manager.poc.route_transaction_to_mempool(transaction)
