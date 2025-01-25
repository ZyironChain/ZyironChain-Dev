import json
import os

class LevelDBBlocks:
    def __init__(self, data_dir='./block_data'):
        self.data_dir = data_dir
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def store_block(self, block, file_number):
        block_binary = json.dumps(block).encode()
        file_path = os.path.join(self.data_dir, f"blk{file_number:05}.dat")
        with open(file_path, "ab") as f:
            byte_offset = f.tell()
            f.write(block_binary + b"\n")
        return {"file_number": file_number, "byte_offset": byte_offset}

    def get_block(self, file_number, byte_offset):
        file_path = os.path.join(self.data_dir, f"blk{file_number:05}.dat")
        with open(file_path, "rb") as f:
            f.seek(byte_offset)
            block_binary = f.readline()
        return json.loads(block_binary.decode())

    def store_undo_data(self, block_hash, undo_data):
        undo_path = os.path.join(self.data_dir, f"undo_{block_hash}.dat")
        with open(undo_path, "w") as f:
            json.dump(undo_data, f)

    def get_undo_data(self, block_hash):
        undo_path = os.path.join(self.data_dir, f"undo_{block_hash}.dat")
        try:
            with open(undo_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Undo data for block {block_hash} not found.")
            return None
