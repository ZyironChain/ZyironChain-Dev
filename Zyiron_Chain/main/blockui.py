from functools import wraps
import sys
import os
import traceback
from typing import Callable, List, Optional

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

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from datetime import datetime
import time
import threading
import json
import os
import atexit
from decimal import Decimal
import webbrowser
from PIL import Image, ImageTk
import sv_ttk
import ttkbootstrap as ttkbs
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip
from ttkbootstrap.scrolled import ScrolledFrame
import logging
import queue

import threading

class BlockchainUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Zyiron Chain Explorer")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        # Setup colors FIRST before creating any UI elements
        self.bg_color = "#121212"
        self.card_bg = "#1E1E1E"
        self.accent_color = "#7B2CBF"
        self.secondary_accent = "#9D4EDD"
        self.text_color = "#E0E0E0"
        self.success_color = "#4CAF50"
        self.warning_color = "#FFC107"
        self.error_color = "#F44336"

        # Set dark theme
        sv_ttk.set_theme("dark")

        # Track loading popup state
        self.loading_popup = None
        self.loading_complete = False
        self.last_progress = 0  # Initialize progress tracking
        self.last_message = ""  # Initialize message tracking

        # Setup basic state and threading
        self.mining_active = False
        self.mining_thread = None
        self.export_folder = os.path.expanduser("~/Downloads")
        self.log_queue = queue.Queue()
        self.root.configure(bg=self.bg_color)

        # Create and show loading screen
        self.create_loading_screen()
        self.root.update()

        # Start the main UI load
        self.root.after(100, self.initialize_ui_async)

        # Register cleanup and window close handler
        atexit.register(self.cleanup)
        self.root.protocol("WM_DELETE_WINDOW", self.exit_cleanly)

        # Bind right-click menu
        self.root.bind_class("Text", "<Button-3><ButtonRelease-3>", self.show_right_click_menu)

    def _load_ui_background(self):
        """Load UI components in the background with proper progress updates"""
        try:
            stages = [
                ("Initializing Blockchain", 30, self._safe_initialize_blockchain),
                ("Setting Up UI", 40, self._safe_setup_ui),
                ("Loading Wallet", 20, self._safe_load_wallet),
                ("Starting Services", 10, self._start_background_services)
            ]

            total_weight = sum(weight for _, weight, _ in stages)
            progress = 0

            for name, weight, func in stages:
                self.root.after(0, lambda p=progress, n=name: self.update_loading_screen(p, n))
                func()  # Runs in background
                progress += (weight / total_weight) * 100
                self.root.after(0, lambda p=min(100, progress), n=name: self.update_loading_screen(p, n))

            self.root.after(0, self.finalize_ui_loading)
            
        except Exception as e:
            self.root.after(0, lambda e=e: self._handle_loading_failure(f"Loading failed: {e}"))

    def create_loading_screen(self):
        """Create and show the loading screen with proper error handling"""
        try:
            if self.loading_popup and self.loading_popup.winfo_exists():
                return

            self.loading_popup = tk.Toplevel(self.root)
            self.loading_popup.title("Loading...")
            self.loading_popup.geometry("400x200")
            self.loading_popup.resizable(False, False)
            self.loading_popup.attributes('-topmost', True)
            self.loading_popup.grab_set()  # Make it modal
            
            # Center the window
            self._center_loading_screen()

            # Loading content
            ttk.Label(self.loading_popup, 
                     text="⚡ Zyiron Chain", 
                     font=('Helvetica', 18, 'bold')).pack(pady=20)
            
            self.loading_label = ttk.Label(self.loading_popup, 
                                          text="Initializing...",
                                          font=('Helvetica', 10))
            self.loading_label.pack()
            
            self.loading_progress_bar = ttk.Progressbar(self.loading_popup, 
                                                       orient='horizontal',
                                                       length=300,
                                                       mode='determinate')
            self.loading_progress_bar.pack(pady=10)
            
            self.loading_percent = ttk.Label(self.loading_popup, 
                                            text="0%",
                                            font=('Helvetica', 10))
            self.loading_percent.pack()
            
            self.root.update()  # Force immediate UI update
            
        except Exception as e:
            print(f"Error creating loading screen: {e}")
            # Fallback to console output if UI fails
            print("Initializing Zyiron Chain...")





    def destroy_loading_screen(self):
        """Safely destroy the loading screen"""
        if self.loading_popup and self.loading_popup.winfo_exists():
            try:
                self.loading_popup.grab_release()
                self.loading_popup.destroy()
            except Exception as e:
                print(f"Error closing loading screen: {e}")
        self.loading_popup = None

    def initialize_ui_async(self):
        """Safely initialize UI components in background with proper error handling"""
        try:
            # Start background thread with proper error propagation
            self._loading_thread = threading.Thread(
                target=self._load_ui_background,
                daemon=True,
                name="UI_Initializer"
            )
            self._loading_thread.start()

            # Start monitoring progress
            self._monitor_loading_progress()

        except Exception as e:
            self._handle_loading_failure(f"Initialization failed: {str(e)}")








    def finalize_ui_loading(self):
        """Finalize UI with proper cleanup and validation"""
        try:
            # Verify critical components
            required_components = [
                'blockchain', 'miner', 'wallet_address',
                'notebook', 'status_bar'
            ]
            missing = [comp for comp in required_components if not hasattr(self, comp)]
            if missing:
                raise RuntimeError(f"Missing critical components: {', '.join(missing)}")

            print("[FINALIZE] All critical components are present.")

            # Safely destroy the loading screen
            if self.loading_popup and self.loading_popup.winfo_exists():
                print("[FINALIZE] Destroying loading screen...")
                self.destroy_loading_screen()
            else:
                print("[FINALIZE] Loading screen already destroyed or missing.")

            # Initial UI content population
            self.update_dashboard()
            self.load_recent_blocks()
            self.refresh_wallet()

            print("[FINALIZE] Dashboard, blocks, and wallet loaded.")
            self.log_output("UI initialization completed successfully", "SUCCESS")

        except Exception as e:
            print(f"[ERROR] UI finalization failed: {str(e)}")
            self._handle_loading_failure(f"Finalization failed: {str(e)}")

    def _handle_loading_failure(self, error_msg):
        """Handle loading failures with proper cleanup"""
        try:
            # Attempt to remove loading screen if it exists
            self.destroy_loading_screen()

            # Show error message
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror(
                    "Initialization Error",
                    f"Failed to initialize application:\n\n{error_msg}",
                    parent=self.root
                )
                self.root.destroy()
            else:
                print(f"Critical error: {error_msg}")
                sys.exit(1)

        except Exception as e:
            print(f"Error during failure handling: {str(e)}")
            sys.exit(1)

    def exit_cleanly(self):
        """Clean exit handler"""
        try:
            self.log_message("Shutting down...", "INFO")
            self.stop_mining()
            
            # Close LMDB environments
            if hasattr(self, 'tx_storage') and self.tx_storage:
                self.tx_storage.close()
            if hasattr(self, 'utxo_storage') and self.utxo_storage:
                self.utxo_storage.close()
            if hasattr(self, 'block_storage') and self.block_storage:
                self.block_storage.close()
                
            self.log_message("Cleanup complete", "INFO")
            self.destroy_loading_screen()
            self.root.destroy()
        except Exception as e:
            self.log_message(f"Cleanup error: {e}", "ERROR")
            self.root.destroy()







    def _monitor_loading_progress(self):
        """Monitor loading progress and handle completion/failure"""
        if not hasattr(self, '_loading_thread'):
            return

        if self._loading_thread.is_alive():
            self.root.after(500, self._monitor_loading_progress)
        else:
            if hasattr(self, '_loading_complete') and self._loading_complete:
                self.root.after(0, self.finalize_ui_loading)
            elif hasattr(self, '_loading_failed') and self._loading_failed:
                self.root.after(0, lambda: self._handle_loading_failure("Background thread failed"))


    def _on_tab_change(self, event):
        selected_tab = event.widget.select()
        tab_text = event.widget.tab(selected_tab, "text")
        if tab_text == "💳 Wallet":  # Match exact tab text
            self.refresh_wallet()



    def _safe_load_wallet(self):
        """Wrapper for wallet loading with validation and error handling"""
        try:
            if not hasattr(self, 'wallet_address') or not self.wallet_address:
                # Initialize wallet if not exists
                self.wallet_address = self.key_manager.get_default_public_key()
                if not self.wallet_address:
                    raise ValueError("Failed to generate wallet address")
            
            # Verify wallet components
            if not all(hasattr(self, attr) for attr in ['key_manager', 'utxo_manager']):
                raise RuntimeError("Missing required wallet components")
                
            # Load wallet data
            self.view_wallet()
            self.refresh_wallet()
            
            return True
        except Exception as e:
            error_msg = f"Wallet loading failed: {str(e)}"
            self.log_message(error_msg, "ERROR")
            raise RuntimeError(error_msg) from e





    def _start_background_services(self):
        """Start all required background services"""
        services = [
            ("Mining Monitor", self.start_mining_monitor),
            ("Log Handler", self.start_log_handler),
            ("Auto-Refresh", self.auto_refresh_ui)
        ]

        for name, service in services:
            try:
                service()
                progress_value = self.loading_progress_bar['value'] if self.loading_progress_bar else 0
                self.update_loading_screen(progress_value, f"Started {name}")
            except Exception as e:
                self.log_output(f"Failed to start {name}: {str(e)}", "WARNING")







    def log_output(self, message, level="INFO"):
        """Enhanced thread-safe logging with UI updates"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_icon = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "SUCCESS": "✅"
        }.get(level, "•")
        
        formatted = f"[{timestamp}] {level_icon} [{level}] {message}"
        
        # Always print to console
        print(formatted)
        
        # Queue for UI update if available
        if hasattr(self, 'log_queue'):
            try:
                color = {
                    "INFO": self.text_color,
                    "WARNING": self.warning_color,
                    "ERROR": self.error_color,
                    "SUCCESS": self.success_color
                }.get(level, self.text_color)
                
                self.log_queue.put((formatted, color))
            except Exception as e:
                print(f"Failed to queue log message: {str(e)}")

        # Immediate UI update if in main thread
        if self.is_main_thread() and hasattr(self, 'log_output_widget'):
            try:
                self.log_output_widget.configure(state='normal')
                self.log_output_widget.insert(tk.END, formatted + "\n")
                self.log_output_widget.configure(state='disabled')
                self.log_output_widget.see(tk.END)
            except Exception as e:
                print(f"Failed direct log update: {str(e)}")

    def is_main_thread(self):
        """Check if current thread is the main thread"""
        return isinstance(threading.current_thread(), threading._MainThread)



    def _confirm_close_loading(self):
        """Handle confirmation when trying to close loading screen"""
        if messagebox.askokcancel(
            "Cancel Initialization", 
            "Are you sure you want to cancel the initialization process?",
            parent=self.loading_screen
        ):
            self._safe_close_loading()
            self.root.destroy()


    def _safe_initialize_blockchain(self):
        self.initialize_blockchain()
        
        # Wait until key components are ready
        while not hasattr(self, "mempool_storage") or not hasattr(self, "orphan_blocks") or not hasattr(self, "utxo_manager"):
            time.sleep(0.2)  # short delay to allow background thread to finish setup


    def _safe_setup_ui(self):
        """Wrapper for UI setup with thread safety checks"""
        if not self.is_main_thread():
            self.root.after(0, self._safe_setup_ui)
            return
            
        try:
            self.setup_ui()
        except Exception as e:
            raise RuntimeError(f"UI setup failed: {str(e)}")
        



    def _center_loading_screen(self):
        """Center the loading screen on parent window"""
        if not self.loading_popup:
            return
            
        self.loading_popup.update_idletasks()
        width = self.loading_popup.winfo_width()
        height = self.loading_popup.winfo_height()
        x = (self.loading_popup.winfo_screenwidth() // 2) - (width // 2)
        y = (self.loading_popup.winfo_screenheight() // 2) - (height // 2)
        self.loading_popup.geometry(f'{width}x{height}+{x}+{y}')


 
    def update_loading_screen(self, progress, message):
        """Update loading screen progress safely"""
        try:
            if not self.loading_popup or not self.loading_popup.winfo_exists():
                return

            # Only update if significant change
            if abs(progress - self.last_progress) > 2 or message != self.last_message:
                # ✅ Ensure we update the actual loading progress bar
                self.loading_progress_bar['value'] = progress
                self.loading_label.config(text=message)
                self.loading_percent.config(text=f"{int(progress)}%")
                self.loading_popup.update_idletasks()

                self.last_progress = progress
                self.last_message = message

        except Exception as e:
            print(f"Error updating loading screen: {e}")



    def _safe_close_loading(self):
        """Safely close the loading screen without animation"""
        try:
            # Corrected from self.loading_screen to self.loading_popup
            if hasattr(self, 'loading_popup') and self.loading_popup.winfo_exists():
                self.loading_popup.destroy()
        except Exception as e:
            print(f"Error closing loading screen: {e}")






    def remove_loading_screen(self):
        if self.loading_screen and tk.Toplevel.winfo_exists(self.loading_screen):
            self.loading_message.config(text="Initialization complete!")
            self.loading_percentage.config(text="100%")
            self.root.after(1500, self._safe_close_loading)


    def _safe_close_loading(self):
        try:
            if self.loading_screen:
                self.loading_screen.destroy()
                self.loading_screen = None
        except Exception as e:
            print("Failed to destroy loading screen:", e)


    def is_mainloop_running(self):
        """Check if the main Tkinter loop is running"""
        try:
            return self.root and self.root.winfo_exists()
        except (tk.TclError, RuntimeError):
            return False




    def animate_loading_complete(self):
        """Show completion animation"""
        completion_label = ttk.Label(
            self.root,
            text="Ready",
            font=('Helvetica', 12, 'bold'),
            foreground=self.success_color,
            background=self.bg_color
        )
        completion_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # Animate fade out and grow
        for i in range(1, 21):
            size = 12 + i
            completion_label.config(font=('Helvetica', size, 'bold'))
            completion_label.place(relx=0.5, rely=0.5, anchor='center')
            self.root.update()
            time.sleep(0.02)

        # Handle fade out by using Toplevel transparency
        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.geometry(f"+{self.root.winfo_rootx()}+{self.root.winfo_rooty()}")
        top.configure(bg=self.bg_color)
        
        temp_label = tk.Label(
            top,
            text="Ready",
            font=('Helvetica', 32, 'bold'),
            fg=self.success_color,
            bg=self.bg_color
        )
        temp_label.pack(expand=True, fill='both')
        top.lift()
        top.attributes('-topmost', True)
        top.update()

        for alpha in range(100, -1, -5):
            top.attributes('-alpha', alpha / 100)
            top.update()
            time.sleep(0.02)

        top.destroy()
        completion_label.destroy()


    def initialize_blockchain(self):
        """Run blockchain initialization in background thread to avoid UI freeze"""
        # Create a queue for UI updates
        self.update_queue = queue.Queue()
        
        # Start the monitor for UI updates
        self.root.after(100, self.process_ui_updates)
        
        # Start initialization in background
        threading.Thread(target=self._initialize_blockchain_thread, daemon=True).start()

    def process_ui_updates(self):
        """Process UI updates from the queue"""
        try:
            while True:
                # Get all pending updates (non-blocking)
                try:
                    callback = self.update_queue.get_nowait()
                    callback()
                except queue.Empty:
                    break
        finally:
            # Schedule next check
            self.root.after(100, self.process_ui_updates)

    def _initialize_blockchain_thread(self):
        try:
            # Major milestones for updates
            milestones = [
                (5, "🔑 Initializing Key Manager..."),
                (25, "📦 Setting up Storage..."),
                (50, "⛓️ Building Blockchain Core..."),
                (75, "⚒️ Initializing Miner..."),
                (100, "✅ Finalizing Setup...")
            ]
            
            # Update via queue instead of direct after(0)
            def update_loading(progress, message):
                self.update_queue.put(lambda: self.update_loading_screen(progress, message))
            
            # Key Manager
            update_loading(*milestones[0])
            self.key_manager = KeyManager()

            # Fee Model
            self.fee_model = FeeModel(Constants.MAX_SUPPLY)

            # Transaction Storage
            self.tx_storage = TxStorage(fee_model=self.fee_model)

            # Block Storage
            update_loading(*milestones[1])
            self.block_storage = BlockStorage(
                tx_storage=self.tx_storage,
                key_manager=self.key_manager,
                utxo_storage=None
            )

            # UTXO Storage
            self.utxo_storage = UTXOStorage(
                utxo_manager=None,
                block_storage=self.block_storage
            )

            # UTXO Manager
            self.utxo_storage.utxo_manager = UTXOManager(self.utxo_storage)
            self.utxo_manager = self.utxo_storage.utxo_manager
            self.block_storage.utxo_storage = self.utxo_storage

            # Transaction Manager
            update_loading(*milestones[2])
            self.transaction_manager = TransactionManager(
                block_storage=self.block_storage,
                tx_storage=self.tx_storage,
                utxo_manager=self.utxo_manager,
                key_manager=self.key_manager
            )

            # Mempool Storage
            self.mempool_storage = MempoolStorage(self.transaction_manager)

            # Blockchain Core
            self.blockchain = Blockchain(
                tx_storage=self.tx_storage,
                utxo_storage=self.utxo_storage,
                transaction_manager=self.transaction_manager,
                key_manager=self.key_manager,
                full_block_store=self.block_storage
            )

            # Block Manager
            update_loading(*milestones[3])
            self.block_manager = BlockManager(
                blockchain=self.blockchain,
                block_storage=self.block_storage,
                block_metadata=self.block_storage,
                tx_storage=self.tx_storage,
                transaction_manager=self.transaction_manager
            )

            # Genesis Block
            self.genesis_block_manager = GenesisBlockManager(
                block_storage=self.block_storage,
                key_manager=self.key_manager,
                chain=self.block_manager.blockchain,
                block_manager=self.block_manager
            )

            # Miner
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

            # Mempools
            self.standard_mempool = StandardMempool(utxo_storage=self.utxo_storage)
            self.smart_mempool = SmartMempool(utxo_storage=self.utxo_storage)

            # Payment Processor
            self.payment_processor = PaymentProcessor(
                utxo_manager=self.utxo_manager,
                tx_storage=self.tx_storage,
                standard_mempool=self.standard_mempool,
                smart_mempool=self.smart_mempool,
                key_manager=self.key_manager,
            )

            # Final setup
            update_loading(*milestones[4])
            self.orphan_blocks = OrphanBlocks()
            self.wallet_address = self.key_manager.get_default_public_key()

            self.log_message("[System] Blockchain components initialized successfully", "INFO")

        except Exception as e:
            error_msg = f"[ERROR] Failed to initialize blockchain: {str(e)}"
            self.update_queue.put(lambda: self.log_message(error_msg, "ERROR"))
            self.update_queue.put(lambda: messagebox.showerror("Initialization Error", "Failed to initialize blockchain components"))


    def close_loading_popup(self):
        try:
            if hasattr(self, "loading_popup") and self.loading_popup:
                self.loading_popup.destroy()
                print("[UI] ✅ Loading popup closed.")
        except Exception as e:
            print(f"[UI] ⚠️ Failed to close loading popup: {e}")

    def show_wallet_tab(self):
        print("[UI] Switching to Wallet tab")
        self.wallet_tab_frame.tkraise()

        # Clear existing widgets in wallet tab frame
        for widget in self.wallet_tab_frame.winfo_children():
            widget.destroy()

        # Add wallet balance label (rebuild UI)
        balance = self.utxo_manager.get_balance(self.key_manager.get_address())
        balance_label = tk.Label(self.wallet_tab_frame, text=f"Balance: {balance} ZYC", font=("Arial", 14))
        balance_label.pack(pady=10)

        # Add a refresh button
        refresh_button = tk.Button(self.wallet_tab_frame, text="Refresh", command=self.show_wallet_tab)
        refresh_button.pack()


    def setup_ui(self):
        """Setup the main UI components with modern styling"""
        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill='both', expand=True)
        
        # Create header
        self.create_header()
        
        # Create notebook for tabs
        self.notebook = ttkbs.Notebook(self.main_container, bootstyle="dark")
        self.notebook.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        # Create tabs
        self.create_dashboard_tab()
        self.create_blockchain_tab()
        self.create_mining_tab()
        self.create_transactions_tab()
        self.create_wallet_tab()
        self.create_explorer_tab()
        self.create_log_tab()
        
        # Create status bar
        self.create_status_bar()
        
        # Apply initial updates
        self.update_dashboard()

    def create_header(self):
        """Create a modern header with logo and quick stats"""
        header_frame = ttk.Frame(self.main_container, style='dark.TFrame')
        header_frame.pack(fill='x', padx=10, pady=10)
        
        # Logo and title
        logo_frame = ttk.Frame(header_frame, style='dark.TFrame')
        logo_frame.pack(side='left', padx=10)
        
        # Replace with your logo
        ttk.Label(logo_frame, text="⚡", font=('Helvetica', 24), 
                 style='primary.TLabel').pack(side='left')
        ttk.Label(logo_frame, text="Zyiron Chain Explorer", font=('Helvetica', 16, 'bold'), 
                 style='primary.TLabel').pack(side='left', padx=5)
        
        # Quick stats
        stats_frame = ttk.Frame(header_frame, style='dark.TFrame')
        stats_frame.pack(side='right', padx=10)
        
        # Network status
        self.network_status = ttk.Label(
            stats_frame, 
            text=f"Network: {Constants.NETWORK}", 
            font=('Helvetica', 10),
            style='info.TLabel'
        )
        self.network_status.pack(side='right', padx=10)
        
        # Block height
        self.header_block_height = ttk.Label(
            stats_frame, 
            text="Height: 0", 
            font=('Helvetica', 10),
            style='info.TLabel'
        )
        self.header_block_height.pack(side='right', padx=10)
        
        # Sync status
        self.sync_status = ttk.Label(
            stats_frame, 
            text="🟢 Synced", 
            font=('Helvetica', 10),
            style='success.TLabel'
        )
        self.sync_status.pack(side='right', padx=10)

    def create_status_bar(self):
        """Create a modern status bar"""
        self.status_bar = ttk.Frame(self.main_container, height=25, style='secondary.TFrame')
        self.status_bar.pack(fill='x', side='bottom', padx=10, pady=(0, 10))
        
        # Left status
        self.status_left = ttk.Label(
            self.status_bar, 
            text="Ready", 
            style='secondary.Inverse.TLabel'
        )
        self.status_left.pack(side='left', padx=10)
        
        # Right status
        self.status_right = ttk.Label(
            self.status_bar, 
            text=f"v{Constants.VERSION}", 
            style='secondary.Inverse.TLabel'
        )
        self.status_right.pack(side='right', padx=10)
        
        # Middle status
        self.status_middle = ttk.Label(
            self.status_bar, 
            text="", 
            style='secondary.Inverse.TLabel'
        )
        self.status_middle.pack(side='right', padx=10)

    def create_dashboard_tab(self):
        """Create the dashboard tab with modern cards"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Dashboard")
        
        # Main container with scrollbar
        container = ScrolledFrame(tab, autohide=True)
        container.pack(fill='both', expand=True)
        
        # Blockchain Info Card
        blockchain_card = ttkbs.Labelframe(
            container, 
            text="Blockchain Information", 
            bootstyle="info"
        )
        blockchain_card.pack(fill='x', padx=10, pady=5)
        
        # Grid layout for stats
        ttk.Label(blockchain_card, text="Network:", style='primary.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=2)
        ttk.Label(blockchain_card, text=f"{Constants.NETWORK}", style='light.TLabel').grid(row=0, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Label(blockchain_card, text="Version:", style='primary.TLabel').grid(row=1, column=0, sticky='w', padx=5, pady=2)
        ttk.Label(blockchain_card, text=f"{Constants.VERSION}", style='light.TLabel').grid(row=1, column=1, sticky='w', padx=5, pady=2)
        
        self.block_height_label = ttk.Label(blockchain_card, text="Block Height: Loading...", style='primary.TLabel')
        self.block_height_label.grid(row=2, column=0, columnspan=2, sticky='w', padx=5, pady=2)
        
        self.difficulty_label = ttk.Label(blockchain_card, text="Difficulty: Loading...", style='primary.TLabel')
        self.difficulty_label.grid(row=3, column=0, columnspan=2, sticky='w', padx=5, pady=2)
        
        self.tx_count_label = ttk.Label(blockchain_card, text="Total Transactions: Loading...", style='primary.TLabel')
        self.tx_count_label.grid(row=4, column=0, columnspan=2, sticky='w', padx=5, pady=2)
        
        self.avg_mine_time_label = ttk.Label(blockchain_card, text="Avg Mining Time: Calculating...", style='primary.TLabel')
        self.avg_mine_time_label.grid(row=5, column=0, columnspan=2, sticky='w', padx=5, pady=2)
        
        # Mempool Info Card
        mempool_card = ttkbs.Labelframe(
            container, 
            text="Mempool Information", 
            bootstyle="warning"
        )
        mempool_card.pack(fill='x', padx=10, pady=5)
        
        self.mempool_size_label = ttk.Label(mempool_card, text="Pending Transactions: Loading...", style='primary.TLabel')
        self.mempool_size_label.pack(anchor='w', padx=5, pady=2)
        
        self.mempool_size_standard_label = ttk.Label(mempool_card, text="Standard TX: Loading...", style='primary.TLabel')
        self.mempool_size_standard_label.pack(anchor='w', padx=5, pady=2)
        
        self.mempool_size_smart_label = ttk.Label(mempool_card, text="Smart TX: Loading...", style='primary.TLabel')
        self.mempool_size_smart_label.pack(anchor='w', padx=5, pady=2)
        
        # UTXO Info Card
        utxo_card = ttkbs.Labelframe(
            container, 
            text="UTXO Information", 
            bootstyle="danger"
        )
        utxo_card.pack(fill='x', padx=10, pady=5)
        
        self.utxo_count_label = ttk.Label(utxo_card, text="Total UTXOs: Loading...", style='primary.TLabel')
        self.utxo_count_label.pack(anchor='w', padx=5, pady=2)
        
        self.orphan_blocks_label = ttk.Label(utxo_card, text="Orphan Blocks: Loading...", style='primary.TLabel')
        self.orphan_blocks_label.pack(anchor='w', padx=5, pady=2)
        
        # Buttons Card
        buttons_card = ttkbs.Labelframe(
            container, 
            text="Actions", 
            bootstyle="success"
        )
        buttons_card.pack(fill='x', padx=10, pady=5)
        
        btn_frame = ttk.Frame(buttons_card)
        btn_frame.pack(fill='x', pady=5)
        
        ttkbs.Button(
            btn_frame, 
            text="🔄 Refresh Data", 
            command=self.update_dashboard,
            bootstyle="outline"
        ).pack(side='left', padx=5)
        
        ttkbs.Button(
            btn_frame, 
            text="🔍 Validate Blockchain", 
            command=self.validate_blockchain,
            bootstyle="outline"
        ).pack(side='left', padx=5)
        
        ttkbs.Button(
            btn_frame, 
            text="📊 View Stats", 
            command=self.show_stats,
            bootstyle="outline"
        ).pack(side='left', padx=5)

    def create_blockchain_tab(self):
        """Create the blockchain tab with modern explorer"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Blockchain")
        
        # Search Card
        search_card = ttkbs.Labelframe(
            tab, 
            text="Block Search", 
            bootstyle="info"
        )
        search_card.pack(fill='x', padx=10, pady=5)
        
        # Search type
        ttk.Label(search_card, text="Search By:").grid(row=0, column=0, padx=5, sticky='w')
        self.block_search_type = tk.StringVar(value="height")
        
        ttkbs.Radiobutton(
            search_card, 
            text="Height", 
            variable=self.block_search_type, 
            value="height",
            bootstyle="info-toolbutton"
        ).grid(row=0, column=1, sticky='w')
        
        ttkbs.Radiobutton(
            search_card, 
            text="Hash", 
            variable=self.block_search_type, 
            value="hash",
            bootstyle="info-toolbutton"
        ).grid(row=0, column=2, sticky='w')
        
        # Search input
        ttk.Label(search_card, text="Value:").grid(row=1, column=0, padx=5, sticky='w')
        self.block_search_entry = ttkbs.Entry(search_card, width=50)
        self.block_search_entry.grid(row=1, column=1, columnspan=2, sticky='we', pady=5)
        
        # Search button
        search_btn = ttkbs.Button(
            search_card, 
            text="🔍 Search Block", 
            command=self.search_block,
            bootstyle="info-outline"
        )
        search_btn.grid(row=2, column=0, columnspan=3, pady=5)
        ToolTip(search_btn, text="Search for a block by height or hash")
        
        # Results display
        results_card = ttkbs.Labelframe(
            tab, 
            text="Block Details", 
            bootstyle="secondary"
        )
        results_card.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.block_results = ttkbs.ScrolledText(
            results_card, 
            height=15, 
            wrap=tk.WORD
        )

        self.block_results.pack(fill='both', expand=True, padx=5, pady=5)
        self.block_results.configure(state='disabled')
        
        # Recent blocks card
        recent_card = ttkbs.Labelframe(
            tab, 
            text="Recent Blocks", 
            bootstyle="primary"
        )
        recent_card.pack(fill='both', padx=10, pady=5)
        
        # Treeview for recent blocks
        self.recent_blocks_tree = ttkbs.Treeview(
            recent_card, 
            columns=('height', 'hash', 'timestamp', 'tx_count'), 
            show='headings',
            bootstyle="dark"
        )
        
        # Configure columns
        self.recent_blocks_tree.heading('height', text='Height')
        self.recent_blocks_tree.heading('hash', text='Hash')
        self.recent_blocks_tree.heading('timestamp', text='Timestamp')
        self.recent_blocks_tree.heading('tx_count', text='TX Count')
        
        self.recent_blocks_tree.column('height', width=80, anchor='center')
        self.recent_blocks_tree.column('hash', width=250)
        self.recent_blocks_tree.column('timestamp', width=150)
        self.recent_blocks_tree.column('tx_count', width=80, anchor='center')
        
        # Add scrollbar
        scrollbar = ttkbs.Scrollbar(
            recent_card, 
            orient="vertical", 
            command=self.recent_blocks_tree.yview,
            bootstyle="round"
        )
        self.recent_blocks_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        self.recent_blocks_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Load recent blocks
        self.load_recent_blocks()

    def create_mining_tab(self):
        """Create the mining tab with modern controls"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Mining")
        
        # Controls Card
        controls_card = ttkbs.Labelframe(
            tab, 
            text="Mining Controls", 
            bootstyle="warning"
        )
        controls_card.pack(fill='x', padx=10, pady=5)
        
        # Mining status
        self.mining_status = ttkbs.Label(
            controls_card, 
            text="⛏️ Mining: Stopped", 
            font=('Helvetica', 12),
            bootstyle="inverse-warning"
        )
        self.mining_status.pack(pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(controls_card)
        btn_frame.pack(pady=5)
        
        self.start_mining_btn = ttkbs.Button(
            btn_frame, 
            text="▶ Start Mining", 
            command=self.start_mining,
            bootstyle="success"
        )
        self.start_mining_btn.pack(side='left', padx=5)
        ToolTip(self.start_mining_btn, text="Start mining new blocks")
        
        self.stop_mining_btn = ttkbs.Button(
            btn_frame, 
            text="⏹ Stop Mining", 
            command=self.stop_mining,
            state='disabled',
            bootstyle="danger"
        )
        self.stop_mining_btn.pack(side='left', padx=5)
        ToolTip(self.stop_mining_btn, text="Stop mining process")
        
        # Stats Card
        stats_card = ttkbs.Labelframe(
            tab, 
            text="Mining Statistics", 
            bootstyle="info"
        )
        stats_card.pack(fill='x', padx=10, pady=5)
        
        self.hashrate_label = ttk.Label(
            stats_card, 
            text="⚡ Hashrate: 0 H/s", 
            style='primary.TLabel'
        )
        self.hashrate_label.pack(anchor='w', padx=5, pady=2)
        
        self.blocks_mined_label = ttk.Label(
            stats_card, 
            text="📦 Blocks Mined: 0", 
            style='primary.TLabel'
        )
        self.blocks_mined_label.pack(anchor='w', padx=5, pady=2)
        
        self.last_block_time_label = ttk.Label(
            stats_card, 
            text="🕒 Last Block Time: Never", 
            style='primary.TLabel'
        )
        self.last_block_time_label.pack(anchor='w', padx=5, pady=2)
        
        # Log Card
        log_card = ttkbs.Labelframe(
            tab, 
            text="Mining Log", 
            bootstyle="secondary"
        )
        log_card.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.mining_log = ttkbs.ScrolledText(
            log_card, 
            height=10, 
            wrap=tk.WORD
        )

        self.mining_log.pack(fill='both', expand=True, padx=5, pady=5)
        self.mining_log.configure(state='disabled')

    def create_transactions_tab(self):
        """Create the transactions tab with modern layout"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Transactions")
        
        # Notebook for transaction sub-tabs
        tx_notebook = ttkbs.Notebook(tab, bootstyle="dark")
        tx_notebook.pack(expand=True, fill='both')
        
        # Send transaction tab
        self.create_send_tx_tab(tx_notebook)
        
        # View transactions tab
        self.create_view_tx_tab(tx_notebook)
        
        # Pending transactions tab
        self.create_pending_tx_tab(tx_notebook)

    def create_send_tx_tab(self, notebook):
        """Create the send transaction tab with modern form"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="💸 Send")
        
        form_card = ttkbs.Labelframe(
            tab, 
            text="Send Payment", 
            bootstyle="info"
        )
        form_card.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Recipient
        ttk.Label(form_card, text="Recipient Address:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.recipient_entry = ttkbs.Entry(form_card, width=50)
        self.recipient_entry.grid(row=0, column=1, padx=5, pady=5, sticky='we')
        ToolTip(self.recipient_entry, text="Enter recipient's wallet address")
        
        # Amount
        ttk.Label(form_card, text="Amount (ZYC):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.amount_entry = ttkbs.Entry(form_card)
        self.amount_entry.grid(row=1, column=1, padx=5, pady=5, sticky='w')
        ToolTip(self.amount_entry, text="Enter amount to send")
        
        # Transaction Type
        ttk.Label(form_card, text="Transaction Type:").grid(row=2, column=0, padx=5, pady=5, sticky='w')
        self.tx_type_var = tk.StringVar(value="STANDARD")
        
        type_frame = ttk.Frame(form_card)
        type_frame.grid(row=2, column=1, sticky='w')
        
        ttkbs.Radiobutton(
            type_frame, 
            text="Standard", 
            variable=self.tx_type_var, 
            value="STANDARD",
            bootstyle="info-toolbutton"
        ).pack(side='left')
        
        ttkbs.Radiobutton(
            type_frame, 
            text="Smart", 
            variable=self.tx_type_var, 
            value="SMART",
            bootstyle="info-toolbutton"
        ).pack(side='left', padx=5)
        
        # Fee display
        self.fee_label = ttk.Label(
            form_card, 
            text="💰 Estimated Fee: 0 ZYC", 
            style='primary.TLabel'
        )
        self.fee_label.grid(row=3, column=0, columnspan=2, pady=2, sticky='w')
        
        # Send Button
        send_btn = ttkbs.Button(
            form_card, 
            text="🚀 Send Payment", 
            command=self.send_payment,
            bootstyle="success"
        )
        send_btn.grid(row=4, column=0, columnspan=2, pady=10)
        ToolTip(send_btn, text="Send transaction to the network")
        
        # Status
        self.send_status = ttk.Label(
            form_card, 
            text="", 
            style='primary.TLabel'
        )
        self.send_status.grid(row=5, column=0, columnspan=2)

    def create_view_tx_tab(self, notebook):
        """Create the view transaction tab with modern layout"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="🔍 Details")
        
        search_card = ttkbs.Labelframe(
            tab, 
            text="Transaction Lookup", 
            bootstyle="info"
        )
        search_card.pack(fill='x', padx=10, pady=5)
        
        # TX ID input
        ttk.Label(search_card, text="Transaction ID:").pack(pady=5)
        self.tx_id_entry = ttkbs.Entry(search_card, width=70)
        self.tx_id_entry.pack(pady=5)
        
        # View button
        view_btn = ttkbs.Button(
            search_card, 
            text="🔎 View Details", 
            command=self.view_transaction_details,
            bootstyle="info-outline"
        )
        view_btn.pack(pady=5)
        
        # Details display
        details_card = ttkbs.Labelframe(
            tab, 
            text="Transaction Details", 
            bootstyle="secondary"
        )
        details_card.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.tx_details_text = ttkbs.ScrolledText(
            details_card, 
            height=15, 
            wrap=tk.WORD
        )

        self.tx_details_text.pack(fill='both', expand=True, padx=5, pady=5)
        self.tx_details_text.configure(state='disabled')

    def create_pending_tx_tab(self, notebook):
        """Create the pending transactions tab with modern table"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="⏳ Pending")
        
        # Refresh button
        refresh_btn = ttkbs.Button(
            tab, 
            text="🔄 Refresh Pending Transactions", 
            command=self.refresh_pending_tx,
            bootstyle="info-outline"
        )
        refresh_btn.pack(pady=10)
        
        # Treeview for pending transactions
        tree_card = ttkbs.Labelframe(
            tab, 
            text="Pending Transactions", 
            bootstyle="primary"
        )
        tree_card.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.pending_tx_tree = ttkbs.Treeview(
            tree_card, 
            columns=('txid', 'type', 'amount', 'fee'), 
            show='headings',
            bootstyle="dark"
        )
        
        # Configure columns
        self.pending_tx_tree.heading('txid', text='Transaction ID')
        self.pending_tx_tree.heading('type', text='Type')
        self.pending_tx_tree.heading('amount', text='Amount')
        self.pending_tx_tree.heading('fee', text='Fee')
        
        self.pending_tx_tree.column('txid', width=250)
        self.pending_tx_tree.column('type', width=80)
        self.pending_tx_tree.column('amount', width=100)
        self.pending_tx_tree.column('fee', width=80)
        
        # Add scrollbar
        scrollbar = ttkbs.Scrollbar(
            tree_card, 
            orient="vertical", 
            command=self.pending_tx_tree.yview,
            bootstyle="round"
        )
        self.pending_tx_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        self.pending_tx_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Load pending transactions
        self.refresh_pending_tx()

    def create_wallet_tab(self):
        """Create the wallet tab with modern layout and contact management"""
        self.wallet_tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.wallet_tab_frame, text="💳 Wallet")

        # Main container with scrollbar
        container = ScrolledFrame(self.wallet_tab_frame, autohide=True)
        container.pack(fill='both', expand=True)

        # Address display
        address_card = ttkbs.Labelframe(
            container, 
            text="Wallet Address", 
            bootstyle="info"
        )
        address_card.pack(fill='x', padx=10, pady=5)

        # Initialize wallet address if not exists
        if not hasattr(self, 'wallet_address'):
            try:
                self.wallet_address = self.key_manager.get_default_public_key()
            except Exception as e:
                self.log_message(f"Failed to get wallet address: {e}", "ERROR")
                self.wallet_address = "Address Unavailable"

        self.wallet_address_label = ttk.Label(
            address_card, 
            text=f"Your Address: {self.wallet_address}", 
            font=('Helvetica', 10),
            style='primary.TLabel'
        )
        self.wallet_address_label.pack(pady=5)

        # Balance display
        balance_card = ttkbs.Labelframe(
            container, 
            text="Balance", 
            bootstyle="success"
        )
        balance_card.pack(fill='x', padx=10, pady=5)

        balance_frame = ttk.Frame(balance_card)
        balance_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(balance_frame, text="Balance:", font=('Helvetica', 12)).pack(side='left', padx=5)
        self.balance_label = ttk.Label(
            balance_frame, 
            text="Loading...", 
            font=('Helvetica', 12, 'bold'),
            style='success.TLabel'
        )
        self.balance_label.pack(side='left', padx=5)

        # Contact Management Section
        contacts_card = ttkbs.Labelframe(
            container,
            text="Address Book",
            bootstyle="info"
        )
        contacts_card.pack(fill='x', padx=10, pady=5)

        # Contact Treeview
        self.contacts_tree = ttkbs.Treeview(
            contacts_card,
            columns=('name', 'address'),
            show='headings',
            bootstyle="dark",
            height=5
        )
        self.contacts_tree.heading('name', text='Contact Name')
        self.contacts_tree.heading('address', text='Wallet Address')
        self.contacts_tree.column('name', width=150)
        self.contacts_tree.column('address', width=300)
        self.contacts_tree.pack(fill='x', padx=5, pady=5)

        # Contact controls
        contact_controls = ttk.Frame(contacts_card)
        contact_controls.pack(fill='x', pady=5)

        ttk.Label(contact_controls, text="Name:").pack(side='left', padx=5)
        self.contact_name_entry = ttkbs.Entry(contact_controls, width=20)
        self.contact_name_entry.pack(side='left', padx=5)

        ttk.Label(contact_controls, text="Address:").pack(side='left', padx=5)
        self.contact_address_entry = ttkbs.Entry(contact_controls, width=40)
        self.contact_address_entry.pack(side='left', padx=5)

        btn_frame = ttk.Frame(contact_controls)
        btn_frame.pack(side='right', padx=5)

        ttkbs.Button(
            btn_frame,
            text="➕ Add",
            command=self.add_contact,
            bootstyle="success-outline",
            width=8
        ).pack(side='left', padx=2)

        ttkbs.Button(
            btn_frame,
            text="➖ Remove",
            command=self.remove_contact,
            bootstyle="danger-outline",
            width=8
        ).pack(side='left', padx=2)

        # UTXO frame
        utxo_card = ttkbs.Labelframe(
            container, 
            text="UTXOs", 
            bootstyle="primary"
        )
        utxo_card.pack(fill='both', expand=True, padx=10, pady=5)

        self.utxo_tree = ttkbs.Treeview(
            utxo_card, 
            columns=('txid', 'index', 'amount', 'locked'), 
            show='headings',
            bootstyle="dark"
        )
        self.utxo_tree.heading('txid', text='Transaction ID')
        self.utxo_tree.heading('index', text='Output Index')
        self.utxo_tree.heading('amount', text='Amount (ZYC)')
        self.utxo_tree.heading('locked', text='Locked')
        self.utxo_tree.column('txid', width=250)
        self.utxo_tree.column('index', width=80)
        self.utxo_tree.column('amount', width=100)
        self.utxo_tree.column('locked', width=80)

        scrollbar = ttkbs.Scrollbar(
            utxo_card, 
            orient="vertical", 
            command=self.utxo_tree.yview,
            bootstyle="round"
        )
        self.utxo_tree.configure(yscrollcommand=scrollbar.set)
        self.utxo_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons frame
        btn_card = ttkbs.Labelframe(
            container, 
            text="Actions", 
            bootstyle="secondary"
        )
        btn_card.pack(fill='x', padx=10, pady=5)

        btn_frame = ttk.Frame(btn_card)
        btn_frame.pack(fill='x', padx=5, pady=5)

        ttkbs.Button(
            btn_frame, 
            text="🔄 Refresh Balance", 
            command=self.refresh_wallet,
            bootstyle="info-outline"
        ).pack(side='left', padx=5)

        ttkbs.Button(
            btn_frame, 
            text="🆕 Generate New Address", 
            command=self.generate_new_address,
            bootstyle="info-outline"
        ).pack(side='left', padx=5)

        # Load initial data
        self.load_contacts()
        self.contacts_tree.bind("<Double-1>", self.on_contact_double_click)

        # Bind tab change event
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def on_tab_changed(self, event):
        """Handle tab change events"""
        selected_tab = self.notebook.select()
        tab_text = self.notebook.tab(selected_tab, "text")
        
        if tab_text == "💳 Wallet":
            self.refresh_wallet()

    def refresh_wallet(self):
        """Refresh the wallet balance and UTXOs"""
        try:
            # Clear existing items
            for item in self.utxo_tree.get_children():
                self.utxo_tree.delete(item)

            # Get UTXOs with error handling
            if not hasattr(self, 'utxo_manager') or not hasattr(self.utxo_manager, 'get_utxos_by_address'):
                self.log_message("UTXO Manager not initialized", "ERROR")
                self.balance_label.config(text="Balance: Error")
                return

            utxos = self.utxo_manager.get_utxos_by_address(self.wallet_address)
            total = Decimal("0")

            for u in utxos:
                try:
                    amt = Decimal(str(u.get("amount", "0")))
                    total += amt

                    tx_out_index = u.get("tx_out_index", u.get("output_index", 0))

                    self.utxo_tree.insert('', 'end', values=(
                        u.get("tx_out_id", "N/A"),
                        tx_out_index,
                        str(amt),
                        "Yes" if u.get('locked', False) else "No"
                    ))
                except Exception as e:
                    self.log_message(f"Skipping invalid UTXO: {e}", "WARNING")
                    continue

            # Update balance display
            self.balance_label.config(text=f"{total} ZYC")
            self.log_message(f"Wallet refreshed. Balance: {total} ZYC", "SUCCESS")

        except Exception as e:
            self.log_message(f"Failed to refresh wallet: {e}", "ERROR")
            self.balance_label.config(text="Balance: Error")

    def add_contact(self):
        """Add a new contact to the address book"""
        name = self.contact_name_entry.get().strip()
        address = self.contact_address_entry.get().strip()
        
        if not name or not address:
            messagebox.showerror("Error", "Both name and address are required")
            return
        
        try:
            # Validate address format
            if not self.key_manager.validate_address(address):
                messagebox.showerror("Error", "Invalid wallet address format")
                return
                
            # Load existing contacts
            contacts = self.load_contacts_from_file()
            
            # Check for duplicate name or address
            if name in contacts:
                messagebox.showerror("Error", "Contact name already exists")
                return
            if address in contacts.values():
                messagebox.showerror("Error", "Address already exists in contacts")
                return
                
            # Add new contact
            contacts[name] = address
            with open('contacts.json', 'w') as f:
                json.dump(contacts, f, indent=4)
                
            # Refresh UI
            self.load_contacts()
            self.contact_name_entry.delete(0, 'end')
            self.contact_address_entry.delete(0, 'end')
            self.log_message(f"Added contact: {name}", "SUCCESS")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add contact: {str(e)}")
            self.log_message(f"Failed to add contact: {str(e)}", "ERROR")

    def remove_contact(self):
        """Remove selected contact from address book"""
        selected = self.contacts_tree.selection()
        if not selected:
            messagebox.showerror("Error", "No contact selected")
            return
            
        try:
            name = self.contacts_tree.item(selected[0])['values'][0]
            contacts = self.load_contacts_from_file()
            
            if name in contacts:
                del contacts[name]
                with open('contacts.json', 'w') as f:
                    json.dump(contacts, f, indent=4)
                    
                self.load_contacts()
                self.log_message(f"Removed contact: {name}", "SUCCESS")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove contact: {str(e)}")
            self.log_message(f"Failed to remove contact: {str(e)}", "ERROR")

    def load_contacts(self):
        """Load contacts into the treeview"""
        for item in self.contacts_tree.get_children():
            self.contacts_tree.delete(item)
            
        contacts = self.load_contacts_from_file()
        for name, address in contacts.items():
            self.contacts_tree.insert('', 'end', values=(name, address))

    def load_contacts_from_file(self):
        """Load contacts from JSON file"""
        try:
            if os.path.exists('contacts.json'):
                with open('contacts.json', 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.log_message(f"Error loading contacts: {str(e)}", "ERROR")
            return {}





    def create_explorer_tab(self):
        """Create the explorer tab with modern layout"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🔎 Explorer")
        
        # Notebook for explorer sub-tabs
        explorer_notebook = ttkbs.Notebook(tab, bootstyle="dark")
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
        notebook.add(tab, text="📜 Transactions")
        
        # Search frame
        search_card = ttkbs.Labelframe(
            tab, 
            text="Transaction Search", 
            bootstyle="info"
        )
        search_card.pack(fill='x', padx=10, pady=5)
        
        # Search type
        ttk.Label(search_card, text="Search By:").grid(row=0, column=0, padx=5, sticky='w')
        self.tx_search_type = tk.StringVar(value="txid")
        
        ttkbs.Radiobutton(
            search_card, 
            text="TXID", 
            variable=self.tx_search_type, 
            value="txid",
            bootstyle="info-toolbutton"
        ).grid(row=0, column=1, sticky='w')
        
        ttkbs.Radiobutton(
            search_card, 
            text="Block Height", 
            variable=self.tx_search_type, 
            value="height",
            bootstyle="info-toolbutton"
        ).grid(row=0, column=2, sticky='w')
        
        # Search input
        ttk.Label(search_card, text="Value:").grid(row=1, column=0, padx=5, sticky='w')
        self.tx_search_entry = ttkbs.Entry(search_card, width=50)
        self.tx_search_entry.grid(row=1, column=1, columnspan=2, sticky='we', pady=5)
        
        # Search button
        search_btn = ttkbs.Button(
            search_card, 
            text="🔍 Search Transaction", 
            command=self.search_transaction,
            bootstyle="info-outline"
        )
        search_btn.grid(row=2, column=0, columnspan=3, pady=5)
        
        # Results display
        results_card = ttkbs.Labelframe(
            tab, 
            text="Transaction Details", 
            bootstyle="secondary"
        )
        results_card.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.tx_results = ttkbs.ScrolledText(
            results_card, 
            height=15, 
            wrap=tk.WORD
        )

        self.tx_results.pack(fill='both', expand=True, padx=5, pady=5)
        self.tx_results.configure(state='disabled')

    def create_utxo_explorer_tab(self, notebook):
        """Create UTXO explorer sub-tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="💰 UTXOs")
        
        # Address search
        search_card = ttkbs.Labelframe(
            tab, 
            text="UTXO Search", 
            bootstyle="info"
        )
        search_card.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(search_card, text="Wallet Address:").pack(pady=5)
        self.utxo_address_entry = ttkbs.Entry(search_card, width=50)
        self.utxo_address_entry.pack(pady=5)
        
        # Buttons frame
        btn_frame = ttk.Frame(search_card)
        btn_frame.pack(pady=5)
        
        ttkbs.Button(
            btn_frame, 
            text="🔍 Find UTXOs", 
            command=self.find_utxos,
            bootstyle="info-outline"
        ).pack(side='left', padx=5)
        
        ttkbs.Button(
            btn_frame, 
            text="🧮 Calculate Balance", 
            command=self.calculate_utxo_balance,
            bootstyle="info-outline"
        ).pack(side='left', padx=5)
        
        # UTXO Treeview
        tree_card = ttkbs.Labelframe(
            tab, 
            text="UTXOs", 
            bootstyle="primary"
        )
        tree_card.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.utxo_explorer_tree = ttkbs.Treeview(
            tree_card, 
            columns=('txid', 'index', 'amount', 'locked'), 
            show='headings',
            bootstyle="dark"
        )
        
        # Configure columns
        self.utxo_explorer_tree.heading('txid', text='Transaction ID')
        self.utxo_explorer_tree.heading('index', text='Output Index')
        self.utxo_explorer_tree.heading('amount', text='Amount (ZYC)')
        self.utxo_explorer_tree.heading('locked', text='Locked')
        
        self.utxo_explorer_tree.column('txid', width=250)
        self.utxo_explorer_tree.column('index', width=80)
        self.utxo_explorer_tree.column('amount', width=100)
        self.utxo_explorer_tree.column('locked', width=80)
        
        self.utxo_explorer_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Balance label
        self.utxo_balance_label = ttk.Label(
            tab, 
            text="💵 Balance: 0 ZYC", 
            font=('Helvetica', 12),
            style='success.TLabel'
        )
        self.utxo_balance_label.pack(pady=5)

    def create_orphan_blocks_tab(self, notebook):
        """Create orphan blocks explorer sub-tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="👻 Orphan Blocks")
        
        # Refresh button
        refresh_btn = ttkbs.Button(
            tab, 
            text="🔄 Refresh Orphan Blocks", 
            command=self.refresh_orphan_blocks,
            bootstyle="info-outline"
        )
        refresh_btn.pack(pady=10)
        
        # Orphan blocks treeview
        tree_card = ttkbs.Labelframe(
            tab, 
            text="Orphan Blocks", 
            bootstyle="primary"
        )
        tree_card.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.orphan_tree = ttkbs.Treeview(
            tree_card, 
            columns=('hash', 'height', 'tx_count'), 
            show='headings',
            bootstyle="dark"
        )
        
        # Configure columns
        self.orphan_tree.heading('hash', text='Block Hash')
        self.orphan_tree.heading('height', text='Height')
        self.orphan_tree.heading('tx_count', text='TX Count')
        
        self.orphan_tree.column('hash', width=300)
        self.orphan_tree.column('height', width=80)
        self.orphan_tree.column('tx_count', width=80)
        
        self.orphan_tree.pack(fill='both', expand=True, padx=5, pady=5)

    def create_export_tools_tab(self, notebook):
        """Create export tools sub-tab"""
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="📤 Export")
        
        # Export buttons
        export_card = ttkbs.Labelframe(
            tab, 
            text="Export Tools", 
            bootstyle="info"
        )
        export_card.pack(fill='both', expand=True, padx=10, pady=5)
        
        ttkbs.Button(
            export_card, 
            text="💾 Export Last 500 Blocks", 
            command=self.export_last_500_blocks,
            bootstyle="info-outline"
        ).pack(pady=10)
        
        ttkbs.Button(
            export_card, 
            text="📂 Select Custom Export Folder", 
            command=self.select_export_folder,
            bootstyle="info-outline"
        ).pack(pady=5)
        
        # Status label
        self.export_status = ttk.Label(
            export_card, 
            text="", 
            style='primary.TLabel'
        )
        self.export_status.pack(pady=5)

    def create_log_tab(self):
        """Create the log tab with modern styling"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📋 System Log")
        
        # Log display
        log_card = ttkbs.Labelframe(
            tab, 
            text="System Log", 
            bootstyle="secondary"
        )
        log_card.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.log_output = scrolledtext.ScrolledText(  # ✅ Use correct ScrolledText
            log_card, 
            height=20, 
            wrap=tk.WORD
        )
        self.log_output.pack(fill='both', expand=True, padx=5, pady=5)
        self.log_output.configure(state='disabled')
        
        # Clear button
        btn_frame = ttk.Frame(log_card)
        btn_frame.pack(fill='x', pady=5)
        
        ttkbs.Button(
            btn_frame, 
            text="🧹 Clear Log", 
            command=self.clear_log,
            bootstyle="danger-outline"
        ).pack(side='left', padx=5)
        
        ttkbs.Button(
            btn_frame, 
            text="📋 Copy Log", 
            command=self.copy_log,
            bootstyle="info-outline"
        ).pack(side='left', padx=5)



    def log_message(self, message, level="INFO"):
        """Log a message to the system log with different levels"""

        def update_log():
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Color coding based on level
                if level == "ERROR":
                    prefix = f"[{timestamp}] [ERROR] ❌ "
                    color = self.error_color
                elif level == "WARNING":
                    prefix = f"[{timestamp}] [WARN] ⚠️ "
                    color = self.warning_color
                elif level == "SUCCESS":
                    prefix = f"[{timestamp}] [SUCCESS] ✅ "
                    color = self.success_color
                else:
                    prefix = f"[{timestamp}] [INFO] ℹ️ "
                    color = self.text_color

                formatted_message = prefix + message

                # Only update GUI if log_output is ready
                if hasattr(self, "log_output") and hasattr(self.log_output, "insert"):
                    # Ensure tag exists
                    if not self.log_output.tag_names().__contains__(color):
                        self.log_output.tag_configure(color, foreground=color)

                    self.log_output.configure(state='normal')
                    self.log_output.insert(tk.END, formatted_message + "\n", color)
                    self.log_output.configure(state='disabled')
                    self.log_output.see(tk.END)

                # Update status bar if available
                if hasattr(self, "status_left") and hasattr(self.status_left, "config"):
                    self.status_left.config(
                        text=formatted_message[:50] + "..." if len(formatted_message) > 50 else formatted_message
                    )

                # Always print to console
                print(formatted_message)

            except Exception as e:
                print(f"Error logging message: {e} - Original message: {message}")

        # Queue log update safely
        if hasattr(self, "root") and callable(getattr(self.root, "after", None)):
            self.root.after(0, update_log)
        else:
            print(f"[LogHandler] Main loop not running, skipping message: {message}")


    def start_log_handler(self):
        """Start a thread to handle log messages safely with main-thread scheduling"""
        def log_handler():
            while True:
                try:
                    message, color = self.log_queue.get()

                    # ✅ This function will run on the main thread
                    def update_log_ui():
                        try:
                            self.log_output.configure(state='normal')
                            self.log_output.insert(tk.END, message + "\n", color)
                            self.log_output.configure(state='disabled')
                            self.log_output.see(tk.END)

                            # Update status bar
                            self.status_left.config(
                                text=message[:50] + "..." if len(message) > 50 else message
                            )
                        except Exception as ui_error:
                            print(f"[UI Update Error] ❌ {ui_error}")

                    # ✅ Schedule on main thread
                    self.root.after(0, update_log_ui)  # <-- This is the problematic part

                    self.log_queue.task_done()
                except Exception as thread_error:
                    print(f"[LogHandler Error] ❌ {thread_error}")
                time.sleep(0.1)

        threading.Thread(target=log_handler, daemon=True).start()


    def clear_log(self):
        """Clear the system log"""
        self.log_output.configure(state='normal')
        self.log_output.delete(1.0, tk.END)
        self.log_output.configure(state='disabled')
        self.log_message("Log cleared", "INFO")

    def copy_log(self):
        """Copy log contents to clipboard"""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log_output.get(1.0, tk.END))
        self.log_message("Log copied to clipboard", "INFO")

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

    def update_dashboard(self):
        """Update the dashboard with current blockchain information"""
        try:
            # Blockchain info
            latest_block = self.block_storage.get_latest_block()

            if latest_block is None:
                self.block_height_label.config(text="Block Height: 0")
                self.difficulty_label.config(text="Difficulty: 0")
                self.header_block_height.config(text="Height: 0")
            else:
                index = latest_block.index if hasattr(latest_block, "index") else latest_block.get("index", "N/A")
                difficulty = latest_block.difficulty if hasattr(latest_block, "difficulty") else latest_block.get("difficulty", "N/A")
                
                self.block_height_label.config(text=f"Block Height: {index}")
                self.difficulty_label.config(text=f"Difficulty: {difficulty}")
                self.header_block_height.config(text=f"Height: {index}")

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

            # Average mining time (last 10 blocks)
            blocks = self.block_storage.get_all_blocks()[-10:]
            if len(blocks) >= 2:
                timestamps = [b.timestamp if hasattr(b, "timestamp") else b.get("timestamp", 0) for b in blocks]
                intervals = [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]
                avg_mine_time = round(sum(intervals) / len(intervals), 2)
                self.avg_mine_time_label.config(text=f"Avg Mining Time: {avg_mine_time} sec")
            else:
                self.avg_mine_time_label.config(text="Avg Mining Time: N/A")

            self.log_message("Dashboard updated with latest blockchain statistics", "INFO")

        except Exception as e:
            self.log_message(f"Failed to update dashboard: {e}", "ERROR")

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
            
            self.log_message("Loaded recent blocks into explorer", "INFO")
        except Exception as e:
            self.log_message(f"Failed to load recent blocks: {e}", "ERROR")

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
                self.log_message(f"Found block: {search_value}", "SUCCESS")
            else:
                self.block_results.insert(tk.END, "Block not found")
                self.log_message(f"Block not found: {search_value}", "WARNING")
                
            self.block_results.configure(state='disabled')
            
        except Exception as e:
            self.log_message(f"Error searching block: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to search block: {e}")

    def start_mining(self):
        """Start the mining process"""
        if self.mining_active:
            return
            
        self.mining_active = True
        self.mining_status.config(text="⛏️ Mining: Running", bootstyle="success")
        self.start_mining_btn.config(state='disabled')
        self.stop_mining_btn.config(state='normal')
        
        # Start mining in a separate thread
        self.mining_thread = threading.Thread(
            target=self.mining_loop, 
            daemon=True,
            name="MiningThread"
        )
        self.mining_thread.start()
        
        self.log_message("Mining started", "SUCCESS")

    def stop_mining(self):
        """Stop the mining process"""
        if not self.mining_active:
            return
            
        try:
            # Stop the miner
            if hasattr(self, 'miner') and self.miner:
                if hasattr(self.miner, 'stop'):
                    self.miner.stop()
                else:
                    self.log_message("Miner doesn't have stop method", "WARNING")
                    self.mining_active = False
                    return
            
            # Update state
            self.mining_active = False
            self.mining_status.config(text="⛏️ Mining: Stopped", bootstyle="danger")
            self.start_mining_btn.config(state='normal')
            self.stop_mining_btn.config(state='disabled')
            
            # Wait for thread to finish (with timeout)
            if hasattr(self, 'mining_thread') and self.mining_thread.is_alive():
                self.mining_thread.join(timeout=2.0)
                if self.mining_thread.is_alive():
                    self.log_message("Mining thread didn't stop gracefully", "WARNING")
            
            self.log_message("Mining stopped", "INFO")
            
        except Exception as e:
            self.log_message(f"Error stopping miner: {e}", "ERROR")
            # Force state update even if error occurred
            self.mining_active = False
            self.mining_status.config(text="⛏️ Mining: Error", bootstyle="danger")
            self.start_mining_btn.config(state='normal')
            self.stop_mining_btn.config(state='disabled')


    def mining_loop(self):
        """Mining loop that runs in a separate thread"""
        blocks_mined = 0
        start_time = time.time()
        
        while self.mining_active and hasattr(self, 'miner'):
            try:
                # Mine a block
                result = self.miner.mine_block()
                
                if result and result.get('success'):
                    blocks_mined += 1
                    block_hash = result.get('block_hash', '')
                    
                    # Update UI in main thread
                    self.root.after(0, lambda: self.update_mining_stats(blocks_mined, block_hash))
                    
                    # Log the mined block
                    self.log_message(f"Mined block {block_hash}", "SUCCESS")
                    
                    # Update recent blocks
                    self.root.after(0, self.load_recent_blocks)
                    
                    # Update dashboard
                    self.root.after(0, self.update_dashboard)
                    
                elif result and not result.get('success'):
                    if result.get('message') == 'Mining stopped':
                        break
                        
            except Exception as e:
                self.log_message(f"Mining error: {e}", "ERROR")
                time.sleep(1)
                
            # Small delay to prevent CPU overload
            time.sleep(0.1)
        
        # Clean up when loop ends
        self.root.after(0, lambda: self.stop_mining())

    def update_mining_stats(self, blocks_mined, block_hash):
        """Update mining statistics"""
        self.blocks_mined_label.config(text=f"📦 Blocks Mined: {blocks_mined}")
        self.last_block_time_label.config(text=f"🕒 Last Block Time: {datetime.now().strftime('%H:%M:%S')}")
        
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
                    hashrate = self.calculate_hashrate()
                    self.root.after(0, self.hashrate_label.config, 
                                   {"text": f"⚡ Hashrate: {hashrate:.2f} H/s"})
                time.sleep(5)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()





    def cleanup(self):
        """Cleanup resources on exit"""
        try:
            self.log_message("Shutting down...", "INFO")
            self.stop_mining()
            
            # Close LMDB environments
            if hasattr(self, 'tx_storage') and self.tx_storage:
                self.tx_storage.close()
            if hasattr(self, 'utxo_storage') and self.utxo_storage:
                self.utxo_storage.close()
            if hasattr(self, 'block_storage') and self.block_storage:
                self.block_storage.close()
                
            self.log_message("Cleanup complete", "INFO")
        except Exception as e:
            self.log_message(f"Cleanup error: {e}", "ERROR")





    def view_wallet(self):
        """Display wallet balance and address info in UI or console"""
        try:
            address = self.key_manager.get_address()
            utxos = self.utxo_manager.get_utxos_by_address(address)
            total_balance = sum(u.amount for u in utxos)

            print("\n===== 👜 WALLET VIEW =====")
            print(f"Address: {address}")
            print(f"Balance: {total_balance} ZYC")
            print(f"Total UTXOs: {len(utxos)}")
            for i, utxo in enumerate(utxos, 1):
                print(f"{i}. Amount: {utxo.amount} | TXID: {utxo.tx_out_id.hex()}")
            print("==========================\n")

            # Optional: push this info to a wallet panel in the UI
            # self.wallet_display_panel.update(address, total_balance, utxos)

        except Exception as e:
            print(f"[view_wallet] ❌ Failed to load wallet: {e}")




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
        
        self.log_message(f"Starting transaction: {amount} ZYC to {recipient}", "INFO")
        
        tx_id = self.payment_processor.send_payment(
            sender_priv_key=priv_key,
            sender_pub_key=pub_key,
            recipient_address=recipient,
            amount=amount,
            tx_type=tx_type
        )
        
        if tx_id:
            self.send_status.config(text=f"✅ Transaction sent! TXID: {tx_id}", style='success.TLabel')
            self.log_message(f"Transaction sent: {tx_id}", "SUCCESS")
            
            # Refresh pending transactions
            self.refresh_pending_tx()
            
            # Refresh wallet balance
            self.refresh_wallet()
        else:
            self.send_status.config(text="❌ Failed to send transaction", style='danger.TLabel')
            self.log_message("Transaction failed", "ERROR")

    def view_transaction_details(self):
        """View details of a transaction"""
        tx_id = self.tx_id_entry.get().strip()
        if not tx_id:
            messagebox.showerror("Error", "Please enter a transaction ID")
            return
            
        self.log_message(f"Looking up transaction {tx_id}", "INFO")
        tx_data = self.tx_storage.get_transaction(tx_id)
        
        self.tx_details_text.configure(state='normal')
        self.tx_details_text.delete(1.0, tk.END)
        
        if not tx_data:
            self.tx_details_text.insert(tk.END, "Transaction not found")
            self.log_message("Transaction not found", "WARNING")
        else:
            for key, value in tx_data.items():
                self.tx_details_text.insert(tk.END, f"{key}: {value}\n")
            self.log_message(f"Found transaction with {len(tx_data)} details", "SUCCESS")
            
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
                self.log_message("No pending transactions", "INFO")
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
                    self.log_message(f"Skipped malformed transaction: {tx_error}", "WARNING")

            self.log_message(f"Loaded {count} pending transactions", "SUCCESS")

        except Exception as e:
            self.log_message(f"Failed to refresh pending transactions: {e}", "ERROR")




    def generate_new_address(self):
        """Generate a new wallet address"""
        try:
            # Generate new key pair
            new_key = self.key_manager.generate_new_keypair()
            self.wallet_address = new_key['hashed_public_key']
            self.wallet_address_label.config(text=f"Your Address: {self.wallet_address}")
            
            # Update UI
            self.refresh_wallet()
            
            self.log_message(f"Generated new address: {self.wallet_address}", "SUCCESS")
            messagebox.showinfo("New Address", f"New address generated:\n{self.wallet_address}")
            
        except Exception as e:
            self.log_message(f"Failed to generate new address: {e}", "ERROR")
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
                    self.log_message(f"Found transaction: {search_value}", "SUCCESS")
                else:
                    self.tx_results.insert(tk.END, "Transaction not found")
                    self.log_message(f"Transaction not found: {search_value}", "WARNING")
                    
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
                    self.log_message(f"Found {len(txs)} transactions at height {search_value}", "SUCCESS")
                else:
                    self.tx_results.insert(tk.END, f"No transactions found at height {search_value}")
                    self.log_message(f"No transactions at height: {search_value}", "WARNING")
                    
            self.tx_results.configure(state='disabled')
            
        except Exception as e:
            self.log_message(f"Error searching transaction: {e}", "ERROR")
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
                self.log_message(f"Found {len(utxos)} UTXOs for address {address}", "SUCCESS")
            else:
                self.log_message(f"No UTXOs found for address {address}", "WARNING")
                
        except Exception as e:
            self.log_message(f"Error finding UTXOs: {e}", "ERROR")
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
            
            self.utxo_balance_label.config(text=f"💵 Balance: {total_balance} ZYC")
            self.log_message(f"Balance for {address}: {total_balance} ZYC", "SUCCESS")
            
        except Exception as e:
            self.log_message(f"Error calculating balance: {e}", "ERROR")
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
                self.log_message(f"Displayed {len(orphan_blocks)} orphan blocks", "SUCCESS")
            else:
                self.log_message("No orphan blocks found", "INFO")
                
        except Exception as e:
            self.log_message(f"Error fetching orphan blocks: {e}", "ERROR")
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
            self.log_message(f"Exported {len(block_data)} blocks to {output_path}", "SUCCESS")
            
            # Open the export folder
            os.startfile(os.path.abspath(self.export_folder))
            
        except Exception as e:
            self.export_status.config(text=f"❌ Export failed: {e}")
            self.log_message(f"Export failed: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to export blocks: {e}")

    def select_export_folder(self):
        """Select a custom export folder"""
        folder = filedialog.askdirectory(title="Select Export Folder")
        if folder:
            self.export_folder = folder
            self.export_status.config(text=f"Export folder set to: {folder}")
            self.log_message(f"Set export folder to: {folder}", "INFO")

    def validate_blockchain(self):
        """Validate the blockchain integrity"""
        try:
            valid = self.blockchain.validate_chain()
            if valid is None:
                messagebox.showwarning("Validation", "Validation returned None. Possible corruption detected.")
                self.log_message("WARNING: Validation returned None", "WARNING")
            elif valid:
                messagebox.showinfo("Validation", "Blockchain validation passed.")
                self.log_message("Blockchain validation passed", "SUCCESS")
            else:
                messagebox.showerror("Validation", "Blockchain validation failed!")
                self.log_message("ERROR: Blockchain validation failed", "ERROR")
        except Exception as e:
            messagebox.showerror("Error", f"Blockchain validation failed: {e}")
            self.log_message(f"Validation failed: {e}", "ERROR")

    def show_stats(self):
        """Show statistics in a new window with actual data"""
        stats_window = tk.Toplevel(self.root)
        stats_window.title("Blockchain Statistics")
        stats_window.geometry("600x400")

        ttk.Label(stats_window, text="Blockchain Statistics", font=('Helvetica', 16)).pack(pady=10)

        try:
            latest_block = self.block_storage.get_latest_block()
            block_height = getattr(latest_block, 'index', latest_block.get('index', 0)) if latest_block else 0
            total_tx = self.tx_storage.get_transaction_count()
            mempool_size = self.mempool_storage.get_pending_transaction_count()
            utxo_count = len(self.utxo_storage.get_all_utxos())
            orphan_count = len(self.orphan_blocks.get_all_orphans())

            blocks = self.block_storage.get_all_blocks()[-10:]
            avg_block_time = "N/A"
            if len(blocks) >= 2:
                timestamps = []
                for b in blocks:
                    if hasattr(b, 'timestamp'):
                        timestamps.append(b.timestamp)
                    elif isinstance(b, dict) and 'timestamp' in b:
                        timestamps.append(b['timestamp'])

                if len(timestamps) >= 2:
                    intervals = [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]
                    avg_block_time = f"{sum(intervals) / len(intervals):.2f} sec"

            stats = [
                f"Block Height: {block_height}",
                f"Total Transactions: {total_tx}",
                f"Mempool Size: {mempool_size}",
                f"UTXO Count: {utxo_count}",
                f"Orphan Blocks: {orphan_count}",
                f"Avg Block Time (last 10): {avg_block_time}"
            ]

            for stat in stats:
                ttk.Label(stats_window, text=stat).pack(anchor='w', padx=20, pady=2)

        except Exception as e:
            ttk.Label(stats_window, text=f"Error loading stats: {e}").pack()


    def on_contact_double_click(self, event):
        """Handle contact double-click to populate Send tab"""
        selected = self.contacts_tree.selection()
        if selected:
            item = self.contacts_tree.item(selected[0])
            address = item['values'][1]  # Assuming address is the second column
            self.recipient_entry.delete(0, tk.END)
            self.recipient_entry.insert(0, address)
            # Switch to Send tab (index may vary)
            self.notebook.select(3)  # Adjust based on your tab order


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
                self.log_message(f"Failed to calculate hashrate: {e}", "ERROR")
                return 0.0
        
    def auto_refresh_ui(self):
        """Auto-refresh all dynamic UI sections"""
        while True:
            try:
                self.root.after(0, self.update_dashboard)
                self.root.after(0, self.load_recent_blocks)
                self.root.after(0, self.refresh_wallet)
                self.root.after(0, self.update_mining_stats_display)
                time.sleep(300)
            except Exception as e:
                self.log_message(f"UI update error: {e}", "ERROR")
                break

    def update_mining_stats_display(self):
        """Refresh hash rate and last mined block stats"""
        try:
            hashrate = self.calculate_hashrate()
            self.hashrate_label.config(text=f"⚡ Hashrate: {hashrate:.2f} H/s")
        except Exception as e:
            self.log_message(f"Failed to update mining stats: {e}", "ERROR")

    def cleanup(self):
        """Cleanup resources on exit"""
        self.log_message("Shutting down...", "INFO")
        self.stop_mining()
        
        # Close LMDB environments
        if hasattr(self, 'utxo_db'):
            self.utxo_db.close()
        if hasattr(self, 'utxo_history_db'):
            self.utxo_history_db.close()
        
        self.log_message("Cleanup complete", "INFO")



class UIPaymentProcessor:
    """
    Handles payment processing for the UI layer with enhanced logging and validation.
    This should be used for UI interactions while the core PaymentProcessor handles backend logic.
    """
    
    def __init__(self, utxo_manager, tx_storage, standard_mempool, smart_mempool, key_manager, fee_model=None):
        self.utxo_manager = utxo_manager
        self.tx_storage = tx_storage
        self.standard_mempool = standard_mempool
        self.smart_mempool = smart_mempool
        self.key_manager = key_manager

        if fee_model is not None:
            self.fee_model = fee_model
            print("[UIPaymentProcessor] ✅ Using provided fee_model.")
        else:
            self.fee_model = FeeModel(Constants.MAX_SUPPLY)
            print("[UIPaymentProcessor] ✅ Created internal FeeModel.")



    
    @staticmethod
    def is_main_thread():
        """Check if we're in the main thread"""
        import threading
        return isinstance(threading.current_thread(), threading._MainThread)


    @staticmethod
    def is_window_alive(window):
        """Safely check if a tkinter window exists"""
        try:
            return window.winfo_exists()
        except (tk.TclError, RuntimeError):
            return False









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

    try:
        # Initialize the root Tkinter window with themed style
        root = ttkbs.Window(themename="darkly")
        root.title("Zyiron Chain Explorer")

        # Optional: Set window icon
        try:
            root.iconbitmap('zyiron_icon.ico')
        except Exception as e:
            print(f"[Icon Warning] Could not set icon: {e}")

        # Create the UI
        app = BlockchainUI(root)

        # Force immediate widget rendering before mainloop
        root.update_idletasks()

        # Start main event loop
        root.mainloop()

    except Exception as e:
        print(f"[Startup Error] UI crashed: {e}")
