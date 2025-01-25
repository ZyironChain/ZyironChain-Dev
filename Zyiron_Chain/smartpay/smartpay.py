import hashlib
import json
import time
from decimal import Decimal
from typing import Dict, Optional

class SmartTransaction:
    def __init__(
        self, tx_id: str, tx_inputs: list, tx_outputs: list, fee: float, block_height: Optional[int] = None
    ):
        if not tx_id.startswith("S-"):
            raise ValueError("Smart Transactions must start with 'S-' prefix.")

        self.tx_id = tx_id
        self.tx_inputs = tx_inputs
        self.tx_outputs = tx_outputs
        self.fee = Decimal(fee)
        self.block_height_at_lock = block_height  # Set when added to a block
        self.priority_flag = False  # Set to True if nearing 5-block limit

    def to_dict(self):
        return {
            "tx_id": self.tx_id,
            "tx_inputs": self.tx_inputs,
            "tx_outputs": self.tx_outputs,
            "fee": float(self.fee),
            "block_height_at_lock": self.block_height_at_lock,
            "priority_flag": self.priority_flag,
        }

    @staticmethod
    def from_dict(data):
        return SmartTransaction(
            tx_id=data["tx_id"],
            tx_inputs=data["tx_inputs"],
            tx_outputs=data["tx_outputs"],
            fee=data["fee"],
            block_height=data.get("block_height_at_lock"),
        )


class PaymentTypeManager:
    @staticmethod
    def validate_transaction_type(tx_id: str) -> str:
        if tx_id.startswith("PID-"):
            return "Parent"
        elif tx_id.startswith("CID-"):
            return "Child"
        elif tx_id.startswith("I-"):
            return "Instant"
        elif tx_id.startswith("S-"):
            return "Smart"
        else:
            raise ValueError("Invalid transaction prefix. Must be one of: PID-, CID-, I-, S-.")

    @staticmethod
    def create_smart_transaction(tx_id: str, tx_inputs: list, tx_outputs: list, fee: float) -> SmartTransaction:
        transaction_type = PaymentTypeManager.validate_transaction_type(tx_id)
        if transaction_type != "Smart":
            raise ValueError("Transaction ID does not correspond to a Smart Transaction.")

        return SmartTransaction(tx_id=tx_id, tx_inputs=tx_inputs, tx_outputs=tx_outputs, fee=fee)


# Example Usage
if __name__ == "__main__":
    tx_id = "S-12345678"
    tx_inputs = [{"tx_out_id": "UTXO1", "index": 0}]
    tx_outputs = [{"recipient": "Recipient1", "amount": 100.0}]
    fee = 0.05

    try:
        smart_tx = PaymentTypeManager.create_smart_transaction(tx_id, tx_inputs, tx_outputs, fee)
        print("Smart Transaction Created:", smart_tx.to_dict())
    except ValueError as e:
        print("Error:", e)
