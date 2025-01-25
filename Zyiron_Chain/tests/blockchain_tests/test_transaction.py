import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))



from Zyiron_Chain.transactions.Blockchain_transaction import Transaction, TransactionIn, TransactionOut


def test_transaction_system():
    print("Starting Transaction System Test...")

    # Step 1: Create Transaction Outputs
    print("\nCreating transaction outputs...")
    tx_out1 = TransactionOut(recipient="address_1", amount=50.0)
    tx_out2 = TransactionOut(recipient="address_2", amount=25.0)
    print(f"TransactionOut 1: {tx_out1.to_dict()}")
    print(f"TransactionOut 2: {tx_out2.to_dict()}")

    # Step 2: Create Transaction Inputs
    print("\nCreating transaction inputs...")
    tx_in1 = TransactionIn(tx_out_id=tx_out1.tx_out_id, signature="signature_1")
    tx_in2 = TransactionIn(tx_out_id=tx_out2.tx_out_id, signature="signature_2")
    print(f"TransactionIn 1: {tx_in1.to_dict()}")
    print(f"TransactionIn 2: {tx_in2.to_dict()}")

    # Step 3: Create a Transaction
    print("\nCreating a transaction...")
    transaction = Transaction(tx_inputs=[tx_in1, tx_in2], tx_outputs=[tx_out1, tx_out2])
    print(f"Transaction: {transaction.to_dict()}")

    # Step 4: Serialize and Deserialize Transaction
    print("\nTesting serialization and deserialization...")
    serialized = transaction.to_dict()
    deserialized = Transaction.from_dict(serialized)
    print(f"Deserialized Transaction: {deserialized.to_dict()}")

    # Step 5: Validate Transaction ID Consistency
    print("\nValidating transaction ID consistency...")
    assert transaction.tx_id == deserialized.tx_id, "Transaction IDs do not match!"

    print("\nAll tests passed!")


if __name__ == "__main__":
    test_transaction_system()