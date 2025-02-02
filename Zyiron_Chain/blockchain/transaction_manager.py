import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


from Zyiron_Chain.transactions.Blockchain_transaction import Transaction, CoinbaseTx
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.txout import UTXOManager
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.blockchain.utils.standardmempool import StandardMempool
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager
from threading import Lock
from Zyiron_Chain.smartpay.smartmempool import SmartMempool  # Add this import

class TransactionManager:
    def __init__(self, storage_manager, key_manager):
        # Existing initialization
        self.standard_mempool = StandardMempool(timeout=86400)
        self.smart_mempool = SmartMempool()  # Add SmartMempool
        self.mempool_lock = Lock()  # Add shared lock

    def store_transaction_in_mempool(self, transaction):
        """Updated to handle both mempool types"""
        with self.mempool_lock:
            if transaction.tx_id.startswith("S-"):
                current_height = len(self.storage_manager.block_manager.chain)
                success = self.smart_mempool.add_transaction(transaction, current_height)
            else:
                success = self.standard_mempool.add_transaction(transaction)
            
            if success:
                self.storage_manager.poc.route_transaction_to_mempool(transaction)

    def select_transactions_for_block(self, max_block_size_mb=10):
        """Updated to combine both mempool types"""
        max_size = max_block_size_mb * 1024 * 1024
        current_height = len(self.storage_manager.block_manager.chain)
        
        # Get transactions from both mempools
        smart_txs = self.smart_mempool.get_smart_transactions(max_block_size_mb, current_height)
        standard_txs = self.standard_mempool.get_pending_transactions()
        
        # Combine and validate
        all_txs = smart_txs + standard_txs
        return [tx for tx in all_txs if self.validate_transaction(tx)][:max_size]

    def select_transactions_for_block(self, max_block_size_mb=10):
        max_size = max_block_size_mb * 1024 * 1024
        selected = []
        current_size = 0
        
        for tx in self.mempool.get_transactions():
            tx_size = sum(
                len(str(inp.to_dict())) + len(str(out.to_dict())) 
                for inp, out in zip(tx.tx_inputs, tx.tx_outputs)
            )
            
            if current_size + tx_size > max_size:
                break
                
            if self.validate_transaction(tx):
                selected.append(tx)
                current_size += tx_size
                
        return selected

    def validate_transaction(self, tx):
        try:
            if not tx.verify_signature():
                return False
                
            input_sum = sum(inp.amount for inp in tx.tx_inputs)
            output_sum = sum(out.amount for out in tx.tx_outputs)
            
            if input_sum < output_sum:
                return False
                
            return True
            
        except Exception as e:
            print(f"Transaction validation failed: {str(e)}")
            return False

    def create_coinbase_tx(self, total_fees, network):
        return CoinbaseTx(
            key_manager=self.key_manager,
            network=network,
            utxo_manager=self.utxo_manager,
            transaction_fees=total_fees
        )

    def store_transaction_in_mempool(self, transaction):
        self.storage_manager.poc.route_transaction_to_mempool(transaction)