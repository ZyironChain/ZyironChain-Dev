import logging

logging.basicConfig(level=logging.INFO)

class BlockchainPoC:
    def __init__(self, poc_instance):
        """
        Initialize the BlockchainPoC with a PoC instance that handles node interactions.
        :param poc_instance: Instance of PoC class to interact with databases.
        """
        self.poc = poc_instance  # PoC instance for routing database operations
        self.chain = []  # List to store the blockchain (blocks)
        self.load_blockchain_data()  # Load blockchain data from the database

    def store_block(self, block):
        """
        Store the block by ensuring its consistency before passing it to PoC for storage.
        :param block: The block to be stored.
        """
        try:
            # Ensure data consistency
            self.ensure_consistency(block)

            # Pass the block to PoC for routing and storing
            self.poc.store_block(block)  # PoC handles storing the block
            self.chain.append(block)  # Add the block to the local chain
            logging.info(f"[INFO] Block {block.index} stored successfully.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to store block: {e}")
            raise

    def ensure_consistency(self, block):
        """
        Ensure the consistency of the blockchain data before any modifications.
        :param block: The block to check for consistency.
        """
        if self.chain:
            last_block = self.chain[-1]
            if block.previous_hash != last_block.hash:
                raise ValueError(f"Previous hash mismatch: {block.previous_hash} != {last_block.hash}")
            if block.index != last_block.index + 1:
                raise ValueError(f"Block index mismatch: {block.index} != {last_block.index + 1}")
        else:
            if block.index != 0:
                raise ValueError("First block must have index 0.")

        # Additional consistency checks can be added here if needed
        if not block.hash or not block.merkle_root:
            raise ValueError("Block hash or Merkle root is missing.")

    def get_blockchain_data(self):
        """
        Return the blockchain data (blocks) that has been loaded.
        :return: A list of blocks.
        """
        return self.chain

    def load_blockchain_data(self):
        """
        Load blockchain data (blocks, transactions, UTXOs) from the appropriate source.
        This can be a database or other persistent storage.
        """
        logging.info("[BlockchainPoC] Loading blockchain data...")

        try:
            # Fetch blockchain data from UnQLite via PoC
            self.chain = self.poc.unqlite_db.get_all_blocks()  # Example of loading blocks from UnQLite via PoC
            logging.info(f"[BlockchainPoC] Loaded {len(self.chain)} blocks.")
        except Exception as e:
            logging.error(f"[BlockchainPoC] Error loading blockchain data: {e}")
            self.chain = []

    def get_block(self, block_hash):
        """
        Fetch a block by its hash from the blockchain (via PoC).
        :param block_hash: The hash of the block to retrieve.
        :return: The block data if found, None otherwise.
        """
        logging.info(f"[BlockchainPoC] Fetching block with hash {block_hash}")
        try:
            block = self.poc.unqlite_db.get_block(block_hash)  # Fetch block by hash from UnQLite via PoC
            if block:
                logging.info(f"[BlockchainPoC] Block {block_hash} found.")
                return block
            else:
                logging.error(f"[BlockchainPoC] Block {block_hash} not found.")
                return None
        except Exception as e:
            logging.error(f"[BlockchainPoC] Failed to fetch block {block_hash}: {e}")
            return None

    def handle_transaction(self, transaction):
        """
        Handle the transaction and pass it to PoC for further processing or storing.
        :param transaction: The transaction to handle.
        """
        try:
            # Validate the transaction before processing
            if not hasattr(transaction, 'tx_id'):
                raise ValueError("Transaction is missing required field: tx_id")

            # Pass the transaction to PoC for routing and storing
            self.poc.store_transaction(transaction)  # PoC handles storing the transaction
            logging.info(f"[INFO] Transaction {transaction.tx_id} handled successfully.")
        except Exception as e:
            logging.error(f"[ERROR] Failed to handle transaction: {e}")
            raise

    def get_last_block(self):
        """
        Fetch the last block in the blockchain.
        :return: The last block if the chain is not empty, None otherwise.
        """
        if self.chain:
            return self.chain[-1]
        return None

    def validate_block(self, block):
        """
        Validate a block before adding it to the blockchain.
        :param block: The block to validate.
        :return: True if the block is valid, False otherwise.
        """
        try:
            self.ensure_consistency(block)
            return True
        except Exception as e:
            logging.error(f"[ERROR] Block validation failed: {e}")
            return False

    def clear_blockchain(self):
        """
        Clear the blockchain data (for testing or reset purposes).
        """
        self.chain = []
        logging.info("[INFO] Blockchain data cleared.")