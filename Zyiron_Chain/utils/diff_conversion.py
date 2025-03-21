import sys
import os
from typing import List, Optional
# Adjust Python path for project structure
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)
from typing import Union

from typing import Union

from typing import Union

class DifficultyConverter:
    """
    Utility class to convert and standardize blockchain difficulty values.
    Supports int, str, bytes, and bytearray inputs, and ensures a
    consistent 96-character hex string output.
    """

    @staticmethod
    def convert(difficulty: Union[int, str, bytes, bytearray]) -> str:
        """
        Converts the input difficulty into a standardized 96-character hex string.

        Args:
            difficulty (Union[int, str, bytes, bytearray]): Difficulty to convert.

        Returns:
            str: 96-character hex string representing the difficulty.

        Raises:
            ValueError: If the input is invalid or cannot be converted.
        """
        try:
            # Integer input
            if isinstance(difficulty, int):
                if difficulty < 0:
                    raise ValueError("Difficulty integer cannot be negative.")
                return f"{difficulty:0>96x}"

            # String input
            elif isinstance(difficulty, str):
                difficulty = difficulty.strip().lower()
                if difficulty.startswith("0x"):
                    difficulty = difficulty[2:]
                if not all(c in "0123456789abcdef" for c in difficulty):
                    raise ValueError("Hex string contains invalid characters.")
                if len(difficulty) > 96:
                    raise ValueError("Hex string exceeds 96 characters.")
                return difficulty.zfill(96)

            # Bytes or Bytearray input
            elif isinstance(difficulty, (bytes, bytearray)):
                hex_str = difficulty.hex()
                if len(hex_str) > 96:
                    raise ValueError("Byte input exceeds 96-character hex length.")
                return hex_str.zfill(96)

            else:
                raise ValueError(f"Unsupported difficulty type: {type(difficulty)}")

        except Exception as e:
            print(f"[DifficultyConverter.convert] ❌ ERROR: Failed to convert difficulty ({difficulty}): {e}")
            raise

    @staticmethod
    def to_standard_hex(difficulty: Union[int, str, bytes, bytearray]) -> str:
        """
        Alias for convert() for compatibility with other modules expecting this method.
        """
        return DifficultyConverter.convert(difficulty)
    


    @staticmethod
    def to_hex(value: int) -> str:
        """
        Converts an integer difficulty value to a 96-character zero-padded hex string.
        """
        return hex(value)[2:].zfill(96)  # strip "0x" and pad

    @staticmethod
    def from_hex(hex_str: str) -> int:
        """
        Converts a 96-character hex difficulty string back to integer.
        """
        return int(hex_str, 16)

