import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))





from decimal import Decimal
import hashlib
import time
import secrets
from Zyiron_Chain.offchain.zkp import ZKP
from Zyiron_Chain.blockchain.utils.standardmempool import StandardMempool
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.smartpay.smartmempool import SmartMempool
import logging
from Zyiron_Chain.blockchain.constants import Constants

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
        required_attributes = ["tx_id", "parent_id", "utxo_id", "sender", "recipient", "amount", "fee"]

        # ✅ Validate all required transaction attributes
        for attr in required_attributes:
            if not hasattr(transaction, attr):
                print(f"[ERROR] Transaction is missing required attribute: {attr}")
                return

        try:
            # ✅ Check if the dispute contract is available
            if not self.dispute_contract:
                print("[ERROR] Dispute contract is not initialized.")
                return

            # ✅ Register the transaction in the smart contract
            self.dispute_contract.register_transaction(
                transaction_id=transaction.tx_id,
                parent_id=transaction.parent_id,
                utxo_id=transaction.utxo_id,
                sender=transaction.sender,
                recipient=transaction.recipient,
                amount=transaction.amount,
                fee=transaction.fee
            )

            # ✅ Ensure the mempool manager is ready
            if not self.mempool_manager:
                print("[ERROR] Mempool manager is not initialized.")
                return

            # ✅ Check if the transaction is already in the mempool
            if self.mempool_manager.has_transaction(transaction.tx_id):
                print(f"[WARN] Transaction {transaction.tx_id} is already in the mempool.")
                return

            # ✅ Add transaction to the mempool
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
        if not all([transaction_id, utxo_id, sender, recipient, amount, fee is not None]):
            raise ValueError("[ERROR] Missing one or more required parameters.")

        if transaction_id in self.transactions:
            raise ValueError("[ERROR] Transaction already registered.")

        # Validate parent transaction
        if parent_id and parent_id not in self.transactions:
            raise ValueError(f"[ERROR] Parent transaction {parent_id} does not exist.")

        # Check UTXO availability before locking
        if not self.utxo_manager.validate_utxo(utxo_id, amount):
            raise ValueError(f"[ERROR] UTXO {utxo_id} is either locked or does not exist.")

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

        print(f"[INFO] Transaction {transaction_id} registered under parent {parent_id}, UTXO {utxo_id} locked.")




    def generate_random_pid(self):
        """
        Generate a randomized Parent Transaction ID (PID) for privacy.
        :return: Randomized PID string.
        """
        try:
            random_value = secrets.token_hex(8)  # Generate a random 8-byte value
            return f"PID-{random_value}"
        except Exception as e:
            logging.error(f"[ERROR] Failed to generate random PID: {e}")
            raise ValueError("Unable to generate random PID. Please try again.")

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
        # ✅ Check if the channel is open
        if not self.is_open:
            logging.error("[ERROR] Channel is closed.")
            raise Exception("Channel is closed.")

        # ✅ Validate payer and recipient balances
        if payer not in self.balances:
            logging.error(f"[ERROR] Payer {payer} does not exist in balances.")
            raise ValueError("Payer does not exist in the channel.")

        if recipient not in self.balances:
            logging.error(f"[ERROR] Recipient {recipient} does not exist in balances.")
            raise ValueError("Recipient does not exist in the channel.")

        if amount <= 0:
            logging.error(f"[ERROR] Invalid amount {amount}. Must be greater than zero.")
            raise ValueError("Amount must be greater than zero.")

        # ✅ Ensure payer has sufficient balance
        if self.balances[payer] < amount:
            logging.error(f"[ERROR] Insufficient funds. Payer balance: {self.balances[payer]}, Amount: {amount}")
            raise ValueError("Insufficient funds for the payment.")

        # ✅ Calculate the fee using FeeModel
        try:
            fee = self.fee_model.calculate_fee(
                block_size=block_size,
                payment_type="Instant",
                amount=amount,
                tx_size=tx_size
            )
        except Exception as e:
            logging.error(f"[ERROR] Fee calculation failed: {e}")
            raise ValueError("Failed to calculate transaction fee.")

        total_amount = amount + fee

        # ✅ Ensure payer has sufficient balance for amount + fee
        if self.balances[payer] < total_amount:
            logging.error(f"[ERROR] Insufficient funds to cover payment and fee. Required: {total_amount}, Available: {self.balances[payer]}")
            raise ValueError(f"Insufficient funds to cover the payment and fee. Total required: {total_amount}.")

        # ✅ Deduct amount and fee from payer, add amount to recipient
        self.balances[payer] -= total_amount
        self.balances[recipient] += amount

        # ✅ Record the transaction
        transaction = {
            "payer": payer,
            "recipient": recipient,
            "amount": amount,
            "fee": fee,
            "timestamp": self.time_provider()
        }
        self.transactions.append(transaction)

        # ✅ Update last activity
        self.update_last_activity()

        logging.info(f"[INFO] Instant payment completed. Payer: {payer}, Recipient: {recipient}, Amount: {amount}, Fee: {fee}")

        return {
            "status": "Payment Successful",
            "transaction": transaction,
            "balances": self.balances
        }


    def update_last_activity(self):
        """
        Update the timestamp of the last activity using the time provider.
        """
        self.last_activity = self.time_provider()

    def open_channel(self):
        """
        Open the payment channel by delegating UTXO locking to the UTXOManager.
        """
        # ✅ Ensure the channel is not already open
        if self.is_open:
            raise Exception("[ERROR] Channel is already open.")

        # ✅ Validate that utxo_manager is initialized
        if not self.utxo_manager:
            raise ValueError("[ERROR] UTXOManager is not initialized.")

        # ✅ Check that utxos list is not empty
        if not self.utxos:
            raise ValueError("[ERROR] No UTXOs provided to open the channel.")

        # ✅ Attempt to lock each UTXO
        failed_utxos = []
        for utxo_id in self.utxos:
            try:
                # Delegate locking to UTXOManager
                self.utxo_manager.lock_utxo(utxo_id, self.channel_id)
                print(f"[INFO] Locked UTXO {utxo_id} for channel {self.channel_id}.")
            except ValueError as e:
                failed_utxos.append(utxo_id)
                print(f"[WARN] UTXO {utxo_id} could not be locked. Details: {e}")

        # ✅ Check if any UTXOs failed to lock
        if failed_utxos:
            print(f"[ERROR] Failed to lock the following UTXOs: {failed_utxos}")
            return {"status": "Failed to Lock UTXOs", "failed_utxos": failed_utxos}

        # ✅ Mark the channel as open and return success
        self.is_open = True
        print(f"[INFO] Channel {self.channel_id} successfully opened.")
        return {"status": "Channel Opened", "channel_id": self.channel_id}


    



    def check_inactivity(self, timeout_duration=None):
        """
        Check if the channel has been inactive for the specified timeout duration.
        :param timeout_duration: Inactivity duration in seconds. Defaults to PAYMENT_CHANNEL_INACTIVITY_TIMEOUT.
        :return: True if the channel should be closed, False otherwise.
        """
        timeout_duration = timeout_duration or Constants.PAYMENT_CHANNEL_INACTIVITY_TIMEOUT

        if timeout_duration <= 0:
            raise ValueError("[ERROR] Timeout duration must be positive.")

        if not isinstance(self.last_activity, (int, float)):
            raise ValueError("[ERROR] last_activity is not properly initialized.")

        try:
            current_time = self.time_provider()
        except Exception as e:
            raise RuntimeError(f"[ERROR] Failed to retrieve current time from time_provider: {e}")

        return current_time - self.last_activity > timeout_duration

    def refund_expired_htlcs(self):
        """
        Refund funds locked in expired HTLCs to the payer.
        """
        if not isinstance(self.htlcs, list):
            raise ValueError("[ERROR] HTLCs are not properly initialized or are not a list.")

        if not self.utxo_manager:
            raise ValueError("[ERROR] UTXOManager is not initialized.")

        if not self.balances or not isinstance(self.balances, dict):
            raise ValueError("[ERROR] Balances are not properly initialized or are not a dictionary.")

        refunded_htlcs = []

        for htlc in self.htlcs:
            if not isinstance(htlc, dict) or not all(k in htlc for k in ["claimed", "expiry", "locked_utxo", "payer", "amount"]):
                print(f"[WARN] Skipping malformed HTLC entry: {htlc}")
                continue

            if not htlc["claimed"] and self.time_provider() > htlc["expiry"]:
                try:
                    self.utxo_manager.unlock_utxo(htlc["locked_utxo"])
                    self.balances[htlc["payer"]] += htlc["amount"]
                    refunded_htlcs.append(htlc)
                except Exception as e:
                    print(f"[ERROR] Failed to refund HTLC {htlc}: {e}")

        print(f"[INFO] Refunded HTLCs: {refunded_htlcs}")
        return {"status": "Refunds Processed", "refunded_htlcs": refunded_htlcs}




    def generate_htlc_hashes(self, sender_public_address, utxo_amount):
        """
        Generate random number, single hash, and double hash for an HTLC.
        :param sender_public_address: The sender's public address.
        :param utxo_amount: Amount of UTXOs to include in the hash.
        :return: (random_number, single_hash, double_hash).
        """
        if not sender_public_address or not isinstance(sender_public_address, str):
            raise ValueError("[ERROR] Sender public address must be a non-empty string.")
        
        if not isinstance(utxo_amount, (int, float)) or utxo_amount <= 0:
            raise ValueError("[ERROR] UTXO amount must be a positive number.")
        
        try:
            random_number = secrets.randbits(94)  # Generate a 94-bit random number
            timestamp = int(time.time())  # Transaction timestamp
            data = f"{random_number}:{timestamp}:{sender_public_address}:{utxo_amount}"
            single_hash = hashlib.sha3_384(data.encode()).hexdigest()  # Single hash
            double_hash = hashlib.sha3_384(single_hash.encode()).hexdigest()  # Double hash
        except Exception as e:
            raise RuntimeError(f"[ERROR] Failed to generate HTLC hashes: {e}")
        
        return random_number, single_hash, double_hash

    def register_transaction(self, transaction_id, parent_id, utxo_id, sender, recipient, amount, fee, zk_commitment):
        """
        Register a transaction and track parent-child relationships.
        :param zk_commitment: The ZKP commitment of the transaction.
        """
        if transaction_id in self.transactions:
            raise ValueError("[ERROR] Transaction already registered.")

        if not zk_commitment or not isinstance(zk_commitment, str):
            raise ValueError("[ERROR] zk_commitment must be a non-empty string.")

        if amount < 0 or fee < 0:
            raise ValueError("[ERROR] Amount and fee must be non-negative values.")

        if parent_id and parent_id not in self.transactions:
            raise ValueError(f"[ERROR] Parent transaction {parent_id} does not exist.")
        
        try:
            # Register the transaction
            self.transactions[transaction_id] = {
                "parent_id": parent_id,
                "child_ids": [],
                "utxo_id": utxo_id,
                "sender": sender,
                "recipient": recipient,
                "amount": amount,
                "fee": fee,
                "zk_commitment": zk_commitment,  # Store ZKP commitment
                "timestamp": self.time_provider(),
                "resolved": False
            }

            # Lock the UTXO
            self.utxo_manager.lock_utxo(utxo_id)

            # Link to parent transaction
            if parent_id:
                self.transactions[parent_id]["child_ids"].append(transaction_id)

            print(f"[INFO] Transaction {transaction_id} registered with ZKP commitment {zk_commitment}, UTXO {utxo_id} locked.")
        
        except Exception as e:
            raise RuntimeError(f"[ERROR] Failed to register transaction {transaction_id}: {e}")





    def claim_htlc(self, zk_proof):
        """
        Claim funds from an HTLC using a Zero-Knowledge Proof (ZKP).
        """
        if not zk_proof or not isinstance(zk_proof, dict):
            raise ValueError("[ERROR] ZK Proof must be a valid dictionary.")

        zk_proof_system = ZKP()

        for htlc in self.htlcs:
            if not htlc["claimed"]:
                # Verify the ZKP proof instead of checking single_hash
                if zk_proof_system.verify_proof(zk_proof, htlc["internal_data"]["single_hash"]):
                    # Unlock the UTXO and release funds
                    self.utxo_manager.unlock_utxo(htlc["locked_utxo"])
                    self.balances[htlc["recipient"]] += htlc["amount"]
                    htlc["claimed"] = True
                    htlc["zkp_verified"] = True  # Mark ZKP verification as passed

                    print(f"[INFO] HTLC claimed successfully using ZKP. Funds transferred to {htlc['recipient']}.")
                    return {"status": "HTLC claimed successfully.", "htlc": htlc}

        raise Exception("[ERROR] Invalid or expired HTLC.")

    def create_htlc(self, payer, recipient, amount, sender_public_address, utxo_id, block_size, tx_size, **kwargs):
        """
        Create an HTLC for conditional payment using Zero-Knowledge Proofs (ZKP).
        """
        utxo_amount = kwargs.get("utxo_amount", amount)

        if not self.is_open:
            raise Exception("[ERROR] Channel is closed.")
        
        if payer not in self.balances or self.balances[payer] < amount:
            raise ValueError("[ERROR] Insufficient funds.")

        if amount <= 0:
            raise ValueError("[ERROR] Amount must be positive.")

        # Calculate the fee using the FeeModel for Instant Pay
        try:
            fee = self.fee_model.calculate_fee(
                block_size=block_size,
                payment_type="Instant",
                amount=amount,
                tx_size=tx_size
            )
        except Exception as e:
            raise RuntimeError(f"[ERROR] Fee calculation failed: {e}")

        total_amount = amount + fee

        if self.balances[payer] < total_amount:
            raise ValueError(f"[ERROR] Insufficient funds to cover the HTLC and fee. Total required: {total_amount}.")

        # Lock the UTXO
        try:
            self.utxo_manager.lock_utxo(utxo_id, self.channel_id)
            print(f"[INFO] UTXO {utxo_id} locked for HTLC.")
        except Exception as e:
            raise RuntimeError(f"[ERROR] Failed to lock UTXO {utxo_id}: {e}")

        # Generate hashes for the HTLC
        try:
            random_number, single_hash, double_hash = self.generate_htlc_hashes(sender_public_address, utxo_amount)
        except Exception as e:
            raise RuntimeError(f"[ERROR] Failed to generate HTLC hashes: {e}")

        # Generate the Zero-Knowledge Proof
        try:
            zkp_proof = self.generate_zkp_proof(single_hash, double_hash)
        except Exception as e:
            raise RuntimeError(f"[ERROR] Failed to generate ZKP proof: {e}")

        htlc = {
            "payer": payer,
            "recipient": recipient,
            "amount": amount,
            "fee": fee,
            "double_hash": double_hash,  # Store only `double_hash` on-chain
            "zkp_proof": zkp_proof,  # Store the ZKP proof instead of `single_hash`
            "expiry": self.time_provider() + kwargs.get("expiry", Constants.HTLC_EXPIRY_TIME),
            "locked_utxo": utxo_id,
            "claimed": False,
            "internal_data": {
                "random_number": random_number,  # Still stored internally
                "single_hash": single_hash  # Still stored internally, but never on-chain
            }
        }

        self.balances[payer] -= total_amount
        self.htlcs.append(htlc)
        self.update_last_activity()

        print(f"[INFO] ZKP-based HTLC created: {htlc}")
        return htlc








    def adjust_fee(self, transaction_id):
        """
        Adjust the fee for a transaction using the base fee model.
        """
        if not transaction_id or not isinstance(transaction_id, str):
            raise ValueError("[ERROR] Transaction ID must be a non-empty string.")

        if transaction_id not in self.transactions:
            raise ValueError("[ERROR] Transaction does not exist.")

        transaction = self.transactions[transaction_id]

        if "fee" not in transaction or not isinstance(transaction["fee"], (int, float, Decimal)):
            raise ValueError("[ERROR] Transaction fee is missing or invalid.")

        if transaction["resolved"]:
            raise ValueError("[ERROR] Transaction already resolved.")

        # Adjust fee
        base_fee = transaction["fee"]
        new_fee = base_fee + (base_fee * Decimal("0.10"))
        transaction["fee"] = new_fee

        print(f"[INFO] Adjusted fee for transaction {transaction_id}: New Fee = {transaction['fee']}.")
        return transaction["fee"]

    def rebroadcast_transaction(self, transaction_id):
        """
        Rebroadcast a transaction with an adjusted fee.
        :param transaction_id: ID of the transaction to rebroadcast.
        """
        if not transaction_id or not isinstance(transaction_id, str):
            raise ValueError("[ERROR] Transaction ID must be a non-empty string.")

        if transaction_id not in self.transactions:
            raise ValueError("[ERROR] Transaction does not exist.")

        transaction = self.transactions[transaction_id]

        if transaction.get("resolved"):
            raise ValueError("[ERROR] Transaction already resolved.")

        # Adjust and rebroadcast
        try:
            new_fee = self.adjust_fee(transaction_id)
            print(f"[INFO] Rebroadcasting transaction {transaction_id} with new fee: {new_fee}.")
        except Exception as e:
            raise RuntimeError(f"[ERROR] Failed to rebroadcast transaction {transaction_id}: {e}")


    def finalize_parent(self, transaction_id):
        """
        Finalize a parent transaction and promote the last child transaction as the new parent with a new PID.
        :param transaction_id: Transaction ID of the parent.
        """
        if not transaction_id or not isinstance(transaction_id, str):
            raise ValueError("[ERROR] Transaction ID must be a non-empty string.")

        if transaction_id not in self.transactions:
            raise ValueError("[ERROR] Transaction does not exist.")

        transaction = self.transactions[transaction_id]

        if transaction.get("resolved"):
            raise ValueError("[ERROR] Transaction already resolved.")

        # Resolve the current parent transaction
        transaction["resolved"] = True

        # Promote the last child as the new parent
        if "child_ids" in transaction and transaction["child_ids"]:
            last_child_id = transaction["child_ids"][-1]

            if last_child_id not in self.transactions:
                raise ValueError(f"[ERROR] Last child transaction {last_child_id} does not exist.")

            # Generate a new PID for the last child
            new_parent_id = self.generate_random_pid()
            child_transaction = self.transactions[last_child_id]
            child_transaction["parent_id"] = None  # Clear parent reference
            child_transaction["transaction_id"] = new_parent_id  # Update to new PID
            child_transaction["child_ids"] = []  # Reset child tracking for the new parent

            print(f"[INFO] Transaction {last_child_id} promoted as the new parent with ID {new_parent_id}.")
            return new_parent_id
        else:
            print(f"[INFO] Transaction {transaction_id} finalized with no children.")
            return None

    def close_channel(self):
        """
        Close the payment channel and unlock all UTXOs.
        """
        if not self.is_open:
            raise Exception("[ERROR] Channel is already closed.")

        self.is_open = False

        if not self.utxos:
            print(f"[INFO] No UTXOs to unlock for channel {self.channel_id}.")
        else:
            for utxo_id in self.utxos:
                try:
                    self.utxo_manager.unlock_utxo(utxo_id)
                except Exception as e:
                    print(f"[WARN] Failed to unlock UTXO {utxo_id}: {e}")

        print(f"[INFO] Channel {self.channel_id} closed.")
        return {"status": "Channel Closed", "balances": self.balances}

