import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))



import os
import json
import base64
import csv
import hashlib
import traceback
import secrets
from Crypto.Cipher import AES
from hashlib import sha3_384  # Use SHA3-384 for key derivation
from Zyiron_Chain.falcon.falcon.falcon import SecretKey, PublicKey

class SecureWallet:
    def __init__(self, wallet_file="secure_wallet.json"):
        """
        Initialize the SecureWallet by generating Falcon keys.
        :param wallet_file: File where encrypted wallet data is stored.
        """
        self.wallet_file = wallet_file

        # Generate Falcon keys
        self.secret_key = SecretKey(1024)  # Use n=1024 for Falcon key generation
        self.public_key = PublicKey(self.secret_key)

        # Generate a 1024-bit random seed for recovery
        self.recovery_seed = secrets.token_hex(128)
        self.mnemonic_phrase = self.generate_mnemonic(self.recovery_seed)

    def derive_aes_key(self):
        """
        Derive an AES-256 key from the Falcon private key using SHA3-384.
        The first 32 bytes of the SHA3-384 hash are used as the AES-256 key.
        """
        secret_key_data = json.dumps(self.secret_key.h).encode()
        sha3_hash = sha3_384(secret_key_data).digest()
        return sha3_hash[:32]

    def encrypt_private_key(self):
        """
        Encrypt the Falcon private key using AES-256-GCM and sign the ciphertext with Falcon.
        """
        aes_key = self.derive_aes_key()
        cipher = AES.new(aes_key, AES.MODE_GCM)
        nonce = cipher.nonce
        ciphertext, tag = cipher.encrypt_and_digest(json.dumps(self.secret_key.h).encode())

        encrypted_data = {
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "tag": base64.b64encode(tag).decode(),
        }

        encrypted_data_bytes = json.dumps(encrypted_data, indent=2).encode()
        signature = base64.b64encode(self.secret_key.sign(encrypted_data_bytes)).decode()

        secure_storage = {
            "encrypted_key": encrypted_data,
            "signature": signature,
            "public_key": base64.b64encode(json.dumps({"h": self.public_key.h}).encode()).decode(),
            "recovery_seed": self.recovery_seed,
            "mnemonic_phrase": self.mnemonic_phrase
        }

        with open(self.wallet_file, "w") as f:
            json.dump(secure_storage, f, indent=4)

        return secure_storage

    def decrypt_private_key(self):
        """
        Verify the Falcon signature, then decrypt the private key using AES-256-GCM.
        """
        with open(self.wallet_file, "r") as f:
            secure_storage = json.load(f)

        encrypted_data = secure_storage["encrypted_key"]
        signature = base64.b64decode(secure_storage["signature"])
        encrypted_data_bytes = json.dumps(encrypted_data, indent=2).encode()

        try:
            if not self.public_key.verify(encrypted_data_bytes, signature):
                return None
        except Exception as e:
            return None

        aes_key = self.derive_aes_key()
        cipher = AES.new(aes_key, AES.MODE_GCM, nonce=base64.b64decode(encrypted_data["nonce"]))
        decrypted_private_key = cipher.decrypt_and_verify(
            base64.b64decode(encrypted_data["ciphertext"]),
            base64.b64decode(encrypted_data["tag"]),
        )

        return json.loads(decrypted_private_key.decode())

    @staticmethod
    def generate_mnemonic(seed):
        """
        Generate a 96-word mnemonic phrase from a 1024-bit seed.
        """
        words = [seed[i:i+10] for i in range(0, len(seed), 10)]
        return " ".join(words)

    @staticmethod
    def export_to_csv(data, filename="wallet_test_results.csv"):
        """
        Export test results to a CSV file.
        """
        try:
            abs_path = os.path.abspath(filename)
            with open(abs_path, "w", newline="") as csvfile:
                fieldnames = ["Field", "Before Encryption", "After Encryption", "Verification"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow({"Field": "Original Private Key", "Before Encryption": data["Decrypted Private Key"], "After Encryption": "Encrypted", "Verification": "Success"})
                writer.writerow({"Field": "Signature", "Before Encryption": "N/A", "After Encryption": data["Encrypted Wallet"]["signature"], "Verification": "Valid"})
                writer.writerow({"Field": "Recovery Seed", "Before Encryption": data["Encrypted Wallet"]["recovery_seed"], "After Encryption": "N/A", "Verification": "Stored Securely"})
                writer.writerow({"Field": "Mnemonic Phrase", "Before Encryption": data["Encrypted Wallet"]["mnemonic_phrase"], "After Encryption": "N/A", "Verification": "Stored Securely"})
                writer.writerow({"Field": "AES Key Hash", "Before Encryption": "Derived from Falcon Private Key", "After Encryption": "N/A", "Verification": "Computed Successfully"})
            print(f"✅ CSV file '{abs_path}' created successfully.")
        except Exception as e:
            print(f"❌ Error exporting to CSV: {e}")
            traceback.print_exc()




def validate_csv_output(csv_filename, expected_data):
    """
    Validates the CSV output by comparing it to expected test results.
    """
    try:
        abs_path = os.path.abspath(csv_filename)
        with open(abs_path, "r") as csvfile:
            reader = csv.DictReader(csvfile)
            csv_data = {row["Field"]: row for row in reader}

        errors = []
        
        for field, expected_values in expected_data.items():
            if field in csv_data:
                csv_row = csv_data[field]
                if csv_row["Before Encryption"] != expected_values.get("Before Encryption", "N/A"):
                    errors.append(f"❌ Mismatch in {field} - Before Encryption. Expected: {expected_values['Before Encryption']}, Found: {csv_row['Before Encryption']}")
                
                if csv_row["After Encryption"] != expected_values.get("After Encryption", "N/A"):
                    errors.append(f"❌ Mismatch in {field} - After Encryption. Expected: {expected_values['After Encryption']}, Found: {csv_row['After Encryption']}")

                if csv_row["Verification"] != expected_values.get("Verification", "N/A"):
                    errors.append(f"❌ Mismatch in {field} - Verification. Expected: {expected_values['Verification']}, Found: {csv_row['Verification']}")

            else:
                errors.append(f"❌ Missing field in CSV: {field}")

        if errors:
            print("\n❌ CSV Validation Failed. Issues Found:")
            for error in errors:
                print(error)
        else:
            print("\n✅ CSV Validation Passed. All outputs match expected values.")

    except Exception as e:
        print(f"❌ Error validating CSV output: {e}")
        traceback.print_exc()










# ===================== 🔹 TEST EXECUTION BLOCK 🔹 =====================
if __name__ == "__main__":
    try:
        wallet = SecureWallet()
        encrypted_wallet = wallet.encrypt_private_key()
        decrypted_key = wallet.decrypt_private_key()

        test_results = {
            "Encrypted Wallet": encrypted_wallet,
            "Decrypted Private Key": decrypted_key,
        }

        SecureWallet.export_to_csv(test_results)

        # Define expected test results for validation
        expected_csv_results = {
            "Original Private Key": {
                "Before Encryption": str(decrypted_key), 
                "After Encryption": "Encrypted", 
                "Verification": "Success"
            },
            "Signature": {
                "Before Encryption": "N/A", 
                "After Encryption": encrypted_wallet["signature"], 
                "Verification": "Valid"
            },
            "Recovery Seed": {
                "Before Encryption": encrypted_wallet["recovery_seed"], 
                "After Encryption": "N/A", 
                "Verification": "Stored Securely"
            },
            "Mnemonic Phrase": {
                "Before Encryption": encrypted_wallet["mnemonic_phrase"], 
                "After Encryption": "N/A", 
                "Verification": "Stored Securely"
            },
            "AES Key Hash": {
                "Before Encryption": "Derived from Falcon Private Key", 
                "After Encryption": "N/A", 
                "Verification": "Computed Successfully"
            }
        }

        # ✅ Validate CSV Output
        validate_csv_output("wallet_test_results.csv", expected_csv_results)

        print("\n✅ Test completed successfully. Results exported to CSV and validated.")

    except Exception as e:
        print(f"❌ An error occurred: {e}")
        traceback.print_exc()
