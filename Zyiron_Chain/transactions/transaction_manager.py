import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from Zyiron_Chain.transactions.tx import Transaction
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.utils.standardmempool import StandardMempool
from Zyiron_Chain.transactions.payment_type import PaymentTypeManager
from threading import Lock
from Zyiron_Chain.smartpay.smartmempool import SmartMempool
from decimal import Decimal
import time
import hashlib
import json
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.utils.hashing import Hashing
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx
    from Zyiron_Chain.transactions.fees import FundsAllocator

class TransactionManager:
    def __init__(self, storage_manager, key_manager, poc):
        """
        [TransactionManager.__init__] Initialize the Transaction Manager.
        Handles transactions in both standard and smart mempools.
        """
        self.storage_manager = storage_manager
        self.key_manager = key_manager
        self.poc = poc

        self.network = Constants.NETWORK
        self.version = Constants.VERSION

        self.standard_mempool = StandardMempool(self.poc, max_size_mb=int(Constants.MEMPOOL_MAX_SIZE_MB * Constants.MEMPOOL_STANDARD_ALLOCATION))
        self.smart_mempool = SmartMempool(max_size_mb=int(Constants.MEMPOOL_MAX_SIZE_MB * Constants.MEMPOOL_SMART_ALLOCATION))

        self.transaction_mempool_map = Constants.TRANSACTION_MEMPOOL_MAP
        self._mempool = self.standard_mempool
        self.mempool_lock = Lock()

        print(f"[TransactionManager.__init__] Initialized on {self.network.upper()} | Version {self.version} | "
              f"Standard Mempool: {Constants.MEMPOOL_STANDARD_ALLOCATION * 100}% | Smart Mempool: {Constants.MEMPOOL_SMART_ALLOCATION * 100}%")

    @property
    def mempool(self):
        """[TransactionManager.mempool] Return the active mempool."""
        return self._mempool

    def set_mempool(self, mempool_type="standard"):
        """
        [TransactionManager.set_mempool] Switch between Standard and Smart mempools.
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

    def store_transaction_in_mempool(self, transaction):
        """
        [TransactionManager.store_transaction_in_mempool] 
        Store a transaction in the appropriate mempool after validating its type and network prefix.
        Uses single SHA3-384 hashing for transaction ID.
        """
        try:
            hashed_tx_id = hashlib.sha3_384(transaction.tx_id.encode()).hexdigest()
            if not hashed_tx_id.startswith(Constants.ADDRESS_PREFIX):
                print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Transaction {transaction.tx_id} has an invalid address prefix for {self.network}. Expected: {Constants.ADDRESS_PREFIX}")
                return False

            tx_type = PaymentTypeManager().get_transaction_type(hashed_tx_id)
            if not tx_type:
                print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Unable to determine transaction type for {transaction.tx_id}")
                return False

            mempool_type = self.transaction_mempool_map.get(tx_type.name, {}).get("mempool", "StandardMempool")
            current_height = len(self.storage_manager.block_manager.chain)
            if mempool_type == "SmartMempool":
                success = self.smart_mempool.add_transaction(transaction, current_height)
            else:
                success = self.standard_mempool.add_transaction(transaction)

            if success:
                print(f"[TransactionManager.store_transaction_in_mempool] INFO: Transaction {hashed_tx_id} stored in {mempool_type}.")
                self.storage_manager.poc.route_transaction_to_mempool(transaction)
                return True
            else:
                print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Failed to store transaction {hashed_tx_id} in {mempool_type}.")
                return False
        except Exception as e:
            print(f"[TransactionManager.store_transaction_in_mempool] ERROR: Unexpected error storing transaction {transaction.tx_id}: {str(e)}")
            return False

    def select_transactions_for_block(self, max_block_size_mb=10):
        """
        [TransactionManager.select_transactions_for_block] 
        Select transactions for the next block, prioritizing high fee-per-byte transactions.
        Ensures transactions fit within the specified block size.
        """
        try:
            max_size_bytes = max_block_size_mb * 1024 * 1024
            current_height = len(self.storage_manager.block_manager.chain)

            smart_tx_allocation = int(max_size_bytes * Constants.BLOCK_ALLOCATION_SMART)
            standard_tx_allocation = int(max_size_bytes * Constants.BLOCK_ALLOCATION_STANDARD)
            instant_tx_allocation = int(max_size_bytes * Constants.INSTANT_PAYMENT_ALLOCATION)

            smart_txs = self.smart_mempool.get_pending_transactions(Constants.BLOCK_ALLOCATION_SMART * max_block_size_mb, current_height)
            standard_txs = self.standard_mempool.get_pending_transactions(Constants.BLOCK_ALLOCATION_STANDARD * max_block_size_mb)
            instant_txs = self.standard_mempool.get_pending_transactions(Constants.INSTANT_PAYMENT_ALLOCATION * max_block_size_mb, transaction_type="Instant")

            all_txs = smart_txs + standard_txs + instant_txs
            sorted_txs = sorted(all_txs, key=lambda tx: tx.fee / self._calculate_transaction_size(tx), reverse=True)

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
                if (current_smart_size + current_standard_size + current_instant_size + tx_size) <= max_size_bytes and self.validate_transaction(tx):
                    selected_txs.append(tx)
                    if tx in smart_txs:
                        current_smart_size += tx_size
                    elif tx in instant_txs:
                        current_instant_size += tx_size
                    else:
                        current_standard_size += tx_size

            print(f"[TransactionManager.select_transactions_for_block] INFO: Selected {len(selected_txs)} transactions | Smart: {current_smart_size} bytes | Standard: {current_standard_size} bytes | Instant: {current_instant_size} bytes | Total: {current_smart_size + current_standard_size + current_instant_size} bytes")
            return selected_txs
        except Exception as e:
            print(f"[TransactionManager.select_transactions_for_block] ERROR: {str(e)}")
            return []

    def _calculate_transaction_size(self, tx):
        """
        [TransactionManager._calculate_transaction_size] 
        Calculate the transaction size in bytes using single SHA3-384 hashing.
        """
        try:
            if isinstance(tx.tx_id, bytes):
                tx.tx_id = tx.tx_id.decode("utf-8")
            single_hashed_tx_id = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()
            base_size = len(single_hashed_tx_id) + len(str(tx.timestamp)) + len(str(tx.nonce))
            input_size = sum(len(json.dumps(inp.to_dict(), sort_keys=True)) for inp in tx.inputs)
            output_size = sum(len(json.dumps(out.to_dict(), sort_keys=True)) for out in tx.outputs)
            total_size = base_size + input_size + output_size
            return total_size
        except Exception as e:
            print(f"[TransactionManager._calculate_transaction_size] ERROR: Failed to calculate size for {tx.tx_id}: {str(e)}")
            return -1

    def validate_transaction(self, tx):
        """
        [TransactionManager.validate_transaction] 
        Validate transaction integrity: signature, UTXO availability, fee, and replay prevention.
        """
        try:
            from Zyiron_Chain.transactions.coinbase import CoinbaseTx
            if isinstance(tx, CoinbaseTx):
                print(f"[TransactionManager.validate_transaction] INFO: Coinbase transaction {tx.tx_id} skipped for further validation.")
                return True
            if isinstance(tx.tx_id, bytes):
                tx.tx_id = tx.tx_id.decode("utf-8")
            single_hashed_tx_id = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()
            if not tx.verify_signature():
                print(f"[TransactionManager.validate_transaction] ERROR: Signature verification failed for {single_hashed_tx_id}")
                return False
            input_sum = Decimal("0")
            for tx_input in tx.tx_inputs:
                utxo = self.utxo_manager.get_utxo(tx_input.tx_out_id)
                if not utxo:
                    print(f"[TransactionManager.validate_transaction] ERROR: Missing UTXO {tx_input.tx_out_id}")
                    return False
                if utxo.spent:
                    print(f"[TransactionManager.validate_transaction] ERROR: UTXO {tx_input.tx_out_id} already spent")
                    return False
                input_sum += Decimal(str(utxo.amount))
            output_sum = sum(Decimal(str(out.amount)) for out in tx.tx_outputs)
            if input_sum < output_sum:
                print(f"[TransactionManager.validate_transaction] ERROR: Transaction {tx.tx_id} inputs {input_sum} < outputs {output_sum}")
                return False
            calculated_fee = input_sum - output_sum
            required_fee = self.fee_model.calculate_fee(
                tx_size=self._calculate_transaction_size(tx),
                tx_type=tx.type,
                network_congestion=self.mempool.size
            )
            min_fee_required = Decimal(Constants.MIN_TRANSACTION_FEE)
            if calculated_fee < required_fee or calculated_fee < min_fee_required:
                print(f"[TransactionManager.validate_transaction] ERROR: Insufficient fee for {tx.tx_id}. Required: {max(required_fee, min_fee_required)}, Given: {calculated_fee}")
                return False
            if self.storage_manager.poc.check_transaction_exists(tx.tx_id, tx.nonce, tx.network_id):
                print(f"[TransactionManager.validate_transaction] ERROR: Replay attack detected for {tx.tx_id}")
                return False
            tx_type = PaymentTypeManager().get_transaction_type(tx.tx_id)
            expected_mempool = Constants.TRANSACTION_MEMPOOL_MAP.get(tx_type.name, {}).get("mempool", "StandardMempool")
            if expected_mempool == "SmartMempool" and tx.tx_id not in self.smart_mempool.transactions:
                print(f"[TransactionManager.validate_transaction] ERROR: {tx.tx_id} should be in SmartMempool but is not")
                return False
            if expected_mempool == "StandardMempool" and tx.tx_id not in self.standard_mempool.transactions:
                print(f"[TransactionManager.validate_transaction] ERROR: {tx.tx_id} should be in StandardMempool but is not")
                return False
            print(f"[TransactionManager.validate_transaction] INFO: Transaction {tx.tx_id} passed all validation checks.")
            return True
        except Exception as e:
            print(f"[TransactionManager.validate_transaction] ERROR: Transaction validation failed for {tx.tx_id}: {str(e)}")
            return False

    def get_pending_transactions(self, block_size_mb=None):
        """
        [TransactionManager.get_pending_transactions] 
        Retrieve pending transactions from both mempools.
        If block_size_mb is provided, filter transactions to fit within that size.
        """
        total_block_size = (block_size_mb or Constants.MEMPOOL_MAX_SIZE_MB) * 1024 * 1024
        smart_tx_allocation = int(total_block_size * Constants.BLOCK_ALLOCATION_SMART)
        standard_tx_allocation = int(total_block_size * Constants.BLOCK_ALLOCATION_STANDARD)
        smart_txs = self.smart_mempool.get_smart_transactions(smart_tx_allocation, len(self.storage_manager.block_manager.chain))
        standard_txs = self.standard_mempool.get_pending_transactions(standard_tx_allocation)
        all_txs = smart_txs + standard_txs
        if block_size_mb is not None:
            max_size_bytes = block_size_mb * 1024 * 1024
            selected_txs = []
            current_size = 0
            sorted_txs = sorted(all_txs, key=lambda tx: tx.fee / self._calculate_transaction_size(tx), reverse=True)
            for tx in sorted_txs:
                tx_size = self._calculate_transaction_size(tx)
                if current_size + tx_size > max_size_bytes:
                    break
                selected_txs.append(tx)
                current_size += tx_size
            print(f"[TransactionManager.get_pending_transactions] INFO: Selected {len(selected_txs)} transactions | Total Size: {current_size} bytes")
            return selected_txs
        return all_txs

    def sign_tx(self, transaction):
        """
        [TransactionManager.sign_tx] Sign the transaction inputs using the miner's private key.
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
                    signature_data = f"{tx_in.tx_out_id}{private_key}"
                    tx_in.script_sig = hashlib.sha3_384(signature_data.encode()).hexdigest()
                print(f"[TransactionManager.sign_tx] INFO: Transaction {transaction.tx_id} successfully signed.")
            except Exception as e:
                print(f"[TransactionManager.sign_tx] ERROR: Failed to sign transaction {transaction.tx_id}: {e}")
                raise ValueError(f"Transaction signing error: {e}")
