import sys
import os
from typing import List, Optional

#!/usr/bin/env python3

import os
import sys

# Ensure correct path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Zyiron_Chain.main.send import PaymentProcessor  # Your import works now

#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import json
import os
import time
from datetime import datetime
from decimal import Decimal
import threading
import atexit
import sys


# Import all required modules
from Zyiron_Chain.network.peerconstant import PeerConstants
from Zyiron_Chain.storage.block_storage import BlockStorage
from Zyiron_Chain.storage.tx_storage import TxStorage
from Zyiron_Chain.storage.utxostorage import UTXOStorage
from Zyiron_Chain.storage.mempool_storage import MempoolStorage
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.storage.orphan_blocks import OrphanBlocks
from Zyiron_Chain.blockchain.blockchain import Blockchain
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.miner.miner import Miner
from Zyiron_Chain.transactions.transaction_manager import TransactionManager
from Zyiron_Chain.accounts.key_manager import KeyManager
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.blockchain.block_manager import BlockManager
from Zyiron_Chain.blockchain.genesis_block import GenesisBlockManager
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.mempool.standardmempool import StandardMempool
from Zyiron_Chain.mempool.smartmempool import SmartMempool
from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.transactions.txin import TransactionIn
from Zyiron_Chain.transactions.txout import TransactionOut

class BlockchainUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Zyiron Chain Explorer")
        self.root.geometry("1200x800")
        self.mining_active = False
        self.mining_thread = None
        
        # Setup colors
        self.bg_color = "#1e1e2e"  # Dark purple
        self.fg_color = "#ffffff"  # White
        self.accent_color = "#a162e8"  # Light purple
        self.text_color = "#cdd6f4"  # Light gray
        
        # Configure root window
        self.root.configure(bg=self.bg_color)
        
        # Initialize core attributes to None first
        self.key_manager = None
        self.blockchain = None
        self.block_storage = None
        self.tx_storage = None
        self.utxo_manager = None
        self.utxo_storage = None
        self.transaction_manager = None
        self.mempool_storage = None
        self.block_manager = None
        self.genesis_block_manager = None
        self.miner = None
        self.standard_mempool = None
        self.smart_mempool = None
        self.payment_processor = None
        self.orphan_blocks = None
        self.wallet_address = None
        
        # Create basic UI elements first (without dependencies)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both')
        self.log_output = scrolledtext.ScrolledText(self.notebook, height=20, wrap=tk.WORD)
        self.log_output.pack(expand=True, fill='both', padx=5, pady=5)
        self.log_output.configure(state='disabled')
        
        # Now initialize blockchain components
        self.initialize_blockchain()
        
        # Then setup the full UI
        self.setup_ui()
        
        # Start mining monitor
        self.start_mining_monitor()
        
        # Register cleanup
        atexit.register(self.cleanup)

        self.root.bind_class("Text", "<Button-3><ButtonRelease-3>", self.show_right_click_menu)


    def initialize_blockchain(self):
        """Initialize all blockchain components with proper error handling"""
        try:
            # 1. Initialize KeyManager
            self.key_manager = KeyManager()

            # 2. Initialize FeeModel
            self.fee_model = FeeModel(Constants.MAX_SUPPLY)

            # 3. Initialize TxStorage
            self.tx_storage = TxStorage(fee_model=self.fee_model)

            # 4. Initialize Block Storage
           # 4. Initialize Block Storage
            self.block_storage = BlockStorage(
                tx_storage=self.tx_storage,
                key_manager=self.key_manager,
                utxo_storage=None  # Will set this later after UTXOManager is ready
            )
            # 5. Initialize UTXOStorage (with fallback support)
            self.utxo_storage = UTXOStorage(
                utxo_manager=None,  # Placeholder for now
                block_storage=self.block_storage
            )

            # 6. Initialize UTXOManager with injected UTXOStorage
            self.utxo_manager = UTXOManager(self.utxo_storage)

            # 7. Inject the UTXOManager back into UTXOStorage
            self.block_storage.utxo_storage = self.utxo_storage

            # 8. Initialize Transaction Manager
            self.transaction_manager = TransactionManager(
                block_storage=self.block_storage,
                tx_storage=self.tx_storage,
                utxo_manager=self.utxo_manager,
                key_manager=self.key_manager
            )

            # 9. Initialize Mempool Storage
            self.mempool_storage = MempoolStorage(self.transaction_manager)

            # 10. Initialize Blockchain
            self.blockchain = Blockchain(
                tx_storage=self.tx_storage,
                utxo_storage=self.utxo_storage,
                transaction_manager=self.transaction_manager,
                key_manager=self.key_manager,
                full_block_store=self.block_storage
            )

            # 11. Initialize BlockManager
            self.block_manager = BlockManager(
                blockchain=self.blockchain,
                block_storage=self.block_storage,
                block_metadata=self.block_storage,
                tx_storage=self.tx_storage,
                transaction_manager=self.transaction_manager
            )

            # 12. Initialize Genesis Block Manager
            self.genesis_block_manager = GenesisBlockManager(
                block_storage=self.block_storage,
                key_manager=self.key_manager,
                chain=self.block_manager.blockchain,
                block_manager=self.block_manager
            )

            # 13. Initialize Miner
            self.miner = Miner(
                blockchain=self.blockchain,
                block_manager=self.block_manager,
                block_storage=self.block_storage,
                transaction_manager=self.transaction_manager,
                key_manager=self.key_manager,
                mempool_storage=self.mempool_storage,
                utxo_storage=self.utxo_storage,
                genesis_block_manager=self.genesis_block_manager
            )

            # 14. Initialize Mempools
            self.standard_mempool = StandardMempool(utxo_storage=self.utxo_storage)
            self.smart_mempool = SmartMempool(utxo_storage=self.utxo_storage)

            # 15. Initialize Payment Processor with fee_model passed in
            self.payment_processor = PaymentProcessor(
                utxo_manager=self.utxo_manager,
                tx_storage=self.tx_storage,
                standard_mempool=self.standard_mempool,
                smart_mempool=self.smart_mempool,
                key_manager=self.key_manager,
                fee_model=self.fee_model  # ✅ Inject fee_model
            )

            # 16. Initialize Orphan Block Store
            self.orphan_blocks = OrphanBlocks()

            # 17. Set wallet address
            self.wallet_address = self.key_manager.get_default_public_key()

            self.log_message("[System] Blockchain components initialized successfully")

        except Exception as e:
            error_msg = f"[ERROR] Failed to initialize blockchain: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("Initialization Error", "Failed to initialize blockchain components")
            raise RuntimeError("Blockchain initialization failed") from e


    def setup_ui(self):
        """Setup the main UI components"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both')
        
        # Create tabs
        self.create_dashboard_tab()
        self.create_blockchain_tab()
        self.create_mining_tab()
        self.create_transactions_tab()
        self.create_wallet_tab()
        self.create_explorer_tab()
        self.create_log_tab()
        
        # Apply styling
        self.apply_styles()

    def apply_styles(self):
        """Apply custom styling to widgets"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure('.', background=self.bg_color, foreground=self.fg_color)
        style.configure('TNotebook', background=self.bg_color, borderwidth=0)
        style.configure('TNotebook.Tab', background=self.bg_color, foreground=self.fg_color, 
                       padding=[10, 5], font=('Arial', 10, 'bold'))
        style.map('TNotebook.Tab', background=[('selected', self.accent_color)])
        
        style.configure('TFrame', background=self.bg_color)
        style.configure('TLabel', background=self.bg_color, foreground=self.fg_color)
        style.configure('TButton', background=self.accent_color, foreground='black', 
                       font=('Arial', 10), padding=5)
        style.map('TButton', background=[('active', '#b583e8')])
        
        style.configure('Treeview', background='#2e2e3e', foreground=self.fg_color, 
                       fieldbackground='#2e2e3e')
        style.map('Treeview', background=[('selected', self.accent_color)])
        style.configure('Treeview.Heading', background='#3e3e4e', foreground=self.fg_color)
        
        style.configure('TEntry', fieldbackground='#2e2e3e', foreground=self.fg_color)
        style.configure('TCombobox', fieldbackground='#2e2e3e', foreground=self.fg_color)

    def create_dashboard_tab(self):
        """Create the dashboard tab with overview information"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Dashboard")
        
        # Main frame
        main_frame = ttk.Frame(tab)
        main_frame.pack(expand=True, fill='both', padx=10, pady=10)
        
        # Blockchain info frame
        info_frame = ttk.LabelFrame(main_frame, text="Blockchain Information")
        info_frame.pack(fill='x', padx=5, pady=5)
        
        # Network info
        ttk.Label(info_frame, text=f"Network: {Constants.NETWORK}").grid(row=0, column=0, sticky='w', padx=5, pady=2)
        ttk.Label(info_frame, text=f"Version: {Constants.VERSION}").grid(row=1, column=0, sticky='w', padx=5, pady=2)
        
        # Blockchain stats
        self.block_height_label = ttk.Label(info_frame, text="Block Height: Loading...")
        self.block_height_label.grid(row=2, column=0, sticky='w', padx=5, pady=2)
        
        self.difficulty_label = ttk.Label(info_frame, text="Difficulty: Loading...")
        self.difficulty_label.grid(row=3, column=0, sticky='w', padx=5, pady=2)
        
        self.tx_count_label = ttk.Label(info_frame, text="Total Transactions: Loading...")
        self.tx_count_label.grid(row=4, column=0, sticky='w', padx=5, pady=2)
        
        # Mempool info frame
        mempool_frame = ttk.LabelFrame(main_frame, text="Mempool Information")
        mempool_frame.pack(fill='x', padx=5, pady=5)
        
        self.mempool_size_label = ttk.Label(mempool_frame, text="Pending Transactions: Loading...")
        self.mempool_size_label.pack(anchor='w', padx=5, pady=2)
        
        self.mempool_size_standard_label = ttk.Label(mempool_frame, text="Standard TX: Loading...")
        self.mempool_size_standard_label.pack(anchor='w', padx=5, pady=2)
        
        self.mempool_size_smart_label = ttk.Label(mempool_frame, text="Smart TX: Loading...")
        self.mempool_size_smart_label.pack(anchor='w', padx=5, pady=2)
        
        # UTXO info frame
        utxo_frame = ttk.LabelFrame(main_frame, text="UTXO Information")
        utxo_frame.pack(fill='x', padx=5, pady=5)
        
        self.utxo_count_label = ttk.Label(utxo_frame, text="Total UTXOs: Loading...")
        self.utxo_count_label.pack(anchor='w', padx=5, pady=2)
        
        self.orphan_blocks_label = ttk.Label(utxo_frame, text="Orphan Blocks: Loading...")
        self.orphan_blocks_label.pack(anchor='w', padx=5, pady=2)
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill='x', padx=5, pady=10)
        
        ttk.Button(buttons_frame, text="Refresh Data", command=self.update_dashboard).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Validate Blockchain", command=self.validate_blockchain).pack(side='left', padx=5)
        
        self.avg_mine_time_label = ttk.Label(info_frame, text="Avg Mining Time: Calculating...")
        self.avg_mine_time_label.grid(row=5, column=0, sticky='w', padx=5, pady=2)
                
        # Initial update
        self.update_dashboard()

    def create_blockchain_tab(self):
        """Create the blockchain tab with block explorer"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Blockchain")
        
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
        
        # Recent blocks frame
        recent_frame = ttk.LabelFrame(tab, text="Recent Blocks")
        recent_frame.pack(fill='both', padx=5, pady=5)
        
        # Treeview for recent blocks
        self.recent_blocks_tree = ttk.Treeview(recent_frame, columns=('height', 'hash', 'timestamp', 'tx_count'), show='headings')
        self.recent_blocks_tree.heading('height', text='Height')
        self.recent_blocks_tree.heading('hash', text='Hash')
        self.recent_blocks_tree.heading('timestamp', text='Timestamp')
        self.recent_blocks_tree.heading('tx_count', text='TX Count')
        self.recent_blocks_tree.column('height', width=80, anchor='center')
        self.recent_blocks_tree.column('hash', width=250)
        self.recent_blocks_tree.column('timestamp', width=150)
        self.recent_blocks_tree.column('tx_count', width=80, anchor='center')
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(recent_frame, orient="vertical", command=self.recent_blocks_tree.yview)
        self.recent_blocks_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        self.recent_blocks_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Load recent blocks
        self.load_recent_blocks()

    def create_mining_tab(self):
        """Create the mining tab with mining controls"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Mining")
        
        # Mining controls frame
        controls_frame = ttk.LabelFrame(tab, text="Mining Controls")
        controls_frame.pack(fill='x', padx=5, pady=5)
        
        # Mining status
        self.mining_status = ttk.Label(controls_frame, text="Mining: Stopped", font=('Arial', 12))
        self.mining_status.pack(pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(controls_frame)
        btn_frame.pack(pady=5)
        
        self.start_mining_btn = ttk.Button(btn_frame, text="Start Mining", command=self.start_mining)
        self.start_mining_btn.pack(side='left', padx=5)
        
        self.stop_mining_btn = ttk.Button(btn_frame, text="Stop Mining", command=self.stop_mining, state='disabled')
        self.stop_mining_btn.pack(side='left', padx=5)
        
        # Mining stats frame
        stats_frame = ttk.LabelFrame(tab, text="Mining Statistics")
        stats_frame.pack(fill='x', padx=5, pady=5)
        
        self.hashrate_label = ttk.Label(stats_frame, text="Hashrate: 0 H/s")
        self.hashrate_label.pack(anchor='w', padx=5, pady=2)
        
        self.blocks_mined_label = ttk.Label(stats_frame, text="Blocks Mined: 0")
        self.blocks_mined_label.pack(anchor='w', padx=5, pady=2)
        
        self.last_block_time_label = ttk.Label(stats_frame, text="Last Block Time: Never")
        self.last_block_time_label.pack(anchor='w', padx=5, pady=2)
        
        # Mining log frame
        log_frame = ttk.LabelFrame(tab, text="Mining Log")
        log_frame.pack(expand=True, fill='both', padx=5, pady=5)
        
        self.mining_log = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD)
        self.mining_log.pack(expand=True, fill='both')
        self.mining_log.configure(state='disabled')

    def create_transactions_tab(self):
        """Create the transactions tab for sending and viewing transactions"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Transactions")
        
        # Notebook for transaction sub-tabs
        tx_notebook = ttk.Notebook(tab)
        tx_notebook.pack(expand=True, fill='both')
        
        # Send transaction tab
        self.create_send_tx_tab(tx_notebook)
        
        # View transactions tab
        self.create_view_tx_tab(tx_notebook)
        
        # Pending transactions tab
        self.create_pending_tx_tab(tx_notebook)

    def create_send_tx_tab(self, notebook):
        """Create the send transaction tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Send")
        
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
        
        # Fee display
        self.fee_label = ttk.Label(tab, text="Estimated Fee: 0 ZYC")
        self.fee_label.grid(row=3, column=0, columnspan=3, pady=2)
        
        # Send Button
        send_btn = ttk.Button(tab, text="Send Payment", command=self.send_payment)
        send_btn.grid(row=4, column=0, columnspan=3, pady=10)
        
        # Status
        self.send_status = ttk.Label(tab, text="", foreground="green")
        self.send_status.grid(row=5, column=0, columnspan=3)

    def get_latest_block(self):
        """Get the latest block in the chain"""
        if not self.chain:
            return None
        return self.chain[-1]
    
    def create_view_tx_tab(self, notebook):
        """Create the view transaction tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Details")
        
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
        self.tx_details_text.configure(state='disabled')

    def create_pending_tx_tab(self, notebook):
        """Create the pending transactions tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Pending")
        
        # Refresh button
        refresh_btn = ttk.Button(tab, text="Refresh Pending Transactions", command=self.refresh_pending_tx)
        refresh_btn.pack(pady=5)
        
        # Treeview for pending transactions
        self.pending_tx_tree = ttk.Treeview(tab, columns=('txid', 'type', 'amount', 'fee'), show='headings')
        self.pending_tx_tree.heading('txid', text='Transaction ID')
        self.pending_tx_tree.heading('type', text='Type')
        self.pending_tx_tree.heading('amount', text='Amount')
        self.pending_tx_tree.heading('fee', text='Fee')
        self.pending_tx_tree.column('txid', width=250)
        self.pending_tx_tree.column('type', width=80)
        self.pending_tx_tree.column('amount', width=100)
        self.pending_tx_tree.column('fee', width=80)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self.pending_tx_tree.yview)
        self.pending_tx_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        self.pending_tx_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Load pending transactions
        self.refresh_pending_tx()

    def create_wallet_tab(self):
        """Create the wallet tab with balance and UTXO information"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Wallet")
        
        # Address display
        self.wallet_address = self.key_manager.get_default_public_key()
        ttk.Label(tab, text=f"Your Address: {self.wallet_address}", font=('Arial', 10)).pack(pady=5)
        
        # Balance display
        balance_frame = ttk.Frame(tab)
        balance_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(balance_frame, text="Balance:", font=('Arial', 12)).pack(side='left', padx=5)
        self.balance_label = ttk.Label(balance_frame, text="0 ZYC", font=('Arial', 12, 'bold'))
        self.balance_label.pack(side='left', padx=5)
        
        # UTXO frame
        utxo_frame = ttk.LabelFrame(tab, text="UTXOs")
        utxo_frame.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Treeview for UTXOs
        self.utxo_tree = ttk.Treeview(utxo_frame, columns=('txid', 'index', 'amount', 'locked'), show='headings')
        self.utxo_tree.heading('txid', text='Transaction ID')
        self.utxo_tree.heading('index', text='Output Index')
        self.utxo_tree.heading('amount', text='Amount (ZYC)')
        self.utxo_tree.heading('locked', text='Locked')
        self.utxo_tree.column('txid', width=250)
        self.utxo_tree.column('index', width=80)
        self.utxo_tree.column('amount', width=100)
        self.utxo_tree.column('locked', width=80)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(utxo_frame, orient="vertical", command=self.utxo_tree.yview)
        self.utxo_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        self.utxo_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Buttons frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Refresh Balance", command=self.refresh_wallet).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Generate New Address", command=self.generate_new_address).pack(side='left', padx=5)
        
        # Initial refresh
        self.refresh_wallet()

    def create_explorer_tab(self):
        """Create the explorer tab with advanced search options"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Explorer")
        
        # Notebook for explorer sub-tabs
        explorer_notebook = ttk.Notebook(tab)
        explorer_notebook.pack(expand=True, fill='both')
        
        # Transaction explorer
        self.create_tx_explorer_tab(explorer_notebook)
        
        # UTXO explorer
        self.create_utxo_explorer_tab(explorer_notebook)
        
        # Orphan blocks explorer
        self.create_orphan_blocks_tab(explorer_notebook)
        
        # Export tools
        self.create_export_tools_tab(explorer_notebook)

    def create_tx_explorer_tab(self, notebook):
        """Create transaction explorer sub-tab"""
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
        
        # Results display
        self.tx_results = scrolledtext.ScrolledText(tab, height=15, wrap=tk.WORD)
        self.tx_results.pack(expand=True, fill='both', padx=5, pady=5)
        self.tx_results.configure(state='disabled')

    def create_utxo_explorer_tab(self, notebook):
        """Create UTXO explorer sub-tab"""
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
        self.utxo_explorer_tree = ttk.Treeview(tab, columns=('txid', 'index', 'amount', 'locked'), show='headings')
        self.utxo_explorer_tree.heading('txid', text='Transaction ID')
        self.utxo_explorer_tree.heading('index', text='Output Index')
        self.utxo_explorer_tree.heading('amount', text='Amount (ZYC)')
        self.utxo_explorer_tree.heading('locked', text='Locked')
        self.utxo_explorer_tree.column('txid', width=250)
        self.utxo_explorer_tree.column('index', width=80)
        self.utxo_explorer_tree.column('amount', width=100)
        self.utxo_explorer_tree.column('locked', width=80)
        self.utxo_explorer_tree.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Balance label
        self.utxo_balance_label = ttk.Label(tab, text="Balance: ", font=('Arial', 12))
        self.utxo_balance_label.pack(pady=5)

    def create_orphan_blocks_tab(self, notebook):
        """Create orphan blocks explorer sub-tab"""
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
        """Create export tools sub-tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Export Tools")
        
        # Export buttons
        ttk.Button(tab, text="Export Last 500 Blocks", command=self.export_last_500_blocks).pack(pady=10)
        ttk.Button(tab, text="Select Custom Export Folder", command=self.select_export_folder).pack(pady=5)
        
        # Status label
        self.export_status = ttk.Label(tab, text="")
        self.export_status.pack(pady=5)

    def create_log_tab(self):
        """Create the log tab for system messages"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="System Log")
        
        # Log display
        self.log_output = scrolledtext.ScrolledText(tab, height=20, wrap=tk.WORD)
        self.log_output.pack(expand=True, fill='both', padx=5, pady=5)
        self.log_output.configure(state='disabled')
        
        # Clear button
        ttk.Button(tab, text="Clear Log", command=self.clear_log).pack(pady=5)

    def log_message(self, message):
        """Log a message to the system log"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"
            
            if hasattr(self, 'log_output'):
                self.log_output.configure(state='normal')
                self.log_output.insert(tk.END, formatted_message + "\n")
                self.log_output.configure(state='disabled')
                self.log_output.see(tk.END)
            
            # Always print to console for debugging
            print(formatted_message)
        except Exception as e:
            print(f"Error logging message: {e} - Original message: {message}")

    def clear_log(self):
        """Clear the system log"""
        self.log_output.configure(state='normal')
        self.log_output.delete(1.0, tk.END)
        self.log_output.configure(state='disabled')

    def update_dashboard(self):
        """Update the dashboard with current blockchain information"""
        try:
            # Blockchain info
            latest_block = self.block_storage.get_latest_block()

            if latest_block is None:
                self.block_height_label.config(text="Block Height: 0")
                self.difficulty_label.config(text="Difficulty: 0")
            else:
                index = latest_block.index if hasattr(latest_block, "index") else latest_block.get("index", "N/A")
                difficulty = latest_block.difficulty if hasattr(latest_block, "difficulty") else latest_block.get("difficulty", "N/A")
                self.block_height_label.config(text=f"Block Height: {index}")
                self.difficulty_label.config(text=f"Difficulty: {difficulty}")

            # Transaction count
            tx_count = self.tx_storage.get_transaction_count()
            self.tx_count_label.config(text=f"Total Transactions: {tx_count}")

            # Mempool info
            mempool_size = self.mempool_storage.get_pending_transaction_count()
            self.mempool_size_label.config(text=f"Pending Transactions: {mempool_size}")

            # UTXO info
            utxo_count = len(self.utxo_storage.get_all_utxos())
            self.utxo_count_label.config(text=f"Total UTXOs: {utxo_count}")

            # Orphan blocks
            orphan_count = len(self.orphan_blocks.get_all_orphans())
            self.orphan_blocks_label.config(text=f"Orphan Blocks: {orphan_count}")

            # ✅ Average mining time (last 10 blocks)
            blocks = self.block_storage.get_all_blocks()[-10:]
            if len(blocks) >= 2:
                timestamps = [b.timestamp if hasattr(b, "timestamp") else b.get("timestamp", 0) for b in blocks]
                intervals = [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]
                avg_mine_time = round(sum(intervals) / len(intervals), 2)
                self.avg_mine_time_label.config(text=f"Avg Mining Time: {avg_mine_time} sec")
            else:
                self.avg_mine_time_label.config(text="Avg Mining Time: N/A")

            self.log_message("[Dashboard] Updated blockchain statistics")

        except Exception as e:
            print(f"[Dashboard ERROR] ❌ Failed to update: {e}")



    def show_right_click_menu(self, event):
        """Show a right-click menu to copy selected text."""
        widget = event.widget
        if not isinstance(widget, tk.Text):
            return

        try:
            menu = tk.Menu(widget, tearoff=0)
            menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()



    def load_recent_blocks(self):
        """Load recent blocks into the blockchain tab"""
        try:
            # Clear existing items
            for item in self.recent_blocks_tree.get_children():
                self.recent_blocks_tree.delete(item)
            
            # Get recent blocks (last 10)
            blocks = self.block_storage.get_all_blocks()[-10:]
            
            for block in reversed(blocks):
                if hasattr(block, 'to_dict'):
                    block_data = block.to_dict()
                else:
                    block_data = block
                
                self.recent_blocks_tree.insert('', 'end', values=(
                    block_data.get('index', ''),
                    block_data.get('hash', '')[:16] + '...',
                    datetime.fromtimestamp(block_data.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M'),
                    len(block_data.get('transactions', []))
                ))
            
            self.log_message("[Blockchain] Loaded recent blocks")
        except Exception as e:
            self.log_message(f"[ERROR] Failed to load recent blocks: {e}")

    def search_block(self):
        """Search for a block by height or hash"""
        search_type = self.block_search_type.get()
        search_value = self.block_search_entry.get().strip()
        
        if not search_value:
            messagebox.showerror("Error", "Please enter a search value")
            return
            
        try:
            if search_type == "height":
                block = self.block_storage.get_block_by_height(int(search_value))
            else:
                block = self.block_storage.get_block_by_hash(search_value)
                
            self.block_results.configure(state='normal')
            self.block_results.delete(1.0, tk.END)
            
            if block:
                if hasattr(block, 'to_dict'):
                    block_data = block.to_dict()
                else:
                    block_data = block
                    
                self.block_results.insert(tk.END, json.dumps(block_data, indent=4))
                self.log_message(f"[Block Explorer] Found block: {search_value}")
            else:
                self.block_results.insert(tk.END, "Block not found")
                self.log_message(f"[Block Explorer] Block not found: {search_value}")
                
            self.block_results.configure(state='disabled')
            
        except Exception as e:
            self.log_message(f"[ERROR] Error searching block: {e}")
            messagebox.showerror("Error", f"Failed to search block: {e}")

    def start_mining(self):
        """Start the mining process"""
        if self.mining_active:
            return
            
        self.mining_active = True
        self.mining_status.config(text="Mining: Running", foreground="green")
        self.start_mining_btn.config(state='disabled')
        self.stop_mining_btn.config(state='normal')
        
        # Start mining in a separate thread
        self.mining_thread = threading.Thread(target=self.mining_loop, daemon=True)
        self.mining_thread.start()
        
        self.log_message("[Miner] Mining started")

    def stop_mining(self):
        """Stop the mining process"""
        if not self.mining_active:
            return
            
        self.mining_active = False
        self.mining_status.config(text="Mining: Stopped", foreground="red")
        self.start_mining_btn.config(state='normal')
        self.stop_mining_btn.config(state='disabled')
        
        self.log_message("[Miner] Mining stopped")

    def mining_loop(self):
        """Mining loop that runs in a separate thread"""
        blocks_mined = 0
        start_time = time.time()
        
        while self.mining_active:
            try:
                # Mine a block
                result = self.miner.mine_block()
                
                if result and result.get('success'):
                    blocks_mined += 1
                    block_hash = result.get('block_hash', '')
                    
                    # Update UI in main thread
                    self.root.after(0, self.update_mining_stats, blocks_mined, block_hash)
                    
                    # Log the mined block
                    self.log_message(f"[Miner] Mined block {block_hash}")
                    
                    # Update recent blocks
                    self.root.after(0, self.load_recent_blocks)
                    
                    # Update dashboard
                    self.root.after(0, self.update_dashboard)
                    
            except Exception as e:
                self.log_message(f"[ERROR] Mining error: {e}")
                time.sleep(1)
                
            # Small delay to prevent CPU overload
            time.sleep(0.1)

    def update_mining_stats(self, blocks_mined, block_hash):
        """Update mining statistics"""
        self.blocks_mined_label.config(text=f"Blocks Mined: {blocks_mined}")
        self.last_block_time_label.config(text=f"Last Block Time: {datetime.now().strftime('%H:%M:%S')}")
        
        # Add to mining log
        self.mining_log.configure(state='normal')
        self.mining_log.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] Mined block: {block_hash}\n")
        self.mining_log.configure(state='disabled')
        self.mining_log.see(tk.END)

    def start_mining_monitor(self):
        """Start a thread to monitor mining stats"""
        def monitor_loop():
            while True:
                if self.mining_active:
                    # Update hashrate (simulated for now)
                    self.root.after(0, self.hashrate_label.config, {"text": "Hashrate: Calculating..."})
                
                time.sleep(5)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()

    def send_payment(self):
        """Send a payment transaction"""
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
        pub_key = self.wallet_address
        
        self.log_message(f"\n[Payment] Starting transaction: {amount} ZYC to {recipient}")
        
        tx_id = self.payment_processor.send_payment(
            sender_priv_key=priv_key,
            sender_pub_key=pub_key,
            recipient_address=recipient,
            amount=amount,
            tx_type=tx_type
        )
        
        if tx_id:
            self.send_status.config(text=f"✅ Transaction sent! TXID: {tx_id}", foreground="green")
            self.log_message(f"[Payment] Transaction sent: {tx_id}")
            
            # Refresh pending transactions
            self.refresh_pending_tx()
            
            # Refresh wallet balance
            self.refresh_wallet()
        else:
            self.send_status.config(text="❌ Failed to send transaction", foreground="red")
            self.log_message("[ERROR] Transaction failed")

    def view_transaction_details(self):
        """View details of a transaction"""
        tx_id = self.tx_id_entry.get().strip()
        if not tx_id:
            messagebox.showerror("Error", "Please enter a transaction ID")
            return
            
        self.log_message(f"\n[Transaction] Looking up transaction {tx_id}")
        tx_data = self.tx_storage.get_transaction(tx_id)
        
        self.tx_details_text.configure(state='normal')
        self.tx_details_text.delete(1.0, tk.END)
        
        if not tx_data:
            self.tx_details_text.insert(tk.END, "Transaction not found")
            self.log_message("[Transaction] TX not found")
        else:
            for key, value in tx_data.items():
                self.tx_details_text.insert(tk.END, f"{key}: {value}\n")
            self.log_message(f"[Transaction] Found transaction with {len(tx_data)} details")
            
        self.tx_details_text.configure(state='disabled')

    def refresh_pending_tx(self):
        """Refresh the pending transactions list"""
        try:
            # Clear existing items
            for item in self.pending_tx_tree.get_children():
                self.pending_tx_tree.delete(item)

            # Get pending transactions from MempoolStorage
            pending_tx_list = self.mempool_storage.get_pending_transactions()

            if not pending_tx_list:
                self.log_message("[Pending TX] No pending transactions")
                return

            count = 0
            for tx in pending_tx_list:
                try:
                    # Convert to dict safely
                    tx_data = tx.to_dict() if hasattr(tx, "to_dict") else tx
                    tx_id = tx_data.get("tx_id", "")
                    tx_type = tx_data.get("tx_type") or tx_data.get("type", "UNKNOWN")
                    amount = str(tx_data.get("amount", "0"))
                    fee = str(tx_data.get("fee", "0"))

                    # Insert into tree
                    self.pending_tx_tree.insert('', 'end', values=(tx_id, tx_type, f"{amount} ZYC", f"{fee} ZYC"))
                    count += 1
                except Exception as tx_error:
                    self.log_message(f"[Pending TX] ⚠️ Skipped malformed transaction: {tx_error}")

            self.log_message(f"[Pending TX] ✅ Loaded {count} pending transactions")

        except Exception as e:
            self.log_message(f"[ERROR] Failed to refresh pending transactions: {e}")


    def refresh_wallet(self):
        """Refresh the wallet balance and UTXOs"""
        try:
            # Clear existing items
            for item in self.utxo_tree.get_children():
                self.utxo_tree.delete(item)

            # Get UTXOs
            utxos = self.utxo_storage.get_utxos_by_address(self.wallet_address)
            total = Decimal("0")

            for u in utxos:
                amt = Decimal(u.get("amount", "0"))
                total += amt

                tx_out_index = u.get("tx_out_index", u.get("output_index", 0))  # ✅ fallback to 'output_index' or 0

                self.utxo_tree.insert('', 'end', values=(
                    u.get("tx_out_id", "N/A"),
                    tx_out_index,
                    str(amt),
                    "Yes" if u.get('locked', False) else "No"
                ))

            # Update balance
            self.balance_label.config(text=f"{total} ZYC")
            self.log_message(f"[Wallet] Refreshed balance: {total} ZYC")

        except Exception as e:
            self.log_message(f"[ERROR] Failed to refresh wallet: {e}")


    def generate_new_address(self):
        """Generate a new wallet address"""
        try:
            # Generate new key pair
            new_key = self.key_manager.generate_new_keypair()
            self.wallet_address = new_key['hashed_public_key']
            
            # Update UI
            self.refresh_wallet()
            
            self.log_message(f"[Wallet] Generated new address: {self.wallet_address}")
            messagebox.showinfo("New Address", f"New address generated:\n{self.wallet_address}")
            
        except Exception as e:
            self.log_message(f"[ERROR] Failed to generate new address: {e}")
            messagebox.showerror("Error", f"Failed to generate new address: {e}")

    def search_transaction(self):
        """Search for a transaction by ID or block height"""
        search_type = self.tx_search_type.get()
        search_value = self.tx_search_entry.get().strip()
        
        if not search_value:
            messagebox.showerror("Error", "Please enter a search value")
            return
            
        try:
            if search_type == "txid":
                tx = self.tx_storage.get_transaction(search_value)
                
                self.tx_results.configure(state='normal')
                self.tx_results.delete(1.0, tk.END)
                
                if tx:
                    if hasattr(tx, 'to_dict'):
                        tx_data = tx.to_dict()
                    else:
                        tx_data = tx
                        
                    self.tx_results.insert(tk.END, json.dumps(tx_data, indent=4))
                    self.log_message(f"[TX Explorer] Found transaction: {search_value}")
                else:
                    self.tx_results.insert(tk.END, "Transaction not found")
                    self.log_message(f"[TX Explorer] Transaction not found: {search_value}")
                    
            else:  # Search by height
                txs = self.tx_storage.get_transactions_by_block(int(search_value))
                
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
                    self.log_message(f"[TX Explorer] Found {len(txs)} transactions at height {search_value}")
                else:
                    self.tx_results.insert(tk.END, f"No transactions found at height {search_value}")
                    self.log_message(f"[TX Explorer] No transactions at height: {search_value}")
                    
            self.tx_results.configure(state='disabled')
            
        except Exception as e:
            self.log_message(f"[ERROR] Error searching transaction: {e}")
            messagebox.showerror("Error", f"Failed to search transaction: {e}")

    def find_utxos(self):
        """Find UTXOs for an address"""
        address = self.utxo_address_entry.get().strip()
        if not address:
            messagebox.showerror("Error", "Please enter an address")
            return
            
        try:
            utxos = self.utxo_storage.get_utxos_by_address(address)
            
            # Clear existing items
            for item in self.utxo_explorer_tree.get_children():
                self.utxo_explorer_tree.delete(item)
                
            if utxos:
                for utxo in utxos:
                    self.utxo_explorer_tree.insert('', 'end', values=(
                        utxo.get('tx_out_id', ''),
                        utxo.get('tx_out_index', ''),
                        str(utxo.get('amount', '0')),
                        "Yes" if utxo.get('locked', False) else "No"
                    ))
                self.log_message(f"[UTXO Explorer] Found {len(utxos)} UTXOs for address {address}")
            else:
                self.log_message(f"[UTXO Explorer] No UTXOs found for address {address}")
                
        except Exception as e:
            self.log_message(f"[ERROR] Error finding UTXOs: {e}")
            messagebox.showerror("Error", f"Failed to find UTXOs: {e}")

    def calculate_utxo_balance(self):
        """Calculate UTXO balance for an address"""
        address = self.utxo_address_entry.get().strip()
        if not address:
            messagebox.showerror("Error", "Please enter an address")
            return
            
        try:
            utxos = self.utxo_storage.get_utxos_by_address(address)
            total_balance = sum(Decimal(utxo.get("amount", "0")) for utxo in utxos) if utxos else Decimal("0")
            
            self.utxo_balance_label.config(text=f"Balance: {total_balance} ZYC")
            self.log_message(f"[UTXO Explorer] Balance for {address}: {total_balance} ZYC")
            
        except Exception as e:
            self.log_message(f"[ERROR] Error calculating balance: {e}")
            messagebox.showerror("Error", f"Failed to calculate balance: {e}")

    def refresh_orphan_blocks(self):
        """Refresh the orphan blocks list"""
        try:
            # Clear existing items
            for item in self.orphan_tree.get_children():
                self.orphan_tree.delete(item)
                
            # Get orphan blocks
            orphan_blocks = self.orphan_blocks.get_all_orphans()
            
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
                self.log_message(f"[Orphan Blocks] Displayed {len(orphan_blocks)} orphan blocks")
            else:
                self.log_message("[Orphan Blocks] No orphan blocks found")
                
        except Exception as e:
            self.log_message(f"[ERROR] Error fetching orphan blocks: {e}")
            messagebox.showerror("Error", f"Failed to get orphan blocks: {e}")

    def export_last_500_blocks(self):
        """Export the last 500 blocks to JSON"""
        try:
            all_blocks = self.block_storage.get_all_blocks()
            recent_blocks = all_blocks[-500:] if len(all_blocks) > 500 else all_blocks

            block_data = []
            for b in recent_blocks:
                if isinstance(b, dict):
                    block_data.append(b)
                elif hasattr(b, "to_dict"):
                    block_data.append(b.to_dict())
                elif hasattr(b, "__dict__") and 'block' in b.__dict__:
                    try:
                        block_data.append(b.__dict__['block'].to_dict())
                    except Exception:
                        block_data.append(b.__dict__)

            output_path = os.path.join(self.export_folder, "blockchain_integrity_check.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(block_data, f, indent=4)

            self.export_status.config(text=f"✅ Export complete: {len(block_data)} blocks saved to {output_path}")
            self.log_message(f"[Export] Exported {len(block_data)} blocks to {output_path}")
            
            # Open the export folder
            os.startfile(os.path.abspath(self.export_folder))
            
        except Exception as e:
            self.export_status.config(text=f"❌ Export failed: {e}")
            self.log_message(f"[ERROR] Export failed: {e}")
            messagebox.showerror("Error", f"Failed to export blocks: {e}")

    def select_export_folder(self):
        """Select a custom export folder"""
        folder = filedialog.askdirectory(title="Select Export Folder")
        if folder:
            self.export_folder = folder
            self.export_status.config(text=f"Export folder set to: {folder}")
            self.log_message(f"[Export] Set export folder to: {folder}")

    def validate_blockchain(self):
        """Validate the blockchain integrity"""
        try:
            valid = self.blockchain.validate_chain()
            if valid is None:
                messagebox.showwarning("Validation", "Validation returned None. Possible corruption detected.")
                self.log_message("[Validation] WARNING: Validation returned None")
            elif valid:
                messagebox.showinfo("Validation", "Blockchain validation passed.")
                self.log_message("[Validation] Blockchain validation passed")
            else:
                messagebox.showerror("Validation", "Blockchain validation failed!")
                self.log_message("[Validation] ERROR: Blockchain validation failed")
        except Exception as e:
            messagebox.showerror("Error", f"Blockchain validation failed: {e}")
            self.log_message(f"[ERROR] Validation failed: {e}")

    def cleanup(self):
        """Cleanup resources on exit"""
        self.log_message("[System] Shutting down...")
        self.stop_mining()
        
        # Close LMDB environments
        self.utxo_db.close()
        self.utxo_history_db.close()
        
        self.log_message("[System] Cleanup complete")


    def auto_refresh_ui(self):
        """Auto-refresh all dynamic UI sections every 3 seconds"""
        while True:
            try:
                self.root.after(0, self.update_dashboard)
                self.root.after(0, self.load_recent_blocks)
                self.root.after(0, self.refresh_wallet)
                self.root.after(0, self.update_mining_stats_display)  # ✅ NEW: full refresh
                time.sleep(60)
            except Exception as e:
                self.log_message(f"[AutoRefresh] ❌ UI update error: {e}")
                break

    def update_mining_stats_display(self):
        """Refresh hash rate and last mined block stats"""
        try:
            hashrate = self.calculate_hashrate()
            self.hashrate_label.config(text=f"Hashrate: {hashrate:.2f} H/s")
            # You could also refresh other miner-related data here if desired
        except Exception as e:
            self.log_message(f"[Mining Stats] ❌ Failed to update mining stats: {e}")


    def calculate_hashrate(self):
        """
        Calculate approximate hash rate based on number of attempts per second.
        This is just an estimate based on block mining timestamps.
        """
        try:
            timestamps = []
            blocks = self.block_storage.get_all_blocks()[-10:]  # last 10 blocks
            for block in blocks:
                if hasattr(block, 'timestamp'):
                    timestamps.append(block.timestamp)
                elif isinstance(block, dict) and 'timestamp' in block:
                    timestamps.append(block['timestamp'])

            if len(timestamps) < 2:
                return 0.0

            timestamps.sort()
            time_deltas = [t2 - t1 for t1, t2 in zip(timestamps, timestamps[1:])]
            avg_time = sum(time_deltas) / len(time_deltas)

            # Simulated hash difficulty as a placeholder (real mining algorithm would provide this)
            hashes_per_block = 1_000_000  # example: assume this many hash attempts per block
            return hashes_per_block / avg_time if avg_time > 0 else 0.0

        except Exception as e:
            self.log_message(f"[HashrateCalc] ❌ Failed to calculate hashrate: {e}")
            return 0.0



class PaymentProcessor:
    def __init__(self, utxo_manager, tx_storage, standard_mempool, smart_mempool, key_manager, fee_model=None):
        self.utxo_manager = utxo_manager
        self.tx_storage = tx_storage
        self.standard_mempool = standard_mempool
        self.smart_mempool = smart_mempool
        self.key_manager = key_manager

        if fee_model is not None:
            self.fee_model = fee_model
            print("[PaymentProcessor] ✅ Using provided fee_model.")
        else:
            from Zyiron_Chain.transactions.fees import FeeModel
            self.fee_model = FeeModel(Constants.MAX_SUPPLY)
            print("[PaymentProcessor] ✅ Created internal FeeModel.")



    def send_payment(self, sender_priv_key, sender_pub_key, recipient_address, amount, tx_type="STANDARD"):
        """Send a payment transaction"""
        if amount <= 0:
            print("[PaymentProcessorUI] ❌ Invalid amount. Must be greater than 0.")
            return None

        if tx_type not in Constants.TRANSACTION_MEMPOOL_MAP:
            print(f"[PaymentProcessorUI] ❌ Unsupported transaction type: {tx_type}")
            return None

        # ✅ Step 1: Select UTXOs
        utxos, total_input = self._select_utxos(sender_pub_key, amount + Decimal("0.00000001"))
        if not utxos:
            print("[PaymentProcessorUI] ❌ No suitable UTXOs found.")
            return None

        # ✅ Step 2: Calculate correct fee using full block context
        try:
            fee = self.fee_model.calculate_fee(
                block_size=Constants.INITIAL_BLOCK_SIZE_MB,
                payment_type=tx_type,
                amount=amount,
                tx_size=512
            )
            print(f"[PaymentProcessorUI] ✅ Fee calculated: {fee}")
        except Exception as e:
            print(f"[PaymentProcessorUI] ❌ Fee calculation failed: {e}")
            return None

        if total_input < amount + fee:
            print(f"[PaymentProcessorUI] ❌ Insufficient funds. Total input: {total_input}, Required: {amount + fee}")
            return None

        # ✅ Step 3: Build placeholder inputs for initial tx signing
        inputs = [TransactionIn(tx_out_id=u.tx_out_id, script_sig="placeholder") for u in utxos]
        outputs = [TransactionOut(script_pub_key=recipient_address, amount=amount)]

        change = total_input - amount - fee
        if change > 0:
            outputs.append(TransactionOut(script_pub_key=sender_pub_key, amount=change))

        # ✅ Step 4: Create and sign the transaction
        tx = Transaction(inputs=inputs, outputs=outputs, tx_type=tx_type)
        tx.sign(sender_priv_key, sender_pub_key)

        # ✅ Step 5: Replace placeholder script_sigs with real signature
        for tx_input in tx.inputs:
            tx_input.script_sig = tx.signature.hex()

        # ✅ Step 6: Verify signature using KeyManager
        if not self.key_manager.verify_transaction(
            message=tx.hash.encode("utf-8") if isinstance(tx.hash, str) else tx.hash,
            signature=tx.signature,
            network=self.key_manager.network,
            identifier=self.key_manager.keys[self.key_manager.network]["defaults"]["miner"]
        ):
            print("[PaymentProcessorUI] ❌ Signature verification failed.")
            return None

        # ✅ Step 7: Lock UTXOs and add to mempool
        self.utxo_manager.lock_selected_utxos([u.tx_out_id for u in utxos])

        if not self._route_to_mempool(tx):
            self.utxo_manager.unlock_selected_utxos([u.tx_out_id for u in utxos])
            print("[PaymentProcessorUI] ❌ Failed to route transaction to mempool.")
            return None

        print(f"[PaymentProcessorUI] ✅ Transaction sent. TXID: {tx.tx_id}")
        return tx.tx_id

    def _select_utxos(self, address, required_amount):
        """Select UTXOs for a transaction"""
        print(f"[UTXO SELECTOR] 🔍 Looking for UTXOs for address: {address} to cover {required_amount} ZYC")

        try:
            utxos = self.utxo_manager.utxo_storage.get_utxos_by_address(address)
        except Exception as e:
            print(f"[UTXO SELECTOR] ❌ Failed to retrieve UTXOs: {e}")
            return [], Decimal("0")

        selected = []
        total = Decimal("0")

        for utxo_dict in utxos:
            try:
                utxo = TransactionOut.from_dict(utxo_dict)
                if utxo.locked:
                    continue
                selected.append(utxo)
                total += utxo.amount
                print(f"   ↳ Selected UTXO: {utxo.tx_out_id[:12]}... | Amount: {utxo.amount}")
                if total >= required_amount:
                    break
            except Exception as e:
                print(f"[UTXO SELECTOR] ⚠️ Skipping invalid UTXO: {e}")
                continue

        print(f"[UTXO SELECTOR] ✅ Selected {len(selected)} UTXOs totaling {total} ZYC")
        return selected, total

    def _route_to_mempool(self, tx):
        """Route transaction to the correct mempool based on type and prefix."""
        try:
            # ✅ Get current chain height from BlockStorage or fallback
            current_height = 0
            if hasattr(self.tx_storage, "block_storage") and self.tx_storage.block_storage:
                current_height = self.tx_storage.block_storage.get_latest_block_height()
            elif hasattr(self.standard_mempool, "block_storage") and self.standard_mempool.block_storage:
                current_height = self.standard_mempool.block_storage.get_latest_block_height()

            print(f"[PaymentProcessorUI] INFO: Routing TX {tx.tx_id} | Type: {tx.tx_type} | Chain Height: {current_height}")

            # ✅ Determine the transaction type from its prefix
            tx_type_detected = "STANDARD"  # default fallback
            for tx_type, info in Constants.TRANSACTION_MEMPOOL_MAP.items():
                for prefix in info["prefixes"]:
                    if tx.tx_id.startswith(prefix):
                        tx_type_detected = tx_type
                        break
                if tx_type_detected != "STANDARD":
                    break

            print(f"[PaymentProcessorUI] ✅ Detected TX Type: {tx_type_detected}")

            # ✅ Route to appropriate mempool
            if tx_type_detected == "SMART":
                return self.smart_mempool.add_transaction(tx, current_block_height=current_height)
            elif tx_type_detected == "INSTANT":
                print("[PaymentProcessorUI] ⚠️ Instant payments not yet supported.")
                return False
            else:
                return self.standard_mempool.add_transaction(tx)

        except Exception as e:
            print(f"[PaymentProcessorUI] ❌ Error routing transaction to mempool: {e}")
            return False


if __name__ == "__main__":
    import tkinter as tk
    from threading import Thread

    # ✅ Initialize the root Tkinter window
    root = tk.Tk()

    # ✅ Launch the Blockchain UI
    app = BlockchainUI(root)

    # ✅ Start auto-refresh UI thread (updates dashboard, mining stats, wallet every 3s)
    Thread(target=app.auto_refresh_ui, daemon=True).start()

    # ✅ Run the Tkinter event loop
    root.mainloop()
