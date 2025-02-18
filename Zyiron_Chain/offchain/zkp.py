







import hashlib
import secrets
import secrets
import hashlib

class ZKP:
    """Zero-Knowledge Proof System"""

    def __init__(self):
        """Initialize the ZKP system with generated public parameters."""
        self.public_parameters = self.generate_public_parameters()

    def generate_public_parameters(self):
        """
        Generate public parameters for the Zero-Knowledge Proof system.
        - Securely defines a prime field and generator.
        """
        # ✅ Securely define the prime for the field
        prime = 2**256 - 2**224 + 2**192 + 2**96 - 1  # Example large prime (similar to secp256r1)

        # ✅ Choose a generator in the prime field (3 is a commonly used generator)
        generator = 3
        return {"prime": prime, "generator": generator}

    def generate_proof(self, secret_preimage: str):
        """
        Generate a Zero-Knowledge Proof (ZKP) that proves knowledge of `single_hash`
        without revealing it.

        :param secret_preimage: The secret preimage as a hexadecimal string.
        :return: A dictionary containing the proof: {commitment, challenge, response}.
        """
        if not secret_preimage or not isinstance(secret_preimage, str):
            raise ValueError("[ERROR] Invalid secret preimage. Must be a non-empty hexadecimal string.")

        p = self.public_parameters["prime"]
        g = self.public_parameters["generator"]

        # ✅ Generate a secure random nonce in the field
        nonce = secrets.randbelow(p)
        if nonce == 0:
            raise ValueError("[ERROR] Nonce must be non-zero.")

        # ✅ Compute commitment: C = g^nonce mod p
        commitment = pow(g, nonce, p)

        # ✅ Compute challenge: H(commitment, single_hash) mod p
        challenge = int(hashlib.sha3_384(f"{commitment}{secret_preimage}".encode()).hexdigest(), 16) % p

        # ✅ Compute response: response = nonce - challenge * secret_preimage mod p
        try:
            secret_preimage_int = int(secret_preimage, 16)
        except ValueError:
            raise ValueError("[ERROR] Invalid secret preimage format. Must be a hexadecimal string.")

        response = (nonce - challenge * secret_preimage_int) % p

        return {"commitment": commitment, "challenge": challenge, "response": response}

    def verify_proof(self, proof: dict, expected_hash: str):
        """
        Verify a Zero-Knowledge Proof (ZKP).

        :param proof: The proof dictionary containing commitment, challenge, and response.
        :param expected_hash: The expected secret hash as a hexadecimal string.
        :return: True if the proof is valid, False otherwise.
        """
        if not all(k in proof for k in ["commitment", "challenge", "response"]):
            raise ValueError("[ERROR] Proof must include 'commitment', 'challenge', and 'response'.")

        if not expected_hash or not isinstance(expected_hash, str):
            raise ValueError("[ERROR] Expected hash must be a non-empty hexadecimal string.")

        p = self.public_parameters["prime"]
        g = self.public_parameters["generator"]

        # ✅ Recalculate commitment from challenge and response
        recalculated_commitment = (
            pow(g, proof["response"], p) * pow(int(expected_hash, 16), proof["challenge"], p)
        ) % p

        # ✅ Check if recalculated commitment matches original
        return recalculated_commitment == proof["commitment"]
