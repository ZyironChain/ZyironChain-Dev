# main.py
import sys
import os
import time
from decimal import Decimal
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.blockchain.blockchain import Blockchain
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager
from decimal import Decimal
from Zyiron_Chain.transactions.transactiontype import TransactionType, PaymentTypeManager
from typing import Dict, List
from Zyiron_Chain.transactions. fees import FeeModel, FundsAllocator
from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx, TransactionFactory, sha3_384_hash


class BlockchainCLI:
    def __init__(self):
        # Initialize core components
        self.key_manager = KeyManager()
        self.poc = PoC()
        self.fee_model = FeeModel()
        self.payment_manager = PaymentTypeManager()
        
        # Initialize blockchain
        self.blockchain = Blockchain(
            key_manager=self.key_manager,
            poc=self.poc,
            network="testnet"
        )
        
        # Mining configuration
        self.block_reward = Decimal("6.25")
        self.current_block_size = 1  # MB
        self.miner_address = self.key_manager.get_miner_address("testnet")

    def mine_block(self):
        """Mine a new block with pending transactions"""
        print("\n⛏️ Starting mining process...")
        
        # Select transactions
        selected_txs = self.blockchain.select_transactions_for_block(self.current_block_size)
        
        # Create coinbase transaction
        total_fees = sum(tx.fee for tx in selected_txs)
        coinbase_tx = CoinbaseTx(
            block_height=len(self.blockchain.chain),
            miner_address=self.miner_address,
            reward=self.block_reward + total_fees
        )
        
        # Create block
        new_block = self.blockchain.create_block(
            transactions=selected_txs,
            coinbase_tx=coinbase_tx,
            block_size=self.current_block_size
        )
        
        print(f"✅ Block #{len(self.blockchain.chain)} mined successfully!")
        print(f"📦 Transactions included: {len(selected_txs)}")
        print(f"💰 Block reward: {self.block_reward} + {total_fees} fees")

    def add_transaction(self):
        """Add a transaction to the mempool"""
        print("\n💸 Create New Transaction")
        tx_type = self._select_transaction_type()
        sender = input("Sender address: ").strip()
        receiver = input("Receiver address: ").strip()
        amount = Decimal(input("Amount: ").strip())
        
        # Create transaction
        tx = self._create_transaction(tx_type, sender, receiver, amount)
        
        # Add to mempool
        self.blockchain.add_transaction(tx)
        print(f"📬 Transaction added to mempool (ID: {tx.tx_id})")

    def _select_transaction_type(self):
        """Select transaction type from menu"""
        print("\nSelect Transaction Type:")
        print("1. Standard (PID-*)")
        print("2. Smart Contract (S-*)")
        print("3. Instant (CID-*)")
        
        choice = input("Choice (1-3): ").strip()
        return {
            '1': TransactionType.STANDARD,
            '2': TransactionType.SMART,
            '3': TransactionType.INSTANT
        }.get(choice, TransactionType.STANDARD)

    def _create_transaction(self, tx_type, sender, receiver, amount):
        """Create a signed transaction"""
        return Transaction(
            tx_type=tx_type,
            sender=sender,
            receiver=receiver,
            amount=amount,
            fee_model=self.fee_model,
            key_manager=self.key_manager
        )

    def show_blockchain(self):
        """Display blockchain status"""
        print("\n🔗 Blockchain Status")
        print(f"📏 Chain length: {len(self.blockchain.chain)} blocks")
        print(f"⏳ Pending transactions: {len(self.blockchain.pending_transactions)}")
        print(f"📦 Current block size: {self.current_block_size} MB")

    def show_balance(self):
        """Display wallet balances"""
        address = input("Enter address to check balance: ").strip()
        balance = self.blockchain.get_balance(address)
        print(f"\n💰 Balance for {address}: {balance}")

    def run(self):
        """Main CLI interface"""
        print("""
        ╔════════════════════════════╗
        ║   Zyiron Chain CLI v1.0    ║
        ╚════════════════════════════╝
        """)
        
        while True:
            print("\nMain Menu:")
            print("1. Mine new block")
            print("2. Create transaction")
            print("3. View blockchain status")
            print("4. Check balance")
            print("5. Exit")
            
            choice = input("Select action (1-5): ").strip()
            
            if choice == '1':
                self.mine_block()
            elif choice == '2':
                self.add_transaction()
            elif choice == '3':
                self.show_blockchain()
            elif choice == '4':
                self.show_balance()
            elif choice == '5':
                print("\n👋 Exiting Zyiron Chain CLI...")
                break
            else:
                print("⚠️ Invalid choice, please try again.")

if __name__ == "__main__":
    cli = BlockchainCLI()
    cli.run()