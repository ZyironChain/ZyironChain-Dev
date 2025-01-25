import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))






import hashlib
import time
import secrets

from Zyiron_Chain.blockchain.utils.standardmempool import StandardMempool
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.smartpay.smartmempool import SmartMempool
class PaymentChannel:
    def __init__(self, channel_id, party_a, party_b, utxos, wallet, network_prefix, time_provider=None, dispute_contract=None, mempool_manager=None, utxo_manager=None):
        self.channel_id = channel_id
        self.party_a = party_a
        self.party_b = party_b
        self.utxos = utxos
        self.wallet = wallet
        self.network_prefix = network_prefix
        self.time_provider = time_provider or time.time
        self.dispute_contract = dispute_contract
        self.mempool_manager = mempool_manager
        self.utxo_manager = utxo_manager
        self.is_open = False
        self.last_activity = self.time_provider()
        self.balances = {party_a: 0, party_b: 0}  # Initialize balances
        self.htlcs = []  # Initialize HTLC tracking


    def send_to_smart_contract(self, transaction):
        """
        Send a transaction to the smart contract for registration and locking.
        """
        try:
            # Register the transaction in the smart contract
            self.dispute_contract.register_transaction(
                transaction_id=transaction.tx_id,
                parent_id=transaction.parent_id,
                utxo_id=transaction.utxo_id,
                sender=transaction.sender,
                recipient=transaction.recipient,
                amount=transaction.amount,
                fee=transaction.fee
            )

            # Add transaction to the mempool with smart contract reference
            self.mempool_manager.add_transaction(transaction, smart_contract=self.dispute_contract)

            print(f"[INFO] Transaction {transaction.tx_id} sent to smart contract and added to mempool.")
        except AttributeError as e:
            print(f"[ERROR] Transaction object missing required attributes: {e}")
        except Exception as e:
            print(f"[ERROR] Failed to send transaction to smart contract: {e}")



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
            "timestamp": self.time_provider(),
            "resolved": False
        }

        # Lock the UTXO
        self.utxo_manager.lock_utxo(utxo_id)

        # Link to parent transaction
        if parent_id:
            self.transactions[parent_id]["child_ids"].append(transaction_id)

        print(f"Transaction {transaction_id} registered under parent {parent_id}, UTXO {utxo_id} locked.")



    def generate_random_pid(self):
        """
        Generate a randomized Parent Transaction ID (PID) for privacy.
        :return: Randomized PID string.
        """
        random_value = secrets.token_hex(8)  # Generate a random 8-byte value
        return f"PID-{random_value}"


    def instant_payment(self, payer, recipient, amount, block_size, tx_size):
        """
        Execute an instant payment in the channel.
        :param payer: Address of the payer.
        :param recipient: Address of the recipient.
        :param amount: Amount to transfer.
        :param block_size: Current block size in MB.
        :param tx_size: Size of the transaction in bytes.
        :return: Transaction details or an error if the payment fails.
        """
        if not self.is_open:
            raise Exception("Channel is closed.")

        if self.balances[payer] < amount:
            raise ValueError("Insufficient funds for the payment.")

        # Calculate the fee using the FeeModel for Instant Pay
        fee = self.fee_model.calculate_fee(
            block_size=block_size,
            payment_type="Instant",
            amount=amount,
            tx_size=tx_size
        )

        total_amount = amount + fee
        if self.balances[payer] < total_amount:
            raise ValueError(f"Insufficient funds to cover the payment and fee. Total required: {total_amount}.")

        # Deduct the amount and fee from the payer's balance
        self.balances[payer] -= total_amount

        # Add the amount to the recipient's balance
        self.balances[recipient] += amount

        # Create a transaction record
        transaction = {
            "payer": payer,
            "recipient": recipient,
            "amount": amount,
            "fee": fee,
            "timestamp": self.time_provider()
        }
        self.transactions.append(transaction)

        self.update_last_activity()

        return {
            "status": "Payment Successful",
            "transaction": transaction,
            "balances": self.balances
        }




    def update_last_activity(self):
        self.last_activity = self.time_provider()

    def update_last_activity(self):
        """
        Update the timestamp of the last activity.
        """
        self.last_activity = time.time()

    def open_channel(self):
        """
        Open the payment channel by delegating UTXO locking to the UTXOManager.
        """
        if self.is_open:
            raise Exception("Channel is already open.")

        for utxo_id in self.utxos:
            try:
                # Delegate locking to UTXOManager
                self.utxo_manager.lock_utxo(utxo_id, self.channel_id)
                print(f"[INFO] Locked UTXO {utxo_id} for channel {self.channel_id}.")
            except ValueError as e:
                print(f"[WARN] UTXO {utxo_id} is already locked. Skipping. Details: {e}")

        self.is_open = True
        print(f"[INFO] Channel {self.channel_id} successfully opened.")
        return {"status": "Channel Opened", "channel_id": self.channel_id}

    



    def check_inactivity(self, timeout_duration=2 * 60 * 60):
        """
        Check if the channel has been inactive for the specified timeout duration.
        :param timeout_duration: Inactivity duration in seconds.
        :return: True if the channel should be closed, False otherwise.
        """
        return self.time_provider() - self.last_activity > timeout_duration



    def refund_expired_htlcs(self):
        """
        Refund funds locked in expired HTLCs to the payer.
        """
        refunded_htlcs = []

        for htlc in self.htlcs:
            if not htlc["claimed"] and self.time_provider() > htlc["expiry"]:
                self.utxo_manager.unlock_utxo(htlc["locked_utxo"])
                self.balances[htlc["payer"]] += htlc["amount"]
                refunded_htlcs.append(htlc)

        print(f"[INFO] Refunded HTLCs: {refunded_htlcs}")
        return {"status": "Refunds Processed", "refunded_htlcs": refunded_htlcs}






    def generate_htlc_hashes(self, sender_public_address, utxo_amount):
        """
        Generate random number, single hash, and double hash for an HTLC.
        :param sender_public_address: The sender's public address.
        :param utxo_amount: Amount of UTXOs to include in the hash.
        :return: (random_number, single_hash, double_hash).
        """
        random_number = secrets.randbits(94)  # Generate a 94-bit random number
        timestamp = int(time.time())  # Transaction timestamp
        data = f"{random_number}:{timestamp}:{sender_public_address}:{utxo_amount}"
        single_hash = hashlib.sha3_384(data.encode()).hexdigest()  # Single hash
        double_hash = hashlib.sha3_384(single_hash.encode()).hexdigest()  # Double hash
        return random_number, single_hash, double_hash
    



    def register_transaction(self, transaction_id, parent_id, utxo_id, sender, recipient, amount, fee):
        """
        Register a transaction and track parent-child relationships.
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
            "timestamp": self.time_provider(),
            "resolved": False
        }

        # Lock the UTXO
        self.utxo_manager.lock_utxo(utxo_id)

        # Link to parent transaction
        if parent_id:
            self.transactions[parent_id]["child_ids"].append(transaction_id)

        print(f"Transaction {transaction_id} registered under parent {parent_id}, UTXO {utxo_id} locked.")


    def close_channel(self):
        """
        Close the payment channel and unlock UTXOs.
        """
        if not self.is_open:
            raise Exception("Channel is already closed.")

        self.is_open = False
        for utxo in self.utxos.values():
            utxo['locked'] = False

        return {
            "status": "Channel Closed",
            "final_balances": self.balances,
        }





    def claim_htlc(self, single_hash):
        """
        Claim funds from an HTLC using the single hash.
        """
        double_hash = hashlib.sha3_384(single_hash.encode()).hexdigest()

        for htlc in self.htlcs:
            if htlc["hash_secret"] == double_hash and not htlc["claimed"]:
                if self.time_provider() > htlc["expiry"]:
                    raise Exception("HTLC expired. Funds refunded to the payer.")

                # Unlock the UTXO
                self.utxo_manager.unlock_utxo(htlc["locked_utxo"])

                # Transfer funds to the recipient
                self.balances[htlc["recipient"]] += htlc["amount"]
                htlc["claimed"] = True

                self.update_last_activity()
                return {"status": "HTLC claimed successfully.", "htlc": htlc}

        raise Exception("Invalid or expired HTLC.")



    def create_htlc(self, payer, recipient, amount, sender_public_address, utxo_id, block_size, tx_size, **kwargs):
        """
        Create an HTLC for conditional payment with updated logic for dispute resolution, fee calculation, and tracking.
        """
        utxo_amount = kwargs.get("utxo_amount", amount)

        if not self.is_open:
            raise Exception("Channel is closed.")
        if self.balances.get(payer, 0) < amount:
            raise ValueError("Insufficient funds.")

        # Calculate the fee using the FeeModel for Instant Pay
        fee = self.fee_model.calculate_fee(
            block_size=block_size,
            payment_type="Instant",
            amount=amount,
            tx_size=tx_size
        )

        total_amount = amount + fee
        if self.balances[payer] < total_amount:
            raise ValueError(f"Insufficient funds to cover the HTLC and fee. Total required: {total_amount}.")

        # Lock the UTXO
        self.utxo_manager.lock_utxo(utxo_id, self.channel_id)
        print(f"[INFO] UTXO {utxo_id} locked for HTLC.")

        # Generate hashes for the HTLC
        random_number, single_hash, double_hash = self.generate_htlc_hashes(sender_public_address, utxo_amount)

        htlc = {
            "payer": payer,
            "recipient": recipient,
            "amount": amount,
            "fee": fee,
            "hash_secret": double_hash,
            "expiry": self.time_provider() + kwargs.get("expiry", 2 * 60 * 60),
            "locked_utxo": utxo_id,
            "claimed": False,
            "internal_data": {
                "random_number": random_number,
                "single_hash": single_hash
            }
        }

        self.balances[payer] -= total_amount
        self.htlcs.append(htlc)
        self.update_last_activity()

        print(f"[INFO] HTLC created: {htlc}")
        return htlc






    def adjust_fee(self, transaction_id):
        """
        Adjust the fee for a transaction using the base fee model.
        """
        if transaction_id not in self.transactions:
            raise ValueError("Transaction does not exist.")

        transaction = self.transactions[transaction_id]
        if transaction["resolved"]:
            raise ValueError("Transaction already resolved.")

        # Adjust fee
        base_fee = transaction["fee"]
        transaction["fee"] = base_fee + (base_fee * 0.10)

        print(f"Adjusted fee for transaction {transaction_id}: New Fee = {transaction['fee']}.")
        return transaction["fee"]




    def rebroadcast_transaction(self, transaction_id):
        """
        Rebroadcast a transaction with an adjusted fee.
        :param transaction_id: ID of the transaction to rebroadcast.
        """
        if transaction_id not in self.transactions:
            raise ValueError("Transaction does not exist.")

        transaction = self.transactions[transaction_id]
        if transaction["resolved"]:
            raise ValueError("Transaction already resolved.")

        # Adjust and rebroadcast
        new_fee = self.adjust_fee(transaction_id)
        print(f"Rebroadcasting transaction {transaction_id} with new fee: {new_fee}.")




    def finalize_parent(self, transaction_id):
        """
        Finalize a parent transaction and promote the last child transaction as the new parent with a new PID.
        :param transaction_id: Transaction ID of the parent.
        """
        if transaction_id not in self.transactions:
            raise ValueError("Transaction does not exist.")

        transaction = self.transactions[transaction_id]
        if transaction["resolved"]:
            raise ValueError("Transaction already resolved.")

        # Resolve the current parent transaction
        transaction["resolved"] = True

        # Promote the last child as the new parent
        if transaction["child_ids"]:
            last_child_id = transaction["child_ids"][-1]
            # Generate a new PID for the last child
            new_parent_id = self.generate_random_pid()
            self.transactions[last_child_id]["parent_id"] = None  # Clear parent reference
            self.transactions[last_child_id]["transaction_id"] = new_parent_id  # Update to new PID
            self.transactions[last_child_id]["child_ids"] = []  # Reset child tracking for the new parent

            print(f"Transaction {last_child_id} promoted as the new parent with ID {new_parent_id}.")
            return new_parent_id
        else:
            print(f"Transaction {transaction_id} finalized with no children.")
            return None
        



    def close_channel(self):
        """
        Close the payment channel and unlock all UTXOs.
        """
        if not self.is_open:
            raise Exception("Channel is already closed.")

        self.is_open = False
        for utxo_id in self.utxos:
            self.utxo_manager.unlock_utxo(utxo_id)

        print(f"[INFO] Channel {self.channel_id} closed.")
        return {"status": "Channel Closed", "balances": self.balances}