import sys
import os
import base64
import json

import hashlib 
from hashlib import sha3_384

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

import sys
import os
import base64
import json
import secrets
import time
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QPushButton, QTextEdit, QFileDialog, QHBoxLayout, QMessageBox, QProgressBar, QLineEdit, QDialog, QStackedWidget, QInputDialog
)
from PyQt6.QtGui import QClipboard, QFont, QPixmap, QColor, QLinearGradient, QPainter
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from hashlib import sha3_512
from Crypto.Cipher import AES
from Zyiron_Chain.falcon.falcon.falcon import SecretKey, PublicKey
from Zyiron_Chain.accounts.wallet import Wallet  # Importing the existing wallet logic


class TransactionDialog(QDialog):
    """Dialog for entering transaction details."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Send Transaction")
        self.setGeometry(400, 200, 400, 400)
        self.setStyleSheet("""
            QDialog {
                background-color: #2E2E2E;
                color: #FFFFFF;
                font-family: "Arial";
                font-size: 14px;
                border-radius: 10px;
            }
            QLabel {
                color: #FFFFFF;
                font-weight: bold;
            }
            QLineEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #9a6aff;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton {
                background-color: #9a6aff;
                color: #000000;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7d4fd1;
            }
        """)

        layout = QVBoxLayout()

        self.address_label = QLabel("Recipient Address:")
        self.address_input = QLineEdit()
        layout.addWidget(self.address_label)
        layout.addWidget(self.address_input)

        self.amount_label = QLabel("Amount:")
        self.amount_input = QLineEdit()
        layout.addWidget(self.amount_label)
        layout.addWidget(self.amount_input)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.accept)
        layout.addWidget(self.send_button)

        self.setLayout(layout)

    def get_transaction_details(self):
        """Return the recipient address and amount."""
        return self.address_input.text(), self.amount_input.text()


class WalletManagerDialog(QDialog):
    """Dialog for managing wallets."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Wallet Manager")
        self.setGeometry(200, 200, 600, 400)
        self.setStyleSheet("""
            QDialog {
                background-color: #2E2E2E;
                color: #FFFFFF;
                font-family: "Arial";
                font-size: 14px;
                border-radius: 10px;
            }
            QLabel {
                color: #FFFFFF;
                font-weight: bold;
            }
            QPushButton {
                background-color: #9a6aff;
                color: #000000;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7d4fd1;
            }
        """)

        layout = QVBoxLayout()

        self.wallet_list_label = QLabel("Your Wallets:")
        self.wallet_list = QTextEdit()
        self.wallet_list.setReadOnly(True)
        layout.addWidget(self.wallet_list_label)
        layout.addWidget(self.wallet_list)

        self.create_wallet_button = QPushButton("Create New Wallet")
        self.create_wallet_button.clicked.connect(self.create_wallet)
        layout.addWidget(self.create_wallet_button)

        self.setLayout(layout)

    def create_wallet(self):
        """Create new wallet with seed integration"""
        wallet_name, ok = QInputDialog.getText(self, "Create Wallet", "Enter wallet name:")
        if ok and wallet_name:
            try:
                # Generate deterministic seed if needed
                if not self.seed:
                    self.generate_seed()
                
                # Initialize wallet with seed
                self.current_wallet = Wallet()
                self.wallets[wallet_name] = self.current_wallet
                
                # Store seed with wallet
                self.current_wallet.seed = self.seed
                
                self.output_display.append(f"✅ Wallet '{wallet_name}' created successfully!")
            except Exception as e:
                self.output_display.append(f"❌ Error creating wallet: {str(e)}")

    def _generate_address_from_seed(self, seed):
        """DEPRECATE THIS METHOD - Use Wallet class instead"""


class HKTDWalletUI(QWidget):
    def __init__(self):
        super().__init__()  # Initialize parent first
        # Initialize instance variables
        self.wallets = {}
        self.current_wallet = None
        self.failed_attempts = 0
        self.max_attempts = 10
        self.seed = None
        self.addresses = {}
        self.encrypted_wallet_data = None

        # Configure main window
        self.setWindowTitle("Zyiron HKTD Wallet")
        self.setGeometry(100, 100, 1200, 900)
        
        # Setup UI components
        self.init_ui()
    def init_ui(self):
        """Initialize all UI components"""
        # Styling and layout setup
        self.setStyleSheet("""
            QWidget {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1E1E1E, stop:1 #000000);
                color: #FFFFFF;
                font-family: "Arial";
                font-size: 14px;
                border-radius: 15px;
            }
            QPushButton { background-color: #9a6aff; color: #000000; padding: 10px; border-radius: 5px; }
            QPushButton:hover { background-color: #7d4fd1; }
            QTextEdit, QLineEdit { background-color: #1E1E1E; color: #FFFFFF; border: 1px solid #9a6aff; }
            QLabel { color: #FFFFFF; font-weight: bold; }
        """)

        layout = QVBoxLayout()

        # Top bar components
        top_bar = QHBoxLayout()
        self.balance_label = QLabel("Balance: 0.00000000 ZYC")
        self.balance_label.setFont(QFont("Rockwell", 45, QFont.Weight.Bold))
        
        # Control buttons
        self.sign_in_button = QPushButton("Sign In")
        self.sign_out_button = QPushButton("Sign Out")
        self.wallets_button = QPushButton("Wallets")
        
        # Add components to layout
        top_bar.addWidget(self.balance_label)
        top_bar.addWidget(self.sign_in_button)
        top_bar.addWidget(self.sign_out_button)
        top_bar.addWidget(self.wallets_button)
        layout.addLayout(top_bar)

        # Logo
        self.logo_label = QLabel()
        self.logo_label.setPixmap(QPixmap("logo.png").scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio))
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.logo_label)

        # Seed section
        seed_layout = QHBoxLayout()
        self.seed_display = QTextEdit()
        self.seed_display.setReadOnly(True)
        seed_layout.addWidget(QLabel("Generated 2048-bit Seed:"))
        seed_layout.addWidget(QPushButton("Copy Seed", clicked=self.copy_seed))
        layout.addLayout(seed_layout)
        layout.addWidget(self.seed_display)

        # Action buttons
        layout.addWidget(QPushButton("Generate New Seed", clicked=self.generate_seed))
        layout.addWidget(QPushButton("Generate Address", clicked=self.generate_address))
        
        # Address display
        self.address_display = QTextEdit()
        self.address_display.setReadOnly(True)
        layout.addWidget(QLabel("Addresses:"))
        layout.addWidget(self.address_display)

        # Output console
        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        layout.addWidget(self.output_display)

        self.setLayout(layout)

        # Connect signals
        self.sign_in_button.clicked.connect(self.sign_in)
        self.sign_out_button.clicked.connect(self.sign_out)
        self.wallets_button.clicked.connect(self.open_wallet_manager)

    # Keep all other methods unchanged from previous implementation
    # (generate_seed, sign_in, sign_out, etc.)

    def generate_address(self):
        """Generate a new address using the Wallet class"""
        if not self.current_wallet:
            QMessageBox.warning(self, "Error", "No active wallet!")
            return

        try:
            # Generate for both networks
            testnet_address = self.current_wallet.public_key("testnet")
            mainnet_address = self.current_wallet.public_key("mainnet")
            
            self.address_display.append(
                f"🔹 Testnet: {testnet_address}\n"
                f"🔹 Mainnet: {mainnet_address}"
            )
            self.output_display.append("✅ Addresses generated successfully!")
        except Exception as e:
            self.output_display.append(f"❌ Error generating addresses: {str(e)}")


        # Modern UI Styling with Gradient
        self.setStyleSheet("""
            QWidget {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1E1E1E, stop:1 #000000);
                color: #FFFFFF;
                font-family: "Arial";
                font-size: 14px;
                border-radius: 15px;
            }
            QPushButton {
                background-color: #9a6aff;
                color: #000000;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7d4fd1;
            }
            QTextEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #9a6aff;
                border-radius: 5px;
                padding: 10px;
            }
            QLabel {
                color: #FFFFFF;
                font-weight: bold;
            }
            QProgressBar {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #9a6aff;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #9a6aff;
                border-radius: 5px;
            }
        """)

        # UI Layout
        layout = QVBoxLayout()

        # Top Bar (Balance and Buttons)
        top_bar_layout = QHBoxLayout()
        self.balance_label = QLabel("Balance: 0.00000000 ZYC ")
        self.balance_label.setFont(QFont("Rockwell", 45, QFont.Weight.Bold))
        top_bar_layout.addWidget(self.balance_label, alignment=Qt.AlignmentFlag.AlignRight)

        self.sign_in_button = QPushButton("Sign In")
        self.sign_in_button.clicked.connect(self.sign_in)
        self.sign_out_button = QPushButton("Sign Out")
        self.sign_out_button.clicked.connect(self.sign_out)
        self.wallets_button = QPushButton("Wallets")
        self.wallets_button.clicked.connect(self.open_wallet_manager)

        # Make buttons smaller
        self.sign_in_button.setFixedSize(85, 40)
        self.sign_out_button.setFixedSize(85, 40)
        self.wallets_button.setFixedSize(85, 40)

        top_bar_layout.addWidget(self.sign_in_button)
        top_bar_layout.addWidget(self.sign_out_button)
        top_bar_layout.addWidget(self.wallets_button)

        layout.addLayout(top_bar_layout)

        # Logo Area
        self.logo_label = QLabel()
        self.logo_label.setPixmap(QPixmap("C:/Users/PC/Desktop/Zyiron_Chain/Zyiron_Chain/logo/logo.png").scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio))
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.logo_label)

        # Seed Section
        self.seed_label = QLabel("Generated 2048-bit Seed:")
        self.seed_display = QTextEdit()
        self.seed_display.setReadOnly(True)
        self.copy_seed_button = QPushButton("Copy Seed")
        self.copy_seed_button.clicked.connect(self.copy_seed)

        seed_layout = QHBoxLayout()
        seed_layout.addWidget(self.seed_label)
        seed_layout.addWidget(self.copy_seed_button)

        layout.addLayout(seed_layout)
        layout.addWidget(self.seed_display)

        # Buttons
        self.generate_seed_button = QPushButton("Generate New Seed")
        self.generate_seed_button.clicked.connect(self.generate_seed)
        layout.addWidget(self.generate_seed_button)

        # Generate Address Button
        self.generate_address_button = QPushButton("Generate Address")
        self.generate_address_button.clicked.connect(self.generate_address)
        layout.addWidget(self.generate_address_button)

        # Address Section
        self.address_label = QLabel("Addresses:")
        self.address_display = QTextEdit()
        self.address_display.setReadOnly(True)
        layout.addWidget(self.address_label)
        layout.addWidget(self.address_display)

        # Add Address Section
        self.add_address_button = QPushButton("Add Address")
        self.add_address_button.clicked.connect(self.add_address)
        layout.addWidget(self.add_address_button)

        # Output Display
        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        layout.addWidget(self.output_display)

        # Loading Animation
        self.loading_label = QLabel("Loading...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.hide()  # Hide by default
        layout.addWidget(self.loading_label)

        # Timer for loading animation
        self.loading_timer = QTimer()
        self.loading_timer.timeout.connect(self.update_loading_animation)

        self.setLayout(layout)

    def update_loading_animation(self):
        """Update the loading animation."""
        if self.loading_label.text() == "Loading...":
            self.loading_label.setText("Loading.")
        elif self.loading_label.text() == "Loading.":
            self.loading_label.setText("Loading..")
        elif self.loading_label.text() == "Loading..":
            self.loading_label.setText("Loading...")

    def show_loading(self, message):
        """Show loading animation."""
        self.loading_label.setText(message)
        self.loading_label.show()
        self.loading_timer.start(500)  # Update every 500ms

    def hide_loading(self):
        """Hide loading animation."""
        self.loading_timer.stop()
        self.loading_label.hide()

    def generate_address(self):
        """Generate a new address and display it."""
        if not self.seed:
            QMessageBox.warning(self, "Error", "No seed generated. Please generate a seed first!")
            return

        # Generate a new address using the seed
        address = self._generate_address_from_seed(self.seed)
        self.address_display.append(f"🔹 {address}")
        self.output_display.append("✅ Address generated successfully!")

    def _generate_address_from_seed(self, seed):
        """Generate an address from the seed."""
        # Use the seed to derive a deterministic address
        # For simplicity, we'll hash the seed and use the result as the address
        address = hashlib.sha256(seed.encode()).hexdigest()
        return address

    def add_address(self):
        """Add an address with a name."""
        address, ok1 = QInputDialog.getText(self, "Add Address", "Enter address:")
        if ok1 and address:
            name, ok2 = QInputDialog.getText(self, "Add Address", "Enter name for the address:")
            if ok2 and name:
                self.addresses[name] = address
                self.address_display.append(f"🔹 {name}: {address}")
                self.output_display.append(f"✅ Address '{name}' added successfully!")

    def save_wallet(self):
        """Save the wallet to a file."""
        if not self.wallet:
            QMessageBox.warning(self, "Error", "No wallet to save.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Wallet", "", "Wallet Files (*.wallet)")
        if file_path:
            with open(file_path, "w") as f:
                json.dump(self.wallet.to_dict(), f)
            self.output_display.append(f"✅ Wallet saved to {file_path}")

    def generate_seed(self):
        """Generate a 2048-bit seed in hexadecimal."""
        self.seed = secrets.token_hex(256)  # 2048 bits = 256 bytes
        self.seed_display.setText(self.seed)
        self.output_display.append("✅ 2048-bit seed generated successfully!")

        # Show pop-up warning to save the seed
        QMessageBox.warning(
            self, "Save Your Seed",
            "Please save this 2048-bit seed securely. It is your master password and the only way to recover your wallet.",
            QMessageBox.StandardButton.Ok
        )
    def generate_wallet_keys(self):
        """Generate keys using the wallet module."""
        if not self.seed:
            self.output_display.append("⚠️ Please generate a seed first!")
            return

        self.show_loading_dialog("Generating wallet keys")
        self.wallet = Wallet()

        # Display public key
        self.public_key_display.setText(self.wallet.public_key('testnet'))

        # Serialize the private key to bytes
        try:
            if hasattr(self.wallet.testnet_secret_key, "export_key"):
                private_key_bytes = self.wallet.testnet_secret_key.export_key()
            elif hasattr(self.wallet.testnet_secret_key, "to_bytes"):
                private_key_bytes = self.wallet.testnet_secret_key.to_bytes()
            elif hasattr(self.wallet.testnet_secret_key, "__str__"):
                private_key_bytes = str(self.wallet.testnet_secret_key).encode()
            else:
                raise TypeError("Unsupported Falcon private key format.")
            
            # Display the private key in hexadecimal format
            self.private_key_display.setText(private_key_bytes.hex())
        except Exception as e:
            self.output_display.append(f"❌ Error: Unable to serialize private key. {str(e)}")
            return

        self.output_display.append("✅ Wallet keys generated!")
        self.output_display.append(f"🔹 Testnet Address: {self.wallet.public_key('testnet')}")
        self.output_display.append(f"🔹 Mainnet Address: {self.wallet.public_key('mainnet')}")
    def aes_encrypt(self, data):
        """Encrypt data using AES-256-GCM with SHA3-512 key derivation."""
        key = sha3_512(self.seed.encode()).digest()[:32]  # Derive AES key from seed using SHA3-512
        iv = os.urandom(12)
        cipher = AES.new(key, AES.MODE_GCM, iv)
        ciphertext, tag = cipher.encrypt_and_digest(data.encode())
        return base64.b64encode(iv + ciphertext + tag).decode()

    def encrypt_private_key(self):
        """Encrypt Falcon private key securely before storing it."""
        if not self.wallet:
            self.output_display.append("⚠️ Please generate wallet keys first!")
            return

        self.show_loading_dialog("Encrypting private key")

        # Ensure testnet_secret_key exists
        if not hasattr(self.wallet, 'testnet_secret_key'):
            self.output_display.append("⚠️ Wallet keys are missing! Please regenerate them.")
            return

        # Try to extract the private key in bytes
        try:
            if isinstance(self.wallet.testnet_secret_key, bytes):
                private_key_bytes = self.wallet.testnet_secret_key
            elif hasattr(self.wallet.testnet_secret_key, "to_bytes"):
                private_key_bytes = self.wallet.testnet_secret_key.to_bytes()
            elif hasattr(self.wallet.testnet_secret_key, "__str__"):
                private_key_bytes = self.wallet.testnet_secret_key.__str__().encode()
            else:
                raise TypeError("Unsupported Falcon private key format.")
        except Exception as e:
            self.output_display.append(f"❌ Error extracting Falcon private key: {str(e)}")
            return

        # Convert private key to Base64 (safe for JSON storage)
        private_key_base64 = base64.b64encode(private_key_bytes).decode()
        self.output_display.append(f"🔹 Encrypted Private Key: {private_key_base64}")

        # Encrypt with AES
        encrypted_private_key = self.aes_encrypt(private_key_base64)

        # Store encrypted key in JSON format
        self.encrypted_wallet_data = {"encrypted_key": encrypted_private_key, "seed": self.seed}
        with open("encrypted_wallet.json", "w") as f:
            json.dump(self.encrypted_wallet_data, f)

        self.output_display.append("✅ Private key encrypted and stored successfully!")
    def sign_in(self):
        """Sign in using the 2048-bit seed phrase."""
        if self.failed_attempts >= self.max_attempts:
            self.output_display.append("❌ Account locked due to too many failed attempts.")
            return

        seed = self.seed_display.toPlainText()
        if seed == self.seed:
            self.output_display.append("✅ Signed in successfully!")
            self.failed_attempts = 0  # Reset failed attempts on successful sign-in
        else:
            self.failed_attempts += 1
            self.output_display.append(f"❌ Invalid seed phrase! {self.max_attempts - self.failed_attempts} attempts remaining.")

    def sign_out(self):
        """Sign out and clear the wallet data."""
        self.wallet = None
        self.seed = None
        self.encrypted_wallet_data = None
        self.seed_display.clear()
        self.address_display.clear()
        self.output_display.append("✅ Signed out successfully!")

    def open_wallet_manager(self):
        """Open the wallet manager dialog."""
        wallet_manager = WalletManagerDialog(self)
        wallet_manager.exec()

    def copy_seed(self):
        """Copy the seed phrase to the clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.seed_display.toPlainText())
        self.output_display.append("✅ Seed copied to clipboard!")

    def paste_seed(self):
        """Paste the seed phrase from the clipboard."""
        clipboard = QApplication.clipboard()
        self.seed_display.setText(clipboard.text())
        self.output_display.append("✅ Seed pasted from clipboard!")

    def copy_public_key(self):
        """Copy the public key to the clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.public_key_display.toPlainText())
        self.output_display.append("✅ Public key copied to clipboard!")

    def copy_private_key(self):
        """Copy the private key to the clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.private_key_display.toPlainText())
        self.output_display.append("✅ Private key copied to clipboard!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HKTDWalletUI()
    window.show()
    sys.exit(app.exec())
