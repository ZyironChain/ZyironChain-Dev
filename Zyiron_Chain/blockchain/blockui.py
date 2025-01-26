import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from flask import Flask, request, jsonify, render_template
from Zyiron_Chain.database.duckdatabase  import AnalyticsNetworkDB  # Replace with the actual import for your database

# Initialize Flask app
app = Flask(__name__)

# Initialize database connection
db = AnalyticsNetworkDB("analytics_network.duckdb")

@app.route("/")
def home():
    """
    Render the main UI page.
    """
    return render_template("index.html")


@app.route("/api/block", methods=["GET"])
def get_block():
    """
    Fetch block details by block hash.
    """
    block_hash = request.args.get("block_hash")
    if not block_hash:
        return jsonify({"error": "Block hash is required"}), 400

    try:
        block = db.fetch_block_metadata(block_hash)
        if block:
            return jsonify(block)
        else:
            return jsonify({"error": f"Block with hash {block_hash} not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Error fetching block: {str(e)}"}), 500


@app.route("/api/blocks", methods=["GET"])
def list_blocks():
    """
    List all blocks in the database.
    """
    try:
        blocks = db.conn.execute("SELECT * FROM block_metadata").fetchall()
        return jsonify([dict(row) for row in blocks])
    except Exception as e:
        return jsonify({"error": f"Error listing blocks: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)
