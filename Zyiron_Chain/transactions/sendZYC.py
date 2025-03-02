import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)


import hashlib
import time
from decimal import Decimal
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
from Zyiron_Chain.blockchain.utils.standardmempool import StandardMempool
from Zyiron_Chain.transactions.fees import FeeModel

from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.transactions.txin import TransactionIn
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.coinbase import CoinbaseTx



import logging


from Zyiron_Chain.blockchain.constants import Constants  # ✅ Import Constants
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # These imports will only be available during type-checking (e.g., for linters, IDEs, or mypy)
    from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
    from Zyiron_Chain.transactions.fees import FundsAllocator

class SendZYC:
    """
    Handles transaction sending, UTXO selection, and fee calculations for ZYC.
    """

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
            raise ValueError(f"[ERROR] Invalid network: {network}. Choose 'mainnet' or 'testnet'.")

        self.key_manager = key_manager
        self.utxo_manager = utxo_manager
        self.mempool = mempool
        self.fee_model = fee_model
        self.network = network
        self.coin_unit = Constants.COIN  # ✅ Use Constants for smallest unit


    def prepare_tx_in(self, required_amount):
        """
        Prepare transaction inputs to fulfill the required amount using UTXOManager.

        :param required_amount: Total amount to send including fees.
        :return: List of TransactionIn objects and the total input amount.
        """
        with self.lock:
            selected_utxos = self.utxo_manager.select_utxos(required_amount)
            inputs = []
            total_input = Decimal("0")

            # ✅ Ensure at least one UTXO is selected
            if not selected_utxos:
                logging.error(f"[ERROR] No available UTXOs to fulfill {required_amount}.")
                raise ValueError("Insufficient UTXOs for the transaction.")

            for utxo_id, utxo_data in selected_utxos.items():
                try:
                    # ✅ Ensure the UTXO has a valid amount
                    utxo_amount = Decimal(utxo_data.get("amount", 0))
                    if utxo_amount <= 0:
                        logging.warning(f"[WARN] Skipping invalid UTXO {utxo_id} with amount {utxo_amount}.")
                        continue

                    # ✅ Generate input signature securely
                    private_key = self.key_manager.get_private_key()
                    signature_data = f"{utxo_id}{private_key}"
                    script_sig = hashlib.sha3_384(signature_data.encode()).hexdigest()

                    # ✅ Add transaction input
                    inputs.append(TransactionIn(tx_out_id=utxo_id, script_sig=script_sig))
                    total_input += utxo_amount

                except Exception as e:
                    logging.error(f"[ERROR] Failed to process UTXO {utxo_id}: {e}")

            # ✅ Ensure total input is sufficient
            if total_input < required_amount:
                logging.error(f"[ERROR] Insufficient funds. Required: {required_amount}, Available: {total_input}.")
                raise ValueError("Insufficient funds for the transaction.")

            logging.info(f"[INFO] Prepared {len(inputs)} inputs with total amount {total_input}.")
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
        with self.lock:
            outputs = []

            # ✅ Validate recipient and amount
            if not recipient or amount <= 0:
                logging.error(f"[ERROR] Invalid recipient ({recipient}) or amount ({amount}).")
                raise ValueError("Recipient address must be valid and amount must be greater than zero.")

            # ✅ Ensure proper Decimal handling to avoid float precision errors
            amount = Decimal(str(amount))
            change_amount = Decimal(str(change_amount))

            # ✅ Create the main recipient output
            outputs.append(TransactionOut(script_pub_key=recipient, amount=amount))

            # ✅ If change exists, create a change output
            if change_amount > 0:
                if not change_address:
                    logging.error(f"[ERROR] Change amount {change_amount} requires a valid change address.")
                    raise ValueError("Change address is required if change amount is greater than zero.")

                outputs.append(TransactionOut(script_pub_key=change_address, amount=change_amount))

            logging.info(f"[INFO] Prepared {len(outputs)} transaction outputs: Total Sent: {amount}, Change: {change_amount}")

            return outputs


    def calculate_fee(self, block_size, payment_type, tx_size):
        """
        Calculate transaction fee using the FeeModel, ensuring it meets the minimum required fee.

        :param block_size: Current block size in MB.
        :param payment_type: Payment type (e.g., "Standard", "Instant", "Smart").
        :param tx_size: Size of the transaction in bytes.
        :return: Final transaction fee.
        """
        with self.lock:
            # ✅ Ensure valid transaction size
            if tx_size <= 0:
                logging.error(f"[ERROR] Invalid transaction size: {tx_size} bytes.")
                raise ValueError("Transaction size must be greater than zero.")

            # ✅ Fetch total mempool size safely
            try:
                mempool_total_size = self.mempool.get_total_size()
            except Exception as e:
                logging.error(f"[ERROR] Failed to get mempool size: {e}")
                mempool_total_size = 0

            # ✅ Ensure valid payment type
            if payment_type not in Constants.TRANSACTION_CONFIRMATIONS:
                logging.warning(f"[WARN] Unrecognized payment type '{payment_type}'. Defaulting to 'STANDARD'.")
                payment_type = "STANDARD"

            # ✅ Calculate the fee using FeeModel
            base_fee = self.fee_model.calculate_fee(
                block_size=block_size,
                payment_type=payment_type,
                amount=mempool_total_size,
                tx_size=tx_size
            )

            # ✅ Ensure the final fee is at least the minimum required fee
            final_fee = max(base_fee, Constants.MIN_TRANSACTION_FEE)

            logging.info(f"[INFO] Calculated fee: {final_fee} (Base: {base_fee}, Min: {Constants.MIN_TRANSACTION_FEE}) for {payment_type} transaction of size {tx_size} bytes.")

            return final_fee


    def broadcast_transaction(self, transaction):
        """
        Add the transaction to the mempool and broadcast it to the network.

        :param transaction: Transaction object.
        """
        with self.lock:
            try:
                # ✅ Attempt to add transaction to mempool
                if self.mempool.add_transaction(transaction):
                    logging.info(f"[INFO] Transaction {transaction.tx_id} added to mempool.")

                    # ✅ Propagate transaction to network nodes
                    if hasattr(self, "network") and hasattr(self.network, "propagate_transaction"):
                        self.network.propagate_transaction(transaction)
                        logging.info(f"[INFO] Transaction {transaction.tx_id} broadcasted to network.")

                    return True
                else:
                    logging.error(f"[ERROR] Failed to add transaction {transaction.tx_id} to mempool.")
                    return False

            except Exception as e:
                logging.error(f"[ERROR] Broadcast failed for transaction {transaction.tx_id}: {e}")
                return False

    def prepare_transaction(self, recipient_script_pub_key, amount, block_size, payment_type="Standard"):
        """
        Prepare a transaction using UTXOs, calculate fees dynamically, and broadcast it.

        :param recipient_script_pub_key: The scriptPubKey for the recipient.
        :param amount: The amount to send to the recipient.
        :param block_size: Current block size in MB.
        :param payment_type: Payment type ("Standard", "Smart", or "Instant").
        :return: The Transaction object.
        """
        with self.lock:
            try:
                amount = Decimal(str(amount))

                # ✅ Estimate transaction size (Placeholder - should be dynamically calculated)
                estimated_tx_size = 250  # Example size in bytes

                # ✅ Calculate the fee using FeeModel
                fee = self.calculate_fee(block_size, payment_type, estimated_tx_size)

                # ✅ Ensure fee is reasonable
                if fee > amount:
                    logging.error(f"[ERROR] Fee ({fee}) exceeds transaction amount ({amount}). Transaction aborted.")
                    raise ValueError("Transaction fee is too high compared to the amount.")

                # ✅ Select UTXOs to cover amount + fee
                required_amount = amount + Decimal(fee)
                inputs, total_input = self.prepare_tx_in(required_amount)

                # ✅ Compute change
                change = total_input - required_amount
                if change < 0:
                    logging.error(f"[ERROR] Insufficient funds. Required: {required_amount}, Available: {total_input}.")
                    raise ValueError("Insufficient funds after UTXO selection.")

                miner_script_pub_key = self.key_manager.get_default_public_key(self.network, role="miner")

                # ✅ Prepare transaction outputs
                outputs = self.prepare_tx_out(recipient_script_pub_key, amount, miner_script_pub_key, change)

                # ✅ Lock the selected UTXOs to prevent double spending
                self.utxo_manager.lock_selected_utxos([tx.tx_out_id for tx in inputs])

                # ✅ Create the transaction
                transaction = Transaction(inputs=inputs, outputs=outputs)

                # ✅ Sign the transaction securely
                self.sign_tx(transaction)

                # ✅ Add the transaction to the mempool and broadcast it
                if self.broadcast_transaction(transaction):
                    logging.info(f"[INFO] Transaction {transaction.tx_id} successfully prepared and broadcasted.")
                    return transaction
                else:
                    logging.error(f"[ERROR] Failed to broadcast transaction {transaction.tx_id}. Unlocking UTXOs.")
                    self.utxo_manager.unlock_selected_utxos([tx.tx_out_id for tx in inputs])
                    return None

            except Exception as e:
                logging.error(f"[ERROR] Failed to prepare transaction: {e}")
                return None


    def sign_tx(self, transaction):
        """
        Sign the transaction inputs using the miner's private key.
        
        :param transaction: Transaction object to sign.
        """
        with self.lock:
            try:
                # ✅ Securely retrieve the miner's private key
                private_key = self.key_manager.get_private_key()
                if not private_key:
                    logging.error("[ERROR] Failed to retrieve private key. Transaction signing aborted.")
                    raise ValueError("Private key retrieval failed.")

                # ✅ Sign each transaction input
                for tx_in in transaction.inputs:
                    if not hasattr(tx_in, "tx_out_id"):
                        logging.error(f"[ERROR] Transaction input missing tx_out_id: {tx_in}")
                        raise ValueError("Invalid transaction input structure.")

                    # ✅ Generate signature securely
                    signature_data = f"{tx_in.tx_out_id}{private_key}"
                    tx_in.script_sig = hashlib.sha3_384(signature_data.encode()).hexdigest()

                logging.info(f"[INFO] Transaction {transaction.tx_id} successfully signed.")

            except Exception as e:
                logging.error(f"[ERROR] Failed to sign transaction {transaction.tx_id}: {e}")
                raise ValueError(f"Transaction signing error: {e}")