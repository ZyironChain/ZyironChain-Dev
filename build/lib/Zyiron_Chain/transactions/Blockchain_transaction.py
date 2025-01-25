import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

import json
import hashlib
import time
from typing import List, Dict
from Zyiron_Chain.transactions.txout import TransactionOut, UTXOManager
from Zyiron_Chain.transactions.fees import FeeModel

from decimal import Decimal

class CoinbaseTx:
    BASE_REWARD = Decimal("100.00000000")  # Base block reward

    def __init__(self, key_manager, network, utxo_manager, transaction_fees=Decimal("0.0")):
        """
        Initialize a Coinbase transaction.
        :param key_manager: KeyManager instance.
        :param network: Network type (e.g., "testnet", "mainnet").
        :param utxo_manager: Instance of UTXOManager to register UTXOs.
        :param transaction_fees: Total fees from transactions in the block (default: 0).
        """
        if not key_manager or not network or not utxo_manager:
            raise ValueError("KeyManager, network, and UTXOManager are required.")

        if network not in ["mainnet", "testnet"]:
            raise ValueError(f"Invalid network: {network}. Choose 'mainnet' or 'testnet'.")

        self.key_manager = key_manager
        self.network = network
        self.utxo_manager = utxo_manager
        self.transaction_fees = Decimal(transaction_fees)

        # Ensure key_manager structure is valid
        if not hasattr(key_manager, "keys") or network not in key_manager.keys:
            raise ValueError(f"KeyManager is missing required keys for network: {network}.")

        # Determine miner details
        miner_identifier = key_manager.keys[network]["defaults"].get("miner")
        if not miner_identifier:
            raise ValueError(f"No default miner key set for network: {network}.")

        miner_key_data = key_manager.keys[network]["keys"].get(miner_identifier)
        if not miner_key_data:
            raise ValueError(f"Miner key '{miner_identifier}' not found in {network}.")

        self.miner_public_key = miner_key_data["hashed_public_key"]
        self.network_prefix = "KCT" if network == "testnet" else "KYZ"  # Determine network prefix
        self.timestamp = time.time()

        # Create and register the transaction output
        self.tx_out = self.create_tx_out()

        # Calculate the transaction ID
        self.tx_id = self.calculate_tx_id()

    def create_tx_out(self):
        """
        Create the transaction output for the miner's reward and register it with the UTXOManager.
        Includes transaction fees in the total reward.
        """
        total_reward = self.BASE_REWARD + self.transaction_fees
        tx_out = TransactionOut(
            script_pub_key=self.miner_public_key,
            amount=total_reward  # Total reward (base + fees)
        )
        # Register the UTXO with the manager
        self.utxo_manager.register_utxo(tx_out.tx_out_id, {
            "amount": float(total_reward),
            "script_pub_key": self.miner_public_key,
            "locked": False
        })
        return tx_out

    def calculate_tx_id(self):
        """
        Calculate the unique transaction ID for the Coinbase transaction.
        """
        tx_data = f"{self.tx_out.tx_out_id}{self.timestamp}"
        return hashlib.sha3_384(tx_data.encode()).hexdigest()




class TransactionIn:
    def __init__(self, tx_out_id: str, script_sig: str):
        """
        Represents a transaction input with an unlocking script.
        :param tx_out_id: ID of the referenced TransactionOut.
        :param script_sig: The unlocking script to satisfy the locking script.
        """
        if not tx_out_id or not isinstance(tx_out_id, str):
            raise ValueError("tx_out_id must be a non-empty string.")
        if not script_sig or not isinstance(script_sig, str):
            raise ValueError("script_sig must be a non-empty string.")

        self.tx_out_id = tx_out_id
        self.script_sig = script_sig

    def to_dict(self) -> Dict:
        """
        Serialize the TransactionIn to a dictionary.
        """
        return {
            "tx_out_id": self.tx_out_id,
            "script_sig": self.script_sig,
        }

    @staticmethod
    def from_dict(data: Dict):
        """
        Deserialize a TransactionIn from a dictionary.
        """
        if "tx_out_id" not in data or "script_sig" not in data:
            raise ValueError("Invalid data for TransactionIn: Missing required fields.")
        return TransactionIn(
            tx_out_id=data["tx_out_id"],
            script_sig=data["script_sig"],
        )

    def validate(self):
        """
        Validate the TransactionIn object to ensure it has valid fields.
        """
        if not self.tx_out_id or not isinstance(self.tx_out_id, str):
            raise ValueError("tx_out_id must be a valid non-empty string.")
        if not self.script_sig or not isinstance(self.script_sig, str):
            raise ValueError("script_sig must be a valid non-empty string.")
        print(f"[DEBUG] TransactionIn is valid with tx_out_id: {self.tx_out_id}, script_sig: {self.script_sig}")

    def __str__(self):
        """
        String representation of the TransactionIn for debugging.
        """
        return f"TransactionIn(tx_out_id={self.tx_out_id}, script_sig={self.script_sig})"



class Transaction:
    def __init__(self, tx_inputs: List[TransactionIn], tx_outputs: List[TransactionOut]):
        """
        Represents a blockchain transaction.
        :param tx_inputs: List of transaction inputs.
        :param tx_outputs: List of transaction outputs.
        """
        if not tx_inputs or not tx_outputs:
            raise ValueError("Transactions must have at least one input and one output.")

        self.tx_inputs = tx_inputs
        self.tx_outputs = tx_outputs
        self.timestamp = time.time()
        self.tx_id = self.calculate_tx_id()


    def store_transaction(self, db, transaction):
        """
        Store a transaction in LevelDB.
        """
        key = f"transaction:{transaction.tx_id}".encode()
        value = json.dumps(transaction.to_dict()).encode()
        try:
            db.Put(key, value)
            print(f"[INFO] Stored transaction {transaction.tx_id} in LevelDB.")
        except Exception as e:
            print(f"[ERROR] Failed to store transaction {transaction.tx_id}: {e}")

    def calculate_tx_id(self) -> str:
        """
        Calculate the unique transaction ID based on its inputs, outputs, and timestamp.
        """
        input_data = "".join(inp.tx_out_id + inp.script_sig for inp in self.tx_inputs)
        output_data = "".join(out.tx_out_id for out in self.tx_outputs)
        tx_data = f"{input_data}{output_data}{self.timestamp}"
        return hashlib.sha3_384(tx_data.encode()).hexdigest()

    @property
    def hash(self):
        """
        Property to return the transaction hash, which is the same as the transaction ID.
        """
        return self.tx_id

    def to_dict(self) -> Dict:
        """
        Serialize the Transaction to a dictionary.
        """
        return {
            "tx_inputs": [inp.to_dict() for inp in self.tx_inputs],
            "tx_outputs": [out.to_dict() for out in self.tx_outputs],
            "timestamp": self.timestamp,
            "tx_id": self.tx_id,
        }

    def validate_transaction(self, utxo_manager, fee_model, block_size, payment_type, leveldb=None):
        """
        Validate the transaction by ensuring valid inputs, outputs, and fees.
        Now supports LevelDB validation in addition to existing logic.
        """
        if not self.tx_inputs or len(self.tx_inputs) == 0:
            raise ValueError("Transaction must have at least one input.")
        if not self.tx_outputs or len(self.tx_outputs) == 0:
            raise ValueError("Transaction must have at least one output.")

        # Validate each input against UTXOManager and optionally LevelDB
        for tx_in in self.tx_inputs:
            # Check UTXOManager
            utxo = utxo_manager.get_utxo(tx_in.tx_out_id)
            if not utxo or utxo.locked:
                raise ValueError(f"Referenced UTXO {tx_in.tx_out_id} is invalid or locked in UTXOManager.")

            # Additional LevelDB validation
            if leveldb:
                try:
                    key = f"utxo:{tx_in.tx_out_id}".encode()
                    stored_utxo = leveldb.Get(key)
                    utxo_data = json.loads(stored_utxo.decode())
                    if utxo_data.get("locked", False):
                        raise ValueError(f"Referenced UTXO {tx_in.tx_out_id} is locked in LevelDB.")
                except KeyError:
                    raise ValueError(f"Referenced UTXO {tx_in.tx_out_id} does not exist in LevelDB.")
                except Exception as e:
                    raise ValueError(f"Error validating UTXO {tx_in.tx_out_id} in LevelDB: {e}")

        # Calculate transaction size
        transaction_size = sum(len(str(tx_in.to_dict())) + len(str(tx_out.to_dict())) 
                            for tx_in, tx_out in zip(self.tx_inputs, self.tx_outputs))

        # Validate transaction fees
        required_fee = fee_model.calculate_fee(block_size=block_size, payment_type=payment_type, tx_size=transaction_size)
        total_input = sum(utxo_manager.get_utxo_amount(tx_in.tx_out_id) for tx_in in self.tx_inputs)
        total_output = sum(out.amount for out in self.tx_outputs)
        actual_fee = total_input - total_output

        if actual_fee < required_fee:
            raise ValueError(f"Insufficient transaction fee. Required: {required_fee}, Actual: {actual_fee}")

        # Register outputs in LevelDB (if available)
        if leveldb:
            for index, tx_out in enumerate(self.tx_outputs):
                try:
                    key = f"utxo:{self.tx_id}:{index}".encode()
                    leveldb.Put(key, json.dumps(tx_out.to_dict()).encode())
                    print(f"[INFO] Registered output for transaction {self.tx_id}:{index} in LevelDB.")
                except Exception as e:
                    print(f"[ERROR] Failed to register output {self.tx_id}:{index} in LevelDB: {e}")


    def get_transaction(self, tx_id):
        """
        Retrieve a transaction by its ID from LevelDB.
        """
        key = f"transaction:{tx_id}".encode()
        try:
            value = self.db.Get(key)
            return Transaction.from_dict(json.loads(value.decode()))
        except KeyError:
            print(f"[INFO] Transaction {tx_id} not found in LevelDB.")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to retrieve transaction {tx_id}: {e}")
            return None



    def validate_with_leveldb(self, tx_in, leveldb):
        """
        Validate a single transaction input with LevelDB.
        """
        try:
            key = f"utxo:{tx_in.tx_out_id}".encode()
            stored_utxo = leveldb.Get(key)
            utxo_data = json.loads(stored_utxo.decode())
            if utxo_data.get("locked", False):
                raise ValueError(f"UTXO {tx_in.tx_out_id} is locked in LevelDB.")
        except KeyError:
            raise ValueError(f"Referenced UTXO {tx_in.tx_out_id} does not exist in LevelDB.")
        except Exception as e:
            raise ValueError(f"Error validating UTXO {tx_in.tx_out_id} in LevelDB: {e}")



    @staticmethod
    def from_dict(data: Dict):
        """
        Deserialize a Transaction from a dictionary.
        """
        if "tx_inputs" not in data or "tx_outputs" not in data:
            raise ValueError("Invalid data for Transaction: Missing required fields.")
        tx_inputs = [TransactionIn.from_dict(inp) for inp in data["tx_inputs"]]
        tx_outputs = [TransactionOut.from_dict(out) for out in data["tx_outputs"]]
        transaction = Transaction(tx_inputs, tx_outputs)
        transaction.timestamp = data["timestamp"]
        transaction.tx_id = data["tx_id"]
        return transaction

    def __str__(self):
        """
        String representation of the Transaction for debugging.
        """
        return str(self.to_dict())




