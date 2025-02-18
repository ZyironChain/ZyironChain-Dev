import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


# transactions/utxo_manager.py
import logging
from decimal import Decimal
from typing import Dict, Optional
from Zyiron_Chain.transactions.txout import TransactionOut

logging.basicConfig(level=logging.INFO)

import logging
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.database.lmdatabase import LMDBManager

class UTXOManager:
    """Manages Unspent Transaction Outputs (UTXOs) with peer-specific LMDB storage."""

    def __init__(self, peer_id: str):
        """
        Initialize the UTXO Manager with a peer-specific LMDB database.

        :param peer_id: Unique identifier for the peer.
        """
        self.peer_id = peer_id
        self.lmdb = LMDBManager("utxo_{peer_id}.lmdb")  # ✅ Each peer has its own LMDB storage
        self._cache = {}  # ✅ Local cache for fast access

    def register_utxo(self, tx_out: TransactionOut):
        """
        Register a new UTXO in both the cache and LMDB.
        Prevents duplicate registration to maintain consistency.

        :param tx_out: The UTXO (TransactionOut) object to register.
        """
        if not isinstance(tx_out, TransactionOut):
            raise TypeError("[ERROR] Invalid UTXO type. Expected TransactionOut instance.")

        # ✅ Check if UTXO already exists in cache or LMDB before registering
        if tx_out.tx_out_id in self._cache or self.lmdb.get(tx_out.tx_out_id):
            logging.warning(f"[WARN] UTXO {tx_out.tx_out_id} already exists in peer {self.peer_id}. Skipping registration.")
            return

        utxo_data = tx_out.to_dict()
        self._cache[tx_out.tx_out_id] = utxo_data  # ✅ Store in local cache
        self.lmdb.put(tx_out.tx_out_id, utxo_data)  # ✅ Store in LMDB

        logging.info(f"[UTXO MANAGER] ✅ Peer {self.peer_id} registered UTXO: {tx_out.tx_out_id} | Amount: {tx_out.amount} | Locked: {tx_out.locked}")

    def get_utxo(self, tx_out_id: str) -> TransactionOut:
        """
        Retrieve a UTXO from the cache or LMDB storage.

        :param tx_out_id: The transaction output ID.
        :return: A TransactionOut instance or None if not found.
        """
        if tx_out_id in self._cache:
            return TransactionOut.from_dict(self._cache[tx_out_id])

        utxo_data = self.lmdb.get(tx_out_id)
        if not utxo_data:
            logging.warning(f"[WARNING] UTXO {tx_out_id} not found in peer {self.peer_id}'s LMDB.")
            return None  # ✅ Return None explicitly if not found

        self._cache[tx_out_id] = utxo_data  # ✅ Store in cache for future lookups
        return TransactionOut.from_dict(utxo_data)

    def delete_utxo(self, tx_out_id: str):
        """
        Delete a UTXO from LMDB and remove it from the cache.

        :param tx_out_id: The transaction output ID to delete.
        """
        if tx_out_id in self._cache:
            del self._cache[tx_out_id]

        self.lmdb.delete(tx_out_id)  # ✅ Remove from LMDB
        logging.info(f"[UTXO MANAGER] ❌ UTXO {tx_out_id} deleted from peer {self.peer_id}'s LMDB.")



    def convert_to_standard_transaction(self, tx_id, new_payment_type=None):
        """
        Convert a confirmed transaction into a Standard transaction by default.
        If sent again with a special payment type (Instant, Smart), update accordingly.

        :param tx_id: The transaction ID to convert.
        :param new_payment_type: Optional new payment type (e.g., "INSTANT", "SMART") if being sent again.
        :return: Updated transaction type.
        """
        with self.lock:
            # ✅ Retrieve transaction UTXO from LMDB
            utxo_data = self.lmdb.get(tx_id)
            if not utxo_data:
                logging.warning(f"[WARN] UTXO for transaction {tx_id} not found in LMDB. Cannot convert.")
                return None

            # ✅ Validate transaction type using Constants
            valid_types = list(Constants.TRANSACTION_MEMPOOL_MAP.keys())
            original_type = utxo_data.get("transaction_type", "STANDARD")

            if original_type not in valid_types:
                logging.warning(f"[WARN] Unknown transaction type {original_type} for {tx_id}. Defaulting to STANDARD.")
                original_type = "STANDARD"

            # ✅ Always convert confirmed transactions to STANDARD first
            utxo_data["transaction_type"] = "STANDARD"

            # ✅ If the transaction is being sent again with a special payment type, update it dynamically
            if new_payment_type in valid_types and new_payment_type != "COINBASE":
                utxo_data["transaction_type"] = new_payment_type
                logging.info(f"[INFO] Transaction {tx_id} reclassified as {new_payment_type} for new transfer.")

            # ✅ Update UTXO in LMDB
            self.lmdb.put(tx_id, utxo_data)
            logging.info(f"[INFO] Transaction {tx_id} converted from {original_type} to {utxo_data['transaction_type']}.")

        return utxo_data["transaction_type"]



    def update_from_block(self, block: Dict):
        """Update UTXO set from block transactions, ensuring proper validation."""
        if not isinstance(block, dict) or "transactions" not in block:
            logging.error("[ERROR] Invalid block format. Must contain 'transactions' key.")
            return

        # ✅ Process coinbase transaction first (ensure it's valid)
        coinbase = block["transactions"][0]
        if "outputs" in coinbase:
            for output in coinbase["outputs"]:
                tx_out = TransactionOut.from_dict(output)
                self.register_utxo(tx_out)

        # ✅ Process regular transactions
        for tx in block["transactions"][1:]:
            # ✅ Validate transaction structure
            if "outputs" not in tx or "inputs" not in tx:
                logging.warning(f"[WARNING] Skipping malformed transaction: {tx}")
                continue

            # ✅ Add new UTXO outputs
            for output in tx["outputs"]:
                tx_out = TransactionOut.from_dict(output)
                self.register_utxo(tx_out)

            # ✅ Remove spent UTXOs from LMDB
            for tx_input in tx["inputs"]:
                self.consume_utxo(tx_input["tx_out_id"])

    def consume_utxo(self, tx_out_id: str):
        """Mark UTXO as spent and remove it from LMDB storage ONLY if it exists."""
        utxo = self.get_utxo(tx_out_id)
        if not utxo:
            logging.warning(f"[WARNING] Attempted to consume non-existent UTXO {tx_out_id}")
            return  # ✅ Prevent removing an already non-existent UTXO

        # ✅ Remove from cache and LMDB
        if tx_out_id in self._cache:
            del self._cache[tx_out_id]

        self.lmdb.delete(tx_out_id)  # ✅ Use LMDB for decentralized storage
        logging.info(f"[UTXO MANAGER] ❌ Consumed UTXO: {tx_out_id} from LMDB.")


    def lock_utxo(self, tx_out_id: str):
        """Lock UTXO for transaction processing, ensuring LMDB consistency."""
        with self.lock:
            utxo = self.get_utxo(tx_out_id)
            if not utxo:
                logging.warning(f"[WARNING] Cannot lock non-existent UTXO: {tx_out_id}")
                return

            if utxo.locked:
                logging.warning(f"[WARNING] UTXO {tx_out_id} is already locked.")
                return

            utxo.locked = True
            self.lmdb.put(tx_out_id, utxo.to_dict())  # ✅ Ensure LMDB updates the lock status
            logging.info(f"[UTXO MANAGER] 🔒 Locked UTXO: {tx_out_id}")

    def unlock_utxo(self, tx_out_id: str):
        """Unlock UTXO after transaction processing, ensuring LMDB consistency."""
        with self.lock:
            utxo = self.get_utxo(tx_out_id)
            if not utxo:
                logging.warning(f"[WARNING] Cannot unlock non-existent UTXO: {tx_out_id}")
                return

            if not utxo.locked:
                logging.warning(f"[WARNING] UTXO {tx_out_id} is already unlocked.")
                return

            utxo.locked = False
            self.lmdb.put(tx_out_id, utxo.to_dict())  # ✅ Ensure LMDB updates the lock status
            logging.info(f"[UTXO MANAGER] 🔓 Unlocked UTXO: {tx_out_id}")

    def validate_utxo(self, tx_out_id: str, amount: Decimal) -> bool:
        """Validate UTXO for transaction spending while ensuring no negative fee calculation."""
        utxo = self.get_utxo(tx_out_id)

        # ✅ Ensure UTXO exists, is unlocked, and has enough balance
        if not utxo:
            logging.error(f"[ERROR] UTXO {tx_out_id} does not exist.")
            return False

        if utxo.locked:
            logging.error(f"[ERROR] UTXO {tx_out_id} is locked. Cannot be spent.")
            return False

        # ✅ Ensure the amount is never greater than UTXO balance
        utxo_amount = Decimal(str(utxo.amount))
        if utxo_amount < amount:
            logging.error(f"[ERROR] UTXO {tx_out_id} has insufficient balance. Required: {amount}, Available: {utxo.amount}")
            return False

        logging.info(f"[UTXO MANAGER] ✅ UTXO {tx_out_id} is valid for spending: Required {amount}, Available {utxo.amount}")
        return True
