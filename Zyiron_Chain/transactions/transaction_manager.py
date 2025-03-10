import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.mempool.standardmempool import StandardMempool
from Zyiron_Chain.mempool.smartmempool import SmartMempool
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from decimal import Decimal
from threading import Lock
import hashlib
import json
import time

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.hashing import Hashing
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Zyiron_Chain.transactions.coinbase import CoinbaseTx

from Zyiron_Chain.utils.deserializer import Deserializer
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.storage.utxostorage import UTXOStorage
from Zyiron_Chain.storage.blockmetadata import BlockMetadata


class TransactionManager:
    """
    Manages transaction creation, validation, and mempool operations
    under the new file structure. All data is processed as bytes,
    and single SHA3-384 hashing is used.
    """

    def __init__(
        self,
        block_storage,     # For retrieving block data if needed
        block_metadata,    # For retrieving block headers / ordering
        tx_storage,        # For checking transaction existence, storing TX data
        utxo_manager: UTXOManager,  # UTXOManager instance for UTXO lookups
        key_manager        # KeyManager for retrieving keys
    ):
        """
        :param block_storage: Module handling full block storage (WholeBlockData).
        :param block_metadata: Module handling block metadata (BlockMetadata).
        :param tx_storage: Module for transaction indexing (TxStorage).
        :param utxo_manager: UTXOManager instance for UTXO lookups.
        :param key_manager: KeyManager for retrieving keys.
        """
        self.block_storage = block_storage
        self.block_metadata = block_metadata
        self.tx_storage = tx_storage
        self.utxo_manager = utxo_manager
        self.key_manager = key_manager

        self.network = Constants.NETWORK
        self.version = Constants.VERSION

        # Initialize UTXOStorage
        utxo_db = LMDBManager(Constants.get_db_path("utxo"))
        utxo_history_db = LMDBManager(Constants.get_db_path("utxo_history"))
        self.utxo_storage = UTXOStorage(
            utxo_db=utxo_db,
            utxo_history_db=utxo_history_db,
            utxo_manager=utxo_manager
        )

        # Initialize the two mempools
        self.standard_mempool = StandardMempool(
            utxo_storage=self.utxo_storage,  # Pass UTXOStorage to StandardMempool
            max_size_mb=int(Constants.MEMPOOL_MAX_SIZE_MB * Constants.MEMPOOL_STANDARD_ALLOCATION)
        )
        self.smart_mempool = SmartMempool(
            max_size_mb=int(Constants.MEMPOOL_MAX_SIZE_MB * Constants.MEMPOOL_SMART_ALLOCATION)
        )

        self.transaction_mempool_map = Constants.TRANSACTION_MEMPOOL_MAP
        self._mempool = self.standard_mempool

        self.mempool_lock = Lock()

        print(f"[TransactionManager.__init__] Initialized on {self.network.upper()} | Version {self.version} | "
              f"Standard Mempool: {Constants.MEMPOOL_STANDARD_ALLOCATION * 100}% | "
              f"Smart Mempool: {Constants.MEMPOOL_SMART_ALLOCATION * 100}%")


    def get_transaction(self, tx_id):
        """Retrieve transaction data and deserialize if necessary."""
        data = self.tx_storage.get_transaction(tx_id)
        return Deserializer().deserialize(data) if data else None
    
    def create_transaction(self, sender, recipient_address=None, amount=None, fee=None, transaction_type="STANDARD", **kwargs):
        """
        Create a new transaction.

        Accepts either 'recipient_address' or (if missing) the legacy keyword 'recipient_script_pub_key'.

        :param sender: Sender's address (must be explicitly provided).
        :param recipient_address: Recipient's address. If None, checks kwargs for 'recipient_script_pub_key'.
        :param amount: Amount to send.
        :param fee: Transaction fee.
        :param transaction_type: Type of the transaction (default: "STANDARD").
        :param kwargs: Additional keyword arguments.
        :return: The created transaction as a dictionary.
        """
        try:
            # **✅ FIX: Ensure sender is explicitly provided**
            if not sender:
                print("[TransactionManager.create_transaction ERROR] Missing required 'sender' argument.")
                raise ValueError("Sender address must be provided.")

            # **Validate sender address using the wallet manager**
            if not self.wallet_manager.validate_address(sender):
                print(f"[TransactionManager.create_transaction ERROR] Invalid sender address: {sender}")
                raise ValueError("Invalid sender address.")

            # **Support for legacy 'recipient_script_pub_key' argument**
            if recipient_address is None and "recipient_script_pub_key" in kwargs:
                recipient_address = kwargs["recipient_script_pub_key"]
                print("[TransactionManager.create_transaction INFO] 'recipient_script_pub_key' found in kwargs; using it as recipient_address.")

            if recipient_address is None:
                print("[TransactionManager.create_transaction ERROR] Missing recipient address.")
                raise ValueError("Recipient address must be provided.")

            print(f"[TransactionManager.create_transaction INFO] Creating transaction from {sender} to {recipient_address}...")

            # **Generate a unique transaction ID using single SHA3-384 hashing**
            tx_data = f"{sender}{recipient_address}{amount}{fee}{transaction_type}{time.time()}"
            tx_hash = Hashing.hash(tx_data.encode()).hex()

            # **Transaction dictionary**
            transaction = {
                "sender": sender,
                "recipient_address": recipient_address,
                "amount": amount,
                "fee": fee,
                "timestamp": int(time.time()),
                "transaction_type": transaction_type,
                "tx_id": tx_hash
            }

            print(f"[TransactionManager.create_transaction SUCCESS] Transaction created with ID {transaction['tx_id']}.")
            return transaction

        except Exception as e:
            print(f"[TransactionManager.create_transaction ERROR] Failed to create transaction: {e}")
            return None



    @property
    def mempool(self):
        """Return the active mempool."""
        return self._mempool

    def set_mempool(self, mempool_type="standard"):
        """
        Switch between Standard and Smart mempools.
        :param mempool_type: "standard" or "smart"
        """
        if mempool_type == "standard":
            self._mempool = self.standard_mempool
            print("[TransactionManager.set_mempool] Switched to StandardMempool.")
        elif mempool_type == "smart":
            self._mempool = self.smart_mempool
            print("[TransactionManager.set_mempool] Switched to SmartMempool.")
        else:
            raise ValueError(f"[TransactionManager.set_mempool] Invalid mempool type: {mempool_type}")


    def store_transaction_in_mempool(self, transaction: Transaction) -> bool:
        """
        Validates the transaction's type & network prefix, then adds it
        to the appropriate mempool. Uses single SHA3-384 hashing for the tx_id check.
        """
        try:
            # Re-hash the tx_id to confirm it starts with the correct prefix
            hashed_tx_id = hashlib.sha3_384(transaction.tx_id.encode()).hexdigest()
            if not hashed_tx_id.startswith(Constants.ADDRESS_PREFIX):
                print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Transaction {transaction.tx_id} has invalid address prefix for {self.network}. Expected: {Constants.ADDRESS_PREFIX}")
                return False

            tx_type = PaymentTypeManager().get_transaction_type(hashed_tx_id)
            if not tx_type:
                print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Unable to determine transaction type for {transaction.tx_id}")
                return False

            mempool_type = self.transaction_mempool_map.get(tx_type.name, {}).get("mempool", "StandardMempool")
            chain_height = self._get_chain_height()

            if mempool_type == "SmartMempool":
                success = self.smart_mempool.add_transaction(transaction, chain_height)
            else:
                success = self.standard_mempool.add_transaction(transaction)

            if success:
                print(f"[TransactionManager.store_transaction_in_mempool] INFO: Transaction {hashed_tx_id} stored in {mempool_type}.")
                # Optionally, store the transaction in tx_storage here:
                # self.tx_storage.store_transaction(transaction.to_dict())
                return True
            else:
                print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Failed to store transaction {hashed_tx_id} in {mempool_type}.")
                return False

        except Exception as e:
            print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Unexpected error storing transaction {transaction.tx_id}: {e}")
            return False

    def select_transactions_for_block(self, max_block_size_mb: int = 10):
        """
        Chooses transactions for the next block, focusing on highest fee-per-byte.
        Ensures transactions fit within block size. Returns a list of chosen transactions.
        """
        try:
            max_size_bytes = max_block_size_mb * 1024 * 1024
            chain_height = self._get_chain_height()

            # Allocation for smart, standard, instant
            smart_tx_allocation = int(max_size_bytes * Constants.BLOCK_ALLOCATION_SMART)
            standard_tx_allocation = int(max_size_bytes * Constants.BLOCK_ALLOCATION_STANDARD)
            instant_tx_allocation = int(max_size_bytes * Constants.INSTANT_PAYMENT_ALLOCATION)

            smart_txs = self.smart_mempool.get_pending_transactions(Constants.BLOCK_ALLOCATION_SMART * max_block_size_mb, chain_height)
            standard_txs = self.standard_mempool.get_pending_transactions(Constants.BLOCK_ALLOCATION_STANDARD * max_block_size_mb)
            instant_txs = self.standard_mempool.get_pending_transactions(Constants.INSTANT_PAYMENT_ALLOCATION * max_block_size_mb, transaction_type="Instant")

            all_txs = smart_txs + standard_txs + instant_txs
            sorted_txs = sorted(
                all_txs,
                key=lambda tx: tx.fee / self._calculate_transaction_size(tx),
                reverse=True
            )

            selected_txs = []
            current_smart_size = current_standard_size = current_instant_size = 0

            for tx in sorted_txs:
                tx_size = self._calculate_transaction_size(tx)

                if tx in smart_txs and current_smart_size + tx_size > smart_tx_allocation:
                    continue
                if tx in standard_txs and current_standard_size + tx_size > standard_tx_allocation:
                    continue
                if tx in instant_txs and current_instant_size + tx_size > instant_tx_allocation:
                    continue

                # Check overall limit and validate transaction
                total_used = current_smart_size + current_standard_size + current_instant_size
                if (total_used + tx_size <= max_size_bytes) and self.validate_transaction(tx):
                    selected_txs.append(tx)

                    # Update category size
                    if tx in smart_txs:
                        current_smart_size += tx_size
                    elif tx in instant_txs:
                        current_instant_size += tx_size
                    else:
                        current_standard_size += tx_size

            total_size = current_smart_size + current_standard_size + current_instant_size
            print(
                "[TransactionManager.select_transactions_for_block] INFO: "
                f"Selected {len(selected_txs)} transactions | Smart: {current_smart_size} bytes | "
                f"Standard: {current_standard_size} bytes | Instant: {current_instant_size} bytes | Total: {total_size} bytes"
            )
            return selected_txs

        except Exception as e:
            print(f"[TransactionManager.select_transactions_for_block] ERROR: {str(e)}")



            return []
        


    def _get_chain_height(self) -> int:
        """
        Retrieve the current blockchain height using block metadata.

        Returns:
            int: The height of the blockchain (number of blocks). Returns 0 if no blocks are found.
        """
        try:
            # Call the get_all_block_headers method from BlockMetadata
            headers = self.block_metadata.get_all_block_headers()
            
            if headers:
                # Calculate the maximum block index (height) from the headers
                height = max(header["index"] for header in headers)
                print(f"[TransactionManager._get_chain_height] Current chain height: {height}")
                return height
            else:
                # No headers found, return 0
                print("[TransactionManager._get_chain_height] No block headers found; returning 0.")
                return 0
        except Exception as e:
            # Handle any exceptions and log the error
            print(f"[TransactionManager._get_chain_height] ERROR: Unable to retrieve chain height: {e}")
            return 0
    def _calculate_transaction_size(self, tx: Transaction) -> int:
        """
        Calculate transaction size in bytes using single SHA3-384 hashing.
        """
        try:
            # Ensure tx_id is a str
            if isinstance(tx.tx_id, bytes):
                tx.tx_id = tx.tx_id.decode("utf-8")

            # We create a single hash from tx_id just for a consistent measure
            single_hashed_tx_id = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()

            # Base fields
            base_size = len(single_hashed_tx_id) + len(str(tx.timestamp)) + len(str(tx.nonce))

            # Inputs and outputs
            input_size = sum(len(json.dumps(inp.to_dict(), sort_keys=True)) for inp in tx.inputs)
            output_size = sum(len(json.dumps(out.to_dict(), sort_keys=True)) for out in tx.outputs)

            total_size = base_size + input_size + output_size
            return total_size

        except Exception as e:
            print(f"[TransactionManager._calculate_transaction_size] ERROR: Failed to calculate size for {tx.tx_id}: {str(e)}")
            return -1

    def validate_transaction(self, tx: Transaction) -> bool:
        """
        Validate a transaction:
        - Ensures correct structure and required fields.
        - Verifies digital signature.
        - Checks for double-spending.
        - Ensures fees meet minimum requirements.
        - Validates mempool placement based on transaction type.
        """
        try:
            from Zyiron_Chain.transactions.coinbase import CoinbaseTx

            print(f"[TransactionManager.validate_transaction] INFO: Validating transaction {tx.tx_id}...")

            # ✅ **Handle Coinbase Transactions (Skip Deeper Checks)**
            if isinstance(tx, CoinbaseTx):
                print(f"[TransactionManager.validate_transaction] INFO: Coinbase transaction {tx.tx_id} skipping deeper validation.")
                return True

            # ✅ **Ensure tx_id is a Valid SHA3-384 Hash**
            if isinstance(tx.tx_id, bytes):
                tx.tx_id = tx.tx_id.decode("utf-8")

            single_hashed_tx_id = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()
            if single_hashed_tx_id != tx.tx_id:
                print(f"[TransactionManager.validate_transaction] ERROR: Transaction ID hash mismatch.")
                return False

            # ✅ **Check Required Fields**
            required_fields = ["tx_id", "inputs", "outputs", "timestamp", "tx_signature"]
            for field in required_fields:
                if not hasattr(tx, field):
                    print(f"[TransactionManager.validate_transaction] ERROR: Missing required field: {field}")
                    return False

            # ✅ **Verify Digital Signature**
            if not tx.verify_signature():
                print(f"[TransactionManager.validate_transaction] ERROR: Signature verification failed for {tx.tx_id}")
                return False

            # ✅ **Check UTXO Inputs for Validity**
            input_sum = Decimal("0")
            for tx_in in tx.inputs:
                utxo = self.utxo_manager.get_utxo(tx_in.tx_out_id)
                if not utxo:
                    print(f"[TransactionManager.validate_transaction] ERROR: Missing UTXO {tx_in.tx_out_id}")
                    return False
                if getattr(utxo, "locked", False):
                    print(f"[TransactionManager.validate_transaction] ERROR: UTXO {tx_in.tx_out_id} is locked. Cannot spend.")
                    return False
                input_sum += Decimal(str(utxo.amount))

            # ✅ **Ensure Outputs Are Properly Structured**
            output_sum = Decimal("0")
            for output in tx.outputs:
                if not hasattr(output, "amount") or not hasattr(output, "script_pub_key"):
                    print(f"[TransactionManager.validate_transaction] ERROR: Invalid transaction output structure.")
                    return False
                output_sum += Decimal(str(output.amount))

            # ✅ **Ensure Input Sum >= Output Sum**
            if input_sum < output_sum:
                print(
                    f"[TransactionManager.validate_transaction] ERROR: Transaction {tx.tx_id} "
                    f"inputs {input_sum} < outputs {output_sum}"
                )
                return False

            # ✅ **Validate Fees Against `FeeModel`**
            calculated_fee = input_sum - output_sum
            min_fee_required = Decimal(Constants.MIN_TRANSACTION_FEE)
            if calculated_fee < min_fee_required:
                print(
                    f"[TransactionManager.validate_transaction] ERROR: Insufficient fee for {tx.tx_id}. "
                    f"Minimum required: {min_fee_required}, Given: {calculated_fee}"
                )
                return False

            # ✅ **Check for Replay Attacks (Duplicate Transactions)**
            if self.tx_storage.transaction_exists(tx.tx_id):
                print(f"[TransactionManager.validate_transaction] ERROR: Replay attack detected for {tx.tx_id}")
                return False

            # ✅ **Ensure Transaction is in Correct Mempool Based on Type**
            tx_type = PaymentTypeManager().get_transaction_type(tx.tx_id)
            expected_mempool = Constants.TRANSACTION_MEMPOOL_MAP.get(tx_type.name, {}).get("mempool", "StandardMempool")

            if expected_mempool == "SmartMempool" and tx.tx_id not in self.smart_mempool.transactions:
                print(f"[TransactionManager.validate_transaction] ERROR: {tx.tx_id} should be in SmartMempool but is not.")
                return False
            if expected_mempool == "StandardMempool" and tx.tx_id not in self.standard_mempool.transactions:
                print(f"[TransactionManager.validate_transaction] ERROR: {tx.tx_id} should be in StandardMempool but is not.")
                return False

            print(f"[TransactionManager.validate_transaction] ✅ SUCCESS: Transaction {tx.tx_id} passed all validation checks.")
            return True

        except Exception as e:
            print(f"[TransactionManager.validate_transaction] ERROR: Transaction validation failed for {tx.tx_id}: {str(e)}")
            return False

    def get_pending_transactions(self, block_size_mb: int = None):
        """
        Returns pending transactions from both mempools. If block_size_mb is provided,
        filter them by size. Uses fee-per-byte ordering if filtering is done.
        """
        total_block_size = (block_size_mb or Constants.MEMPOOL_MAX_SIZE_MB) * 1024 * 1024
        smart_tx_allocation = int(total_block_size * Constants.BLOCK_ALLOCATION_SMART)
        standard_tx_allocation = int(total_block_size * Constants.BLOCK_ALLOCATION_STANDARD)

        chain_height = self._get_chain_height()
        smart_txs = self.smart_mempool.get_smart_transactions(smart_tx_allocation, chain_height)
        standard_txs = self.standard_mempool.get_pending_transactions(standard_tx_allocation)

        all_txs = smart_txs + standard_txs

        # If a block size is specified, filter by size
        if block_size_mb is not None:
            max_size_bytes = block_size_mb * 1024 * 1024
            selected_txs = []
            current_size = 0

            # Sort by fee-per-byte descending
            sorted_txs = sorted(all_txs, key=lambda tx: tx.fee / self._calculate_transaction_size(tx), reverse=True)

            for tx in sorted_txs:
                tx_size = self._calculate_transaction_size(tx)
                if current_size + tx_size > max_size_bytes:
                    break
                selected_txs.append(tx)
                current_size += tx_size

            print(
                "[TransactionManager.get_pending_transactions] INFO: "
                f"Selected {len(selected_txs)} transactions | Total Size: {current_size} bytes"
            )
            return selected_txs

        # Otherwise return all
        return all_txs

    def sign_tx(self, transaction: Transaction):
        """
        Sign each input in the transaction using the miner's private key from key_manager.
        """
        with self.mempool_lock:
            try:
                private_key = self.key_manager.get_private_key()
                if not private_key:
                    print("[TransactionManager.sign_tx] ERROR: Failed to retrieve private key. Transaction signing aborted.")
                    raise ValueError("Private key retrieval failed.")

                for tx_in in transaction.inputs:
                    if not hasattr(tx_in, "tx_out_id"):
                        print(f"[TransactionManager.sign_tx] ERROR: Transaction input missing tx_out_id: {tx_in}")
                        raise ValueError("Invalid transaction input structure.")

                    # Single-hash the signature data
                    signature_data = f"{tx_in.tx_out_id}{private_key}"
                    tx_in.script_sig = hashlib.sha3_384(signature_data.encode()).hexdigest()

                print(f"[TransactionManager.sign_tx] INFO: Transaction {transaction.tx_id} successfully signed.")

            except Exception as e:
                print(f"[TransactionManager.sign_tx] ERROR: Failed to sign transaction {transaction.tx_id}: {e}")
                raise ValueError(f"Transaction signing error: {e}")

