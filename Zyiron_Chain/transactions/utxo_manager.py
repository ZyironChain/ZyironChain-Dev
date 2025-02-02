import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


# transactions/utxo_manager.py
import logging
from decimal import Decimal
from typing import Dict, Optional
from Zyiron_Chain.transactions.txout import TransactionOut

logging.basicConfig(level=logging.INFO)

class UTXOManager:
    """Manages Unspent Transaction Outputs with PoC integration"""
    def __init__(self, poc):
        self.poc = poc  # Proof-of-Contact layer
        self._cache = {}  # Local cache for fast access

    def register_utxo(self, tx_out: TransactionOut):
        """Register a new UTXO in both cache and PoC"""
        utxo_data = tx_out.to_dict()
        self._cache[tx_out.tx_out_id] = utxo_data
        self.poc.store_utxo(tx_out.tx_out_id, utxo_data)
        logging.info(f"Registered UTXO: {tx_out.tx_out_id}")

    def get_utxo(self, tx_out_id: str) -> Optional[TransactionOut]:
        """Retrieve UTXO from cache or PoC"""
        if tx_out_id in self._cache:
            return TransactionOut.from_dict(self._cache[tx_out_id])
        
        utxo_data = self.poc.get_utxo(tx_out_id)
        if utxo_data:
            self._cache[tx_out_id] = utxo_data
            return TransactionOut.from_dict(utxo_data)
        return None

    def update_from_block(self, block: Dict):
        """Update UTXO set from block transactions"""
        # Process coinbase transaction first
        coinbase = block["transactions"][0]
        for idx, output in enumerate(coinbase["outputs"]):
            tx_out = TransactionOut.from_dict(output)
            self.register_utxo(tx_out)

        # Process regular transactions
        for tx in block["transactions"][1:]:
            # Add new outputs
            for idx, output in enumerate(tx["outputs"]):
                tx_out = TransactionOut.from_dict(output)
                self.register_utxo(tx_out)

            # Remove spent inputs
            for tx_input in tx["inputs"]:
                self.consume_utxo(tx_input["tx_out_id"])

    def consume_utxo(self, tx_out_id: str):
        """Mark UTXO as spent and remove from system"""
        if tx_out_id in self._cache:
            del self._cache[tx_out_id]
        self.poc.delete_utxo(tx_out_id)
        logging.info(f"Consumed UTXO: {tx_out_id}")

    def lock_utxo(self, tx_out_id: str):
        """Lock UTXO for transaction processing"""
        if utxo := self.get_utxo(tx_out_id):
            utxo.locked = True
            self.poc.update_utxo(tx_out_id, utxo.to_dict())
            logging.info(f"Locked UTXO: {tx_out_id}")

    def unlock_utxo(self, tx_out_id: str):
        """Unlock UTXO after transaction processing"""
        if utxo := self.get_utxo(tx_out_id):
            utxo.locked = False
            self.poc.update_utxo(tx_out_id, utxo.to_dict())
            logging.info(f"Unlocked UTXO: {tx_out_id}")

    def validate_utxo(self, tx_out_id: str, amount: Decimal) -> bool:
        """Validate UTXO for transaction spending"""
        utxo = self.get_utxo(tx_out_id)
        return (
            utxo is not None and
            not utxo.locked and
            Decimal(str(utxo.amount)) >= amount
        )