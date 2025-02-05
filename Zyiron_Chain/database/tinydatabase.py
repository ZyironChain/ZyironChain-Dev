from tinydb import TinyDB, Query
from datetime import datetime


from tinydb import TinyDB, Query
from datetime import datetime

from tinydb import TinyDB, Query
from datetime import datetime

class TinyDBManager:
    def __init__(self, db_path="tinydb.json"):
        """Initialize TinyDB and create tables"""
        self.db = TinyDB(db_path)  # ✅ Keep database open
        self.node_table = self.db.table("node_configurations")
        self.session_table = self.db.table("session_data")
        self.peer_table = self.db.table("peers")

    def get_all_peers(self):
        """Fetch all peers from the TinyDB 'peers' table."""
        return self.peer_table.all()

    def add_peer(self, peer_address, port):
        """Add a peer to the TinyDB 'peers' table."""
        self.peer_table.insert({"peer_address": peer_address, "port": port})

    def add_node_configuration(self, node_id, peer_address, port, network, role):
        """Add a new node configuration."""
        self.node_table.insert({
            "node_id": node_id,
            "peer_address": peer_address,
            "port": port,
            "network": network,
            "role": role
        })

    def update_node_configuration(self, node_id, updates):
        """Update a node configuration by node_id."""
        query = Query()
        self.node_table.update(updates, query.node_id == node_id)

    def fetch_node_configuration(self, node_id):
        """Fetch a node configuration by node_id."""
        query = Query()
        return self.node_table.search(query.node_id == node_id)

    def delete_node_configuration(self, node_id):
        """Delete a node configuration by node_id."""
        query = Query()
        self.node_table.remove(query.node_id == node_id)

    def fetch_all_nodes(self):
        """Fetch all node configurations."""
        return self.node_table.all()

    def add_session_data(self, session_id, node_id, last_activity, active_connections):
        """Add session data."""
        self.session_table.insert({
            "session_id": session_id,
            "node_id": node_id,
            "last_activity": last_activity,
            "active_connections": active_connections
        })

    def update_session_data(self, session_id, updates):
        """Update session data by session_id."""
        query = Query()
        self.session_table.update(updates, query.session_id == session_id)

    def fetch_session_data(self, session_id):
        """Fetch session data by session_id."""
        query = Query()
        return self.session_table.search(query.session_id == session_id)

    def delete_session_data(self, session_id):
        """Delete session data by session_id."""
        query = Query()
        self.session_table.remove(query.session_id == session_id)

    def fetch_all_sessions(self):
        """Fetch all session data."""
        return self.session_table.all()

    def clear_all_data(self):
        """Clear all tables."""
        self.node_table.truncate()
        self.session_table.truncate()
        self.peer_table.truncate()

    def close(self):
        """Close the TinyDB database."""
        self.db.close()


# Example Usage
if __name__ == "__main__":
    db_manager = TinyDBManager()

    # Add Node Configurations
    db_manager.add_node_configuration("node1", "192.168.1.1", 8333, "mainnet", "full")
    db_manager.add_node_configuration("node2", "192.168.1.2", 18333, "testnet", "validator")
    print("All Nodes:", db_manager.fetch_all_nodes())

    # Update Node Configuration
    db_manager.update_node_configuration("node1", {"role": "miner"})
    print("Updated Node Configuration:", db_manager.fetch_node_configuration("node1"))

    # Add Session Data
    db_manager.add_session_data("session1", "node1", datetime.now().isoformat(), 5)
    db_manager.add_session_data("session2", "node2", datetime.now().isoformat(), 10)
    print("All Sessions:", db_manager.fetch_all_sessions())

    # Update Session Data
    db_manager.update_session_data("session1", {"active_connections": 8})
    print("Updated Session Data:", db_manager.fetch_session_data("session1"))

    # Delete Node and Session Data
    db_manager.delete_node_configuration("node2")
    db_manager.delete_session_data("session2")
    print("Nodes After Deletion:", db_manager.fetch_all_nodes())
    print("Sessions After Deletion:", db_manager.fetch_all_sessions())

    # Clear all data
    db_manager.clear_all_data()
    print("After Clearing Data:")
    print("Nodes:", db_manager.fetch_all_nodes())
    print("Sessions:", db_manager.fetch_all_sessions())

    # Close the database
    db_manager.close()
