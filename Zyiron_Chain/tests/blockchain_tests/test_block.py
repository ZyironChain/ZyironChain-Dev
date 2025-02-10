import sys
import os

# Add the project root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))



import unittest
from Zyiron_Chain.blockchain.block import Block, BlockHeader


class TestBlock(unittest.TestCase):
    def setUp(self):
        self.block = Block(
            index=1,
            previous_hash="0" * 64,
            transactions=["Alice pays Bob 5 coins", "Bob pays Charlie 2 coins"]
        )
        print(f"Setup Block: {self.block}")

    def test_set_header(self):
        merkle_root = "abc123def4567890abcdef1234567890abcdef1234567890abcdef1234567890"
        self.block.set_header(version=1, merkle_root=merkle_root)
        print(f"Set Header: {self.block.header}")
        self.assertIsNotNone(self.block.header)
        self.assertEqual(self.block.header.merkle_root, merkle_root)

    def test_calculate_hash(self):
        self.block.set_header(
            version=1,
            merkle_root="abc123def4567890abcdef1234567890abcdef1234567890abcdef1234567890"
        )
        hash_value = self.block.calculate_hash()
        print(f"Calculated Hash: {hash_value}")
        self.assertIsInstance(hash_value, str)
        self.assertNotEqual(hash_value, "")

    def test_mine(self):
        self.block.set_header(
            version=1,
            merkle_root="abc123def4567890abcdef1234567890abcdef1234567890abcdef1234567890"
        )
        target = 2 ** 240
        newBlockAvailable = False
        print(f"Start Mining: Target={target}, NewBlockAvailable={newBlockAvailable}")
        result = self.block.mine(target, newBlockAvailable)
        print(f"Mining Result: {result}, Nonce={self.block.header.nonce}, Hash={self.block.header.calculate_hash()}")
        self.assertTrue(result)
        self.assertTrue(self.block.header.nonce > 0)
        self.assertTrue(
            int(self.block.header.calculate_hash(), 16) <= target
        )

if __name__ == "__main__":
    print("Running Block Tests...")
    unittest.main()
