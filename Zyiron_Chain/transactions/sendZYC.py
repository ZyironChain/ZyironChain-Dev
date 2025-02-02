import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)


import hashlib
import time
from decimal import Decimal
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction,  TransactionOut, TransactionIn
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
from Zyiron_Chain.blockchain.utils.standardmempool import StandardMempool
from Zyiron_Chain.transactions.fees import FeeModel







class SendZYC:
    COIN = Decimal("0.00000001")  # Smallest unit (like Bitcoin's satoshi)

    def __init__(self, key_manager, utxo_manager, mempool, fee_model, network="mainnet"):
        """
        Initialize SendZYC with KeyManager, UTXOManager, Mempool, FeeModel, and network.
        :param key_manager: KeyManager instance.
        :param utxo_manager: UTXOManager instance.
        :param mempool: Mempool instance.
        :param fee_model: FeeModel instance.
        :param network: "mainnet" (ZYC) or "testnet" (ZYT).
        """
        if not key_manager or not utxo_manager or not mempool or not fee_model:
            raise ValueError("KeyManager, UTXOManager, Mempool, and FeeModel are required.")

        if network not in ["mainnet", "testnet"]:
            raise ValueError(f"Invalid network: {network}. Choose 'mainnet' or 'testnet'.")

        self.key_manager = key_manager
        self.utxo_manager = utxo_manager
        self.mempool = mempool
        self.fee_model = fee_model
        self.network = network

    def prepare_tx_in(self, required_amount):
        """
        Prepare transaction inputs to fulfill the required amount using UTXOManager.
        :param required_amount: Total amount to send including fees.
        :return: List of TransactionIn objects and the total input amount.
        """
        selected_utxos = self.utxo_manager.select_utxos(required_amount)
        inputs = []
        total_input = Decimal("0")

        for utxo_id, utxo_data in selected_utxos.items():
            # Simulate signing the input
            private_key = self.key_manager.get_private_key()
            signature_data = f"{utxo_id}{private_key}"
            script_sig = hashlib.sha3_384(signature_data.encode()).hexdigest()

            inputs.append(TransactionIn(tx_out_id=utxo_id, script_sig=script_sig))
            total_input += Decimal(utxo_data["amount"])

        if total_input < required_amount:
            raise ValueError("Insufficient funds for the transaction.")

        return inputs, total_input
    



    def prepare_tx_out(self, recipient, amount, change_address, change_amount):
        """
        Prepare transaction outputs for the recipient and change.
        :param recipient: Recipient's public key hash.
        :param amount: Amount to send to the recipient.
        :param change_address: Public key hash for the change.
        :param change_amount: Amount to send back as change.
        :return: List of TransactionOut objects.
        """
        outputs = [
            TransactionOut(script_pub_key=recipient, amount=float(amount))
        ]
        if change_amount > 0:
            outputs.append(
                TransactionOut(
                    script_pub_key=change_address,
                    amount=float(change_amount),
                )
            )
        return outputs

    def calculate_fee(self, block_size, payment_type, tx_size):
        """
        Calculate transaction fee using the FeeModel.
        :param block_size: Current block size in MB.
        :param payment_type: Payment type (e.g., "Standard").
        :param tx_size: Size of the transaction in bytes.
        :return: Calculated fee.
        """
        mempool_total_size = self.mempool.get_total_size()
        fee = self.fee_model.calculate_fee(
            block_size=block_size,
            payment_type=payment_type,
            amount=mempool_total_size,
            tx_size=tx_size
        )
        return fee

    def broadcast_transaction(self, transaction):
        """
        Add the transaction to the mempool and broadcast it to the network.
        :param transaction: Transaction object.
        """
        if self.mempool.add_transaction(transaction):
            print(f"[INFO] Transaction {transaction.tx_id} broadcasted successfully.")
        else:
            print(f"[ERROR] Failed to broadcast transaction {transaction.tx_id}.")

    def prepare_transaction(self, recipient_script_pub_key, amount, block_size, payment_type="Standard"):
        """
        Prepare a transaction using UTXOs, calculate fees dynamically, and broadcast it.
        :param recipient_script_pub_key: The scriptPubKey for the recipient.
        :param amount: The amount to send to the recipient.
        :param block_size: Current block size in MB.
        :param payment_type: Payment type ("Standard", "Smart", or "Instant").
        :return: The Transaction object.
        """
        amount = Decimal(amount)

        # Estimate transaction size (placeholder for real calculation)
        estimated_tx_size = 250  # Example size in bytes

        # Calculate the fee
        fee = self.calculate_fee(block_size, payment_type, estimated_tx_size)

        # Select UTXOs
        required_amount = amount + Decimal(fee)
        inputs, total_input = self.prepare_tx_in(required_amount)

        # Create outputs
        change = total_input - required_amount
        miner_script_pub_key = self.key_manager.get_default_public_key(self.network, role="miner")
        outputs = self.prepare_tx_out(recipient_script_pub_key, amount, miner_script_pub_key, change)

        # Lock the selected UTXOs
        self.utxo_manager.lock_selected_utxos([tx.tx_out_id for tx in inputs])

        # Create the transaction
        transaction = Transaction(tx_inputs=inputs, tx_outputs=outputs)

        # Sign the transaction
        self.sign_tx(transaction)

        # Add the transaction to the mempool and broadcast it
        self.broadcast_transaction(transaction)

        return transaction

    def sign_tx(self, transaction):
        """
        Sign the transaction inputs using the miner's private key.
        :param transaction: Transaction object to sign.
        """
        private_key = self.get_private_key()
        for tx_in in transaction.tx_inputs:
            # Simulate signing using the private key (mock implementation)
            signature_data = f"{tx_in.tx_out_id}{private_key}"
            tx_in.script_sig = hashlib.sha3_384(signature_data.encode()).hexdigest()



