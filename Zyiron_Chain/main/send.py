

import sys
import os
from typing import List, Optional
# Adjust Python path for project structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)


import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from decimal import Decimal

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from decimal import Decimal
import json
import os
from datetime import datetime

from decimal import Decimal
from typing import Optional, List, Dict, Union

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.transactions.coinbase import CoinbaseTx
from Zyiron_Chain.transactions.txin import TransactionIn
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.storage.tx_storage import TxStorage
from Zyiron_Chain.mempool.standardmempool import StandardMempool
from Zyiron_Chain.mempool.smartmempool import SmartMempool # type: ignore
from Zyiron_Chain.utils.hashing import Hashing
from decimal import Decimal
from datetime import datetime
import time


from decimal import Decimal
from typing import Optional, List, Tuple



class PaymentProcessor:
    """
    Handles sending transactions across Standard, Smart, and future Instant models.
    Integrates UTXO, mempool, fee estimation, and KeyManager-based Falcon verification.
    """

    def __init__(self,
                 utxo_manager: UTXOManager,
                 tx_storage: TxStorage,
                 standard_mempool: StandardMempool,
                 smart_mempool: SmartMempool,
                 key_manager):
        self.utxo_manager = utxo_manager
        self.tx_storage = tx_storage
        self.standard_mempool = standard_mempool
        self.smart_mempool = smart_mempool
        self.key_manager = key_manager
        self.fee_model = self.key_manager.fee_model if hasattr(self.key_manager, 'fee_model') else FeeModel(Constants.MAX_SUPPLY)

        print("[PaymentProcessor INIT] ✅ Initialized with KeyManager-based signing")

    def send_payment(self,
                     sender_priv_key: str,
                     sender_pub_key: str,
                     recipient_address: str,
                     amount: Decimal,
                     tx_type: str = "STANDARD",
                     metadata: Optional[dict] = None) -> Optional[str]:
        print(f"\n[PaymentProcessor] 💸 Starting Payment TX")
        print(f"   ↳ Amount: {amount} ZYC | Type: {tx_type} | To: {recipient_address}")

        if amount <= 0:
            print("[ERROR] ❌ Amount must be greater than zero.")
            return None

        if tx_type not in Constants.TRANSACTION_MEMPOOL_MAP:
            print(f"[ERROR] ❌ Unknown transaction type: {tx_type}")
            return None

        # Step 1: Gather UTXOs
        utxos, total_input = self._select_utxos(sender_pub_key, amount + Decimal("0.0001"))
        if not utxos:
            print("[ERROR] ❌ No valid UTXOs available.")
            return None

        fee = self.fee_model.calculate_fee(tx_type=tx_type, tx_size=512)
        print(f"[FeeModel] 💰 Estimated fee: {fee} ZYC")

        if total_input < amount + fee:
            print(f"[ERROR] ❌ Insufficient funds. Needed: {amount + fee}, Found: {total_input}")
            return None

        # Step 2: Build Inputs and Outputs
        inputs = [TransactionIn(tx_out_id=u.tx_out_id, script_sig="") for u in utxos]
        outputs = [TransactionOut(script_pub_key=recipient_address, amount=amount)]
        change = total_input - amount - fee
        if change > 0:
            outputs.append(TransactionOut(script_pub_key=sender_pub_key, amount=change))
            print(f"[Change] 💵 Returning change to sender: {change} ZYC")

        # Step 3: Create and sign transaction
        tx = Transaction(inputs=inputs, outputs=outputs, tx_type=tx_type, metadata=metadata or {})
        tx.sign(sender_priv_key, sender_pub_key)
        print(f"[TX] 🧾 Transaction created: {tx.tx_id} | Size: {tx.size} bytes")

        # Step 4: Verify with KeyManager
        if not self.key_manager.verify_transaction(
            message=tx.hash(),
            signature=tx.signature,
            network=self.key_manager.network,
            identifier=self.key_manager.keys[self.key_manager.network]["defaults"]["miner"]
        ):
            print("[ERROR] ❌ Signature verification failed using KeyManager.")
            return None

        print("[Signature] ✅ Verified via KeyManager")

        # Step 5: Lock UTXOs
        self.utxo_manager.lock_selected_utxos([u.tx_out_id for u in utxos])
        print(f"[UTXO] 🔒 Locked {len(utxos)} UTXOs")

        # Step 6: Add to Mempool
        if not self._route_to_mempool(tx):
            print("[Mempool] ❌ Routing failed. Unlocking UTXOs...")
            self.utxo_manager.unlock_selected_utxos([u.tx_out_id for u in utxos])
            return None

        print(f"[Success] ✅ TX Sent: {tx.tx_id}")
        return tx.tx_id

    def _select_utxos(self, address: str, required_amount: Decimal) -> Tuple[List[TransactionOut], Decimal]:
        print(f"[UTXO] 🔍 Selecting UTXOs for {address} to cover {required_amount} ZYC")
        utxos = self.utxo_manager.utxo_storage.get_utxos_by_address(address)
        selected = []
        total = Decimal("0")

        for utxo_dict in utxos:
            utxo = TransactionOut.from_dict(utxo_dict)
            if utxo.locked:
                continue
            selected.append(utxo)
            total += utxo.amount
            print(f"   ↳ Picked: {utxo.tx_out_id[:12]}... | Amount: {utxo.amount}")
            if total >= required_amount:
                break

        return selected, total

    def _route_to_mempool(self, tx: Transaction) -> bool:
        try:
            prefix = tx.tx_type.upper()
            if prefix.startswith("S"):
                print("[Mempool] ➡️ Routing to SmartMempool...")
                return self.smart_mempool.add_transaction(tx)
            elif prefix.startswith("I"):
                print("[Mempool] ⚠️ Instant transactions not implemented yet.")
                return False
            else:
                print("[Mempool] ➡️ Routing to StandardMempool...")
                return self.standard_mempool.add_transaction(tx)
        except Exception as e:
            print(f"[Mempool] ❌ Failed: {e}")
            return False


    def run_cli_send(self, key_manager):
        """
        Interactive CLI sender for ZYC blockchain.
        Uses Falcon keys from KeyManager, builds, signs, and broadcasts the transaction.
        """
        try:
            print("\n🔹 [CLI SEND MODE] Starting interactive send...")

            # 1️⃣ Load default key info from KeyManager
            network = key_manager.network  # should be 'mainnet'
            role = "miner"
            identifier = key_manager.keys[network]["defaults"][role]
            key_data = key_manager.keys[network]["keys"][identifier]

            print(f"\n🔐 Using default {role.upper()} key for {network.upper()}: {identifier}")
            pub_key = key_data["hashed_public_key"]
            priv_key = key_data["private_key"]
            print(f"🔑 Public Key (Hashed): {pub_key}")
            print("🔐 Private Key: [Loaded internally for signing]")

            # 2️⃣ Get recipient + amount + type
            recipient = input("\n📬 Enter recipient address (ZYC...): ").strip()
            amount_str = input("💰 Enter amount to send (e.g., 2.5): ").strip()
            tx_type = input("📦 Transaction type [STANDARD / SMART]: ").strip().upper()

            try:
                amount = Decimal(amount_str)
                if amount <= 0:
                    raise ValueError
            except:
                print("❌ Invalid amount.")
                return

            if tx_type not in Constants.TRANSACTION_MEMPOOL_MAP:
                print(f"❌ Invalid transaction type: {tx_type}")
                return

            print(f"\n✅ Preparing to send {amount} ZYC to {recipient} as a {tx_type} transaction...")

            # 3️⃣ UTXO Selection
            print("\n🔍 Selecting UTXOs for funding...")
            utxos, total_input = self._select_utxos(pub_key, amount)
            if not utxos:
                print("❌ No valid UTXOs found.")
                return

            print(f"📦 Selected {len(utxos)} UTXOs totaling {total_input} ZYC")
            for u in utxos:
                print(f"   - UTXO: {u.tx_out_id[:16]}... | Amount: {u.amount} | Locked: {u.locked}")

            # 4️⃣ Fee Calculation
            fee = self.fee_model.calculate_fee(tx_type=tx_type, tx_size=512)
            print(f"\n💸 Estimated network fee: {fee} ZYC")

            if total_input < amount + fee:
                print("❌ Insufficient funds after fee deduction.")
                return

            change = total_input - amount - fee
            print(f"💰 Change to return: {change} ZYC")

            # 5️⃣ Build transaction
            print("\n🛠️ Building transaction...")
            inputs = [TransactionIn(tx_out_id=u.tx_out_id, script_sig="") for u in utxos]
            outputs = [TransactionOut(script_pub_key=recipient, amount=amount)]
            if change > 0:
                outputs.append(TransactionOut(script_pub_key=pub_key, amount=change))

            tx = Transaction(inputs=inputs, outputs=outputs, tx_type=tx_type)
            tx.sign(priv_key, pub_key)

            print(f"📝 Transaction Created:")
            print(f"   - TXID: {tx.tx_id}")
            print(f"   - Inputs: {len(inputs)}")
            print(f"   - Outputs: {len(outputs)}")
            print(f"   - Fee: {tx.fee}")
            print(f"   - Size: {tx.size} bytes")

            # 6️⃣ Verify Signature
            if not self.verifier.verify(tx.signature, pub_key, tx.hash()):
                print("❌ Signature verification failed.")
                return

            print("🔐 Signature ✅ Verified")

            # 7️⃣ Lock UTXOs
            utxo_ids = [u.tx_out_id for u in utxos]
            print(f"🔒 Locking {len(utxo_ids)} UTXOs...")
            self.utxo_manager.lock_selected_utxos(utxo_ids)

            # 8️⃣ Route to mempool
            print(f"📨 Routing to {'SmartMempool' if tx_type.startswith('S') else 'StandardMempool'}...")
            if not self._route_to_mempool(tx):
                print("❌ Failed to route to mempool. Unlocking UTXOs...")
                self.utxo_manager.unlock_selected_utxos(utxo_ids)
                return

            print(f"\n✅ Transaction successfully submitted!")
            print(f"📜 TXID: {tx.tx_id}")

        except KeyboardInterrupt:
            print("\n[EXIT] User aborted.")
        except Exception as e:
            print(f"❌ [FATAL ERROR] {e}")


class BlockchainCLI:
    def __init__(self, processor, key_manager, utxo_manager, blockchain, tx_storage, standard_mempool, smart_mempool):
        self.processor = processor
        self.key_manager = key_manager
        self.utxo_manager = utxo_manager
        self.blockchain = blockchain
        self.tx_storage = tx_storage
        self.standard_mempool = standard_mempool
        self.smart_mempool = smart_mempool
        self.address = self.key_manager.get_default_public_key()

    def start(self):
        while True:
            print("\n🔹 Blockchain CLI Menu")
            print("1. 🔁 Send ZYC")
            print("2. 💰 Check Balance")
            print("3. 📜 View Transaction Details")
            print("4. ⛓️ Track Confirmation Count")
            print("5. 🧠 Estimate TX Time")
            print("0. Exit")

            choice = input("Enter your choice: ").strip()
            if choice == "1":
                self.send_transaction()
            elif choice == "2":
                self.check_balance()
            elif choice == "3":
                self.view_transaction()
            elif choice == "4":
                self.track_confirmations()
            elif choice == "5":
                self.estimate_tx_time()
            elif choice == "0":
                print("👋 Exiting CLI.")
                break
            else:
                print("❌ Invalid choice.")

    def send_transaction(self):
        print("\n📤 SEND PAYMENT")
        recipient = input("Recipient address: ").strip()
        amount = Decimal(input("Amount (e.g., 1.25): ").strip())
        tx_type = input("Transaction type [STANDARD / SMART]: ").strip().upper()

        priv_key = self.key_manager.keys["mainnet"]["keys"][
            self.key_manager.keys["mainnet"]["defaults"]["miner"]
        ]["private_key"]
        pub_key = self.address

        tx_id = self.processor.send_payment(
            sender_priv_key=priv_key,
            sender_pub_key=pub_key,
            recipient_address=recipient,
            amount=amount,
            tx_type=tx_type
        )
        if tx_id:
            print(f"✅ Sent! TXID: {tx_id}")
        else:
            print("❌ Failed to send transaction.")

    def check_balance(self):
        print(f"\n🔍 Checking balance for {self.address}")
        utxos = self.utxo_manager.utxo_storage.get_utxos_by_address(self.address)
        total = Decimal("0")
        for u in utxos:
            amt = Decimal(u["amount"])
            total += amt
            print(f" - {u['tx_out_id'][:12]}... | Amount: {amt}")
        print(f"💰 Total Available: {total} ZYC")

    def view_transaction(self):
        tx_id = input("Enter TXID to view: ").strip()
        tx_data = self.tx_storage.get_transaction(tx_id)
        if not tx_data:
            print("❌ TX not found.")
            return
        print(f"\n📜 TX Details for {tx_id}")
        for key, value in tx_data.items():
            print(f" - {key}: {value}")

    def track_confirmations(self):
        tx_id = input("TXID to check confirmations: ").strip()
        tx_data = self.tx_storage.get_transaction(tx_id)
        if not tx_data:
            print("❌ TX not found.")
            return

        block_hash = tx_data.get("block_hash")
        if not block_hash:
            print("⏳ TX not confirmed yet.")
            return

        current_height = self.blockchain.get_latest_block().index
        block_height = tx_data.get("block_height", 0)
        confirmations = max(0, current_height - block_height + 1)

        print(f"🧱 TX {tx_id} has {confirmations} confirmation(s).")
        if confirmations == 0:
            print("⏳ Waiting for inclusion...")
        elif confirmations < 3:
            print("⚠️ Not fully confirmed.")
        else:
            print("✅ Safe to consider final.")

    def estimate_tx_time(self):
        total_pending = self.standard_mempool.get_transaction_count() + self.smart_mempool.get_transaction_count()
        print(f"\n🧠 Estimating time for inclusion...")
        print(f" - Pending in mempool: {total_pending} transactions")

        if total_pending == 0:
            print("✅ Likely included in the next block (~10s)")
        elif total_pending < 50:
            print("⌛ Estimated time: 1–2 blocks (~10–20s)")
        else:
            print("⏱️ High network load. Could take multiple blocks (~30s+)")




class PaymentProcessorUI:
    def __init__(self, root, processor, key_manager, utxo_manager, blockchain, tx_storage, 
                 standard_mempool, smart_mempool, blockchain_indexer=None):
        self.root = root
        self.processor = processor
        self.key_manager = key_manager
        self.utxo_manager = utxo_manager
        self.blockchain = blockchain
        self.tx_storage = tx_storage
        self.standard_mempool = standard_mempool
        self.smart_mempool = smart_mempool
        self.blockchain_indexer = blockchain_indexer
        
        self.address = self.key_manager.get_default_public_key()
        self.log_output = None
        
        self.setup_ui()




    def setup_ui(self):
        self.root.title("ZYC Blockchain Payment Processor")
        self.root.geometry("1000x700")
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both')
        
        # Create tabs
        self.create_send_tab()
        self.create_balance_tab()
        self.create_tx_details_tab()
        self.create_confirmations_tab()
        self.create_estimate_tab()
        
        # Only add indexer tab if blockchain_indexer is provided
        if self.blockchain_indexer:
            self.create_indexer_tab()
            
        self.create_log_tab()
        
    def create_indexer_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Blockchain Indexer")
        
        # Create notebook within indexer tab for organization
        indexer_notebook = ttk.Notebook(tab)
        indexer_notebook.pack(expand=True, fill='both')
        
        # Block Explorer Sub-tab
        self.create_block_explorer_tab(indexer_notebook)
        
        # Transaction Explorer Sub-tab
        self.create_tx_explorer_tab(indexer_notebook)
        
        # UTXO Explorer Sub-tab
        self.create_utxo_explorer_tab(indexer_notebook)
        
        # Orphan Blocks Sub-tab
        self.create_orphan_blocks_tab(indexer_notebook)
        
        # Export Tools Sub-tab
        self.create_export_tools_tab(indexer_notebook)
        
    def create_block_explorer_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Block Explorer")
        
        # Search frame
        search_frame = ttk.LabelFrame(tab, text="Block Search")
        search_frame.pack(fill='x', padx=5, pady=5)
        
        # Search type
        ttk.Label(search_frame, text="Search By:").grid(row=0, column=0, padx=5, sticky='w')
        self.block_search_type = tk.StringVar(value="height")
        ttk.Radiobutton(search_frame, text="Height", variable=self.block_search_type, value="height").grid(row=0, column=1, sticky='w')
        ttk.Radiobutton(search_frame, text="Hash", variable=self.block_search_type, value="hash").grid(row=0, column=2, sticky='w')
        
        # Search input
        ttk.Label(search_frame, text="Value:").grid(row=1, column=0, padx=5, sticky='w')
        self.block_search_entry = ttk.Entry(search_frame, width=50)
        self.block_search_entry.grid(row=1, column=1, columnspan=2, sticky='we')
        
        # Search button
        search_btn = ttk.Button(search_frame, text="Search Block", command=self.search_block)
        search_btn.grid(row=2, column=0, columnspan=3, pady=5)
        
        # Results display
        self.block_results = scrolledtext.ScrolledText(tab, height=15, wrap=tk.WORD)
        self.block_results.pack(expand=True, fill='both', padx=5, pady=5)
        self.block_results.configure(state='disabled')
        
    def create_tx_explorer_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Transaction Explorer")
        
        # Search frame
        search_frame = ttk.LabelFrame(tab, text="Transaction Search")
        search_frame.pack(fill='x', padx=5, pady=5)
        
        # Search type
        ttk.Label(search_frame, text="Search By:").grid(row=0, column=0, padx=5, sticky='w')
        self.tx_search_type = tk.StringVar(value="txid")
        ttk.Radiobutton(search_frame, text="TXID", variable=self.tx_search_type, value="txid").grid(row=0, column=1, sticky='w')
        ttk.Radiobutton(search_frame, text="Block Height", variable=self.tx_search_type, value="height").grid(row=0, column=2, sticky='w')
        
        # Search input
        ttk.Label(search_frame, text="Value:").grid(row=1, column=0, padx=5, sticky='w')
        self.tx_search_entry = ttk.Entry(search_frame, width=50)
        self.tx_search_entry.grid(row=1, column=1, columnspan=2, sticky='we')
        
        # Search button
        search_btn = ttk.Button(search_frame, text="Search Transaction", command=self.search_transaction)
        search_btn.grid(row=2, column=0, columnspan=3, pady=5)
        
        # Pending transactions button
        pending_btn = ttk.Button(tab, text="View Pending Transactions", command=self.view_pending_transactions)
        pending_btn.pack(pady=5)
        
        # Results display
        self.tx_results = scrolledtext.ScrolledText(tab, height=15, wrap=tk.WORD)
        self.tx_results.pack(expand=True, fill='both', padx=5, pady=5)
        self.tx_results.configure(state='disabled')
        
    def create_utxo_explorer_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="UTXO Explorer")
        
        # Address search
        ttk.Label(tab, text="Wallet Address:").pack(pady=5)
        self.utxo_address_entry = ttk.Entry(tab, width=50)
        self.utxo_address_entry.pack(pady=5)
        
        # Buttons frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(pady=5)
        
        ttk.Button(btn_frame, text="Find UTXOs", command=self.find_utxos).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Calculate Balance", command=self.calculate_utxo_balance).pack(side='left', padx=5)
        
        # UTXO Treeview
        self.utxo_tree = ttk.Treeview(tab, columns=('txid', 'index', 'amount', 'locked'), show='headings')
        self.utxo_tree.heading('txid', text='Transaction ID')
        self.utxo_tree.heading('index', text='Output Index')
        self.utxo_tree.heading('amount', text='Amount (ZYC)')
        self.utxo_tree.heading('locked', text='Locked')
        self.utxo_tree.column('txid', width=250)
        self.utxo_tree.column('index', width=80)
        self.utxo_tree.column('amount', width=100)
        self.utxo_tree.column('locked', width=80)
        self.utxo_tree.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Balance label
        self.utxo_balance_label = ttk.Label(tab, text="Balance: ", font=('Arial', 12))
        self.utxo_balance_label.pack(pady=5)
        
    def create_orphan_blocks_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Orphan Blocks")
        
        # Refresh button
        refresh_btn = ttk.Button(tab, text="Refresh Orphan Blocks", command=self.refresh_orphan_blocks)
        refresh_btn.pack(pady=10)
        
        # Orphan blocks treeview
        self.orphan_tree = ttk.Treeview(tab, columns=('hash', 'height', 'tx_count'), show='headings')
        self.orphan_tree.heading('hash', text='Block Hash')
        self.orphan_tree.heading('height', text='Height')
        self.orphan_tree.heading('tx_count', text='TX Count')
        self.orphan_tree.column('hash', width=300)
        self.orphan_tree.column('height', width=80)
        self.orphan_tree.column('tx_count', width=80)
        self.orphan_tree.pack(expand=True, fill='both', padx=5, pady=5)
        
    def create_export_tools_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Export Tools")
        
        # Export buttons
        ttk.Button(tab, text="Export Last 500 Blocks", command=self.export_last_500_blocks).pack(pady=10)
        ttk.Button(tab, text="Select Custom Export Folder", command=self.select_export_folder).pack(pady=5)
        
        # Status label
        self.export_status = ttk.Label(tab, text="")
        self.export_status.pack(pady=5)
        
    # Indexer Tab Methods
    def search_block(self):
        search_type = self.block_search_type.get()
        search_value = self.block_search_entry.get().strip()
        
        if not search_value:
            messagebox.showerror("Error", "Please enter a search value")
            return
            
        try:
            if search_type == "height":
                block = self.blockchain_indexer.block_storage.get_block_by_height(int(search_value))
            else:
                block = self.blockchain_indexer.block_storage.get_block_by_hash(search_value)
                
            self.block_results.configure(state='normal')
            self.block_results.delete(1.0, tk.END)
            
            if block:
                if hasattr(block, 'to_dict'):
                    block_data = block.to_dict()
                else:
                    block_data = block
                    
                self.block_results.insert(tk.END, json.dumps(block_data, indent=4))
                self.log_message(f"[Indexer] ✅ Found block: {search_value}")
            else:
                self.block_results.insert(tk.END, "Block not found")
                self.log_message(f"[Indexer] ⚠️ Block not found: {search_value}")
                
            self.block_results.configure(state='disabled')
            
        except Exception as e:
            self.log_message(f"[Indexer] ❌ Error searching block: {e}")
            messagebox.showerror("Error", f"Failed to search block: {e}")
            
    def search_transaction(self):
        search_type = self.tx_search_type.get()
        search_value = self.tx_search_entry.get().strip()
        
        if not search_value:
            messagebox.showerror("Error", "Please enter a search value")
            return
            
        try:
            if search_type == "txid":
                tx = self.blockchain_indexer.tx_storage.get_transaction(search_value)
                
                self.tx_results.configure(state='normal')
                self.tx_results.delete(1.0, tk.END)
                
                if tx:
                    if hasattr(tx, 'to_dict'):
                        tx_data = tx.to_dict()
                    else:
                        tx_data = tx
                        
                    self.tx_results.insert(tk.END, json.dumps(tx_data, indent=4))
                    self.log_message(f"[Indexer] ✅ Found transaction: {search_value}")
                else:
                    self.tx_results.insert(tk.END, "Transaction not found")
                    self.log_message(f"[Indexer] ⚠️ Transaction not found: {search_value}")
                    
            else:  # Search by height
                txs = self.blockchain_indexer.tx_storage.get_transactions_by_block(int(search_value))
                
                self.tx_results.configure(state='normal')
                self.tx_results.delete(1.0, tk.END)
                
                if txs:
                    self.tx_results.insert(tk.END, f"Transactions at height {search_value}:\n\n")
                    for tx in txs:
                        if hasattr(tx, 'to_dict'):
                            tx_data = tx.to_dict()
                        else:
                            tx_data = tx
                            
                        self.tx_results.insert(tk.END, json.dumps(tx_data, indent=4))
                        self.tx_results.insert(tk.END, "\n\n")
                    self.log_message(f"[Indexer] ✅ Found {len(txs)} transactions at height {search_value}")
                else:
                    self.tx_results.insert(tk.END, f"No transactions found at height {search_value}")
                    self.log_message(f"[Indexer] ⚠️ No transactions at height: {search_value}")
                    
            self.tx_results.configure(state='disabled')
            
        except Exception as e:
            self.log_message(f"[Indexer] ❌ Error searching transaction: {e}")
            messagebox.showerror("Error", f"Failed to search transaction: {e}")
            
    def view_pending_transactions(self):
        try:
            mempool_tx = self.blockchain_indexer.mempool_storage.get_pending_transactions()
            
            self.tx_results.configure(state='normal')
            self.tx_results.delete(1.0, tk.END)
            
            if mempool_tx:
                self.tx_results.insert(tk.END, f"Pending Transactions ({len(mempool_tx)}):\n\n")
                for tx in mempool_tx:
                    if hasattr(tx, 'to_dict'):
                        tx_data = tx.to_dict()
                    else:
                        tx_data = tx
                        
                    self.tx_results.insert(tk.END, json.dumps(tx_data, indent=4))
                    self.tx_results.insert(tk.END, "\n\n")
                self.log_message(f"[Indexer] ✅ Displayed {len(mempool_tx)} pending transactions")
            else:
                self.tx_results.insert(tk.END, "No pending transactions")
                self.log_message("[Indexer] ⚠️ No pending transactions")
                
            self.tx_results.configure(state='disabled')
            
        except Exception as e:
            self.log_message(f"[Indexer] ❌ Error fetching pending transactions: {e}")
            messagebox.showerror("Error", f"Failed to get pending transactions: {e}")
            
    def find_utxos(self):
        address = self.utxo_address_entry.get().strip()
        if not address:
            messagebox.showerror("Error", "Please enter an address")
            return
            
        try:
            utxos = self.blockchain_indexer.utxo_storage.get_utxos_by_address(address)
            
            # Clear existing items
            for item in self.utxo_tree.get_children():
                self.utxo_tree.delete(item)
                
            if utxos:
                for utxo in utxos:
                    self.utxo_tree.insert('', 'end', values=(
                        utxo.get('tx_out_id', ''),
                        utxo.get('tx_out_index', ''),
                        str(utxo.get('amount', '0')),
                        "Yes" if utxo.get('locked', False) else "No"
                    ))
                self.log_message(f"[Indexer] ✅ Found {len(utxos)} UTXOs for address {address}")
            else:
                self.log_message(f"[Indexer] ⚠️ No UTXOs found for address {address}")
                
        except Exception as e:
            self.log_message(f"[Indexer] ❌ Error finding UTXOs: {e}")
            messagebox.showerror("Error", f"Failed to find UTXOs: {e}")
            
    def calculate_utxo_balance(self):
        address = self.utxo_address_entry.get().strip()
        if not address:
            messagebox.showerror("Error", "Please enter an address")
            return
            
        try:
            utxos = self.blockchain_indexer.utxo_storage.get_utxos_by_address(address)
            total_balance = sum(Decimal(utxo.get("amount", "0")) for utxo in utxos) if utxos else Decimal("0")
            
            self.utxo_balance_label.config(text=f"Balance: {total_balance} ZYC")
            self.log_message(f"[Indexer] ✅ Balance for {address}: {total_balance} ZYC")
            
        except Exception as e:
            self.log_message(f"[Indexer] ❌ Error calculating balance: {e}")
            messagebox.showerror("Error", f"Failed to calculate balance: {e}")
            
    def refresh_orphan_blocks(self):
        try:
            orphan_blocks = self.blockchain_indexer.orphan_blocks.get_all_orphans()
            
            # Clear existing items
            for item in self.orphan_tree.get_children():
                self.orphan_tree.delete(item)
                
            if orphan_blocks:
                for block in orphan_blocks:
                    if hasattr(block, 'to_dict'):
                        block_data = block.to_dict()
                    else:
                        block_data = block
                        
                    self.orphan_tree.insert('', 'end', values=(
                        block_data.get('hash', ''),
                        block_data.get('height', ''),
                        len(block_data.get('transactions', []))
                    ))
                self.log_message(f"[Indexer] ✅ Displayed {len(orphan_blocks)} orphan blocks")
            else:
                self.log_message("[Indexer] ⚠️ No orphan blocks found")
                
        except Exception as e:
            self.log_message(f"[Indexer] ❌ Error fetching orphan blocks: {e}")
            messagebox.showerror("Error", f"Failed to get orphan blocks: {e}")
            
    def export_last_500_blocks(self):
        try:
            self.blockchain_indexer.dump_last_500_blocks()
            self.export_status.config(text="✅ Last 500 blocks exported successfully")
            self.log_message("[Indexer] ✅ Exported last 500 blocks")
            
            # Open the export folder
            export_path = os.path.abspath(self.blockchain_indexer.export_folder)
            os.startfile(export_path)
            
        except Exception as e:
            self.export_status.config(text=f"❌ Export failed: {e}")
            self.log_message(f"[Indexer] ❌ Export failed: {e}")
            messagebox.showerror("Error", f"Failed to export blocks: {e}")
            
    def select_export_folder(self):
        folder = filedialog.askdirectory(title="Select Export Folder")
        if folder:
            self.blockchain_indexer.export_folder = folder
            self.export_status.config(text=f"Export folder set to: {folder}")
            self.log_message(f"[Indexer] Set export folder to: {folder}")



    def create_send_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Send Payment")
        
        # Recipient
        ttk.Label(tab, text="Recipient Address:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.recipient_entry = ttk.Entry(tab, width=50)
        self.recipient_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # Amount
        ttk.Label(tab, text="Amount (ZYC):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.amount_entry = ttk.Entry(tab)
        self.amount_entry.grid(row=1, column=1, padx=5, pady=5, sticky='w')
        
        # Transaction Type
        ttk.Label(tab, text="Transaction Type:").grid(row=2, column=0, padx=5, pady=5, sticky='w')
        self.tx_type_var = tk.StringVar(value="STANDARD")
        ttk.Radiobutton(tab, text="Standard", variable=self.tx_type_var, value="STANDARD").grid(row=2, column=1, padx=5, pady=5, sticky='w')
        ttk.Radiobutton(tab, text="Smart", variable=self.tx_type_var, value="SMART").grid(row=2, column=2, padx=5, pady=5, sticky='w')
        
        # Send Button
        send_btn = ttk.Button(tab, text="Send Payment", command=self.send_payment)
        send_btn.grid(row=3, column=0, columnspan=3, pady=10)
        
        # Status
        self.send_status = ttk.Label(tab, text="", foreground="green")
        self.send_status.grid(row=4, column=0, columnspan=3)
        
    def create_balance_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Check Balance")
        
        # Address display
        ttk.Label(tab, text=f"Your Address: {self.address}").pack(pady=5)
        
        # Balance display
        self.balance_label = ttk.Label(tab, text="Balance: Checking...", font=('Arial', 14))
        self.balance_label.pack(pady=10)
        
        # UTXO list
        ttk.Label(tab, text="UTXOs:").pack(pady=5)
        self.utxo_tree = ttk.Treeview(tab, columns=('txid', 'amount', 'locked'), show='headings')
        self.utxo_tree.heading('txid', text='Transaction ID')
        self.utxo_tree.heading('amount', text='Amount (ZYC)')
        self.utxo_tree.heading('locked', text='Locked')
        self.utxo_tree.column('txid', width=300)
        self.utxo_tree.column('amount', width=100)
        self.utxo_tree.column('locked', width=80)
        self.utxo_tree.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Refresh button
        refresh_btn = ttk.Button(tab, text="Refresh Balance", command=self.refresh_balance)
        refresh_btn.pack(pady=5)
        
    def create_tx_details_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Transaction Details")
        
        # TX ID input
        ttk.Label(tab, text="Transaction ID:").pack(pady=5)
        self.tx_id_entry = ttk.Entry(tab, width=70)
        self.tx_id_entry.pack(pady=5)
        
        # View button
        view_btn = ttk.Button(tab, text="View Details", command=self.view_transaction_details)
        view_btn.pack(pady=5)
        
        # Details display
        self.tx_details_text = scrolledtext.ScrolledText(tab, height=15, wrap=tk.WORD)
        self.tx_details_text.pack(expand=True, fill='both', padx=5, pady=5)
        
    def create_confirmations_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Track Confirmations")
        
        # TX ID input
        ttk.Label(tab, text="Transaction ID:").pack(pady=5)
        self.confirm_tx_id_entry = ttk.Entry(tab, width=70)
        self.confirm_tx_id_entry.pack(pady=5)
        
        # Check button
        check_btn = ttk.Button(tab, text="Check Confirmations", command=self.check_confirmations)
        check_btn.pack(pady=5)
        
        # Results display
        self.confirmations_text = scrolledtext.ScrolledText(tab, height=10, wrap=tk.WORD)
        self.confirmations_text.pack(expand=True, fill='both', padx=5, pady=5)
        
    def create_estimate_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Estimate TX Time")
        
        # Info label
        ttk.Label(tab, text="Estimate time for transaction inclusion:").pack(pady=10)
        
        # Estimate button
        estimate_btn = ttk.Button(tab, text="Estimate Now", command=self.estimate_tx_time)
        estimate_btn.pack(pady=5)
        
        # Results display
        self.estimate_text = scrolledtext.ScrolledText(tab, height=10, wrap=tk.WORD)
        self.estimate_text.pack(expand=True, fill='both', padx=5, pady=5)
        
    def create_log_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Transaction Log")
        
        # Log display
        self.log_output = scrolledtext.ScrolledText(tab, height=20, wrap=tk.WORD)
        self.log_output.pack(expand=True, fill='both', padx=5, pady=5)
        self.log_output.configure(state='disabled')
        
    def log_message(self, message):
        if self.log_output:
            self.log_output.configure(state='normal')
            self.log_output.insert(tk.END, message + "\n")
            self.log_output.configure(state='disabled')
            self.log_output.see(tk.END)
        
    def send_payment(self):
        recipient = self.recipient_entry.get().strip()
        amount_str = self.amount_entry.get().strip()
        tx_type = self.tx_type_var.get()
        
        if not recipient or not amount_str:
            messagebox.showerror("Error", "Recipient and amount are required")
            return
            
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError
        except:
            messagebox.showerror("Error", "Invalid amount")
            return
            
        priv_key = self.key_manager.keys["mainnet"]["keys"][
            self.key_manager.keys["mainnet"]["defaults"]["miner"]
        ]["private_key"]
        pub_key = self.address
        
        self.log_message(f"\n[PaymentProcessor] 💸 Starting Payment TX")
        self.log_message(f"   ↳ Amount: {amount} ZYC | Type: {tx_type} | To: {recipient}")
        
        tx_id = self.processor.send_payment(
            sender_priv_key=priv_key,
            sender_pub_key=pub_key,
            recipient_address=recipient,
            amount=amount,
            tx_type=tx_type
        )
        
        if tx_id:
            self.send_status.config(text=f"✅ Transaction sent! TXID: {tx_id}", foreground="green")
            self.log_message(f"[Success] ✅ TX Sent: {tx_id}")
        else:
            self.send_status.config(text="❌ Failed to send transaction", foreground="red")
            self.log_message("[ERROR] ❌ Transaction failed")
            
    def refresh_balance(self):
        self.log_message("\n[Balance] 🔍 Checking balance...")
        utxos = self.utxo_manager.utxo_storage.get_utxos_by_address(self.address)
        total = Decimal("0")
        
        # Clear existing items
        for item in self.utxo_tree.get_children():
            self.utxo_tree.delete(item)
            
        for u in utxos:
            amt = Decimal(u["amount"])
            total += amt
            self.utxo_tree.insert('', 'end', values=(
                u['tx_out_id'],
                str(amt),
                "Yes" if u.get('locked', False) else "No"
            ))
            
        self.balance_label.config(text=f"Balance: {total} ZYC")
        self.log_message(f"[Balance] 💰 Total Available: {total} ZYC")
        
    def view_transaction_details(self):
        tx_id = self.tx_id_entry.get().strip()
        if not tx_id:
            messagebox.showerror("Error", "Please enter a transaction ID")
            return
            
        self.log_message(f"\n[TX Details] 🔍 Looking up transaction {tx_id}")
        tx_data = self.tx_storage.get_transaction(tx_id)
        
        self.tx_details_text.configure(state='normal')
        self.tx_details_text.delete(1.0, tk.END)
        
        if not tx_data:
            self.tx_details_text.insert(tk.END, "Transaction not found")
            self.log_message("[TX Details] ❌ TX not found")
        else:
            for key, value in tx_data.items():
                self.tx_details_text.insert(tk.END, f"{key}: {value}\n")
            self.log_message(f"[TX Details] ✅ Found transaction with {len(tx_data)} details")
            
        self.tx_details_text.configure(state='disabled')
        
    def check_confirmations(self):
        tx_id = self.confirm_tx_id_entry.get().strip()
        if not tx_id:
            messagebox.showerror("Error", "Please enter a transaction ID")
            return
            
        self.log_message(f"\n[Confirmations] 🔍 Checking confirmations for {tx_id}")
        tx_data = self.tx_storage.get_transaction(tx_id)
        
        self.confirmations_text.configure(state='normal')
        self.confirmations_text.delete(1.0, tk.END)
        
        if not tx_data:
            self.confirmations_text.insert(tk.END, "Transaction not found")
            self.log_message("[Confirmations] ❌ TX not found")
        else:
            block_hash = tx_data.get("block_hash")
            if not block_hash:
                self.confirmations_text.insert(tk.END, "Transaction not yet confirmed")
                self.log_message("[Confirmations] ⏳ TX not confirmed yet")
            else:
                current_height = self.blockchain.get_latest_block().index
                block_height = tx_data.get("block_height", 0)
                confirmations = max(0, current_height - block_height + 1)
                
                self.confirmations_text.insert(tk.END, f"Confirmations: {confirmations}\n")
                
                if confirmations == 0:
                    self.confirmations_text.insert(tk.END, "Status: Waiting for inclusion...")
                    self.log_message("[Confirmations] ⏳ Waiting for inclusion...")
                elif confirmations < 3:
                    self.confirmations_text.insert(tk.END, "Status: Not fully confirmed")
                    self.log_message("[Confirmations] ⚠️ Not fully confirmed")
                else:
                    self.confirmations_text.insert(tk.END, "Status: Safe to consider final")
                    self.log_message("[Confirmations] ✅ Safe to consider final")
                    
        self.confirmations_text.configure(state='disabled')
        
    def estimate_tx_time(self):
        self.log_message("\n[Estimate] 🧠 Estimating TX inclusion time...")
        total_pending = (self.standard_mempool.get_transaction_count() + 
                         self.smart_mempool.get_transaction_count())
        
        self.estimate_text.configure(state='normal')
        self.estimate_text.delete(1.0, tk.END)
        
        self.estimate_text.insert(tk.END, f"Pending in mempool: {total_pending} transactions\n\n")
        
        if total_pending == 0:
            self.estimate_text.insert(tk.END, "Likely included in the next block (~10s)")
            self.log_message("[Estimate] ✅ Likely next block (~10s)")
        elif total_pending < 50:
            self.estimate_text.insert(tk.END, "Estimated time: 1–2 blocks (~10–20s)")
            self.log_message("[Estimate] ⌛ 1-2 blocks (~10-20s)")
        else:
            self.estimate_text.insert(tk.END, "High network load. Could take multiple blocks (~30s+)")
            self.log_message("[Estimate] ⏱️ High network load (~30s+)")
            
        self.estimate_text.configure(state='disabled')

