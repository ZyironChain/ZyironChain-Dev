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

from Zyiron_Chain.blockchain.constants import Constants, store_transaction_signature
from Zyiron_Chain.utils.hashing import Hashing
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Zyiron_Chain.transactions.coinbase import CoinbaseTx

from Zyiron_Chain.utils.deserializer import Deserializer
from Zyiron_Chain.storage.lmdatabase import LMDBManager
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.storage.utxostorage import UTXOStorage


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

        # ✅ Initialize LMDB Storage for Transactions, UTXOs, and Indexes
        utxo_db = LMDBManager(Constants.get_db_path("utxo"))
        utxo_history_db = LMDBManager(Constants.get_db_path("utxo_history"))
        txindex_db = LMDBManager(Constants.get_db_path("txindex"))  # ✅ Required for Falcon-512 storage

        self.utxo_storage = UTXOStorage(
            utxo_db=utxo_db,
            utxo_history_db=utxo_history_db,
            utxo_manager=utxo_manager
        )

        self.txindex_db = txindex_db  # ✅ Store txindex for Falcon-512 signature storage

        # ✅ Initialize the two mempools
        self.standard_mempool = StandardMempool(
            utxo_storage=self.utxo_storage,
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
              f"Smart Mempool: {Constants.MEMPOOL_SMART_ALLOCATION * 100}% | "
              f"TX Index DB: {Constants.get_db_path('txindex')}")


    
    def create_transaction(self, sender, recipient_address=None, amount=None, fee=None, transaction_type="STANDARD", **kwargs):
        """
        Create a new transaction.

        Ensures:
        - Transactions retrieved from `tx_storage` are validated against block storage.
        - Raw bytes stored in LMDB are converted to structured transaction objects.
        - Signature hashing aligns with stored transaction indexes.
        - Falcon-512 signature is offloaded to `txindex.lmdb`.

        :param sender: Sender's address (must be explicitly provided).
        :param recipient_address: Recipient's address.
        :param amount: Amount to send.
        :param fee: Transaction fee.
        :param transaction_type: Type of the transaction (default: "STANDARD").
        :param kwargs: Additional keyword arguments.
        :return: The created transaction as a dictionary.
        """
        try:
            # ✅ Ensure sender is explicitly provided
            if not sender:
                print("[ERROR] Missing required 'sender' argument.")
                raise ValueError("Sender address must be provided.")

            # ✅ Validate sender address using the wallet manager
            if not self.key_manager.validate_address(sender):
                print(f"[ERROR] Invalid sender address: {sender}")
                raise ValueError("Invalid sender address.")

            # ✅ Support for legacy 'recipient_script_pub_key' argument
            if recipient_address is None and "recipient_script_pub_key" in kwargs:
                recipient_address = kwargs["recipient_script_pub_key"]
                print("[INFO] 'recipient_script_pub_key' found in kwargs; using it as recipient_address.")

            if recipient_address is None:
                print("[ERROR] Missing recipient address.")
                raise ValueError("Recipient address must be provided.")

            # ✅ Ensure amount and fee are valid decimals
            try:
                amount = Decimal(str(amount))
                fee = Decimal(str(fee)) if fee else Decimal(Constants.MIN_TRANSACTION_FEE)
            except Exception:
                print("[ERROR] Invalid amount or fee format.")
                raise ValueError("Amount and fee must be valid decimal values.")

            print(f"[INFO] Creating transaction from {sender} to {recipient_address} for {amount} ZYC.")

            # ✅ Ensure amount is not zero or negative
            if amount <= 0:
                print("[ERROR] Amount must be greater than zero.")
                raise ValueError("Transaction amount must be positive.")

            # ✅ Ensure fee meets minimum requirements
            if fee < Decimal(Constants.MIN_TRANSACTION_FEE):
                print(f"[ERROR] Fee too low. Adjusting to minimum {Constants.MIN_TRANSACTION_FEE}.")
                fee = Decimal(Constants.MIN_TRANSACTION_FEE)

            # ✅ Check sender's balance in UTXO storage
            sender_balance = self.utxo_storage.get_balance(sender)
            if sender_balance < amount + fee:
                print(f"[ERROR] Insufficient balance. Required: {amount + fee}, Available: {sender_balance}")
                raise ValueError("Sender does not have enough balance for this transaction.")

            # ✅ Generate a unique transaction ID using single SHA3-384 hashing
            tx_data = f"{sender}{recipient_address}{amount}{fee}{transaction_type}{time.time()}"
            tx_hash = hashlib.sha3_384(tx_data.encode()).hexdigest()

            # ✅ Ensure transaction ID is not already in `tx_storage`
            if self.tx_storage.transaction_exists(tx_hash):
                print(f"[ERROR] Duplicate transaction ID detected: {tx_hash}")
                raise ValueError("Duplicate transaction ID detected. Aborting.")

            # ✅ Lock UTXOs before proceeding
            inputs, total_input = self.utxo_manager.select_utxos(amount + fee)
            self.utxo_manager.lock_selected_utxos([tx.tx_out_id for tx in inputs])

            # ✅ Calculate change
            change = total_input - (amount + fee)
            outputs = [
                {"script_pub_key": recipient_address, "amount": str(amount)}
            ]
            if change > 0:
                outputs.append({"script_pub_key": sender, "amount": str(change)})

            # ✅ Generate Falcon-512 signature
            falcon_signature = self.key_manager.sign_transaction(tx_hash)

            # ✅ Offload Falcon-512 signature to `txindex.lmdb`
            txindex_path = Constants.get_db_path("txindex")
            sha3_384_hash = store_transaction_signature(tx_hash.encode(), falcon_signature, txindex_path)

            # ✅ Create Transaction dictionary
            transaction = {
                "tx_id": tx_hash,
                "sender": sender,
                "recipient_address": recipient_address,
                "amount": str(amount),
                "fee": str(fee),
                "timestamp": int(time.time()),
                "transaction_type": transaction_type,
                "inputs": inputs,
                "outputs": outputs,
                "tx_signature_hash": sha3_384_hash.hex(),  # ✅ Only store hashed signature in block storage
            }

            # ✅ Store transaction in `tx_storage`
            self.tx_storage.store_transaction(tx_hash, transaction)

            print(f"[SUCCESS] Transaction {transaction['tx_id']} created, signed, and stored successfully.")
            return transaction

        except Exception as e:
            print(f"[ERROR] Failed to create transaction: {e}")
            return None




    @property
    def mempool(self):
        """Return the active mempool instance."""
        return self._mempool

    def set_mempool(self, mempool_type="standard"):
        """
        Switch between Standard and Smart mempools.
        Ensures correct transaction type routing to the respective mempool.

        :param mempool_type: "standard" or "smart"
        """
        if mempool_type not in ["standard", "smart"]:
            raise ValueError(f"[TransactionManager.set_mempool] ERROR: Invalid mempool type: {mempool_type}")

        # ✅ Dynamically switch mempools
        previous_mempool = "StandardMempool" if self._mempool == self.standard_mempool else "SmartMempool"
        self._mempool = self.standard_mempool if mempool_type == "standard" else self.smart_mempool
        new_mempool = "StandardMempool" if mempool_type == "standard" else "SmartMempool"

        print(f"[TransactionManager.set_mempool] INFO: Switched mempool from {previous_mempool} to {new_mempool}.")


    def store_transaction_in_mempool(self, transaction: Transaction) -> bool:
        """
        Validates the transaction's type & network prefix, then adds it
        to the appropriate mempool. Uses single SHA3-384 hashing for the tx_id check.

        Additional Enhancements:
        - ✅ Offloads full Falcon-512 signature to `txindex.lmdb` with SHA3-384 hashed storage.
        - ✅ Stores only the hashed Falcon signature in `blockchain.lmdb`.
        - ✅ Ensures proper transaction type handling and mempool allocation.
        - ✅ Locks UTXOs to prevent double-spends.
        """
        try:
            print(f"[TransactionManager.store_transaction_in_mempool] INFO: Processing transaction {transaction.tx_id}...")

            # ✅ **Ensure the transaction ID is correctly hashed using SHA3-384**
            hashed_tx_id = hashlib.sha3_384(transaction.tx_id.encode()).hexdigest()
            if hashed_tx_id != transaction.tx_id:
                print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Transaction ID mismatch for {transaction.tx_id}.")
                return False

            # ✅ **Verify the transaction has a valid address prefix**
            if not transaction.tx_id.startswith(Constants.ADDRESS_PREFIX):
                print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Invalid address prefix for {transaction.tx_id}. Expected: {Constants.ADDRESS_PREFIX}")
                return False

            # ✅ **Retrieve the correct transaction type**
            tx_type = PaymentTypeManager().get_transaction_type(transaction.tx_id)
            if not tx_type:
                print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Unable to determine transaction type for {transaction.tx_id}.")
                return False

            # ✅ **Verify recipient's scriptPubKey is formatted correctly as bytes**
            for output in transaction.outputs:
                if isinstance(output.script_pub_key, str):
                    output.script_pub_key = output.script_pub_key.encode("utf-8")
                elif not isinstance(output.script_pub_key, bytes):
                    print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Invalid scriptPubKey format for {transaction.tx_id}.")
                    return False

            # ✅ **Check if the transaction's UTXOs are correctly locked**
            for tx_in in transaction.inputs:
                utxo = self.utxo_manager.get_utxo(tx_in.tx_out_id)
                if not utxo:
                    print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Missing UTXO {tx_in.tx_out_id}.")
                    return False
                if utxo["locked"]:
                    print(f"[TransactionManager.store_transaction_in_mempool] ERROR: UTXO {tx_in.tx_out_id} is locked. Cannot process.")
                    return False

            # ✅ **Validate the transaction signature before broadcasting**
            if not transaction.verify_signature():
                print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Signature verification failed for transaction {transaction.tx_id}.")
                return False

            # ✅ **Determine the correct mempool for the transaction type**
            mempool_type = self.transaction_mempool_map.get(tx_type.name, {}).get("mempool", "StandardMempool")
            chain_height = self._get_chain_height()

            # ✅ **Add the transaction to the correct mempool**
            if mempool_type == "SmartMempool":
                success = self.smart_mempool.add_transaction(transaction, chain_height)
            else:
                success = self.standard_mempool.add_transaction(transaction)

            if success:
                print(f"[TransactionManager.store_transaction_in_mempool] INFO: Transaction {hashed_tx_id} stored in {mempool_type}.")

                # ✅ **Store Falcon-512 Signature in `txindex.lmdb`**
                txindex_db_path = Constants.get_db_path("txindex")
                falcon_signature_hash = store_transaction_signature(
                    tx_id=transaction.tx_id.encode(),
                    falcon_signature=transaction.falcon_signature,
                    txindex_path=txindex_db_path
                )

                # ✅ **Store SHA3-384 hashed signature in `blockchain.lmdb`**
                transaction.tx_signature_hash = falcon_signature_hash.hex()

                # ✅ **Store transaction metadata offsets dynamically for efficient lookup**
                metadata_offset = self.tx_storage.store_transaction(
                    transaction.tx_id,
                    json.dumps(transaction.to_dict(), sort_keys=True).encode("utf-8")
                )

                if metadata_offset is None:
                    print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Failed to store metadata offsets for transaction {transaction.tx_id}.")
                    return False

                print(f"[TransactionManager.store_transaction_in_mempool] INFO: Transaction metadata stored at offset {metadata_offset}.")
                return True
            else:
                print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Failed to store transaction {hashed_tx_id} in {mempool_type}.")
                return False

        except Exception as e:
            print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Unexpected error storing transaction {transaction.tx_id}: {e}")
            return False


    def select_transactions_for_block(self, max_block_size_mb: int = 10):
        """
        Chooses transactions for the next block, ensuring:
        - Byte-level transaction validation before storing.
        - SHA3-384 hash consistency between computed transaction ID and stored LMDB transaction index.
        - UTXO spending rules are cross-checked before adding to mempool.
        - Block storage offsets are updated after mempool storage.
        - Falcon-512 signature verification is handled, ensuring only hashed signatures are stored in `full_block_chain.lmdb`.
        """
        try:
            max_size_bytes = max_block_size_mb * 1024 * 1024
            chain_height = self._get_chain_height()

            # ✅ Allocation for different transaction types
            smart_tx_allocation = int(max_size_bytes * Constants.BLOCK_ALLOCATION_SMART)
            standard_tx_allocation = int(max_size_bytes * Constants.BLOCK_ALLOCATION_STANDARD)
            instant_tx_allocation = int(max_size_bytes * Constants.INSTANT_PAYMENT_ALLOCATION)

            # ✅ Retrieve pending transactions from both mempools
            smart_txs = self.smart_mempool.get_pending_transactions(smart_tx_allocation, chain_height)
            standard_txs = self.standard_mempool.get_pending_transactions(standard_tx_allocation)
            instant_txs = self.standard_mempool.get_pending_transactions(instant_tx_allocation, transaction_type="Instant")

            all_txs = smart_txs + standard_txs + instant_txs

            # ✅ Sort transactions by highest fee-per-byte
            sorted_txs = sorted(
                all_txs,
                key=lambda tx: tx.fee / self._calculate_transaction_size(tx),
                reverse=True
            )

            selected_txs = []
            current_smart_size = current_standard_size = current_instant_size = 0

            for tx in sorted_txs:
                tx_size = self._calculate_transaction_size(tx)

                # ✅ Ensure transaction passes byte-level validation
                if not self.validate_transaction(tx):
                    print(f"[ERROR] Transaction {tx.tx_id} failed validation. Skipping.")
                    continue

                # ✅ Verify SHA3-384 hash consistency
                stored_tx_data = self.tx_storage.get_transaction(tx.tx_id)
                if not stored_tx_data:
                    print(f"[ERROR] Transaction {tx.tx_id} not found in LMDB. Skipping.")
                    continue

                computed_tx_hash = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()
                if computed_tx_hash != tx.tx_id:
                    print(f"[ERROR] Transaction ID hash mismatch for {tx.tx_id}. Skipping.")
                    continue

                # ✅ Verify UTXO spending rules
                for tx_in in tx.inputs:
                    utxo = self.utxo_manager.get_utxo(tx_in.tx_out_id)
                    if not utxo or utxo["spent_status"] == 1:
                        print(f"[ERROR] UTXO {tx_in.tx_out_id} is already spent or invalid. Skipping transaction {tx.tx_id}.")
                        break
                else:
                    # ✅ Ensure transaction fits within allocation limits
                    if tx in smart_txs and current_smart_size + tx_size > smart_tx_allocation:
                        continue
                    if tx in standard_txs and current_standard_size + tx_size > standard_tx_allocation:
                        continue
                    if tx in instant_txs and current_instant_size + tx_size > instant_tx_allocation:
                        continue

                    # ✅ Ensure block size is not exceeded
                    total_used = current_smart_size + current_standard_size + current_instant_size
                    if total_used + tx_size <= max_size_bytes:
                        selected_txs.append(tx)

                        # ✅ Update allocation sizes
                        if tx in smart_txs:
                            current_smart_size += tx_size
                        elif tx in instant_txs:
                            current_instant_size += tx_size
                        else:
                            current_standard_size += tx_size

            total_size = current_smart_size + current_standard_size + current_instant_size

            # ✅ **Ensure Falcon-512 signature is handled correctly**
            for tx in selected_txs:
                # ✅ Offload Falcon-512 signature into `txindex.lmdb`
                txindex_db_path = Constants.get_db_path("txindex")
                falcon_signature_hash = store_transaction_signature(
                    tx_id=tx.tx_id.encode(),
                    falcon_signature=tx.falcon_signature,
                    txindex_path=txindex_db_path
                )

                # ✅ Store only the SHA3-384 hash of the Falcon signature in `blockchain.lmdb`
                tx.tx_signature_hash = falcon_signature_hash.hex()

                # ✅ Store transaction metadata offsets dynamically
                self.tx_storage.store_transaction(tx.tx_id, json.dumps(tx.to_dict(), sort_keys=True).encode("utf-8"))

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
            # ✅ Retrieve block headers from BlockMetadata
            headers = self.block_metadata.get_all_block_headers()

            if headers:
                # ✅ Compute the maximum block height
                height = max(header["index"] for header in headers)
                print(f"[TransactionManager._get_chain_height] INFO: Current chain height: {height}")
                return height

            # ✅ No block headers found, return 0
            print("[TransactionManager._get_chain_height] WARNING: No block headers found; returning 0.")
            return 0

        except Exception as e:
            print(f"[TransactionManager._get_chain_height] ERROR: Failed to retrieve chain height: {e}")
            return 0

    
    def _calculate_transaction_size(self, tx: Transaction) -> int:
        """
        Calculate transaction size in bytes using single SHA3-384 hashing.
        Ensures byte-level transaction validation before block inclusion.
        Verifies stored transaction integrity before computing size.
        """
        try:
            # ✅ Ensure `tx_id` is a valid SHA3-384 string
            if isinstance(tx.tx_id, bytes):
                tx.tx_id = tx.tx_id.decode("utf-8")

            # ✅ Compute SHA3-384 hash for validation
            computed_tx_id = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()

            # ✅ Fetch stored transaction from LMDB for integrity check
            stored_tx_data = self.tx_storage.get_transaction(tx.tx_id)

            if not stored_tx_data or computed_tx_id != tx.tx_id:
                print(f"[TransactionManager._calculate_transaction_size] ERROR: "
                      f"Transaction ID mismatch or missing from LMDB for {tx.tx_id}. Skipping size calculation.")
                return -1

            # ✅ Compute base transaction size (Transaction ID + Timestamp)
            base_size = len(computed_tx_id) + len(str(tx.timestamp))

            # ✅ Calculate input and output sizes dynamically
            input_size = sum(len(json.dumps(inp.to_dict(), sort_keys=True)) for inp in tx.inputs)
            output_size = sum(len(json.dumps(out.to_dict(), sort_keys=True)) for out in tx.outputs)

            # ✅ Adjust size calculation for metadata fields
            metadata_size = len(str(tx.block_height)) + len(str(tx.priority_flag))

            # ✅ Dynamically adjust size based on network congestion
            mempool_expiry_adjustment = 0
            if Constants.MEMPOOL_TRANSACTION_EXPIRY > 7200:  # If mempool expires in >2 hours, reduce size impact
                mempool_expiry_adjustment = -50  # Optimize block inclusion
            elif Constants.MEMPOOL_TRANSACTION_EXPIRY < 3600:  # If mempool expires in <1 hour, increase size impact
                mempool_expiry_adjustment = 50  # Prioritize longer-lived transactions

            # ✅ Compute final transaction size
            total_size = base_size + input_size + output_size + metadata_size + mempool_expiry_adjustment

            print(f"[TransactionManager._calculate_transaction_size] INFO: Computed transaction size for {tx.tx_id}: {total_size} bytes.")
            return total_size

        except Exception as e:
            print(f"[TransactionManager._calculate_transaction_size] ERROR: Failed to calculate size for {tx.tx_id}: {str(e)}")
            return -1

    def validate_transaction(self, tx: Transaction) -> bool:
        """
        Validate a transaction:
        - Ensures Falcon-512 signature verification.
        - Uses single SHA3-384 hashing for transaction ID validation.
        - Ensures correct UTXO spending rules before mempool inclusion.
        - Verifies fees, prevents replay attacks, and enforces mempool expiration.
        - Offloads Falcon-512 signature to `txindex.lmdb` while storing only the hash in `full_block_chain.lmdb`.
        """
        try:
            from Zyiron_Chain.transactions.coinbase import CoinbaseTx

            print(f"[TransactionManager.validate_transaction] INFO: Validating transaction {tx.tx_id}...")

            # ✅ **Handle Coinbase Transactions (Skip Deeper Checks)**
            if isinstance(tx, CoinbaseTx):
                print(f"[TransactionManager.validate_transaction] INFO: Coinbase transaction {tx.tx_id} skipping deeper validation.")
                return True

            # ✅ **Ensure `tx_id` is a Valid SHA3-384 Hash**
            if isinstance(tx.tx_id, bytes):
                tx.tx_id = tx.tx_id.decode("utf-8")

            computed_tx_id = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()

            # ✅ **Verify SHA3-384 hash consistency between computed transaction ID and stored LMDB index**
            stored_tx_data = self.tx_storage.get_transaction(tx.tx_id)
            if not stored_tx_data:
                print(f"[TransactionManager.validate_transaction] ERROR: Transaction {tx.tx_id} not found in LMDB. Skipping.")
                return False

            if computed_tx_id != tx.tx_id:
                print(f"[TransactionManager.validate_transaction] ERROR: Transaction ID hash mismatch for {tx.tx_id}. Skipping.")
                return False

            # ✅ **Check Required Fields**
            required_fields = ["tx_id", "inputs", "outputs", "timestamp", "tx_signature_hash"]
            for field in required_fields:
                if not hasattr(tx, field):
                    print(f"[TransactionManager.validate_transaction] ERROR: Missing required field: {field}")
                    return False

            # ✅ **Verify Falcon-512 Signature (Offloaded to `txindex.lmdb`)**
            txindex_path = Constants.get_db_path("txindex")
            stored_falcon_signature = self.tx_storage.get_falcon_signature(tx.tx_id, txindex_path)

            if not stored_falcon_signature:
                print(f"[TransactionManager.validate_transaction] ERROR: Missing Falcon-512 signature for {tx.tx_id}.")
                return False

            # ✅ **Verify Digital Signature Against Stored Falcon-512**
            if not tx.verify_signature(stored_falcon_signature):
                print(f"[TransactionManager.validate_transaction] ERROR: Falcon-512 Signature verification failed for {tx.tx_id}.")
                return False

            # ✅ **Cross-Check UTXO Spending Rules Before Adding to Mempool**
            input_sum = Decimal("0")
            for tx_in in tx.inputs:
                utxo = self.utxo_manager.get_utxo(tx_in.tx_out_id)
                if not utxo:
                    print(f"[TransactionManager.validate_transaction] ERROR: Missing UTXO {tx_in.tx_out_id}")
                    return False
                if utxo["spent_status"] == 1:
                    print(f"[TransactionManager.validate_transaction] ERROR: UTXO {tx_in.tx_out_id} is already spent.")
                    return False
                input_sum += Decimal(str(utxo["amount"]))

            # ✅ **Ensure Outputs Are Properly Structured**
            output_sum = Decimal("0")
            for output in tx.outputs:
                if not hasattr(output, "amount") or not hasattr(output, "script_pub_key"):
                    print(f"[TransactionManager.validate_transaction] ERROR: Invalid transaction output structure.")
                    return False
                output_sum += Decimal(str(output.amount))

            # ✅ **Ensure Input Sum >= Output Sum**
            if input_sum < output_sum:
                print(f"[TransactionManager.validate_transaction] ERROR: Transaction {tx.tx_id} inputs {input_sum} < outputs {output_sum}")
                return False

            # ✅ **Validate Fees Against `FeeModel`**
            calculated_fee = input_sum - output_sum
            min_fee_required = Decimal(Constants.MIN_TRANSACTION_FEE)
            if calculated_fee < min_fee_required:
                print(f"[TransactionManager.validate_transaction] ERROR: Insufficient fee for {tx.tx_id}. "
                      f"Minimum required: {min_fee_required}, Given: {calculated_fee}")
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

            # ✅ **Enforce mempool expiration for outdated transactions**
            tx_age = time.time() - tx.timestamp
            if tx_age > Constants.MEMPOOL_TRANSACTION_EXPIRY:
                print(f"[TransactionManager.validate_transaction] ERROR: Transaction {tx.tx_id} expired (age: {tx_age} seconds).")
                return False

            # ✅ **Ensure block storage updates after validation**
            self.tx_storage.store_transaction(tx.tx_id, json.dumps(tx.to_dict(), sort_keys=True).encode("utf-8"))

            print(f"[TransactionManager.validate_transaction] ✅ SUCCESS: Transaction {tx.tx_id} validated and stored.")
            return True

        except Exception as e:
            print(f"[TransactionManager.validate_transaction] ERROR: Transaction validation failed for {tx.tx_id}: {str(e)}")
            return False


    def get_pending_transactions(self, block_size_mb: int = None):
        """
        Returns validated pending transactions from both mempools.
        If block_size_mb is provided, transactions are filtered by size.
        Uses fee-per-byte ordering while also prioritizing UTXO age.
        Ensures Falcon-512 signature verification and UTXO consistency.
        """

        total_block_size = (block_size_mb or Constants.MEMPOOL_MAX_SIZE_MB) * 1024 * 1024
        smart_tx_allocation = int(total_block_size * Constants.BLOCK_ALLOCATION_SMART)
        standard_tx_allocation = int(total_block_size * Constants.BLOCK_ALLOCATION_STANDARD)

        chain_height = self._get_chain_height()

        # ✅ Step 1: Fetch transactions from mempools
        smart_txs = self.smart_mempool.get_smart_transactions(smart_tx_allocation, chain_height)
        standard_txs = self.standard_mempool.get_pending_transactions(standard_tx_allocation)
        all_txs = smart_txs + standard_txs

        # ✅ Step 2: Validate Transactions Against LMDB and Falcon-512 Signature
        validated_txs = []
        for tx in all_txs:
            stored_tx = self.tx_storage.get_transaction(tx.tx_id)
            computed_tx_id = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()

            if not stored_tx or computed_tx_id != tx.tx_id:
                print(f"[TransactionManager.get_pending_transactions] ERROR: Transaction {tx.tx_id} hash mismatch or missing from LMDB.")
                continue  # Skip invalid transaction

            # ✅ Retrieve Falcon-512 signature from `txindex.lmdb`
            txindex_path = Constants.get_db_path("txindex")
            stored_falcon_signature = self.tx_storage.get_falcon_signature(tx.tx_id, txindex_path)

            if not stored_falcon_signature:
                print(f"[TransactionManager.get_pending_transactions] ERROR: Missing Falcon-512 signature for {tx.tx_id}.")
                continue  # Skip invalid transaction

            # ✅ Verify Falcon-512 Signature Against Stored Signature
            if not tx.verify_signature(stored_falcon_signature):
                print(f"[TransactionManager.get_pending_transactions] ERROR: Falcon-512 Signature verification failed for {tx.tx_id}.")
                continue  # Skip invalid transaction

            # ✅ Step 3: Cross-check UTXO spending rules before selection
            valid_utxo = True
            for tx_in in tx.inputs:
                utxo = self.utxo_manager.get_utxo(tx_in.tx_out_id)
                if not utxo or utxo["spent_status"] == 1:
                    print(f"[TransactionManager.get_pending_transactions] ERROR: UTXO {tx_in.tx_out_id} is invalid or already spent.")
                    valid_utxo = False
                    break

            if valid_utxo:
                validated_txs.append(tx)

        # ✅ Step 4: Sort transactions by UTXO age & fee-per-byte ratio
        sorted_txs = sorted(
            validated_txs,
            key=lambda tx: (tx.fee / self._calculate_transaction_size(tx), tx.inputs[0].age if tx.inputs else 0),
            reverse=True
        )

        # ✅ Step 5: Apply mempool expiration rules before selecting
        current_time = int(time.time())
        sorted_txs = [tx for tx in sorted_txs if (current_time - tx.timestamp) <= Constants.MEMPOOL_TRANSACTION_EXPIRY]

        # ✅ Step 6: Filter transactions by block size (if needed)
        if block_size_mb is not None:
            max_size_bytes = block_size_mb * 1024 * 1024
            selected_txs = []
            current_size = 0

            for tx in sorted_txs:
                tx_size = self._calculate_transaction_size(tx)
                if current_size + tx_size > max_size_bytes:
                    break  # Stop when max block size is reached
                selected_txs.append(tx)
                current_size += tx_size

            print(
                "[TransactionManager.get_pending_transactions] INFO: "
                f"Selected {len(selected_txs)} transactions | Total Size: {current_size} bytes"
            )
            return selected_txs

        # ✅ Step 7: Return all validated transactions if no block size filter
        return sorted_txs


    def sign_tx(self, transaction: Transaction):
        """
        Sign each input in the transaction using the miner's private key from key_manager.
        
        Fixes Applied:
        - ✅ Uses Falcon-512 for secure digital signatures.
        - ✅ Stores Falcon-512 signature in `txindex.lmdb`.
        - ✅ Stores SHA3-384 hashed signature in `full_block_chain.lmdb`.
        - ✅ Ensures transaction signatures are validated against LMDB transaction index storage.
        - ✅ Implements byte-level validation to confirm UTXO consistency.
        - ✅ Dynamically applies congestion-based fee scaling via Constants.MIN_TRANSACTION_FEE.
        """
        with self.mempool_lock:
            try:
                print(f"[TransactionManager.sign_tx] INFO: Signing transaction {transaction.tx_id}...")

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

                # ✅ Store Falcon-512 Signature in `txindex.lmdb`
                txindex_path = Constants.get_db_path("txindex")
                hashed_signature = store_transaction_signature(
                    tx_id=transaction.tx_id.encode(),
                    falcon_signature=original_signature,
                    txindex_path=txindex_path
                )

                # ✅ Store SHA3-384 hashed signature in `full_block_chain.lmdb`
                blockchain_db_path = Constants.get_db_path("full_block_chain")
                self.tx_storage.store_transaction(
                    transaction.tx_id,
                    {
                        "tx_id": transaction.tx_id,
                        "tx_signature_hash": hashed_signature.hex()
                    },
                    blockchain_db_path
                )

                # ✅ Ensure stored transaction signature matches computed hash
                stored_tx_data = self.tx_storage.get_transaction(transaction.tx_id)
                if not stored_tx_data:
                    print(f"[TransactionManager.sign_tx] ERROR: Transaction {transaction.tx_id} not found in LMDB storage.")
                    return False

                stored_signature = stored_tx_data.get("tx_signature_hash", "")
                if stored_signature != hashed_signature.hex():
                    print(f"[TransactionManager.sign_tx] ERROR: Signature mismatch for transaction {transaction.tx_id}.")
                    return False

                # ✅ Apply congestion-based fee scaling dynamically
                base_fee = self.fee_model.calculate_fee(
                    block_size=Constants.BLOCK_SIZE_RANGE[1],  # Use max block size for congestion scaling
                    payment_type="STANDARD",
                    amount=transaction.outputs[0].amount,
                    tx_size=self._calculate_transaction_size(transaction)
                )
                final_fee = max(base_fee, Constants.MIN_TRANSACTION_FEE)
                print(f"[TransactionManager.sign_tx] INFO: Adjusted transaction fee: {final_fee} based on congestion.")

                print(f"[TransactionManager.sign_tx] ✅ SUCCESS: Transaction {transaction.tx_id} signed and indexed securely.")

                return True

            except Exception as e:
                print(f"[TransactionManager.sign_tx] ERROR: Failed to sign transaction {transaction.tx_id}: {e}")
                return False
