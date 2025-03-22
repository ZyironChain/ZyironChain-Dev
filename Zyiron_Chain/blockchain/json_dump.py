import json
from datetime import datetime
import sys
import os
from typing import List, Optional
# Adjust Python path for project structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

import json
from datetime import datetime

# Import your BlockStorage model
from Zyiron_Chain.storage.block_storage import BlockStorage  # Adjust this path based on your project structure

import os
import json
import time
from datetime import datetime

# Import blockchain storage models
from Zyiron_Chain.storage.block_storage import BlockStorage
from Zyiron_Chain.storage. tx_storage import TxStorage
from Zyiron_Chain.storage.utxostorage import UTXOStorage
from Zyiron_Chain.storage.mempool_storage import MempoolStorage
from Zyiron_Chain.storage.orphan_blocks import OrphanBlocks

import os
import json
import time
from datetime import datetime
from decimal import Decimal

from Zyiron_Chain.accounts. key_manager import KeyManager  # Ensure this exists

class BlockchainIndexer:
    """
    Interactive blockchain indexer with database queries and JSON export.
    """
    def __init__(self):
        import os
        from Zyiron_Chain.transactions.fees import FeeModel
        from Zyiron_Chain.blockchain.constants import Constants
        from Zyiron_Chain.transactions.utxo_manager import UTXOManager
        from Zyiron_Chain.transactions.transaction_manager import TransactionManager

        # ✅ Step 1: Setup FeeModel, TxStorage, KeyManager, BlockStorage
        self.fee_model = FeeModel(Constants.MAX_SUPPLY)
        self.tx_storage = TxStorage(self.fee_model)
        self.key_manager = KeyManager()
        self.block_storage = BlockStorage(self.tx_storage, self.key_manager)

        # ✅ Step 2: Initialize UTXOStorage first with dummy UTXOManager (will be updated after)
        temp_utxo_manager = UTXOManager(None)  # temporarily pass None
        temp_utxo_storage = UTXOStorage(temp_utxo_manager)
        temp_utxo_manager.utxo_storage = temp_utxo_storage

        # ✅ Assign properly
        self.utxo_manager = temp_utxo_manager
        self.utxo_storage = temp_utxo_storage

        # ✅ Step 3: Create TransactionManager (must come before MempoolStorage)
        self.transaction_manager = TransactionManager(
            key_manager=self.key_manager,
            block_storage=self.block_storage,
            utxo_manager=self.utxo_manager,
            tx_storage=self.tx_storage
            
        )

        # ✅ Step 4: Initialize MempoolStorage with TransactionManager
        self.mempool_storage = MempoolStorage(transaction_manager=self.transaction_manager)

        # ✅ Step 5: Initialize OrphanBlocks
        self.orphan_blocks = OrphanBlocks()

        # ✅ Step 6: Ensure export folder exists
        self.export_folder = "JsonBlockIndex"
        if not os.path.exists(self.export_folder):
            os.makedirs(self.export_folder)
            print(f"[BlockchainIndexer] INFO: Created folder '{self.export_folder}' for JSON dumps.")


    def dump_last_500_blocks(self):
        """Dumps the last 500 full blocks into a JSON file for integrity checks."""
        try:
            print("\n📦 Exporting last 500 blockchain blocks for integrity check...")
            all_blocks = self.block_storage.get_all_blocks()

            # Take last 500 or fewer
            recent_blocks = all_blocks[-500:] if len(all_blocks) > 500 else all_blocks

            block_data = []
            for b in recent_blocks:
                # Case 1: already a dict
                if isinstance(b, dict):
                    block_data.append(b)
                # Case 2: has a .to_dict() method
                elif hasattr(b, "to_dict") and callable(getattr(b, "to_dict")):
                    block_data.append(b.to_dict())
                # Case 3: nested structure with a 'block' key
                elif isinstance(b, object) and hasattr(b, "__dict__") and 'block' in b.__dict__:
                    try:
                        block_data.append(b.__dict__['block'].to_dict())
                    except Exception:
                        block_data.append(b.__dict__)
                else:
                    print(f"[WARN] Skipped unrecognized block object of type: {type(b)}")

            output_path = os.path.join(self.export_folder, "blockchain_integrity_check.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(block_data, f, indent=4)

            print(f"✅ Export complete: {len(block_data)} blocks saved.\n")
        except Exception as e:
            self.log_error(f"❌ Failed to dump last 500 blocks: {e}")


    def lookup_block(self):
        """Looks up a block by height or hash."""
        try:
            search_type = input("\n🔍 Search by (1) Block Height or (2) Block Hash? ")

            if search_type == "1":
                height = int(input("Enter block height: "))
                block = self.block_storage.get_block_by_height(height)
            elif search_type == "2":
                block_hash = input("Enter block hash: ")
                block = self.block_storage.get_block_by_hash(block_hash)
            else:
                print("❌ Invalid option.")
                return

            if block:
                print(json.dumps(block.to_dict(), indent=4))
            else:
                print("⚠️ Block not found.")

        except Exception as e:
            self.log_error(f"❌ Error looking up block: {e}")

    def lookup_transaction(self):
        """Looks up a transaction by ID or block height."""
        try:
            search_type = input("\n🔍 Search by (1) Transaction ID or (2) Block Height? ")

            if search_type == "1":
                tx_id = input("Enter transaction ID: ")
                tx = self.tx_storage.get_transaction(tx_id)
            elif search_type == "2":
                height = int(input("Enter block height: "))
                tx_list = self.tx_storage.get_transactions_by_block(height)
                if tx_list:
                    for tx in tx_list:
                        print(json.dumps(tx.to_dict(), indent=4))
                else:
                    print("⚠️ No transactions found at that height.")
                return
            else:
                print("❌ Invalid option.")
                return

            if tx:
                print(json.dumps(tx.to_dict(), indent=4))
            else:
                print("⚠️ Transaction not found.")

        except Exception as e:
            self.log_error(f"❌ Error looking up transaction: {e}")

    def list_pending_transactions(self):
        """Lists all pending transactions in the mempool."""
        try:
            print("\n📦 Fetching pending transactions from the mempool...")
            mempool_tx = self.mempool_storage.get_pending_transactions()
            if mempool_tx:
                for tx in mempool_tx:
                    print(json.dumps(tx.to_dict(), indent=4))
            else:
                print("⚠️ No pending transactions.")
        except Exception as e:
            self.log_error(f"❌ Error listing pending transactions: {e}")

    def find_utxos(self):
        """Finds UTXOs for a specific address."""
        try:
            address = input("\n🔍 Enter wallet address to find UTXOs: ")
            utxos = self.utxo_storage.get_utxos_by_address(address)
            if utxos:
                for utxo in utxos:
                    print(json.dumps(utxo, indent=4))  # ❗ Remove .to_dict()
            else:
                print("⚠️ No UTXOs found for this address.")
        except Exception as e:
            self.log_error(f"❌ Error fetching UTXOs: {e}")



    def check_orphan_blocks(self):
        """Lists all orphan blocks."""
        try:
            print("\n📦 Fetching orphan blocks...")
            orphan_blocks = self.orphan_blocks.get_all_orphans()
            if orphan_blocks:
                for block in orphan_blocks:
                    print(json.dumps(block.to_dict(), indent=4))
            else:
                print("⚠️ No orphan blocks found.")
        except Exception as e:
            self.log_error(f"❌ Error fetching orphan blocks: {e}")

    def query_utxo_balance(self):
        """Queries total UTXO balance for a specific address."""
        try:
            address = input("\n🔍 Enter wallet address to check balance: ")
            utxos = self.utxo_storage.get_utxos_by_address(address)

            total_balance = sum(Decimal(utxo["amount"]) for utxo in utxos) if utxos else Decimal("0")

            print(f"💰 Total Balance for {address}: {total_balance} ZYC")
        except Exception as e:
            self.log_error(f"❌ Error fetching UTXO balance: {e}")


    def log_error(self, message):
        """Logs errors to a file."""
        print(message)
        with open("indexer_errors.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] {message}\n")


    def calculate_balance(self, address):
        try:
            utxos = self.utxo_storage.get_utxos_by_address(address)
            total_balance = sum(Decimal(utxo["amount"]) for utxo in utxos)
            print(f"💰 Total Balance for {address}: {total_balance} ZYC")
        except Exception as e:
            print(f"❌ Error fetching UTXO balance: {e}")




    def run_interactive_menu(self):
        """Runs an interactive menu for indexing the blockchain."""
        while True:
            print("\n===== 🏦 Blockchain Indexer Menu =====")
            print("1️⃣  Dump last 500 blocks to JSON (Integrity Check)")
            print("2️⃣  Lookup a block")
            print("3️⃣  Lookup a transaction")
            print("4️⃣  List all pending transactions")
            print("5️⃣  Find UTXOs for an address")
            print("6️⃣  Check orphan blocks")
            print("7️⃣  Query total UTXO balance")
            print("8️⃣  Exit")

            choice = input("Enter your choice: ")

            if choice == "1":
                self.dump_last_500_blocks()
            elif choice == "2":
                self.lookup_block()
            elif choice == "3":
                self.lookup_transaction()
            elif choice == "4":
                self.list_pending_transactions()
            elif choice == "5":
                self.find_utxos()
            elif choice == "6":
                self.check_orphan_blocks()
            elif choice == "7":
                self.query_utxo_balance()
            elif choice == "8":
                print("🚀 Exiting Blockchain Indexer. Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    try:
        indexer = BlockchainIndexer()
        indexer.run_interactive_menu()
    except Exception as init_error:
        print(f"[{datetime.now()}] ❌ Initialization Error: {init_error}")
