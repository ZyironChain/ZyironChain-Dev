import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from decimal import Decimal, getcontext
from Zyiron_Chain.blockchain.constants import Constants, store_transaction_signature
from Zyiron_Chain.accounts.key_manager import KeyManager
from Zyiron_Chain.mempool.standardmempool import StandardMempool
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.transactions.txin import TransactionIn
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.coinbase import CoinbaseTx
from Zyiron_Chain.transactions.transactiontype import TransactionType
from Zyiron_Chain.utils.deserializer import Deserializer
import json
import hashlib
# Set high precision for financial calculations
getcontext().prec = 18

class SendZYC:
    """
    Handles transaction sending, UTXO selection, and fee calculations for ZYC.
    Uses single SHA3-384 hashing, integrates LMDB-based storage, and follows the UTXOManager structure.
    """

    def __init__(self, key_manager, utxo_manager, mempool, fee_model, network="mainnet"):
        """
        Initializes the SendZYC class with the required blockchain components.

        :param key_manager: KeyManager instance for retrieving keys.
        :param utxo_manager: UTXOManager instance for managing unspent transaction outputs.
        :param mempool: Mempool instance for storing pending transactions.
        :param fee_model: FeeModel instance for calculating fees.
        :param network: Blockchain network (mainnet, testnet, regnet).
        """
        if not key_manager or not utxo_manager or not mempool or not fee_model:
            raise ValueError("KeyManager, UTXOManager, Mempool, and FeeModel are required.")

        if network not in Constants.NETWORK_DATABASES:
            raise ValueError(f"Invalid network: {network}. Choose from {list(Constants.NETWORK_DATABASES.keys())}.")

        self.key_manager = key_manager
        self.utxo_manager = utxo_manager  # ✅ Uses UTXOManager for correct handling
        self.mempool = mempool
        self.fee_model = fee_model
        self.network = network
        self.coin_unit = Constants.COIN
        self.lock = __import__("threading").Lock()

        print(f"[SendZYC] Initialized for network {self.network.upper()} with coin unit {self.coin_unit}")



    def prepare_tx_in(self, required_amount):
        """
        Selects UTXOs to fulfill the required amount, ensuring valid inputs.
        Validates UTXO selection and locks selected UTXOs to prevent double spending.
        """
        with self.lock:
            print(f"[SendZYC.prepare_tx_in] INFO: Selecting UTXOs to fulfill {required_amount} ZYC...")

            selected_utxos = self.utxo_manager.select_utxos(required_amount)
            inputs = []
            total_input = Decimal("0")

            if not selected_utxos:
                print(f"[SendZYC.prepare_tx_in] ERROR: No available UTXOs to fulfill {required_amount}.")
                raise ValueError("Insufficient UTXOs for the transaction.")

            for utxo_id, utxo_data in selected_utxos.items():
                try:
                    # ✅ Ensure UTXO structure matches LMDB storage
                    if not isinstance(utxo_id, str):
                        print(f"[SendZYC.prepare_tx_in] ERROR: Invalid UTXO ID format for {utxo_id}. Expected a string.")
                        continue

                    # ✅ Convert stored amounts correctly
                    utxo_amount = Decimal(str(utxo_data.get("amount", "0")))

                    # ✅ Retrieve sender address securely
                    sender_address = self.key_manager.get_default_public_key(self.network)

                    # ✅ Ensure UTXO belongs to the sender
                    if utxo_data.get("script_pub_key") != sender_address:
                        print(f"[SendZYC.prepare_tx_in] WARN: Skipping UTXO {utxo_id}: Does not belong to sender.")
                        continue

                    # ✅ Ensure UTXO amount is valid
                    if utxo_amount <= 0:
                        print(f"[SendZYC.prepare_tx_in] WARN: Skipping invalid UTXO {utxo_id} with amount {utxo_amount}.")
                        continue

                    # ✅ Retrieve private key securely
                    private_key = self.key_manager.get_private_key()
                    if not private_key:
                        print(f"[SendZYC.prepare_tx_in] ERROR: Failed to retrieve private key for UTXO {utxo_id}.")
                        raise ValueError("Private key retrieval failed.")

                    # ✅ Generate script signature using SHA3-384
                    signature_data = f"{utxo_id}{private_key}"
                    script_sig = hashlib.sha3_384(signature_data.encode()).hexdigest()

                    # ✅ Append valid transaction input
                    inputs.append(TransactionIn(tx_out_id=utxo_id, script_sig=script_sig))

                    total_input += utxo_amount

                except Exception as e:
                    print(f"[SendZYC.prepare_tx_in] ERROR: Failed to process UTXO {utxo_id}: {e}")

            # ✅ Ensure total input meets required amount
            if total_input < required_amount:
                print(f"[SendZYC.prepare_tx_in] ERROR: Insufficient funds. Required: {required_amount}, Available: {total_input}.")
                raise ValueError("Insufficient funds for the transaction.")

            # ✅ Lock UTXOs after selection
            self.utxo_manager.lock_selected_utxos([tx.tx_out_id for tx in inputs])

            print(f"[SendZYC.prepare_tx_in] INFO: Prepared {len(inputs)} inputs with total amount {total_input}.")
            return inputs, total_input


    def prepare_tx_out(self, recipient, amount, change_address, change_amount):
        """
        Prepares transaction outputs, ensuring:
        - Valid recipient address.
        - Correct amount handling.
        - Properly formatted change output.
        """
        with self.lock:
            print(f"[SendZYC.prepare_tx_out] INFO: Preparing outputs for recipient {recipient} with amount {amount} ZYC...")

            # ✅ Validate recipient and amount
            if not recipient or amount <= 0:
                print(f"[SendZYC.prepare_tx_out] ERROR: Invalid recipient ({recipient}) or amount ({amount}).")
                raise ValueError("Recipient address must be valid and amount must be greater than zero.")

            amount = Decimal(str(amount))
            change_amount = Decimal(str(change_amount))

            # ✅ Prepare main recipient output
            outputs = [TransactionOut(script_pub_key=recipient, amount=amount)]

            # ✅ Handle change output if applicable
            if change_amount > 0:
                if not change_address:
                    print(f"[SendZYC.prepare_tx_out] ERROR: Change amount {change_amount} requires a valid change address.")
                    raise ValueError("Change address is required if change amount is greater than zero.")
                outputs.append(TransactionOut(script_pub_key=change_address, amount=change_amount))

            print(f"[SendZYC.prepare_tx_out] INFO: Prepared {len(outputs)} outputs. Total Sent: {amount}, Change: {change_amount}.")
            return outputs


    def calculate_fee(self, block_size, payment_type, tx_size):
        """
        Calculate the transaction fee based on block size, payment type, and transaction size.
        Ensures that fees do not fall below the minimum required fee.
        """
        with self.lock:
            print(f"[SendZYC.calculate_fee] INFO: Calculating fee for {payment_type} transaction of size {tx_size} bytes...")

            # ✅ Validate transaction size
            if tx_size <= 0:
                print(f"[SendZYC.calculate_fee] ERROR: Invalid transaction size: {tx_size} bytes.")
                raise ValueError("Transaction size must be greater than zero.")

            try:
                # ✅ Retrieve current mempool size from LMDB-backed storage
                mempool_total_size = self.mempool.get_total_size()
                print(f"[SendZYC.calculate_fee] INFO: Current mempool size: {mempool_total_size} bytes.")
            except Exception as e:
                print(f"[SendZYC.calculate_fee] ERROR: Failed to get mempool size: {e}")
                mempool_total_size = 0

            # ✅ Validate payment type from Constants
            if payment_type not in Constants.TRANSACTION_CONFIRMATIONS:
                print(f"[SendZYC.calculate_fee] WARN: Unrecognized payment type '{payment_type}'. Defaulting to 'STANDARD'.")
                payment_type = "STANDARD"

            # ✅ Validate and calculate fee using FeeModel
            try:
                base_fee = self.fee_model.calculate_fee(
                    block_size=block_size,
                    payment_type=payment_type,
                    amount=mempool_total_size,
                    tx_size=tx_size
                )
            except Exception as e:
                print(f"[SendZYC.calculate_fee] ERROR: Fee calculation failed: {e}")
                raise ValueError("Error occurred while calculating transaction fee.")

            # ✅ Ensure fee does not fall below the required minimum
            final_fee = max(base_fee, Constants.MIN_TRANSACTION_FEE)

            print(f"[SendZYC.calculate_fee] INFO: Calculated fee: {final_fee} (Base: {base_fee}, Min: {Constants.MIN_TRANSACTION_FEE}) "
                  f"for {payment_type} transaction of size {tx_size} bytes.")

            return final_fee


    def broadcast_transaction(self, transaction):
        """
        Broadcasts a transaction by ensuring:
        - Signatures are verified against LMDB transaction index storage.
        - Transaction is added to the mempool and propagated to the network.
        """
        with self.lock:
            try:
                print(f"[SendZYC.broadcast_transaction] INFO: Broadcasting transaction {transaction.tx_id}...")

                # ✅ Verify transaction signature using LMDB-backed transaction index storage
                tx_index_db = self.mempool.txindex_db  
                stored_tx_data = tx_index_db.get(f"tx:{transaction.tx_id}".encode("utf-8"))

                if stored_tx_data:
                    stored_tx = json.loads(stored_tx_data.decode("utf-8"))
                    stored_signature = stored_tx.get("tx_signature_hash", "")

                    # ✅ Compute transaction signature using SHA3-384
                    computed_signature = hashlib.sha3_384(transaction.tx_id.encode()).hexdigest()

                    if computed_signature != stored_signature:
                        print(f"[SendZYC.broadcast_transaction] ERROR: Signature mismatch for transaction {transaction.tx_id}. "
                              f"Stored: {stored_signature}, Computed: {computed_signature}")
                        raise ValueError("Transaction signature verification failed.")

                # ✅ Add transaction to the LMDB-backed mempool
                if self.mempool.add_transaction(transaction):
                    print(f"[SendZYC.broadcast_transaction] INFO: Transaction {transaction.tx_id} added to mempool.")

                    # ✅ Propagate transaction to the network
                    if hasattr(self, "network") and hasattr(self.network, "propagate_transaction"):
                        self.network.propagate_transaction(transaction)
                        print(f"[SendZYC.broadcast_transaction] INFO: Transaction {transaction.tx_id} broadcasted to network.")

                    return True
                else:
                    print(f"[SendZYC.broadcast_transaction] ERROR: Failed to add transaction {transaction.tx_id} to mempool.")
                    return False

            except Exception as e:
                print(f"[SendZYC.broadcast_transaction] ERROR: Broadcast failed for transaction {transaction.tx_id}: {e}")
                return False


    def prepare_transaction(self, recipient_script_pub_key, amount, block_size, payment_type="STANDARD"):
        """
        Prepares a transaction by selecting UTXOs, calculating fees, and constructing inputs and outputs.
        Ensures transactions adhere to network-specific confirmation times.
        """
        with self.lock:
            try:
                print(f"[SendZYC.prepare_transaction] INFO: Preparing transaction to {recipient_script_pub_key} for {amount} ZYC...")

                # ✅ Convert amount to Decimal safely
                amount = Decimal(str(amount))

                # ✅ Estimate transaction size dynamically
                estimated_tx_size = 550  # Placeholder, should be computed dynamically

                # ✅ Calculate transaction fee dynamically
                fee_details = self.fee_model.calculate_fee_and_tax(block_size, payment_type, amount, estimated_tx_size)
                fee = max(fee_details["base_fee"], Constants.MIN_TRANSACTION_FEE)  # Ensure minimum fee
                miner_fee = fee_details["miner_fee"]
                tax_fee = fee_details["tax_fee"]

                print(f"[SendZYC.prepare_transaction] INFO: Fee Breakdown - Base Fee: {fee}, Miner Fee: {miner_fee}, Tax Fee: {tax_fee}")

                # ✅ Ensure fee does not exceed transaction amount
                if fee > amount:
                    print(f"[ERROR] Fee ({fee}) exceeds transaction amount ({amount}). Transaction aborted.")
                    raise ValueError("Transaction fee is too high compared to the amount.")

                # ✅ Calculate total required amount
                required_amount = amount + fee

                # ✅ Select UTXOs for required amount
                inputs, total_input = self.prepare_tx_in(required_amount)

                # ✅ Calculate change
                change = total_input - required_amount
                if change < 0:
                    print(f"[ERROR] Insufficient funds. Required: {required_amount}, Available: {total_input}.")
                    raise ValueError("Insufficient funds after UTXO selection.")

                print(f"[SendZYC.prepare_transaction] INFO: Selected UTXOs cover {total_input} ZYC, Change: {change} ZYC")

                # ✅ Retrieve miner's script pub key for fee allocation
                miner_script_pub_key = self.key_manager.get_default_public_key(self.network, role="miner")

                # ✅ Prepare transaction outputs
                outputs = self.prepare_tx_out(recipient_script_pub_key, amount, miner_script_pub_key, change)

                # ✅ Lock selected UTXOs
                self.utxo_manager.lock_selected_utxos([tx.tx_out_id for tx in inputs])

                # ✅ Construct transaction with correct type prefix
                transaction = Transaction(inputs=inputs, outputs=outputs, tx_type=payment_type)

                # ✅ Assign required confirmations based on transaction type
                confirmation_times = Constants.TRANSACTION_CONFIRMATIONS
                transaction.confirmations_required = confirmation_times.get(payment_type.upper(), confirmation_times["STANDARD"])

                print(f"[SendZYC.prepare_transaction] INFO: Transaction {transaction.tx_id} requires {transaction.confirmations_required} confirmations.")

                # ✅ Sign transaction
                self.sign_tx(transaction)

                # ✅ Broadcast transaction
                if self.broadcast_transaction(transaction):
                    print(f"[INFO] Transaction {transaction.tx_id} successfully prepared and broadcasted.")
                    return transaction
                else:
                    print(f"[ERROR] Failed to broadcast transaction {transaction.tx_id}. Unlocking UTXOs.")
                    self.utxo_manager.unlock_selected_utxos([tx.tx_out_id for tx in inputs])
                    return None

            except Exception as e:
                print(f"[ERROR] Failed to prepare transaction: {e}")
                return None



    def sign_tx(self, transaction):
        """
        Signs the transaction securely by ensuring:
        - The Falcon-512 signature is generated.
        - The signature is hashed and stored in `full_block_chain.lmdb`.
        - The full Falcon-512 signature is offloaded to `txindex.lmdb`.
        - Transaction integrity is preserved.
        """
        with self.lock:
            try:
                print(f"[SendZYC.sign_tx] INFO: Signing transaction {transaction.tx_id}...")

                # ✅ Retrieve private key securely
                private_key = self.key_manager.get_private_key()
                if not private_key:
                    print("[ERROR] Failed to retrieve private key. Transaction signing aborted.")
                    raise ValueError("Private key retrieval failed.")

                # ✅ Generate Falcon-512 Signature
                original_signature = self.key_manager.sign_falcon(transaction.tx_id, private_key)
                if not original_signature:
                    print("[ERROR] Failed to generate Falcon-512 signature. Transaction signing aborted.")
                    raise ValueError("Falcon-512 signature generation failed.")

                # ✅ Store the Falcon-512 Signature in `txindex.lmdb`
                txindex_path = Constants.get_db_path("txindex")  # Retrieve correct `txindex.lmdb` path
                hashed_signature = store_transaction_signature(
                    tx_id=transaction.tx_id.encode(),
                    falcon_signature=original_signature,
                    txindex_path=txindex_path
                )

                # ✅ Store Hashed Signature in `full_block_chain.lmdb`
                block_data = {
                    "tx_id": transaction.tx_id,
                    "tx_signature_hash": hashed_signature.hex()
                }
                blockchain_db_path = Constants.get_db_path("full_block_chain")
                self.mempool.blockchain_db.put(f"block_tx:{transaction.tx_id}", block_data)

                print(f"[SendZYC.sign_tx] INFO: Stored hashed Falcon-512 signature for {transaction.tx_id} in full_block_chain.lmdb.")

                print(f"[SendZYC.sign_tx] ✅ SUCCESS: Transaction {transaction.tx_id} signed and indexed securely.")

            except Exception as e:
                print(f"[ERROR] Failed to sign transaction {transaction.tx_id}: {e}")
                raise ValueError(f"Transaction signing error: {e}")
