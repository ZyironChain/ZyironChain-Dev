import os

def create_structure(base_path, structure):
    """Creates the directory and file structure based on a nested dictionary."""
    for name, content in structure.items():
        path = os.path.join(base_path, name)
        if isinstance(content, dict):
            os.makedirs(path, exist_ok=True)
            create_structure(path, content)
        else:
            with open(path, "w") as f:
                f.write(content)

# Define the complete structure
structure = {
    "blockchain": {
        "__init__.py": "# Initializes the blockchain package",
        "block.py": "# Defines block structure (hashing, timestamp, nonce)",
        "blockchain.py": "# Manages the blockchain (chain structure, validation)",
        "consensus.py": "# Implements Proof-of-Work (mining and validation)",
        "cryptography_utils.py": "# Handles SPHINCS+, Falcon, Kyber algorithms",
        "wallet.py": "# Wallet creation, signing, and private/public keys",
        "transaction.py": "# Defines transaction structure and validation",
        "data_storage.py": "# Manages JSON dumps for blockchain and transactions",
        "network": {
            "__init__.py": "# Initializes the networking subpackage",
            "node.py": "# Node setup and P2P communication logic",
            "peer_manager.py": "# Manages peer connections and discovery",
            "messaging.py": "# Message protocols and data exchange format",
        },
        "utils": {
            "__init__.py": "# Initializes the utilities subpackage",
            "hashing.py": "# Helper functions for hashing (e.g., SHA-3)",
            "serialization.py": "# Functions for serializing/deserializing data",
        },
    },
    "backend": {
        "__init__.py": "# Initializes the backend package",
        "app.py": "# Main API server (Flask or FastAPI)",
        "routes": {
            "__init__.py": "# Initializes the routes subpackage",
            "wallet_routes.py": "# API endpoints for wallet operations",
            "transaction_routes.py": "# API endpoints for transactions",
            "block_routes.py": "# API endpoints for blockchain data",
            "admin_routes.py": "# API endpoints for admin and monitoring tasks",
        },
        "utils": {
            "__init__.py": "# Initializes the backend utilities",
            "database.py": "# Manages database connections and queries (if used)",
            "security.py": "# Handles token validation and rate limiting",
            "blockchain_adapter.py": "# Interfaces between the backend and blockchain",
        },
    },
    "frontend": {
        "web": {
            "public": {},  # Static files (e.g., index.html, favicon)
            "src": {
                "components": {},  # Reusable UI components
                "pages": {},  # Page-level components
                "services": {},  # API service calls for the front end
                "utils": {},  # Front-end utility functions
                "App.js": "// Main React app file",
                "index.js": "// Entry point for the React application",
            },
            "package.json": '{ "name": "kyiron-web", "version": "1.0.0" }',
        },
        "mobile": {},  # Mobile application (React Native or Kivy)
    },
    "tests": {
        "blockchain_tests": {
            "test_block.py": "# Tests for block creation and hashing",
            "test_blockchain.py": "# Tests for chain validation",
            "test_consensus.py": "# Tests for Proof-of-Work mechanism",
            "test_transaction.py": "# Tests for transaction validation",
        },
        "backend_tests": {
            "test_wallet_routes.py": "# Tests for wallet-related APIs",
            "test_transaction_routes.py": "# Tests for transaction-related APIs",
            "test_block_routes.py": "# Tests for blockchain data APIs",
        },
        "frontend_tests": {
            "__init__.py": "# Initialize frontend tests package",
        },
    },
    "scripts": {
        "deploy.py": "# Script for deploying the application",
        "reset_blockchain.py": "# Script to reset or clear the blockchain",
        "generate_genesis_block.py": "# Generates the genesis block for the chain",
        "performance_tests.py": "# Tests for blockchain performance",
        "monitoring.py": "# Script for monitoring blockchain health",
    },
    "docs": {
        "architecture.md": "# High-level system architecture",
        "blockchain_spec.md": "# Technical details of the blockchain",
        "api_reference.md": "# API documentation",
        "setup_guide.md": "# Setup instructions for developers",
        "faq.md": "# Frequently Asked Questions",
    },
    "requirements.txt": "# Python dependencies",
    ".gitignore": "# Git ignore file",
    "README.md": "# Project overview and instructions",
}

# Create the structure
base_path = "kyiron_chain"
create_structure(base_path, structure)
print(f"Project structure created at '{base_path}'!")
