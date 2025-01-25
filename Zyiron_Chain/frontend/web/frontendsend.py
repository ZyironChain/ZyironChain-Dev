import sys
import os

# Add the root directory of your project to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))




from flask import Flask, render_template, request
from Kyiron_Chain.blockchain.wallet import Wallet
from Kyiron_Chain.blockchain.blockchain import Blockchain
from Kyiron_Chain.blockchain.utils.key_manager import KeyManager

import os

app = Flask(__name__)

# Globals for blockchain and UTXO management
BLOCKCHAIN = None
UTXOS = {}
MEMPOOL = {}

def initialize_blockchain():
    """
    Initialize the blockchain by loading it from disk or creating a new one.
    """
    global BLOCKCHAIN

    # Initialize the KeyManager
    key_manager = KeyManager("kc/blockchain_data/keys.json")

    try:
        # Load blockchain from JSON file or create a new one
        BLOCKCHAIN = Blockchain.load_blockchain("kc/blockchain_data/blockchain.json", key_manager)
    except Exception as e:
        print(f"[ERROR] Failed to initialize blockchain: {e}")


def send_transaction(from_address, to_address, amount):
    """
    Prepare and validate a transaction, adding it to the mempool if valid.
    """
    global UTXOS, MEMPOOL
    key_manager = KeyManager("kc/blockchain_data/keys.json")  # Use KeyManager to manage keys

    # Retrieve the private key for the from_address
    private_key = None
    for network in ["testnet", "mainnet"]:
        for identifier, key_data in key_manager.keys[network]["keys"].items():
            if key_data["hashed_public_key"] == from_address:
                private_key = key_data["private_key"]
                break

    if not private_key:
        return "Private key for the given address not found."

    # Create the transaction using the blockchain
    transaction = BLOCKCHAIN.create_transaction(
        from_address=from_address,
        to_address=to_address,
        amount=amount,
        private_key=private_key
    )

    # Validate and add to the mempool
    if transaction and BLOCKCHAIN.verify_transaction(transaction):
        MEMPOOL[transaction.tx_id] = transaction
        return "Transaction successfully added to the mempool."
    else:
        return "Transaction validation failed."

@app.route("/", methods=["GET", "POST"])
def wallet():
    """
    Wallet interface for sending transactions.
    """
    message = ""
    if request.method == "POST":
        from_address = request.form.get("fromAddress")
        to_address = request.form.get("toAddress")
        amount = request.form.get("Amount", type=float)
        
        if from_address and to_address and amount:
            message = send_transaction(from_address, to_address, amount)
        else:
            message = "Invalid input. Please fill all fields."

    return render_template("wallet.html", message=message)

def main(utxos, mempool):
    """
    Main entry point to run the Flask application.
    """
    global UTXOS, MEMPOOL
    UTXOS = utxos
    MEMPOOL = mempool
    initialize_blockchain()
    app.run()

if __name__ == "__main__":
    # Sample UTXO and mempool data for testing
    sample_utxos = {
        "sample_tx_id": {"to_address": "sample_address", "amount": 100}
    }
    sample_mempool = {}

    main(sample_utxos, sample_mempool)
