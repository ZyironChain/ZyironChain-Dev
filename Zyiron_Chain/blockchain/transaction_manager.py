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
        - Handles transactions in both standard and smart mempools.
        """
        self.storage_manager = storage_manager
        self.key_manager = key_manager
        self.poc = poc

        # Initialize the mempools
        self.standard_mempool = StandardMempool(self.poc)
        self.smart_mempool = SmartMempool(self.poc)

    def store_transaction_in_mempool(self, transaction):
        """
        Store a transaction in the appropriate mempool and route it via PoC.
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


    def _calculate_block_reward(self, block_height):
        """
        Calculate the current block reward using halving logic.
        - Halves every 420,480 blocks (~4 years at 5 min block times).
        """
        halving_interval = 420480  # 4 years in 5-min blocks
        initial_reward = Decimal("100.00")  # ✅ Set the starting reward

        halvings = block_height // halving_interval
        reward = initial_reward / (2 ** halvings)

        # ✅ Ensure reward does not go below 0
        return max(reward, Decimal("0"))




    def create_coinbase_tx(self, fees, block_height, network):
        """
        Creates a coinbase transaction for miners.
        :param fees: Total transaction fees collected in the block.
        :param block_height: Height of the block being mined.
        :param network: Mainnet or Testnet identifier (must be a string).
        :return: Coinbase transaction object.
        """
        if not isinstance(network, str):
            raise ValueError(f"[ERROR] Invalid network parameter: {network} (Expected string)")

        miner_address = self.key_manager.get_default_public_key(network, "miner")  # ✅ Get miner address

        block_reward = self._calculate_block_reward(block_height)
        total_reward = block_reward + fees

        return CoinbaseTx(
            block_height=block_height,
            miner_address=miner_address,
            reward=total_reward
        )


    def store_transaction_in_mempool(self, transaction):
        """
        Store a transaction in the appropriate mempool and route it via PoC.
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


    def add_transaction_to_mempool(self, transaction):
        """
        Add a transaction to the mempool, ensuring it's valid and preventing replay attacks.
        :param transaction: The transaction object to add.
        """
        with self.mempool_lock:
            if transaction.tx_id in self.mempool:
                logging.error(f"[ERROR] Transaction {transaction.tx_id} already exists in mempool.")
                return False

            # Ensure that the transaction is valid
            if not self.validate_transaction(transaction):
                logging.error(f"[ERROR] Transaction {transaction.tx_id} is invalid.")
                return False

            # Add the transaction to the mempool
            self.mempool[transaction.tx_id] = transaction
            logging.info(f"[INFO] Transaction {transaction.tx_id} added to mempool.")
            return True
        

    def create_coinbase_tx(self, fees, block_height, network):
        """
        Creates a coinbase transaction for miners.
        :param fees: Total transaction fees collected in the block.
        :param block_height: Height of the block being mined.
        :param network: Mainnet or Testnet identifier (must be a string).
        :return: Coinbase transaction object.
        """
        if not isinstance(network, str):
            raise ValueError(f"[ERROR] Invalid network parameter: {network} (Expected string)")

        # ✅ Get the miner's public key using key_manager
        miner_address = self.key_manager.get_default_public_key(network, "miner")  # Get miner address

        # Calculate block reward
        block_reward = self._calculate_block_reward(block_height)
        total_reward = block_reward + fees

        return CoinbaseTx(
            block_height=block_height,
            miner_address=miner_address,
            reward=total_reward

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
        




    def select_transactions_for_block(self, max_block_size_mb=10):
        """
        Select transactions for the next block, prioritizing high-fee transactions.
        - Includes transactions from both mempools.
        - Ensures the selected transactions fit within the block size.
        """
        max_size = max_block_size_mb * 1024 * 1024  # Convert MB to bytes
        current_height = len(self.storage_manager.block_manager.chain)

        # Fetch transactions from both mempools
        smart_txs = self.smart_mempool.get_smart_transactions(max_block_size_mb, current_height)

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





    def get_pending_transactions(self):
        """
        Get all pending transactions from both mempools.
        """
        # Retrieve transactions from both Smart and Standard mempools
        standard_txs = self.standard_mempool.get_pending_transactions()
        smart_txs = self.smart_mempool.get_pending_transactions()

        # Combine both lists and return them
        return standard_txs + smart_txs