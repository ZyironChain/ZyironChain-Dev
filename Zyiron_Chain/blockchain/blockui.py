import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from flask import Flask, request, jsonify, render_template
from Zyiron_Chain.database.duckdatabase  import AnalyticsNetworkDB  # Replace with the actual import for your database

import sys
import time
import logging
from decimal import Decimal

from Zyiron_Chain.database.poc import PoC
from Zyiron_Chain.blockchain.storage_manager import StorageManager
from Zyiron_Chain.blockchain.transaction_manager import TransactionManager
from Zyiron_Chain.blockchain.block_manager import BlockManager
from Zyiron_Chain.blockchain.miner import Miner
from Zyiron_Chain.blockchain.utils.key_manager import KeyManager

logging.basicConfig(level=logging.INFO)

class BlockchainMain:
    def __init__(self):
        """Initialize Blockchain System with Core Components"""
        logging.info("[BOOT] Initializing Blockchain System...")

        # ✅ Initialize PoC (Point of Contact)
        self.poc_instance = PoC()

        # ✅ Initialize Database Storage
        self.storage_manager = StorageManager(self.poc_instance)

        # ✅ Initialize Key Manager
        self.key_manager = KeyManager()

        # ✅ Initialize Transaction Manager
        self.transaction_manager = TransactionManager(self.storage_manager, self.key_manager, self.poc_instance)

        # ✅ Initialize Block Manager
        self.block_manager = BlockManager(self.storage_manager, self.transaction_manager)

        # ✅ Initialize Miner
        self.miner = Miner(self.block_manager, self.transaction_manager, self.storage_manager)

    def start_mining(self):
        """Start the mining process"""
        logging.info("[MINER] 🚀 Starting Mining Process...")

        while True:
            try:
                # ✅ Ensure Genesis Block Exists
                if not self.block_manager.chain:
                    logging.info("[MINER] 🔄 Mining Genesis Block...")
                    self.block_manager.create_genesis_block()

                else:
                    logging.info(f"[MINER] 🔄 Mining Block {len(self.block_manager.chain)}...")
                    if self.miner.mine_block():
                        logging.info("[MINER] ✅ Block Mined Successfully!")
                    else:
                        logging.error("[MINER] ❌ Failed to Mine Block!")

            except KeyboardInterrupt:
                logging.info("\n[INFO] Mining stopped by user (Ctrl+C).")
                break
            except Exception as e:
                logging.error(f"[ERROR] Mining error: {str(e)}")
                break

    def run(self):
        """Run the blockchain system with options for mining and querying."""
        while True:
            print("\n[🌐 BLOCKCHAIN NODE]")
            print("[1] Start Mining")
            print("[2] Query Blockchain")
            print("[3] Exit")
            choice = input("Enter your choice: ")

            if choice == "1":
                self.start_mining()
            elif choice == "2":
                self.query_blockchain()
            elif choice == "3":
                logging.info("[EXIT] Shutting Down Blockchain System.")
                sys.exit()
            else:
                print("[ERROR] Invalid Choice! Please select 1, 2, or 3.")

    def query_blockchain(self):
        """Query blockchain data"""
        while True:
            print("\n[🔍 BLOCKCHAIN QUERY TOOL]")
            print("[1] Query Specific Block")
            print("[2] Query Latest Block")
            print("[3] Query All Blocks")
            print("[4] Exit")
            choice = input("Enter your choice (1-4): ")

            if choice == "1":
                block_id = input("Enter Block ID to Query: ")
                block_data = self.poc_instance.get_block(block_id)
                if block_data:
                    print(f"\n[BLOCK {block_id}] {block_data}")
                else:
                    print("[ERROR] Block Not Found!")

            elif choice == "2":
                last_block = self.poc_instance.get_last_block()
                print(f"\n[LATEST BLOCK] {last_block}")

            elif choice == "3":
                all_blocks = self.poc_instance.unqlite_db.get_all_blocks()
                if all_blocks:
                    for block in all_blocks:
                        print(f"\n[BLOCK {block['header']['index']}] {block}")
                else:
                    print("[ERROR] No Blocks Found!")

            elif choice == "4":
                print("[INFO] Exiting Query Tool.")
                break

            else:
                print("[ERROR] Invalid Choice! Please select 1, 2, 3, or 4.")

# ✅ Run Blockchain System
if __name__ == "__main__":
    blockchain = BlockchainMain()
    blockchain.run()