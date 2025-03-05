import sys
import os
from decimal import Decimal
import hashlib
import time
import json
from typing import Any

# Import Constants and necessary modules from the project
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.coinbase import CoinbaseTx
from Zyiron_Chain.transactions.fees import FeeModel

# Using single hashing via hashlib.sha3_384 directly.
# Detailed print statements are used to trace steps (print instead of logging as per mission)
# This class is specifically for validating transactions according to our protocol rules.


class TXValidation:
    def __init__(self, block_manager: Any, storage_manager: Any, fee_model: FeeModel):
        """
        Initialize TXValidation with references to block_manager, storage_manager, and fee_model.
        
        :param block_manager: The BlockManager handling blockchain chain.
        :param storage_manager: The StorageManager instance for blockchain storage.
        :param fee_model: The FeeModel instance used for fee calculations.
        """
        self.block_manager = block_manager
        self.storage_manager = storage_manager
        self.fee_model = fee_model
        print("[TXVALIDATION] Initialized TXValidation instance.")

    def _validate_coinbase(self, tx: Any) -> bool:
        """
        Ensure the coinbase transaction follows protocol rules:
         - No inputs.
         - Exactly one output.
         - Transaction type is "COINBASE".
         - Fee is zero.
         - Uses correct single SHA3-384 hashing for transaction ID.
        
        :param tx: The transaction object to validate.
        :return: True if valid coinbase transaction, False otherwise.
        """
        # Lazy import to avoid circular dependencies
        from Zyiron_Chain.transactions.Blockchain_transaction import CoinbaseTx

        print(f"[TXVALIDATION] Validating Coinbase transaction with tx_id: {tx.tx_id}")
        # Ensure tx_id exists and is a string
        if not hasattr(tx, "tx_id") or not isinstance(tx.tx_id, str):
            print(f"[TXVALIDATION ERROR] Invalid Coinbase tx_id format: {tx.tx_id}")
            return False

        # Use single SHA3-384 hashing on tx_id
        single_hashed_tx_id = hashlib.sha3_384(tx.tx_id.encode()).hexdigest()
        print(f"[TXVALIDATION] Single hashed tx_id: {single_hashed_tx_id}")

        # Validate properties specific to Coinbase transactions
        if not (isinstance(tx, CoinbaseTx) and len(tx.inputs) == 0 and len(tx.outputs) == 1 and
                tx.type == "COINBASE" and Decimal(tx.fee) == Decimal("0") and single_hashed_tx_id == tx.tx_id):
            print(f"[TXVALIDATION ERROR] Coinbase transaction {tx.tx_id} failed validation rules.")
            return False

        print(f"[TXVALIDATION] Coinbase transaction {tx.tx_id} validated successfully.")
        return True

    def _calculate_block_reward(self) -> Decimal:
        """
        Calculate the current block reward using halving logic.
         - Halves every BLOCKCHAIN_HALVING_BLOCK_HEIGHT blocks (~4 years at 5 min block times).
         - Once MAX_SUPPLY is reached, reward is reduced to only transaction fees.
        
        :return: The block reward as a Decimal.
        """
        try:
            print("[TXVALIDATION] Calculating block reward using halving logic.")
            halving_interval = getattr(Constants, "BLOCKCHAIN_HALVING_BLOCK_HEIGHT", None)
            initial_reward = getattr(Constants, "INITIAL_COINBASE_REWARD", None)
            max_supply = getattr(Constants, "MAX_SUPPLY", None)
            min_fee = getattr(Constants, "MIN_TRANSACTION_FEE", None)

            if halving_interval is None or initial_reward is None or min_fee is None:
                print("[TXVALIDATION ERROR] Missing required constants for block reward calculation.")
                return Decimal("0")

            initial_reward = Decimal(initial_reward)
            min_fee = Decimal(min_fee)

            if not hasattr(self.block_manager, "chain") or not isinstance(self.block_manager.chain, list):
                print("[TXVALIDATION ERROR] Invalid blockchain reference in block manager.")
                return Decimal("0")

            current_height = len(self.block_manager.chain)
            halvings = max(0, current_height // halving_interval)
            reward = initial_reward / (2 ** halvings)

            try:
                total_mined = self.storage_manager.get_total_mined_supply()
            except Exception as e:
                print(f"[TXVALIDATION ERROR] Failed to retrieve total mined supply: {e}")
                return Decimal("0")

            if max_supply is not None and isinstance(max_supply, (int, float, Decimal)) and total_mined >= Decimal(max_supply):
                print("[TXVALIDATION] Max supply reached! Only transaction fees will be rewarded.")
                return Decimal("0")

            final_reward = max(reward, min_fee)
            print(f"[TXVALIDATION] Block reward calculated: {final_reward} (Total Mined: {total_mined} / MAX_SUPPLY: {max_supply})")
            return final_reward

        except Exception as e:
            print(f"[TXVALIDATION ERROR] Unexpected error during reward calculation: {e}")
            return Decimal("0")

    def validate_transaction_fee(self, transaction: Any) -> bool:
        """
        Ensure a transaction has sufficient fees.
         - Calculates required fee using FeeModel.
         - Compares it with the actual fee from inputs and outputs.
        
        :param transaction: The transaction object to validate.
        :return: True if fee is sufficient, False otherwise.
        """
        try:
            print(f"[TXVALIDATION] Validating fee for transaction {transaction.tx_id}.")
            # Calculate transaction size using storage manager's calculation
            transaction_size = self.storage_manager.calculate_transaction_size(transaction)
            print(f"[TXVALIDATION] Transaction size (bytes): {transaction_size}")

            required_fee = self.fee_model.calculate_fee(
                block_size=Constants.MAX_BLOCK_SIZE_BYTES,
                payment_type=transaction.type,
                amount=sum(Decimal(inp.amount) for inp in transaction.inputs),
                tx_size=transaction_size
            )
            total_fee = sum(Decimal(inp.amount) for inp in transaction.inputs) - \
                        sum(Decimal(out.amount) for out in transaction.outputs)
            print(f"[TXVALIDATION] Required fee: {required_fee} | Calculated fee: {total_fee}")

            if total_fee >= required_fee:
                print(f"[TXVALIDATION] Transaction {transaction.tx_id} meets fee requirement.")
                return True
            else:
                print(f"[TXVALIDATION WARNING] Insufficient fee for transaction {transaction.tx_id}. "
                      f"Required: {required_fee}, Provided: {total_fee}")
                return False

        except Exception as e:
            print(f"[TXVALIDATION ERROR] Failed to validate transaction fee for {transaction.tx_id}: {e}")
            return False
