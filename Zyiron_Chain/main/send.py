from decimal import Decimal
from typing import Optional, List, Dict, Union

from Zyiron_Chain.blockchain.constants import Constants
from Zyiron_Chain.transaction.tx import Transaction
from Zyiron_Chain.transaction.coinbase import CoinbaseTx
from Zyiron_Chain.transaction.txin import TransactionIn
from Zyiron_Chain.transaction.txout import TransactionOut
from Zyiron_Chain.utxo.utxo_manager import UTXOManager
from Zyiron_Chain.fees.fee_model import FeeModel
from Zyiron_Chain.transaction.tx_storage import TxStorage
from Zyiron_Chain.mempool.standard import StandardMempool
from Zyiron_Chain.mempool.smart import SmartMempool
from Zyiron_Chain.utils.hashing import Hashing
from Zyiron_Chain.security.signature import FalconSignatureVerifier


class PaymentProcessor:
    """
    Central processor for all payments across transaction models:
    - Standard
    - Smart Contract-based
    - Instant
    - Coinbase

    Handles:
    - Fee calculation
    - Transaction validation
    - UTXO management
    - Mempool routing
    - Signature verification
    """

    def __init__(self,
                 utxo_manager: UTXOManager,
                 tx_storage: TxStorage,
                 standard_mempool: StandardMempool,
                 smart_mempool: SmartMempool):
        self.utxo_manager = utxo_manager
        self.tx_storage = tx_storage
        self.standard_mempool = standard_mempool
        self.smart_mempool = smart_mempool
        self.fee_model = FeeModel()
        self.verifier = FalconSignatureVerifier()

        print("[PaymentProcessor INIT] ✅ Initialized PaymentProcessor")

    def send_payment(self,
                     sender_priv_key: str,
                     sender_pub_key: str,
                     recipient_address: str,
                     amount: Decimal,
                     tx_type: str = "STANDARD",
                     metadata: Optional[dict] = None) -> Optional[str]:
        """
        Process a new payment request:
        - Validates input
        - Gathers UTXOs
        - Creates transaction
        - Verifies signature
        - Sends to appropriate mempool
        """
        print(f"[PaymentProcessor] 🔄 Initiating send_payment() - Type: {tx_type}")

        if amount <= 0:
            print("[PaymentProcessor ERROR] ❌ Amount must be positive.")
            return None

        if tx_type not in Constants.TRANSACTION_MEMPOOL_MAP:
            print(f"[PaymentProcessor ERROR] ❌ Unknown transaction type: {tx_type}")
            return None

        # Step 1: Gather UTXOs and calculate total input
        utxos, total_input = self._select_utxos(sender_pub_key, amount)
        if not utxos:
            print("[PaymentProcessor ERROR] ❌ No valid UTXOs to cover transaction.")
            return None

        # Step 2: Calculate fee
        fee = self.fee_model.calculate_fee(tx_type=tx_type, tx_size=512)  # Estimated size
        if total_input < amount + fee:
            print("[PaymentProcessor ERROR] ❌ Insufficient funds after fee.")
            return None

        # Step 3: Build inputs and outputs
        inputs = [TransactionIn(tx_out_id=utxo.tx_out_id, script_sig="") for utxo in utxos]
        outputs = [TransactionOut(script_pub_key=recipient_address, amount=amount)]
        if total_input > amount + fee:
            change_amount = total_input - amount - fee
            outputs.append(TransactionOut(script_pub_key=sender_pub_key, amount=change_amount))

        # Step 4: Create transaction
        tx = Transaction(inputs=inputs, outputs=outputs, tx_type=tx_type, metadata=metadata or {})
        tx.sign(sender_priv_key, sender_pub_key)

        # Step 5: Verify signature
        if not self.verifier.verify(tx.signature, sender_pub_key, tx.hash()):
            print("[PaymentProcessor ERROR] ❌ Signature verification failed.")
            return None

        # Step 6: Lock UTXOs
        self.utxo_manager.lock_selected_utxos([utxo.tx_out_id for utxo in utxos])

        # Step 7: Route to appropriate mempool
        success = self._route_to_mempool(tx)
        if not success:
            self.utxo_manager.unlock_selected_utxos([utxo.tx_out_id for utxo in utxos])
            return None

        print(f"[PaymentProcessor SUCCESS] ✅ Payment sent. TXID: {tx.tx_id}")
        return tx.tx_id

    def _select_utxos(self, address: str, required_amount: Decimal) -> (List[TransactionOut], Decimal):
        """
        Select UTXOs for given address to meet the required amount + estimated fees.
        Returns a list of TransactionOut and the total selected input.
        """
        print(f"[PaymentProcessor] 🔍 Selecting UTXOs for address {address}...")
        utxos = self.utxo_manager.utxo_storage.get_utxos_by_address(address)
        selected = []
        total = Decimal("0")

        for utxo_dict in utxos:
            utxo = TransactionOut.from_dict(utxo_dict)
            if utxo.locked:
                continue
            selected.append(utxo)
            total += utxo.amount
            if total >= required_amount:
                break

        print(f"[PaymentProcessor] 🧮 Selected {len(selected)} UTXOs, total: {total}")
        return selected, total

    def _route_to_mempool(self, tx: Transaction) -> bool:
        """
        Routes a validated transaction to the appropriate mempool.
        """
        try:
            prefix = tx.tx_type.upper()
            if prefix.startswith("S"):
                print(f"[PaymentProcessor] 🚀 Routing to SmartMempool")
                return self.smart_mempool.add_transaction(tx)
            elif prefix.startswith("I"):
                print(f"[PaymentProcessor] ⚡ Instant Payments not yet implemented")
                return False  # Instant logic will be integrated later
            else:
                print(f"[PaymentProcessor] 📥 Routing to StandardMempool")
                return self.standard_mempool.add_transaction(tx)
        except Exception as e:
            print(f"[PaymentProcessor ERROR] ❌ Failed to route to mempool: {e}")
            return False
