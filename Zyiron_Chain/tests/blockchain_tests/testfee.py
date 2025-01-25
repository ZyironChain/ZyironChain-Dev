import sys
import os

# Dynamically add the parent directory of Zyiron_Chain to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)



from Zyiron_Chain.transactions.fees import FeeModel

def interactive_fee_model_test():
    """
    Interactive menu to test the FeeModel with various parameters.
    """
    fee_model = FeeModel()

    print("\nWelcome to the FeeModel Tester!")
    print("You can input different parameters to calculate transaction fees.")

    while True:
        try:
            # Input block size
            block_size = float(input("Enter block size (1-10 MB, including decimals): "))
            if block_size < 1 or block_size > 10:
                print("[ERROR] Block size must be between 1.0 and 10.0 MB, including decimals.")
                continue

            # Input payment type
            print("\nPayment Types:")
            print("1. Standard Payment")
            print("2. Smart Payment")
            print("3. Instant Payment")
            payment_type_map = {1: "Standard", 2: "Smart", 3: "Instant"}
            payment_type_choice = int(input("Select payment type (1-3): "))
            if payment_type_choice not in payment_type_map:
                print("[ERROR] Invalid payment type selected.")
                continue
            payment_type = payment_type_map[payment_type_choice]

            # Input total transaction amount
            total_amount_input = input("Enter total transaction amount in the block: ").replace(",", "")
            total_amount = float(total_amount_input)
            if total_amount <= 0:
                print("[ERROR] Total transaction amount must be greater than zero.")
                continue

            # Calculate transaction size based on payment type
            if payment_type == "Standard":
                tx_size = int(total_amount * 0.15)  # Standard: Smaller transaction size
            elif payment_type == "Smart":
                tx_size = int(total_amount * 0.35)  # Smart: Larger due to smart contract data
            elif payment_type == "Instant":
                tx_size = int(total_amount * 0.25)  # Instant: Includes channel data, moderate size

            # Calculate fee and tax details
            fee_details = fee_model.calculate_fee_and_tax(
                block_size=block_size,
                payment_type=payment_type,
                amount=total_amount,
                tx_size=tx_size
            )

            # Display results
            print("\n[DETAILED REPORT]")
            print(f"Block Size: {block_size:.2f} MB")
            print(f"Payment Type: {payment_type}")
            print(f"Total Transaction Amount: {total_amount:,.2f}")
            print(f"Transaction Size: {tx_size:,} bytes (calculated based on payment type)")
            print(f"Congestion Level: {fee_details['congestion_level']} ({fee_details['scaled_tax_rate']}% Tax)")
            print(f"Fee Per Byte: {fee_details['base_fee'] / tx_size:.6f}")
            print(f"Transaction Fee: {fee_details['base_fee']:,.6f}")
            print(f"Tax Fee: {fee_details['tax_fee']:,.6f} ({fee_details['tax_fee_percentage']}% of Fee)")
            print(f"Net Fee After Tax: {fee_details['miner_fee']:,.6f}")

            fund_allocation = fee_details['fund_allocation']
            print("\n[Fund Allocation]")
            print(f"  Smart Contract Fund: {fund_allocation['Smart Contract Fund']:,.6f}")
            print(f"  Governance Fund: {fund_allocation['Governance Fund']:,.6f}")
            print(f"  Network Contribution Fund: {fund_allocation['Network Contribution Fund']:,.6f}")

        except ValueError as e:
            print(f"[ERROR] Invalid input: {e}")

        # Continue or exit
        again = input("\nDo you want to test another case? (yes/no): ").strip().lower()
        if again not in ["yes", "y"]:
            print("\nExiting the FeeModel Tester. Goodbye!")
            break

if __name__ == "__main__":
    interactive_fee_model_test()
