import random
import math

# Compression and decompression routines for signatures
def compress(v, slen):
    """
    Take as input a list of integers v and a bytelength slen, and
    return a bytestring of length slen that encode/compress v.
    If this is not possible, return False.
    """
    u = ""
    for coef in v:
        # Encode the sign
        s = "1" if coef < 0 else "0"
        # Encode the low bits
        s += format((abs(coef) % (1 << 7)), '#09b')[2:]
        # Encode the high bits
        s += "0" * (abs(coef) >> 7) + "1"
        u += s
    # The encoding is too long
    if len(u) > 8 * slen:
        return False
    u += "0" * (8 * slen - len(u))
    w = [int(u[8 * i: 8 * i + 8], 2) for i in range(len(u) // 8)]
    x = bytes(w)
    return x

def decompress(x, slen, n):
    """
    Take as input an encoding x, a bytelength slen and a length n, and
    return a list of integers v of length n such that x encode v.
    If such a list does not exist, the encoding is invalid and we output False.
    """
    if not x or len(x) > slen:
        print("Too long")
        return False
    w = list(x)
    u = ""
    for elt in w:
        u += bin((1 << 8) ^ elt)[3:]
    v = []

    # Remove the last bits
    while u[-1] == "0":
        u = u[:-1]

    try:
        while u != "" and len(v) < n:
            # Recover the sign of coef
            sign = -1 if u[0] == "1" else 1
            # Recover the 7 low bits of abs(coef)
            low = int(u[1:8], 2)
            i, high = 8, 0
            # Recover the high bits of abs(coef)
            while u[i] == "0":
                i += 1
                high += 1
            # Compute coef
            coef = sign * (low + (high << 7))
            # Enforce a unique encoding for coef = 0
            if coef == 0 and sign == -1:
                return False
            # Store intermediate results
            v.append(coef)
            u = u[i + 1:]
        # In this case, the encoding is invalid
        if len(v) != n:
            return False
        return v
    except IndexError:
        return False

class PublicKey:
    """Mock public key representation."""
    def __init__(self, key):
        self.key = key

    def __repr__(self):
        return f"PublicKey: {self.key[:10]}... (truncated)"

class PrivateKey:
    """Mock private key representation."""
    def __init__(self, key):
        self.key = key

    def __repr__(self):
        return f"PrivateKey: {self.key[:10]}... (truncated)"

def calculate_slen(data):
    """Dynamically calculate `slen` based on the input data."""
    # Estimate bits needed for encoding
    bits_needed = sum(1 + 7 + (math.ceil(abs(coef) / (1 << 7))) for coef in data)
    # Convert bits to bytes and add a buffer
    return math.ceil(bits_needed / 8) + 10  # Adding a buffer

if __name__ == "__main__":
    # Key generation for testing
    key_length = 256  # Adjust key length for testing
    private_key = PrivateKey([random.randint(-10000, 10000) for _ in range(key_length)])
    public_key = PublicKey([random.randint(-10000, 10000) for _ in range(key_length)])

    print("Original Keys:")
    print(f"Private Key: {private_key}")
    print(f"Public Key: {public_key}")

    # Calculate dynamic `slen`
    private_key_slen = calculate_slen(private_key.key)
    public_key_slen = calculate_slen(public_key.key)

    # Compress the private key
    compressed_private_key = compress(private_key.key, private_key_slen)
    compressed_public_key = compress(public_key.key, public_key_slen)

    if compressed_private_key:
        print(f"Compressed Private Key: {compressed_private_key[:10]}... (truncated)")
        print(f"Compressed size (Private Key): {len(compressed_private_key)} bytes")
    else:
        print("Compression failed for Private Key; data too large for specified length.")

    if compressed_public_key:
        print(f"Compressed Public Key: {compressed_public_key[:10]}... (truncated)")
        print(f"Compressed size (Public Key): {len(compressed_public_key)} bytes")
    else:
        print("Compression failed for Public Key; data too large for specified length.")

    # Decompress the private key
    if compressed_private_key:
        decompressed_private_key = decompress(compressed_private_key, private_key_slen, len(private_key.key))
        if decompressed_private_key:
            print(f"Decompressed Private Key matches original: {decompressed_private_key == private_key.key}")
        else:
            print("Decompression failed for Private Key; invalid encoding.")

    if compressed_public_key:
        decompressed_public_key = decompress(compressed_public_key, public_key_slen, len(public_key.key))
        if decompressed_public_key:
            print(f"Decompressed Public Key matches original: {decompressed_public_key == public_key.key}")
        else:
            print("Decompression failed for Public Key; invalid encoding.")

    # Test with a mock signature
    original_signature = [random.randint(-1024, 1024) for _ in range(10)]  # Example signature values
    signature_slen = calculate_slen(original_signature)
    compressed_signature = compress(original_signature, signature_slen)

    print("\nOriginal Signature:")
    print(f"Signature: {original_signature}")

    if compressed_signature:
        print(f"Compressed Signature: {compressed_signature}")
        print(f"Compressed size (Signature): {len(compressed_signature)} bytes")
        decompressed_signature = decompress(compressed_signature, signature_slen, len(original_signature))
        if decompressed_signature:
            print(f"Decompressed Signature matches original: {decompressed_signature == original_signature}")
        else:
            print("Decompression failed for Signature; invalid encoding.")
    else:
        print("Compression failed for Signature; data too large for specified length.")
