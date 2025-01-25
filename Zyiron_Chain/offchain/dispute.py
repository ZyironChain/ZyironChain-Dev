import time
import hashlib

class DisputeResolutionContract:
    def __init__(self, ttl=3600):
        """
        Initialize the Dispute Resolution Contract.
        :param ttl: Time-to-live (in seconds) for transactions to be confirmed.
        """
        self.transactions = {}  # Store transaction details by transaction ID
        self.locked_utxos = {}  # Track locked UTXOs
        self.htlcs = {}  # Track HTLCs by hash_secret
        self.ttl = ttl  # Time-to-live for transactions

    def register_transaction(self, transaction_id, parent_id, utxo_id, sender, recipient, amount, fee):
        """
        Register a transaction and track parent-child relationships.
        :param transaction_id: Unique transaction ID.
        :param parent_id: ID of the parent transaction.
        :param utxo_id: ID of the UTXO locked in this transaction.
        :param sender: Address of the sender.
        :param recipient: Address of the recipient.
        :param amount: Amount to transfer.
        :param fee: Transaction fee.
        """
        if transaction_id in self.transactions:
            raise ValueError("Transaction already registered.")

        # Register the transaction
        self.transactions[transaction_id] = {
            "parent_id": parent_id,
            "child_ids": [],
            "utxo_id": utxo_id,
            "sender": sender,
            "recipient": recipient,
            "amount": amount,
            "fee": fee,
            "timestamp": time.time(),
            "resolved": False
        }

        # Lock the UTXO
        self.locked_utxos[utxo_id] = transaction_id

        # Link to parent transaction
        if parent_id:
            self.transactions[parent_id]["child_ids"].append(transaction_id)

        print(f"Transaction {transaction_id} registered and UTXO {utxo_id} locked.")

    def trigger_dispute(self, transaction_id):
        """
        Trigger a dispute for a transaction and its unresolved child transactions.
        :param transaction_id: Transaction ID to dispute.
        """
        if transaction_id not in self.transactions:
            raise ValueError("Transaction does not exist.")

        transaction = self.transactions[transaction_id]
        if transaction["resolved"]:
            raise ValueError("Transaction already resolved.")

        # Check if the TTL has expired
        if time.time() - transaction["timestamp"] < self.ttl:
            raise ValueError("Transaction still within TTL.")

        # Handle unresolved child transactions
        unresolved_children = [
            child_id for child_id in transaction["child_ids"]
            if not self.transactions[child_id]["resolved"]
        ]

        for child_id in unresolved_children:
            self.rebroadcast_transaction(child_id)

        print(f"Dispute triggered for transaction {transaction_id}.")
        return transaction

    def resolve_dispute(self, transaction_id):
        """
        Resolve a transaction dispute by finalizing or refunding the transaction.
        :param transaction_id: Transaction ID to resolve.
        """
        if transaction_id not in self.transactions:
            raise ValueError("Transaction does not exist.")

        transaction = self.transactions[transaction_id]
        if transaction["resolved"]:
            raise ValueError("Transaction already resolved.")

        # Finalize transaction
        transaction["resolved"] = True
        del self.locked_utxos[transaction["utxo_id"]]

        print(f"Transaction {transaction_id} resolved and funds transferred to {transaction['recipient']}.")
        return {"status": "Resolved", "transaction": transaction}

    def refund_transaction(self, transaction_id):
        """
        Refund a failed transaction and release its UTXO.
        :param transaction_id: Transaction ID to refund.
        """
        if transaction_id not in self.transactions:
            raise ValueError("Transaction does not exist.")

        transaction = self.transactions[transaction_id]
        if transaction["resolved"]:
            raise ValueError("Transaction already resolved.")

        # Check if the TTL has expired
        if time.time() - transaction["timestamp"] < self.ttl:
            raise ValueError("Transaction still within TTL.")

        # Refund the sender and unlock UTXO
        del self.locked_utxos[transaction["utxo_id"]]
        transaction["resolved"] = True

        print(f"Transaction {transaction_id} refunded. UTXO {transaction['utxo_id']} unlocked and funds returned to {transaction['sender']}.")
        return {"status": "Refunded", "transaction": transaction}

    def rebroadcast_transaction(self, transaction_id, increment_factor=1.5):
        """
        Rebroadcast a transaction with an increased fee.
        :param transaction_id: ID of the transaction to rebroadcast.
        :param increment_factor: Factor by which to increase the fee.
        """
        if transaction_id not in self.transactions:
            raise ValueError("Transaction does not exist.")

        transaction = self.transactions[transaction_id]
        if transaction["resolved"]:
            raise ValueError("Transaction already resolved.")

        # Increase the fee and simulate rebroadcast
        transaction["fee"] *= increment_factor
        print(f"Rebroadcasting transaction {transaction_id} with increased fee.")

    def rollback_to_parent(self, transaction_id):
        """
        Rollback UTXOs to the parent transaction state if a transaction fails.
        :param transaction_id: ID of the failed transaction.
        """
        if transaction_id not in self.transactions:
            raise ValueError("Transaction does not exist.")

        transaction = self.transactions[transaction_id]
        if "parent_id" not in transaction:
            raise ValueError("No parent transaction found for rollback.")

        parent_id = transaction["parent_id"]

        # Validate parent transaction state
        if parent_id not in self.transactions:
            raise ValueError("Parent transaction does not exist.")

        parent_transaction = self.transactions[parent_id]
        if not parent_transaction["resolved"]:
            raise ValueError("Parent transaction is not finalized.")

        # Unlock UTXOs and reallocate to the parent state
        self.locked_utxos[transaction["utxo_id"]] = parent_id
        transaction["resolved"] = True

        print(f"Transaction {transaction_id} failed. UTXOs reverted to parent transaction {parent_id}.")
        return {"status": "Rolled back", "parent_id": parent_id}
    

    
    def broadcast_to_mempool(self, transaction_id, recipient, fee):
        """
        Broadcast transaction metadata to the mempool.
        """
        # Prepare the payload for the mempool
        mempool_data = {
            "transaction_id": transaction_id,
            "recipient": recipient,
            "fee": fee
        }
        print(f"[INFO] Broadcasting transaction {transaction_id} to mempool: {mempool_data}")
        return mempool_data