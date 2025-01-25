import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))



from Zyiron_Chain.blockchain.utils.data_storage import JSONHandler
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction, TransactionIn, CoinbaseTx
import json
import hashlib
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
from Zyiron_Chain.blockchain.utils.data_storage import JSONHandler
from Zyiron_Chain.blockchain.block import Block, BlockHeader
from Zyiron_Chain.blockchain.utils.standardmempool import StandardMempool
from Zyiron_Chain.transactions.txout import UTXOManager, TransactionOut
import time
from Zyiron_Chain.transactions.fees import FeeModel
from Zyiron_Chain.transactions.transactiontype import TransactionType
from Zyiron_Chain.smartpay.smartmempool import SmartMempool






class Blockchain:
    ZERO_HASH = "0" * 96  # 384-bit zero hash for SHA-3 384

    def __init__(self, key_manager, fee_model, difficulty=4):
        """
        Initialize the Blockchain with KeyManager, FeeModel, and other components.
        """
        self.key_manager = key_manager
        self.fee_model = fee_model
        self.difficulty = difficulty
        self.chain = []  # Blockchain data will be loaded from LevelDB
        self.utxo_manager = UTXOManager()

        # Load the blockchain data from LevelDB
        self.load_chain_from_leveldb()

        # Create the genesis block if the chain is empty
        if not self.chain:
            self.create_genesis_block()

                
    def create_genesis_block(self):
        """
        Create and add the genesis block to the blockchain if none exists in LevelDB.
        """
        try:
            if self.utxo_manager.db.get(b"block:0"):
                print("[INFO] Genesis block already exists in LevelDB.")
                return

            print("[INFO] Attempting to create a new genesis block...")
            genesis_block = Block(
                index=0,
                previous_hash=self.ZERO_HASH,
                transactions=["Genesis Block"],
                timestamp=time.time(),
            )
            genesis_block.merkle_root = self.calculate_merkle_root(genesis_block.transactions)
            genesis_block.mine(
                target=self.calculate_target(),
                fee_model=self.fee_model,
                mempool=None,
                block_size=None,
                newBlockAvailable=False,
            )
            self.chain.append(genesis_block)

            # Save genesis block to LevelDB
            block_key = f"block:{genesis_block.index}".encode()
            self.utxo_manager.db.put(block_key, json.dumps(genesis_block.to_dict()).encode())
            print("[INFO] Genesis block created and saved to LevelDB.")
        except KeyError:
            print(f"[ERROR] Genesis block does not exist and could not be found.")
        except Exception as e:
            print(f"[ERROR] Failed to create and save the genesis block: {e}")





    # Additional methods such as `add_block` and others remain unchanged unless affected

    def dynamic_block_size(self):
        """
        Calculate dynamic block size based on current network conditions.
        Returns block size in MB (1-10 MB).
        """
        block_size = min(max(1, self.mempool.get_total_size() // (1024 * 1024)), 10)  # Example logic
        print(f"[DEBUG] Calculated dynamic block size: {block_size} MB")
        return block_size


    def validate_transaction_prefix(tx_id):
        valid_prefixes = ["S-", "PID-", "CID-"]
        if not any(tx_id.startswith(prefix) for prefix in valid_prefixes):
            if tx_id.startswith("T-") or tx_id.startswith("I-"):
                raise ValueError(f"Transaction ID {tx_id} uses a deprecated or unsupported prefix.")
        return True

    def export_utxos_to_leveldb(self):
        """
        Export all UTXOs to LevelDB.
        """
        for utxo_key, utxo_value in self.utxo_manager.get_all_utxos().items():
            self.utxo_manager.db.Put(f"utxo:{utxo_key}".encode(), json.dumps(utxo_value).encode())
        print("[INFO] Exported UTXOs to LevelDB.")



    def select_transactions_for_block(self, max_block_size_mb, fee_model):
        """
        Select transactions from the mempool to include in a new block.
        :param max_block_size_mb: Maximum block size in MB.
        :param fee_model: FeeModel instance.
        :return: List of transactions to include in the block.
        """
        max_block_size_bytes = max_block_size_mb * 1024 * 1024
        selected_transactions = []
        current_block_size = 0

        # Fetch transactions sorted by fee-per-byte
        pending_transactions = self.mempool.get_pending_transactions()

        for tx in pending_transactions:
            # Calculate transaction size
            tx_size = sum(
                len(str(inp.to_dict())) + len(str(out.to_dict())) 
                for inp, out in zip(tx.tx_inputs, tx.tx_outputs)
            )
            if current_block_size + tx_size > max_block_size_bytes:
                break

            # Validate fees using FeeModel
            required_fee = fee_model.calculate_fee(
                block_size=max_block_size_mb,
                payment_type="Standard",  # Assume Standard; adapt as needed
                amount=self.mempool.get_total_size(),
                tx_size=tx_size
            )
            actual_fee = sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)
            if actual_fee < required_fee:
                print(f"[WARN] Skipping transaction {tx.tx_id}: Insufficient fees.")
                continue

            selected_transactions.append(tx)
            current_block_size += tx_size

        return selected_transactions

    def add_block(self, block_height, previous_hash, network, fee_model, max_block_size_mb=None):
        """
        Add a new block with dynamic block size based on network conditions.
        :param block_height: The height of the new block.
        :param previous_hash: The hash of the previous block.
        :param network: Network type ("mainnet" or "testnet").
        :param fee_model: FeeModel instance for fee validation.
        :param max_block_size_mb: Optional maximum block size in MB (1-10 MB). Defaults to an optimal calculated size.
        """
        # Calculate optimal block size if not provided
        max_block_size_mb = max_block_size_mb or self.calculate_optimal_block_size()

        # Validate block size
        if not (1 <= max_block_size_mb <= 10):
            raise ValueError(f"Invalid block size {max_block_size_mb}MB. Must be between 1 and 10 MB.")

        # Select transactions for the block
        transactions = self.select_transactions_for_block(max_block_size_mb, fee_model)

        # Validate transaction prefixes
        for tx in transactions:
            payment_type = TransactionType.get_type_prefix(tx.tx_id)
            if not payment_type:
                raise ValueError(f"Invalid transaction prefix for {tx.tx_id}. Transaction rejected.")

        # Calculate total fees from transactions
        total_fees = sum(
            sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)
            for tx in transactions
        )

        # Create a coinbase transaction with fees included
        coinbase_transaction = CoinbaseTx(
            key_manager=self.key_manager,
            network=network,
            utxo_manager=self.utxo_manager,
            transaction_fees=total_fees
        )
        transactions.insert(0, coinbase_transaction.to_dict())

        # Calculate Merkle root and create the block
        transaction_ids = [tx["tx_id"] for tx in transactions if isinstance(tx, dict) and "tx_id" in tx]
        new_block = Block(index=block_height, previous_hash=previous_hash, transactions=transactions)
        merkle_root = self.calculate_merkle_root(transaction_ids)
        new_block.set_header(version=1, merkle_root=merkle_root)

        # Mine the block
        target = self.calculate_target()
        if not new_block.mine(target, fee_model, self.mempool, max_block_size_mb, newBlockAvailable=False):
            print(f"[ERROR] Failed to mine block {block_height}.")
            return

        # Validate and append the block
        if new_block.previous_hash != previous_hash:
            raise ValueError("New block's previous hash does not match the last block's hash!")

        self.chain.append(new_block)

        # Update UTXOs using UTXOManager
        self.utxo_manager.update_from_block(new_block)

        # Save the blockchain
        try:
            self.save_blockchain()
            print(f"[INFO] Blockchain saved successfully after adding block {block_height}.")
        except Exception as e:
            print(f"[ERROR] Failed to save blockchain after adding block {block_height}: {e}")
            raise

        print(f"[INFO] Block {block_height} mined successfully with Coinbase Transaction for network: {network}")


    def calculate_optimal_block_size(self):
        """
        Calculate the optimal block size dynamically based on network conditions.
        :return: Optimal block size in MB (between 1 and 10 MB).
        """
        network_utilization = self.mempool.get_total_size() / (10 * 1024 * 1024)  # Assuming 10 MB maximum mempool capacity
        return min(max(1, int(network_utilization * 10)), 10)  # Scale between 1 MB and 10 MB



    def store_transaction(self, transaction):
        """
        Store a transaction in LevelDB.
        """
        key = f"transaction:{transaction.tx_id}".encode()
        self.utxo_manager.db.Put(key, json.dumps(transaction.to_dict()).encode())
        print(f"[INFO] Transaction {transaction.tx_id} stored in LevelDB.")





    def store_block_metadata(self, block):
        """
        Store metadata for a block in LevelDB.
        """
        key = f"block_metadata:{block.hash}".encode()
        value = json.dumps({
            "height": block.index,
            "parent_hash": block.previous_hash,
            "timestamp": block.timestamp,
        }).encode()
        self.utxo_manager.db.Put(key, value)
        print(f"[INFO] Metadata for block {block.hash} stored in LevelDB.")


    def update_chain_state(self, best_block_hash, total_work, block_height):
        """
        Update chain state in LevelDB.
        """
        key = b"chain_state"
        value = json.dumps({
            "best_block_hash": best_block_hash,
            "total_work": total_work,
            "block_height": block_height,
        }).encode()
        self.utxo_manager.db.Put(key, value)
        print("[INFO] Chain state updated in LevelDB.")




    def calculate_merkle_root(self, transactions):
        """
        Calculate the Merkle root of a list of transactions.
        :param transactions: List of transactions to calculate the Merkle root for.
        :return: The Merkle root as a hex string.
        """
        if not transactions:
            print("[DEBUG] No transactions provided. Returning ZERO_HASH as Merkle root.")
            return self.ZERO_HASH

        def hash_transaction(tx):
            """
            Hashes a single transaction. If the transaction is a dictionary, serialize it to JSON.
            """
            if isinstance(tx, dict):
                # Ensure prefix validation for dictionary-based transactions
                tx_id = tx.get("tx_id", "")
                if not self.is_valid_transaction_prefix(tx_id):
                    raise ValueError(f"Invalid transaction ID prefix: {tx_id}")
                tx = json.dumps(tx, sort_keys=True)
            hashed = hashlib.sha3_384(tx.encode()).hexdigest()
            print(f"[DEBUG] Transaction hash: {hashed} for transaction: {tx}")
            return hashed

        def merkle_parent_level(hashes):
            """
            Takes a list of hashes and returns the parent level.
            If odd, duplicate the last hash.
            """
            if len(hashes) % 2 == 1:  # If odd, duplicate the last hash
                hashes.append(hashes[-1])
                print("[DEBUG] Odd number of hashes detected, duplicating the last hash.")

            parent_level = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                parent_hash = hashlib.sha3_384(combined.encode()).hexdigest()
                parent_level.append(parent_hash)
                print(f"[DEBUG] Parent hash: {parent_hash} from {hashes[i]} + {hashes[i + 1]}")
            return parent_level

        # Step 1: Hash all transactions
        hashed_transactions = [hash_transaction(tx) for tx in transactions]
        print(f"[DEBUG] Initial transaction hashes: {hashed_transactions}")

        # Step 2: Build the Merkle tree
        current_level = hashed_transactions
        level = 0  # For debug purposes
        while len(current_level) > 1:
            print(f"[DEBUG] Level {level} hashes: {current_level}")
            current_level = merkle_parent_level(current_level)
            level += 1

        # Step 3: The last remaining hash is the Merkle root
        print(f"[DEBUG] Final Merkle root: {current_level[0]}")
        return current_level[0]



    def calculate_target(self, block_size_mb=None):
        """
        Adjust the mining target dynamically based on block size and difficulty.
        """
        size_factor = 1 if not block_size_mb else (block_size_mb / 10)  # Normalize to a 1-10 MB scale
        target = int(2 ** (384 - self.difficulty * 4) * size_factor)
        print(f"[DEBUG] Calculated target for difficulty {self.difficulty} and block size {block_size_mb} MB: {hex(target)}")
        return target




    def initialize_chain_state(self):
        """
        Initialize the chain state from LevelDB.
        """
        try:
            key = b"chain_state"
            value = self.utxo_manager.db.Get(key)
            chain_state = json.loads(value.decode())
            self.best_block_hash = chain_state["best_block_hash"]
            self.total_work = chain_state["total_work"]
            self.block_height = chain_state["block_height"]
            print("[INFO] Chain state initialized from LevelDB.")
        except KeyError:
            print("[INFO] No chain state found. Initializing with default values.")
            self.best_block_hash = None
            self.total_work = 0
            self.block_height = 0
        except Exception as e:
            print(f"[ERROR] Failed to initialize chain state: {e}")


    def get_transaction(self, tx_id):
        """
        Retrieve a transaction by its ID from LevelDB.
        """
        try:
            key = f"transaction:{tx_id}".encode()
            value = self.utxo_manager.db.Get(key)
            return Transaction.from_dict(json.loads(value.decode()))
        except KeyError:
            print(f"[INFO] Transaction {tx_id} not found in LevelDB.")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to retrieve transaction {tx_id}: {e}")
            return None

    def select_transactions_for_block(self, max_block_size_mb, fee_model):
        """
        Dynamically select transactions for the block based on the provided block size and fee model.
        """
        max_block_size_bytes = max_block_size_mb * 1024 * 1024  # Convert MB to bytes
        selected_transactions = []
        current_block_size = 0

        # Fetch transactions sorted by fee-per-byte
        pending_transactions = self.mempool.get_pending_transactions()

        for tx in pending_transactions:
            tx_size = sum(
                len(str(inp.to_dict())) + len(str(out.to_dict())) 
                for inp, out in zip(tx.tx_inputs, tx.tx_outputs)
            )
            if current_block_size + tx_size > max_block_size_bytes:
                break

            # Validate fees using FeeModel
            required_fee = fee_model.calculate_fee(
                block_size=max_block_size_mb,
                payment_type="Standard",
                amount=self.mempool.get_total_size(),
                tx_size=tx_size
            )
            actual_fee = sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)
            if actual_fee < required_fee:
                continue

            selected_transactions.append(tx)
            current_block_size += tx_size

        return selected_transactions



    def fetch_last_block(self):
        """
        Retrieve the last block in the chain.
        :return: The last block if the chain is not empty, else None.
        """
        if self.chain:
            print(f"[DEBUG] Fetching last block: Index {self.chain[-1].index}")
            return self.chain[-1]
        print("[DEBUG] No blocks in the chain. Returning None.")
        return None


    def is_chain_valid(self):
        """
        Validates the entire blockchain.
        :return: True if valid, False otherwise.
        """
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]

            # Validate previous hash link
            if current_block.previous_hash != previous_block.hash:
                print(f"[ERROR] Block {i} has an invalid previous hash!")
                print(f"Expected: {previous_block.hash}")
                print(f"Found: {current_block.previous_hash}")
                return False

            # Recalculate and verify block hash
            recalculated_hash = current_block.calculate_hash()
            if current_block.hash != recalculated_hash:
                print(f"[ERROR] Block {i} has an invalid hash!")
                print(f"Expected: {recalculated_hash}")
                print(f"Found: {current_block.hash}")
                return False

            # Verify Merkle root
            try:
                recalculated_merkle_root = self.calculate_merkle_root(current_block.transactions)
            except Exception as e:
                print(f"[ERROR] Block {i} failed during Merkle root calculation: {e}")
                return False

            if current_block.header.merkle_root != recalculated_merkle_root:
                print(f"[ERROR] Block {i} has an invalid Merkle root!")
                print(f"Expected: {recalculated_merkle_root}")
                print(f"Found: {current_block.header.merkle_root}")
                return False

            # Verify block difficulty
            target = self.calculate_target()
            if int(recalculated_hash, 16) > target:
                print(f"[ERROR] Block {i} does not meet the required difficulty!")
                print(f"Hash: {recalculated_hash}")
                print(f"Target: {hex(target)}")
                return False

        print("[INFO] Blockchain validation passed.")
        return True




    def import_utxos_from_leveldb(self):
        """
        Import all UTXOs from LevelDB.
        """
        self.utxo_manager.clear_utxos()
        for key, value in self.utxo_manager.db.RangeIter(prefix=b"utxo:"):
            utxo_key = key.decode().split("utxo:")[1]
            utxo_value = json.loads(value.decode())
            self.utxo_manager.add_utxo(utxo_key, utxo_value)
        print("[INFO] Imported UTXOs from LevelDB.")


    def load_chain_from_leveldb(self):
        """
        Load the blockchain data from LevelDB.
        """
        try:
            self.chain = []
            keys_to_process = [key for key, _ in self.utxo_manager.db.RangeIter() if key.decode().startswith("block:")]
            
            for key in keys_to_process:
                block_data = json.loads(self.utxo_manager.db.get(key).decode())
                self.chain.append(Block.from_dict(block_data))

            if not self.chain:
                print("[INFO] No blocks found in LevelDB. Initializing with genesis block...")
                self.create_genesis_block()
            else:
                print(f"[INFO] Blockchain successfully loaded from LevelDB with {len(self.chain)} blocks.")
        except Exception as e:
            print(f"[ERROR] Failed to load blockchain from LevelDB: {e}")
            if not self.chain:
                self.create_genesis_block()




    def validate_block(self, block, fee_model, block_size):
        """
        Validates a single block and its transactions.
        :param block: The block to validate.
        :param fee_model: FeeModel instance for fee validation.
        :param block_size: Block size in MB (dynamic between 1-10 MB).
        :return: True if the block is valid, False otherwise.
        """
        try:
            # Check block size limits
            block_size_bytes = block_size * 1024 * 1024
            block_data_size = sum(len(str(tx)) for tx in block.transactions)
            if block_data_size > block_size_bytes:
                print(f"[ERROR] Block {block.index} exceeds size limit of {block_size} MB!")
                return False

            # Validate transactions in the block
            for tx in block.transactions:
                if isinstance(tx, dict):  # Skip coinbase transactions
                    continue

                # Check if the transaction exists in LevelDB
                stored_tx = self.get_transaction(tx.tx_id)
                if not stored_tx:
                    print(f"[ERROR] Transaction {tx.tx_id} not found in LevelDB.")
                    return False

                # Validate transaction size and fees
                tx_size = sum(
                    len(str(inp.to_dict())) + len(str(out.to_dict()))
                    for inp, out in zip(tx.tx_inputs, tx.tx_outputs)
                )
                required_fee = fee_model.calculate_fee(
                    block_size=block_size,
                    payment_type="Standard",
                    amount=self.mempool.get_total_size(),
                    tx_size=tx_size,
                )
                actual_fee = sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)
                if actual_fee < required_fee:
                    print(f"[ERROR] Transaction {tx.tx_id} in block {block.index} has insufficient fees.")
                    return False

            # Verify block hash, previous hash, and Merkle root
            recalculated_hash = block.header.calculate_hash()
            if block.hash != recalculated_hash:
                print(f"[ERROR] Block {block.index} has an invalid hash!")
                return False

            recalculated_merkle_root = self.calculate_merkle_root(block.transactions)
            if block.header.merkle_root != recalculated_merkle_root:
                print(f"[ERROR] Block {block.index} has an invalid Merkle root!")
                return False

            # Verify block difficulty
            target = self.calculate_target()
            if int(recalculated_hash, 16) > target:
                print(f"[ERROR] Block {block.index} does not meet the required difficulty!")
                return False

            print(f"[INFO] Block {block.index} validated successfully.")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to validate block {block.index}: {e}")
            return False


    def lock_utxo_for_channel(self, utxo_id):
        self.utxo_manager.lock_utxo(utxo_id)

    def unlock_utxo_for_channel(self, utxo_id):
        self.utxo_manager.unlock_utxo(utxo_id)





    def deserialize_block(self, block_data):
        """
        Deserialize block data and ensure all required fields are present.
        """
        required_keys = {"index", "header", "transactions"}
        missing_keys = required_keys - block_data.keys()
        if missing_keys:
            raise KeyError(f"Missing required key(s): {missing_keys} in block data.")

        header_required_keys = {"previous_hash", "merkle_root", "timestamp", "nonce"}
        missing_header_keys = header_required_keys - block_data["header"].keys()
        if missing_header_keys:
            raise KeyError(f"Missing required key(s): {missing_header_keys} in block header.")

        return Block.from_dict(block_data)

    def get_block_metadata(self, block_hash):
        """
        Retrieve metadata for a block from LevelDB.
        """
        try:
            key = f"block_metadata:{block_hash}".encode()
            value = self.utxo_manager.db.Get(key)
            return json.loads(value.decode())
        except KeyError:
            print(f"[INFO] Metadata for block {block_hash} not found in LevelDB.")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to retrieve block metadata: {e}")
            return None



    def main(self):
        """
        Main blockchain loop for adding blocks.
        """
        try:
            if not self.chain:
                print("[INFO] No blocks found in the chain. Initializing genesis block...")
                self.create_genesis_block()

            while True:
                last_block = self.chain[-1]
                block_height = last_block.index + 1
                prev_block_hash = last_block.hash
                self.add_block(block_height, prev_block_hash, network="testnet", fee_model=self.fee_model)
        except IndexError as e:
            print(f"[ERROR] Blockchain is uninitialized or empty. Please verify genesis block creation: {e}")
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred in the blockchain main loop: {e}")

class BlockchainConfig:
    MIN_BLOCK_SIZE_MB = 1
    MAX_BLOCK_SIZE_MB = 10
    DYNAMIC_SIZING_ENABLED = True






if __name__ == "__main__":
    key_manager = KeyManager()
    fee_model = FeeModel()
    blockchain = Blockchain(key_manager, fee_model)
    blockchain.main()