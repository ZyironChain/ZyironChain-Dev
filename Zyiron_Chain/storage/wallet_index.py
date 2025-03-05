import os
import sys
import json
import threading
from decimal import Decimal
from typing import Optional, Dict, List

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.database.lmdatabase import LMDBManager

class WalletStorage:
    """
    WalletStorage manages wallet addresses and their associated UTXO index.
    
    Responsibilities:
      - Store and update wallet records in LMDB using wallet_index.lmdb.
      - Index wallet addresses using network-specific prefixes from Constants.
      - Allow retrieval of wallet data (balance and UTXOs) for fast balance queries.
      - All data is handled in bytes.
      - Uses detailed print statements for debugging and error reporting.
    """

    def __init__(self):
        try:
            db_path = Constants.DATABASES.get("wallet_index")
            if not db_path:
                raise ValueError("Wallet index database path not found in Constants.DATABASES.")
            self.wallet_db = LMDBManager(db_path)
            self._db_lock = threading.Lock()
            print(f"[WalletStorage.__init__] SUCCESS: Initialized WalletStorage with DB path '{db_path}'.")
        except Exception as e:
            print(f"[WalletStorage.__init__] ERROR: Failed to initialize WalletStorage: {e}")
            raise

    def store_wallet(self, wallet_address: str, balance: Decimal, utxos: Optional[List[dict]] = None) -> None:
        """
        Stores or updates a wallet record in LMDB.

        Args:
            wallet_address (str): The wallet address to store (must match network prefixes).
            balance (Decimal): The current wallet balance.
            utxos (Optional[List[dict]]): A list of UTXO dictionaries associated with the wallet.
        """
        try:
            accepted_prefixes = Constants.NETWORK_ADDRESS_PREFIXES.get(Constants.NETWORK, [])
            if not any(wallet_address.startswith(prefix) for prefix in accepted_prefixes):
                print(f"[WalletStorage.store_wallet] ERROR: Wallet address '{wallet_address}' does not start with accepted prefixes {accepted_prefixes}.")
                return

            record = {
                "wallet_address": wallet_address,
                "balance": str(balance),  # Store as string to preserve precision
                "utxos": utxos if utxos is not None else []
            }
            key = wallet_address.encode("utf-8")
            value = json.dumps(record).encode("utf-8")

            with self._db_lock:
                with self.wallet_db.env.begin(write=True) as txn:
                    txn.put(key, value, replace=True)

            print(f"[WalletStorage.store_wallet] SUCCESS: Stored/Updated wallet '{wallet_address}' with balance {balance}.")
        except Exception as e:
            print(f"[WalletStorage.store_wallet] ERROR: Failed to store wallet '{wallet_address}': {e}")
            raise

    def get_wallet(self, wallet_address: str) -> Optional[Dict]:
        """
        Retrieves a wallet record from LMDB.

        Args:
            wallet_address (str): The wallet address to retrieve.

        Returns:
            Optional[Dict]: The wallet record as a dictionary, or None if not found.
        """
        try:
            key = wallet_address.encode("utf-8")
            with self.wallet_db.env.begin() as txn:
                value = txn.get(key)
            if value:
                record = json.loads(value.decode("utf-8"))
                print(f"[WalletStorage.get_wallet] SUCCESS: Retrieved wallet '{wallet_address}'.")
                return record
            else:
                print(f"[WalletStorage.get_wallet] WARNING: Wallet '{wallet_address}' not found.")
                return None
        except Exception as e:
            print(f"[WalletStorage.get_wallet] ERROR: Failed to retrieve wallet '{wallet_address}': {e}")
            return None

    def update_wallet_balance(self, wallet_address: str, new_balance: Decimal) -> None:
        """
        Updates the balance of an existing wallet record.

        Args:
            wallet_address (str): The wallet address.
            new_balance (Decimal): The new balance.
        """
        try:
            record = self.get_wallet(wallet_address)
            if record is None:
                print(f"[WalletStorage.update_wallet_balance] ERROR: Wallet '{wallet_address}' not found.")
                return

            record["balance"] = str(new_balance)
            key = wallet_address.encode("utf-8")
            value = json.dumps(record).encode("utf-8")

            with self._db_lock:
                with self.wallet_db.env.begin(write=True) as txn:
                    txn.put(key, value, replace=True)
            print(f"[WalletStorage.update_wallet_balance] SUCCESS: Updated wallet '{wallet_address}' balance to {new_balance}.")
        except Exception as e:
            print(f"[WalletStorage.update_wallet_balance] ERROR: Failed to update wallet '{wallet_address}': {e}")
            raise

    def add_utxo_to_wallet(self, wallet_address: str, utxo: dict) -> None:
        """
        Adds a UTXO to the specified wallet's record.

        Args:
            wallet_address (str): The wallet address.
            utxo (dict): The UTXO data.
        """
        try:
            record = self.get_wallet(wallet_address)
            if record is None:
                print(f"[WalletStorage.add_utxo_to_wallet] ERROR: Wallet '{wallet_address}' not found.")
                return

            if "utxos" not in record or not isinstance(record["utxos"], list):
                record["utxos"] = []
            record["utxos"].append(utxo)
            key = wallet_address.encode("utf-8")
            value = json.dumps(record).encode("utf-8")
            with self._db_lock:
                with self.wallet_db.env.begin(write=True) as txn:
                    txn.put(key, value, replace=True)
            print(f"[WalletStorage.add_utxo_to_wallet] SUCCESS: Added UTXO to wallet '{wallet_address}'.")
        except Exception as e:
            print(f"[WalletStorage.add_utxo_to_wallet] ERROR: Failed to add UTXO to wallet '{wallet_address}': {e}")
            raise

    def remove_utxo_from_wallet(self, wallet_address: str, utxo_id: str) -> None:
        """
        Removes a specific UTXO from the wallet record.

        Args:
            wallet_address (str): The wallet address.
            utxo_id (str): The identifier of the UTXO to remove.
        """
        try:
            record = self.get_wallet(wallet_address)
            if record is None:
                print(f"[WalletStorage.remove_utxo_from_wallet] ERROR: Wallet '{wallet_address}' not found.")
                return

            if "utxos" in record and isinstance(record["utxos"], list):
                original_count = len(record["utxos"])
                record["utxos"] = [u for u in record["utxos"] if u.get("tx_out_id") != utxo_id]
                updated_count = len(record["utxos"])
                key = wallet_address.encode("utf-8")
                value = json.dumps(record).encode("utf-8")
                with self._db_lock:
                    with self.wallet_db.env.begin(write=True) as txn:
                        txn.put(key, value, replace=True)
                print(f"[WalletStorage.remove_utxo_from_wallet] SUCCESS: Removed UTXO '{utxo_id}' from wallet '{wallet_address}'. (Count: {original_count} -> {updated_count})")
            else:
                print(f"[WalletStorage.remove_utxo_from_wallet] WARNING: Wallet '{wallet_address}' has no UTXO list.")
        except Exception as e:
            print(f"[WalletStorage.remove_utxo_from_wallet] ERROR: Failed to remove UTXO from wallet '{wallet_address}': {e}")
            raise

    def get_all_wallets(self) -> List[Dict]:
        """
        Retrieves all wallet records from the wallet index.

        Returns:
            List[Dict]: A list of wallet records.
        """
        wallets = []
        try:
            with self.wallet_db.env.begin() as txn:
                cursor = txn.cursor()
                for key, value in cursor:
                    try:
                        record = json.loads(value.decode("utf-8"))
                        wallets.append(record)
                    except Exception as e:
                        print(f"[WalletStorage.get_all_wallets] ERROR: Failed to decode record for key {key}: {e}")
                        continue
            print(f"[WalletStorage.get_all_wallets] SUCCESS: Retrieved {len(wallets)} wallet records.")
            return wallets
        except Exception as e:
            print(f"[WalletStorage.get_all_wallets] ERROR: Failed to retrieve wallet records: {e}")
            return []
