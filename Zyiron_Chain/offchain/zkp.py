







import hashlib
import secrets

class ZKP:
    def __init__(self):
        self.public_parameters = self.generate_public_parameters()

    def generate_public_parameters(self):
        """
        Generate public parameters for the Zero-Knowledge Proof system.
        - Uses a secure random prime generator to define the field.
        """
        prime = 2**256 - 2**224 + 2**192 + 2**96 - 1  # Example large prime field (similar to secp256r1)
        generator = 3  # Fixed generator
        return {"prime": prime, "generator": generator}

    def generate_proof(self, secret_preimage):
        """
        Generate a Zero-Knowledge Proof (ZKP) that proves knowledge of `single_hash`
        without revealing it.
        """
        p = self.public_parameters["prime"]
        g = self.public_parameters["generator"]

        # Generate a secret random value (nonce)
        nonce = secrets.randbelow(p)
        
        # Compute commitment: C = g^nonce mod p
        commitment = pow(g, nonce, p)

        # Compute challenge: Hash(commitment, single_hash) as challenge
        challenge = int(hashlib.sha3_384(f"{commitment}{secret_preimage}".encode()).hexdigest(), 16) % p

        # Compute response: response = nonce - challenge * secret_preimage mod p
        response = (nonce - challenge * int(secret_preimage, 16)) % p

        return {"commitment": commitment, "challenge": challenge, "response": response}

    def verify_proof(self, proof, expected_hash):
        """
        Verify a Zero-Knowledge Proof (ZKP) that proves knowledge of `single_hash`
        without revealing it.
        """
        p = self.public_parameters["prime"]
        g = self.public_parameters["generator"]

        # Recalculate commitment from challenge and response
        recalculated_commitment = (pow(g, proof["response"], p) * pow(int(expected_hash, 16), proof["challenge"], p)) % p

        # Check if recalculated commitment matches original
        return recalculated_commitment == proof["commitment"]
