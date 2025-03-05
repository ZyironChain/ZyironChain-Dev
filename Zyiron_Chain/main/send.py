#!/usr/bin/env python3
import sys
import os
import time
import logging
from decimal import Decimal, getcontext

# Set high precision for financial calculations
getcontext().prec = 18

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

# Import required modules from the project
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.keys.key_manager import KeyManager
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.transactions.transaction_manager import TransactionManager
from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.transactions.txin import TransactionIn
from Zyiron_Chain.transactions.txout import TransactionOut

# Import WalletStorage to fetch wallet index balance from LMDB
from Zyiron_Chain.database.wallet_index import WalletStorage # type: ignore
from Zyiron_Chain.database.storage_manager import StorageManager # type: ignore
from Zyiron_Chain.blockchain.blockchain import Blockchain

def debug_print(msg: str):
    print(f"[SEND.PY DEBUG] {msg}")

class TransactionSender:
    """
    Interactive transaction sender that allows users to:
      - Check wallet UTXO balances (via LMDB wallet index),
      - Send transactions (Standard, Smart, Instant),
      - And view detailed debug output.
      
    This class integrates key management, wallet index, UTXO management,
    transaction creation, and blockchain/mempool operations.
    """
    def __init__(self):
        debug_print("Initializing TransactionSender...")
        # Initialize core modules
        self.key_manager = KeyManager()
        self.storage_manager = StorageManager()
        self.blockchain = Blockchain(self.storage_manager, None, self.key_manager)
        
        # Retrieve the user's wallet address from KeyManager
        self.user_address = self.key_manager.get_default_public_key(Constants.NETWORK, "user")
        debug_print(f"User wallet address: {self.user_address}")
        
        # Initialize WalletStorage to fetch UTXO balance from the wallet index LMDB
        self.wallet_storage = WalletStorage()  # Assumes WalletStorage initializes with correct DB path
        
        # For UTXOManager, we use the user's wallet address
        self.utxo_manager = UTXOManager(self.user_address)
        self.transaction_manager = TransactionManager(self.storage_manager, self.key_manager, None)
        debug_print("Modules initialized successfully.")

    def display_menu(self):
        print("\n=== Transaction Sender Menu ===")
        print("1. Check Wallet Balance (from Wallet Index)")
        print("2. Send Standard Transaction")
        print("3. Send Smart Transaction")
        print("4. Send Instant Transaction")
        print("5. Exit")
        print("================================")

    def get_wallet_balance(self):
        debug_print("Fetching wallet balance from LMDB Wallet Index...")
        try:
            balance = self.wallet_storage.get_balance(self.user_address)
            print(f"Wallet Balance for {self.user_address}: {balance} {Constants.ADDRESS_PREFIX}")
            debug_print("Wallet balance fetched successfully from Wallet Index.")
        except Exception as e:
            print(f"Error fetching wallet balance: {e}")
            debug_print(f"get_wallet_balance error: {e}")

    def send_transaction(self, payment_type: str):
        """
        Prepares and sends a transaction of the given payment type.
        Payment type can be 'STANDARD', 'SMART', or 'INSTANT'.
        """
        try:
            recipient = input("Enter recipient address: ").strip()
            if not recipient:
                print("Recipient address cannot be empty.")
                return

            amount_input = input("Enter amount to send: ").strip()
            try:
                amount = Decimal(amount_input)
            except Exception:
                print("Invalid amount. Please enter a valid number.")
                return

            debug_print(f"Preparing {payment_type.upper()} transaction to {recipient} for amount {amount}.")
            # Use the maximum block size (converted from bytes to MB) from Constants
            block_size_mb = Constants.MAX_BLOCK_SIZE_BYTES / (1024 * 1024)
            
            # Create transaction via TransactionManager
            tx_data = self.transaction_manager.create_transaction(
                recipient_script_pub_key=recipient,
                amount=amount,
                block_size=block_size_mb,
                payment_type=payment_type.upper()
            )
            if tx_data and "transaction" in tx_data:
                transaction: Transaction = tx_data["transaction"]
                print(f"Transaction {transaction.tx_id} created and broadcasted.")
                debug_print(f"Transaction details: {transaction.to_dict()}")
            else:
                print("Transaction creation failed.")
        except Exception as e:
            print(f"Error sending transaction: {e}")
            debug_print(f"send_transaction error: {e}")

    def run(self):
        debug_print("Starting interactive transaction sender...")
        while True:
            self.display_menu()
            choice = input("Select an option (1-5): ").strip()
            if choice == "1":
                self.get_wallet_balance()
            elif choice == "2":
                self.send_transaction("STANDARD")
            elif choice == "3":
                self.send_transaction("SMART")
            elif choice == "4":
                self.send_transaction("INSTANT")
            elif choice == "5":
                print("Exiting Transaction Sender.")
                break
            else:
                print("Invalid option. Please choose between 1 and 5.")
            # Pause briefly for readability
            time.sleep(1)

if __name__ == "__main__":
    sender = TransactionSender()
    sender.run()
