import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))




def int_to_little_endian(value: int, length: int) -> bytes:
    return value.to_bytes(length, "little")


def little_endian_to_int(data: bytes) -> int:
    return int.from_bytes(data, "little")




