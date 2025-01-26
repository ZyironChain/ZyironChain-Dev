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
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.database.blockchainpoc import BlockchainPoC
import logging

class Blockchain:
    ZERO_HASH = "0" * 96  # 384-bit zero hash for SHA-3 384

    def __init__(self, key_manager, poc_instance, difficulty=4):
        """
        Initialize the Blockchain with KeyManager, PoC, and other components.
        """
        self.key_manager = key_manager
        self.poc = poc_instance  # PoC is passed in as an instance
        self.chain = []  # This will be populated from PoC
        self.difficulty = difficulty
        self.utxo_manager = UTXOManager(self.poc)
        self.pending_transactions = []  # Initialize pending_transactions

        # Initialize the PoC (Point of Contact) layer
        self.mempool = StandardMempool(timeout=86400)

        # Load the blockchain data from PoC
        self.load_chain_from_poc()

        # Create the genesis block if the chain is empty
        if not self.chain:
            self.create_genesis_block()

    def load_chain_from_poc(self):
        """
        Load the blockchain data from the PoC layer.
        """
        logging.info("[Blockchain] Loading blockchain data from PoC...")
        self.poc.load_blockchain_data()  # Let PoC load the blockchain data
        self.chain = self.poc.get_blockchain_data()  # Get the loaded data from PoC
        print(f"[Blockchain] Loaded {len(self.chain)} blocks.")


    def create_genesis_block(self):
        """
        Create and add the genesis block to the blockchain if none exists.
        """
        if self.poc.get_block("block:0"):  # Check if genesis block exists in the PoC
            print("[INFO] Genesis block already exists.")
            return

        try:
            # Create the genesis transaction
            genesis_transaction = Transaction(
                tx_inputs=[],  # Empty list because it's a genesis transaction
                tx_outputs=[TransactionOut(script_pub_key="genesis_output", amount=50, locked=False)]
            )
            genesis_transactions = [genesis_transaction]  # The genesis block will have this single transaction

            # Calculate Merkle root
            merkle_root = self.calculate_merkle_root(genesis_transactions)
            print(f"[INFO] Merkle root calculated: {merkle_root}")

            # Create the Genesis Block
            genesis_block = Block(
                index=0,  # Explicitly set index to 0 for the genesis block
                previous_hash=self.ZERO_HASH,  # Zero hash for the genesis block
                transactions=genesis_transactions,  # Use the valid genesis transactions
                timestamp=int(time.time()),  # Ensure timestamp is an integer
                merkle_root=merkle_root,  # Pass the Merkle root directly during initialization
            )

            # Set the miner address using the KeyManager
            genesis_block.miner_address = self.key_manager.get_default_public_key("testnet", "miner")
            print(f"[INFO] Miner address set to: {genesis_block.miner_address}")

            # Calculate the target for mining
            target = self.calculate_target()

            print("[INFO] Mining the genesis block...")

            # Pass fee_model, mempool, block_size, and newBlockAvailable to mine()
            fee_model = self.poc.fee_model  # Example, should get it from the PoC instance
            mempool = self.poc.lmdb_manager  # Example, should get it from the PoC instance
            block_size = 1024 * 1024  # Example block size in bytes (1MB)
            newBlockAvailable = False  # Since we're mining the genesis block, we set this to False

            # Mine the block with required parameters
            if not genesis_block.mine(target, fee_model, mempool, block_size, newBlockAvailable):
                print("[ERROR] Failed to mine the genesis block.")
                return

            print(f"[INFO] Genesis block mined successfully! Nonce: {genesis_block.nonce}")

            # Append the genesis block to the chain
            self.chain.append(genesis_block)

            # Calculate difficulty for the genesis block using the Blockchain class method
            difficulty = self.calculate_block_difficulty(genesis_block)

            # Store the genesis block through PoC
            self.poc.store_block(genesis_block, difficulty)  # Pass difficulty to store_block

            print("[INFO] Genesis block created and stored successfully!")

        except Exception as e:
            print(f"[ERROR] Failed to create and save the genesis block: {e}")
            raise

    def calculate_block_difficulty(self, block):
        """
        Calculate the difficulty for a block based on a dynamic difficulty adjustment algorithm.
        :param block: The block for which difficulty is being calculated.
        :return: The calculated difficulty value.
        """
        # Default difficulty for the genesis block
        if block.index == 0:
            return 1  # Genesis block has a fixed difficulty

        # Get the previous block
        previous_block = self.chain[-1]

        # Calculate the time difference between the current block and the previous block
        time_diff = block.timestamp - previous_block.timestamp

        # Define the target block time (e.g., 10 minutes per block, similar to Bitcoin)
        target_block_time = 15  # 600 seconds = 10 minutes

        # Difficulty adjustment logic
        if time_diff < target_block_time:
            # If blocks are mined too quickly, increase difficulty
            return previous_block.difficulty + 1
        elif time_diff > target_block_time:
            # If blocks are mined too slowly, decrease difficulty
            return max(previous_block.difficulty - 1, 1)  # Ensure difficulty doesn't go below 1
        else:
            # If the block time is close to the target, keep the difficulty the same
            return previous_block.difficulty
    def validate_transaction_prefix(tx_id):
        # Valid prefixes for transactions
        valid_prefixes = ["S-", "PID-", "CID-"]
        
        # Check if the tx_id starts with a valid prefix
        if not any(tx_id.startswith(prefix) for prefix in valid_prefixes):
            raise ValueError(f"Transaction ID {tx_id} uses an unsupported prefix.")
        
        return True




    def save_blockchain_state(self):
        """
        Save the current state of the blockchain to persistent storage.
        """
        try:
            # Serialize the blockchain data
            blockchain_data = {
                "chain": [block.to_dict() if hasattr(block, "to_dict") else block for block in self.chain],
                "difficulty": self.difficulty,
                "pending_transactions": [tx.to_dict() if hasattr(tx, "to_dict") else tx for tx in self.pending_transactions],
            }

            # Save to a file (example)
            with open("blockchain_state.json", "w") as f:
                json.dump(blockchain_data, f, indent=4)
            print("[INFO] Blockchain state saved successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to save blockchain state: {e}")
            raise





    def export_utxos_to_leveldb(self):
        """
        Export all UTXOs to LevelDB.
        """
        for utxo_key, utxo_value in self.utxo_manager.get_all_utxos().items():
            self.utxo_manager.db.Put(f"utxo:{utxo_key}".encode(), json.dumps(utxo_value).encode())
        print("[INFO] Exported UTXOs to LevelDB.")

    def select_transactions_for_block(self, max_block_size_mb, fee_model):
        """
        Select transactions from the mempool (via PoC) to include in a new block.
        :param max_block_size_mb: Maximum block size in MB.
        :param fee_model: FeeModel instance for fee validation.
        :return: List of transactions to include in the block.
        """
        max_block_size_bytes = max_block_size_mb * 1024 * 1024
        selected_transactions = []
        current_block_size = 0

        # Fetch transactions sorted by fee-per-byte from the PoC's mempool
        pending_transactions = self.poc.get_pending_transactions_from_mempool()

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
                amount=self.poc.get_total_size_of_mempool(),
                tx_size=tx_size
            )
            actual_fee = sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)
            if actual_fee < required_fee:
                print(f"[WARN] Skipping transaction {tx.tx_id}: Insufficient fees.")
                continue

            selected_transactions.append(tx)
            current_block_size += tx_size

        return selected_transactions

    def add_block(self, block_height, previous_hash, network, fee_model):
        """
        Add a new block to the blockchain.
        :param block_height: The height of the new block.
        :param previous_hash: The hash of the previous block.
        :param network: Network type ("mainnet" or "testnet").
        :param fee_model: FeeModel instance for fee validation.
        """
        # Select transactions from mempool (via PoC)
        transactions = self.select_transactions_for_block(
            max_block_size_mb=10,  # Assuming 10 MB as the max block size
            fee_model=fee_model
        )

        # Validate transactions before adding to the block
        valid_transactions = []
        for tx in transactions:
            if self.validate_transaction(tx):
                valid_transactions.append(tx)
            else:
                print(f"[WARNING] Skipping invalid transaction: {tx}")

        if not valid_transactions:
            print("[ERROR] No valid transactions to include in the block.")
            return

        # Create a coinbase transaction with fees included
        total_fees = sum(
            sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)
            for tx in valid_transactions
        )
        coinbase_transaction = CoinbaseTx(
            key_manager=self.key_manager,
            network=network,
            utxo_manager=self.utxo_manager,
            transaction_fees=total_fees
        )
        valid_transactions.insert(0, coinbase_transaction.to_dict())

        # Create the new block
        new_block = Block(
            index=block_height,
            previous_hash=previous_hash,
            transactions=valid_transactions,
            miner_address=self.key_manager.get_miner_address()
        )

        # Mine the new block
        target = self.calculate_target()
        if not new_block.mine(target):
            print(f"[ERROR] Failed to mine block {block_height}.")
            return

        # Add the new block to the chain
        self.chain.append(new_block)
        print(f"[INFO] Block {block_height} mined and added to the blockchain.")

        print(f"[INFO] Block {block_height} mined successfully with Coinbase Transaction for network: {network}")




    def store_transaction_in_mempool(self, transaction):
        """
        Route the transaction to the PoC to be stored in the mempool.
        """
        self.poc.route_transaction_to_mempool(transaction)
        print(f"[INFO] Transaction {transaction.tx_id} stored in mempool.")

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

    def hash_transaction(self, tx):
        """
        Hashes a single transaction. If the transaction is a dictionary, serialize it to JSON.
        If it's a Transaction object, serialize it using its to_dict() method.
        If it's a string (transaction ID), hash it directly.
        :param tx: The transaction to hash (can be a dictionary, Transaction object, or string).
        :return: A hex string representing the hash of the transaction.
        """
        try:
            if isinstance(tx, dict):
                # Serialize dictionary-based transactions to JSON
                tx_str = json.dumps(tx, sort_keys=True)
            elif isinstance(tx, Transaction):  # If it's a Transaction object, serialize it
                tx_str = json.dumps(tx.to_dict(), sort_keys=True)
            elif isinstance(tx, str):  # If it's a string (transaction ID), hash it directly
                tx_str = tx
            else:
                raise ValueError(f"Invalid transaction type: {type(tx)}. Expected dict, Transaction, or str.")

            # Encode the serialized transaction and hash it
            hashed = hashlib.sha3_384(tx_str.encode()).hexdigest()
            print(f"[DEBUG] Transaction hash: {hashed} for transaction: {tx_str}")
            return hashed

        except Exception as e:
            print(f"[ERROR] Failed to hash transaction: {e}")
            raise


  
    def calculate_merkle_root(self, transactions):
        """
        Calculate the Merkle root of a list of transactions.
        :param transactions: List of transactions (Transaction objects or dictionaries).
        :return: The Merkle root as a hex string.
        """
        if not transactions:
            print("[DEBUG] No transactions provided. Returning ZERO_HASH as Merkle root.")
            return self.ZERO_HASH  # Use the class-level constant

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

        try:
            # Step 1: Extract transaction IDs
            transaction_ids = []
            for tx in transactions:
                if hasattr(tx, 'tx_id'):  # If tx is an object with a tx_id attribute
                    transaction_ids.append(tx.tx_id)
                elif isinstance(tx, dict) and "tx_id" in tx:  # If tx is a dictionary with a "tx_id" key
                    transaction_ids.append(tx["tx_id"])
                else:
                    raise ValueError(f"Transaction {tx} does not have a valid tx_id")

            # Step 2: Hash all transaction IDs
            hashed_transactions = [hashlib.sha3_384(tx_id.encode()).hexdigest() for tx_id in transaction_ids]
            print(f"[DEBUG] Initial transaction hashes: {hashed_transactions}")

            # Step 3: Build the Merkle tree
            current_level = hashed_transactions
            level = 0  # For debug purposes
            while len(current_level) > 1:
                print(f"[DEBUG] Level {level} hashes: {current_level}")
                current_level = merkle_parent_level(current_level)
                level += 1

            # Step 4: The last remaining hash is the Merkle root
            if not current_level:
                print("[ERROR] Merkle tree construction failed. Returning ZERO_HASH.")
                return self.ZERO_HASH  # Fallback in case of an error

            print(f"[DEBUG] Final Merkle root: {current_level[0]}")
            return current_level[0]

        except Exception as e:
            print(f"[ERROR] Failed to calculate Merkle root: {e}")
            return self.ZERO_HASH  # Fallback in case of an erro


    def calculate_target(self):
        """
        Calculate the mining target based on the difficulty level.
        """
        target = 2 ** (384 - self.difficulty * 4)
        print(f"[DEBUG] Calculated target for difficulty {self.difficulty}: {hex(target)}")
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

    def fetch_last_block(self):
        """
        Fetch the last mined block from the PoC.
        """
        try:
            last_block = self.poc.get_last_block()
            if last_block:
                print(f"[INFO] Fetched last block: Height = {last_block.index}, Hash = {last_block.hash}")
                return last_block
            else:
                print("[INFO] No last block found. Starting from genesis block.")
                return None
        except Exception as e:
            print(f"[ERROR] Failed to fetch last block: {e}")
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

    def validate_block(self, block, fee_model, block_size):
        """
        Validates a single block and its transactions.
        :param block: The block to validate.
        :param fee_model: FeeModel instance for fee validation.
        :param block_size: Block size in MB.
        :return: True if the block is valid, False otherwise.
        """
        try:
            # Verify transactions in the block
            for tx in block.transactions:
                if isinstance(tx, dict):  # Skip validation for coinbase transactions
                    continue

                # Check if transaction exists in LevelDB
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
                    payment_type="Standard",  # Adapt as needed
                    amount=self.mempool.get_total_size(),
                    tx_size=tx_size
                )
                actual_fee = sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)
                if actual_fee < required_fee:
                    print(f"[ERROR] Transaction {tx.tx_id} in block {block.index} has insufficient fees.")
                    return False

            # Validate block hash, previous hash, and Merkle root
            recalculated_hash = block.header.calculate_hash()
            if block.hash != recalculated_hash:
                print(f"[ERROR] Block {block.index} has an invalid hash!")
                return False

            recalculated_merkle_root = self.calculate_merkle_root(block.transactions)
            if block.header.merkle_root != recalculated_merkle_root:
                print(f"[ERROR] Block {block.index} has an invalid Merkle root!")
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
        Main blockchain loop for continuous mining.
        """
        # Fetch the last block from the database
        last_block = self.fetch_last_block()
        if last_block:
            self.chain.append(last_block)
            print(f"[INFO] Continuing from block {last_block.index}.")
        else:
            # Create the genesis block if no last block is found
            print("[INFO] Blockchain is empty. Mining genesis block...")
            self.create_genesis_block()

        # Start continuous mining
        while True:
            try:
                # Get the last block in the chain
                last_block = self.chain[-1]
                block_height = last_block.index + 1
                prev_block_hash = last_block.hash

                print(f"[INFO] Mining block {block_height}...")

                # Add a new block to the blockchain
                self.add_block(block_height, prev_block_hash, network="testnet", fee_model=self.poc.fee_model)

                # Print the newly mined block
                new_block = self.chain[-1]
                print(f"[INFO] Block {block_height} mined successfully!")
                print(f"Block Hash: {new_block.hash}")
                print(f"Previous Hash: {new_block.previous_hash}")
                print(f"Merkle Root: {new_block.header.merkle_root}")
                print(f"Transactions: {len(new_block.transactions)}")

                # Save the blockchain state
                self.save_blockchain_state()

                # Ask the user if they want to mine another block
                user_input = input("Do you want to mine another block? (y/n): ").strip().lower()
                if user_input != 'y':
                    print("[INFO] Exiting blockchain mining loop.")
                    break

            except Exception as e:
                print(f"[ERROR] An error occurred while mining block {block_height}: {e}")
                break
if __name__ == "__main__":
    # Initialize the PoC (Point of Contact) layer
    poc_instance = PoC()  # Create the PoC instance

    # Initialize the KeyManager
    key_manager = KeyManager()

    # Initialize the Blockchain with KeyManager and PoC instance
    blockchain = Blockchain(key_manager, poc_instance)  # Pass both key_manager and poc_instance to Blockchain

    # Load blockchain data using PoC
    blockchain.load_chain_from_poc()  # Load blockchain from PoC (this will use the method in PoC)
    
    # Optionally, run the main blockchain loop or any other operations
    blockchain.main()

    # After running the main process, you can load the blockchain from PoC if needed again
    blockchain_data = poc_instance.get_blockchain_data()
    print(f"Blockchain loaded with {len(blockchain_data)} blocks.")