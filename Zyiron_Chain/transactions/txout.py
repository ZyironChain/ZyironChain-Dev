import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)


import hashlib
import time
from typing import List, Dict

import json  

from decimal import Decimal



import json
import logging
from Zyiron_Chain.transactions.transactiontype import TransactionType
from BTrees.OOBTree import OOBTree # type: ignore
from decimal import Decimal
import hashlib
logging.basicConfig(level=logging.INFO)

class TransactionOut:
    """
    Represents a transaction output.
    """
    def __init__(self, script_pub_key: str, amount: float, locked: bool = False):
        self.script_pub_key = script_pub_key  # Script that locks the output
        self.amount = amount  # Amount of the output
        self.locked = locked  # Whether the UTXO is locked or not
        self.tx_out_id = self.calculate_tx_out_id()

    def calculate_tx_out_id(self) -> str:
        """
        Calculate the unique transaction output ID.
        """
        tx_out_data = f"{self.script_pub_key}{self.amount}{self.locked}"
        return hashlib.sha3_384(tx_out_data.encode()).hexdigest()

    def to_dict(self) -> Dict:
        """
        Serialize the TransactionOut to a dictionary.
        """
        return {
            "script_pub_key": self.script_pub_key,
            "amount": self.amount,
            "locked": self.locked,
            "tx_out_id": self.tx_out_id,
        }

    @staticmethod
    def from_dict(data: Dict):
        """
        Deserialize a TransactionOut from a dictionary.
        """
        return TransactionOut(
            script_pub_key=data["script_pub_key"],
            amount=data["amount"],
            locked=data.get("locked", False),
        )



import logging

logging.basicConfig(level=logging.INFO)

class UTXOManager:
    def __init__(self, poc):
        """
        Initialize the UTXO Manager with PoC for handling UTXO routing.
        """
        self.poc = poc  # Pass PoC for routing
        self.utxos = {}  # Dictionary to store UTXOs

    def register_utxo(self, tx_out_id, utxo_data):
        """
        Register a new UTXO (Unspent Transaction Output).
        :param tx_out_id: The ID of the transaction output.
        :param utxo_data: The UTXO data to register.
        """
        if tx_out_id in self.utxos:
            logging.warning(f"[WARN] UTXO {tx_out_id} already exists.")
            return

        self.utxos[tx_out_id] = utxo_data
        logging.info(f"[INFO] Registered UTXO: {tx_out_id}")

    def get_utxo(self, tx_out_id):
        """
        Retrieve a UTXO by its ID.
        :param tx_out_id: The ID of the transaction output.
        :return: The UTXO if found, otherwise None.
        """
        return self.utxos.get(tx_out_id)

    def is_utxo_valid(self, tx_out_id):
        """
        Verify if a UTXO exists and is unlocked.
        :param tx_out_id: The ID of the transaction output.
        :return: True if the UTXO is valid, otherwise False.
        """
        utxo = self.get_utxo(tx_out_id)
        return utxo is not None and not utxo.get("locked", False)

    def consume_utxo(self, tx_out_id):
        """
        Mark a UTXO as consumed.
        :param tx_out_id: The ID of the transaction output.
        """
        if tx_out_id in self.utxos:
            del self.utxos[tx_out_id]
            logging.info(f"[INFO] Consumed UTXO: {tx_out_id}")
        else:
            logging.error(f"[ERROR] UTXO {tx_out_id} does not exist.")

    def lock_utxo(self, tx_out_id):
        """
        Lock a UTXO.
        :param tx_out_id: The ID of the transaction output.
        """
        utxo = self.get_utxo(tx_out_id)
        if utxo:
            utxo["locked"] = True
            logging.info(f"[INFO] Locked UTXO: {tx_out_id}")
        else:
            logging.error(f"[ERROR] UTXO {tx_out_id} does not exist.")

    def unlock_utxo(self, tx_out_id):
        """
        Unlock a UTXO.
        :param tx_out_id: The ID of the transaction output.
        """
        utxo = self.get_utxo(tx_out_id)
        if utxo:
            utxo["locked"] = False
            logging.info(f"[INFO] Unlocked UTXO: {tx_out_id}")
        else:
            logging.error(f"[ERROR] UTXO {tx_out_id} does not exist.")

    def get_all_utxos(self):
        """
        Retrieve all UTXOs.
        :return: A dictionary of all UTXOs.
        """
        return self.utxos

    def clear(self):
        """
        Clear all UTXOs.
        """
        self.utxos.clear()
        logging.info("[INFO] Cleared all UTXOs.")

    def update_from_block(self, block):
        """
        Update the UTXO set based on the transactions in the block.
        :param block: The block containing transactions to update the UTXO set.
        """
        for tx in block.transactions:
            if isinstance(tx, dict):  # Skip coinbase transaction
                continue

            # Add transaction outputs to UTXOs
            for index, output in enumerate(tx.get("tx_outputs", [])):
                utxo_key = f"{tx['tx_id']}:{index}"
                self.utxos[utxo_key] = output

            # Remove transaction inputs from UTXOs
            for tx_input in tx.get("tx_inputs", []):
                spent_utxo_key = f"{tx_input['tx_out_id']}:{tx_input['index']}"
                if spent_utxo_key in self.utxos:
                    del self.utxos[spent_utxo_key]
                    logging.info(f"[INFO] Consumed UTXO: {spent_utxo_key}")