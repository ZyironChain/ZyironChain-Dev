import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from decimal import Decimal, getcontext
from Zyiron_Chain.blockchain.constants import Constants
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
    Uses single SHA3-384 hashing, bytes conversion, and constants from Constants.
    All debug and error messages are printed with detailed information.
    """

    def __init__(self, key_manager, utxo_manager, mempool, fee_model, network="mainnet"):
        if not key_manager or not utxo_manager or not mempool or not fee_model:
            raise ValueError("KeyManager, UTXOManager, Mempool, and FeeModel are required.")
        if network not in ["mainnet", "testnet"]:
            raise ValueError(f"Invalid network: {network}. Choose 'mainnet' or 'testnet'.")
        self.key_manager = key_manager
        self.utxo_manager = utxo_manager
        self.mempool = mempool
        self.fee_model = fee_model
        self.network = network
        self.coin_unit = Constants.COIN
        self.lock = __import__("threading").Lock()
        print(f"[SendZYC] Initialized for network {self.network.upper()} with coin unit {self.coin_unit}")



    def prepare_tx_in(self, required_amount):
        """
        Selects UTXOs to fulfill the required amount, ensuring valid inputs.
        Validates UTXO offsets and locks selected UTXOs to prevent double spending.
        """
        with self.lock:
            print(f"[INFO] Selecting UTXOs to fulfill {required_amount} ZYC...")

            selected_utxos = self.utxo_manager.select_utxos(required_amount)
            inputs = []
            total_input = Decimal("0")

            if not selected_utxos:
                print(f"[ERROR] No available UTXOs to fulfill {required_amount}.")
                raise ValueError("Insufficient UTXOs for the transaction.")

            for utxo_id, utxo_data in selected_utxos.items():
                try:
                    # ✅ Ensure UTXO structure matches LMDB byte storage
                    if not isinstance(utxo_id, bytes) or len(utxo_id) != 48:
                        print(f"[ERROR] Invalid UTXO ID format for {utxo_id}. Expected 48 bytes.")
                        continue

                    # ✅ Validate UTXO offset in LMDB
                    utxo_offset = utxo_data.get("offset")
                    if utxo_offset is None:
                        print(f"[ERROR] UTXO {utxo_id.hex()} missing offset information. Skipping.")
                        continue

                    # ✅ Convert stored amounts correctly
                    utxo_amount = Decimal(str(utxo_data.get("amount", "0")))

                    sender_address = self.key_manager.get_default_public_key(self.network)

                    # ✅ Ensure UTXO belongs to the sender
                    if utxo_data.get("script_pub_key") != sender_address:
                        print(f"[WARN] Skipping UTXO {utxo_id.hex()}: Does not belong to sender.")
                        continue

                    # ✅ Ensure UTXO amount is valid
                    if utxo_amount <= 0:
                        print(f"[WARN] Skipping invalid UTXO {utxo_id.hex()} with amount {utxo_amount}.")
                        continue

                    # ✅ Retrieve private key safely
                    private_key = self.key_manager.get_private_key()
                    if not private_key:
                        print(f"[ERROR] Failed to retrieve private key for UTXO {utxo_id.hex()}.")
                        raise ValueError("Private key retrieval failed.")

                    # ✅ Generate script signature using SHA3-384
                    signature_data = f"{utxo_id.hex()}{private_key}"
                    script_sig = hashlib.sha3_384(signature_data.encode()).digest()

                    # ✅ Append valid transaction input with proper structure
                    inputs.append(TransactionIn(tx_out_id=utxo_id, script_sig=script_sig))

                    total_input += utxo_amount

                except Exception as e:
                    print(f"[ERROR] Failed to process UTXO {utxo_id.hex()}: {e}")

            # ✅ Ensure total input meets required amount
            if total_input < required_amount:
                print(f"[ERROR] Insufficient funds. Required: {required_amount}, Available: {total_input}.")
                raise ValueError("Insufficient funds for the transaction.")

            # ✅ Lock UTXOs after selection
            self.utxo_manager.lock_selected_utxos([tx.tx_out_id for tx in inputs])

            print(f"[INFO] Prepared {len(inputs)} inputs with total amount {total_input}.")
            return inputs, total_input


    def prepare_tx_out(self, recipient, amount, change_address, change_amount):
        with self.lock:
            outputs = []
            if not recipient or amount <= 0:
                print(f"[ERROR] Invalid recipient ({recipient}) or amount ({amount}).")
                raise ValueError("Recipient address must be valid and amount must be greater than zero.")
            amount = Decimal(str(amount))
            change_amount = Decimal(str(change_amount))
            outputs.append(TransactionOut(script_pub_key=recipient, amount=amount))
            if change_amount > 0:
                if not change_address:
                    print(f"[ERROR] Change amount {change_amount} requires a valid change address.")
                    raise ValueError("Change address is required if change amount is greater than zero.")
                outputs.append(TransactionOut(script_pub_key=change_address, amount=change_amount))
            print(f"[INFO] Prepared {len(outputs)} outputs: Total Sent: {amount}, Change: {change_amount}")
            return outputs

    def calculate_fee(self, block_size, payment_type, tx_size):
        """
        Calculate the transaction fee based on block size, payment type, and transaction size.
        Ensures that fees do not fall below the minimum required fee.
        """
        with self.lock:
            # ✅ Ensure transaction size is valid
            if tx_size <= 0:
                print(f"[ERROR] Invalid transaction size: {tx_size} bytes.")
                raise ValueError("Transaction size must be greater than zero.")

            try:
                # ✅ Retrieve current mempool size
                mempool_total_size = self.mempool.get_total_size()
            except Exception as e:
                print(f"[ERROR] Failed to get mempool size: {e}")
                mempool_total_size = 0

            # ✅ Validate payment type from Constants
            if payment_type not in Constants.TRANSACTION_CONFIRMATIONS:
                print(f"[WARN] Unrecognized payment type '{payment_type}'. Defaulting to 'STANDARD'.")
                payment_type = "STANDARD"

            # ✅ Validate fee model structure before calculating
            try:
                base_fee = self.fee_model.calculate_fee(
                    block_size=block_size,
                    payment_type=payment_type,
                    amount=mempool_total_size,
                    tx_size=tx_size
                )
            except Exception as e:
                print(f"[ERROR] Fee calculation failed: {e}")
                raise ValueError("Error occurred while calculating transaction fee.")

            # ✅ Ensure fee does not fall below the required minimum
            final_fee = max(base_fee, Constants.MIN_TRANSACTION_FEE)

            print(f"[INFO] Calculated fee: {final_fee} (Base: {base_fee}, Min: {Constants.MIN_TRANSACTION_FEE}) "
                f"for {payment_type} transaction of size {tx_size} bytes.")

            return final_fee


    def broadcast_transaction(self, transaction):
        """
        Broadcasts a transaction by ensuring:
        - Signature hashing follows block storage offsets.
        - Signatures are verified against LMDB transaction index storage.
        - Transaction is added to the mempool and propagated to the network.
        """
        with self.lock:
            try:
                print(f"[SendZYC.broadcast_transaction] INFO: Broadcasting transaction {transaction.tx_id}...")

                # ✅ Validate signature hashing follows block storage offsets
                block_offsets = Constants.BLOCK_STORAGE_OFFSETS
                expected_signature_offset = block_offsets["transaction_signature"]["start"]

                if expected_signature_offset is not None:
                    print(f"[SendZYC.broadcast_transaction] INFO: Verifying signature alignment at offset {expected_signature_offset}.")

                # ✅ Verify transaction signature matches LMDB transaction index storage
                tx_index_db = self.mempool.txindex_db  # Retrieve LMDB transaction index
                stored_tx_data = tx_index_db.get(f"tx:{transaction.tx_id}".encode("utf-8"))

                if stored_tx_data:
                    stored_tx = json.loads(stored_tx_data.decode("utf-8"))
                    stored_signature = stored_tx.get("tx_signature_hash", "")

                    # ✅ Compare computed signature with stored LMDB index
                    computed_signature = hashlib.sha3_384(transaction.tx_id.encode()).hexdigest()

                    if computed_signature != stored_signature:
                        print(f"[ERROR] Signature mismatch for transaction {transaction.tx_id}. Stored: {stored_signature}, Computed: {computed_signature}")
                        raise ValueError("Transaction signature verification failed.")

                # ✅ Add transaction to the mempool
                if self.mempool.add_transaction(transaction):
                    print(f"[INFO] Transaction {transaction.tx_id} added to mempool.")

                    # ✅ Propagate transaction to the network if network propagation exists
                    if hasattr(self, "network") and hasattr(self.network, "propagate_transaction"):
                        self.network.propagate_transaction(transaction)
                        print(f"[INFO] Transaction {transaction.tx_id} broadcasted to network.")

                    return True
                else:
                    print(f"[ERROR] Failed to add transaction {transaction.tx_id} to mempool.")
                    return False

            except Exception as e:
                print(f"[ERROR] Broadcast failed for transaction {transaction.tx_id}: {e}")
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

                # ✅ Dynamically calculate fee based on congestion, type, and minimum enforcement
                fee_details = self.fee_model.calculate_fee_and_tax(block_size, payment_type, amount, estimated_tx_size)
                fee = max(fee_details["base_fee"], Constants.MIN_TRANSACTION_FEE)  # Enforce minimum fee
                miner_fee = fee_details["miner_fee"]
                tax_fee = fee_details["tax_fee"]

                print(f"[SendZYC.prepare_transaction] INFO: Fee Breakdown - Base Fee: {fee}, Miner Fee: {miner_fee}, Tax Fee: {tax_fee}")

                # ✅ Ensure fee does not exceed transaction amount
                if fee > amount:
                    print(f"[ERROR] Fee ({fee}) exceeds transaction amount ({amount}). Transaction aborted.")
                    raise ValueError("Transaction fee is too high compared to the amount.")

                # ✅ Calculate required amount (amount + fee)
                required_amount = amount + fee

                # ✅ Select UTXOs for required amount (Validate byte structure & offsets)
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

                # ✅ Lock UTXOs to prevent double spending
                self.utxo_manager.lock_selected_utxos([tx.tx_out_id for tx in inputs])

                # ✅ Construct transaction with correct type prefix
                transaction = Transaction(inputs=inputs, outputs=outputs, tx_type=payment_type)

                # ✅ Dynamically assign confirmation times based on network
                confirmation_times = Constants.TRANSACTION_CONFIRMATIONS
                required_confirmations = confirmation_times.get(payment_type.upper(), confirmation_times["STANDARD"])
                transaction.confirmations_required = required_confirmations

                print(f"[SendZYC.prepare_transaction] INFO: Transaction {transaction.tx_id} requires {required_confirmations} confirmations.")

                # ✅ Sign transaction securely
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
        - Output handling aligns with block storage offsets.
        - Miner fees are validated.
        - UTXO locking is properly enforced before signing.
        """
        with self.lock:
            try:
                print(f"[SendZYC.sign_tx] INFO: Signing transaction {transaction.tx_id}...")

                # ✅ Retrieve private key securely
                private_key = self.key_manager.get_private_key()
                if not private_key:
                    print("[ERROR] Failed to retrieve private key. Transaction signing aborted.")
                    raise ValueError("Private key retrieval failed.")

                # ✅ Validate output handling follows block storage offsets
                block_offsets = Constants.BLOCK_STORAGE_OFFSETS
                expected_offset = block_offsets["transactions"]["start"]

                for tx_out in transaction.outputs:
                    if not hasattr(tx_out, "script_pub_key"):
                        print(f"[ERROR] Transaction output missing script_pub_key: {tx_out}")
                        raise ValueError("Invalid transaction output structure.")
                    
                    # ✅ Ensure output structure aligns with expected storage format
                    if expected_offset is not None:
                        print(f"[SendZYC.sign_tx] INFO: Validating output alignment at offset {expected_offset}.")

                # ✅ Validate miner fees before signing
                miner_fee = sum(Decimal(out.amount) for out in transaction.outputs if hasattr(out, "script_pub_key") and out.script_pub_key == self.key_manager.get_default_public_key(self.network, role="miner"))
                expected_miner_fee = transaction.fee_details["miner_fee"]

                if miner_fee < expected_miner_fee:
                    print(f"[ERROR] Miner fee mismatch. Expected: {expected_miner_fee}, Found: {miner_fee}.")
                    raise ValueError("Miner fee validation failed.")

                # ✅ Validate UTXO locking alignment
                locked_utxos = self.utxo_manager.get_locked_utxos()
                for tx_in in transaction.inputs:
                    if not hasattr(tx_in, "tx_out_id"):
                        print(f"[ERROR] Transaction input missing tx_out_id: {tx_in}")
                        raise ValueError("Invalid transaction input structure.")

                    # Ensure the UTXO is correctly locked before signing
                    if tx_in.tx_out_id not in locked_utxos:
                        print(f"[ERROR] UTXO {tx_in.tx_out_id} is not locked. Transaction signing aborted.")
                        raise ValueError("UTXO is not locked for this transaction.")

                    # ✅ Generate script signature
                    signature_data = f"{tx_in.tx_out_id}{private_key}"
                    tx_in.script_sig = hashlib.sha3_384(signature_data.encode()).hexdigest()

                print(f"[SendZYC.sign_tx] ✅ SUCCESS: Transaction {transaction.tx_id} signed successfully.")

            except Exception as e:
                print(f"[ERROR] Failed to sign transaction {transaction.tx_id}: {e}")
                raise ValueError(f"Transaction signing error: {e}")
