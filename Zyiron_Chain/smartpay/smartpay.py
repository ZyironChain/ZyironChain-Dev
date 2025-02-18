import hashlib
import json
import time
from decimal import Decimal
from typing import Dict, List, Optional
from Zyiron_Chain.blockchain.constants import Constants
import logging

import logging
from decimal import Decimal
from typing import Dict, List, Optional
from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transactions.txin import TransactionIn
from Zyiron_Chain.transactions.txout import TransactionOut
from Zyiron_Chain.transactions.utxo_manager import UTXOManager

class SmartTransaction:
    """Represents a Smart Transaction with enhanced validation and priority handling."""

    def __init__(self, tx_id: str, inputs: List[Dict], outputs: List[Dict], fee: Decimal, utxo_manager: UTXOManager, block_height: Optional[int] = None):
        """
        Initialize a Smart Transaction.

        :param tx_id: Unique Smart Transaction ID.
        :param inputs: List of transaction inputs (UTXOs).
        :param outputs: List of transaction outputs (recipients).
        :param fee: Transaction fee.
        :param utxo_manager: Instance of UTXOManager for validation.
        :param block_height: Block height when transaction was locked (if applicable).
        """
        if not tx_id.startswith("S-"):
            raise ValueError("[ERROR] Smart Transactions must start with 'S-' prefix.")

        if not isinstance(fee, (float, Decimal)) or fee < Constants.MIN_TRANSACTION_FEE:
            raise ValueError(f"[ERROR] Transaction fee must be at least {Constants.MIN_TRANSACTION_FEE}.")

        # ✅ Ensure inputs and outputs are properly structured
        if not isinstance(inputs, list) or not all(isinstance(i, dict) for i in inputs):
            raise ValueError("[ERROR] Inputs must be a list of dictionaries.")

        if not isinstance(outputs, list) or not all(isinstance(o, dict) for o in outputs):
            raise ValueError("[ERROR] Outputs must be a list of dictionaries.")

        # ✅ Validate all inputs reference existing UTXOs
        for inp in inputs:
            if "tx_out_id" not in inp or not utxo_manager.validate_utxo(inp["tx_out_id"], Decimal(inp.get("amount", 0))):
                raise ValueError(f"[ERROR] Invalid or non-existent UTXO referenced in inputs: {inp}")

        self.tx_id = tx_id
        self.inputs = inputs
        self.outputs = outputs
        self.fee = Decimal(fee)
        self.utxo_manager = utxo_manager
        self.block_height_at_lock = block_height  # Set when added to a block
        self.priority_flag = False  # Set to True if nearing 5-block limit

        logging.info(f"[SMART TRANSACTION] ✅ Created Smart Transaction: {self.tx_id} | Fee: {self.fee}")

    def to_dict(self) -> Dict:
        """Serialize SmartTransaction to a dictionary format."""
        return {
            "tx_id": self.tx_id,
            "inputs": [inp for inp in self.inputs],
            "outputs": [out for out in self.outputs],
            "fee": str(self.fee),  # ✅ Ensure fee is stored as a string for precision
            "block_height_at_lock": self.block_height_at_lock,
            "priority_flag": self.priority_flag,
        }

    @staticmethod
    def from_dict(data: Dict, utxo_manager: UTXOManager) -> "SmartTransaction":
        """Create a SmartTransaction instance from a dictionary."""
        if not isinstance(data, dict):
            raise TypeError("[ERROR] Input data must be a dictionary.")

        required_fields = ["tx_id", "inputs", "outputs", "fee"]
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            raise KeyError(f"[ERROR] Missing required fields: {', '.join(missing_fields)}")

        return SmartTransaction(
            tx_id=data["tx_id"],
            inputs=data["inputs"],
            outputs=data["outputs"],
            fee=Decimal(str(data["fee"])),  # ✅ Ensure Decimal precision
            utxo_manager=utxo_manager,
            block_height=data.get("block_height_at_lock"),
        )

    def validate_transaction(self) -> bool:
        """Validate transaction format, UTXO references, and fee compliance."""
        if not self.tx_id.startswith("S-"):
            logging.error(f"[VALIDATION ERROR] ❌ Invalid Smart Transaction ID: {self.tx_id}")
            return False

        if not isinstance(self.fee, Decimal) or self.fee < Constants.MIN_TRANSACTION_FEE:
            logging.error(f"[VALIDATION ERROR] ❌ Fee too low for Smart Transaction: {self.tx_id}")
            return False

        # ✅ Ensure all inputs reference valid and unspent UTXOs
        for inp in self.inputs:
            if not self.utxo_manager.validate_utxo(inp["tx_out_id"], Decimal(inp.get("amount", 0))):
                logging.error(f"[VALIDATION ERROR] ❌ Invalid UTXO referenced: {inp}")
                return False

        # ✅ Ensure output values do not exceed input values (excluding fees)
        total_input = sum(Decimal(inp.get("amount", 0)) for inp in self.inputs)
        total_output = sum(Decimal(out.get("amount", 0)) for out in self.outputs)

        if total_output + self.fee > total_input:
            logging.error(f"[VALIDATION ERROR] ❌ Output sum exceeds input sum. Inputs: {total_input}, Outputs: {total_output}, Fee: {self.fee}")
            return False

        logging.info(f"[SMART TRANSACTION] ✅ Validation successful for {self.tx_id}")
        return True
