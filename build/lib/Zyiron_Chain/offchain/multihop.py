import heapq
from collections import defaultdict

class NetworkGraph:
    def __init__(self):
        """
        Initialize the network graph.
        """
        self.nodes = set()
        self.edges = {}  # (node_a, node_b): {"distance": x}

    def add_channel(self, node_a, node_b, distance):
        """
        Add a channel to the network graph.
        :param node_a: First node.
        :param node_b: Second node.
        :param distance: Distance or cost between the nodes.
        """
        self.nodes.add(node_a)
        self.nodes.add(node_b)
        self.edges[(node_a, node_b)] = {"distance": distance}
        self.edges[(node_b, node_a)] = {"distance": distance}

    def get_neighbors(self, node):
        """
        Get neighboring nodes for a given node.
        :param node: Node to get neighbors for.
        :return: List of neighboring nodes.
        """
        return [neighbor for (a, neighbor) in self.edges if a == node]

    def find_advanced_path(self, start, end, algorithm="dijkstra"):
        """
        Find a path between two nodes using the specified algorithm.
        :param start: Starting node.
        :param end: Target node.
        :param algorithm: Algorithm to use (default: "dijkstra").
        :return: List of nodes representing the path.
        """
        if algorithm == "dijkstra":
            return self._dijkstra_path(start, end)
        elif algorithm == "astar":
            return self._astar_path(start, end)
        else:
            raise ValueError(f"[ERROR] Unsupported algorithm: {algorithm}")

    def _dijkstra_path(self, start, end):
        """
        Dijkstra's algorithm for finding the shortest path.
        """
        distances = {node: float('inf') for node in self.nodes}
        previous_nodes = {node: None for node in self.nodes}
        distances[start] = 0
        priority_queue = [(0, start)]

        while priority_queue:
            current_distance, current_node = heapq.heappop(priority_queue)

            if current_distance > distances[current_node]:
                continue

            for neighbor in self.get_neighbors(current_node):
                edge = self.edges[(current_node, neighbor)]
                new_distance = current_distance + edge["distance"]
                if new_distance < distances[neighbor]:
                    distances[neighbor] = new_distance
                    previous_nodes[neighbor] = current_node
                    heapq.heappush(priority_queue, (new_distance, neighbor))

        # Reconstruct the path
        path = []
        current = end
        while current:
            path.append(current)
            current = previous_nodes[current]
        path.reverse()
        if not path or path[0] != start:
            raise ValueError(f"No path found from {start} to {end}.")
        return path

    def _astar_path(self, start, end):
        """
        A* algorithm for finding the shortest path.
        """
        def heuristic(node, target):
            # Placeholder heuristic function
            return abs(hash(node) - hash(target)) % 100

        open_set = {start}
        came_from = {}
        g_score = {node: float('inf') for node in self.nodes}
        g_score[start] = 0
        f_score = {node: float('inf') for node in self.nodes}
        f_score[start] = heuristic(start, end)

        while open_set:
            current = min(open_set, key=lambda node: f_score[node])
            if current == end:
                # Reconstruct path
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                path.reverse()
                return path

            open_set.remove(current)
            for neighbor in self.get_neighbors(current):
                tentative_g_score = g_score[current] + self.edges[(current, neighbor)]["distance"]
                if tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + heuristic(neighbor, end)
                    if neighbor not in open_set:
                        open_set.add(neighbor)

        raise ValueError(f"No path found from {start} to {end}.")

class MultiHop:
    def __init__(self):
        """
        Initialize the MultiHop instance.
        """
        self.network = NetworkGraph()  # Graph to manage channels and nodes
        self.batched_transactions = defaultdict(list)  # Batches of transactions grouped by path

    def add_channel(self, node_a, node_b, distance):
        """
        Add an open channel to the network graph.
        :param node_a: Starting node.
        :param node_b: Ending node.
        :param distance: Cost or distance between nodes.
        """
        self.network.add_channel(node_a, node_b, distance)

    def find_shortest_path(self, start, end):
        """
        Find the shortest path using Dijkstra's algorithm.
        :param start: Starting node.
        :param end: Target node.
        :return: List of nodes representing the shortest path.
        """
        return self.network.find_advanced_path(start, end, algorithm="dijkstra")

    def batch_transactions(self, transactions):
        """
        Batch transactions going through the same path.
        :param transactions: List of transactions in the format (sender, recipient, amount).
        :return: Batched transactions grouped by path.
        """
        for tx in transactions:
            sender, recipient, amount = tx
            path = tuple(self.find_shortest_path(sender, recipient))
            self.batched_transactions[path].append(tx)
        return self.batched_transactions

    def forward_batches(self):
        """
        Forward batched transactions along their respective paths.
        """
        for path, batch in self.batched_transactions.items():
            print(f"Forwarding batch along path {path}:")
            for tx in batch:
                sender, recipient, amount = tx
                print(f"  Transaction: {sender} -> {recipient}, Amount: {amount}")

    def execute_multi_hop(self, transactions):
        """
        Execute multi-hop payments with batching.
        :param transactions: List of transactions in the format (sender, recipient, amount).
        """
        # Batch transactions by path
        self.batch_transactions(transactions)
        # Forward each batch along its path
        self.forward_batches()
