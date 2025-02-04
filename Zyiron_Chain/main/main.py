import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)


from decimal import Decimal
from Zyiron_Chain.blockchain.blockchain import Blockchain
from Zyiron_Chain.blockchain.miner import Miner
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager
from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.transactions.Blockchain_transaction import Transaction, CoinbaseTx

def initialize_blockchain():
    """Initialize core blockchain components"""
    key_manager = KeyManager()
    poc = PoC()
    
    # Initialize blockchain with genesis block
    blockchain = Blockchain()
    blockchain.create_genesis_block(key_manager)
    
    return blockchain, key_manager, poc

def initialize_services(blockchain, key_manager):
    """Initialize supporting services"""
    from Zyiron_Chain.blockchain.storage_manager import StorageManager
    from Zyiron_Chain.blockchain.transaction_manager import TransactionManager
    
    storage_manager = StorageManager(blockchain.poc)
    transaction_manager = TransactionManager(storage_manager, key_manager)
    
    return storage_manager, transaction_manager

def mine_initial_blocks(blockchain, miner, num_blocks=5):
    """Mine initial blocks to bootstrap the chain"""
    for _ in range(num_blocks):
        miner.mine_block()
        print(f"Mined block {len(blockchain.chain)} - Hash: {blockchain.chain[-1].hash}")

def main():
    # Initialize core components
    blockchain, key_manager, poc = initialize_blockchain()
    storage_manager, transaction_manager = initialize_services(blockchain, key_manager)
    
    # Initialize miner
    miner = Miner(
        block_manager=blockchain.block_manager,
        transaction_manager=transaction_manager,
        storage_manager=storage_manager
    )
    
    # Mine initial blocks
    mine_initial_blocks(blockchain, miner)
    
    # Example transaction flow
    try:
        # Create sample transaction
        sample_tx = Transaction(
            tx_id="PID-12345678",
            tx_inputs=[{"tx_out_id": "genesis_output", "amount": 50}],
            tx_outputs=[{"recipient": "test_recipient", "amount": 45}],
            poc=poc
        )
        
        # Add to mempool
        transaction_manager.store_transaction_in_mempool(sample_tx)
        print(f"Transaction {sample_tx.tx_id} added to mempool")
        
        # Mine block containing transaction
        miner.mine_block()
        
    except Exception as e:
        print(f"Transaction failed: {str(e)}")

    print("\nBlockchain Summary:")
    print(f"Chain Height: {len(blockchain.chain)}")
    print(f"Total Supply: {blockchain.total_issued}")
    print(f"Last Block Hash: {blockchain.chain[-1].hash}")

if __name__ == "__main__":
    main()