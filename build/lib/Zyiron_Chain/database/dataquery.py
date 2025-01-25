import sys
import os

# Add the project root directory dynamically
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../'))
sys.path.insert(0, project_root)

# Print sys.path for debugging
print("Current sys.path:")
print("\n".join(sys.path))

import json
import csv
from Zyiron_Chain.database.leveldbmeta import LevelDBMeta
from Zyiron_Chain.database.leveldbblocks import LevelDBBlocks



def interactive_menu():
    print("\nBlockchain Query Menu")
    print("1. Query Block by Hash")
    print("2. Query Transaction by ID")
    print("3. Query Block Size by Height")
    print("4. Query Merkle Root by Block Height")
    print("5. Query UTXO")
    print("6. Query Current Block Height")
    print("7. Query Last 5 Blocks")
    print("8. Query Highest Block in the Chain")
    print("9. Query Transactions by ScriptPubKey")
    print("0. Exit")
    return input("Select an option (0-9): ")

class BlockchainQuery:
    def __init__(self):
        self.meta_db = LevelDBMeta()
        self.blocks_db = LevelDBBlocks()

    def query_block_by_hash(self, block_hash):
        metadata = self.meta_db.get_block_metadata(block_hash)
        if metadata:
            block = self.blocks_db.get_block(metadata["file_number"], metadata["byte_offset"])
            self.output_result(block, "Block retrieved successfully.")
        else:
            print(f"Cannot find block with hash {block_hash}.")

    def query_transaction_by_id(self, tx_id):
        transaction = self.meta_db.get_transaction_index(tx_id)
        if transaction:
            self.output_result(transaction, "Transaction retrieved successfully.")
        else:
            print(f"Cannot find transaction {tx_id}.")

    def query_block_size(self, height):
        try:
            heights = [int(key.split(":")[1]) for key in self.meta_db.db if key.startswith("block_index:")]
            if height in heights:
                block_hash = [key.split(":")[1] for key in self.meta_db.db if f"block_index:{height}" in key][0]
                metadata = self.meta_db.get_block_metadata(block_hash)
                block = self.blocks_db.get_block(metadata["file_number"], metadata["byte_offset"])
                block_size = len(json.dumps(block).encode())
                result = {"Block Height": height, "Size (bytes)": block_size}
                self.output_result(result, "Block size retrieved successfully.")
            else:
                print(f"Cannot find block at height {height}.")
        except Exception as e:
            print(f"Error retrieving block size: {e}")

    def query_merkle_root(self, height):
        try:
            heights = [int(key.split(":")[1]) for key in self.meta_db.db if key.startswith("block_index:")]
            if height in heights:
                block_hash = [key.split(":")[1] for key in self.meta_db.db if f"block_index:{height}" in key][0]
                metadata = self.meta_db.get_block_metadata(block_hash)
                block = self.blocks_db.get_block(metadata["file_number"], metadata["byte_offset"])
                merkle_root = block.get("merkle_root", "Not found.")
                result = {"Block Height": height, "Merkle Root": merkle_root}
                self.output_result(result, "Merkle root retrieved successfully.")
            else:
                print(f"Cannot find block at height {height}.")
        except Exception as e:
            print(f"Error retrieving merkle root: {e}")

    def query_utxo(self, tx_id, output_index):
        utxo = self.meta_db.get_utxo(tx_id, output_index)
        if utxo:
            self.output_result(utxo, "UTXO retrieved successfully.")
        else:
            print(f"Cannot find UTXO {tx_id}:{output_index}.")

    def query_current_block_height(self):
        chain_state = self.meta_db.get_chain_state()
        if chain_state:
            self.output_result(chain_state, "Current block height retrieved successfully.")
        else:
            print("Chain state not available.")

    def query_last_n_blocks(self, n=5):
        try:
            heights = sorted([int(key.split(":")[1]) for key in self.meta_db.db if key.startswith("block_index:")], reverse=True)
            blocks = []
            for height in heights[:n]:
                block_hash = [key.split(":")[1] for key in self.meta_db.db if f"block_index:{height}" in key][0]
                metadata = self.meta_db.get_block_metadata(block_hash)
                blocks.append(self.blocks_db.get_block(metadata["file_number"], metadata["byte_offset"]))
            print("Last 5 blocks retrieved successfully.")
            for block in blocks:
                print(json.dumps(block, indent=4))
        except Exception as e:
            print(f"Error retrieving the last blocks: {e}")

    def query_highest_block(self):
        self.query_current_block_height()

    def query_script_pubkey(self, pubkey):
        prefix = f"scriptPubKey:{pubkey}".encode()
        results = []
        for key in self.meta_db.db:
            if key.startswith(prefix):
                try:
                    results.append(json.loads(self.meta_db.db.get(key).decode()))
                except json.JSONDecodeError:
                    print(f"Deserialization error: Could not decode data for scriptPubKey {pubkey}.")
        if results:
            self.output_result(results, "Transactions retrieved successfully.")
        else:
            print(f"Cannot find transactions for scriptPubKey {pubkey}.")

    def output_result(self, data, success_message):
        print(success_message)
        choice = input("Would you like the information in the terminal or as a CSV? (Enter 'terminal' or 'csv'): ").strip().lower()
        if choice == 'csv':
            file_name = input("Enter the file name for the CSV (e.g., output.csv): ").strip()
            self.save_as_csv(data, file_name)
        else:
            print(json.dumps(data, indent=4))

    def save_as_csv(self, data, file_name):
        try:
            if isinstance(data, list):
                with open(file_name, 'w', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
            elif isinstance(data, dict):
                with open(file_name, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    for key, value in data.items():
                        writer.writerow([key, value])
            print(f"Data successfully saved to {file_name}.")
        except Exception as e:
            print(f"Error saving to CSV: {e}")

if __name__ == "__main__":
    blockchain = BlockchainQuery()

    while True:
        choice = interactive_menu()

        if choice == '1':
            block_hash = input("Enter Block Hash: ")
            blockchain.query_block_by_hash(block_hash)
        elif choice == '2':
            tx_id = input("Enter Transaction ID: ")
            blockchain.query_transaction_by_id(tx_id)
        elif choice == '3':
            height = input("Enter Block Height: ")
            blockchain.query_block_size(int(height))
        elif choice == '4':
            height = input("Enter Block Height: ")
            blockchain.query_merkle_root(int(height))
        elif choice == '5':
            tx_id = input("Enter Transaction ID: ")
            output_index = input("Enter Output Index: ")
            blockchain.query_utxo(tx_id, int(output_index))
        elif choice == '6':
            blockchain.query_current_block_height()
        elif choice == '7':
            blockchain.query_last_n_blocks()
        elif choice == '8':
            blockchain.query_highest_block()
        elif choice == '9':
            pubkey = input("Enter ScriptPubKey: ")
            blockchain.query_script_pubkey(pubkey)
        elif choice == '0':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please select a valid option.")
