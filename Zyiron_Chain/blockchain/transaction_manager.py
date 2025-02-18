import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


from Zyiron_Chain.transactions.Blockchain_transaction import Transaction
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.utxo_manager import UTXOManager
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.blockchain.utils.standardmempool import StandardMempool
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager
from threading import Lock
from Zyiron_Chain.smartpay.smartmempool import SmartMempool  # Add this import
from decimal import Decimal
import time 
import logging

# Remove all existing handlers (prevents log conflicts across modules)
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Set up clean logging for this module
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

log = logging.getLogger(__name__)  # Each module gets its own logger

log.info(f"{__name__} logger initialized.")

import json
# Ensure this is at the very top of your script, before any other code
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.coinbase import CoinbaseTx 
from Zyiron_Chain.transactions.transactiontype import PaymentTypeManager

class TransactionManager:
    def __init__(self, storage_manager, key_manager, poc):
        """
        Initialize the Transaction Manager.
        - Handles transactions in both standard and smart mempools.
        """
        self.storage_manager = storage_manager
        self.key_manager = key_manager
        self.poc = poc

        # ✅ Fetch the active network dynamically
        self.network = Constants.NETWORK  
        self.version = Constants.VERSION  # ✅ Fetch blockchain version

        # ✅ Initialize the mempools with sizes from constants
        self.standard_mempool = StandardMempool(self.poc, max_size_mb=int(Constants.MEMPOOL_MAX_SIZE_MB * Constants.STANDARD_MEMPOOL_ALLOCATION))
        self.smart_mempool = SmartMempool(max_size_mb=int(Constants.MEMPOOL_MAX_SIZE_MB * Constants.SMART_MEMPOOL_ALLOCATION))

        # ✅ Fetch transaction mempool routing from constants
        self.transaction_mempool_map = Constants.TRANSACTION_MEMPOOL_MAP

        # ✅ Set the default mempool to StandardMempool
        self._mempool = self.standard_mempool  

        logging.info(f"[TRANSACTION MANAGER] Initialized on {self.network.upper()} | Version {self.version} | Standard Mempool: {Constants.STANDARD_MEMPOOL_ALLOCATION * 100}% | Smart Mempool: {Constants.SMART_MEMPOOL_ALLOCATION * 100}%")

    @property
    def mempool(self):
        """ Return the active mempool """
        return self._mempool

    def set_mempool(self, mempool_type="standard"):
        """
        Switch between StandardMempool and SmartMempool based on the type.
        :param mempool_type: "standard" or "smart"
        """
        if mempool_type == "standard":
            self._mempool = self.standard_mempool
        elif mempool_type == "smart":
            self._mempool = self.smart_mempool
        else:
            raise ValueError(f"Invalid mempool type: {mempool_type}")

    def store_transaction_in_mempool(self, transaction):
        """
        Store a transaction in the appropriate mempool.
        """
        if not transaction.tx_id.startswith(Constants.ADDRESS_PREFIX):
            logging.error(f"[ERROR] Transaction {transaction.tx_id} has an invalid address prefix for {self.network}. Expected: {Constants.ADDRESS_PREFIX}")
            return False

        tx_type = PaymentTypeManager().get_transaction_type(transaction.tx_id)
        mempool_type = self.transaction_mempool_map.get(tx_type.name, {}).get("mempool", "StandardMempool")

        if mempool_type == "SmartMempool":
            current_height = len(self.storage_manager.block_manager.chain)
            success = self.smart_mempool.add_transaction(transaction, current_height)
        else:
            success = self.standard_mempool.add_transaction(transaction)

        if success:
            self.storage_manager.poc.route_transaction_to_mempool(transaction)
        else:
            logging.error(f"[ERROR] Failed to store transaction {transaction.tx_id} in the {mempool_type}.")


    def select_transactions_for_block(self, max_block_size_mb=10):
        """
        Select transactions for the next block, prioritizing high-fee transactions.
        - Includes transactions from both mempools.
        - Ensures the selected transactions fit within the block size.
        - Allocates space dynamically based on configured mempool allocations.
        - Prioritizes high-fee transactions within allocated space limits.
        """
        max_size_bytes = max_block_size_mb * 1024 * 1024  # Convert MB to bytes
        current_height = len(self.storage_manager.block_manager.chain)

        # ✅ Dynamically allocate block space using constants
        smart_tx_allocation = int(max_size_bytes * Constants.SMART_MEMPOOL_ALLOCATION)
        standard_tx_allocation = int(max_size_bytes * Constants.STANDARD_MEMPOOL_ALLOCATION)
        instant_tx_allocation = int(max_size_bytes * Constants.INSTANT_PAYMENT_ALLOCATION)
        
        # ✅ Fetch transactions based on allocation limits
        smart_txs = self.smart_mempool.get_smart_transactions(Constants.SMART_MEMPOOL_ALLOCATION * max_block_size_mb, current_height)
        standard_txs = self.standard_mempool.get_pending_transactions(Constants.STANDARD_MEMPOOL_ALLOCATION * max_block_size_mb)
        instant_txs = self.standard_mempool.get_pending_transactions(Constants.INSTANT_PAYMENT_ALLOCATION * max_block_size_mb, transaction_type="Instant")

        # ✅ Sort transactions by fee-per-byte (Higher fees get priority)
        all_txs = sorted(smart_txs + standard_txs + instant_txs, key=lambda tx: tx.fee / self._calculate_transaction_size(tx), reverse=True)

        # ✅ Track allocations separately for precise selection
        selected_txs, current_smart_size, current_standard_size, current_instant_size = [], 0, 0, 0

        for tx in all_txs:
            tx_size = self._calculate_transaction_size(tx)

            # ✅ Ensure transactions stay within their allocated space
            if tx in smart_txs and current_smart_size + tx_size > smart_tx_allocation:
                continue
            if tx in standard_txs and current_standard_size + tx_size > standard_tx_allocation:
                continue
            if tx in instant_txs and current_instant_size + tx_size > instant_tx_allocation:
                continue

            # ✅ Check overall block size limit and validate transaction
            if sum([current_smart_size, current_standard_size, current_instant_size]) + tx_size <= max_size_bytes and self.validate_transaction(tx):
                selected_txs.append(tx)

                # ✅ Update size tracking per category
                if tx in smart_txs:
                    current_smart_size += tx_size
                elif tx in instant_txs:
                    current_instant_size += tx_size
                else:
                    current_standard_size += tx_size

        logging.info(
            f"[BLOCK SELECTION] ✅ Selected {len(selected_txs)} transactions | "
            f"Smart Tx Size: {current_smart_size} bytes | "
            f"Standard Tx Size: {current_standard_size} bytes | "
            f"Instant Tx Size: {current_instant_size} bytes | "
            f"Total Size: {sum([current_smart_size, current_standard_size, current_instant_size])} bytes"
        )

        return selected_txs





    def _calculate_transaction_size(self, tx):
        """
        Calculate transaction size for block inclusion.
        - Uses SHA3-384-based size estimation.
        - Ensures metadata (timestamp, nonce, tx_id) is included.
        """
        base_size = len(tx.tx_id) + len(str(tx.timestamp)) + len(str(tx.nonce))

        input_size = sum(len(json.dumps(inp.to_dict(), sort_keys=True)) for inp in tx.inputs)
        output_size = sum(len(json.dumps(out.to_dict(), sort_keys=True)) for out in tx.outputs)

        return base_size + input_size + output_size

    def validate_transaction(self, tx):
        """
        Comprehensive transaction validation:
        - Signature verification
        - Input/output balance check
        - UTXO validation
        - Replay attack prevention
        - Fee validation
        - Coinbase transaction handling
        """
        try:
            # ✅ 1. Skip validation for coinbase transactions (Already Validated)
            if isinstance(tx, CoinbaseTx):
                return True

            # ✅ 2. Verify cryptographic signatures
            if not tx.verify_signature():
                logging.error(f"[TRANSACTION VALIDATION] ❌ Signature verification failed: {tx.tx_id}")
                return False

            # ✅ 3. Validate UTXO references
            input_sum = Decimal("0")
            for tx_input in tx.inputs:
                utxo = self.utxo_manager.get_utxo(tx_input.tx_out_id)
                if not utxo:
                    logging.error(f"[TRANSACTION VALIDATION] ❌ Missing UTXO: {tx_input.tx_out_id}")
                    return False
                if utxo.spent:
                    logging.error(f"[TRANSACTION VALIDATION] ❌ UTXO already spent: {tx_input.tx_out_id}")
                    return False
                input_sum += Decimal(str(utxo.amount))

            # ✅ 4. Validate outputs
            output_sum = sum(Decimal(str(out.amount)) for out in tx.outputs)

            # ✅ 5. Check value conservation (Prevent Inflation Attacks)
            if input_sum < output_sum:
                logging.error(f"[TRANSACTION VALIDATION] ❌ Inputs < Outputs ({input_sum} < {output_sum})")
                return False

            # ✅ 6. Validate Transaction Fees
            calculated_fee = input_sum - output_sum
            required_fee = self.fee_model.calculate_fee(
                tx_size=self._calculate_transaction_size(tx),
                tx_type=tx.type,
                network_congestion=self.mempool.size
            )

            # ✅ Fetch minimum fee requirement from constants
            min_fee_required = Decimal(Constants.MIN_TRANSACTION_FEE)

            if calculated_fee < required_fee or calculated_fee < min_fee_required:
                logging.error(
                    f"[TRANSACTION VALIDATION] ❌ Insufficient fee: {calculated_fee} < {required_fee} "
                    f"| Min Required: {min_fee_required}"
                )
                return False

            # ✅ 7. Prevent Replay Attacks (Ensure Unique Nonce & Network ID)
            if self.storage_manager.check_transaction_exists(
                tx.tx_id, 
                nonce=tx.nonce,
                network_id=tx.network_id
            ):
                logging.error(f"[TRANSACTION VALIDATION] ❌ Replay attack detected: {tx.tx_id}")
                return False

            logging.info(f"[TRANSACTION VALIDATION] ✅ Transaction {tx.tx_id} successfully validated.")
            return True

        except AttributeError as ae:
            logging.error(f"[TRANSACTION VALIDATION] ❌ Malformed transaction structure: {str(ae)}")
            return False
        except ValueError as ve:
            logging.error(f"[TRANSACTION VALIDATION] ❌ Invalid transaction values: {str(ve)}")
            return False
        except Exception as e:
            logging.error(f"[TRANSACTION VALIDATION] ❌ Unexpected validation error: {str(e)}")
            return False



    def _calculate_block_reward(self, block_height):
        """
        Calculate the current block reward using halving logic.
        - Halves every `BLOCKCHAIN_HALVING_BLOCK_HEIGHT` blocks (~4 years at 5 min block times).
        - Once `MAX_SUPPLY` is reached, the reward is reduced to only transaction fees.
        """
        halving_interval = Constants.BLOCKCHAIN_HALVING_BLOCK_HEIGHT  # ✅ Defined in constants
        initial_reward = Decimal(Constants.INITIAL_COINBASE_REWARD)  # ✅ Uses constant value

        halvings = block_height // halving_interval
        reward = initial_reward / (2 ** halvings)

        # ✅ Ensure we do NOT create coins beyond `MAX_SUPPLY`
        total_mined = self.storage_manager.get_total_mined_supply()
        
        if total_mined >= Constants.MAX_SUPPLY:
            logging.info(f"[BLOCK REWARD] Max supply reached! Only transaction fees will be rewarded.")
            return Decimal("0")  # ✅ No new coins, miners only get transaction fees

        return max(reward, Decimal("0"))  # ✅ Ensure it never goes negative



    def create_coinbase_tx(self, fees, block_height, network):
        """
        Creates a coinbase transaction for miners.
        :param fees: Total transaction fees collected in the block.
        :param block_height: Height of the block being mined.
        :param network: Mainnet or Testnet identifier (must be a string).
        :return: Coinbase transaction object.
        """
        if not isinstance(network, str) or network not in Constants.AVAILABLE_NETWORKS:
            raise ValueError(f"[ERROR] Invalid network parameter: {network}. Expected: {Constants.AVAILABLE_NETWORKS}")

        miner_address = self.key_manager.get_default_public_key(network, "miner")  # ✅ Get miner address

        # ✅ Ensure fees are always a valid Decimal and non-negative
        fees = Decimal(fees) if isinstance(fees, (int, float, Decimal)) and fees >= 0 else Decimal("0")

        # ✅ Check if the max supply has been reached
        total_mined = self.storage_manager.get_total_mined_supply()
        if total_mined >= Constants.MAX_SUPPLY:
            logging.info(f"[COINBASE TX] Max supply reached! Only transaction fees will be rewarded.")
            block_reward = Decimal("0")  # ✅ No new coins, only fees are given
        else:
            block_reward = self._calculate_block_reward(block_height)  # ✅ Normal reward before max supply

        total_reward = max(block_reward + fees, Decimal(Constants.MIN_TRANSACTION_FEE))  # ✅ Ensures min payout

        logging.info(f"[COINBASE TX] Creating Coinbase Transaction | Block Height: {block_height} | Reward: {block_reward} | Fees: {fees} | Total: {total_reward}")

        return CoinbaseTx(
            block_height=block_height,
            miner_address=miner_address,
            reward=total_reward
        )



    def store_transaction_in_mempool(self, transaction):
        """
        Store a transaction in the appropriate mempool and route it via PoC.
        """
        with self.mempool_lock:
            try:
                # ✅ Validate transaction ID prefix against network
                if not transaction.tx_id.startswith(Constants.ADDRESS_PREFIX):
                    logging.error(
                        f"[TRANSACTION MEMPOOL] ❌ Invalid transaction prefix {transaction.tx_id} for {self.network}. "
                        f"Expected: {Constants.ADDRESS_PREFIX}"
                    )
                    return False

                # ✅ Determine the transaction type dynamically
                tx_type = PaymentTypeManager().get_transaction_type(transaction.tx_id)
                mempool_config = Constants.TRANSACTION_MEMPOOL_MAP.get(tx_type.name, {})

                # ✅ Ensure the transaction type exists in constants
                if not mempool_config:
                    logging.error(f"[TRANSACTION MEMPOOL] ❌ Unknown transaction type: {tx_type.name}")
                    return False

                mempool_type = mempool_config.get("mempool", "StandardMempool")

                # ✅ Route transaction to the correct mempool
                if mempool_type == "SmartMempool":
                    current_height = len(self.storage_manager.block_manager.chain)
                    success = self.smart_mempool.add_transaction(transaction, current_height)
                else:
                    success = self.standard_mempool.add_transaction(transaction)

                if success:
                    logging.info(f"[TRANSACTION MEMPOOL] ✅ Transaction {transaction.tx_id} stored in {mempool_type}.")
                    self.storage_manager.poc.route_transaction_to_mempool(transaction)
                    return True
                else:
                    logging.error(f"[TRANSACTION MEMPOOL] ❌ Failed to store transaction {transaction.tx_id} in {mempool_type}.")
                    return False

            except AttributeError as ae:
                logging.error(f"[TRANSACTION MEMPOOL] ❌ Transaction structure error: {str(ae)}")
                return False
            except Exception as e:
                logging.error(f"[TRANSACTION MEMPOOL] ❌ Unexpected error storing transaction {transaction.tx_id}: {str(e)}")
                return False



    def add_transaction_to_mempool(self, transaction):
        """
        Add a transaction to the correct mempool, ensuring validity and preventing replay attacks.
        :param transaction: The transaction object to add.
        """
        with self.mempool_lock:
            try:
                # ✅ Check if the transaction already exists in any mempool
                if transaction.tx_id in self.smart_mempool.transactions or transaction.tx_id in self.standard_mempool.transactions:
                    logging.error(f"[MEMPOOL] ❌ Transaction {transaction.tx_id} already exists in a mempool.")
                    return False

                # ✅ Validate the transaction before adding
                if not self.validate_transaction(transaction):
                    logging.error(f"[MEMPOOL] ❌ Transaction {transaction.tx_id} is invalid.")
                    return False

                # ✅ Prevent replay attacks using nonce & network_id
                if self.storage_manager.check_transaction_exists(transaction.tx_id, transaction.nonce, transaction.network_id):
                    logging.error(f"[MEMPOOL] ❌ Replay attack detected for transaction {transaction.tx_id}.")
                    return False

                # ✅ Determine the correct mempool using Constants
                tx_type = PaymentTypeManager().get_transaction_type(transaction.tx_id)
                mempool_config = Constants.TRANSACTION_MEMPOOL_MAP.get(tx_type.name, {})

                if not mempool_config:
                    logging.error(f"[MEMPOOL] ❌ Unknown transaction type: {tx_type.name}")
                    return False

                mempool_type = mempool_config.get("mempool", "StandardMempool")

                # ✅ Determine current block height
                current_height = len(self.storage_manager.block_manager.chain)

                # ✅ Store transaction in the correct mempool
                if mempool_type == "SmartMempool":
                    success = self.smart_mempool.add_transaction(transaction, current_height)
                else:
                    success = self.standard_mempool.add_transaction(transaction)

                # ✅ Retry in StandardMempool if SmartMempool is full
                if not success and mempool_type == "SmartMempool":
                    logging.warning(f"[MEMPOOL] ⚠️ SmartMempool is full. Retrying transaction {transaction.tx_id} in StandardMempool.")
                    success = self.standard_mempool.add_transaction(transaction)

                # ✅ Route transaction to LMDB if successful
                if success:
                    self.storage_manager.poc.route_transaction_to_mempool(transaction)
                    logging.info(f"[MEMPOOL] ✅ Transaction {transaction.tx_id} added to {mempool_type}.")
                    return True
                else:
                    logging.error(f"[MEMPOOL] ❌ Failed to add transaction {transaction.tx_id} to {mempool_type}.")
                    return False

            except AttributeError as ae:
                logging.error(f"[MEMPOOL] ❌ Transaction structure error: {str(ae)}")
                return False
            except Exception as e:
                logging.error(f"[MEMPOOL] ❌ Unexpected error storing transaction {transaction.tx_id}: {str(e)}")
                return False






    def validate_transaction(self, tx):
        """
        Validate transaction integrity:
        - Signature verification.
        - Input/output balance check.
        - Prevent replay attacks by ensuring unique nonce and network_id.
        - Ensure fees meet the required minimum.
        - Validate UTXO availability.
        - Ensure proper transaction routing.
        """
        try:
            # ✅ 1. Verify cryptographic signature
            if not tx.verify_signature():
                logging.error(f"[VALIDATION] ❌ Signature verification failed for transaction {tx.tx_id}.")
                return False

            # ✅ 2. Retrieve and sum input amounts from UTXOs
            input_sum = Decimal(0)
            for tx_input in tx.tx_inputs:
                utxo = self.storage_manager.get_utxo(tx_input.tx_out_id)
                if not utxo:
                    logging.error(f"[VALIDATION] ❌ Missing UTXO reference: {tx_input.tx_out_id}")
                    return False
                if utxo.spent:
                    logging.error(f"[VALIDATION] ❌ UTXO already spent: {tx_input.tx_out_id}")
                    return False
                input_sum += Decimal(utxo.amount)

            # ✅ 3. Sum output amounts
            output_sum = sum(Decimal(out.amount) for out in tx.tx_outputs)

            # ✅ 4. Ensure inputs cover outputs
            if input_sum < output_sum:
                logging.error(f"[VALIDATION] ❌ Transaction {tx.tx_id} input sum {input_sum} < output sum {output_sum}.")
                return False

            # ✅ 5. Ensure minimum fee is met based on congestion
            transaction_fee = input_sum - output_sum
            required_fee = self.fee_model.calculate_fee(
                tx_size=self._calculate_transaction_size(tx),
                tx_type=tx.type,
                network_congestion=self.mempool.size
            )

            min_fee_required = Decimal(Constants.MIN_TRANSACTION_FEE)
            if transaction_fee < required_fee or transaction_fee < min_fee_required:
                logging.error(f"[VALIDATION] ❌ Insufficient fee for transaction {tx.tx_id}. "
                            f"Required: {max(required_fee, min_fee_required)}, Given: {transaction_fee}")
                return False

            # ✅ 6. Prevent replay attacks
            if self.storage_manager.poc.check_transaction_exists(tx.tx_id, tx.nonce, tx.network_id):
                logging.error(f"[VALIDATION] ❌ Replay attack detected for transaction {tx.tx_id}.")
                return False

            # ✅ 7. Validate correct transaction routing based on mempool mapping
            tx_type = PaymentTypeManager().get_transaction_type(tx.tx_id)
            expected_mempool = Constants.TRANSACTION_MEMPOOL_MAP.get(tx_type.name, {}).get("mempool", "StandardMempool")

            if expected_mempool == "SmartMempool" and tx.tx_id not in self.smart_mempool.transactions:
                logging.error(f"[VALIDATION] ❌ Transaction {tx.tx_id} should be in SmartMempool but isn't.")
                return False

            if expected_mempool == "StandardMempool" and tx.tx_id not in self.standard_mempool.transactions:
                logging.error(f"[VALIDATION] ❌ Transaction {tx.tx_id} should be in StandardMempool but isn't.")
                return False

            logging.info(f"[VALIDATION] ✅ Transaction {tx.tx_id} passed all validation checks.")
            return True

        except Exception as e:
            logging.error(f"[VALIDATION] ❌ Transaction validation failed: {str(e)}")
            return False




    def get_pending_transactions(self, block_size_mb=None):
        """
        Retrieve pending transactions from both Smart and Standard Mempools.
        - If `block_size_mb` is provided, filters transactions to fit within that limit.
        - Uses configured allocations for Smart and Standard transactions.
        - Ensures transactions adhere to block space constraints dynamically.

        :param block_size_mb: (Optional) Maximum block size in MB.
        :return: A list of selected transactions fitting within the block size.
        """
        # ✅ Define block size constraints dynamically
        total_block_size = (block_size_mb or Constants.MEMPOOL_MAX_SIZE_MB) * 1024 * 1024
        smart_tx_allocation = int(total_block_size * Constants.SMART_MEMPOOL_ALLOCATION)
        standard_tx_allocation = int(total_block_size * Constants.STANDARD_MEMPOOL_ALLOCATION)

        # ✅ Fetch transactions from each mempool based on defined allocations
        smart_txs = self.smart_mempool.get_smart_transactions(smart_tx_allocation, len(self.storage_manager.block_manager.chain))
        standard_txs = self.standard_mempool.get_pending_transactions(standard_tx_allocation)

        all_txs = smart_txs + standard_txs

        # ✅ If block size limit is set, filter transactions dynamically
        if block_size_mb is not None:
            max_size_bytes = block_size_mb * 1024 * 1024
            selected_txs, current_size = [], 0

            # ✅ Prioritize transactions by highest fee per byte
            sorted_txs = sorted(all_txs, key=lambda tx: tx.fee / self._calculate_transaction_size(tx), reverse=True)

            for tx in sorted_txs:
                tx_size = self._calculate_transaction_size(tx)

                # ✅ Ensure we do not exceed the block size limit
                if current_size + tx_size > max_size_bytes:
                    break

                selected_txs.append(tx)
                current_size += tx_size

            logging.info(f"[MEMPOOL] ✅ Selected {len(selected_txs)} transactions | Total Size: {current_size} bytes")
            return selected_txs

        return all_txs  # ✅ Return all pending transactions if no size limit is set.
