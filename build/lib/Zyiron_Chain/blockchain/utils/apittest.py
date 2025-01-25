from flask import Flask, request, jsonify
import sqlite3
import json

app = Flask(__name__)
DB_PATH = "blockchain_simulation.db"

def query_database(query, params=()):
    """Helper function to query the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results

@app.route("/blocks", methods=["GET"])
def get_all_blocks():
    """Retrieve all blocks."""
    blocks = query_database("SELECT * FROM blocks")
    return jsonify(blocks)

@app.route("/block/<int:height>", methods=["GET"])
def get_block_by_height(height):
    """Retrieve a block by height."""
    block = query_database("SELECT * FROM blocks WHERE height = ?", (height,))
    return jsonify(block if block else {"error": "Block not found"})

@app.route("/block/hash/<block_hash>", methods=["GET"])
def get_block_by_hash(block_hash):
    """Retrieve a block by its hash."""
    block = query_database("SELECT * FROM blocks WHERE hash = ?", (block_hash,))
    return jsonify(block if block else {"error": "Block not found"})

@app.route("/transactions", methods=["GET"])
def get_all_transactions():
    """Retrieve all transactions."""
    transactions = query_database("SELECT * FROM transactions")
    return jsonify(transactions)

@app.route("/transaction/txid/<txid>", methods=["GET"])
def get_transaction_by_txid(txid):
    """Retrieve a transaction by its txid."""
    transaction = query_database("SELECT * FROM transactions WHERE txid = ?", (txid,))
    return jsonify(transaction if transaction else {"error": "Transaction not found"})

@app.route("/transactions/sender/<sender>", methods=["GET"])
def get_transactions_by_sender(sender):
    """Retrieve transactions by sender."""
    transactions = query_database("SELECT * FROM transactions WHERE sender = ?", (sender,))
    return jsonify(transactions)

@app.route("/export", methods=["GET"])
def export_to_json():
    """Export all blockchain data to JSON."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM blocks")
    blocks = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM transactions")
    transactions = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

    conn.close()

    output = {"blocks": blocks, "transactions": transactions}
    with open("blockchain_data.json", "w") as f:
        json.dump(output, f, indent=4)

    return jsonify({"message": "Blockchain data exported to blockchain_data.json"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
