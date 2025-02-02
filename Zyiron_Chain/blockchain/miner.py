import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


import time
from Zyiron_Chain.blockchain.block import Block 
from Zyiron_Chain.blockchain.block_manager import BlockManager


class Miner:
    def __init__(self, block_manager, transaction_manager, storage_manager):
        self.block_manager = block_manager
        self.transaction_manager = transaction_manager
        self.storage_manager = storage_manager
        self.difficulty_adjustment_interval = 2016  # Similar to Bitcoin's 2016 block interval

    def mine_block(self, network="testnet"):
        last_block = self.block_manager.chain[-1] if self.block_manager.chain else None
        block_height = last_block.index + 1 if last_block else 0
        prev_hash = last_block.hash if last_block else BlockManager.ZERO_HASH

        transactions = self.transaction_manager.select_transactions_for_block()
        total_fees = sum(
            sum(inp.amount for inp in tx.tx_inputs) - sum(out.amount for out in tx.tx_outputs)
            for tx in transactions
        )

        coinbase_tx = self.transaction_manager.create_coinbase_tx(total_fees, network)
        transactions.insert(0, coinbase_tx)

        new_block = Block(
            index=block_height,
            previous_hash=prev_hash,
            transactions=transactions,
            timestamp=int(time.time()),
            merkle_root=self.block_manager.calculate_merkle_root(transactions),
            miner_address=self.transaction_manager.key_manager.get_miner_address()
        )

        target = self.block_manager.calculate_target()
        if new_block.mine(target):
            self.block_manager.chain.append(new_block)
            self.storage_manager.store_block(new_block, self.block_manager.calculate_block_difficulty(new_block))
            self.storage_manager.save_blockchain_state(self.block_manager.chain, [])
            return True
        return False

    def mining_loop(self):
        while True:
            try:
                if not self.block_manager.chain:
                    print("Mining genesis block...")
                    self.block_manager.create_genesis_block(self.transaction_manager.key_manager)
                else:
                    print(f"Mining block {len(self.block_manager.chain)}...")
                    if self.mine_block():
                        print("Block mined successfully!")
                    else:
                        print("Failed to mine block")

                user_input = input("Mine another block? (y/n): ").lower()
                if user_input != 'y':
                    break
            except KeyboardInterrupt:
                print("\nMining interrupted")
                break
            except Exception as e:
                print(f"Mining error: {str(e)}")
                break