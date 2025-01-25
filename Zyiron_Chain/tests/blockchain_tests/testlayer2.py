import sys
import os

# Add the project root directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from Zyiron_Chain.offchain.multihop import MultiHop, NetworkGraph
from Zyiron_Chain.offchain.instantpay import PaymentChannel
from Zyiron_Chain.blockchain.utils.standardmempool import StandardMempool
from Zyiron_Chain.transactions.txout import UTXOManager
from Zyiron_Chain.offchain.dispute import DisputeResolutionContract
import time


import random
import string
import sys
import os




class MockTime:
    """
    A mock time provider for testing time-sensitive logic.
    """
    def __init__(self, start_time):
        self.current_time = start_time

    def time(self):
        return self.current_time

    def fast_forward(self, seconds):
        self.current_time += seconds


class DummyTransaction:
    def __init__(self, tx_id, parent_id, utxo_id, tx_inputs, tx_outputs, sender, recipient, amount, fee, size, timestamp):
        self.tx_id = tx_id
        self.parent_id = parent_id
        self.utxo_id = utxo_id
        self.tx_inputs = tx_inputs
        self.tx_outputs = tx_outputs
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.fee = fee
        self.size = size
        self.timestamp = timestamp

    @staticmethod
    def generate_dummy_transaction(transaction_type="Standard"):
        prefixes = {
            "Parent": "PID-",
            "Child": "CID-PID123-",
            "Instant": "I-",
            "Smart": "S-"
        }
        tx_id_prefix = prefixes.get(transaction_type, "")
        tx_id = tx_id_prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        utxo_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        sender = ''.join(random.choices(string.ascii_uppercase, k=5))
        recipient = ''.join(random.choices(string.ascii_uppercase, k=5))
        amount = random.randint(1, 100)
        fee = round(random.uniform(0.01, 0.1), 2)

        return DummyTransaction(
            tx_id=tx_id,
            parent_id=None if transaction_type != "Child" else "PID123",
            utxo_id=utxo_id,
            tx_inputs=[{"tx_out_id": utxo_id, "index": 0}],
            tx_outputs=[{"recipient": recipient, "amount": amount}],
            sender=sender,
            recipient=recipient,
            amount=amount,
            fee=fee,
            size=random.randint(200, 300),
            timestamp=time.time()
        )




def test_full_system_with_errors():
    print("\n=== Running Full System Tests with Error Injection ===")

    # Initialize mock time
    mock_time = MockTime(start_time=1670000000)

    # Initialize dependencies
    dispute_contract = DisputeResolutionContract(ttl=10)
    utxo_manager = UTXOManager()
    mempool_manager = StandardMempool(max_size_mb=10, timeout=10, expiry_time=20)

    # Initialize Payment Channel
    payment_channel = PaymentChannel(
        channel_id="channel_1",
        party_a="Alice",
        party_b="Bob",
        utxos={
            "UTXO-1": {"amount": 100, "locked": False},
            "UTXO-2": {"amount": 50, "locked": False},
        },
        wallet=None,
        network_prefix="ZYC",
        time_provider=mock_time.time,
        dispute_contract=dispute_contract,
        mempool_manager=mempool_manager,
        utxo_manager=utxo_manager
    )

    # Step 1: Open Channel
    print("\n--- Testing Payment Channel Initialization ---")
    try:
        payment_channel.open_channel()
        print("[SUCCESS] Channel opened successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to open channel: {e}")

    # Step 2: Test Random Dummy Transactions
    print("\n--- Testing Random Dummy Transactions ---")
    for i in range(5):
        transaction = DummyTransaction.generate_dummy_transaction()
        try:
            payment_channel.send_to_smart_contract(transaction)
            print(f"[SUCCESS] Dummy transaction {i + 1} processed: {transaction.__dict__}")
        except Exception as e:
            print(f"[ERROR] Dummy transaction {i + 1} failed: {vars(transaction)}, Error: {e}")
    # Step 3: HTLC Creation and Errors
    print("\n--- Testing HTLC Creation and Error Handling ---")
    try:
        htlc = payment_channel.create_htlc(
            payer="Alice",
            recipient="Bob",
            amount=10,
            sender_public_address="AlicePublicKey",
            utxo_id="UTXO-1",
            utxo_amount=10,
            block_size=1,
            tx_size=250,
            expiry=10
        )
        print("[SUCCESS] HTLC created successfully:", htlc)
    except Exception as e:
        print(f"[ERROR] Failed to create HTLC: {e}")

    # Step 4: Trigger Dispute Resolution
    print("\n--- Testing Dispute Resolution ---")
    try:
        mempool_manager.trigger_dispute("INVALID_TX", dispute_contract)
        print("[ERROR] Dispute resolution for invalid transaction should have failed.")
    except Exception as e:
        print(f"[EXPECTED ERROR] Dispute resolution error: {e}")

    # Step 5: Rebroadcast Transaction
    print("\n--- Testing Transaction Rebroadcast ---")
    try:
        mempool_manager.rebroadcast_transaction("I-12345", increment_factor=1.5, smart_contract=dispute_contract)
        print("[SUCCESS] Transaction rebroadcasted successfully.")
    except Exception as e:
        print(f"[ERROR] Rebroadcast failed: {e}")

    # Step 6: Handle HTLC Expiry and Refund
    print("\n--- Testing HTLC Expiry and Refund ---")
    mock_time.fast_forward(10)  # Move time forward beyond HTLC expiry
    try:
        refund_result = payment_channel.refund_expired_htlcs()
        print("[SUCCESS] HTLC refund processed:", refund_result)
    except Exception as e:
        print(f"[ERROR] HTLC refund failed: {e}")

    # Step 7: Close Channel
    print("\n--- Testing Channel Closure ---")
    try:
        payment_channel.close_channel()
        print("[SUCCESS] Channel closed successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to close channel: {e}")

    print("\n=== Full System Test with Errors Completed ===")


if __name__ == "__main__":
    print("\n=== Running Full System Validation with Errors ===")
    test_full_system_with_errors()
